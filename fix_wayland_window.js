// this is a KWin script that's only used in the specific case you're running KDE's Plasma desktop on Wayland.
// if you are, it's loaded via dbus in widgets.py's start() function with the name 'pywidgets-fix'.
// if a script with that name is already running, nothing else is done
function setState(window) {
    if (window.caption == 'PyWidgets') {
        window.skipTaskbar = true;
        window.skipSwitcher = true;
        window.skipPager = true;
        window.keepBelow = true;
        window.frameGeometry.x = workspace.workspaceWidth - window.width;
        window.frameGeometry.y = 0;
        window.onAllDesktops = true;
    }
}
workspace.windowAdded.connect(setState);
for (cl of workspace.stackingOrder) {
    setState(cl);
}
