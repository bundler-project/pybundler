from bundler import *

bundler = Bundler("./bin", "/tmp", logf=(lambda msg: print(msg)), dry=False)
#cc_alg = CCAlg("nimbus",
#    flow_mode = "XTCP",
#    loss_mode = "Bundle",
#    bw_est_mode = "false",
#    bundler_qlen_alpha=100,
#    bundler_qlen_beta=10000,
#    use_switching= "true",
#    pass_through = "false",
#    bundler_qlen = 150,
#)

# Attempt to send at a constant rate of 6Mbps with a maximum cwnd of 120 pkts
cc_alg = CCAlg("const", rate="6", cwnd_cap="120")

outgoing_filter = make_filter("10gp1", "10.1.1.2","10.1.1.5", "tcp", (4000,5000), (4000,5000))
incoming_filter = make_filter("em2", "10.1.1.5","10.1.1.2", "tcp", (4000,5000), (4000,5000))
config = BundlerConfig(
    outgoing_iface="10gp1",
    outgoing_filter=outgoing_filter,
    incoming_iface="em2",
    incoming_filter=incoming_filter,
    inbox_listen_addr='0.0.0.0:28317',
    outbox_send_addr='10.1.1.5:28317',
    initial_sample_rate=128,
    qdisc_buffer_size='15Mbit',
)
bundler.activate(cc_alg, config)

bundler.check_alive()
bundler.deactivate()
