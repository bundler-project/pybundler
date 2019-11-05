import subprocess
import math
from typing import List, Tuple

def mask(start, end):
    """Return the mask that matches the range [start, end).

    >>> mask(5000, 6000)
    61440
    """
    mask = 0x8000
    while range_from_mask(start, mask)[1] > end:
        mask = mask | (mask >> 1)
    mask = (mask << 1) & 0xffff
    return (hex(mask), range_from_mask(start, mask))

def range_from_mask(n, mask):
    return (n, n | (~mask & 0xffff))

def filter():
    # by default, everything goes in the lowest priority
    subprocess.call("sudo tc filter add dev 10gp1 parent 1: protocol all prio 7 u32 match u32 0 0 flowid 1:3")

def make_filter(
        src_ip: str,
        dst_ip: str,
        protocol: str,
        src_portrange: Tuple[int, int],
        dst_portrange: Tuple[int, int],
    ) -> Tuple[str, Tuple[Tuple[int, int], Tuple[int, int]]]:
    """make_filter helps construct an invocation of tc.

    # Arguments
    - src_ip and dst_ip should be of the form "x.x.x.x/x"; i.e., to match on all IP addresses
    callers should pass "0.0.0.0/0".
    - protocol should be either "tcp" or "udp".
    - src_portrange and dst_portrange are of the form [min_port, max_port] (inclusive).

    # Return Value
    Because tc uses bitmasking to express port ranges, this function converts from the [min, max] format.
    In the conversion, the portrange may change. This function therefore returns the new port ranges as the
    second return value as follows:

    (invocation_string, (new_src_portrange, new_dst_portrange))

    If the new portranges are acceptable, callers can pass invocation_string to apply_filter() to apply it.
    """
    if protocol == "tcp":
        proto = 6
    elif protocol == "udp":
        proto = 17
    else:
        raise Exception(f"unknown protocol {protocol}, must be (tcp|udp)")

    s = src_portrange[0]
    d = src_portrange[1]
    sport_mask, sport_range = mask(s, d)
    sport, sport_mask = (s, sport_mask)
    s = dst_portrange[0]
    d = dst_portrange[1]
    dport_mask, dport_range = mask(s, d)
    dport, dport_mask = (s, dport_mask)
    filter_str = f"\
        sudo tc filter add dev 10gp1 \
        parent 1: \
        protocol ip prio 6 \
        u32 \
        protocol {proto} 0xff \
        match ip src {src_ip} \
        match ip dst {dst_ip} \
        match ip sport {sport} {sport_mask} \
        match dport {dport} {dport_mask} \
        flowid 1:2"
    return (filter_str, (sport_range, dport_range))

def apply_filter(filter_str):
    """Takes the first return value of make_filter().
    """
    subprocess.call(filter_str)
