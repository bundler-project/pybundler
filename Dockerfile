FROM ubuntu:18.04

RUN apt update && apt install -y git build-essential
RUN apt install -y sudo curl
RUN apt install -y libtool automake autoconf \
		llvm llvm-dev clang libclang-dev \
		libnl-3-dev libnl-genl-3-dev libnl-route-3-dev libnfnetlink-dev \
		libdb-dev \
		bison flex libpcap-dev

RUN useradd -ms /bin/bash docker
RUN adduser docker sudo
RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
USER docker
WORKDIR /home/docker
ADD . .

RUN git submodule update --init --recursive
RUN sudo chown -R docker:docker .
RUN make
