from bundler import *

bundler = Bundler("/path/to/bin/", "/tmp", logf=(lambda msg: print(msg)), dry=True)
cc_alg = CCAlg("nimbus", arg="val", arg2="val2")
outgoing_filter = make_filter("1.1.1.1","2.2.2.2","tcp", (4000,5000), (4000,5000))
incoming_filter = make_filter("2.2.2.2","1.1.1.1","tcp", (4000,5000), (4000,5000))
config = BundlerConfig(
    outgoing_iface="ethout", 
    outgoing_filter=outgoing_filter,
    incoming_iface="ethin", 
    incoming_filter=incoming_filter,
    inbox_listen_addr='0.0.0.0:28317',
    outbox_send_addr='1.2.3.4:28317',
    initial_sample_rate=128, 
    qdisc_buffer_size='15Mbit',
)
bundler.activate(cc_alg, config)

bundler.check_alive()

bundler.deactivate()
