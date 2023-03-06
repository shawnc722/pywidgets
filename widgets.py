#!/usr/bin/python3.8
from typing import Union, Callable
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtGui import QPainter, QPen, QPolygon, QRegion, QColor, QPainterPath
from pywidgets.JITstrings import JITstring
import pyqtgraph as pg
from math import asin, cos


class Window(QtWidgets.QMainWindow):
    def __init__(self, width: int, height: int, stylesheet: str = "default", maintain_position: str = "bottom",
                 default_color: QColor = QtCore.Qt.GlobalColor.gray, flags: QtCore.Qt.WindowType = None):
        """
        The main window containing all your pywidgets. After instantiating one of these,
        call its finish_init() method with a list of the pywidgets you want in the window to complete the setup.
        :param width: the width of the window in pixels.
        :param height: the height of the window in pixels.
        :param stylesheet: a css stylesheet for all the widgets - usually contains at least a color and a font-family.
        :param maintain_position: where the window should stay - "bottom" to appear part of the desktop, "top" to stay
            on top, or "default" to behave like a normal window.
        :param default_color: the color for all widgets to default to, if not provided a different color as an argument.
            Accepts anything that can be cast to a QColor.
        :param flags: Window type flags, to be passed along to the QMainWindow class.
        """
        if flags is not None: super().__init__(flags=flags)
        else: super().__init__()
        self.main_widget = None
        self.layout = None
        self.title = "PyWidget"
        self.default_color = QColor(default_color)
        self.setWindowTitle(self.title)
        self.setFixedSize(width, height)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        types = QtCore.Qt.WindowType
        flags = types.FramelessWindowHint
        if maintain_position.lower() == 'bottom': flags = flags | types.Tool | types.WindowStaysOnBottomHint
        elif maintain_position.lower() == 'top': flags = flags | types.Tool | types.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if stylesheet == 'default':
            stylesheet = "color: grey; font-family: Inter, Helvetica, Roboto, sans-serif; " + \
                         f"font-size: {round(self.height() / 100)}px;"  # font-family borrowed from elementary OS
        self.setStyleSheet(stylesheet)
        self.style().polish(self)  # force the stylesheet to be handled now before initializing widgets for proper inheritance
        self.main_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.main_widget)
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

    def finish_init(self, layout: QtWidgets.QLayout = None, add_stretch: bool = True, spacing: int = None) -> None:
        """
        Adds the stored pywidgets to the Window and finishes off the setup. Uses a custom layout if provided.
        :param layout: a Qt layout to use for the widgets.
        :param add_stretch: whether to pad the end of the layout with blank space to condense the widgets. Only works with
            certain types of layouts.
        :param spacing: the spacing in pixels between widgets. Use None for default settings.
        """
        if layout is None:
            layout = QtWidgets.QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
        self.layout = layout
        self.main_widget.setLayout(self.layout)
        for widget in self.widgets: self.layout.addWidget(*widget)
        if add_stretch: self.layout.addStretch()
        if spacing is not None: self.layout.setSpacing(spacing)
        self.show()


class BaseWidget(QtWidgets.QWidget):
    """A basic widget class, meant to be overridden by other widgets."""
    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.setFont(parent.font())
        if hasattr(parent, 'default_color'): self.default_color = parent.default_color
        else: self.default_color = QColor(QtCore.Qt.GlobalColor.black)

    @classmethod
    def ghetto_inherit(cls, child, parent):
        """A temporary workaround for widgets which inherit from other classes that break multiple inheritance with BaseWidget.
        Currently, only pyqtgraph's PlotWidget."""
        child.setFont(parent.font())
        if hasattr(parent, 'default_color'):
            child.default_color = parent.default_color
        else:
            child.default_color = QColor(QtCore.Qt.GlobalColor.black)


class ArcsWidget(BaseWidget):
    def __init__(self, parent: QtWidgets.QWidget, percs: Union[list, Callable], percent: bool = True, size: int = None,
                 update_interval: Union[int, None] = 1000, arccol: QColor = None, arcthic: int = 0,
                 arcstart: float = 270., arcspan: float = -270., arcspace: int = None):
        """Concentric arcs showing the percentage of each of the items in percs. The first item in the list is the outermost arc.
        :param parent: the parent widget of this widget, usually the main window.
        :param percs: either a list of commands or a single function/command that produces a list. Results must match the percent argument.
        :param percent: whether percs is in percentage (0-100) or decimal (0-1).
        :param size: the radius of the arcs.
        :param update_interval: the time in ms between calls to the percs function(s). Can be None if you call do_cmds() manually.
        :param arccol: the color of the arcs as a Qt color. Leave as None to use the parent widget's default color.
        :param arcthic: the thickness of the arcs in pixels. Set to 0 to use half the text height.
        :param arcstart: the angle in degrees to start drawing the arc at, relative to the x-axis and moving counter-clockwise.
        :param arcspan: the angle in degrees the arc should span in total; positive moves counter-clockwise.
        :param arcspace: the spacing between the centers of each arc. Leave it as None to use the font's line spacing.
        """
        super().__init__(parent)
        if size is None: size = round(parent.height() / 10)
        self.setFixedSize(size, size)
        self.percs = percs
        self.percent = percent
        self._percs_now = None
        self.arccol = self.default_color if arccol is None else arccol
        self.arcstart = arcstart
        self.arcspan = arcspan
        if arcthic == 0: arcthic = round(self.fontMetrics().height() / 2)
        self.arcthic = arcthic
        if arcspace is None: arcspace = self.fontMetrics().lineSpacing()
        self.arcspace = arcspace
        if update_interval:
            self.update_interval = update_interval
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.do_cmds)
            self.timer.start(self.update_interval)
        self.do_cmds()

    def do_cmds(self):
        if type(self.percs) == list:
            self._percs_now = [float(i) for i in self.percs]
        else:
            self._percs_now = list(self.percs())
        if self.percent: self._percs_now = [i/100 for i in self._percs_now]
        self.update()

    def center_at(self, x: int, y: int) -> None:
        """Convenience function to move the center of the arcs to the given coordinates."""
        offset = round(self.height() / 2)
        self.move(x - offset, y - offset)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.arccol, max(self.arcthic // 4, 1), QtCore.Qt.PenStyle.SolidLine)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        for i, perc in enumerate(self._percs_now):
            ioff = i * 2 * self.arcspace + self.arcthic
            arcsize = self.height() - ioff
            ioff = round(ioff / 2)
            painter.drawArc(ioff, ioff, arcsize, arcsize, self.arcstart * 16, self.arcspan * 16)
            pen.setWidth(self.arcthic)
            painter.setPen(pen)
            painter.drawArc(ioff, ioff, arcsize, arcsize, self.arcstart * 16, round(self.arcspan * perc * 16))
            pen.setWidth(max(self.arcthic // 4, 1))
            painter.setPen(pen)
        painter.end()


class ProgressArcsWidget(BaseWidget):
    pos_options = ("bottom left", "bottom right", "top right", "top left")

    def __init__(self, parent: QtWidgets.QWidget, text: Union[JITstring, str], percs: Union[list, Callable],
                 percent: bool = True, title: Union[JITstring, str] = None, height: int = None, update_interval: int = 1000,
                 arccol: QColor = None, arcthic: float = 0.6, arcpos: str = "top left"):
        """A widget that displays percentage values as arcs around some text - or a JITstring, for dynamic text.
        :param parent: the parent widget of this widget, usually the main window.
        :param text: the text for the arcs to be drawn around.
        :param percs: either a list of commands or a single function/command that produces a list. Results must match the percent argument.
        :param percent: whether the results of percs are in percent (0-100) or decimal (0-1).
        :param height: the height of the widget in pixels.
        :param update_interval: the time in ms between calls to the percs function(s)
        :param arccol: the color of the arcs as a Qt color. Leave as None to use the parent widget's default color.
        :param arcthic: the thickness of the arcs relative to the text height. Set to 0 to auto-match the default underline position.
        :param title: an optional title that sits above the text.
        :param arcpos: where to place the arcs; one of ["top left", "top right", "bottom left", "bottom right"]
        """
        super().__init__(parent)
        if height is None: height = round(parent.height() / 10)
        self.setFixedSize(parent.width(), height)
        self.text = text
        self.update_interval = update_interval
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.do_cmds)
        fonth = self.fontMetrics().height()
        if arcthic == 0.:
            arcthic = (fonth - self.fontMetrics().underlinePos()) / 2
        else:
            arcthic = fonth * arcthic
        arcpos = arcpos.lower()
        if arcpos not in self.pos_options:
            raise ValueError(f"arcpos {arcpos} is invalid: must be one of {self.pos_options}.")
        self.label_wrapper = QtWidgets.QWidget(self)
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setDirection(self.layout.Direction.BottomToTop if 'top' in arcpos else self.layout.Direction.TopToBottom)
        self.label_wrapper.setLayout(self.layout)
        self.label = TextWidget(self)
        self.label.setIndent(0)
        self.layout.setSpacing(0)
        self.layout.addWidget(self.label)
        self.layout.addStretch(1)
        self.title = title
        arcsize = self.height() - round(max((self.fontMetrics().lineSpacing() - arcthic) / 2, 0))
        offset = round(arcsize / 2)
        yoff = offset if "top" in arcpos else 0
        xoff = offset if "left" in arcpos else 0
        self.label_wrapper.setGeometry(xoff, yoff, self.width() - offset, self.height() - offset)
        arcstart = 90 * self.pos_options.index(arcpos)
        self.arcs = ArcsWidget(self, percs, percent, arcsize, None, arccol, arcthic, arcstart, -270)
        ypos = yoff if yoff != 0 else self.height() - offset
        xpos = xoff if xoff != 0 else self.width() - offset
        self.arcs.center_at(xpos, ypos)
        if title is not None:
            self.title_label = TextWidget(self)
            self.layout.addWidget(self.title_label)
            ls = self.fontMetrics().lineSpacing()
            self.label_wrapper.setGeometry(xoff, max(yoff - ls, 0), self.width() - offset, self.height() - offset + ls)
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignBottom)
        self.label.setWordWrap(True)
        if self.update_interval: self.timer.start(self.update_interval)
        self.do_cmds()

    def do_cmds(self):
        self.label.setText(str(self.text))
        if hasattr(self, 'title_label'): self.title_label.setText(str(self.title))
        self.arcs.do_cmds()
        self.update()


class ProgressBarWidget(BaseWidget):
    def __init__(self, parent: QtWidgets.QWidget, perc: Callable = None, height: int = None, update_interval: int = None,
                 barcol: QColor = QtCore.Qt.GlobalColor.white, bgcol: QColor = None, squareness: float = 3):
        """A progress bar that can be manually updated or given a command and an update interval for automatic updates.
        :param parent: the parent widget of this widget, usually a sub-widget of the main window.
        :param perc: a function/command that produces a float between 0 and 1.
        :param height: the height of the widget in pixels. If none, the height is a tenth of the parent widget's.
        :param update_interval: the time in ms between calls to the perc function. Only relevant if perc is given too.
        :param barcol: the color of the bar as a Qt color.
        :param bgcol: the color of the unfilled portion of the bar as a Qt color. Leave as None to use the parent widget's default color.
        :param squareness: how square the corners should be. Radius of curvature is height divided by this.
        """
        super().__init__(parent)
        if height is None: height = round(parent.height() / 10)
        self.setFixedHeight(height)
        self.barcol = QColor(barcol)
        self.bgcol = QColor(bgcol) if bgcol is not None else self.default_color
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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, rad, rad)
        painter.fillPath(path, self.bgcol)
        path = QPainterPath()
        path.addRoundedRect(0, 0, w * self._progress, h, rad, rad)
        painter.fillPath(path, self.barcol)

        painter.end()


class GraphWidget(pg.PlotWidget):  # also inherits from  BaseWidget, but currently using a workaround
    def __init__(self, parent: QtWidgets.QWidget, title: Union[JITstring, str], getdata: Callable, height: int = -1,
                 update_interval: int = 500, time_span: int = 60000, yrange=(0, 100),
                 ylabel_str_fn=str, linecolor=None, linewidth: float = None, lines: int = 1):
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
            See documentation for pyqtgraph.mkColor() for all options. Leave as None to use the parent widget's default color.
        :param linewidth: the width of the line.
        :param lines: how many lines to be drawn - if greater than 1, getdata must return a list of the multiple line data.
        """
        super().__init__(parent)
        BaseWidget.ghetto_inherit(self, parent)
        if height == -1: height = round(parent.height()/10)
        if height is not None: self.setFixedHeight(height)
        self.graph_title = title
        if linecolor is None: linecolor = self.default_color
        self.xs = list(range(time_span // update_interval))
        self.ys = [0] * len(self.xs) if lines == 1 else [[0] * len(self.xs)] * lines
        self.update_interval = update_interval
        self.getdata = getdata
        self.lines = lines
        self.setTitle(title, size=f"{self.fontInfo().pixelSize()}px")
        self.getPlotItem().titleLabel.item.setFont(self.font())
        self.setStyleSheet("background-color: transparent;")
        pen = pg.mkPen(color=linecolor) if linewidth is None else pg.mkPen(color=linecolor, width=linewidth)
        self.setXRange(0, self.xs[-1], padding=0)
        self.getAxis('bottom').setStyle(showValues=False, tickLength=0)
        self.getAxis('left').setStyle(tickLength=0, tickAlpha=0, hideOverlappingLabels=False, tickFont=self.font())
        if yrange:
            self.setYRange(*yrange, padding=0)
            dy = yrange[1] - yrange[0]
            num_ticks = 5
            tick_offset = 0.06  # % of y-axis to move the tick labels upwards by (causes imprecision in the middle labels)
            tickstrs = [ylabel_str_fn(i/(num_ticks - 1) * dy) for i in range(num_ticks)]
            ticks = [(i * (1 - tick_offset) / (num_ticks - 1) + tick_offset) * dy for i in range(num_ticks)]
            self.getAxis('left').setTicks([list(zip(ticks, tickstrs)), []])
        if lines == 1: self.data_line = self.plot(self.xs, self.ys, pen=pen)
        else: self.data_lines = self.multiDataPlot(x=self.xs, y=self.ys, pen=pen)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(update_interval)
        self.timer.timeout.connect(self.update_plot_data)
        self.timer.start()

    def update_plot_data(self):
        if self.lines == 1:
            self.ys.pop(0)
            self.ys.append(float(self.getdata()))
            self.data_line.setData(self.xs, self.ys)
        else:
            data = self.getdata()
            for i, y in enumerate(self.ys):
                y.pop(0)
                y.append(data[i])
                self.data_lines[i].setData(self.xs, y)


class _MediaListFramework(BaseWidget):
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
        self.setFont(parent.font())
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


class _MediaFramework(BaseWidget):
    def __init__(self, parent: QtWidgets.QWidget, imgsize: int = None, butsize: int = None, update_interval: int = 250,
                 primary_color: Union[str, QColor] = None, secondary_color: Union[str, QColor] = 'white'):
        """
        A skeleton of a MediaWidget for platform-specific subclasses to inherit from. Does nothing on its own.
        :param parent: the parent widget of this widget, usually the MediaListWidget controlling it.
        :param imgsize: the size of the album art in pixels.
        :param butsize: the size of the media control buttons in pixels.
        :param update_interval: the time in ms between updates for progress bars.
        :param primary_color: the color to use for most of the widget. Accepts a QColor or CSS color strings. Leave as None to use
        the parent widget's default color.
        :param secondary_color: the color to use for buttons when the mouse is hovering over them, and for the progress bar.
        Accepts a QColor or CSS color strings.
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
        if primary_color is None: primary_color = self.default_color

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
        style = """
        QPushButton{
            background-color: $c1;
        } 
        QPushButton:hover{
            background-color: $c2;
        }"""
        style = style.replace('$c1', primary_color if type(primary_color) == str else f'rgba{primary_color.getRgb()}')
        style = style.replace('$c2', secondary_color if type(secondary_color) == str else f'rgba{secondary_color.getRgb()}')
        self.setStyleSheet(style)

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

        self.pbar = ProgressBarWidget(self, height=int(self.height()//2.5), bgcol=primary_color, barcol=secondary_color)
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
        self.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Minimum)


class TextWidget(QtWidgets.QLabel, BaseWidget):
    def __init__(self, parent, text: Union[JITstring, str] = None, alignment: str = "Center", wordwrap: bool = True,
                 update_interval: int = None):
        """
        A simple widget for showing text; can be a dynamic JITstring or regular static text.
        :param parent: the parent widget containing this one.
        :param text: the text to be displayed.
        :param alignment: the alignment style for the text; any of Qt's values, such as "Center", "Left", "Right", etc.
        :param wordwrap: whether word wrap should be enabled for the text.
        :param update_interval: how often to refresh the text, if it's dynamic. Leave as None for static text.
        """
        super().__init__(parent)
        self.setWordWrap(wordwrap)
        self.setAlignment(getattr(QtCore.Qt.AlignmentFlag, "Align" + alignment))
        self.get_text = text
        if update_interval is not None:
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.do_cmds)
            self.timer.start(update_interval)
        self.do_cmds()

    def do_cmds(self):
        self.setText(str(self.get_text))


def html_table(array: list, title='', style: str = "border-collapse: collapse;", right_td_style: str = "text-align: right;",
               tstyle: str = "text-align: center;") -> str:
    """
    Creates a 2 column HTML table out of the provided info for use in pywidgets.
    :param array: a list of lists where each secondary list has two rows.
    :param title: the title of the table.
    :param style: a CSS style for the table element.
    :param right_td_style: a CSS style to be given to the right cells.
    :param tstyle: the css style element for the title
    :return: a string containing the HTML data for the table.
    """
    table = f'<div style="{tstyle}">{title}</div>' if title else ''
    table += f'<table width=100% style="{style}">'
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
    window.move(window_dims.width() - width - offset, 0)
    return window
