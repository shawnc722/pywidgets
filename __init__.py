#!/usr/bin/python3.8
import sys
import pywidgets
from pywidgets.widgets import *


if sys.platform == "linux":
    from pywidgets.linuxwidgets import MediaListWidget
elif sys.platform == "win32":
    from pywidgets.windowswidgets import MediaListWidget, NotificationWidget
elif sys.platform == "darwin":
    pass

