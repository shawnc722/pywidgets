import pywidgets
from clock_widget import ClockWidget

app = pywidgets.get_application()
window = pywidgets.get_window(app)
window.add_widget(ClockWidget(window))
window.finish_init()
exit(app.exec())
