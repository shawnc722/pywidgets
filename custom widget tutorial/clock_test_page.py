import pywidgets
from clock_widget import ClockWidget

app = pywidgets.get_application()
default_color = "grey"  # this is already the default so there's no need to specify, but it's here in case you want to change it
window = pywidgets.get_window(app, default_color=default_color)
window.add_widget(ClockWidget(window))
window.finish_init()
exit(app.exec())
