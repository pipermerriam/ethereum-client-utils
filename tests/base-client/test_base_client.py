import time
import threading

import pytest

from eth_client_utils import BaseClient


class AsyncError(Exception):
    pass


class ExampleClient(BaseClient):
    _request_in_progress = False

    def _make_request(self, *args, **kwargs):
        """
        Implementation that isn't friendly to async requests.
        """
        if self._request_in_progress is True:
            raise AsyncError("Request already in progress")
        self._request_in_progress = True
        time.sleep(1)
        self._request_in_progress = False
        return {'result': hex(1)}

    def do_something(self):
        return self.make_request()


def test_fails_when_synchronous():
    client = ExampleClient(async=False)

    threads = []
    errors = []

    def spam_block_number():
        for i in range(10):
            try:
                client.do_something()
            except AsyncError as e:
                errors.append(e)
                raise

    for i in range(3):
        thread = threading.Thread(target=spam_block_number)
        thread.daemon = True
        threads.append(thread)

    [thread.start() for thread in threads]
    [thread.join() for thread in threads]
    assert len(errors) > 0


def test_succeeds_when_asynchrounous():
    client = ExampleClient(async=True)

    threads = []
    errors = []

    def spam_block_number():
        for i in range(10):
            try:
                client.do_something()
            except AsyncError as e:
                errors.append(e)
                raise

    for i in range(3):
        thread = threading.Thread(target=spam_block_number)
        thread.daemon = True
        threads.append(thread)

    [thread.start() for thread in threads]
    [thread.join() for thread in threads]

    assert not errors
