# PyWidgets

PyWidgets is a desktop widget manager using Qt and Python, built to be cross-platform and fully customizable.
Widgets are a small window of their own which can display a certain type of information (text, times, numbers, etc.) in a given style.
A sample widget is included to show the capabilities without any coding required, but the intent is for users to extend the project through adding new data sources (requiring minimal coding) or designing new widgets (requiring coding and/or Qt familiarity) or both.

![sample widget image](somefile.jpg "An example of a widget setup")
## Examples

**Combining pre-made data sources and widgets:**  
```python3
import pywidgets
from pywidgets.sample_data import cpu_cmds

app = pywidgets.get_application()
window = pywidgets.get_window()

data = cpu_cmds["overall usage"]
display_string = "CPU usage"
widget = pywidgets.GraphWidget(window, display_string, data)
widget_list = [widget]  # normally you'd have more than one

window.finish_init(widget_list)
exit(app.exec())
```
[picture of resulting GraphWidget]
## Features
* Cross-platform - the same widget setup can work between Linux/Windows dual boots, and/or can be used on a Mac.
* Customizable sources - any data you can access from python or from the terminal can be displayed.
* Customizable looks - widgets are created with Qt, so if you have a design in mind creating it is easy.
* Powerful - if you can think of an idea for a widget, you can probably make it.
## Motivation

I created this because I tried and enjoyed [conky](https://wiki.archlinux.org/title/Conky), but regretted not having the same thing on my Windows dual-boot.
Lots of widget solutions exist purely for Windows, but overall they lacked the customization I wanted and trying to create the same thing with two widget platforms on two different operating systems just felt like a waste of effort. I started building this to resolve that issue, but also mostly for fun. 
## Requirements
* Python 3.8+
* various python libraries (TODO)

## Installation or Getting Started

Provide code examples and explanations of how to get the project, e.g.,

	git clone https://github.com/Jasonnor/README.md.git
    cd README.md
    npm install README.md
    npm start

## Usage

Show how to use the project or library.
    
## Reference

+ [jxson](https://gist.github.com/jxson) - [README.md](https://gist.github.com/jxson/1784669)
+ [gistfrojd](https://gist.github.com/gistfrojd) - [README.md](https://gist.github.com/gistfrojd/5fcd3b70949ac6376f66)

Depending on the size of the project, if it is small and simple enough the reference docs can be added to the README. For medium size to larger projects it is important to at least provide a link to where the API reference docs live.

## Contributing
Any contributions to this project are more than welcome, whether that's refining the existing project, adding new widgets/sources/features, giving ideas, reporting bugs, etc.
Pull requests are great if you have code to add/edit, and otherwise creating an issue here on GitHub is probably best.

## License

This project uses Qt, so [their license](https://www.qt.io/licensing/) affects it.
Otherwise, you can do whatever you want with this project as far as I'm concerned. The only thing I'd ask is if you make something cool, please share it so others can use it too.