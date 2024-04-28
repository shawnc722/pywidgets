from PyQt6 import QtGui, QtCore, QtWidgets
from pywidgets.JITstrings import JITstring, PyCmd
from pywidgets.widgets import TextWidget
from datetime import datetime
from math import sin, cos, pi


class AnalogClock(QtWidgets.QWidget):
    """A simple analog clock."""
    def __init__(self, parent):
        super().__init__(parent)
        policy = QtWidgets.QSizePolicy()
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def sizeHint(self) -> QtCore.QSize: return QtCore.QSize(self.width(), self.width())

    def heightForWidth(self, a0: int) -> int: return a0

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        thickness = round(self.fontMetrics().height() / 2)  # pixels, use a size relative to font height so it scales
        style = QtCore.Qt.PenStyle.SolidLine
        color = self.palette().window().color()
        pen = QtGui.QPen(color, thickness, style)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        clock_size = self.width() - thickness
        offset = round(thickness / 2)

        # drawArc() takes (x, y, width, height, start angle, span angle)
        # angle units are 16th of a degree, so 16 * 360deg gives a full circle while 16 * 180deg gives half of one, etc.
        painter.drawArc(offset, offset, clock_size, clock_size, 0, 360 * 16)

        time = datetime.now()
        # note that time.hour and time.minute start at 0, so we use 11 hours instead of 12 and 59 min instead of 60
        hour_angle = ((time.hour % 11) / 11) * 2 * pi  # percentage of rotation done * a full circle in radians
        minute_angle = (time.minute / 59) * 2 * pi  # percentage of a rotation done * a full circle in radians

        minute_hand_length = round(clock_size / 2 - thickness)  # inner radius of the circle minus the line thickness
        hour_hand_length = .75 * minute_hand_length

        center = round(self.width() / 2)  # center x and y coordinates are the same, so only using one

        hour_x = center + round(hour_hand_length * sin(hour_angle))
        hour_y = center - round(hour_hand_length * cos(hour_angle))

        minute_x = center + round(minute_hand_length * sin(minute_angle))
        minute_y = center - round(minute_hand_length * cos(minute_angle))

        painter.drawLine(center, center, minute_x, minute_y)
        painter.drawLine(center, center, hour_x, hour_y)

        painter.end()


class ClockWidget(QtWidgets.QWidget):
    """A widget displaying an analog clock."""

    def __init__(self, parent, update_interval=1000):
        super().__init__(parent)
        self.graphic = AnalogClock(self)
        self.label = TextWidget(self)  # a TextWidget is just a QLabel wrapper w/ formatting, perfect for text (if you hadn't guessed)
        layout = QtWidgets.QHBoxLayout()  # create the desired type of layout

        # add widgets in order:
        layout.addWidget(self.graphic, stretch=1)
        layout.addWidget(self.label, stretch=2)

        self.setLayout(layout)  # finally, add the layout to the main widget

        def get_time(fmt): return datetime.now().strftime(fmt)

        time = PyCmd(get_time, "%I:%M %p")
        date = PyCmd(get_time, "%A, %B %d")
        self.text = JITstring("The time is {} on {}.", [time, date])

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.do_cmds)

        self.timer.start(update_interval)
        self.do_cmds()

    def do_cmds(self):
        self.label.setText(str(self.text))  # sets the text to an up-to-date copy of the string produced by self.text
        self.update()  # tells Qt it's time to redraw this widget, forcing the graphics portion (our clock) to refresh
