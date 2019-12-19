all: bundler-procs ccp-procs

bundler-procs: bin/inbox bin/outbox
ccp-procs: bin/nimbus bin/const
	
bin/inbox: bundler/target/debug/inbox 
	mkdir -p bin && cp bundler/target/debug/inbox bin/inbox
	
bin/outbox: bundler/target/debug/outbox
	mkdir -p bin && cp bundler/target/debug/outbox bin/outbox

bin/nimbus: nimbus/target/debug/nimbus
	mkdir -p bin && cp nimbus/target/debug/nimbus bin/nimbus

bin/const: const/target/debug/ccp_const
	mkdir -p bin && cp const/target/debug/ccp_const bin/const

rustup.sh:
	curl https://sh.rustup.rs -sSf > rustup.sh

~/.cargo/bin/cargo: rustup.sh
	sh rustup.sh -y --default-toolchain=nightly

bundler/target/debug/inbox bundler/target/debug/outbox: ~/.cargo/bin/cargo $(shell find bundler/src -name "*.rs")
	sudo apt update && sudo DEBIAN_FRONTEND=noninteractive apt install -y \
		libtool automake autoconf \
		llvm llvm-dev clang libclang-dev \
		libnl-3-dev libnl-genl-3-dev libnl-route-3-dev libnfnetlink-dev \
		libdb-dev \
		bison flex libpcap-dev \
		screen
	cd bundler && ~/.cargo/bin/cargo +nightly build

nimbus/target/debug/nimbus: ~/.cargo/bin/cargo $(shell find nimbus/src -name "*.rs")
	cd nimbus && ~/.cargo/bin/cargo +nightly build

const/target/debug/ccp_const: ~/.cargo/bin/cargo $(shell find const/src -name "*.rs")
	cd const && ~/.cargo/bin/cargo +nightly build

clean:
	rm -rf const/target/ nimbus/target/ bundler/target/ bin/
