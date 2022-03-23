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
