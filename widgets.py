#!/usr/bin/python3.8
from typing import Union, Callable, Iterable
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QPainter, QPen, QPolygon, QRegion, QColor, QPainterPath
from pywidgets.JITstrings import JITstring
import pyqtgraph as pg
from math import asin, cos

class Window(QtWidgets.QMainWindow):
    def __init__(self, width: int, height: int, stylesheet: str = "default", maintain_position: str = "bottom"):
        """
        The main window containing all your pywidgets. After instantiating one of these,
        call its finish_init() method with a list of the pywidgets you want in the window to complete the setup.
        :param width: the width of the window in pixels.
        :param height: the height of the window in pixels.
        :param stylesheet: a css stylesheet for all the widgets - usually contains at least a color and a font-family.
        :param maintain_position: where the window should stay - "bottom" to appear part of the desktop, "top" to stay
            on top, or "default" to behave like a normal window.
        """
        super().__init__()
        self.central_widget = None
        self.layout = None
        self.title = "PyWidget"
        self.setWindowTitle(self.title)
        self.setFixedSize(width, height)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        flags = QtCore.Qt.FramelessWindowHint
        if maintain_position.lower() == 'bottom': flags = flags | QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnBottomHint
        elif maintain_position.lower() == 'top': flags = flags | QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if stylesheet == 'default':
            stylesheet = f"color: grey; font-family: Monospace, Play-Regular; font-size: {round(self.height() / 120)}px;"
        self.setStyleSheet(stylesheet)
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.widgets = []

    def add_widget(self, widget, *args) -> None:
        """
        Stores the given widget for adding to the main layout, with the given args.
        :param widget: the widget to add.
        :param args: any optional arguments to the layout.addWidget() call, ie stretch, row/col number, etc.
        """
        self.widgets.append((widget, *args))

    def add_widgets(self, widgets) -> None:
        """
        Similar to add_widget, but for multiple inputs at once.
        :param widgets: Either a list of widgets, or a list of lists of the format [[widget, *args], ...]
        """
        for widget in widgets:
            if not hasattr(widget, '__next__'): self.widgets.append((widget, ))  # if it's not iterable, wrap in tuple
            else: self.widgets.append(widget)  # if 'widget' is iterable, assuming it matches the [widget, *args] format

    def finish_init(self, layout = None, add_stretch: bool = True) -> None:
        """
        Adds the stored pywidgets to the Window and finishes off the setup. Uses a custom layout if provided.
        :param layout: a Qt layout to use for the widgets.
        :param add_stretch: whether to pad the end of the layout with blank space to condense the widgets. Only works with
            certain types of layouts.
        """
        if layout is None:
            layout = QtWidgets.QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
        self.layout = layout
        self.central_widget.setLayout(self.layout)
        for widget in self.widgets: self.layout.addWidget(*widget)
        if add_stretch: self.layout.addStretch()
        self.show()


class ProgressArcsWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget, text: Union[JITstring, str], percs: Union[list, Callable],
                 title: Union[JITstring, str] = None, height: int = None, update_interval: int = 1000,
                 arccol: QColor = QtCore.Qt.gray, arcthic: int = -1):
        """A widget that displays percentage values as arcs around some text - or a JITstring, for dynamic text.
        :param parent: the parent widget of this widget, usually the main window.
        :param text: the text for the arcs to be drawn around.
        :param percs: either a list of commands or a single function/command that produces a list. Results must resemble a float between 0 and 100.
        :param height: the height of the widget in pixels.
        :param update_interval: the time in ms between calls to the percs function(s)
        :param arccol: the color of the arcs as a Qt color.
        :param arcthic: the thickness of the arcs in pixels. Leave as -1 to use half the text height, or use None to match text height.
        :param title: an optional title that sits above the text.
        """
        super().__init__(parent)
        if height is None: height = round(parent.height() / 10)
        self.setFixedSize(parent.width(), height)
        self.text = text
        self.percs = percs
        self._percs_now = None
        self.update_interval = update_interval
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.do_cmds)
        self.arccol = arccol
        if arcthic == -1: self.arcthic = round(self.fontMetrics().height()/2)
        elif not arcthic: self.arcthic = self.fontMetrics().height()
        else: self.arcthic = arcthic
        self.label_wrapper = QtWidgets.QWidget(self)
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.setDirection(QtWidgets.QBoxLayout.BottomToTop)
        self.label_wrapper.setLayout(self.layout)
        self.label = QtWidgets.QLabel(self.label_wrapper)
        self.label.setContentsMargins(0, 0, 0, 0)
        self.label_wrapper.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.label)
        self.title = title
        if title is not None:
            self.title_label = QtWidgets.QLabel(self.label_wrapper)
            self.layout.addWidget(self.title_label)
        self.arcsize = height
        offset = self.arcsize // 2 + self.arcthic
        self.label_wrapper.setFixedWidth(self.width() - offset)
        self.label_wrapper.setGeometry(offset, offset, self.width() - offset, self.height() - offset)
        self.label.setAlignment(QtCore.Qt.AlignLeft)
        self.label.setWordWrap(True)
        if self.update_interval: self.timer.start(self.update_interval)
        self.do_cmds()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for i, perc in enumerate(self._percs_now):
            offset = self.arcthic // 2 + i * (self.arcthic + self.arcthic // 4)
            arcsize = self.arcsize - offset * 2
            self.arc(painter, offset, offset, arcsize, arcsize, 270, -270, thickness=self.arcthic // 4)
            self.arc(painter, offset, offset, arcsize, arcsize, 270, int(-270 * perc / 100), thickness=self.arcthic)
        painter.end()

    def do_cmds(self):
        if type(self.percs) == list:
            self._percs_now = [float(i) for i in self.percs]
        else:
            self._percs_now = list(self.percs())
        self.label.setText(str(self.text))
        if hasattr(self, 'title_label'): self.title_label.setText(str(self.title))
        self.update()

    def arc(self, painter, x, y, w, h, start, span, thickness=8):
        """
        Draws a solid arc using the given painter and self.arccol for color.
        :param painter: the QPainter object to use for drawing.
        :param x: the x coordinate to begin drawing at, relative to this widget.
        :param y: the y coordinate to begin drawing at, relative to this widget.
        :param w: the width of the final shape in pixels.
        :param h: the height of the final shape in pixels.
        :param start: the angle (in degrees) to start the arc at.
        :param span: the angle (in degrees) the arc should span in total.
        :param thickness: the line thickness to use for the arc, in pixels.
        """
        painter.setPen(QPen(self.arccol, thickness, QtCore.Qt.SolidLine))
        painter.drawArc(x, y, w, h, start * 16, span * 16)


class ProgressArcWidget(QtWidgets.QWidget):
    angle_args = {  # 0deg is right and 90deg is up.
        'top right': (-90, 270),
        'top left': (-90, -270),
        'bottom right': (180, 270),
        'bottom left': (0, -270)
    }

    def __init__(self, parent: QtWidgets.QWidget, text: Union[JITstring, str], perc: Callable,
                 title: Union[JITstring, str] = None, arcpos: str = "top left", height: int = None,
                 update_interval: int = 1000, arccol: QColor = QtCore.Qt.gray, arcthic: int = 8):
        """A widget that displays a percentage value as an arc around some text - or a JITstring, for dynamic text.
        :param parent: the parent widget of this widget, usually the main window.
        :param text: the text for the arcs to be drawn around.
        :param perc: a function/command that produces something resembling a float between 0 and 100.
        :param title: short text to put inside the arc.
        :param arcpos: where to place the arc on the text box. One of: ['top left', 'top right', 'bottom left', 'bottom right'].
        :param height: the height of the widget in pixels.
        :param update_interval: the time in ms between calls to the perc function
        :param arccol: the color of the arcs as a Qt color.
        :param arcthic: the thickness of the arcs in pixels.
        """
        super().__init__(parent)
        if height is None: height = round(parent.height() / 10)
        self.setFixedSize(parent.width(), height)
        self.text = text
        self.perc = perc
        self.perc_text = title
        self.arcpos = arcpos
        self._perc_now = None
        self.update_interval = update_interval
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.do_cmds)
        self.arccol = arccol
        self.arcthic = arcthic
        self.label = QtWidgets.QLabel(self)
        self.arcsize = height
        offset = self.arcsize // 2 + self.arcthic
        x = 0 if 'right' in self.arcpos else offset
        y = 0 if 'bottom' in self.arcpos else offset
        self.label.setGeometry(x, y, self.width() - offset, self.height() - offset)
        self.label.setAlignment(QtCore.Qt.AlignLeft)
        self.label.setWordWrap(True)
        self.arclabel = QtWidgets.QLabel(self)
        lh = self.arcsize // 8
        self.arclabel.setStyleSheet(f"line-height: {lh}px;")  # doesn't seem to be working
        self.arclabel.setScaledContents(True)
        padding = 2
        lw = round(self.arcsize * cos(asin(lh*padding / self.arcsize)))
        x = offset - round(lw/2) if 'left' in arcpos else self.width() - offset - round(lw/2)
        y = offset - round(lh * padding) if 'top' in arcpos else self.height() - offset + padding
        self.arclabel.setGeometry(x, y, lw, lh*padding)
        self.arclabel.setAlignment(QtCore.Qt.AlignCenter)
        self.timer.start(self.update_interval)
        self.do_cmds()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        offset = self.arcthic // 2
        arcsize = self.arcsize - offset * 2
        x = self.width() - offset - arcsize if 'right' in self.arcpos else offset
        y = self.height() - offset - arcsize if 'bottom' in self.arcpos else offset
        start, span = self.angle_args[self.arcpos]
        self.arc(painter, x, y, arcsize, arcsize, start, span, thickness=self.arcthic // 4)
        self.arc(painter, x, y, arcsize, arcsize, start, round(span * self._perc_now / 100), thickness=self.arcthic)
        painter.end()

    def do_cmds(self):
        self._perc_now = float(self.perc())
        self.label.setText(str(self.text))
        self.arclabel.setText(self.perc_text)
        self.update()

    def arc(self, painter, x, y, w, h, start, span, thickness=8):
        """
        Draws a solid arc using the given painter and self.arccol for color. 0deg is right and 90deg is up.
        :param painter: the QPainter object to use for drawing.
        :param x: the x coordinate to begin drawing at, relative to this widget.
        :param y: the y coordinate to begin drawing at, relative to this widget.
        :param w: the width of the final shape in pixels.
        :param h: the height of the final shape in pixels.
        :param start: the angle (in degrees) to start the arc at.
        :param span: the angle (in degrees) the arc should span in total.
        :param thickness: the line thickness to use for the arc, in pixels.
        """
        painter.setPen(QPen(self.arccol, thickness, QtCore.Qt.SolidLine))
        painter.drawArc(x, y, w, h, start * 16, span * 16)


class ProgressBarWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget, perc: Callable = None, height: int = None, update_interval: int = None,
                 barcol: QColor = QtCore.Qt.white, bgcol: QColor = QtCore.Qt.gray, squareness: float = 3):
        """A progress bar that can be manually updated or given a command and an update interval for automatic updates.
        :param parent: the parent widget of this widget, usually a sub-widget of the main window.
        :param perc: a function/command that produces a float between 0 and 1.
        :param height: the height of the widget in pixels. If none, the height is a tenth of the parent widget's.
        :param update_interval: the time in ms between calls to the perc function. Only relevant if perc is given too.
        :param barcol: the color of the bar as a Qt color.
        :param bgcol: the color of the unfilled portion of the bar
        :param squareness: how square the corners should be. Radius of curvature is height divided by this.
        """
        super().__init__(parent)
        if height is None: height = round(parent.height() / 10)
        self.setFixedHeight(height)
        self.barcol = barcol
        self.bgcol = bgcol
        self._progress = 0
        self.squareness = squareness
        pol = self.sizePolicy()
        pol.setHorizontalStretch(255)  # max stretch
        self.setSizePolicy(pol)
        if perc is not None:
            self.perc = perc
            self.update_interval = update_interval
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.update)
            self.timer.start(self.update_interval)
        self.set_progress(0)

    def set_progress(self, perc: float = None):
        """Call this without an argument to update from the perc command given in the constructor, or with a value from 0-1 to manually set the progress.
        :param perc: a float from 0 to 100.
        """
        if perc is None: perc = self.perc()  # will fail if you don't provide a percentage in constructor or argument
        self._progress = min(100, max(0, perc))  # force progress to stay between 0 and 1
        self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        rad = round(h/self.squareness)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, rad, rad)
        painter.fillPath(path, self.bgcol)
        path = QPainterPath()
        path.addRoundedRect(0, 0, w * self._progress, h, rad, rad)
        painter.fillPath(path, self.barcol)

        painter.end()


class GraphWidget(pg.PlotWidget):
    def __init__(self, parent: QtWidgets.QWidget, title: Union[JITstring, str], getdata: Callable, height: int = -1,
                 update_interval: int = 500, time_span: int = 60000, yrange=(0, 100),
                 ylabel_str_fn=str, linecolor=(128, 128, 128, 255), linewidth: float = None):
        """
        A widget showing a graph with time as the x-axis and a title.
        :param parent: the parent widget of this widget, usually the main window.
        :param title: the title for the graph.
        :param getdata: a function or command that returns numerical data.
        :param height: the height of the widget in pixels. Set to None for responsive, and -1 to automatically set fixed height (default).
        :param update_interval: how often (in ms) the graph should update.
        :param time_span: the range in ms for the x-axis.
        :param yrange: the range for the y-axis, as a tuple with (min, max).
        :param ylabel_str_fn: a function returning the labels for the y-axis. Must take a y value and return a str.
        :param linecolor: the color of the graph. Can be (R,G,B,[A]) tuple (values from 0-255), "#RGB" or "#RRGGBBAA" hex strings, QColor, etc.
            See documentation for pyqtgraph.mkColor() for all options.
        :param linewidth: the width of the line.
        """
        super().__init__(parent)
        if height == -1: height = round(parent.height()/10)
        if height is not None: self.setFixedHeight(height)
        self.graph_title = title
        self.xs = list(range(time_span // update_interval))
        self.ys = [0] * len(self.xs)
        self.update_interval = update_interval
        self.getdata = getdata
        self.setBackground(None)
        self.setTitle(title)
        self.setStyleSheet("background-color:transparent;")
        pen = pg.mkPen(color=linecolor) if linewidth is None else pg.mkPen(color=linecolor, width=linewidth)
        self.setXRange(0, self.xs[-1], padding=0)
        self.getAxis('bottom').setStyle(showValues=False, tickLength=0)
        self.getAxis('left').setStyle(tickLength=0)
        if yrange:
            self.setYRange(*yrange, padding=0)
            dy = yrange[1] - yrange[0]
            ticks = [i * dy for i in (0.04, 0.25, 0.5, 0.75, 0.96)]
            tickstrs = [i * dy for i in (0, 0.25, 0.5, 0.75, 1)]
            tickstrs = [ylabel_str_fn(i) for i in tickstrs]
            self.getAxis('left').setTicks([list(zip(ticks, tickstrs)), []])
        self.data_line = self.plot(self.xs, self.ys, pen=pen)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(update_interval)
        self.timer.timeout.connect(self.update_plot_data)
        self.timer.start()

    def update_plot_data(self):
        self.ys.pop(0)
        self.ys.append(float(self.getdata))
        self.data_line.setData(self.xs, self.ys)


class _MediaListFramework(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget, imgsize: int = 200, butsize: int = 50, update_interval: int = 250):
        """
        A skeleton of a MediaListWidget for platform-specific subclasses to inherit from. Does nothing on its own.
        :param parent: the parent widget of this widget, usually the main window.
        :param imgsize: the size of the album art image in pixels.
        :param butsize: the size of the media control buttons in pixels.
        :param update_interval: the time in ms between updates for progress bars.
        """
        super().__init__(parent)
        self.butsize = butsize
        self.imgsize = imgsize
        self.update_interval = update_interval
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.mediawidgets = {}

    def remove_widget(self, widget):
        """
        Removes and deletes the given media widget from this list widget.
        :param widget: the child widget of this widget to be removed. Will be deleted.
        """
        widget.hide()
        self.mediawidgets.pop(widget.player)
        self.layout.removeWidget(widget)
        widget.deleteLater()

    def add_widget(self, widget, name):
        """
        Adds a media widget to this list widget.
        :param widget: the widget to add.
        :param name: the name to store the widget under.
        """
        self.layout.addWidget(widget)
        self.mediawidgets[name] = widget


class _MediaFramework(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget, imgsize: int = None, butsize: int = None, update_interval: int = 250):
        """
        A skeleton of a MediaWidget for platform-specific subclasses to inherit from. Does nothing on its own.
        :param parent: the parent widget of this widget, usually the MediaListWidget controlling it.
        :param imgsize: the size of the album art in pixels.
        :param butsize: the size of the media control buttons in pixels.
        :param update_interval: the time in ms between updates for progress bars.
        """
        super().__init__(parent)
        self.albumart = None
        if imgsize is None: imgsize = round(parent.parent().height()/10)
        self.imgsize = imgsize
        if butsize is None: butsize = round(imgsize/4)
        self.butsize = butsize
        self.playername = None
        self.update_interval = update_interval
        self.displaytext = ""
        self.playing = False

        self.infolabel = QtWidgets.QLabel(self)
        self.infolabel.setWordWrap(True)
        self.infolabel.setScaledContents(True)
        self.playernamelabel = QtWidgets.QLabel(self)
        self.playernamelabel.setWordWrap(True)
        self.playernamelabel.setScaledContents(True)
        self.layout = QtWidgets.QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout = QtWidgets.QVBoxLayout()
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.imglabel = QtWidgets.QLabel(self)
        self.imglabel.setFixedSize(imgsize, imgsize)
        self.imglabel.setScaledContents(True)
        self.imglabel.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.imglabel)
        self.info_layout.addWidget(self.infolabel)
        self.info_layout.addWidget(self.playernamelabel)

        self.ctrllayout = QtWidgets.QHBoxLayout()
        self.setStyleSheet("""
        QPushButton{
            background-color: grey;
        } 
        QPushButton:hover{
            background-color: white;
        }
        QProgressBar{
            min-height: 12px;
            max-height: 12px;
            border-radius: 4px;
            background-color: grey;
        }
        QProgressBar::chunk{
        background-color: white; 
        border-radius: 4px;
        }""")

        self.buttons = [QtWidgets.QPushButton(), QtWidgets.QPushButton(), QtWidgets.QPushButton()]
        for but in self.buttons:
            but.setFixedSize(butsize, butsize)
            self.ctrllayout.addWidget(but)
        lpoints = [QtCore.QPoint(round(butsize * i), round(butsize * j)) for i, j in
                   [(1, 0), (0.6, 0.25), (0.6, 0), (0, 0.5), (0.6, 1), (0.6, 0.75), (1, 1)]]
        ppoints = [QtCore.QPoint(0, 0), QtCore.QPoint(butsize, round(butsize / 2)), QtCore.QPoint(0, butsize)]

        npoints = [QtCore.QPoint(round(butsize * i), round(butsize * j)) for i, j in
                   [(0, 0), (0.4, 0.25), (0.4, 0), (1, 0.5), (0.4, 1), (0.4, 0.75), (0, 1)]]
        for but, pts in zip(self.buttons, (lpoints, ppoints, npoints)): but.setMask(QRegion(QPolygon(pts)))
        for but, fn in zip(self.buttons, (self.do_prev, self.do_playpause, self.do_next)):
            but.clicked.connect(fn)

        self.pbar = ProgressBarWidget(self, height=self.height()//2.5)
        pol = self.pbar.sizePolicy()
        pol.setRetainSizeWhenHidden(True)
        self.pbar.setSizePolicy(pol)

        self.info_layout.addLayout(self.ctrllayout)
        self.info_layout.addWidget(self.pbar)
        self.layout.addLayout(self.info_layout)

        placeholder = QtWidgets.QWidget()  # to make the spacing equal - otherwise have to set spacing to 0 and adjust content margins
        placeholder.setMaximumSize(0, 0)
        self.layout.addWidget(placeholder)

        self.setFixedHeight(imgsize)
        self.playernamelabel.setText(f"<b>{self.playername}</b>")

    def _redraw_playpause_button(self):
        """
        Sets the icon on the play/pause button depending on the value of self.playing
        """
        bs = self.butsize
        if self.playing:
            reg = QRegion(0, 0, round(bs/3), bs)
            reg = reg.united(reg.translated(round(2*bs/3), 0))
            self.buttons[1].setMask(reg)
        else:
            self.buttons[1].setMask(QRegion(QPolygon([QtCore.QPoint(x, y) for x, y in
                                                      [(0, 0), (bs, round(bs/2)), (0, bs)]])))
        self.update()

    def do_next(self):
        """
        Request the next song.
        """
        raise NotImplementedError

    def do_prev(self):
        """
        Request the previous song.
        """
        raise NotImplementedError

    def do_playpause(self):
        """
        Request to start playing if paused, or to pause if playing.
        """
        raise NotImplementedError

    def progressupdate(self, perc):
        """
        Updates the progress bar percentage.
        :param perc: the percentage to update the bar with. From 0-1 inclusive.
        """
        self.pbar.set_progress(perc)

    def played(self):
        """
        Call this when the playback starts.
        """
        self.playing = True
        self._redraw_playpause_button()

    def paused(self):
        """
        Call this when the playback is paused.
        """
        self.playing = False
        self._redraw_playpause_button()

    def stopped(self):
        """
        Call this when the playback is stopped.
        """
        self.playing = False
        self._redraw_playpause_button()


class HrWidget(QtWidgets.QFrame):
    def __init__(self, height: int = 3):
        """
        A horizontal rule across the window.
        :param height: the height in pixels of the line.
        """
        super().__init__()
        self.setMinimumWidth(1)
        self.setFixedHeight(height)
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)


class TextWidget(QtWidgets.QLabel):
    def __init__(self, parent, text: Union[JITstring, str] = None, alignment: str = "Center", wordwrap: bool = True, update_interval: int = None):
        """
        A simple widget for showing text; can be a dynamic JITstring or regular static text.
        :param parent: the parent widget containing this one.
        :param text: the text to be displayed.
        :param alignment: the alignment style for the text; any of Qt's values, such as "Center", "Left", "Right", etc.
        :param wordwrap: whether word wrap should be enabled for the text.
        :param update_interval: how often to refresh the text, if it's dynamic. Leave as None for static text.
        """
        if text is None: super().__init__(parent)
        else: super().__init__(str(text), parent)
        self.setWordWrap(wordwrap)
        self.setAlignment(getattr(QtCore.Qt, "Align" + alignment))
        if update_interval is not None:
            self.get_text = text
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.do_cmds)
            self.timer.start(update_interval)

    def do_cmds(self):
        self.setText(str(self.get_text))



def html_table(array: list, title='', right_td_style: str = "text-align:right;") -> str:
    """
    Creates a 2 column HTML table out of the provided info for use in pywidgets.
    :param array: a list of lists where each secondary list has two rows.
    :param title: the title of the table.
    :param right_td_style: a CSS style to be given to the right cells.
    :return: a string containing the HTML data for the table.
    """
    table = title + '<table width=100%>'
    for row in array:
        table += f'<tr><td>{row[0]}</td><td style="{right_td_style}">{row[1]}</td></tr>'
    table += '</table>'
    return table


def get_application(*args, **kwargs) -> QtWidgets.QApplication:
    """
    A wrapper function for QtWidgets.QApplication. Any arguments passed to this function will be passed on.
    :return: the new QApplication instance.
    """
    return QtWidgets.QApplication(*args, **kwargs) if args or kwargs else QtWidgets.QApplication([])


def get_window(app: QtWidgets.QApplication, width: Union[int, str] = "default", offset: int = 1,
               stylesheet: str = "default", **kwargs) -> Window:
    """
    A wrapper function for creating a new window with dimensions {width} by your screen height on the right edge of the screen.
    Any other keyword arguments passed to this function will be passed on to the Window class.
    :param app: the QApplication instance, can be created with get_application() as a convenience wrapper.
    :param width: the width the new window should have, in pixels, or one of the strings "default" (for ~1/8th width) or "max".
    :param offset: the amount of pixels left the window should be moved to account for how visible the edge is. Ignored if width is max.
    :param stylesheet: a css stylesheet for the window to use.
    :return: the new Window instance.
    """
    window_dims = app.primaryScreen().availableGeometry()
    height = window_dims.height()
    if type(width) == str:
        if width.lower() == "default": width = round(window_dims.width()*17/128)  # a bit wider than 1/8th of the screen. 4K->510px
        elif width.lower() == "max":
            width = window_dims.width()
            offset = 0
        else: raise ValueError(f"No preset width corresponding to given argument {width} in get_window().")
    window = Window(width, height, stylesheet, **kwargs)
    window.move(QtWidgets.QDesktopWidget().availableGeometry().width() - width - offset, 0)
    return window
