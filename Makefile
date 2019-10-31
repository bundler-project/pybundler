all: bundler-procs

bundler-procs: bundler/target/debug/inbox bundler/target/debug/outbox

rustup.sh:
	curl https://sh.rustup.rs -sSf > rustup.sh

~/.cargo/bin/cargo: rustup.sh
	sh rustup.sh -y

bundler/target/debug/inbox bundler/target/debug/outbox: ~/.cargo/bin/cargo $(shell find bundler/src -name "*.rs")
	sudo apt update && sudo DEBIAN_FRONTEND=noninteractive apt install -y \
		libtool automake autoconf \
		llvm llvm-dev clang libclang-dev \
		libnl-3-dev libnl-genl-3-dev libnl-route-3-dev libnfnetlink-dev \
		libdb-dev \
		bison flex libpcap-dev
	cd bundler && ~/.cargo/bin/cargo build

nimbus/target/debug/nimbus: ~/.cargo/bin/cargo $(shell find nimbus/src -name "*.rs")
	cd nimbus && ~/.cargo/bin/cargo build

install: bundler-procs setup.py
	pip install .
