from PyQt6.QtGui import QPixmap
from datetime import datetime, timedelta

import pywidgets
from pywidgets.widgets import _MediaListFramework, _MediaFramework, schedule, run_on_app_start, call_threadsafe, QWidget
from asyncio import sleep

from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as SessionManager,
    GlobalSystemMediaTransportControlsSession as Session,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus
)

from winsdk.windows.ui.notifications.management import UserNotificationListener, UserNotificationListenerAccessStatus
from winsdk.windows.ui.notifications import UserNotificationChangedEventArgs as NotifArgs, \
    UserNotificationChangedKind as NotifChangedKind

from winsdk.windows.storage.streams import DataReader, IRandomAccessStreamReference
from winsdk.windows.foundation import AsyncStatus
from winsdk.windows.applicationmodel import AppInfo

NOTIME = timedelta(0)


def enum_to_rdict(enum):
    return {getattr(enum, attr): attr for attr in dir(enum) if attr == attr.upper()}


class MediaListWidget(_MediaListFramework):
    def __init__(self, parent: QWidget, **kwargs):
        """
        A widget that automatically creates and manages MediaWidgets corresponding to each active media source
        on the device.
        :param parent: the parent widget of this widget, usually the main window.
        :param imgsize: the size of the album art image in pixels.
        :param butsize: the size of the media control buttons in pixels.
        :param update_interval: the time in ms between updates for progress bars.
        """
        super().__init__(parent, **kwargs)
        self.manager = None  # is requested asynchronously and assigned in _manager_received()
        self.session_changed_token = None  # also assigned in _manager_received()
        run_on_app_start(win_schedule, SessionManager.request_async, self._manager_received)

    def _manager_received(self, task):
        self.manager: SessionManager = task.result()
        task.cancel()  # probably unnecessary since task should end to call this method, but just in case
        self.session_changed_token = self.manager.add_sessions_changed(
            lambda man, arg: call_threadsafe(self.sessions_changed, man, arg)
        )
        self.sessions_changed(self.manager)

    def sessions_changed(self, manager: SessionManager = None, args=None):
        current = {s.source_app_user_model_id: s for s in manager.get_sessions()}
        new = [session for session in current.keys() if session not in self.mediawidgets]
        expired = [session for session in self.mediawidgets if session not in current]

        for session in new: self.new_session(current[session])
        for session in expired: self.remove_widget(session)

    def new_session(self, session: Session):
        id = session.source_app_user_model_id
        try:
            name = AppInfo.get_from_app_user_model_id(id).display_info.display_name
            # get logo to show here too? it's display_info.get_logo
        except:  # this'll fail if it's not a UWP app but if it fails for any reason just use the appID
            name = id.replace('.exe', '').title()
        self.add_widget(MediaWidget(self, session=session, playername=name), id)


class MediaWidget(_MediaFramework):
    inverse_playback_info = enum_to_rdict(PlaybackStatus)

    def __init__(self, parent: QWidget, session: Session, **kwargs):
        """
        A widget for displaying media info from one specific source, usually created and managed by a MediaListWidget.
        :param parent: the parent widget of this widget, usually the MediaListWidget controlling it.
        :param playername: the name of the player this widget is handling.
        :param imgsize: the size of the album art in pixels.
        :param butsize: the size of the media control buttons in pixels.
        :param primary_color: the color to use for most of the widget. Accepts a QColor or CSS color strings.
        Leave as None to use the parent widget's default color.
        :param secondary_color: the color to use for buttons when the mouse is hovering over them,
        and for the progress bar. Accepts a QColor or CSS color strings.
        """
        super().__init__(parent, **kwargs)
        self.session = session
        self.playback_token = session.add_playback_info_changed(
            lambda ses, args: call_threadsafe(self.playback_changed, ses, args)
        )
        self.timeline_token = session.add_timeline_properties_changed(
            lambda ses, args: call_threadsafe(self.timeline_changed, ses, args)
        )
        self.metadata_token = session.add_media_properties_changed(
            lambda ses, args: call_threadsafe(self.metadata_changed, ses, args)
        )
        self.controls = None
        self.last_update_call = NOTIME
        self.playtime_since_last_update = NOTIME
        self.last_timeline = None

        self.playback_changed(self.session)
        self.timeline_changed(self.session)
        self.metadata_changed(self.session)

    def playback_changed(self, session: Session, args=None):
        info = session.get_playback_info()
        if not info: return
        if info.playback_status == PlaybackStatus.CLOSED:
            self.handle_removed()
        elif info.playback_status == PlaybackStatus.PLAYING:
            self.played()
        elif info.playback_status == PlaybackStatus.PAUSED:
            self.paused()

        if not self.controls == info.controls:
            self.controls = info.controls
            if self.controls.is_play_pause_toggle_enabled != self.buttons[1].isVisible():
                self.buttons[1].setVisible(self.controls.is_play_pause_toggle_enabled)
            if self.controls.is_next_enabled != self.buttons[2].isVisible():
                self.buttons[2].setVisible(self.controls.is_next_enabled)
            if self.controls.is_previous_enabled != self.buttons[0].isVisible():
                self.buttons[0].setVisible(self.controls.is_previous_enabled)
            if self.controls.is_playback_position_enabled != self.pbar.isVisible():
                self.pbar.setVisible(self.controls.is_playback_position_enabled)
                self.has_progress = self.controls.is_playback_position_enabled

    def timeline_changed(self, session: Session, args=None):
        self.last_timeline = session.get_timeline_properties()
        self.last_update_call = datetime.utcnow()
        self.playtime_since_last_update = NOTIME
        self.update_timeline()

    def metadata_changed(self, session: Session, args=None):
        task = schedule(self.get_metadata())

    async def get_metadata(self):
        metadata = await self.session.try_get_media_properties_async()
        self.update_info(metadata.title, metadata.artist)
        thumb = metadata.thumbnail
        if thumb is None and not self.albumart:
            self.imglabel.hide()
        elif thumb is None:
            pass  # leave it alone for now, another update is on the way w/ thumb (they come in groups of 2-3 for most apps)
        else:
            self.albumart = await read_thumb_stream(thumb)
            if self.albumart is None:
                self.imglabel.hide()
                return
            self.imglabel.setPixmap(self.albumart)
            if self.imglabel.isHidden(): self.imglabel.show()

    def do_next(self, *args):
        """
        Request the next song.
        """
        if self.controls.is_next_enabled: task = schedule(winrt_to_async(self.session.try_skip_next_async))

    def do_prev(self, *args):
        """
        Request the previous song.
        """
        if self.controls.is_previous_enabled: task = schedule(winrt_to_async(self.session.try_skip_previous_async))

    def do_playpause(self, *args):
        """
        Request to start playing if paused, or to pause if playing.
        """
        if self.controls.is_play_pause_toggle_enabled:
            task = schedule(winrt_to_async(self.session.try_toggle_play_pause_async()))

    def update_timeline(self):
        """
        Updates the progressbar with the correct percentage.
        """
        if not self.last_timeline: return  # right now just ignore fuckery
        now = datetime.utcnow()
        if self.playing: self.playtime_since_last_update += now - self.last_update_call
        self.last_update_call = now
        length = self.last_timeline.end_time - self.last_timeline.start_time
        perc = self.last_timeline.position + self.playtime_since_last_update

        perc = 0 if not length else perc / length

        self.progressupdate(perc)

    def handle_removed(self):
        """
        Called when this widget has been removed from its parent MediaListWidget. Should handle any cleanup
        this widget requires before deletion.
        """
        self.session.remove_media_properties_changed(self.metadata_token)
        self.session.remove_playback_info_changed(self.playback_token)
        self.session.remove_timeline_properties_changed(self.timeline_token)


class NotificationWidget(pywidgets.NotificationWidgetFramework):
    inverse_access_status = enum_to_rdict(UserNotificationListenerAccessStatus)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.manager = UserNotificationListener.current
        self.token = None  # filled out in subscribe
        run_on_app_start(win_schedule, self.manager.request_access_async, self.handle_access)

    def handle_notif(self, listener: UserNotificationListener, args: NotifArgs):
        if args.change_kind == NotifChangedKind.ADDED:
            notif = listener.get_notification(args.user_notification_id)
            print(notif, notif.notification, notif.app_info)
        elif args.change_kind == NotifChangedKind.REMOVED:
            pass # remove notif
        else:
            raise ValueError("Invalid UserNotificationChangedKind:", args.change_kind)

    def subscribe(self):
        print("subscribing...")
        try:
            self.token = self.manager.add_notification_changed(
                lambda lis, args: call_threadsafe(self.handle_notif, lis, args)
            )
        except OSError:
            print("Subscription failed because of 'Element not found' Windows bug, NotificationWidget can't listen for notifs.")
        else:
            print("subscribed successfully")

    def handle_access(self, task):
        access = task.result()
        if access == UserNotificationListenerAccessStatus.ALLOWED:
            self.subscribe()
        elif access == UserNotificationListenerAccessStatus.UNSPECIFIED:
            print("unspecified access")
        else:
            raise PermissionError("Notification access must be granted for notification widgets on Windows.")

    def handle_removed(self):
        if self.token is not None: self.manager.remove_notification_changed(self.token)


async def winrt_to_async(winrt_fn, *args): return await winrt_fn(*args)


def win_schedule(winrt_fn, callback, *args): return schedule(winrt_to_async(winrt_fn, *args), callback)


async def read_thumb_stream(stream_ref: IRandomAccessStreamReference) -> QPixmap | None:
    open_stream = await stream_ref.open_read_async()
    input_stream = open_stream.get_input_stream_at(0)
    reader = DataReader(input_stream)
    task = reader.load_async(open_stream.size)
    while not task.status:
        await sleep(0.05)  # I really hate this but DataReader.load_async doesn't work with await
    if task.status != 1:
        print("Something went wrong in read_stream:", AsyncStatus[task.status])
        return None
    data = bytearray(reader.read_byte() for i in range(reader.unconsumed_buffer_length))  # read_bytes() stopped working after an update
    img = QPixmap()
    img.loadFromData(data)
    input_stream.close()
    open_stream.close()
    reader.close()
    return img
