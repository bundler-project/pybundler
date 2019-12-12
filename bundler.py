import os
import util
from collections import namedtuple
from typing import List, Tuple

"""
Example of how to use Bundler API.

>>> from bundler import Bundler, CCAlg, BundlerConfig, Filter, make_filter
>>>
>>> bundler = Bundler("/path/to/bin/", "absolute/path/to/log", logf=(lambda msg: print(msg)))
>>> cc_alg = CCAlg('nimbus', param="val", param2="val2", param3="val3")
>>> outgoing_filter = make_filter(...)
>>> incoming_filter = make_filter(...)
>>> # check to make sure *_filter.sport_range and outgoing_filter.dport_range are ok
>>> config = BundlerRoutingConfig(
>>>    outgoing_filter=outgoing_filter,
>>>    incoming_filter=incoming_filter,
>>>    key=val,
>>>    ...
>>> )
>>> # all of the above functions simply construct commands but do not run them. the following
>>> # command runs everything.
>>> bundler.activate(cc_alg, config)
>>>
>>> ...
>>>
>>> # make sure bundler is still running
>>> bundler.check_alive()
>>>
>>> ...
>>>
>>> # done with bundler
>>> bundler.deactivate()
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

"""
:param outgoing_iface  network interface (eg. eth0) that inbox should attach to
:param outgoing_filter Filter object describing exactly which outgoing packets should be routed through bundler
:param incoming_iface  network interface (eg. eth0) that outbox should listen for pkts on
:param incoming_filter Filter object describing exactly which incoming packets are controlled by a remote bundler
:param inbox_listen_addr The address, in ip:port format, that the inbox should listen on for reports from the remote outbox
:param outbox_send_addr The address, in ip:port format, of the remote inbox that the outbox should send rate updates to
:param initial_sample_rate The initial rate at which bundler will sample packets. Higher data transfer rates allow for higher sampling rates (and thus less overhead) without loss of performance.
:param qdisc_buffer_size string, eg. "15Mbit" describing total size of the internal bundler queue
"""
BundlerConfig = namedtuple('BundlerConfig', [
    'outgoing_iface',
    'outgoing_filter',
    'incoming_iface',
    'incoming_filter',
    'inbox_listen_addr',
    'outbox_send_addr',
    'initial_sample_rate',
    'qdisc_buffer_size',
])

Filter = namedtuple('Filter', [
    'src_ip',
    'sport',
    'sport_mask',
    'sport_range',
    'dst_ip',
    'dport',
    'dport_mask',
    'dport_range',
    'proto',
    'tc_command',
    'pcap_command'
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
        :param log_dir (string) *absolute* path to directory where all bundler logs can be created
        :param dry     (boolean) if true, don't actually run any commands
        :param logf    (function str->) given a string message, handles printing or logging it

        """
        if log_dir[0] != "/":
            raise BundlerException("log_dir must be an *absolute* path (and thus should start with '/')")

        self.bin_dir = bin_dir
        self.log_dir = log_dir

        self.shell = util.CommandRunner(dry=dry, log=logf)

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
        self.config = config

        self._start_inbox(config)
        self._add_filters(config)
        self._start_ccp(cc_alg, config)
        self._start_outbox(config)

    def update_outgoing_filter(self, new_filter):
        self._remove_all_filters()
        if not self.actiavted:
            raise BundlerException("bundler not active. cannot update filter if bundler is not activated yet.")
        self.shell.expect(self.shell.run(
            new_filter.tc_command,
            sudo=True,
        ), "failed to update outgoing filter")

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
            self.shell.check_file_not('err', outfile)

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
        iface = self.config.outgoing_iface
        self.shell.expect(self.shell.run(
            f"tc filter del dev {iface} root"
        ), "failed to remove all filters")

    def _kill_all(self):
        proc_regex = "|".join(self.running_procs)
        self.shell.run("pkill -f -9 \"({search})\"".format(search=proc_regex), sudo=True)
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
                port=config.inbox_listen_addr.split(":")[1],
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

    def _add_filters(self, config):
        outfile = self._get_log_path("tc")

        with open(outfile, 'a') as f:
            f.write("> " + config.outgoing_filter.tc_command + "\n")
        self.shell.expect(self.shell.run(
            config.outgoing_filter.tc_command,
            sudo=True,
            stdout=outfile,
            stderr=outfile,
        ), "failed to insert bundler traffic tc filter")

        catch_all_filter = "tc filter add dev {iface} parent 1: protocol all prio 7 u32 match 32 0 0 flowid 1:3".format(
            iface=config.outgoing_iface
        )
        with open(outfile, 'a') as f:
            f.write("> " + catch_all_filter + "\n")
        self.shell.expect(self.shell.run(
            catch_all_filter,
            sudo=True,
            stdout=outfile,
            stderr=outfile,
        ), "failed to insert catch-all tc filter")


    def _start_ccp(self, cc_alg, config):
        """
        Starts CCP.

        :param  cc_alg_name  (string) name of the algorithm. must have been compiled already.
        :param  cc_args      (dictionary) containing argument keys and values to be passed as
                             command line parameters to ccp
        """

        outfile = self._get_log_path("ccp")
        cmd_args = [f"--{arg}=\"{val}\"" for arg, val in cc_alg.kwargs.items()]

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
                pcap_filter=config.incoming_filter.pcap_command,
                iface=config.incoming_iface,
                inbox_addr=config.outbox_send_addr,
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

def make_filter(
        src_ip: str,
        dst_ip: str,
        protocol: str,
        src_portrange: Tuple[int, int],
        dst_portrange: Tuple[int, int],
    ) -> Filter:
    """make_filter helps construct a filter for bundler that is amenable to both tc and pcap

    :param src_ip should be of the form "x.x.x.x/x"; i.e., to match on all IP addresses
    callers should pass "0.0.0.0/0".
    :param dst_ip same as src_ip.
    :param protocol should be either "tcp" or "udp".
    :param src_portrange are of the form [min_port, max_port] (inclusive).
    :param dst_portrange same as src_portrange.

    # Return Value
    This function returns a filter object that bundler knows how to install.
    Because tc uses bitmasking to express port ranges, it may not be possible to achieve exactly
    the range requested in the parameters. This function does its best to keep as close as possible
    to the ranges during the conversion process. The caller should check the actual port ranges
    generated and make sure they are acceptable, eg.
    >>> outgoing_filter = make_filter(...)
    >>> print(outgoing_filter.sport_range, outgoing_filter.dport_range)

    This function does not actually apply any commands, so it can be called repeatedly to adjust
    the portranges as desired. Once the caller is happy with the generated ranges, they can be
    used in the config for bundler.activate() or to update the outgoing filter in
    bundler.update_outgoing_filter()
    """
    if protocol == "tcp":
        proto = 6
    elif protocol == "udp":
        proto = 17
    else:
        raise Exception(f"unknown protocol {protocol}, must be (tcp|udp)")

    def _range_from_mask(n, mask):
        return (n, n | (~mask & 0xffff))

    def _mask(start, end):
        """Return the mask that matches the range [start, end).

        >>> _mask(5000, 6000)
        61440
        """
        mask = 0x8000
        while _range_from_mask(start, mask)[1] > end:
            mask = mask | (mask >> 1)
        mask = (mask << 1) & 0xffff
        return (hex(mask), _range_from_mask(start, mask))

    s = src_portrange[0]
    d = src_portrange[1]
    sport_mask, sport_range = _mask(s, d)
    sport, sport_mask = (s, sport_mask)
    s = dst_portrange[0]
    d = dst_portrange[1]
    dport_mask, dport_range = _mask(s, d)
    dport, dport_mask = (s, dport_mask)

    tc_command = f"\
        tc filter add dev 10gp1 \
        parent 1: \
        protocol ip prio 6 \
        u32 \
        protocol {proto} 0xff \
        match ip src {src_ip} \
        match ip dst {dst_ip} \
        match ip sport {sport} {sport_mask} \
        match ip dport {dport} {dport_mask} \
        flowid 1:2"

    pcap_command = f"{protocol} and src {src_ip} and dst {dst_ip} and src portrange {sport_range} and dst portrange {dport_range}"

    f = Filter(src_ip=src_ip, sport=sport, sport_mask=sport_mask, sport_range=sport_range,
           dst_ip=dst_ip, dport=dport, dport_mask=dport_mask, dport_range=dport_range,
           proto=proto, tc_command=tc_command, pcap_command=pcap_command)

    return f

