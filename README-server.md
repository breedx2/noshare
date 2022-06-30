# noshare server

The `noshare` server is really just a glorified configuration of
[openssh server running in docker](https://hub.docker.com/r/linuxserver/openssh-server).

It provides pubkey-only, shell-less ssh connections and allows port forwarding
only to `localhost` (in-container). The result is a docker container acting as
an encrypted port-bridge inside a lazy jail.

The server doesn't store any files, doesn't keep track of connection history,
and doesn't log anything. It acts only as a bridge for a small static set of
authorized users.

Please note: as a server owner, you may pay for bandwidth. Your server consumes
(send/receive) every byte transferred between peers.

# running

First, copy the `server.sh` and `prefix` files somewhere.

Every user that wants to use the `noshare` will have to supply you with
an ssh pubkey. Put all of those separate pubkey files into a directory named `keys`
next to the `server.sh` script. After you do this it'll look something like:


```
- server.sh
- prefix
- keys/
   +---- user1.pub
   +---- user2.pub
   +---- whatever.pub
```

Then run:

```
./server.sh
```

## config

There are a few things that can be customized via environment
variables or by hacking/hard coding the `server.sh` script:

* `NOSHARE_PORT` - the incoming port for clients to connect to (default = 20666)
* `NOSHARE_KEYS_DIR` - where the directory of ssh pubkeys are found (default = `keys` dir peer of `server.sh`)

# caveats / improvements

* the modified keys dir is not configurable and requires the `KEYS_DIR` to be writable
  by the user starting the server.
* the key prefix file `prefix` has to be in the same dir as the `server.sh` script.
