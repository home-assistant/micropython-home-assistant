# from http_client import SUPPORT_TIMEOUT, request
import time
import usocket
import ujson
try:
    import ussl
except ImportError:
    ussl = None

SUPPORT_SSL = ussl is not None
SUPPORT_TIMEOUT = hasattr(usocket.socket, 'settimeout')
CONTENT_TYPE_JSON = "application/json"


class Response(object):
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content

    @property
    def text(self, encoding='utf-8'):
        return self.content.decode(encoding)

    def json(self):
        return ujson.loads(self.content)

    def raise_for_status(self):
        if 400 <= self.status_code < 500:
            raise OSError('Client error: %s' % self.status_code)
        if 500 <= self.status_code < 600:
            raise OSError('Server error: %s' % self.status_code)


# Adapted from upip
def request(method, url, json=None, timeout=None, headers=None,
            skip_body=False):
    urlparts = url.split('/', 3)
    proto = urlparts[0]
    host = urlparts[2]
    urlpath = '' if len(urlparts) < 4 else urlparts[3]

    if proto == 'http:':
        port = 80
    elif proto == 'https:':
        port = 443
    else:
        raise OSError('Unsupported protocol: %s' % proto[:-1])

    if ':' in host:
        host, port = host.split(':')
        port = int(port)

    if json is not None:
        content = ujson.dumps(json)
        content_type = CONTENT_TYPE_JSON
    else:
        content = None

    ai = usocket.getaddrinfo(host, port)
    addr = ai[0][4]

    sock = usocket.socket()

    if timeout is not None:
        assert SUPPORT_TIMEOUT, 'Socket does not support timeout'
        sock.settimeout(timeout)

    try:
        sock.connect(addr)

        if proto == 'https:':
            assert SUPPORT_SSL, 'HTTPS not supported: could not find ussl'
            sock = ussl.wrap_socket(sock)

        # MicroPython rawsocket module supports file interface directly
        sock.write('%s /%s HTTP/1.0\r\nHost: %s\r\n' % (method, urlpath, host))

        if headers is not None:
            for header in headers.items():
                sock.write('%s: %s\r\n' % header)

        if content is not None:
            sock.write('content-length: %s\r\n' % len(content))
            sock.write('content-type: %s\r\n' % content_type)
            sock.write('\r\n')
            sock.write(content)
        else:
            sock.write('\r\n')

        l = sock.readline()
        protover, status, msg = l.split(None, 2)

        # Skip headers
        while sock.readline() != b'\r\n':
            pass

        content = b''
        # Needed for first alpha MicroPython + HA
        time.sleep_ms(10)

        if not skip_body:
            while 1:
                l = sock.read(1024)
                if not l:
                    break
                content += l

        return Response(int(status), content)
    finally:
        sock.close()
# END http_client

METHOD_GET = 0
METHOD_POST = 1

DEFAULT_TIMEOUT = 5


class HomeAssistant(object):
    def __init__(self, base_url, api_password=None, timeout=None):
        assert base_url[-1] != '/', 'Host should not end with a /'
        self._base_url = base_url + '/api/'

        if api_password is None:
            self._headers = None
        else:
            self._headers = {'X-HA-access': api_password}

        if timeout is None and SUPPORT_TIMEOUT:
            timeout = DEFAULT_TIMEOUT
        elif timeout and not SUPPORT_TIMEOUT:
            raise OSError('Timeout is not supported on your platform')

        self._timeout = timeout

    def fire_event(self, event_type, data=None):
        res = self._api(METHOD_POST, 'events/' + event_type, data, True)
        res.raise_for_status()

    def states(self):
        res = self._api(METHOD_GET, 'states')
        res.raise_for_status()
        return res.json()

    def get_state(self, entity_id):
        res = self._api(METHOD_GET, 'states/' + entity_id)
        res.raise_for_status()
        return res.json()

    def set_state(self, entity_id, new_state, attributes=None,
                  parse_response=False):
        data = {'state': new_state}

        if attributes is not None:
            data['attributes'] = attributes

        res = self._api(METHOD_POST, 'states/' + entity_id, data)
        res.raise_for_status()

        if parse_response:
            return res.json()

        return None

    def is_state(self, entity_id, state):
        try:
            return self.get_state(entity_id)['state'] == state
        except OSError:
            return False

    def call_service(self, domain, service, service_data=None,
                     parse_response=False):

        res = self._api(METHOD_POST, 'services/' + domain + '/' + service,
                        service_data, not parse_response)
        res.raise_for_status()

        if parse_response:
            return res.json()

        return None

    def _api(self, method, path, data=None, ignore_content=False):
        url = self._base_url + path
        if method == METHOD_GET:
            return request(
                'GET', url, timeout=self._timeout, headers=self._headers)
        elif method == METHOD_POST:
            return request(
                'POST', url, json=data, timeout=self._timeout,
                headers=self._headers)
