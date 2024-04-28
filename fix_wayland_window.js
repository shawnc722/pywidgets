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
