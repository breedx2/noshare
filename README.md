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

(for server setup/usage [go here](README-server.md))

Your server/admin must give you:
* a hostname or ip address
* a port (or "default" which is 20666)


## keygen

You probably have an ssh pubkey in `~/.ssh/id_rsa.pub` and you can just use
that (preferred), or if you're stubborn you can make a new one:

```
$ ssh-keygen -f ~/.ssh/noshare
```

If you set a pasphrase, you probably need to add the key to the ssh agent
for every session with `ssh-add ~/.ssh/noshare`.

## path/shell

Now to get the noshare command into your shell!

**Option 1** -- Add this to the end of your `~/.bash_profile` or whatever and
afterward restart your shell:
```
alias noshare="python $(pwd)/noshare.py"
```

**Option 2** -- Create an executable file called `noshare` and put it in your path,
with the contents:

```
#!/bin/bash
python /path/to/noshare.py $@
```

**Option 3** -- Run `python /full/path/to/noshare.py` each time (blah)

## setup

Run `noshare config` and enter the host, port, and keyfile.
The result will be saved in `~/.noshare` and looks like this:

```
[noshare]
host = your.example.com
port = 20666
keyfile = /home/user/.ssh/noshare
```

## usage


# shortcomings/weaknesses/future

In order to keep things moderately simple, corners are cut. In the interest
of disclosure, some obvious problems are listed here. These should probably
turn into issues.

* server host key checking -- Straight-up disabled. yup. sorry. It's convenient,
  but insecure and it should be improved. This means someone could redirect dns
  and intercept/mitm traffic.
* multiple servers -- for simplicity, not supported.
* one-shot -- it's convenient but kinda stupid that files are one-shot, and
  maybe there should be a way to keep an offer open/alive for some time or number
  of serves.
* no idea if ssh key passphrase prompts work, probably not.
