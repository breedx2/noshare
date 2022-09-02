from configparser import ConfigParser
from datetime import datetime
import asyncio
import os
import random
import re
import subprocess
import sys
import tempfile
import uuid
import socket

DEFAULT_NOSHARE_PORT = 20666
DEFAULT_SSHKEY = '~/.ssh/id_rsa'
CHUNK_LEN = 64*1024

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
        line = await reader.readline()
        line = line.decode('utf-8').rstrip()
        if 'done' == line:
            print('remote confirms complete.')
        else:
            print('remote did not confirm. something is foul.')
        writer.write('done\n'.encode())
        await writer.drain()
        self.server.close()

    async def do_handshake(self, reader, writer):
        id = await reader.readline()
        id = id.decode('utf-8').rstrip()
        print("client requests: {}".format(id))
        if self.offer_id != id:
            print("INVALID OFFER!")
            writer.write('no\n'.encode())
            await writer.drain()
            return False
        file_and_size = '{}\n{}\n'.format(os.path.basename(self.config.file), self.config.file_size)
        # TODO: Send file hash so remote can validate...or include hash in id!
        writer.write(file_and_size.encode())
        ack = await reader.readline()
        ack = ack.decode('utf-8').rstrip()
        if ack != 'ok':
            print('remote side refused.')
            return False
        return True

    async def send_file(self, reader, writer):
        with open(self.config.file, "rb") as infile:
            progress = Progress(self.config.file_size)
            remaining = self.config.file_size
            while True:
                await writer.drain()
                buff = infile.read(CHUNK_LEN)
                if len(buff) == 0:
                    break
                writer.write(buff)
                remaining -= len(buff)
                progress.show(remaining)
            progress.show(0, force=True)
            print('\u001b[32;1mtransfer complete!\033[0m')

class FileReceiver:
    def __init__(self, id, local_port):
        self.id = id
        self.local_port = local_port
    async def receive(self):
        reader,writer = await self.connect()
        file,size = await self.handshake(reader, writer)
        if not file or not size: return
        if not self._confirm('Download {} ({})'.format(file, sized(size)), writer):
            return
        if os.path.exists(file):
            if not self._confirm('\u001b[31;1m* FILE EXISTS *\033[0m -- are you very sure you want to overwrite', writer, 'n'):
                return

        print('downloading...')
        writer.write('ok\n'.encode())
        await writer.drain()

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
        writer.write('done\n'.encode());
        await writer.drain()
        await reader.readline()

    def _confirm(self, prefix, writer, default = 'y'):
        yn = input('{}? [{}] '.format(prefix, default)) or default
        if yn.lower() == 'y':
            return True
        print('refused.')
        writer.write('no\n'.encode())
        return False

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

    async def handshake(self, reader, writer):
        writer.write("{}\n".format(self.id).encode())

        try:
            line = await reader.readline()
        except ConnectionResetError as e:
            print("ERROR: offer is invalid or connection couldn't be established")
            return None,None

        line = line.decode('utf-8').rstrip()
        if line == 'no':
            print('ERROR: offer was refused :(')
            return None,None
        file = os.path.basename(line)
        size = await reader.readline()

        if not file or not size:
            print('ERROR: invalid remote shit')
            return None,None

        size = int(size.decode('utf-8').rstrip())
        return file,size

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
        str = " {} {} [{}] {} {}      ".format(throb, percent, rate_str, size_bit, eta)
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
        if remaining == 0:
            eta_s = datetime.now().timestamp() - self.start_time
        hours = int(eta_s / (60*60))
        rest = eta_s - 60*60*hours
        min = int(rest / 60)
        sec = int(rest - 60 * min)
        prefix = 'eta' if remaining > 0 else 'took'
        str = "{:02d}:{:02d}:{:02d}".format(hours, min, sec)
        return "{} \u001b[37;1m{}\033[0m".format(prefix, str)


class Tunnel:
    def __init__(self, config):
        self.config = config
    async def offer(self):
        print("Setting up local server listener...")

        sender = FileSender(config)

        server = await asyncio.start_server(sender.send, '127.0.0.1', 0, backlog=1)
        sender.server = server
        ip, port = server.sockets[0].getsockname()
        print("Local ephemeral port is {}".format(port))

        remote_port = self._random_port()
        sender.offer_id = "{}:{}".format(remote_port, uuid.uuid4().hex)
        print("Setting up ssh tunnel...")
        ssh = Ssh(config, port, remote_port)
        ssh.connect()
        print("offer id: \u001b[32;1m{}\033[0m".format(sender.offer_id))
        try:
            await server.serve_forever()
        except asyncio.exceptions.CancelledError:
            print('exiting.')
        self._cleanup(ssh)

    async def receive(self, id):
        print("Setting up ssh tunnel...")
        local_port = self._random_port()
        remote_port = re.sub(r':.*', '', id)
        ssh = Ssh(config, local_port, remote_port, offer_side=False)
        ssh.connect()
        # print("DEBUG: tunnel local {} to remote {}".format(local_port, remote_port))
        receiver = FileReceiver(id, local_port)
        await receiver.receive()
        self._cleanup(ssh)

    def _cleanup(self, ssh):
        ssh.close()
        ssh.wait(quiet=True)
        if config.tempKnownHostsFile:
            os.remove(config.tempKnownHostsFile)

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
        if self.config.tempKnownHostsFile:
            hosts_file = config.tempKnownHostsFile
            check_host_key = 'yes'
        else:
            hosts_file = '/dev/null'
            check_host_key = 'no'
        cmd = [
            "ssh", "-p", str(self.config.remotePort), 
            "-o", f"StrictHostKeyChecking={check_host_key}",
            "-o", f"UserKnownHostsFile={hosts_file}",
            "-N", #"-q",
            tunnel_flag, tunnel_arg,
            "-i", self.config.keyfile,
            "app@" + self.config.remoteHost
        ]
        # print(cmd)
        self.child = subprocess.Popen(cmd, 
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, 
            universal_newlines=True)
        rc = self._verify_connection()
        if not rc:
            raise Exception('Error opening ssh tunnel. Aborting.')
        # rc = self.child.poll()
        # print(rc)
        print("ssh tunnel established (pid={})".format(self.child.pid))


    def _verify_connection(self):
        try:
            out,errs = self.child.communicate(timeout=3)
            if errs:
                print(errs)
                return False
        except subprocess.TimeoutExpired:
            print('timeout expired (probably a good thing!)')    
            rc = self.child.poll()
            if rc:
                return False
        return True
    # def _verify_connection(self):
    #     if self.offer_side:
    #         sleep(2) 
    #         sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #         sock.settimeout(2)
    #         result = sock.connect_ex(('127.0.0.1', self.local_port))
    #         if result == 0:
    #             print('port OPEN')
    #         else:
    #             print('port CLOSED, connect_ex returned: '+str(result))
    #         sock.close()

    def close(self):
        self.child.terminate()

    def wait(self, quiet=False):
        if not quiet:
            print("waiting for child to exit")
        self.child.wait()
        if not quiet:
            print("child finished? exit code = {}".format(self.child.returncode))
        if self.child.returncode != 0:
            # todo: probably check that we didn't complete?
            print("ssh tunnel failed - is the share down (lolololo)?")

    def _make_tunnel_arg(self):
        if self.offer_side:
            return "{}:localhost:{}".format(self.remote_port, self.local_port)
        return "{}:localhost:{}".format(self.local_port, self.remote_port)

class Config:
    def __init__(self, remoteHost, remotePort = DEFAULT_NOSHARE_PORT, keyfile = DEFAULT_SSHKEY, 
                fingerprint = None, tempKnownHostsFile = None):
        self.remoteHost = remoteHost
        self.remotePort = remotePort
        self.keyfile = keyfile
        self.fingerprint = fingerprint
        self.tempKnownHostsFile = tempKnownHostsFile

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
        fingerprint = input('ssh host fingerprint [None]: ')
        return Config(host, port, keyfile, fingerprint)

    @staticmethod
    def read():
        config = ConfigParser()
        config.read(Config.filename())
        ns = config['noshare']
        fingerprint = ns.get('fingerprint')
        if fingerprint:
            print(f'\u001b[32mUsing host fingerprint {fingerprint}\033[0m')
            tempKnownHostsFile = Config._write_temp_known_hosts(ns['host'], ns['port'], fingerprint)
        else:
            print('\u001b[31m** \u001b[33mWarning: No server fingerprint found in config file.\033[0m')
            print('\u001b[31m** \u001b[33mVulnerable to MITM/eavesdropping.\033[0m')
            tempKnownHostsFile = None
        return Config(ns['host'], ns['port'], ns['keyfile'], fingerprint, tempKnownHostsFile)

    @staticmethod
    def _write_temp_known_hosts(host, port, fingerprint):
        handle, filename = tempfile.mkstemp(prefix='noshare_')
        with os.fdopen(handle, 'w') as out:
            out.write(f'[{host}]:{port} {fingerprint}\n')
        return filename

    def write(self):
        config = ConfigParser()
        config['noshare'] = {
            'host': self.remoteHost, 'port': self.remotePort, 'keyfile': self.keyfile, 
            'fingerprint': self.fingerprint
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
    print(" noshare help      : show this help")
    print(" noshare config    : configure the program")
    print(" noshare <file>    : offer a single file")
    print(" noshare <id>      : receive a file by id\n")
    sys.exit()

def match_id(str):
    pass

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

if cmd == 'config':
    if Config.exists():
        print("Warning: config exists -- this will overwrite it.")
    config = Config.prompt()
    config.write()
    print("Config saved to {}".format(Config.filename()))
    usage()

arg = cmd
config = None
if(Config.exists()):
    config = Config.read()
    print("Config read from {}".format(Config.filename()))
else:
    print("\n\u001b[33;1mNot yet configured. Let's get you set up.\033[0m\n")
    config = Config.prompt()
    config.write()
    config = Config.read()
    print("Config saved to {}".format(Config.filename()))

# If the argument exists as a file, assume offer
if os.path.exists(arg):
    config.file = arg
    config.file_size = os.path.getsize(config.file)
    tunnel = Tunnel(config)
    asyncio.run(tunnel.offer())
elif re.match(r'^\d+:[0-9,a-z]{32}$', arg): # presumed receive id
    tunnel = Tunnel(config)
    asyncio.run(tunnel.receive(arg))
else:
    print('invalid offer id or no such file')
    usage()
    sys.exit(-1)
