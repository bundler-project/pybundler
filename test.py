from bundler import *

bundler = Bundler("/path/to/bin/", "/path/to/log/", logf=(lambda msg: print(msg)), dry=True)
cc_alg = CCAlg("nimbus", arg="val", arg2="val2")
config = BundlerConfig(
    outgoing_iface="eth-out", 
    incoming_iface="eth-in", 
    inbox_inband_port=1000, 
    outbox_inband_port=2000, 
    initial_sample_rate=128, 
    qdisc_buffer_size='15Mbit',
    other_inbox='0.0.0.0:28317',
    other_inbox_ports=(4000,5000)
)
bundler.activate(cc_alg, config)

bundler.check_alive()

bundler.deactivate()
