import pywidgets
from clock_widget import ClockWidget
from PyQt6 import QtGui

palette = pywidgets.Window.default_palette  # only required if you plan on changing the colors
# palette.setColor(palette.ColorRole.Window, QtGui.QColor("sky blue"))  # set colors like this
# palette.setColor(palette.ColorRole.WindowText, QtGui.QColor(0, 128, 0))  # and/or like this
window = pywidgets.Window(palette=palette)

window.add_widget(ClockWidget(window))

window.finalize()
pywidgets.start()
