#!/usr/bin/python3.8
import sys
from pywidgets.widgets import *
import pywidgets.external_sources

VERSION = "0.8.1"
if sys.platform == "linux":
    from pywidgets.linuxwidgets import MediaListWidget
elif sys.platform == "win32":
    from pywidgets.windowswidgets import MediaListWidget, NotificationWidget
elif sys.platform == "darwin":
    pass

