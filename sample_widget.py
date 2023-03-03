#!/usr/bin/python3.8
from pywidgets.JITstrings import JITstring, PyCmd, BashCmd
from pywidgets.sample_data import system_strings, cpu_cmds, mem_cmds, nvidia_cmds, cur_OS, numbers_only_fn, \
    bytes2human, disk_cmds, net_cmds
import pywidgets

app = pywidgets.get_application()
window = pywidgets.get_window(app)

window.add_widget(pywidgets.HrWidget())
window.add_widget(pywidgets.TextWidget(window, f"{system_strings['system name']} - {system_strings['distro']}<br/>" +
                                       f"Running {cur_OS} {system_strings['release']}<br/>" + system_strings['CPU name']))
window.add_widget(pywidgets.HrWidget())

if cur_OS in ['Windows', 'Linux']:  # no media pywidgets for mac yet
    window.add_widgets([pywidgets.MediaListWidget(window), pywidgets.HrWidget()])

blkstr = JITstring(pywidgets.html_table([[p, '{} / {}'] for p in disk_cmds['disks mountpoint']]),
                   [i for l in zip(disk_cmds['disks used'], disk_cmds['disks total']) for i in l])

window.add_widgets(
    [pywidgets.ProgressArcsWidget(window, blkstr, disk_cmds['disks percent'][::-1], "<b>Disk Usage</b>",
                                  update_interval=2000),
     pywidgets.HrWidget()])

window.add_widgets(
    [pywidgets.GraphWidget(window, "<b>CPU Usage</b>", cpu_cmds['overall usage']),
     pywidgets.GraphWidget(window, "<b>RAM Usage</b>", mem_cmds['used bytes'],
                           yrange=(0, mem_cmds['total bytes'].run()), ylabel_str_fn=bytes2human),
     pywidgets.GraphWidget(window, "<b>Network Download</b>", net_cmds['current down (bytes)'],
                           yrange=(0, int(net_cmds['total net max speed'])), ylabel_str_fn=bytes2human)])

if 'GPU 0:' in BashCmd("nvidia-smi -L"):  # if the list of nvidia gpus returns at least one
    text = [['Temp: {}C', 'Throttled: {}'], ['Clock Speed:', '{} / {}'], ['Power:', '{} / {}']]
    vals = [nvidia_cmds['GPU']['temp'],
            PyCmd(lambda x: ["no", "yes"][str(x) != "Not Active"], nvidia_cmds['GPU']['throttling']),
            nvidia_cmds['clocks']['graphics clock freq'], nvidia_cmds['clocks']['graphics clock freq max'],
            nvidia_cmds['power']['draw'], nvidia_cmds['power']['limit']]

    gpustr = JITstring(pywidgets.html_table(text, title='<b>' + nvidia_cmds['GPU']['name'].run() + '</b>'), vals)
    percs = [numbers_only_fn(nvidia_cmds['GPU']['usage'])]
    window.add_widget(pywidgets.ProgressArcsWidget(window, gpustr, percs, "<b>GPU Usage</b>", update_interval=500))

if cur_OS == 'Linux':
    from pywidgets.sample_data import temp_cmds

    try:  # in case the system this is running on has exactly the same device names and labels as mine
        tempstr = JITstring(pywidgets.html_table(
            [["CPU temp:", "{}C"], ["NVME temp:", "{}C"], ["Wifi temp:", "{}C"]], "<b>Temperatures</b>"),
            [temp_cmds["k10temp Tctl current"], temp_cmds["nvme Composite current"], temp_cmds["iwlwifi_1  current"]]
        )

        window.add_widgets([pywidgets.HrWidget(), pywidgets.TextWidget(window, tempstr, update_interval=1000)])
    except IndexError:
        pass  # if any of the devices or labels are wrong, just move on

window.finish_init()
exit(app.exec())
