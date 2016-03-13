# from http_client import SUPPORT_TIMEOUT, request
import usocket
import ujson
try:
    import ussl
    SUPPORT_SSL = True
except ImportError:
    ussl = None
    SUPPORT_SSL = False

SUPPORT_TIMEOUT = hasattr(usocket.socket, 'settimeout')
CONTENT_TYPE_JSON = 'application/json'


class Response(object):
    def __init__(self, status_code, raw):
        self.status_code = status_code
        self.raw = raw
        self._content = False
        self.encoding = 'utf-8'

    @property
    def content(self):
        if self._content is False:
            self._content = self.raw.read()
            self.raw.close()
            self.raw = None

        return self._content

    @property
    def text(self):
        content = self.content

        return str(content, self.encoding) if content else ''

    def close(self):
        if self.raw is not None:
            self._content = None
            self.raw.close()
            self.raw = None

    def json(self):
        return ujson.loads(self.text)

    def raise_for_status(self):
        if 400 <= self.status_code < 500:
            raise OSError('Client error: %s' % self.status_code)
        if 500 <= self.status_code < 600:
            raise OSError('Server error: %s' % self.status_code)


# Adapted from upip
def request(method, url, json=None, timeout=None, headers=None):
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

    sock.connect(addr)

    if proto == 'https:':
        assert SUPPORT_SSL, 'HTTPS not supported: could not find ussl'
        sock = ussl.wrap_socket(sock)

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

    return Response(int(status), sock)
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
        res = self._api(METHOD_POST, 'events/' + event_type, data)
        res.raise_for_status()
        res.close()

    def states(self):
        res = self._api(METHOD_GET, 'states')
        res.raise_for_status()
        data = res.json()
        res.close()
        return data

    def get_state(self, entity_id):
        res = self._api(METHOD_GET, 'states/' + entity_id)
        res.raise_for_status()
        data = res.json()
        res.close()
        return data

    def set_state(self, entity_id, new_state, attributes=None,
                  parse_response=False):
        data = {'state': new_state}

        if attributes is not None:
            data['attributes'] = attributes

        res = self._api(METHOD_POST, 'states/' + entity_id, data)
        res.raise_for_status()

        if not parse_response:
            res.close()
            return None

        data = res.json()
        res.close()
        return data

    def is_state(self, entity_id, state):
        try:
            return self.get_state(entity_id)['state'] == state
        except OSError:
            return False

    def call_service(self, domain, service, service_data=None,
                     parse_response=False):

        res = self._api(METHOD_POST, 'services/%s/%s' % (domain, service),
                        service_data)
        res.raise_for_status()

        if not parse_response:
            res.close()
            return None

        data = res.json()
        res.close()
        return data

    def _api(self, method, path, data=None):
        url = self._base_url + path
        if method == METHOD_GET:
            return request(
                'GET', url, timeout=self._timeout, headers=self._headers)
        elif method == METHOD_POST:
            return request(
                'POST', url, json=data, timeout=self._timeout,
                headers=self._headers)
