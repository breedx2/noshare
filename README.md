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

(for server setup/usage [go here](server/README.md))
