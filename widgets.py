import os
from typing import Callable, Sequence, Self
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, pyqtSlot, QSize
from PyQt6.QtGui import QPainter, QPen, QColor, QScreen, QResizeEvent, QPalette, QAction, QPixmap, QPainterPath, QIcon
from PyQt6.QtSvg import QSvgRenderer
from pywidgets.JITstrings import JITstring, PyCmd
import pyqtgraph as pg
import numpy as np

try:
    import asyncio, qtinter  # optional, only required for certain widgets that use async (windows media widget, etc)
    from asyncio import Task, sleep

    loop: qtinter.QiProactorEventLoop | None = None
except ImportError: asyncio, qtinter, loop = None, None, None
_use_async = False
_app: QtWidgets.QApplication | None = None


class Window(QtWidgets.QMainWindow):
    default_stylesheet = "font-family: Inter, Helvetica, Roboto, sans-serif;"
    default_palette = QPalette()
    default_palette.setColor(QPalette.ColorRole.Window, QColor('grey'))
    default_palette.setColor(QPalette.ColorRole.WindowText, QColor('grey'))
    default_palette.setColor(QPalette.ColorRole.Light, QColor('white'))
    default_palette.setColor(QPalette.ColorRole.Shadow, QColor('black'))

    def __init__(self, font_size_vh: float = 1.0, stylesheet: str = "default", palette: QPalette = None,
                 background_color: tuple[int, int, int, int] = None, maintain_position: str = "bottom",
                 set_size: Callable[[Self, QRect], None] = None, use_async: bool = False,
                 shadow_radius: float = 3, window_flags: Qt.WindowType = None, application_flags: list[str] = None):
        """
        The main window containing all your pywidgets. After instantiating one of these,
        call its finish_init() method with a list of the pywidgets you want in the window to complete the setup.

        :param font_size_vh: the font size, in css vh (percentage of screen height) to use.
        :param stylesheet: a css stylesheet for all the widgets - usually contains at least a font-family.
            Using a 'color' tag will overwrite the palette's WindowText color.
        :param palette: the colors for all widgets to default to, if not provided a different color as an argument.
            Takes a QT QPalette object. The stylesheet's 'color' tag, if there is one, will overwrite the Window color.
            The Window color is typically the main color for widgets, WindowText is for text, and Light for highlights.
        :param background_color: an RGBA tuple for the background of the page. Defaults to fully transparent.
            Use this argument instead of setting it in stylesheet to avoid each widget's background color stacking.
        :param maintain_position: where the window should stay - "bottom" to appear part of the desktop, "top" to stay
            on top, or "default" to behave like a normal window.
        :param set_size: the method that decides placement and size of the window. Must take the window instance and
            a QRect of available geometry and is responsible for setting the window position and size.
        :param use_async: whether to enable async functionality. Required for some widgets (ie WindowsMediaWidget).
        :param shadow_radius: the radius (in pixels) of the shadow (outline) behind widgets. Set 0 to disable shadow.
            Shadows don't behave well with transparency, so don't use with non-opaque background_color.
        :param window_flags: Window type flags, to be passed along to the QMainWindow class.
        :param application_flags: flags to pass to the Qt QApplication.
        """

        # get (or start) application and initialize window
        global _app
        if _app is None:  # start application if it's not running
            _app = QtWidgets.QApplication(["PyWidgets"] if not application_flags else application_flags)
        super().__init__() if window_flags is None else super().__init__(flags=window_flags)

        if use_async:  # set up the loop to be assigned as Qt's first task, so other widgets can reference it
            global _use_async
            _use_async = True

            def set_loop():
                global loop
                loop = asyncio.get_running_loop()
            run_on_app_start(set_loop)

        # fill out properties
        self.main_widget = None
        self.layout = None
        self.widgets = []
        self.font_size_vh = font_size_vh
        self.main_widget = QWidget()
        self.main_widget.setObjectName("main_widget")
        self.setCentralWidget(self.main_widget)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Maximum)
        if set_size is not None: self.set_size = set_size

        # setup style of window
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("PyWidgets")
        types = Qt.WindowType
        flags = types.FramelessWindowHint
        if maintain_position.lower() == 'bottom': flags = flags | types.Tool | types.WindowStaysOnBottomHint
        elif maintain_position.lower() == 'top': flags = flags | types.Tool | types.WindowStaysOnTopHint
        self.setWindowFlags(flags)

        if stylesheet == 'default':  stylesheet = self.default_stylesheet
        self.setStyleSheet(stylesheet)
        if palette is None: palette = self.default_palette
        _app.setPalette(palette)
        self.style().polish(self)  # force the stylesheet to be handled now before initializing widgets for proper inheritance

        if background_color is not None:
            self.main_widget.setStyleSheet('#main_widget {background-color: rgba(' + ','.join(background_color) + ');}')

        if shadow_radius:  # shadow effect burns in on plotwidget static elements
            sw = self.main_widget
            shadow = QtWidgets.QGraphicsDropShadowEffect(sw)
            shadow.setColor(self.palette().shadow().color())
            shadow.setOffset(0)
            shadow.setBlurRadius(shadow_radius)
            sw.setGraphicsEffect(shadow)

        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Expanding)

        # context menu setup
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.right_click_menu = QtWidgets.QMenu(self)
        self.right_click_menu.setStyleSheet('''
            QMenu::item { padding: 2% 15%; 
                          border-bottom: 1px solid;}
            QMenu::item:selected {border: 2px solid;}
        ''')
        self.customContextMenuRequested.connect(self.right_click_performed)
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.handle_resize)
        self.right_click_menu.addAction(refresh_action)
        self.move_screen_menu = self.right_click_menu.addMenu("Move to Screen")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.exit_clicked)
        self.right_click_menu.addAction(exit_action)

        self.handle_resize()  # sets window size and position

    def resizeEvent(self, a0: QResizeEvent):
        super().resizeEvent(a0)
        self.handle_resize()

    def set_size(self: Self, dims: QRect) -> None:
        width = round(dims.width() * 17 / 128)  # a bit wider than 1/8th of the screen. 4K->510px
        offset = 0  # the amount to move the window left, for better visibility
        self.setFixedWidth(width)
        #self.setMaximumHeight(dims.height())  # disabled for now, see next line
        self.setFixedHeight(dims.height())  # QT doesn't handle resizing on wayland yet, so just take all the height
        self.move(dims.x() + dims.width() - width - offset, dims.y())

    @pyqtSlot()
    def exit_clicked(self, *args):
        self.handle_removed()
        self.close()
        _app.quit()

    @pyqtSlot(QPoint)
    def right_click_performed(self, a0: QPoint):
        self.move_screen_menu.clear()
        for screen in _app.screens():
            act = QAction(screen.name(), self)
            act.triggered.connect(PyCmd(self.handle_resize, screen))
            self.move_screen_menu.addAction(act)
        self.right_click_menu.popup(self.mapToGlobal(a0))

    def handle_removed(self):
        for widget in QtWidgets.QApplication.allWidgets():
            if widget is not self and hasattr(widget, 'handle_removed'): widget.handle_removed()

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

    def handle_resize(self, screen: QScreen = None, _signal: bool = None):
        """Resize and reconfigure the Window, optionally on a specific screen. Uses the geometry from the get_geometry
        argument in Window's init.
        :param screen: The QScreen to use for display, or None for the current one.
        :param _signal: the signal of the menuitem that's passed along when clicked; ignored."""
        if type(screen) == bool: screen = None  # if called from the right click menu, sends a bool
        if screen is not None: self.setScreen(screen)
        dims = self.screen().availableGeometry()
        font = self.font()
        newsize = round(self.font_size_vh / 100 * dims.height())
        if newsize != font.pixelSize():
            font.setPixelSize(newsize)
            _app.setFont(font)  # set font on the whole app, so it propagates downward.
        self.set_size(dims)

    def finalize(self, layout: QtWidgets.QLayout = None, add_stretch: bool = True, spacing: int = None) -> None:
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
        self.screen().geometryChanged.connect(self.handle_resize)
        self.show()

    @classmethod
    def start(cls):
        """Equivalent to pywidgets.start() - here for convenience."""
        start()


class ArcsWidget(QWidget):
    def __init__(self, parent: QWidget, percs: Sequence[Callable[[], float]] | Callable[[], Sequence[float]],
                 percent: bool = True, size: float = 1, update_interval: int | None = 1000, arccol: QColor = None,
                 arcthic: float = .5, arcstart: float = 270., arcspan: float = -270., arcspace: float = 1):
        """Concentric arcs showing the percentage of each of the items in percs. The first item in the list is the outermost arc.
        :param parent: the parent widget of this widget, usually the main window.
        :param percs: either a list of commands or a single function/command that produces a list. Results must match the percent argument.
        :param percent: whether percs is in percentage (0-100) or decimal (0-1).
        :param size: the radius of the arcs, in decimal percentage of parent height (1=100%). Use 0 to manage manually.
        :param update_interval: the time in ms between calls to the percs function(s). Can be None if you call do_cmds() manually.
        :param arccol: the color of the arcs as a Qt color. Leave as None to use the parent widget's default color.
        :param arcthic: the thickness of the arcs in decimal percentage of the text height (1 = 100%). Use 0 to manage manually.
        :param arcstart: the angle in degrees to start drawing the arc at, relative to the x-axis and moving counter-clockwise.
        :param arcspan: the angle in degrees the arc should span in total; positive moves counter-clockwise.
        :param arcspace: the spacing between the centers of each arc, in decimal percentage of the space between text lines (1 = 100%).
        """
        super().__init__(parent)
        self.arc_size_perc = size
        self.percs = percs
        self.percent = percent
        self._percs_now = None
        self.arccol = self.palette().window().color() if arccol is None else arccol
        self.arcstart = arcstart
        self.arcspan = arcspan
        self.arcthic_perc = arcthic
        self.arcthic = None
        self.arcspace_perc = arcspace
        self.arcspace = None

        if update_interval:
            self.update_interval = update_interval
            self.timer = QTimer()
            self.timer.timeout.connect(self.do_cmds)
            self.timer.start(self.update_interval)
        if self.arcthic_perc and self.arc_size_perc and self.arcspace_perc:  # if it can draw, do it.
            # otherwise, the widget manually controlling these needs to update it.
            self.adjustSize()
            self.do_cmds()

    def resizeEvent(self, a0: QResizeEvent) -> None:
        super().resizeEvent(a0)
        if self.arc_size_perc:
            size = round(self.arc_size_perc * self.parent().height())
            self.setFixedSize(size, size)
        if self.arcthic_perc:
            self.arcthic = round(self.fontMetrics().height() * self.arcthic_perc)
        if self.arcspace_perc:
            self.arcspace = round(self.fontMetrics().lineSpacing() * self.arcspace_perc)

    def do_cmds(self) -> None:
        if isinstance(self.percs, Sequence):
            self._percs_now = [float(i) for i in self.percs]
        else:
            self._percs_now = list(self.percs())
        if self.percent: self._percs_now = [float(i)/100 for i in self._percs_now]
        self.update()

    def center_at(self, x: int, y: int) -> None:
        """Convenience function to move the center of the arcs to the given coordinates."""
        offset = round(self.height() / 2)
        self.move(x - offset, y - offset)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.arccol, max(self.arcthic // 4, 1), Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        for i, perc in enumerate(self._percs_now):
            ioff = i * 2 * self.arcspace + self.arcthic
            arcsize = self.height() - ioff
            ioff = round(ioff / 2)
            painter.drawArc(ioff, ioff, arcsize, arcsize, round(self.arcstart * 16), round(self.arcspan * 16))
            pen.setWidth(self.arcthic)
            painter.setPen(pen)
            painter.drawArc(ioff, ioff, arcsize, arcsize, round(self.arcstart * 16), round(self.arcspan * perc * 16))
            pen.setWidth(max(round(self.arcthic / 4), 1))
            painter.setPen(pen)
        painter.end()


class ProgressArcsWidget(QWidget):
    pos_options = ("bottom left", "bottom right", "top right", "top left")

    def __init__(self, parent: QWidget, text: str | PyCmd | JITstring,
                 percs: Sequence[Callable[[], float]] | Callable[[], Sequence[float]], percent: bool = True,
                 title: JITstring | str = None, height: float = .1, update_interval: int = 1000,
                 arccol: QColor = None, arcthic: float = 0.6, arcpos: str = "top left"):
        """A widget that displays percentage values as arcs around some text - or a JITstring, for dynamic text.
        :param parent: the parent widget of this widget, usually the main window.
        :param text: the text for the arcs to be drawn around.
        :param percs: either a list of commands or a single function/command that produces a list. Results must match the percent argument.
        :param percent: whether the results of percs are in percent (0-100) or decimal (0-1).
        :param height: the height of the widget in decimal percentage of the screen height (1 = 100%).
        :param update_interval: the time in ms between calls to the percs function(s)
        :param arccol: the color of the arcs as a Qt color. Leave as None to use the parent widget's default color.
        :param arcthic: the thickness of the arcs relative to the text height. Set to 0 to auto-match the default underline position.
        :param title: an optional title that sits above the text.
        :param arcpos: where to place the arcs; one of ["top left", "top right", "bottom left", "bottom right"]
        """
        super().__init__(parent)
        self.height_perc = height
        self.text = text
        self.update_interval = update_interval
        self.timer = QTimer()
        self.timer.timeout.connect(self.do_cmds)
        self.arcthic_perc = arcthic
        self.arcthic = None
        self.arcpos = arcpos.lower()
        if self.arcpos not in self.pos_options:
            raise ValueError(f"arcpos {arcpos} is invalid: must be one of {self.pos_options}.")
        self.label_wrapper = QWidget(self)
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

        if title is not None:
            self.title_label = TextWidget(self)
            self.layout.addWidget(self.title_label)

        arcstart = 90 * self.pos_options.index(self.arcpos)

        self.arcs = ArcsWidget(self, percs, percent, 0, None, arccol, 0, arcstart)

        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.label.setWordWrap(True)
        if self.update_interval: self.timer.start(self.update_interval)
        self.adjustSize()
        self.do_cmds()

    def resizeEvent(self, a0: QResizeEvent):
        super().resizeEvent(a0)
        height = round(self.screen().availableGeometry().height() * self.height_perc)
        newdims = a0.size()
        newdims.setHeight(height)
        self.setMinimumHeight(height)
        fonth = self.fontMetrics().height()
        if self.arcthic_perc == 0.:
            arcthic = (fonth - self.fontMetrics().underlinePos()) / 2
        else:
            arcthic = fonth * self.arcthic_perc

        arcsize = newdims.height() - round(max((self.fontMetrics().lineSpacing() - arcthic) / 2, 0))
        offset = round(arcsize / 2)
        yoff = offset if "top" in self.arcpos else 0
        xoff = offset if "left" in self.arcpos else 0
        self.label_wrapper.setGeometry(xoff, yoff, newdims.width() - offset, newdims.height() - offset)

        self.arcs.setFixedSize(arcsize, arcsize)
        if self.title:
            ls = self.fontMetrics().lineSpacing()
            self.label_wrapper.setGeometry(xoff, max(yoff - ls, 0), newdims.width() - offset, newdims.height() - offset + ls)

        ypos = yoff if yoff != 0 else newdims.height() - offset
        xpos = xoff if xoff != 0 else newdims.width() - offset
        self.arcs.arcthic = round(arcthic)
        self.arcs.center_at(xpos, ypos)

    def do_cmds(self):
        self.label.setText(str(self.text))
        if hasattr(self, 'title_label'): self.title_label.setText(str(self.title))
        self.arcs.do_cmds()
        self.update()


class ProgressBarWidget(QWidget):
    def __init__(self, parent: QWidget, perc: Callable[[], float] = None, max_height: int = None,
                 update_interval: int = None, barcol: QColor = None, bgcol: QColor = None, squareness: float = 3):
        """A linear progress bar that can be manually updated or given a command and an update interval for automatic updates.
        :param parent: the parent widget of this widget, usually a sub-widget of the main window.
        :param perc: a function/command that produces a float between 0 and 1. If given, make sure to set update_interval or call set_progress() manually.
        :param max_height: the max height of the widget in pixels. If none, set to one tenth of the parent widget's height.
        :param update_interval: the time in ms between calls to the perc function. Only relevant if perc is given too.
        :param barcol: the color of the bar as a Qt color.
        :param bgcol: the color of the unfilled portion of the bar as a Qt color. Leave as None to use the page default.
        :param squareness: how square the corners should be. Radius of curvature is height divided by this.
        """
        super().__init__(parent)
        if max_height is None: max_height = round(parent.height() / 10)
        self.setMaximumHeight(max_height)
        self.setMinimumHeight(3)  # lowest pixel count that can still be rounded
        self.barcol = QColor(barcol) if barcol else self.palette().light().color()
        self.bgcol = QColor(bgcol) if bgcol is not None else self.palette().window().color()
        self._progress: float = 0
        self.squareness = squareness
        pol = self.sizePolicy()
        pol.setHorizontalStretch(255)  # max stretch
        pol.setVerticalPolicy(pol.Policy.MinimumExpanding)
        self.setSizePolicy(pol)
        if perc is not None: self.perc = perc
        if update_interval is not None:
            self.update_interval = update_interval
            self.timer = QTimer()
            self.timer.timeout.connect(self.set_progress)
            self.timer.start(self.update_interval)
        self.set_progress(0)

    def set_progress(self, perc: float = None):
        """Call this without an argument to update from the perc command given in the constructor, or with a value from 0-1 to manually set the progress.
        :param perc: a float from 0 to 100.
        """
        if perc is None: perc = self.perc()  # will fail if you don't provide a percentage in constructor or argument
        self._progress = min(100., max(0., perc))  # force progress to stay between 0 and 1
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


class GraphWidget(pg.PlotWidget):
    def __init__(self, parent: QWidget, title: JITstring | str, getdata: Callable[[], float] | Callable[[], Sequence[float]],
                 height: int = -1, update_interval: int = 500, time_span: int = 60000, yrange: tuple = (0, 100),
                 ylabel_str_fn: Callable[[float], str] = str, linecolor=None,
                 linecolors: None | Sequence = None, linewidth: float = None, lines: int = 1):
        """
        A widget showing a graph with time as the x-axis and a title.
        :param parent: the parent widget of this widget, usually the main window.
        :param title: the title for the graph.
        :param getdata: a function or command that returns numerical data.
        :param height: the height of the widget in pixels. Set to None for responsive, and -1 to automatically set fixed height (default).
        :param update_interval: how often (in ms) the graph should update.
        :param time_span: the range in ms for the x-axis.
        :param yrange: the range for the y-axis, as a tuple with (bottom, top).
        :param ylabel_str_fn: a function returning the labels for the y-axis. Must take a y value and return a str.
        :param linecolor: the color of the graph's line. Can be (R,G,B,[A]) tuple (values from 0-255), "#RGB" or "#RRGGBBAA" hex strings, QColor, etc.
            See documentation for pyqtgraph.mkColor() for all options. Leave as None to use the parent widget's default color.
        :param linecolors: can only use if lines > 1 and linecolor is None. Must be a list containing colors in the same format as linecolor,
            in the same order as the data returned by getdata.
        :param linewidth: the width of the line.
        :param lines: how many lines to be drawn - if greater than 1, getdata must return a list of the multiple line data.
        """
        super().__init__(parent=None, background=None)
        self.setStyleSheet("background-color:transparent;")
        if height == -1: height = round(parent.screen().availableGeometry().height()/10)
        if height is not None: self.setFixedHeight(height)
        self.graph_title = title
        default_color = parent.palette().window().color()  # use parent palette because the PlotWidget sets its own
        text_color = parent.palette().windowText().color()
        if linecolor is None and linecolors is None: linecolor = default_color
        elif linecolors is not None:
            if linecolor is not None:
                raise AssertionError("linecolor and linecolors arguments to GraphWidget cannot both be given; change one to None.")
            if lines == 1:
                raise AssertionError(f"linecolors argument to GraphWidget can only be used with multiple lines - you gave lines={lines}")
        self.xs = np.arange(0, time_span, update_interval)
        self.ys = np.zeros(self.xs.shape if lines == 1 else (lines, self.xs.shape[0]), np.float64)
        self.update_interval = update_interval
        self.getdata = getdata
        self.lines = lines
        self.setTitle(title, size=f"{self.fontInfo().pixelSize()}px", color=text_color)
        self.getPlotItem().titleLabel.item.setFont(self.font())
        bott = self.getAxis('bottom')
        bott.setStyle(showValues=False, tickLength=0)
        bott.setPen(color=default_color)
        left = self.getAxis('left')
        left.setStyle(tickLength=0, tickAlpha=0, hideOverlappingLabels=False, tickFont=self.font())
        left.setPen(color=default_color)
        left.setTextPen(color=text_color)
        self.setXRange(0, time_span, padding=0)  # method is overloaded by pg.ViewBox one at runtime, ignore IDE warning
        if yrange:
            dy = yrange[1] - yrange[0]
            num_ticks = 5
            tick_offset = 0.06  # % of y-axis to move the tick labels upwards by (causes imprecision in the middle labels)
            tickstrs = [ylabel_str_fn(i/(num_ticks - 1) * dy) for i in range(num_ticks)]
            ticks = [(i * (1 - tick_offset) / (num_ticks - 1) + tick_offset) * dy for i in range(num_ticks)]
            self.getAxis('left').setTicks([list(zip(ticks, tickstrs)), []])
            self.setYRange(*yrange, padding=0)

        if lines == 1:
            pen = pg.mkPen(color=linecolor) if linewidth is None else pg.mkPen(color=linecolor, width=linewidth)
            self.data_line = self.plot(self.xs, self.ys, pen=pen)
        else:
            self.data_lines = self.multiDataPlot(x=self.xs, y=self.ys)
            if linecolor is not None:
                pen = pg.mkPen(color=linecolor) if linewidth is None else pg.mkPen(color=linecolor, width=linewidth)
            for i, line in enumerate(self.data_lines):
                if linecolors is not None:
                    pen = pg.mkPen(color=linecolors[i]) if linewidth is None else pg.mkPen(color=linecolors[i], width=linewidth)
                line.setPen(pen)
        self.timer = QTimer()
        self.timer.setInterval(update_interval)
        self.timer.timeout.connect(self.update_plot_data)
        self.timer.start()

    def update_plot_data(self):
        if self.lines == 1:
            self.ys = np.roll(self.ys, -1)
            self.ys[-1] = float(self.getdata())
            self.data_line.setData(self.xs, self.ys)
        else:
            data = self.getdata()
            self.ys = np.roll(self.ys, -1, axis=1)
            self.ys[:, -1] = data
            for i, y in enumerate(self.ys):
                self.data_lines[i].setData(self.xs, y)


class VisualizerWidget(pg.PlotWidget):
    def __init__(self, parent: QWidget, getdata: Callable[[], Sequence[float]], yrange: tuple = None, linecolor=None,
                 linewidth: float = None, update_interval: int = 500):
        """A mirrored line graphing the output of getdata with no axes, labels, or title. Meant to be used in other widgets.
        :param parent: the parent widget of this widget.
        :param getdata: a function or PyCmd that returns a list of floats. The length of the list must be the same each call.
        :param yrange: the range for the y-axis, as a tuple with (bottom, top).
        :param linecolor: the color of the graph's line. Can be (R,G,B,[A]) tuple (values from 0-255), "#RGB" or "#RRGGBBAA" hex strings, QColor, etc.
            See documentation for pyqtgraph.mkColor() for all options. Leave as None to use the parent widget's default color.
        :param linewidth: the width of the line.
        :param update_interval: how often get_data should be called and the graph updated."""
        super().__init__(parent)
        if linecolor is None: linecolor = self.palette().window().color()
        ys = np.array(getdata())
        self.xs = np.arange(0, len(ys))
        pen = pg.mkPen(color=linecolor) if linewidth is None else pg.mkPen(color=linecolor, width=linewidth)
        self.getdata = getdata
        self.update_interval = 500
        self.setStyleSheet("background-color: transparent;")
        for axis in ('bottom', 'left'):
            self.hideAxis(axis)

        self.setXRange(0, self.xs[-1], padding=0)
        if yrange: self.setYRange(*yrange, padding=0)

        self.data_lines = self.plot(self.xs, ys, pen=pen), self.plot(self.xs, -ys, pen=pen)
        self.timer = QTimer()
        self.timer.setInterval(update_interval)
        self.timer.timeout.connect(self.update_plot_data)
        self.timer.start()

    def update_plot_data(self):
        ys = np.array(self.getdata())
        self.data_lines[0].setData(self.xs, ys)
        self.data_lines[1].setData(self.xs, -ys)


class ImageWithTextWidget(QWidget):
    def __init__(self, parent: QWidget, text: str | JITstring = None, img: bytes | Callable[[], bytes] = None,
                 text_and_img: Callable[[], tuple[str, bytes]] = None, img_size: tuple[int, int] = None,
                 img_side: str = 'left', update_interval: int | None = 1000*60*60):
        """
        A widget for displaying an image beside text.
        :param parent: the parent widget of this widget.
        :param text: the text to display.
        :param img: the image to display as bytes, or a callable (function, PyCmd, etc) that returns an image in bytes.
        :param text_and_img: one callable that returns both text and img parameters in a tuple of (text, img). Both text
            and img parameters are ignored if this isn't None.
        :param img_size: a fixed size for the image in pixels. Default is dependent on how much space the image has.
        :param img_side: which side of the widget the image is on.
        :param update_interval: the time in ms between updates - defaults to 1 hour. Set to None to disable updates.
        """
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        self.get_img = img
        self.get_text = text
        self.text_and_img = text_and_img
        self.img_label = QtWidgets.QLabel(self)
        self.text_label = TextWidget(self, alignment='VCenter')
        if img_size is not None: self.img_label.setFixedSize(*img_size)
        self.img_label.setScaledContents(True)
        self.img_label.setContentsMargins(0, 0, 0, 0)
        self.text_label.setContentsMargins(0, 0, 0, 0)
        ws = (self.img_label, self.text_label)
        if img_side != 'left': ws = ws[::-1]
        for w in ws:
            layout.addWidget(w)
        self.setLayout(layout)
        self.adjustSize()

        if update_interval != -1:
            self.timer = QTimer()
            self.timer.setInterval(update_interval)
            self.timer.timeout.connect(self.do_cmds)
            self.timer.start()
        self.do_cmds()

    def do_cmds(self):
        if self.text_and_img is None:
            text = self.get_text if type(self.get_text) == str else self.get_text()
            img = self.get_img if type(self.get_img) == bytes else self.get_img()
        else:
            text, img = self.text_and_img()
        self.text_label.setText(text)
        pixmap = QPixmap()
        pixmap.loadFromData(img)
        self.img_label.setPixmap(pixmap)


class ColorSvg:
    def __init__(self, data: str, maintain_aspect=True):
        self.svg = data
        self.svg_renderer = QSvgRenderer()
        self.maintain_aspect = maintain_aspect

    def render(self, size: QSize) -> QPixmap:
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self.svg_renderer.render(painter)
        painter.end()
        return pixmap

    def recolor(self, color: QColor):
        self.svg_renderer.load(self.svg.replace('currentColor', 'rgb({},{},{})'.format(*color.getRgb()[:3])).encode())
        if self.maintain_aspect:
            self.svg_renderer.setAspectRatioMode(self.svg_renderer.aspectRatioMode().KeepAspectRatio)


class SvgIcon(QtWidgets.QLabel):
    def __init__(self, parent: QWidget, data: str, min_size=(8, 8), maintain_aspect=True):
        """An icon using SVG syntax that respects the svg currentColor attribute."""
        super().__init__(parent)
        self.svg = ColorSvg(data, maintain_aspect)
        self.min_size = QSize(*min_size)
        self.hover = False
        self.hover_changed = True
        self.setScaledContents(False)
        pol = self.sizePolicy()
        pol.setHorizontalPolicy(pol.Policy.MinimumExpanding)
        pol.setVerticalPolicy(pol.Policy.MinimumExpanding)
        self.setSizePolicy(pol)

    def sizeHint(self): return self.min_size

    def resizeEvent(self, event: QResizeEvent = None):
        if self.hover_changed:
            self.svg.recolor(getattr(self.palette(), 'light' if self.hover else 'window')().color())
            self.hover_changed = False
        self.setPixmap(self.svg.render(self.size()))

    def enterEvent(self, event):
        self.hover = True
        self.hover_changed = True
        self.resizeEvent()

    def leaveEvent(self, a0):
        self.hover = False
        self.hover_changed = True
        self.resizeEvent()

    def replace_svg(self, data: str):
        self.svg.svg = data
        self.hover_changed = True
        self.resizeEvent()


class SvgButton(QtWidgets.QPushButton):
    def __init__(self, parent: QWidget, data: str, min_size=(16, 16), maintain_aspect=True):
        super().__init__(parent)
        self.svg = ColorSvg(data, maintain_aspect)
        self.setFlat(True)
        self.min_size = QSize(*min_size)
        self.setContentsMargins(0, 0, 0, 0)
        self.hover = False
        self.hover_changed = True
        pol = self.sizePolicy()
        pol.setHorizontalPolicy(pol.Policy.MinimumExpanding)
        pol.setVerticalPolicy(pol.Policy.MinimumExpanding)
        self.setSizePolicy(pol)

    def sizeHint(self): return self.min_size

    def resizeEvent(self, event: QResizeEvent = None):
        if self.hover_changed:
            self.svg.recolor(getattr(self.palette(), 'light' if self.hover else 'window')().color())
            self.hover_changed = False
        icon = QIcon(self.svg.render(self.size()))
        self.setIcon(icon)
        self.setIconSize(self.size())

    def enterEvent(self, event):
        self.hover = True
        self.hover_changed = True
        self.resizeEvent()

    def leaveEvent(self, a0):
        self.hover = False
        self.hover_changed = True
        self.resizeEvent()

    def replace_svg(self, data: str):
        self.svg.svg = data
        self.hover_changed = True
        self.resizeEvent()


class _MediaListFramework(QWidget):
    def __init__(self, parent: QWidget, imgsize: int = None, update_interval: int | None = 250):
        """
        A skeleton of a MediaListWidget for platform-specific subclasses to inherit from. Does nothing on its own.
        :param parent: the parent widget of this widget, usually the main window.
        :param imgsize: the size of the album art image in pixels.
        :param update_interval: the time in ms between updates for progress bars. Set to None to disable updates.
        """
        super().__init__(parent)
        self.imgsize = imgsize
        self.update_interval = update_interval
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.mediawidgets: dict[str, _MediaFramework] = {}

        if update_interval is not None:
            self.timer = QTimer()
            self.timer.setInterval(update_interval)
            self.timer.timeout.connect(self.update_timelines)
            self.timer.start()

    def remove_widget(self, name: str):
        """
        Removes and deletes the given media widget from this list widget.
        :param name: the name of the child widget to be removed. Should be the same as what was given to add_widget.
        """
        widget = self.mediawidgets.pop(name)
        print(' remove widget from layout:')
        self.layout.removeWidget(widget)
        print(' done')
        widget.handle_removed()
        print(' post-removal update')
        #self.update()
        print(' done')

    def add_widget(self, widget, name: str):
        """
        Adds a media widget to this list widget.
        :param widget: the widget to add.
        :param name: the name to store the widget under.
        """
        self.mediawidgets[name] = widget
        self.layout.addWidget(widget)
        #self.update()
        print(' done adding widget')

    def update_timelines(self):
        for widget in self.mediawidgets.values():
            if widget.playing and widget.has_progress: widget.update_timeline()


class _MediaFramework(QWidget):
    media_icons = {
        'play': '<svg width="24" height="19" xmlns="http://www.w3.org/2000/svg" fill="currentColor"><path d="m7.50632,0.64931c-1.33102,-0.85565 -3.08152,0.10003 -3.08152,1.68236l0,14.33666c0,1.5823 1.7505,2.538 3.08152,1.6824l11.15078,-7.1684c1.2246,-0.7872 1.2246,-2.5774 0,-3.3647l-11.15078,-7.16832z"/></svg>',
        'pause': '<svg width="24" height="19" xmlns="http://www.w3.org/2000/svg" fill="currentColor"><path d="m6,0.5c-1.10457,0 -2,0.89543 -2,2l0,14c0,1.1046 0.89543,2 2,2l3,0c1.1046,0 2,-0.8954 2,-2l0,-14c0,-1.10457 -0.8954,-2 -2,-2l-3,0z"/><path d="m15,0.5c-1.1046,0 -2,0.89543 -2,2l0,14c0,1.1046 0.8954,2 2,2l3,0c1.1046,0 2,-0.8954 2,-2l0,-14c0,-1.10457 -0.8954,-2 -2,-2l-3,0z"/></svg>',
        'forward': '<svg width="24" height="19" xmlns="http://www.w3.org/2000/svg" fill="currentColor"><path d="m3.42091,2.3383c-0.98529,-0.76634 -2.42091,-0.06419 -2.42091,1.18403l0,11.95539c0,1.2482 1.43562,1.9503 2.42091,1.184l8.19299,-6.3724c0.2436,-0.1894 0.3861,-0.4807 0.3861,-0.7893l0,5.9777c0,1.2482 1.4356,1.9503 2.4209,1.184l8.193,-6.3724c0.2436,-0.1894 0.3861,-0.4807 0.3861,-0.7893c0,-0.3086 -0.1425,-0.5999 -0.3861,-0.7894l-8.193,-6.37232c-0.9853,-0.76634 -2.4209,-0.06419 -2.4209,1.18403l0,5.97769c0,-0.3086 -0.1425,-0.5999 -0.3861,-0.7894l-8.19299,-6.37232z"/></svg>',
        'backward': '<svg width="24" height="19" xmlns="http://www.w3.org/2000/svg" fill="currentColor"><path d="m9.57909,2.3383c0.98531,-0.76634 2.42091,-0.06419 2.42091,1.18403l0,5.97769l0,5.9777c0,1.2482 -1.4356,1.9503 -2.42091,1.184l-8.19303,-6.3724c-0.24359,-0.1894 -0.38606,-0.4807 -0.38606,-0.7893c0,-0.3086 0.14247,-0.5999 0.38606,-0.7894l8.19303,-6.37232z"/><path d="m12,9.50002c0,0.3086 0.1425,0.5999 0.3861,0.7893l8.193,6.3724c0.9853,0.7663 2.4209,0.0642 2.4209,-1.184l0,-11.95539c0,-1.24822 -1.4356,-1.95037 -2.4209,-1.18403l-8.193,6.37232c-0.2436,0.1895 -0.3861,0.4808 -0.3861,0.7894z"/></svg>'
    }

    def __init__(self, parent: QWidget, playername: str = None, imgsize: int = None):
        """
        A skeleton of a MediaWidget for platform-specific subclasses to inherit from. Does nothing on its own.
        :param parent: the parent widget of this widget, usually the MediaListWidget controlling it.
        :param playername: the name of the media player this widget handles.
        :param imgsize: the size of the album art in pixels.
        """
        super().__init__(parent)
        if imgsize is None: imgsize = round(parent.screen().geometry().height()/10)
        self.imgsize = imgsize
        max_button_height = round(imgsize/4)
        self.playername = playername
        self.displaytext = ""
        self.playing = False
        self.has_progress = True
        self.can_raise = False

        self.infolabel = TextWidget(self, alignment="Left")
        self.infolabel.setScaledContents(True)
        pol = self.infolabel.sizePolicy().Policy
        self.infolabel.setSizePolicy(pol.Expanding, pol.Preferred)
        self.playernamelabel = TextWidget(self, alignment="Left")
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

        self.buttons = []
        for state, action in zip(('backward', 'play', 'forward'), (self.do_prev, self.do_playpause, self.do_next)):
            but = SvgButton(self, self.media_icons[state])
            but.setMaximumHeight(max_button_height)
            but.clicked.connect(action)
            self.buttons.append(but)
            self.ctrllayout.addWidget(but)


        self.pbar = ProgressBarWidget(self, max_height=int(self.height() // 2.5))
        pol = self.pbar.sizePolicy()
        pol.setRetainSizeWhenHidden(True)
        self.pbar.setSizePolicy(pol)

        self.info_layout.addLayout(self.ctrllayout)
        self.info_layout.addWidget(self.pbar)
        self.layout.addLayout(self.info_layout)
        self.info_layout.setStretchFactor(self.ctrllayout, 5)
        self.info_layout.setStretchFactor(self.pbar, 1)

        placeholder = QWidget()  # to make the spacing equal - otherwise have to set spacing to 0 and adjust content margins
        placeholder.setMaximumSize(0, 0)
        self.layout.addWidget(placeholder)

        self.setFixedHeight(imgsize)
        self.playernamelabel.setText(f"<b>{self.playername}</b>")
        self.update()

    def _redraw_playpause_button(self):
        """
        Sets the icon on the play/pause button depending on the value of self.playing
        """
        self.buttons[1].replace_svg(self.media_icons['pause' if self.playing else 'play'])
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

    def mousePressEvent(self, a0):
        if self.can_raise and a0.button() == Qt.MouseButton.LeftButton: self.raise_player()
        super().mousePressEvent(a0)

    def raise_player(self):
        """
        Request to raise the player to the foreground.
        """
        raise NotImplementedError

    def update_timeline(self):
        """
        Called by the parent MediaListWidget's timer every [update_interval] ms (default 250) and should call self.progressupdate
        with a new percentage completion.
        """
        raise NotImplementedError

    def handle_removed(self):
        """
        Called when this widget has been removed from its parent MediaListWidget. Should handle any cleanup
        this widget requires before deletion.
        """
        raise NotImplementedError

    def update_info(self, title: str, artist: str):
        """
        Displays the title/artist info. Should be called whenever any of this info changes.
        """
        self.infolabel.setText(f"{title}<br>{artist}")

    def update_player(self, playername: str):
        """
        Call when you want the player name updated for whatever reason.
        :param playername: the new playername to set.
        """
        self.playername = playername
        self.playernamelabel.setText(f"<b>{self.playername}</b>")

    def progressupdate(self, perc: float):
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


class NotificationWidgetFramework(QWidget):
    def __init__(self, parent):
        super().__init__(parent)


class HrWidget(QtWidgets.QFrame):
    def __init__(self, parent: QWidget, height: int = 3, color: str = None):
        """
        A horizontal rule across the window.
        :param parent: the parent widget containing this one.
        :param height: the height in pixels of the line.
        :param color: the color of the line, as a css string.
        """
        super().__init__(parent)
        self.setMinimumWidth(1)
        self.setFixedHeight(height)
        self.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Minimum)
        if color is not None: self.setStyleSheet(f"background-color: {color};")


class TextWidget(QtWidgets.QLabel):
    def __init__(self, parent: QWidget, text: JITstring | str = None, alignment: str = "Center",
                 wordwrap: bool = True, update_interval: int = None):
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
        self.setAlignment(getattr(Qt.AlignmentFlag, "Align" + alignment))
        self.get_text = text
        if update_interval is not None:
            self.timer = QTimer()
            self.timer.timeout.connect(self.do_cmds)
            self.timer.start(update_interval)
        self.do_cmds()

    def do_cmds(self):
        self.setText(str(self.get_text))


def html_table(array: Sequence[Sequence], title='', style: str = "border-collapse: collapse;",
               right_td_style: str = "text-align: right;", tstyle: str = "text-align: center;") -> str:
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


def start() -> None:
    global _app
    if _app is None:
        raise AssertionError("QApplication not found, have you created a Window yet?")
    if _app.platformName() == 'wayland':  # remove when Qt updates with proper support
        if os.environ['XDG_SESSION_DESKTOP'] == 'KDE':
            print("Plasma on wayland detected, running Kwin script to handle flags wayland ignores")
            from PyQt6.QtDBus import QDBusInterface
            script = QDBusInterface('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting')
            loaded = script.call('isScriptLoaded', 'pywidgets-fix').arguments()[0]
            if not loaded:
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fix_wayland_window.js')
                script.call('loadScript', path, 'pywidgets-fix')
                script.call('start')
        else:
            print('running on wayland - unable to position window or set flags (stay on top/bottom, no alt-tab display, etc)')
    if not _use_async:
        _app.exec()
    else:
        with qtinter.using_asyncio_from_qt():
            _app.exec()


def schedule(coro, callback=None):
    try:
        task = loop.create_task(coro)
    except AttributeError:  # if loop is None, but this way is hopefully faster than checking (only first call can fail)
        raise AssertionError("One of your widgets is trying to use async functionality, which is disabled. " +
                             "Make sure qtinter is installed and that use_async is True in your Window initialization.")
    if callback is None:
        def callback(task): task.cancel()
    task.add_done_callback(callback)
    return task


def call_threadsafe(fn: callable, *args, context=None) -> None:
    loop.call_soon_threadsafe(fn, *args, context=context)


def run_on_app_start(f: Callable, *args, **kwargs) -> None:
    """Takes the given function/method/PyCmd and runs it immediately once the QApplication starts.
    Just a wrapper for a single-shot QTimer to make code more readable."""
    QTimer.singleShot(0, PyCmd(f, *args, **kwargs))