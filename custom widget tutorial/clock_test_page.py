import pywidgets
from clock_widget import ClockWidget

app = pywidgets.get_application()
window = pywidgets.get_window()
widget_list = [ClockWidget(window)]
window.finish_init(widget_list)
exit(app.exec())
