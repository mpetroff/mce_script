import sys
import socket
import time
import array
import numpy
import errno
import json

def send_dahi(sock, data):
    n = len(data)
    pre = 'dahi' + array.array('i', [n]).tostring()
    # Great
    data = pre + data
    n = 0
    while n < len(data):
        try:
            dn = sock.send(data[n:])
            if dn == 0:
                return False, 'fail'
            n += dn
        except socket.error as err:
            return False, err
    return True, 0

def recv_wrapped(sock, n):
    """
    Attempt to read n bytes from sock.  Returns tuple
       (ok, n_read, data)
    """
    ok, data = True, ''
    
    try:
        data = sock.recv(n)
        if data == '':
            ok = False
    except socket.timeout as err:
        return True, 0, ''
    except socket.error as err:
        if err.args[0] != errno.EAGAIN:
            ok = False
    return ok, len(data), data
    
def recv_dahi(sock, block=True):
    """
    Returns None on error; string otherwise.

    Return string will be '', or a complete and valid dahi packet.
    """
    n_read = 0
    header = False
    data = ''
    n = 8
    while True:
        ok, _n, new_data = recv_wrapped(sock, n-n_read)
        if not ok:
            return None
        if _n == 0:
            if n_read == 0 and not block:
                return ''
            time.sleep(.01)
            continue
        n_read += _n
        data += new_data
        if n_read == n:
            if header:
                return data[8:]
            else:
                if data[:4] != 'dahi':
                    return ''
                # Payload size
                n += array.array('i', data[4:])[0]
                header = True
            
def encode_json(d):
    return 'json\x00' + json.dumps(d)

def decode_json(d):
    a, b = d.split('\x00')
    if not a == 'json':
        raise ValueError, "does not appear to be a jsondict"
    return json.loads(b)


def encode_strings(ss):
    return '\x00'.join(ss) + '\x00'

def decode_strings(s, n=-1):
    if n == -1:
        return s.split('\x00')[:-1]
    return s.split('\x00', n)

def decode_address(addr):
    if isinstance(addr, basestring):
        host, port = addr.split(':')
        port = int(port)
        return (host, port)
    return addr

#
# New encapsulation
#

class packetFormatV1:
    class addressBlock:
        def __init__(self, type='', name='', source='', dest=''):
            self.type = type
            self.name = name
            self.source = source
            self.dest = dest
        @classmethod
        def decode(cls, packet):
            t, n, s, d = packet.split('\x00')[:-1]
            self = cls(t,n,s,d)
            return self
        def encode(self):
            t, n, s, d = self.type, self.name, self.source, self.dest
            return ''.join([x+'\x00' for x in [t,n,s,d]])
    class payloadBlock:
        @classmethod
        def decode(cls, packet):
            n1, n2 = array.array('i', packet[:8])
            d1, d2 = packet[8:8+n1], packet[8+n1:8+n1+n2]
            self = cls()
            if n1 == 0:
                self.json_data = None
            else:
                self.json_data = json.loads(d1)
            self.bin_data = d2
            return self

        @classmethod
        def encode(cls, json_data=None, bin_data=None):
            n1, n2, d1, d2 = 0, 0, '', ''
            if json_data != None:
                d1 = json.dumps(json_data)
                n1 = len(d1)
            if bin_data != None:
                d2 = bin_data
                n2 = len(d2)
            payload = array.array('i', [n1, n2]).tostring() + d1 + d2
            return payload
            
    @classmethod
    def encode_packet(cls, stream_type, stream_name, source_client, dest_client,
                      json_data=None, bin_data=None,
                      dahi_header=False):
        # Validate
        ## ...
        # Form addressing
        address = cls.addressBlock(stream_type, stream_name,
                                   source_client, dest_client).encode()
        address = array.array('i', [len(address)]).tostring() + address
        # Form payload packet
        payload = cls.payloadBlock.encode(json_data, bin_data)
        # Encapuslate
        if dahi_header:
            header = 'dahi' + \
                array.array('i', [len(address) + len(payload)]).tostring()
        else:
            header = ''
        # These encodes are necessary because unicode doesn't like ex ascii?
        X = header.encode() + address.encode() + payload
        return True, X

    @classmethod
    def decode_packet(cls, data, dahi_header=False):
        # Pre-amble
        if dahi_header:
            code, size = data[:4], array.array('i', data[4:8])[0]
            data = data[8:]
        # Validate...
        ## ...
        # Addressing
        addr_len = array.array('i', data[0:4])[0]
        addr_data = data[4:4+addr_len]
        # Payload
        payload = data[4+addr_len:]
        # Great.
        return True, cls.addressBlock.decode(addr_data), \
            cls.payloadBlock.decode(payload)
