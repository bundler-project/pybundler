from util import CommandRunner
import os
from collections import namedtuple

"""
Example of how to use Bundler API.

```
bundler = Bundler("/path/to/bin/", "/path/to/log", logf=(lambda msg: print(msg)))
cc_alg = CCAlg('nimbus', param="val", param2="val2", param3="val3")
config = BundlerRoutingConfig(
    key=val,
    key=val,
)
bundler.activate(cc_alg, config)

...

# make sure bundler is still running
bundler.check_alive()

...

# done with bundler
bundler.deactivate()
```
"""
class BundlerException(Exception):
    """
    Indicates some sort of problem with bundler. Contains a single parameter, a string describing
    the error.
    """
    pass


class CCAlg:
    """
    Convenience wrapper for representing a CCP congestion control algorithm.
    """
    def __init__(self, name, **kwargs):
        """
        Create a new algorithm parameterization. Does not actually run the algorithm, just contains
        all the necessary information to run it. Bundler.activate() handles actually starting CCP.

        :param name   (string) name of the algorithm, e.g. nimbus
        :param kwargs any other key=val style arguments passed will be fed as --key=value to CCP
        """
        self.name = name
        self.kwargs = kwargs


#class BundlerConfig:
#    """
#    Convenience wrapper for describing all parameters for bundler
#
#    (network setup)
#    :param outgoing_iface      network interface (eg. eth0) that inbox should attach to
#    :param incoming_iface      network interface (eg. eth0) that outbox should listen for pkts on
#    :param inbox_inband_port   port inbox will listen on for feedback from outbox
#    :param outbox_inband_port  port outbox will listen on for sample rate updates from inbox
#    :param other_inbox         string ip:port describing how to reach other inbox
#    :param other_inbox_ports   (int,int) tuple range of ports describing where outbox should listen
#
#    (internal parameters)
#    :param initial_sample_rate must be power of 2, e.g. 128
#    :param qdisc_buffer_size   string, e.g. 15Mbit describing total size of internal bundler queue
#
#    """
#    def __init__(self, **kwargs):
#
#        for param in params:
#            if not param in kwargs:
#                raise BundlerException('config missing key {}'.format(param))
#        self.kwargs = kwargs
#        print(self.kwargs)

BundlerConfig = namedtuple('BundlerConfig', [
    'outgoing_iface',
    'incoming_iface',
    'inbox_inband_port',
    'outbox_inband_port',
    'initial_sample_rate',
    'qdisc_buffer_size',
    'other_inbox',
    'other_inbox_ports'
])


class Bundler:
    """
    This class handles starting, stopping, and checking on bundler.
    
    Note: Functions beginning with an underscore (except __init__) are private internal functions
    that are not meant to be called directly. 
    """
    def __init__(self, bin_dir, log_dir, dry=False, logf=None):
        """
        :param bin_dir (string) path to directory where all bundler binaries are located
        :param log_dir (string) path to directory where all bundler logs can be created
        :param dry     (boolean) if true, don't actually run any commands
        :param logf    (function str->) given a string message, handles printing or logging it

        """
        self.bin_dir = bin_dir
        self.log_dir = log_dir

        self.shell = CommandRunner(dry=dry, log=logf)

        self.running_logs = []
        self.running_procs = []

        self.activated = False

    def activate(self, cc_alg, config):
        """ 
        Starts all Bundler and CCP processes, and inserts appropriate tc and pcap filters to 
        direct traffic through the Bundler.

        :param  cc_alg          (CCAlg object) contains a CCP algorithm and runtime parameters
        :param  config 

        :raise  BundlerException if any of the processes fail to start.
        :return nothing
        """

        if self.activated:
            raise BundlerException("bundler already activated, call deactivate() first")

        self.activated = True

        self._start_inbox(config)
        self._start_ccp(cc_alg, config)
        self._start_outbox(config)


    def deactivate(self):
        """
        Stops all Bundler and CCP processes and removes all associated tc and pcap filters.

        :raises  BundlerException if unable to kill any of the processes or remove the filters.
        """
        self._kill_all()
        self._remove_all_filters()
        self.activated = False


    def check_alive(self):
        """
        Ensures all components of bundler are still healthy.

        :raise  BundlerException if any of the processes have died or have error messages in their logs.

        """
        if not self.running_procs:
            raise BundlerException("called check_alive(), but no processes have been started yet")
        self.shell.check_procs("|".join(self.running_procs))
        for outfile in self.running_logs:
            self.shell.check_file('err', outfile)

    def check_dead(self):
        """
        Returns True if all components of bundler are dead, False otherwise.
        
        """
        if not self.running_procs:
            return True
        try:
            self.shell.check_procs("|".join(self.running_procs))
        except BundlerException:
            return True
        return False

    def _remove_all_filters(self):
        # TODO Akshay
        if False:
            raise BundlerException("failed to removea all filters")

    def _kill_all(self):
        proc_regex = "|".join(self.running_procs)
        self.shell.run("pkill -9 \"({search})\"".format(search=proc_regex), sudo=True)
        if not self.check_dead() and not self.shell.dry:
            raise BundlerException("failed to kill all bundler processes")
        self.running_logs = []
        self.running_procs = []


    def _get_log_path(self, proc):
        return os.path.join(self.log_dir, proc + ".log")
    def _get_bin_path(self, proc):
        return os.path.join(self.bin_dir, proc)


    def _start_inbox(self, config):
        outfile = self._get_log_path("inbox")

        self.shell.expect(self.shell.run(
            "{path} --iface={iface} --port={port} --sample_rate={sample} --qtype={qtype} --buffer={buf}".format(
                path=self._get_bin_path("inbox"),
                iface=config.outgoing_iface,
                port=config.inbox_inband_port,
                sample=config.initial_sample_rate,
                qtype="prio",
                buf=config.qdisc_buffer_size,
            ),
            sudo=True,
            background=True,
            stdout=outfile,
            stderr=outfile,
        ), "failed to start send side")

        self.shell.check_proc('inbox')
        self.shell.check_file('Wait for CCP to install datapath program', outfile)

        self.running_logs.append(outfile)
        self.running_procs.append('inbox')
        
    def _start_ccp(self, cc_alg, config):
        """
        Starts CCP. 

        :param  cc_alg_name  (string) name of the algorithm. must have been compiled already.
        :param  cc_args      (dictionary) containing argument keys and values to be passed as 
                             command line parameters to ccp
        """

        outfile = self._get_log_path("ccp")
        cmd_args = ["--{arg}=\"{val}\"".format(arg=arg,val=val) for arg, val in cc_alg.kwargs.items()]

        path = self._get_bin_path(cc_alg.name)
        self.shell.expect(self.shell.run(
            "{path} --ipc=unix {args}".format(
                path=path,
                args=" ".join(cmd_args),
            ),
            sudo=True,
            background=True,
            stdout=outfile,
            stderr=outfile
        ), "failed to start ccp")

        self.shell.check_proc(cc_alg.name)
        self.shell.check_file('starting CCP', outfile)
        
        self.running_logs.append(outfile)
        self.running_procs.append(cc_alg.name)


    def _start_outbox(self, config):
        outfile = self._get_log_path("outbox")

        self.shell.expect(self.shell.run(
            "{path} --filter \"{pcap_filter}\" --iface {iface} --inbox {inbox_addr} --sample_rate {sample_rate}".format(
                path=self._get_bin_path("outbox"),
                # TODO Akshay do we also need to handle multiple ranges here?
                pcap_filter="src portrange {}-{}".format(
                    *config.other_inbox_ports
                ),
                iface=config.incoming_iface,
                inbox_addr=config.other_inbox,
                sample_rate=config.initial_sample_rate,
            ),
            sudo=True,
            background=True,
            stdout=outfile,
            stderr=outfile,
        ), "failed to start recv side")

        self.shell.check_proc('outbox')

        self.running_logs.append(outfile)
        self.running_procs.append('outbox')


