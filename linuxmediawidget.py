#!/usr/bin/env python3
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtGui import QPixmap
from time import time
from pywidgets.widgets import _MediaListFramework, _MediaFramework
from PyQt6.QtDBus import QDBusConnection, QDBusInterface

S_TO_MS = 1000000


class MediaListWidget(_MediaListFramework):
    def __init__(self, parent: QtWidgets.QWidget, imgsize: int = None, butsize: int = None, update_interval: int = 250):
        """
        A widget that automatically creates and removes MediaWidgets in response to MPRIS players playing or stopping.
        :param parent: the parent widget of this widget, usually the main window.
        :param imgsize: the size of the album art image in pixels.
        :param butsize: the size of the media control buttons in pixels.
        :param update_interval: the time in ms between updates for progress bars.
        """
        super().__init__(parent, imgsize, butsize, update_interval)
        self.bus = QDBusConnection.sessionBus()
        self.handler = _MprisPlayerDetector(self.bus)
        self.handler.add_subscriber(self)
        self.handler.properties_changed("", {"PlaybackStatus": "Playing"})  # to force it to find players immediately

    def remove_players(self, players):
        for player in players: self.remove_widget(player)

    def new_players(self, players):
        for player in players:
            self.add_widget(MediaWidget(self, player, self.bus, self.imgsize, self.butsize), player)


class MediaWidget(_MediaFramework):
    def __init__(self, parent: QtWidgets.QWidget, player: str, bus: QDBusConnection, imgsize: int = None, butsize: int = None,
):
        """
        An individual now playing pane. Normally created and handled by a MediaListWidget, but could be manually created for a static now playing
        widget for a single player that doesn't go away when the player is stopped.
        :param parent: the parent widget of this widget, usually the MediaListWidget controlling it.
        :param player: the MPRIS name of the player, e.g. org.mpris.MediaPlayer2.vlc
        :param bus: the Qt proxy for the bus to use, usually Session - ie PyQt5.QtDBus.QDBusConnection.sessionBus()
        :param imgsize: the size of the album art in pixels.
        :param butsize: the size of the media control buttons in pixels.
        """
        super().__init__(parent, player, imgsize, butsize)
        self.handler = _MprisHandler(player, bus)
        self.handler.add_subscriber(self)
        self.update_player(self.handler.data_proxy.call("Get", "org.mpris.MediaPlayer2", "Identity").arguments()[0])

        self.can_control = self.handler.data_proxy.call("Get", "org.mpris.MediaPlayer2.Player", "CanControl").arguments()[0]
        if not self.can_control: self.ctrllayout.hide()
        if self.handler.playing: self.played()
        self.metadatachanged()

    def do_next(self):
        if self.can_control: self.handler.media_ctrl("Next")

    def do_prev(self):
        if self.can_control: self.handler.media_ctrl("Prev")

    def do_playpause(self):
        if self.can_control: self.handler.media_ctrl("PlayPause")

    def update_timeline(self):
        self.handler.update()

    def handle_removed(self):
        pass  # TODO: unsubscribe from listeners, but this probably needs a rewrite anyway so not worrying about it rn

    def metadatachanged(self):
        self.update_info(self.handler.title(), self.handler.artist())
        newart = self.handler.albumart()
        if not self.albumart == newart:
            self.albumart = newart
            if not self.albumart:
                self.imglabel.hide()
            else:
                self.imglabel.setPixmap(QPixmap(self.albumart))
                self.imglabel.show()
        self.update()


class _MprisHandler(QtCore.QObject):
    def __init__(self, player: str, bus: QDBusConnection):
        """
        Handles Mpris media, and updates its subscribers whenever a PropertiesChanged event is sent.
        Each subscriber must have a metadata_changed() method.
        :param player: the MPRIS name of the player, e.g. org.mpris.MediaPlayer2.vlc
        :param bus: the Qt proxy for the bus to use, usually Session - ie PyQt5.QtDBus.QDBusConnection.sessionBus()
        """
        super().__init__()
        self.bus = bus
        self.dbus_proxy = QDBusInterface
        # may need getter functions for these next two if they're passed as objects instead of references
        self.player = player
        self.trackid = None
        self.length = None
        self.playpos = 0
        self.lastupdatetime = 0
        self.rate = 1
        self.playing = False
        self.subscribers = []
        self.control_proxy = QDBusInterface(self.player, "/org/mpris/MediaPlayer2",
                                            "org.mpris.MediaPlayer2.Player", self.bus)
        self.data_proxy = QDBusInterface(self.player, "/org/mpris/MediaPlayer2",
                                         "org.freedesktop.DBus.Properties", self.bus)
        self.metadata = self.manual_get_metadata()
        self.connection_args = [self.player, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties",
                                "PropertiesChanged", self.properties_changed]
        self.bus.connect(*self.connection_args)
        starter = {"Metadata": self.metadata,
                   "Rate": self.data_proxy.call("Get", "org.mpris.MediaPlayer2.Player", "Rate").arguments()[0],
                   "PlaybackStatus":
                       self.data_proxy.call("Get", "org.mpris.MediaPlayer2.Player", "PlaybackStatus").arguments()[0]}
        self.properties_changed("", starter)

    def manual_get_metadata(self):
        return self.data_proxy.call("Get", "org.mpris.MediaPlayer2.Player", "Metadata").arguments()[0]

    def update(self):
        self.updatepos()
        perc = 0
        if not self.length:
            try:
                self.length = self.data_proxy.call("Get", "org.mpris.MediaPlayer2.Player", "Metadata").arguments()[0][
                    "Length"]
            except KeyError:
                pass
            if self.length:
                perc = self.playpos / self.length
            else:
                pass
        else:
            perc = self.playpos / self.length
        for subscriber in self.subscribers:
            subscriber.progressupdate(perc)

    def getnewpos(self):
        self.playpos = self.data_proxy.call("Get", "org.mpris.MediaPlayer2.Player", "Position").arguments()[0]
        self.lastupdatetime = time() * S_TO_MS

    def updatepos(self):
        t = time() * S_TO_MS
        if not self.rate == 0 or self.rate == 1:
            self.playpos += (t - self.lastupdatetime) * self.rate
        else:
            self.playpos += t - self.lastupdatetime
        self.lastupdatetime = t

    def add_subscriber(self, subscriber):
        self.subscribers.append(subscriber)

    def title(self):  # none of these should be properties, to make sure they can be passed as methods
        try:
            return self.metadata["xesam:title"]
        except KeyError:
            return "No Title"

    def artist(self):
        try:
            return " & ".join(self.metadata["xesam:artist"])
        except KeyError:
            return "No Artist"
        except TypeError:
            return "No Artist"

    def album(self):
        try:
            return self.metadata["xesam:album"]
        except KeyError:
            return "No Album"

    def albumart(self):
        try:
            return self.metadata["mpris:artUrl"].replace("file://", "")
        except KeyError:
            return None
        except AttributeError:
            return None

    def media_ctrl(self, command: str):
        self.control_proxy.call(command)

    @QtCore.pyqtSlot("QString", "QVariantMap", "QStringList")
    def properties_changed(self, interface, changed_properties,
                           invalidated_properties=None):
        if invalidated_properties: print("Invalidated properties actually did something! Dropped: ",
                                         invalidated_properties)
        if 'Metadata' in changed_properties and changed_properties["Metadata"] != {}:
            md = changed_properties["Metadata"]
            try:
                trid = md["mpris:trackid"]
            except KeyError:
                trid = str(time())  # if no track ID, use the current time to make a "unique" one
            if not self.trackid == trid:
                self.trackid = trid
                self.getnewpos()
                self.length = md["mpris:length"]
            self.metadata = md
            for subscriber in self.subscribers:
                subscriber.metadatachanged()
        if 'PlaybackStatus' in changed_properties:
            ps = changed_properties["PlaybackStatus"]
            if ps == "Playing":
                if not self.playing:
                    self.getnewpos()
                    self.playing = True
                    if self.title() == "No Title":
                        self.properties_changed('', self.manual_get_metadata())
                for subscriber in self.subscribers:
                    subscriber.played()
            elif ps == "Paused":
                if self.playing:
                    self.updatepos()
                    self.playing = False
                    self.update()
                for subscriber in self.subscribers:
                    subscriber.paused()
            elif ps == "Stopped":
                self.playing = False
                self.bus.disconnect(*self.connection_args)
                for subscriber in self.subscribers:
                    subscriber.stopped()
            else:
                print(self.player, "is breaking the MPRIS spec by using PlaybackStatus = ", ps)
        if 'Rate' in changed_properties:
            if self.playing and changed_properties["Rate"] != self.rate:
                self.updatepos()
            self.rate = changed_properties["Rate"]


class _MprisPlayerDetector(QtCore.QObject):
    def __init__(self, bus: QDBusConnection, update_interval: int = 2000):
        """
        A detector that listens to all PropertiesChanged signals from MPRIS players to keep its subscribers updated
        on which players are active and which are dead.
        All subscribers must have new_players and remove_players methods that both take lists of players to be added/removed.
        :param bus: the Qt proxy for the bus to use, usually Session - ie PyQt5.QtDBus.QDBusConnection.sessionBus()
        :param update_interval: the amount of time in ms between manual checks of current players.
        """
        super().__init__()
        self.bus = bus
        self.connection_args = ["", "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties",
                                "PropertiesChanged", self.properties_changed]
        self.players = []
        self.players = self.get_players()
        self.subscribers = []
        self.bus.connect(*self.connection_args)
        self.update_interval = update_interval

        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.update_interval)
        self.timer.timeout.connect(self.update)
        self.timer.start()

    def get_players(self):
        return [s for s in self.bus.interface().registeredServiceNames().value() if "org.mpris.MediaPlayer2" in s]

    def add_subscriber(self, subscriber):
        self.subscribers.append(subscriber)
        subscriber.new_players(self.players)

    def update(self):
        self.properties_changed('', {"PlaybackStatus": "Playing"})  # force a check for changed players

    @QtCore.pyqtSlot("QString", "QVariantMap", "QStringList")
    def properties_changed(self, interface, changed_properties, invalidated_properties=None):
        if "PlaybackStatus" in changed_properties:
            players = self.get_players()
            new_players = [player for player in players if player not in self.players]
            dead_players = [player for player in self.players if player not in players]
            self.players = players
            for subscriber in self.subscribers:
                subscriber.new_players(new_players)
                if dead_players: subscriber.remove_players(dead_players)
