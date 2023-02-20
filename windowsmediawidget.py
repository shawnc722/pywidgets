#!/usr/bin/env python3
from PyQt6 import QtCore, QtWidgets, QtGui
from datetime import datetime
from PyQt6.QtGui import QPixmap
from pywidgets.widgets import _MediaListFramework, _MediaFramework

import asyncio
# from https://stackoverflow.com/questions/71005262/event-handling-with-winrt-for-python
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as SessionManager,
    GlobalSystemMediaTransportControlsSession as Session,
    SessionsChangedEventArgs, PlaybackInfoChangedEventArgs, MediaPropertiesChangedEventArgs,
    TimelinePropertiesChangedEventArgs
)
from winsdk.windows.storage.streams import \
    DataReader, Buffer, InputStreamOptions

PLAYBACK_STATUS_CLOSED = 0
PLAYBACK_STATUS_OPENED = 1
PLAYBACK_STATUS_CHANGING = 2
PLAYBACK_STATUS_STOPPED = 3
PLAYBACK_STATUS_PLAYING = 4
PLAYBACK_STATUS_PAUSED = 5

# TODO: rewrite asyncio parts using proper createTask() setup and a callback for album art


class MediaListWidget(_MediaListFramework):
    session_started = QtCore.pyqtSignal(list)
    session_died = QtCore.pyqtSignal(list)

    def __init__(self, parent: QtWidgets.QWidget, imgsize: int = None, butsize: int = None, update_interval: int = 250):
        """
        A widget that automatically creates and removes MediaWidgets in response to Windows Global System Media Transport
        sessions playing or stopping.
        :param parent: the parent widget of this widget, usually the main window.
        :param imgsize: the size of the album art image in pixels.
        :param butsize: the size of the media control buttons in pixels.
        :param update_interval: the time in ms between updates for progress bars.
        """
        super().__init__(parent, imgsize, butsize, update_interval)
        self.manager = None
        self.sessions = []
        self.session_changed_token = None
        self.session_started.connect(self.new_sessions)
        self.session_died.connect(self.dead_sessions)
        asyncio.run(self._do_async())  # updates self.manager and self.session_changed_token
        self.sessions_changed(self.manager, None)
        # TODO: run once to update

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        for session in self.mediawidgets.values():
            session.remove_listeners()
        self.manager.remove_sessions_changed(self.session_changed_token)
        super().closeEvent(a0)

    async def _do_async(self):
        self.manager = await SessionManager.request_async()
        self.session_changed_token = self.manager.add_sessions_changed(self.sessions_changed)

    def remove_widget(self, widget):
        self.sessions.remove(widget.player)
        super().remove_widget(widget)

    def new_sessions(self, sessions: list):
        for session in sessions:
            self.sessions.append(session.source_app_user_model_id)
            self.add_widget(MediaWidget(self, session, self.imgsize, self.butsize, self.update_interval),
                            session.source_app_user_model_id)
        self.update()

    def remove_widget(self, widget): raise NotImplementedError

    def dead_sessions(self, sessions: list):
        for session in sessions:
            self.sessions.remove(session)
            widg = self.mediawidgets.pop(session)
            widg.remove_listeners()
            self.layout.removeWidget(widg)
            del widg
        self.update()

    def sessions_changed(self, manager: SessionManager, args: SessionsChangedEventArgs = None) -> None:
        sessionsl = manager.get_sessions()
        sessions = {s.source_app_user_model_id: s for s in sessionsl}
        new_sessions = [sessions[session] for session in sessions.keys() if session not in self.sessions]  # list of sessions
        dead_sessions = [session for session in self.sessions if session not in sessionsl]  # list of strs
        if new_sessions: self.session_started.emit(new_sessions)
        if dead_sessions: self.session_died.emit(dead_sessions)


class MediaWidget(_MediaFramework):
    EPOCH = datetime(1970, 1, 1)
    changed_playback = QtCore.pyqtSignal()
    changed_metadata = QtCore.pyqtSignal(bool)  # True if image changed too
    changed_albumart = QtCore.pyqtSignal(bool, QPixmap)  # bool is always True, QPixmap is new image

    def __init__(self, parent: QtWidgets.QWidget, session: Session, imgsize: int = None, butsize: int = None,
                 update_interval: int = 250):
        """
        An individual now playing pane. Normally created and handled by a MediaListWidget, but could be manually created for a static now playing
        widget for a single player that doesn't go away when the player is stopped.
        :param parent: the parent widget of this widget, usually the MediaListWidget controlling it.
        :param session: the session to display media from.
        :param imgsize: the size of the album art in pixels.
        :param butsize: the size of the media control buttons in pixels.
        :param update_interval: the time in ms between updates for progress bars.
        """
        super().__init__(parent, imgsize, butsize, update_interval)
        self.session = session

        self.playername = self.session.source_app_user_model_id.replace('.exe', '').lower()  # get lowercase name minus extension, ie 'EXAMPLE.exe' -> 'example'
        self.playername = self.playername[0].upper()+self.playername[1:]  # capitalize first letter, ie 'example' -> 'Example'
        self.playernamelabel.setText(f"<b>{self.playername}</b>")

        self.metadata = {}
        self.last_album = {"No Last Album": "Using dict cuz None is a possible value"}
        self.can_next = None
        self.can_prev = None
        self.can_playpause = None
        self.can_position = None

        self.timer = QtCore.QTimer()
        self.timer.setInterval(update_interval)
        self.timer.timeout.connect(self.update_pos)

        self.changed_playback.connect(self.handle_playback_changed)
        self.changed_metadata.connect(self.handle_metadata_changed)
        self.changed_albumart.connect(self.handle_metadata_changed)

        self.playback_token = session.add_playback_info_changed(self.playback_changed)
        self.timeline_token = session.add_timeline_properties_changed(self.timeline_changed)
        self.metadata_token = session.add_media_properties_changed(self.metadata_changed)

        self.playback_changed(self.session, None)  # set play/pause status
        self.metadata_changed(self.session, None)

    def artist(self):
        return self.metadata.artist

    def title(self):
        return self.metadata.title

    def album(self):
        return self.metadata.album_title

    def do_next(self):
        if self.can_next: asyncio.run(self.async_next())

    async def async_next(self):
        await self.session.try_skip_next_async()

    def do_prev(self):
        if self.can_prev: asyncio.run(self.async_prev())

    async def async_prev(self):
        await self.session.try_skip_previous_async()

    def do_playpause(self):
        if self.can_playpause: asyncio.run(self.async_playpause())

    async def async_playpause(self):
        await self.session.try_toggle_play_pause_async()

    def played(self):
        if not self.playing:
            self.playing = True
            #self.timer.start()
            self.update_pos()
        super().played()

    def paused(self):
        #self.timer.stop()
        super().paused()

    def stopped(self):
        #self.timer.stop()
        super().stopped()

    def handle_playback_changed(self):
        pbinfo = self.session.get_playback_info()
        if pbinfo.playback_status == PLAYBACK_STATUS_PLAYING: self.played()
        elif pbinfo.playback_status == PLAYBACK_STATUS_PAUSED: self.paused()
        controls = pbinfo.controls
        if not self.can_prev == controls.is_previous_enabled:
            self.can_prev = controls.is_previous_enabled
            if controls.is_previous_enabled: self.buttons[0].show()
            else: self.buttons[0].hide()
        if not self.can_playpause == controls.is_play_pause_toggle_enabled:
            self.can_playpause = controls.is_play_pause_toggle_enabled
            if controls.is_play_pause_toggle_enabled: self.buttons[1].show()
            else: self.buttons[1].hide()
        if not self.can_next == controls.is_next_enabled:
            self.can_next = controls.is_next_enabled
            if controls.is_next_enabled: self.buttons[2].show()
            else: self.buttons[2].hide()
        if not self.can_position == controls.is_playback_position_enabled:
            self.can_position = controls.is_playback_position_enabled
            if controls.is_playback_position_enabled: self.pbar.show()
            else: self.pbar.hide()
        # also listen for rate change? pbinfo.playback_rate

    def playback_changed(self, session: Session, args: PlaybackInfoChangedEventArgs):
        self.changed_playback.emit()

    def timeline_changed(self, session: Session, args: TimelinePropertiesChangedEventArgs):
        print('Timeline changed on', self.playername, ':', get_pub_props(session.get_timeline_properties()))

    async def read_stream_into_buffer(self, stream_ref, buffer):
        readable_stream = await stream_ref.open_read_async()
        readable_stream.read_async(buffer, buffer.capacity, InputStreamOptions.READ_AHEAD)
        return  # to avoid run ending the program

    def metadata_changed(self, session: Session, args: MediaPropertiesChangedEventArgs):
        asyncio.run(self.get_metadata())
        if (self.last_album and not self.last_album == self.album()) and self.playing:
            # from https://stackoverflow.com/questions/65011660/how-can-i-get-the-title-of-the-currently-playing-media-in-windows-10-with-python
            self.last_album = self.album()
            thumb = self.metadata.thumbnail
            if thumb:
                buffer = Buffer(250000)  # 2.5MB buffer to give lots of space
                finished, unfinished = asyncio.run(
                    asyncio.wait([self.read_stream_into_buffer(thumb, buffer)], timeout=2))
                if unfinished:
                    self.last_album = {"No Last Album": "Using dict cuz None is a possible value"}
                    return self.changed_metadata.emit(True)
                asyncio.run(self.read_stream_into_buffer(thumb, buffer))
                buffer_reader = DataReader.from_buffer(buffer)
                byte_buffer = buffer_reader.read_bytes(buffer.length)
                del buffer
                img = QPixmap()
                img.loadFromData(bytearray(byte_buffer))
                return self.changed_albumart.emit(True, img)
            self.last_album = {"No Last Album": "Using dict cuz None is a possible value"}
            return self.changed_metadata.emit(True)
        self.changed_metadata.emit(False)

    def handle_metadata_changed(self, img_changed: bool, img=None):
        self.infolabel.setText(self.displaytext)
        self.update_pos()
        if img:
            self.imglabel.setPixmap(img)
            self.imglabel.show()
        elif img_changed:
            self.imglabel.hide()

    async def get_metadata(self):
        self.metadata = await self.session.try_get_media_properties_async()
        self.displaytext = f"{self.title()}<br>{self.artist()}"

    def update_pos(self):
        if self.can_position:
            ts = self.session.get_timeline_properties()
            if self.playing:
                length = ts.end_time.duration - ts.start_time.duration
                now = (datetime.utcnow() - self.EPOCH).total_seconds()
                time_since_update = now - ts.last_updated_time.universal_time
                perc = ts.position.duration + time_since_update
                if not length == 0: perc = perc/length
                else: perc = 0
                self.progressupdate(perc)

    def remove_listeners(self):
        self.session.remove_playback_info_changed(self.playback_token)
        self.session.remove_timeline_properties_changed(self.timeline_token)
        self.session.remove_media_properties_changed(self.metadata_token)
        self.changed_metadata.disconnect()
        self.changed_playback.disconnect()
        self.changed_albumart.disconnect()


def get_pub_props(obj):
    return {prop: getattr(obj, prop) for prop in dir(obj) if prop[0] != '_'}
