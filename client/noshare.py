import os
import sys
import subprocess
from configparser import ConfigParser
from datetime import datetime
import asyncio
import random
import uuid
import re

DEFAULT_NOSHARE_PORT = 20666
DEFAULT_SSHKEY = '~/.ssh/id_rsa'
CHUNK_LEN = 1024*1024
# CHUNK_LEN = 16*1024

class FileSender:
    def __init__(self, config):
        self.config = config
        self.server = None
        self.offer_id = ''
    async def send(self, reader, writer):
        print('New client connected.')
        handshake = await self.do_handshake(reader, writer)
        if not handshake:
            # TODO: Decide if we wanna close out....
            # self.server.close()
            return
        await self.send_file(reader, writer)


    async def do_handshake(self, reader, writer):
        id = await reader.readline()
        id = id.decode('utf-8').rstrip()
        print("client requests: {}".format(id))
        if self.offer_id != id:
            print("INVALID OFFER!")
            writer.write('no\n'.encode())
            return False
        file_and_size = '{}\n{}\n'.format(os.path.basename(self.config.file), self.config.file_size)
        # TODO: Send file hash so remote can validate...or include hash in id!
        writer.write(file_and_size.encode())
        ack = await reader.readline()
        ack = ack.decode('utf-8').rstrip()
        if ack != 'ok':
            print('remote side aborted.')
            return False
        return True

    async def send_file(self, reader, writer):
        with open(self.config.file, "rb") as infile:
            while True:
                await writer.drain()
                buff = infile.read(CHUNK_LEN)
                if len(buff) == 0:
                    break
                writer.write(buff)


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
        file = os.path.basename(line)
        size = await reader.readline()
        size = int(size.decode('utf-8').rstrip())
        # TODO: Warn about overwrite!
        yn = input('Download {} ({})? [y] '.format(file, sized(size)))
        if yn.lower() != 'y' and yn != '':
            print('refused.')
            writer.write('no\n'.encode())
            return
        print('downloading...')
        writer.write('ok\n'.encode())

        progress = Progress(size)
        remaining = size
        with open(file, "wb") as out:
            while remaining > 0:
                buff = await reader.read(CHUNK_LEN)
                if len(buff) > 0:
                    out.write(buff)
                remaining -= len(buff)
                progress.show(remaining)
        progress.show(0, force=True)
        print("saved {}".format(file))

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

class Progress:
    def __init__(self, size):
        self.size = size
        self.start_time = datetime.now().timestamp()
        self.last_display = 0.0
        self.spin = ['/', '-', '\\', '|']
        self.last_str = ''

    def show(self, remaining, force=False):
        now = datetime.now().timestamp()
        if not force and now - self.last_display < 0.5:
            return
        print(''.ljust(len(self.last_str), '\b'), end='', flush=True)

        elapsed = now - self.start_time
        transferred = self.size - remaining
        rate = transferred / elapsed
        rate_str = self.rate(rate)
        percent = self.percent(transferred)
        size_bit = self.size_bit(transferred)
        eta = self.eta(rate, remaining)
        throb = self.throb()
        str = " {} {} [{}] {} eta {}      ".format(throb, percent, rate_str, size_bit, eta)
        print(str, end='', flush=True)
        self.last_display = now
        self.last_str = str
        if remaining == 0: print('')

    def rate(self, rate):
        return "\u001b[31;1m{}/s\033[0m".format(sized(rate))

    def percent(self, transferred):
        p = transferred * 100.0 / self.size
        return "\u001b[33;1m{:3.1f}%\033[0m".format(p)

    def size_bit(self, transferred):
        a = "\u001b[36;1m{}\033[0m".format(sized(transferred))
        b = "\u001b[36;1m{}\033[0m".format(sized(self.size))
        inner = "{} of {}".format(a, b)
        return "\u001b[37;1m[\033[0m{}\u001b[37;1m]\033[0m".format(inner)

    def throb(self):
        self.spin.append(self.spin.pop(0))
        ch = self.spin[0]
        return " \u001b[31;1m{}\033[0m".format(ch)

    def eta(self, rate, remaining):
        eta_s = remaining/rate
        hours = int(eta_s / (60*60))
        rest = eta_s - 60*60*hours
        min = int(rest / 60)
        sec = int(rest - 60 * min)
        str = "{:02d}:{:02d}:{:02d}".format(hours, min, sec)
        return "\u001b[37;1m{}\033[0m".format(str)


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

def sized(size):
    if size < 1024: return "{:.1f} bytes".format(size)
    size /= 1024
    if size < 1024: return "{:.1f} kB".format(size)
    size /= 1024
    if size < 1024: return "{:.1f} MB".format(size)
    size /= 1024
    return "{:.1f} GB".format(size)

def usage():
    print("\n\u001b[36m noshare \033[0musage: \n")
    print(" noshare help            : show this help")
    print(" noshare config          : configure the program")
    print(" noshare offer <file>    : offer a single file")
    print(" noshare receive <id>    : receive a file by id\n")
    sys.exit()


# --------- begin main ----------

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
