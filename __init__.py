#!/usr/bin/python3.8
import sys
import pywidgets
from pywidgets.widgets import *


if sys.platform == "linux":
    from pywidgets.linuxmediawidget import MediaListWidget
elif sys.platform == "win32":
    from pywidgets.windowsmediawidget import MediaListWidget
elif sys.platform == "darwin":
    pass

