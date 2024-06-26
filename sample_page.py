#!/usr/bin/env python
import pywidgets
from pywidgets.JITstrings import JITstring, PyCmd
from pywidgets.sample_data import system_strings, cpu_cmds, mem_cmds, nvidia_cmds, cur_OS, numbers_only_fn, \
    bytes2human, disk_cmds, temp_cmds, net_cmds
try:
    from pywidgets.sample_web_data import web_cmds
except ImportError:  # web commands are optional, if requests isn't installed this should fail
    web_cmds = None

background_color = None  # use RGBA tuple to specify, eg (0,0,0,128) for half opacity black background. None for no bg
use_async = cur_OS == 'Windows'
if use_async:
    import importlib.util
    use_async = importlib.util.find_spec("qtinter") is not None  # use async iff on windows and qtinter is installed

window = pywidgets.Window(background_color=background_color, use_async=use_async, shadow_radius=8)

window.add_widget(pywidgets.HrWidget(window))
window.add_widget(pywidgets.TextWidget(window, f"{system_strings['system name']} - {system_strings['distro']}<br/>" +
                                       f"Running {cur_OS} {system_strings['version']}<br/>" + system_strings['CPU name']))
window.add_widget(pywidgets.HrWidget(window))

if hasattr(pywidgets, "MediaListWidget"):  # currently only Linux and Windows versions written
    window.add_widgets([pywidgets.MediaListWidget(window), pywidgets.HrWidget(window)])

blkstr = PyCmd(lambda: pywidgets.html_table([[disk_cmds['shrink path'](p), '{} / {}'] for p in disk_cmds['disks mountpoint']]).format(
    *[i for l in zip(disk_cmds['disks used'], disk_cmds['disks total']) for i in l]))

window.add_widgets(
    [pywidgets.ProgressArcsWidget(window, blkstr, PyCmd(lambda: disk_cmds['disks percent'][::-1]),
                                  True, "<b>Disk Usage</b>", update_interval=2000),
     pywidgets.HrWidget(window)])

add_cores_avg = True
per_core = cpu_cmds['per core usage']
num_cores = int(cpu_cmds['cpu thread count'])
title = "<b>CPU Usage</b>"
# this linecolor just uses your default color at half opacity for the cpu graph to tone down the mess of lines for high core count cpus
linecolor = tuple(val if i < 3 else val//2 for i, val in enumerate(window.palette().window().color().getRgb()))
if add_cores_avg:
    def fn():
        l = per_core()
        l += [sum(l)/num_cores]
        return l
    per_core_w_avg = PyCmd(fn)
    lcs = [linecolor] * num_cores + [window.palette().light().color().getRgb()]  # add a lighter color line for the avg
    window.add_widget(pywidgets.GraphWidget(window, title, per_core_w_avg, lines=num_cores+1, linecolors=lcs))
else:
    pywidgets.GraphWidget(window, title, per_core, lines=num_cores, linecolor=linecolor)

yrange = int(net_cmds['total net max speed'])  # for the network download GraphWidget
yrange = (0, 100_000_000) if yrange == 0 else (0, yrange)  # if the max speed is unknown (0), set to ~100MBPS
update_interval = 0.5  # s
window.add_widgets(
    [pywidgets.GraphWidget(window, "<b>RAM Usage</b>", mem_cmds['used bytes'],
                           yrange=(0, mem_cmds['total bytes'].run()), ylabel_str_fn=bytes2human),
     pywidgets.GraphWidget(window, "<b>Network Download</b>",
                           PyCmd(net_cmds['current down (bytes)'], postformat_fn=lambda x: x / update_interval),
                           yrange=yrange, ylabel_str_fn=bytes2human, update_interval=round(update_interval*1000))])


if nvidia_cmds['usable?']():  # if a nvidia gpu and nvidia-smi are installed - for amd/intel/integrated gpus, skips this widget
    text = [['Temp: {}C', 'Fan Speed: {}'], ['Clock speed:', '{} / {}'], ['Power:', '{} / {}']]
    vals = PyCmd(nvidia_cmds['query'],
                 'temperature.gpu,fan.speed,clocks.gr,clocks.max.gr,power.draw,enforced.power.limit')  # using query rather than each key individually for performance

    gpustr = JITstring(pywidgets.html_table(text, title='<b>' + str(nvidia_cmds['GPU']['name']) + '</b>'), vals)
    percs = [numbers_only_fn(nvidia_cmds['GPU']['usage'])]
    window.add_widget(pywidgets.ProgressArcsWidget(window, gpustr, percs, title="<b>GPU Usage</b>", update_interval=500))

try:  # the keys of temp_cmds accessed here will usually need to be changed - if so, your system's options will be printed when the script is run
    tempstr = JITstring(pywidgets.html_table(
        [["CPU temp:", "{}C"], ["NVME temp:", "{}C"], ["Wifi temp:", "{}C"]], "<b>Temperatures</b>"),
        [temp_cmds["k10temp Tctl current"], temp_cmds["nvme Composite current"], temp_cmds["iwlwifi_1  current"]])
    window.add_widgets([pywidgets.HrWidget(window), pywidgets.TextWidget(window, tempstr, update_interval=1000)])
except KeyError:
    print("Invalid devices in temp_cmds - temperature widgets won't be added. Possible devices:", list(temp_cmds.keys()))


def fmt_weather():
    weather = web_cmds['weather cmds']['current weather']()
    if weather is None: return "", None
    desc, img = web_cmds['weather cmds']['get icon'](weather['weathercode'], weather['is_day'] == 1)
    text = f"<b>{desc}</b><br/>Currently in {web_cmds['ip cmds']['city']} it's " + \
           f"{weather['temperature']}\N{DEGREE SIGN}C with a wind speed of {weather['windspeed']} km/h.<br/>"
    return text, img


if web_cmds: window.add_widget(pywidgets.ImageWithTextWidget(window, text_and_img=fmt_weather, img_size=None,
                                                             update_interval=1000*60*10))  # update every 10min

window.finalize()
pywidgets.start()
