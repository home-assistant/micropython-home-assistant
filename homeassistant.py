import http_client

METHOD_GET = 0
METHOD_POST = 1

DEFAULT_TIMEOUT = 5


class HomeAssistant(object):
    def __init__(self, base_url, timeout=None):
        assert base_url[-1] != '/', 'Host should not end with a /'
        self._base_url = base_url + '/api/'

        if timeout is None and http_client.support_timeout():
            timeout = DEFAULT_TIMEOUT
        elif timeout and not http_client.support_timeout():
            raise OSError('Timeout is not supported on your platform')

        self._timeout = timeout

    def fire_event(self, event_type, data=None):
        res = self._api(METHOD_POST, 'events/' + event_type, data)
        res.raise_for_status()

    def states(self):
        res = self._api(METHOD_GET, 'states')
        res.raise_for_status()
        return res.json()

    def get_state(self, entity_id):
        res = self._api(METHOD_GET, 'states/' + entity_id)
        res.raise_for_status()
        return res.json()

    def set_state(self, entity_id, new_state, attributes=None):
        data = {'state': new_state}

        if attributes is not None:
            data['attributes'] = attributes

        res = self._api(METHOD_POST, 'states/' + entity_id, data)
        res.raise_for_status()
        return res.json()

    def is_state(self, entity_id, state):
        try:
            return self.get_state(entity_id)['state'] == state
        except OSError:
            return False

    def call_service(self, domain, service, service_data=None,
                     parse_response=False):

        res = self._api(METHOD_POST, 'services/' + domain + '/' + service,
                        service_data)
        res.raise_for_status()

        if parse_response:
            return res.json()

        return None

    def _api(self, method, path, data=None):
        url = self._base_url + path
        if method == METHOD_GET:
            return http_client.request('GET', url, timeout=self._timeout)
        elif method == METHOD_POST:
            return http_client.request('POST', url, json=data,
                                       timeout=self._timeout)
