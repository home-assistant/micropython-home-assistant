class Sensor(object):
    """Sensor class for Home Assistant.

    Optionally allows a report_delta parameter to only report if current value
    differs more than `report_delta` from previously reported value.
    """

    def __init__(self, entity_id, value_func, unit_of_measurement,
                 report_delta=None):
        self._entity_id = entity_id
        self._value_func = value_func
        self._value = None
        self._report_delta = report_delta
        self._attributes = {'unit_of_measurement': unit_of_measurement}

    def report(self, hass):
        value = self._value_func()

        do_report = (self._value is None or self._report_delta is None or
                     abs(value - self._value) > self._report_delta)

        if not do_report:
            return

        hass.set_state(self.entity_id, value, self._attributes)
        self._value = value
