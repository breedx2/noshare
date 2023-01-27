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


# setup

First, copy the `server.sh` and `prefix` files somewhere.

```
$ git clone https://github.com/breedx2/noshare.git
$ mkdir server
$ cp noshare/server.sh server/
$ cp noshare/prefix server/
$ cd server
```

## user ssh keys

Every user that wants to use the `noshare` will have to supply you with
an ssh pubkey. Put all of those separate pubkey files into a directory named `keys`
next to the `server.sh` script. 

```
$ mkdir keys
$ cp /users/user1.pub keys/
$ cp /users/user2.pub keys/
...
$ cp /users/whatever.pub keys/
```

You can add keys later, but will need to restart the server after each addition.

## hostkeys

This step is optional, but **highly encouraged**. If you do not specify hostkeys,
you users will need to reconfigure the server fingerprint every time the 
docker container restarts, or will need to run without host key checking
enabled (this leaves them vulnerable to MITM attacks).

Every ssh server has a set of host keys that are used to securely identify
a server instance. If you do not provide your own, new ones will be created
each time the container is started. Let's create some.

```
$ mkdir -p /tmp/keys/ssh/etc
$ ssh-keygen -A -f /tmp/keys
$ mkdir ssh_host_keys
$ cp /tmp/keys/ssh/etc/* ssh_host_keys/
$ rm -rf /tmp/keys
```

By default, `server.sh` will use the `ssh_host_keys` dir in the same directory
as the `server.sh` script itself, but you can override it by setting the 
`NOSHARE_HOST_KEYS_DIR` env var.


# running

Once your setup is complete, you should have a directory that looks
similar to this:

```
- server.sh
- prefix
- keys/
   +---- user1.pub
   +---- user2.pub
   +---- whatever.pub
- ssh_host_keys/
   +---- ssh_host_ed25519_key
   +---- ssh_host_ed25519_key.pub
   +---- (others)
```

Now that your directory is set up, you can just run the script:

```
$ ./server.sh
```

Note: This script does some preprocessing of the user ssh keys to restrict
some settings and to allow a tunnel to be created to localhost only.

## config

There are a few things that can be customized via environment
variables or by hacking/hard coding the `server.sh` script:

* `NOSHARE_PORT` - the incoming port for clients to connect to (default = 20666)
* `NOSHARE_KEYS_DIR` - the directory of user ssh pubkeys (default = `keys` dir peer of `server.sh`)
* `NOSHARE_HOST_KEYS_DIR` - the directory of server keys (default = `ssh_host_keys` in dir peer of `server.sh` or recreated on container start) 

# your users

There are 2 or 3 things then to give to your users:

* host 
* port
* ssh fingerprint (optional)

## server ssh fingerprint

The ssh fingerprint helps protect against "man in the middle" (MITM) attacks.
Unless you have provided the `NOSHARE_HOST_KEYS_DIR` env var or have the `ssh_host_keys`
directory populated with keys, new server keys will be generated each time you
start the docker container. This is not ideal.

The `ssh-keyscan` tool is useful for getting server fingerprints.

Simply run:
```
ssh-keyscan -p <port> -t ssh-ed25519 <host>
```

Or to automate the fetching of the value:
```
ssh-keyscan -p <port> -t ssh-ed25519 <host> 2>&1 | tail -1 | awk '{print $2 " " $3}'
```

# caveats / improvements

* the modified keys dir is not configurable and requires the `KEYS_DIR` to be writable
  by the user starting the server.
* the key prefix file `prefix` has to be in the same dir as the `server.sh` script.
