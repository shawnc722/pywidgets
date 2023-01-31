from PyQt5.QtWidgets import QWidget
from PyQt5 import QtGui, QtCore
from pywidgets.JITstrings import JITstring, PyCmd
from pywidgets.widgets import TextWidget
from datetime import datetime
from math import sin, cos, pi


class ClockWidget(QWidget):
    """A widget displaying an analog clock."""

    def __init__(self, parent, height=None):
        super().__init__(parent)
        height = height if height is not None else round(parent.height() / 10)
        self.setFixedSize(parent.width(), height)

        self.clock_size = height
        self.label = TextWidget(self)   # a TextWidget is just a QLabel wrapper w/ formatting
        # set position and size: setGeometry(x, y, w, h) relative to this widget's top left
        self.label.setGeometry(self.clock_size, 0, self.width() - self.clock_size, height)

        def get_time(fmt): return datetime.now().strftime(fmt)

        time = PyCmd(get_time, "%I:%M %p")
        date = PyCmd(get_time, "%A, %B %d")
        self.text = JITstring("The time is {} on {}.", [time, date])

        update_interval = 1000  # 1 second in ms
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.do_cmds)
        self.timer.start(update_interval)
        self.do_cmds()

    def do_cmds(self):
        self.label.setText(str(self.text))
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        color = QtCore.Qt.gray
        thickness = round(self.height() / 18)  # pixels, use 1/18th of height so that it scales
        style = QtCore.Qt.SolidLine
        pen = QtGui.QPen(color, thickness, style)
        painter.setPen(pen)

        newsize = self.clock_size - thickness
        offset = round(thickness / 2)
        # drawArc() takes (x, y, width, height, start angle, span angle)
        # angle units are 16th of a degree, so 16 * 360deg gives a full circle while 16 * 180deg gives half of one, etc.
        painter.drawArc(offset, offset, newsize, newsize, 0, 360 * 16)

        time = datetime.now()
        hour_angle = ((time.hour % 12) / 12) * 2 * pi  # percentage of rotation done * a full circle in radians
        minute_angle = (time.minute / 60) * 2 * pi  # percentage of a rotation done * a full circle in radians

        minute_hand_length = round(newsize / 2 - thickness)  # inner radius of the circle minus the line thickness
        hour_hand_length = .75 * minute_hand_length

        center = round(self.clock_size / 2)  # center x and y coordinates are the same, so only using one

        hour_x = center + round(hour_hand_length * sin(hour_angle))
        hour_y = center - round(hour_hand_length * cos(hour_angle))

        minute_x = center + round(minute_hand_length * sin(minute_angle))
        minute_y = center - round(minute_hand_length * cos(minute_angle))

        painter.drawLine(center, center, hour_x, hour_y)
        painter.drawLine(center, center, minute_x, minute_y)

        painter.end()

