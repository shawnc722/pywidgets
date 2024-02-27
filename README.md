# PyWidgets

PyWidgets is a desktop widget manager using Qt and Python, built to be cross-platform, modular, and fully customizable.
Widgets are a small window of their own which can display a certain type of information (text, times, numbers, etc.) in a given style.
A sample page of widgets is included to show the capabilities without any coding required, but the intent is for users to extend the project through adding new data sources (requiring minimal coding) or designing new widgets (requiring coding and/or Qt familiarity) or both.

![sample widget image](pictures/sample_widget_example_linux.jpg "An example of a widget setup")
## Features
* Cross-platform - the same widget setup can work between Linux/Windows dual boots, and/or can be used on a Mac.
* Customizable sources - any data you can access from python or from the terminal can be displayed.
* Customizable looks - widgets are created with Qt, so if you have a design in mind creating it is easy.
* Powerful - if you can think of an idea for a widget, you can probably make it.
* Modular - widgets and data are independent, so it's easy to use multiple looks for the same data source.
## Examples

**Combining pre-made data sources and widgets:**

```python3
import pywidgets
from pywidgets.sample_data import cpu_cmds

# first create the window itself:
window = pywidgets.Window()

# next, add widget(s)
# for each widget, decide what data it should display (a GraphWidget displays numerical data)
data = cpu_cmds["overall usage"]  # there's lots of choices in pywidgets.sample_data, but any function returning a number works too
title = "CPU usage"

# next, create the widget with the desired data:
widget = pywidgets.GraphWidget(window, title, data)

# the last step per widget is to add it to the window. By default, widgets appear the order they were added in.
window.add_widget(widget)

# finally, tell the window to finish setup and then start the program:
window.finalize()
pywidgets.start()
```
This code results in the following widget, which shows the percentage use of 
the CPU over the last one minute and updates every second:  
![Image of above widget](pictures/graph_widget_example.jpg "The widget created by the code above")

## Requirements
Python version 3.11 or higher is required, because this project makes heavy use of the new type hinting features. Additionally, the following python packages are required (requirements are automatically installed if you follow the install guide below):
* PyQt6
* psutil
* pyqtgraph  

The following packages aren't required for the base project but enable certain widgets (currently only required on Windows):
* asyncio (Windows only)
* qtinter (Windows only)
* winsdk (Windows only)
* requests

## Installation or Getting Started

This project can be installed as a package or run in place.  

First, ensure you have python 3.11 or higher and pip (the python install guide is [here](https://wiki.python.org/moin/BeginnersGuide/Download) if you need it).

To install as a package, download the latest wheel (.whl)
from the [releases](https://github.com/shawnc722/pywidgets/releases) section and install it, plus dependencies,
with `python -m pip install [filename]`. By default, it won't have async widgets on Windows (the media and notification widgets, 
currently) or any online capabilities (weather/location data from open source APIs). If you want either or both, add
`[async]`, `[web]`, or `[async,web]` immediately after the filename, for example:  
`python -m pip install pywidgets-0.8-py3-none-any.whl[async,web]` 

To run it in place, first install all the dependencies from the requirements 
section and then clone the project with `git clone https://github.com/shawnc722/pywidgets.git`.  

It isn't required, but the default font is [Inter](https://github.com/rsms/inter) and if it's not on your system already you may want to install it. If not, a different font will be automatically chosen - though you can also just specify one yourself.

To start up the sample page, just run the module from your command line: `python -m pywidgets` or `python3 -m pywidgets` (depending on your system).

## Usage

This project can be used as-is via `python -m pywidgets` or `python3 -m pywidgets`, customized using existing widgets and data sources, and/or extended with new widgets and data sources. The `pywidgets.sample_data` module provides some data sources to get you started - to see which ones and their current values, run it in your console with: `python -m pywidgets.sample_data`  
Once you've chosen a data source to use - for example let's go with `overall usage` from the `cpu cmds` section - 
we just need to use the titles and name to find it in `sample_data`'s `all_cmds` dict. For our 
example, that means we want `sample_data.all_cmds['cmd cmds']['overall usage']`, which returns a [PyCmd](https://github.com/shawnc722/pywidgets/wiki/Data-Formatting#pycmdsbashcmds) corresponding to the current total CPU usage of the system.  
If you have a data source that isn't in `sample_data`, all you need to do is make it into a callable. If it's coming from a python import it probably already is, ie the `datetime.now()` function from the datetime package, and if it's from your terminal you only need to make a [BashCmd](https://github.com/shawnc722/pywidgets/wiki/Data-Formatting#pycmdsbashcmds).  

With a data source chosen, the next step is to pick (or create) a widget to display it. Example images and further detail for each widget is available in the [widgets](https://github.com/shawnc722/pywidgets/wiki/Widgets) page.

A minimal `page.py` file can be generated from the command line in the current working directory using `python -m pywidgets.make_page_stub` to streamline custom page creation.

## Reference

* [widgets](https://github.com/shawnc722/pywidgets/wiki/Widgets) - Sample images and documentation for individual widgets  
* [data formatting](https://github.com/shawnc722/pywidgets/wiki/Data-Formatting) - info on PyCmds, JITstrings, and BashCmds  
* [tutorial](https://github.com/shawnc722/pywidgets/blob/main/custom%20widget%20tutorial/tutorial.md) - a walkthrough for creating a custom analogue clock widget

## Motivation

I created this because I tried and enjoyed [conky](https://wiki.archlinux.org/title/Conky), but regretted not having 
the same thing on my Windows dual-boot.
Lots of widget solutions exist purely for Windows, but overall they lacked the customization I wanted and trying to 
create the same thing with two widget platforms on two different operating systems just felt like a waste of effort. 
I started building this to resolve that issue, but also mostly for fun. 

## Contributing
Any contributions to this project are more than welcome, whether that's refining the existing project, adding new widgets/sources/features, sharing ideas, reporting bugs, etc.
Pull requests are great if you have code to add/edit, and otherwise creating an issue here on GitHub is best.

## License

This project uses Qt, so [their license](https://www.qt.io/licensing/) affects it.
Otherwise, you can do whatever you want with this project as far as I'm concerned. The only thing I'd ask is if you make 
something cool, please consider sharing it so others can use it too.
