#!/usr/bin/python3.11
from psutil import cpu_percent, virtual_memory, cpu_freq, disk_partitions, \
    disk_usage, net_io_counters, net_if_stats, cpu_count
from psutil._common import bytes2human
from platform import uname, system, version
from pywidgets.JITstrings import PyCmd, BashCmd, PyCmdWithMem
import pywidgets


cur_OS = system()
BYTES_PER_MEGABIT = 131072


def _test_cmds(cmds, title=None, layer=0):
    """Prints output of given commands to test compatibility."""
    if title is not None: print(layer * '  ' + title)
    for k, v in cmds.items():
        if type(v) == dict:
            _test_cmds(v, k, layer + 1)
            continue
        print((layer + 1) * "  " + f"{k}:  {v}")


def _nvidiainfo(query):
    return BashCmd(f'nvidia-smi --query-gpu={query} --format=csv,noheader')


def numbers_only(string: str) -> float:
    """
    A helper function to get only the numbers from a string, for example 'a1b2c3' --> '123'
    :param string: the string to get numbers out of.
    :return: the given string, minus any characters that aren't numeric.
    """
    return float(''.join(i for i in string if i.isnumeric()))


def numbers_only_fn(cmd: PyCmd) -> PyCmd:
    """
    A helper function to get only the numbers from a string, for example '10:00PM' --> '1000'. This version takes a
    command and returns that command wrapped in the numbers_only function.
    :param cmd: the command whose output should be turned into numbers only.
    :return: the given command, outputting only the numeric characters.
    """
    return PyCmd(numbers_only, cmd)


def populate_runtime_strs(cmds):
    return {k: (_os_strs[cur_OS][k]() if v == 'populated at runtime' else v) for k, v in cmds.items()}


def wrap_for_exceptions(cmd: callable, exceptions: list, handler: callable) -> callable:
    """Returns the given command wrapped in a try/catch block that handles exceptions by calling the handler command."""
    def wrapped():
        try: cmd()
        except BaseException as e:
            if type(e) not in exceptions: raise e
            handler()
    return wrapped


system_strings = {
    "system name": uname().node,
    "CPU name": 'populated at runtime',
    "distro": 'populated at runtime',
    "version": version(),
    "release": uname().release
}
_linux_strs = {
    "CPU name": BashCmd("lscpu | grep 'Model name'", postformat_fn=lambda x: x.split(':', 1)[1].lstrip()),
    "distro": BashCmd('lsb_release -ds')
}
_windows_strs = {
    "CPU name": BashCmd("wmic cpu get name", postformat_fn=lambda x: x.split('\r\n')[1]),
    "distro": BashCmd("wmic os get caption", postformat_fn=lambda x: x.split('\r\n')[1])
}
_darwin_strs = {
    "CPU name": BashCmd("sysctl -n machdep.cpu.brand_string"),
    "distro": PyCmd(lambda: "Not available")
}
_os_strs = {'Linux': _linux_strs, '': _linux_strs, 'Windows': _windows_strs,
            'Darwin': _darwin_strs}
cpu_cmds = {
    "cpu thread count": PyCmd(cpu_count),
    "cpu core count": PyCmd(cpu_count, logical=False),
    "overall usage": PyCmd(cpu_percent),
    "per core usage": PyCmd(cpu_percent, percpu=True),
    "overall freq": PyCmd(lambda: round(cpu_freq().current, 1)),
    "per core freq": PyCmd(
        lambda: [round(i.current, 1) for i in cpu_freq(percpu=True)]),
    "overall max freq": PyCmd(lambda: cpu_freq().max),
    "per core max freq": PyCmd(
        lambda: [i.max for i in cpu_freq(percpu=True)])
}

mem_cmds = {
    "usage": PyCmd(virtual_memory, get_attr="percent"),
    "used": PyCmd(virtual_memory, get_attr="used", postformat_fn=bytes2human),
    "total": PyCmd(virtual_memory, get_attr="total", postformat_fn=bytes2human),
    "free": PyCmd(virtual_memory, get_attr="free", postformat_fn=bytes2human),
    "used bytes": PyCmd(virtual_memory, get_attr="used"),
    "total bytes": PyCmd(virtual_memory, get_attr="total"),
    "free bytes": PyCmd(virtual_memory, get_attr="free")
}

net_cmds = {
    "current up": PyCmdWithMem(net_io_counters, lambda x, y: x - y, get_attr="bytes_sent", postformat_fn=bytes2human),
    "current up (bytes)": PyCmdWithMem(net_io_counters, lambda x, y: x - y, get_attr="bytes_sent"),
    "total up": PyCmd(net_io_counters, get_attr="bytes_sent", postformat_fn=bytes2human),
    "total up (bytes)": PyCmd(net_io_counters, get_attr="bytes_sent"),
    "current down": PyCmdWithMem(net_io_counters, lambda x, y: x - y, get_attr="bytes_recv", postformat_fn=bytes2human),  # must be divided by time since last call to give speed rather than count
    "current down (bytes)": PyCmdWithMem(net_io_counters, lambda x, y: x - y, get_attr="bytes_recv"),
    "total down": PyCmd(net_io_counters, get_attr="bytes_recv", postformat_fn=bytes2human),
    "total down (bytes)": PyCmd(net_io_counters, get_attr="bytes_recv"),
    "total net max speed": PyCmd(net_if_stats, postformat_fn=lambda x: sum(v.speed * BYTES_PER_MEGABIT
                                                                           for k, v in x.items()))
}

nvidia_cmds = {
    "clocks": {
        "SM clock freq": _nvidiainfo('clocks.sm'),
        "SM clock freq max": _nvidiainfo('clocks.max.sm'),
        "graphics clock freq": _nvidiainfo('clocks.gr'),
        "graphics clock freq max": _nvidiainfo('clocks.max.gr'),
        "memory clock freq": _nvidiainfo('clocks.mem'),
        "memory clock freq max": _nvidiainfo('clocks.max.mem'),
        "video clock freq": _nvidiainfo('clocks.video')
    },

    "power": {
        "draw": _nvidiainfo('power.draw'),
        "limit": _nvidiainfo('enforced.power.limit'),
        "max limit": _nvidiainfo('power.max_limit')
    },

    "memory": {
        "usage": _nvidiainfo('utilization.memory'),
        "total": _nvidiainfo('memory.total'),
        "used": _nvidiainfo('memory.used'),
        "free": _nvidiainfo('memory.free'),
        "temp": _nvidiainfo('temperature.memory')
    },

    "GPU": {
        "name": _nvidiainfo('name'),
        "usage": _nvidiainfo('utilization.gpu'),
        "temp": _nvidiainfo('temperature.gpu'),
        "fan speed": _nvidiainfo('fan.speed'),
        "throttling": _nvidiainfo('clocks_throttle_reasons.hw_slowdown'),
        "thermal throttling": _nvidiainfo('clocks_throttle_reasons.hw_thermal_slowdown'),
        "power throttling": _nvidiainfo('clocks_throttle_reasons.hw_power_brake_slowdown'),
        "performance state": _nvidiainfo('pstate')
    }
}

_partitions = PyCmd(disk_partitions, postformat_fn=lambda x: [p.mountpoint for p in x])
disk_cmds = {
    "disks mountpoint": _partitions,
    "disks used":
        PyCmd(lambda: [bytes2human(disk_usage(p).used) for p in _partitions]),
    "disks used (bytes)":
        PyCmd(lambda: [disk_usage(p).used for p in _partitions]),
    "disks total":
        PyCmd(lambda: [bytes2human(disk_usage(p).total) for p in _partitions]),
    "disks total (bytes)":
        PyCmd(lambda: [disk_usage(p).total for p in _partitions]),
    "disks percent":
        PyCmd(lambda: [disk_usage(p).percent for p in _partitions])
}


temp_cmds = {}  # placeholder
if cur_OS == "Linux":
    from psutil import sensors_temperatures
    # these are gonna be filled with device names and labels, could be different for each system.
    temp_cmds = {dev: PyCmd(sensors_temperatures, get=dev) for dev in sensors_temperatures()}
    temp_cmds = {f"{k} {temp.label}": PyCmd(v, get=i) for k, v in temp_cmds.items()
                 for i, temp in enumerate(v.run())}
    temp_cmds = {f"{k} {label}": PyCmd(v, get_attr=label) for k, v in temp_cmds.items()
                 for label in ["current", "high", "critical"]}

if cur_OS == "Windows":
    temp_cmds = {  # not supported on all systems, some it may also not update or require admin
        # TODO: these are returned in a \n deliminated list if there's multiple
        "CPU": BashCmd(r"wmic /namespace:\\root\wmi PATH MSAcpi_ThermalZoneTemperature get CurrentTemperature",
                       postformat_fn=lambda x: numbers_only(x) / 10 - 273.15),
        "active throttle temp":
            BashCmd(r"wmic /namespace:\\root\wmi PATH MSAcpi_ThermalZoneTemperature get ActiveTripPoint",
                    postformat_fn=lambda x: numbers_only(x) / 10 - 273.15),
        "passive throttle temp":
            BashCmd(r"wmic /namespace:\\root\wmi PATH MSAcpi_ThermalZoneTemperature get PassiveTripPoint",
                    postformat_fn=lambda x: numbers_only(x) / 10 - 273.15),
        "instance name":
            BashCmd(r"wmic /namespace:\\root\wmi PATH MSAcpi_ThermalZoneTemperature get InstanceName")
    }
system_strings = populate_runtime_strs(system_strings)

all_cmds = {
    "system strings": system_strings,
    "cpu cmds": cpu_cmds,
    "mem cmds": mem_cmds,
    "nvidia cmds": nvidia_cmds,
    "disk cmds": disk_cmds,
    "net cmds": net_cmds,
    "temp cmds": temp_cmds
}

if __name__ == "__main__":
    # if this is run on its own, test all the commands and print results.
    for key, item in all_cmds.items():
        try:
            _test_cmds(item, title=f"{key}:")
            print()
        except Exception as e:
            print(f"Error in {key}:", e)
    perm = input("Run web commands too? These use HTTP requests, and will send information to unaffiliated servers.\n" +
                 "'y' or 'yes' to continue, any other response won't send the requests. Answer:  ").lower()
    if perm == 'y' or perm == 'yes':
        from pywidgets.sample_web_data import web_cmds
        try:
            _test_cmds(web_cmds, title="web cmds:")
        except Exception as e:
            print("Error in web cmds:", e)
