# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from functools import wraps

import os
import sys
import binascii
from libcloud.utils.py3 import httplib

import socket
from datetime import datetime, timedelta
import time

from libcloud.common.exceptions import RateLimitReachedError

DEFAULT_TIMEOUT = 30
DEFAULT_SLEEP = 1
DEFAULT_BACKCOFF = 1
EXCEPTION_TYPES = (RateLimitReachedError, socket.error, socket.gaierror,
                   httplib.NotConnected, httplib.ImproperConnectionState)

__all__ = [
    'find',
    'get_driver',
    'set_driver',
    'merge_valid_keys',
    'get_new_obj',
    'str2dicts',
    'dict2str',
    'reverse_dict',
    'lowercase_keys',
    'get_secure_random_string',
    'retry',

    'ReprMixin'
]


def find(l, predicate):
    results = [x for x in l if predicate(x)]
    return results[0] if len(results) > 0 else None


def get_driver(drivers, provider):
    """
    Get a driver.

    :param drivers: Dictionary containing valid providers.
    :param provider: Id of provider to get driver
    :type provider: :class:`libcloud.types.Provider`
    """
    if provider in drivers:
        mod_name, driver_name = drivers[provider]
        _mod = __import__(mod_name, globals(), locals(), [driver_name])
        return getattr(_mod, driver_name)

    raise AttributeError('Provider %s does not exist' % (provider))


def set_driver(drivers, provider, module, klass):
    """
    Sets a driver.

    :param drivers: Dictionary to store providers.
    :param provider: Id of provider to set driver for
    :type provider: :class:`libcloud.types.Provider`
    :param module: The module which contains the driver
    :type module: L
    :param klass: The driver class name
    :type klass:
    """

    if provider in drivers:
        raise AttributeError('Provider %s already registered' % (provider))

    drivers[provider] = (module, klass)

    # Check if this driver is valid
    try:
        driver = get_driver(drivers, provider)
    except (ImportError, AttributeError):
        exp = sys.exc_info()[1]
        drivers.pop(provider)
        raise exp

    return driver


def merge_valid_keys(params, valid_keys, extra):
    """
    Merge valid keys from extra into params dictionary and return
    dictionary with keys which have been merged.

    Note: params is modified in place.
    """
    merged = {}
    if not extra:
        return merged

    for key in valid_keys:
        if key in extra:
            params[key] = extra[key]
            merged[key] = extra[key]

    return merged


def get_new_obj(obj, klass, attributes):
    """
    Pass attributes from the existing object 'obj' and attributes
    dictionary to a 'klass' constructor.
    Attributes from 'attributes' dictionary are only passed to the
    constructor if they are not None.
    """
    kwargs = {}
    for key, value in list(obj.__dict__.items()):
        if isinstance(value, dict):
            kwargs[key] = value.copy()
        elif isinstance(value, (tuple, list)):
            kwargs[key] = value[:]
        else:
            kwargs[key] = value

    for key, value in list(attributes.items()):
        if value is None:
            continue

        if isinstance(value, dict):
            kwargs_value = kwargs.get(key, {})
            for key1, value2 in list(value.items()):
                if value2 is None:
                    continue

                kwargs_value[key1] = value2
            kwargs[key] = kwargs_value
        else:
            kwargs[key] = value

    return klass(**kwargs)


def str2dicts(data):
    """
    Create a list of dictionaries from a whitespace and newline delimited text.

    For example, this:
    cpu 1100
    ram 640

    cpu 2200
    ram 1024

    becomes:
    [{'cpu': '1100', 'ram': '640'}, {'cpu': '2200', 'ram': '1024'}]
    """
    list_data = []
    list_data.append({})
    d = list_data[-1]

    lines = data.split('\n')
    for line in lines:
        line = line.strip()

        if not line:
            d = {}
            list_data.append(d)
            d = list_data[-1]
            continue

        whitespace = line.find(' ')

        if not whitespace:
            continue

        key = line[0:whitespace]
        value = line[whitespace + 1:]
        d.update({key: value})

    list_data = [val for val in list_data if val != {}]
    return list_data


def str2list(data):
    """
    Create a list of values from a whitespace and newline delimited text
    (keys are ignored).

    For example, this:
    ip 1.2.3.4
    ip 1.2.3.5
    ip 1.2.3.6

    becomes:
    ['1.2.3.4', '1.2.3.5', '1.2.3.6']
    """
    list_data = []

    for line in data.split('\n'):
        line = line.strip()

        if not line:
            continue

        try:
            splitted = line.split(' ')
            # key = splitted[0]
            value = splitted[1]
        except Exception:
            continue

        list_data.append(value)

    return list_data


def dict2str(data):
    """
    Create a string with a whitespace and newline delimited text from a
    dictionary.

    For example, this:
    {'cpu': '1100', 'ram': '640', 'smp': 'auto'}

    becomes:
    cpu 1100
    ram 640
    smp auto

    cpu 2200
    ram 1024
    """
    result = ''
    for k in data:
        if data[k] is not None:
            result += '%s %s\n' % (str(k), str(data[k]))
        else:
            result += '%s\n' % str(k)

    return result


def reverse_dict(dictionary):
    return dict([(value, key) for key, value in list(dictionary.items())])


def lowercase_keys(dictionary):
    return dict(((k.lower(), v) for k, v in dictionary.items()))


def get_secure_random_string(size):
    """
    Return a string of ``size`` random bytes. Returned string is suitable for
    cryptographic use.

    :param size: Size of the generated string.
    :type size: ``int``

    :return: Random string.
    :rtype: ``str``
    """
    value = os.urandom(size)
    value = binascii.hexlify(value)
    value = value.decode('utf-8')[:size]
    return value


class ReprMixin(object):
    """
    Mixin class which adds __repr__ and __str__ methods for the attributes
    specified on the class.
    """

    _repr_attributes = []

    def __repr__(self):
        attributes = []
        for attribute in self._repr_attributes:
            value = getattr(self, attribute, None)
            attributes.append('%s=%s' % (attribute, value))

        values = (self.__class__.__name__, ', '.join(attributes))
        result = '<%s %s>' % values
        return result

    def __str__(self):
        return str(self.__repr__())


def retry(retry_exceptions=EXCEPTION_TYPES, retry_delay=None,
          timeout=None, backoff=None):
    """
    Retry method that helps to handle common exception.

    :param retry_exceptions: types of exceptions to retry on.
    :param retry_delay: retry delay between the attempts.
    :param timeout: maximum time to wait.
    :param backoff: multiplier added to delay between attempts.

    :Example:

    retry_request = retry(timeout=1, retry_delay=1, backoff=1)
    retry_request(self.connection.request)()
    """
    def deco_retry(func):
        @wraps(func)
        def retry_loop(*args, **kwargs):
            delay = retry_delay
            end = datetime.now() + timedelta(seconds=timeout)
            exc_info = None
            while datetime.now() < end:
                try:
                    result = func(*args, **kwargs)
                    return result
                except retry_exceptions:
                    e = sys.exc_info()[1]

                    if isinstance(e, RateLimitReachedError):
                        time.sleep(e.retry_after)
                        end = datetime.now() + timedelta(
                            seconds=e.retry_after + timeout)
                    else:
                        exc_info = e
                        time.sleep(delay)
                        delay *= backoff
            if exc_info:
                raise exc_info
            return func(*args, **kwargs)
        return retry_loop
    return deco_retry
