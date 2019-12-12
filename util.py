import subprocess

class CommandRunner:
    def __init__(self, dry=False, verbose=False, log=None):
        self.dry = dry
        self.silent = not verbose
        if log:
            self.log = log
        else:
            self.log = (lambda *args: None)

    def run(self, cmd, stdin="/dev/stdin", stdout="/dev/stdout", stderr="/dev/stderr", ignore_out=False, wd=None, sudo=False, background=False, pty=True, **kwargs):
        pre = ""
        if wd:
            pre += "cd {} && ".format(wd)
        if background:
            pre += "screen -d -m "
        cmd = cmd.replace("\"", "\\\"")
        if sudo:
            pre += "sudo "
        pre += "bash -c \""
        if ignore_out:
            if self.silent and stdout == "/dev/stdout":
                stdout="/dev/null"
            if self.silent and stderr == "/dev/stderr":
                stderr="/dev/null"
        if background:
            stdin="/dev/null"

        full_cmd = "{pre}{cmd} > {stdout} 2> {stderr} < {stdin}".format(
            pre=pre,
            cmd=cmd,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        )

        full_cmd += "\""

        if self.dry:
            self.log("> {}".format(full_cmd))
            return 0
        else:
            return subprocess.call(full_cmd, shell=True, **kwargs)

        
    def file_exists(self, fname):
        self.expect(
            self.run("ls {}".format(fname)),
            "file does not exist: {}".format(fname)
        )

    def prog_exists(self, prog):
        self.expect(
            self.run("which {}".format(prog)),
            "program does not exist: {}".format(prog)
        )

    def check_proc(self, proc_name):
        self.expect(
            self.run("pgrep -f {}".format(proc_name)),
            'failed to find running process with name \"{}\"'.format(proc_name)
        )

    def check_procs(self, proc_regex):
        self.expect(
            self.run("pgrep -f -c \"{search}\"".format(search=proc_regex), sudo=True),
            'failed to find any of the running processes: \"{}\"'.format(proc_regex)
        )

    def check_file(self, grep, where):
        self.expect(
            self.run("grep \"{}\" {}".format(grep, where)),
            "unable to find search string (\"{}\") in process output file {}".format(
                grep,
                where
            )
        )

    def search_file(self, grep, where):
        self.expect(
            not self.run("grep \"{}\" {}".format(grep, where)),
            "found error message in log file {}".format(where)
        )

    def expect(self, res, msg):
        if res:
            raise Exception(msg)

