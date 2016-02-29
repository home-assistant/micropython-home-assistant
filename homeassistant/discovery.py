import ujson
import usocket

from . import HomeAssistant

MCAST_IP = "224.0.0.123"
MCAST_PORT = 38123
TIMEOUT = 5

QUERY = 'Home Assistants Assemble!'.encode('utf-8')


def get_instance(api_password=None):
    info = scan()
    return HomeAssistant(info.get('host'),
                         info.get('api_password', api_password))


def scan():
    sock = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)
    try:
        if hasattr(sock, 'settimeout'):
            sock.settimeout(TIMEOUT)

        addrs = usocket.getaddrinfo(MCAST_IP, MCAST_PORT, usocket.AF_INET,
                                    usocket.SOCK_DGRAM)
        sock.sendto(QUERY, addrs[0][4])
        data, addr = sock.recvfrom(1024)
        return ujson.loads(data.decode('utf-8'))
    finally:
        sock.close()
