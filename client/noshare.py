import os
import sys
import subprocess
from configparser import ConfigParser
import threading
import random
import uuid
import socketserver

# 4 commands to build:
# * help
# * config (write ~/.noshare)
# * offser <file>
# * receive <key>

# key could be base64.b64encode(uuid.uuid4().bytes)

DEFAULT_NOSHARE_PORT = 20666
DEFAULT_SSHKEY = '~/.ssh/id_rsa'

class OfferServerHandler(socketserver.BaseRequestHandler):
    def handle(self):
        print("HANDLE CALLED IN HANDLER OMG OMG {}".format(self.server.secret_id))
        # data = str(self.request.recv(1024), 'ascii')
        # cur_thread = threading.current_thread()
        # response = bytes("{}: {}".format(cur_thread.name, data), 'ascii')
        # self.request.sendall(response)

class Tunnel:
    def __init__(self, config):
        self.config = config
    def offer(self):
        # TODO: Validate config.file exists/readable before continuing
        print("Setting up local server listener...")
        with socketserver.TCPServer(("127.0.0.1", 0), OfferServerHandler) as server:
            ip, port = server.server_address
            print("Local ephemeral port is {}".format(port))
            server_thread = threading.Thread(target=server.handle_request)
            # Exit the server thread when the main thread terminates
            server_thread.daemon = True
            server_thread.start()
            print("Setting up ssh tunnel...")
            remote_port = random.randint(1025, 65000)
            server.secret_id = "{}:{}".format(remote_port, uuid.uuid4().hex)
            ssh = Ssh(config, port, remote_port)
            ssh.connect()
            print("offer id: {}".format(server.secret_id))
            ssh.wait()

class Ssh:
    def __init__(self, config, local_port, remote_port):
        self.config = config
        self.local_port = local_port
        self.remote_port = remote_port
        self.child = None
    def connect(self):
        cmd = [
            "ssh", "-p", self.config.remotePort, "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-N", "-q",
            # "-L", "6666:localhost:2222",
            "-R", "{}:localhost:{}".format(self.remote_port, self.local_port),
            "-i", self.config.keyfile,
            "app@" + self.config.remoteHost
        ]
        print(cmd)
        self.child = subprocess.Popen(cmd)
        print(self.child)
        # print("result of call = {}".format(rc))
        print("ssh tunnel established")

    def wait(self):
        print("waiting for child to exit")
        self.child.wait()
        print("child finished? exit code = {}".format(self.child.returncode))
        if self.child.returncode != 0:
            # todo: probably check that we didn't complete?
            print("ssh tunnel failed - is the share down (lolololo)?")

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
    print(" noshare receive <id> : receive a file by id\n")
    sys.exit()

# parser = argparse.ArgumentParser(description='noshare tunnels a file with a peer over ssh')
# parser.add_argument('command', metavar='CMD', nargs=1, choices=['config', 'offer', 'receive'])
# parser.add_argument('arg', metavar='arg', nargs=1, choices=['config', 'offer', 'receive'])

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
    tunnel = Tunnel(config)
    tunnel.offer()
elif cmd == 'receive':
    if len(sys.argv) <= 2:
        usage()
    print("not ready yet")
