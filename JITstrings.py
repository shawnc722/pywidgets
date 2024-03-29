from subprocess import check_output
from typing import Callable, Generic, Sequence, TypeVar, Any

T = TypeVar('T')
U = TypeVar('U')


class PyCmd(Generic[T, U]):
    def __init__(self, cmd: Callable[..., T], *args, postformat_fn: Callable[[T], Any] = None, get: int | object = None,
                 get_attr: str = None, _debug=False, **kwargs):
        """
        A container for a function that behaves like the function's results; think of this like the function's returned
        value, except that the value will update each time it's checked.
        :param cmd: the base function/command to be run.
        :param args: the arguments to pass to the function on runtime. Adds to any arguments given if calling the PyCmd.
        :param postformat_fn: an optional function to format the results, e.g. round. Applied last, after get or get_attr.
        :param get: a key to access from the output of cmd (e.g. output[key]). Can't be used with get_attr.
        :param get_attr: an attribute to access from the output of cmd (e.g. output.attr). Can't be used with get.
        :param _debug: if True, will print args and kwargs when running the PyCmd.
        :param kwargs: the keyword arguments to pass to the function on runtime. Adds to any kwargs given if calling the PcCmd.
        """
        self.cmd = cmd
        self.args = args
        self.kwargs = kwargs
        self.postformat = postformat_fn
        if get is not None and get_attr is not None: raise RuntimeError("'get' and 'get_attr' cannot both be used. Try nesting two PyCmds instead.")
        self.get = get
        self.get_attr = get_attr

        self._debug = _debug

    def __repr__(self): return str(self.run())

    def __str__(self): return str(self.run())

    def __int__(self): return int(self.run())

    def __float__(self): return float(self.run())

    def __getitem__(self, key): return self.run()[key]

    def __contains__(self, item): return item in self.run()

    def __iter__(self):
        for i in self.run(): yield i

    def __call__(self, *args, **kwargs) -> U:
        return self.run(*args, **kwargs)

    def run(self, *runtime_args, **runtime_kwargs) -> U:
        args = self.args + runtime_args
        kwargs = runtime_kwargs.copy()
        kwargs.update(self.kwargs)
        if self._debug:
            print(args, kwargs)
        def call():
            if args and kwargs: return self.cmd(*args, **kwargs)
            elif kwargs: return self.cmd(**kwargs)
            elif args: return self.cmd(*args)
            else: return self.cmd()

        if self.postformat:
            if self.get is not None:
                return self.postformat(call()[self.get])
            if self.get_attr is not None:
                return self.postformat(getattr(call(), self.get_attr))
            return self.postformat(call())
        if self.get is not None:
            return call()[self.get]
        if self.get_attr is not None:
            return getattr(call(), self.get_attr)
        return call()


class BashCmd(PyCmd):
    def __init__(self, cmd: str, use_shell: bool = True, postformat_fn: Callable[[str], T] = None,
                 get: int | object = None, get_attr: str = None, _debug=False, **kwargs):
        """
        Similar to a PyCmd, but using the system terminal to run the command rather than Python.
        :param cmd: the command to pass to the sytem terminal.
        :param use_shell: True by default. Uses system shell to interpret, e.g. /bin/sh on Linux.
        :param postformat_fn: an optional function to format the results.
        :param get: a key to access from the output of cmd (e.g. output[key]). Can't be used with get_attr.
        :param get_attr: an attribute to access from the output of cmd (e.g. output.attr). Can't be used with get.
        :param _debug: if True, will print args and kwargs when running the PyCmd.
        :param kwargs: the keyword arguments to pass to the function on runtime. Adds to any kwargs given if calling the PcCmd.
        """
        self.cmd = cmd
        self.postformat = postformat_fn
        self.use_shell = use_shell

    def run(self) -> str | T:
        if self.postformat:
            return self.postformat(check_output(self.cmd, shell=self.use_shell).decode().strip())
        return check_output(self.cmd, shell=self.use_shell).decode().strip()


class PyCmdWithMem(PyCmd):
    def __init__(self, cmd: Callable, compare: Callable, *args, postformat_fn=None, startval=None,
                 get_attr: str = None, **kwargs):
        """
        Just like a PyCmd, but stores the last result for comparison against the new one.
        :param cmd: the base function/command to be run.
        :param compare: the function/command which compares the previous and current results. Should take two arguments:
            first the current result, and second the previous result.
        :param args: the arguments to pass to the function on runtime. Adds to any arguments given if calling the PyCmd.
        :param postformat_fn: an optional function to format the results.
        :param startval: the starting value to use as the previous result. If None, cmd will immediately be called to store the result.
        :param get_attr: an attribute to access from the output of cmd.
        :param kwargs: the keyword arguments to pass to the function on runtime. Adds to any kwargs given if calling the PcCmd.
        """
        super().__init__(cmd, *args, postformat_fn=postformat_fn, get_attr=get_attr, **kwargs)
        self.compare = compare
        if startval is None and not self.get_attr: self.last = self.cmd(*self.args, **self.kwargs)
        elif startval is None: self.last = getattr(self.cmd(*self.args, **self.kwargs), self.get_attr)
        else: self.last = startval

    def run(self, *runtime_args, **runtime_kwargs):
        if self.get_attr:
            now = getattr(self.cmd(*self.args, *runtime_args, **self.kwargs, **runtime_kwargs), self.get_attr)
        else: now = self.cmd(*self.args, *runtime_args, **self.kwargs, **runtime_kwargs)
        diff = self.compare(now, self.last)
        self.last = now
        if self.postformat:
            return self.postformat(diff)
        return diff


class JITstring(object):
    def __init__(self, static_text: str, cmds: Sequence | Callable):
        """
        A "Just In Time" string that only formats its arguments when displayed, to allow changing the value with each use.
        :param static_text: the unchanging text to format the commands into, with curly brackets anywhere a command should be inserted.
        :param cmds: a list of commands to format into the static text. The number of commands should equal the number of {} in static_text.
        """
        self.static_text = static_text
        self.cmds = cmds

    def add_line(self, line: str, cmds: (list, PyCmd), prepend: str = '<br/>'):
        """Adds another line and/or more commands to the JITstring. Prepends a new line by default."""
        self.static_text += prepend + line
        self.cmds += cmds

    def __repr__(self):
        if type(self.cmds) != list:
            return str(self.static_text).format(*self.cmds())
        return self.static_text.format(*self.cmds)

    def __call__(self): return self.__repr__()
