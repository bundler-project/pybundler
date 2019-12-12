# pybundler

This repository contains a Python library interface for easily running [Bundler](https://github.com/bundler-project/bundler).

Bundler itself consists of two main parts: a userspace program (written in Rust), and a custom qdisc (implemented as a Linux kernel module that must be installed into the kernel). 
This library simply helps with running the proper commands to start, stop, and configure Bundler and the associated traffic filters.  

Before using this library, you must be follow the steps below to install all of the necessary dependencies. 

**Important**: Bundler *must* be run on both sides of a connection (near/at the sender, and near/at the receiver). Thus, the following setup steps need to be performed on *both* machines. 

## Setup


1. Inside this repository, fetch all git submodules:
```git submodule update --init --recursive```

2. Build all dependencies: 
```make```
(**Note**: this may take a while, it needs to install the Rust language and a bunch of Ubuntu packages, and then compile Bundler source code)

3. Take note of the `bin` directory. By default, it is created immediately inside this repository after running make (`pybundler/bin`). You may place it elsewhere, but either way you must supply the full absolute path to the `pybundler` library upon initialization.

4. You may need to make sure NOPASSWD is enabled (for example, the script may internally be trying to start processes with sudo and hanging on a password prompt). 
Run `sudo visudo` and edit the sudo permissions line to look as follows:
```%sudo   ALL=(ALL:ALL) ALL```

## Usage

The following steps describe the high-level API and expected usage of bundler within a script. Please see `bundler.py` for detailed documentation of each class and function, as well as descriptions of the required parameters.

All of these calls will throw a `BundlerException` with an associated error message if anything goes wrong, so you may want to place these calls inside of a `try`/`except` block to make sure you are handling errors properly.

1. Important the pybundler library:

```python
from bundler import *
```

**Note**: `bundler` is just referencing the name of the local `bundler.py` found in this repository. If you try to import it in a different directory, it will fail, because python doesn't know where to find it. Thus, you must tell python where to find it (eg. using `sys.path.insert(...)` or move this script directly to your source (may work, but not recommended).

2. Initialize an instance of Bundler. The first argument is where you will specify the bin directory you noted above. This dummy lambda log function prints all log messages to stdout, and the `dry` parameter allows us to perform a "dry-run", seeing what commands would be run without actually running them.

```python
bundler = Bundler("/path/to/bin/", "./", logf=(lambda msg: print(msg)), dry=True)
```

3. Initialize the congestion control algorithm we'd like to use (at the moment, only Nimbus is recommended). All optional command line arguments can be passed as optional parameters to the constructor. For a list of available parameters, please see the Nimbus repository. 

```python
cc_alg = CCAlg("nimbus", arg="val", arg2="val2")
```

4. Initialize the bundler config, describing all of the relevant network interfaces, addresses, and bundler default parameters. Please see bundler.py for a description of each.

```python
config = BundlerConfig(...)
```

5. Up until this point, we have just been constructing configuration objects. To actually start running bundler, which involves installing the qdisc and all necessary tc/pcap filters, and the corresponding cc algorithm, use `activate`:

```python
bundler.activate(cc_alg, config);
```

At any time, you can check if all bundler components are running as expected (this method will throw an exception if there are any problems and do nothing otherwise):

```python
bundler.check_alive()
```

Finally, when you want to stop bundler:

```python
bundler.deactivate()
```

For a complete dry-run example (that should work properly out of the box once everything has been installed), see `test.py`.
