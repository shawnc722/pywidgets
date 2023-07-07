#!/usr/bin/python3.11
import subprocess

from pywidgets.JITstrings import JITstring, PyCmd, BashCmd
from pywidgets.sample_data import system_strings, cpu_cmds, mem_cmds, nvidia_cmds, cur_OS, numbers_only_fn, \
    bytes2human, disk_cmds, net_cmds
import pywidgets

app = pywidgets.get_application()
window = pywidgets.Window()#background_color=(0,0,0,128))

window.add_widget(pywidgets.HrWidget(window))
window.add_widget(pywidgets.TextWidget(window, f"{system_strings['system name']} - {system_strings['distro']}<br/>" +
                                       f"Running {cur_OS} {system_strings['release']}<br/>" + system_strings['CPU name']))
window.add_widget(pywidgets.HrWidget(window))

if hasattr(pywidgets, "MediaListWidget"):  # currently only Linux and Windows versions written
    window.add_widgets([pywidgets.MediaListWidget(window), pywidgets.HrWidget(window)])

blkstr = JITstring(pywidgets.html_table([[p, '{} / {}'] for p in disk_cmds['disks mountpoint']]),
                   [i for l in zip(disk_cmds['disks used'], disk_cmds['disks total']) for i in l])

window.add_widgets(
    [pywidgets.ProgressArcsWidget(window, blkstr, disk_cmds['disks percent'][::-1], True, "<b>Disk Usage</b>",
                                  update_interval=2000),
     pywidgets.HrWidget(window)])

add_cores_avg = True
per_core = cpu_cmds['per core usage']
num_cores = int(cpu_cmds['cpu thread count'])
title = "<b>CPU Usage</b>"
# this linecolor just uses your default color at half opacity for the cpu graph to tone down the mess of lines
linecolor = tuple(val if i < 3 else val//2 for i, val in enumerate(window.default_color.getRgb()))
if add_cores_avg:
    def fn():
        l = per_core()
        l += [sum(l)/num_cores]
        return l
    per_core_w_avg = PyCmd(fn)
    lcs = [linecolor] * num_cores + [(255, 255, 255, 255)]  # add a white line for the average
    window.add_widget(pywidgets.GraphWidget(window, title, per_core_w_avg, lines=num_cores+1, linecolors=lcs))
else:
    pywidgets.GraphWidget(window, title, per_core, lines=num_cores, linecolor=linecolor)

yrange = int(net_cmds['total net max speed'])  # for the network download GraphWidget
yrange = (0, 100_000_000) if yrange == 0 else (0, yrange)  # if the max speed is unknown (0), set to ~100MBPS
window.add_widgets(
    [pywidgets.GraphWidget(window, "<b>RAM Usage</b>", mem_cmds['used bytes'],
                           yrange=(0, mem_cmds['total bytes'].run()), ylabel_str_fn=bytes2human),
     pywidgets.GraphWidget(window, "<b>Network Download</b>", net_cmds['current down (bytes)'],
                           yrange=yrange, ylabel_str_fn=bytes2human)])

try:
    BashCmd("nvidia-smi -L")  # test that a nvidia card is installed, but we don't care about the output
    text = [['Temp: {}C', 'Fan Speed: {}'], ['Clock speed:', '{} / {}'], ['Power:', '{} / {}']]
    vals = [nvidia_cmds['GPU']['temp'], nvidia_cmds['GPU']['fan speed'],
            nvidia_cmds['clocks']['graphics clock freq'], nvidia_cmds['clocks']['graphics clock freq max'],
            nvidia_cmds['power']['draw'], nvidia_cmds['power']['limit']]

    gpustr = JITstring(pywidgets.html_table(text, title='<b>' + str(nvidia_cmds['GPU']['name']) + '</b>'), vals)
    percs = [numbers_only_fn(nvidia_cmds['GPU']['usage'])]
    window.add_widget(pywidgets.ProgressArcsWidget(window, gpustr, percs, title="<b>GPU Usage</b>", update_interval=500))
except subprocess.CalledProcessError: pass  # if nvidia-smi fails, no nvidia gpu

if cur_OS == 'Linux':
    from pywidgets.sample_data import temp_cmds

    try:  # in case the system this is running on has exactly the same device names and labels as mine
        tempstr = JITstring(pywidgets.html_table(
            [["CPU temp:", "{}C"], ["NVME temp:", "{}C"], ["Wifi temp:", "{}C"]], "<b>Temperatures</b>"),
            [temp_cmds["k10temp Tctl current"], temp_cmds["nvme Composite current"], temp_cmds["iwlwifi_1  current"]])

        def f():
            return temp_cmds["k10temp Tctl current"], temp_cmds["nvme Composite current"], temp_cmds["iwlwifi_1  current"]

        window.add_widgets([pywidgets.HrWidget(window),
                            pywidgets.GraphWidget(window, "<b>Temperatures</b>", f, lines=3, yrange=(20, 100), update_interval=1000,
                                                  ylabel_str_fn=lambda s: str(round(s)) + u'\N{DEGREE SIGN}C')])

        window.add_widgets([pywidgets.HrWidget(window), pywidgets.TextWidget(window, tempstr, update_interval=1000)])
    except IndexError:
        pass  # if any of the devices or labels are wrong, just move on

window.finish_init()
pywidgets.run_application(app)
