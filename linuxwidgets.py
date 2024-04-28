#!/usr/bin/env python3
from PyQt6 import QtCore
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QPixmap
from time import time
from pywidgets.widgets import _MediaListFramework, _MediaFramework, QWidget
from PyQt6.QtDBus import QDBusConnection, QDBusInterface
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

S_TO_MS = 1000000


class MediaListWidget(_MediaListFramework):
    def __init__(self, parent: QWidget, imgsize: int = None, update_interval: int | None = 250):
        """
        A widget that automatically creates and removes MediaWidgets in response to MPRIS players playing or stopping.
        :param parent: the parent widget of this widget, usually the main window.
        :param imgsize: the size of the album art image in pixels.
        :param update_interval: the time in ms between updates for progress bars.
        """
        super().__init__(parent, imgsize, update_interval)
        self.bus = QDBusConnection.sessionBus()

        self.players = []
        self.bus.connect("", "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties",
                         "PropertiesChanged", self.properties_changed)
        self.update_properties()

    def update_properties(self):
        self.properties_changed('', {"PlaybackStatus": "Playing"})  # force a check for changed players

    def get_players(self):
        return [s for s in self.bus.interface().registeredServiceNames().value() if "org.mpris.MediaPlayer2" in s]

    @QtCore.pyqtSlot("QString", "QVariantMap", "QStringList")
    def properties_changed(self, interface, changed_properties, invalidated_properties=None):
        if "PlaybackStatus" in changed_properties:
            players = self.get_players()
            new_players = [player for player in players if player not in self.players]
            dead_players = [player for player in self.players if player not in players]
            self.players = players
            self.new_players(new_players)
            if dead_players: self.remove_players(dead_players)

    def remove_players(self, players):
        for player in players: self.remove_widget(player)

    def new_players(self, players):
        for player in players:
            self.add_widget(MediaWidget(self, player, self.bus, self.imgsize), player)


class MediaWidget(_MediaFramework):
    def __init__(self, parent: QWidget, player: str, bus: QDBusConnection, imgsize: int = None):
        """
        An individual now playing pane. Normally created and handled by a MediaListWidget, but could be manually created for a static now playing
        widget for a single player that doesn't go away when the player is stopped.
        :param parent: the parent widget of this widget, usually the MediaListWidget controlling it.
        :param player: the MPRIS name of the player, e.g. org.mpris.MediaPlayer2.vlc
        :param bus: the Qt proxy for the bus to use, usually Session - ie PyQt5.QtDBus.QDBusConnection.sessionBus()
        :param imgsize: the size of the album art in pixels.
        """
        super().__init__(parent, player, imgsize)
        self.bus = bus

        self.trackid = None
        self.length = None
        self.playpos = 0
        self.lastupdatetime = 0
        self.rate = 1

        self.control_proxy = QDBusInterface(self.playername, "/org/mpris/MediaPlayer2",
                                            "org.mpris.MediaPlayer2.Player", self.bus)
        self.data_proxy = QDBusInterface(self.playername, "/org/mpris/MediaPlayer2",
                                         "org.freedesktop.DBus.Properties", self.bus)
        self.player_proxy = QDBusInterface(self.playername, "/org/mpris/MediaPlayer2",
                                           "org.mpris.MediaPlayer2", self.bus)
        self.metadata = self.data_proxy.call("Get", "org.mpris.MediaPlayer2.Player", "Metadata").arguments()[0]

        self.connection_args = [self.playername, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties",
                                "PropertiesChanged", self.properties_changed]
        self.bus.connect(*self.connection_args)

        starter = {"Metadata": self.metadata,
                   "Rate": self.data_proxy.call("Get", "org.mpris.MediaPlayer2.Player", "Rate").arguments()[0],
                   "PlaybackStatus":
                       self.data_proxy.call("Get", "org.mpris.MediaPlayer2.Player", "PlaybackStatus").arguments()[0]}

        self.update_player(self.data_proxy.call("Get", "org.mpris.MediaPlayer2", "Identity").arguments()[0])

        self.can_control = self.data_proxy.call("Get", "org.mpris.MediaPlayer2.Player", "CanControl").arguments()[0]
        if not self.can_control: self.ctrllayout.hide()
        self.can_raise = self.data_proxy.call("Get", "org.mpris.MediaPlayer2", "CanRaise").arguments()[0]
        if self.playing: self.played()

        self.properties_changed("", starter)

    def do_next(self):
        if self.can_control: self.control_proxy.call("Next")

    def do_prev(self):
        if self.can_control: self.control_proxy.call("Prev")

    def do_playpause(self):
        if self.can_control: self.control_proxy.call("PlayPause")

    def raise_player(self):
        self.player_proxy.call("Raise")

    def update_timeline(self):
        self.updatepos()
        self.progressupdate(0 if not self.length else self.playpos / self.length)

    def handle_removed(self):
        self.bus.disconnect(*self.connection_args)

    def download_art(self, url):
        if not hasattr(self, 'network_manager'):
            self.network_manager = QNetworkAccessManager(self)  # don't define earlier because some setups won't require it
            self.network_manager.finished.connect(self.download_complete)
        self.network_manager.get(QNetworkRequest(QUrl(url)))

    def download_complete(self, resp: QNetworkReply):
        if not resp.isFinished(): print('download not complete', resp.downloadProgress())
        art = QPixmap()
        art.loadFromData(resp.readAll())
        self.set_art(art)
        resp.deleteLater()  # required, not managed by Qt

    def set_art(self, art: QPixmap):
        self.imglabel.setPixmap(art)
        self.imglabel.show()

    @QtCore.pyqtSlot("QString", "QVariantMap", "QStringList")
    def properties_changed(self, interface, changed_properties,
                           invalidated_properties=None):
        if 'Metadata' in changed_properties and changed_properties["Metadata"]:
            md: dict = changed_properties["Metadata"]
            if self.isHidden() and md.get("mpris:trackid") != "/org/mpris/MediaPlayer2/TrackList/NoTrack": self.show()
            self.update_info(md.get("xesam:title") or 'No title', " & ".join(md.get("xesam:artist") or ['No artist']))
            self.length = md.get('mpris:length') or 0
            art = md.get("mpris:artUrl")
            if art:
                if 'file://' in art: self.set_art(QPixmap(art.replace('file://', '')))
                else: self.download_art(art)
            else: self.imglabel.hide()
        if 'PlaybackStatus' in changed_properties:
            ps = changed_properties["PlaybackStatus"]
            if ps == "Playing": self.played()
            elif ps == "Paused": self.paused()
            elif ps == "Stopped":
                self.stopped()
                self.hide()
                return
            else:
                print(self.playername, "is breaking the MPRIS spec by using PlaybackStatus =", ps)
        if 'Rate' in changed_properties:
            if self.playing and changed_properties["Rate"] != self.rate:
                self.updatepos()
            self.rate = changed_properties["Rate"]
        self.getnewpos()
        self.update_timeline()

    def getnewpos(self):
        self.playpos = self.data_proxy.call("Get", "org.mpris.MediaPlayer2.Player", "Position").arguments()[0]
        self.lastupdatetime = time() * S_TO_MS

    def updatepos(self):
        t = time() * S_TO_MS
        try:
            self.playpos += (t - (self.lastupdatetime or t)) * self.rate
        except:
            print("invalid multiplication in updatepos():")
            print(t, self.lastupdatetime, self.rate)
        self.lastupdatetime = t
