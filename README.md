# noshare

`noshare` is a low overhead centralized/brokered peer-to-peer cloud file sharing
mechanism...because:

* sharing files with friends/family is _still_ hard
* hole punching through NATs (like with webrtc) is still flaky
* ...and...
* sometimes other shared resources are unreliable.

The server facilitates encrypted and authorized bridging between clients.
The client provides an easy way to send/receive a file with another
user on the same server, and that's it. That's all it is.

# how

* The server is a single static/restricted, dockerized openssh instance.
* The client is a zero-dependency python script that leverages ssh as a tunnel
  through which to pipe data.

It looks like this:

[diagram]

# client quickstart

The noshare client can both _offer_ files and _receive_ files.

You must give your server admin your public ssh key (below).

Your server/admin must give you:
* a hostname or ip address
* a port (or "default" which is 20666)

And optionally:
* server ssh fingerprint

## keygen

You probably have an ssh pubkey in `~/.ssh/id_rsa.pub` and you can just use
that (preferred), or if you're stubborn you can make a new one:

```
$ ssh-keygen -f ~/.ssh/noshare
```

If you set a passphrase, you probably need to add the key to the ssh agent
for every session with `ssh-add ~/.ssh/noshare`.

## path/shell

Now to get the `noshare` command into your shell!

**Option 1** -- Add this to the end of your `~/.bash_profile` or whatever and
afterward restart your shell:
```
alias noshare="python /path/to/noshare.py"
```

**Option 2** -- Create an executable file called `noshare` and put it in your path,
with the contents:

```
#!/bin/bash
python /path/to/noshare.py $@
```

Don't forget to `chmod 755 /path/to/noshare`.

**Option 3** -- Run `python /full/path/to/noshare.py` each time (blah)

## config

Now that you've got the client available, you need to do a one-time configuration.
You can safely skip this and it'll prompt you the first time you offer or
receive.

Run `noshare config` and enter the host and port that your admin gave you,
and the path to the private key corresponding to the pubkey you gave to your admin.

If your admin gave you an ssh server hostkey, you can add that as well, otherwise
the config step will probe for it. It's a good idea to verify that the probed 
value matches the true server hostkey fingerprint (check with the admin if unsure).

The result will be saved in `~/.noshare` and looks like this:

```
[noshare]
host = your.example.com
port = 20666
keyfile = /home/user/.ssh/noshare
fingerprint = ssh-ed25519 ABCDC3NzaC1lZDI1NTE5AAAdIJB8pG9d87RdbLBXKpD7tSMKACL2gbpDiCfX123123123
```

## offer

To offer a one-shot file:

```
noshare /path/to/file.tgz
```

The output will look like:

```
$ noshare /path/to/file.tgz
Config read from /home/user/.noshare
Setting up local server listener...
Local ephemeral port is 12123
Setting up ssh tunnel...
offer id: 42731:ef38e8e7dc6f4536b5430bf52083e0bc
ssh tunnel established (pid=1234)
```

Copy the offer id (in this example `42731:ef38e8e7dc6f4536b5430bf52083e0bc`)
and send that to the receiving party somehow.

The offer must continue running on your side until the receiver has completed
the transaction. If you kill the app or close the terminal session or power
down, the offer is dead and will fail.

There is no server "upload"...just a transfer to the receiver when requested.
Once the transfer is complete, the offer id is no longer valid for any
other peers.

## receive

Have an offer id from someone? Great! If you've already configured `noshare`,
it's simple:

```
$ noshare 42731:ef38e8e7dc6f4536b5430bf52083e0bc
Config read from /home/user/.noshare
Setting up ssh tunnel...
ssh tunnel established (pid=12345)
Download file.tgz (236.8 MB)? [y]
downloading...
  / 100.0% [1.5 MB/s] [236.8 MB of 236.8 MB] took 00:02:52      
saved file.tgz
```

If the target file already exists, you should be prompted before overwriting.

# server quickstart

For server setup/usage [go here](README-server.md).

# shortcomings/weaknesses/future

In order to keep things moderately simple, corners are cut. In the interest
of disclosure, some obvious problems are listed here. These should probably
turn into issues.

* multiple servers -- for simplicity, not supported.
* one-shot -- it's convenient but kinda stupid that files are one-shot, and
  maybe there should be a way to keep an offer open/alive for some time or number
  of serves.
* no idea if ssh key passphrase prompts work, probably not.
* send/receive buffers are both static and hard coded -- a dynamic approach might
  yield more efficient transfers.
* there are no server bandwidth guardrails and trusted clients could abuse this
