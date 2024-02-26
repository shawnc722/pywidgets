from os import getcwd, listdir
stub = """#!/usr/bin/python3.11
import pywidgets
import pywidgets.sample_data as data

background_color = None  # use RGBA tuple to specify, eg (0,0,0,128) for half opacity black background. None for no bg
shadow_radius = 8        # adds a black shadow around everything to improve visibility on transparent bg. Unit: pixels

# create the window:
window = pywidgets.Window(background_color=background_color, shadow_radius=shadow_radius)

# define some text:
widget_text = f"PyWidgets v{pywidgets.VERSION} running on {data.system_strings['system name']}."

# add the text to a widget:
first_widget = pywidgets.TextWidget(parent=window, text=widget_text)

# add the widget to the window:
window.add_widget(first_widget)

# tell the window to handle widget layout (default arguments for simplicity):
window.finalize()

# start the application:
window.start()
"""


if __name__ == '__main__':
    cwd = getcwd()
    filename = 'pywidgets-page.py'
    destination = f'{cwd}/{filename}'
    if filename in listdir(cwd):
        print(filename, 'already exists in', cwd)
        print('exiting without modifying filesystem.')
        exit(1)
    else:
        with open(destination, 'w') as file: file.write(stub)
        print('created', destination)