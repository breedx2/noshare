import os
import sys
import subprocess
from configparser import ConfigParser
# import threading
import asyncio
import random
import uuid
# import socketserver
import re

# 4 commands to build:
# * help
# * config (write ~/.noshare)
# * offser <file>
# * receive <key>

# key could be base64.b64encode(uuid.uuid4().bytes)

DEFAULT_NOSHARE_PORT = 20666
DEFAULT_SSHKEY = '~/.ssh/id_rsa'

# class OfferServerHandler(socketserver.StreamRequestHandler):
#     def handle(self):
#         print("HANDLE CALLED IN HANDLER OMG OMG {}".format(self.server.secret_id))
#         # data = str(self.request.recv(1024), 'ascii')
#         id = self.rfile.readline().strip()
#         print("Client requests: {}".format(id))
#         if self.server.secret_id != id:
#             self.wfile.write('no\n')
#             self.connection.close()
#             return
#         self.wfile.write('{}\n{}\n'.format(self.config.file, self.config.file_size))

        # cur_thread = threading.current_thread()
        # response = bytes("{}: {}".format(cur_thread.name, data), 'ascii')
        # self.request.sendall(response)

class FileSender:
    def __init__(self, config):
        self.config = config
        self.server = None
        self.offer_id = ''
    async def send(self, reader, writer):
        print('New client connected.')
        id = await reader.readline()
        id = id.decode('utf-8').rstrip()
        print("client requests: {}".format(id))
        if self.offer_id != id:
            print("INVALID OFFER!")
            writer.write('no\n'.encode())
            self.server.close()
            return
        writer.write('{}\n{}\n'.format(self.config.file, self.config.file_size).encode())

class FileReceiver:
    def __init__(self, id, local_port):
        self.id = id
        self.local_port = local_port
    async def receive(self):
        reader,writer = await self.connect()
        writer.write("{}\n".format(self.id).encode())

        line = await reader.readline()
        line = line.decode('utf-8').rstrip()
        if line == 'no':
            print('offer was refused :(')
            return
        file = line
        size = await reader.readline()
        size = size.decode('utf-8').rstrip()
        print('I think the file is {} at size {}'.format(file, size))

    async def connect(self):
        import time
        tries = 50
        while tries > 0:
            try:
                reader, writer = await asyncio.open_connection('127.0.0.1', self.local_port)
                return reader,writer
            except:
                tries = tries - 1
                time.sleep(0.1)

class Tunnel:
    def __init__(self, config):
        self.config = config
    async def offer(self):
        # TODO: Validate config.file exists/readable before continuing
        print("Setting up local server listener...")

        sender = FileSender(config)

        # async def new_connection(reader, writer):
        #     print('got new connection')

        server = await asyncio.start_server(sender.send, '127.0.0.1', 0, backlog=1)
        sender.server = server
        ip, port = server.sockets[0].getsockname()
        print("Local ephemeral port is {}".format(port))

        remote_port = self._random_port()
        sender.offer_id = "{}:{}".format(remote_port, uuid.uuid4().hex)
        print("Setting up ssh tunnel...")
        print("offer id: {}".format(sender.offer_id))
        ssh = Ssh(config, port, remote_port)
        ssh.connect()
        await server.serve_forever()
        # ssh.wait()

    async def receive(self, id):
        print("Setting up ssh tunnel...")
        local_port = self._random_port()
        remote_port = re.sub(r':.*', '', id)
        ssh = Ssh(config, local_port, remote_port, offer_side=False)
        ssh.connect()
        print("DEBUG: tunnel local {} to remote {}".format(local_port, remote_port))
        receiver = FileReceiver(id, local_port)
        await receiver.receive()
        # ssh.wait() # DEBUG ONLY

    def _random_port(self):
        return random.randint(1025, 65000)


class Ssh:
    def __init__(self, config, local_port, remote_port, offer_side = True):
        self.config = config
        self.local_port = local_port
        self.remote_port = remote_port
        self.offer_side = offer_side
        self.child = None
    def connect(self):
        tunnel_flag = '-R' if self.offer_side else '-L'
        tunnel_arg = self._make_tunnel_arg()
        cmd = [
            "ssh", "-p", self.config.remotePort, "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-N", "-q",
            tunnel_flag, tunnel_arg,
            "-i", self.config.keyfile,
            "app@" + self.config.remoteHost
        ]
        self.child = subprocess.Popen(cmd)
        print("ssh tunnel established")

    def wait(self):
        print("waiting for child to exit")
        self.child.wait()
        print("child finished? exit code = {}".format(self.child.returncode))
        if self.child.returncode != 0:
            # todo: probably check that we didn't complete?
            print("ssh tunnel failed - is the share down (lolololo)?")

    def _make_tunnel_arg(self):
        if self.offer_side:
            return "{}:localhost:{}".format(self.remote_port, self.local_port)
        return "{}:localhost:{}".format(self.local_port, self.remote_port)

class Config:
    def __init__(self, remoteHost, remotePort = DEFAULT_NOSHARE_PORT, keyfile = DEFAULT_SSHKEY):
        self.remoteHost = remoteHost
        self.remotePort = remotePort
        self.keyfile = keyfile

    @staticmethod
    def exists():
        return os.path.exists(Config.filename())

    @staticmethod
    def filename():
        return os.path.expanduser('~/.noshare')

    @staticmethod
    def prompt():
        host = input('host: ')
        if not host: raise Exception('host is required')
        port = input('port [{}]: '.format(DEFAULT_NOSHARE_PORT))
        if not port: port = DEFAULT_NOSHARE_PORT
        keyfile = input('ssh key file [{}]: '.format(DEFAULT_SSHKEY))
        if not keyfile: keyfile = DEFAULT_SSHKEY
        return Config(host, port, keyfile)

    @staticmethod
    def read():
        config = ConfigParser()
        config.read(Config.filename())
        ns = config['noshare']
        return Config(ns['host'], ns['port'], ns['keyfile'])

    def write(self):
        config = ConfigParser()
        config['noshare'] = {
            "host": self.remoteHost, "port": self.remotePort, "keyfile": self.keyfile
        }
        with open(Config.filename(), 'w') as out:
            config.write(out)

def usage():
    print("\n\u001b[36m noshare \033[0musage: \n")
    print(" noshare help            : show this help")
    print(" noshare config          : configure the program")
    print(" noshare offer <file>    : offer a single file")
    print(" noshare receive <id>    : receive a file by id\n")
    sys.exit()


# ---- begin main ----

if len(sys.argv) == 1:
    usage()

if len(sys.argv) > 1:
    cmd = sys.argv[1].lstrip('-')

arg = None
if len(sys.argv) > 2:
    arg = sys.argv[2].lstrip('-')

if (cmd == 'help') or (cmd == 'h'):
    usage()

if cmd == 'config' or not Config.exists():
    if Config.exists():
        print("Warning: config exists -- this will overwrite it.")
    config = Config.prompt()
    config.write()
    print("Config saved to {}".format(Config.filename()))
    usage()

config = None
if cmd == 'offer' or cmd == 'receive':
    if len(sys.argv) <= 2:
        usage()
    if(Config.exists()):
        config = Config.read()
        print("Config read from {}".format(Config.filename()))
    else:
        print("Not yet configured. Let's get you set up.\n")
        config = Config.prompt()
        config.write()
        print("Config saved to {}".format(Config.filename()))
        usage()

if cmd == 'offer':
    config.file = arg
    config.file_size = os.path.getsize(config.file)
    tunnel = Tunnel(config)
    asyncio.run(tunnel.offer())
elif cmd == 'receive':
    if len(sys.argv) <= 2:
        usage()
    tunnel = Tunnel(config)
    asyncio.run(tunnel.receive(arg))
