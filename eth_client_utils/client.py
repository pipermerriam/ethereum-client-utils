import time
import json
import numbers
from six.moves.queue import Queue
import threading
import uuid

from eth_client_utils.utils import (
    get_transaction_params,
    construct_filter_args,
    wait_for_transaction,
    wait_for_block,
    get_max_gas,
)


class BaseClient(object):
    def __init__(self, async=True, async_timeout=10):
        self.is_async = async
        self.async_timeout = async_timeout

        if self.is_async:
            self.request_queue = Queue()
            self.results = {}

            self.request_thread = threading.Thread(target=self.process_requests)
            self.request_thread.daemon = True
            self.request_thread.start()

    def process_requests(self):
        """
        Loop that runs in a thread to process requests synchronously.
        """
        while True:
            id, args, kwargs = self.request_queue.get()
            try:
                response = self._make_request(*args, **kwargs)
            except Exception as e:
                response = e
            self.results[id] = response

    def make_request(self, *args, **kwargs):
        if self.is_async:
            request_id = uuid.uuid4()
            self.request_queue.put((request_id, args, kwargs))
            start = time.time()
            while time.time() - start < self.async_timeout:
                if request_id in self.results:
                    result = self.results.pop(request_id)
                    if isinstance(result, Exception):
                        raise result
                    return result
            raise ValueError("Timeout waiting for {0}".format(request_id))
        else:
            return self._make_request(*args, **kwargs)

    def _make_request(self, method, params):
        raise NotImplementedError("Clients must implement this method")


class JSONRPCBaseClient(BaseClient):
    _nonce = 0

    def get_nonce(self):
        self._nonce += 1
        return self._nonce

    _coinbase_cache = None
    _coinbase_cache_til = None

    @property
    def default_from_address(self):
        """
        Cache the coinbase address so that we don't make two requests for every
        single transaction.
        """
        if self._coinbase_cache_til is not None:
            if time.time - self._coinbase_cache_til > 30:
                self._coinbase_cache_til = None
                self._coinbase_cache = None

        if self._coinbase_cache is None:
            self._coinbase_cache = self.get_coinbase()

        return self._coinbase_cache

    def construct_json_request(self, method, params):
        request = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self.get_nonce(),
        })
        return request

    #
    # Utility Methods
    #
    get_max_gas = get_max_gas
    wait_for_transaction = wait_for_transaction
    wait_for_block = wait_for_block

    #
    # JSON-RPC Methods
    #
    def get_coinbase(self):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_coinbase
        """
        response = self.make_request("eth_coinbase", [])
        return response['result']

    def get_gas_price(self):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_gasprice
        """
        response = self.make_request("eth_gasPrice", [])
        return int(response['result'], 16)

    def get_balance(self, address, block="latest"):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_getbalance
        """
        response = self.make_request("eth_getBalance", [address, block])
        return int(response['result'], 16)

    def get_code(self, address, block="latest"):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_getcode
        """
        response = self.make_request("eth_getCode", [address, block])
        return response['result']

    def call(self, _from=None, to=None, gas=None, gas_price=None, value=0,
             data=None, block="latest"):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_call
        """
        if _from is None:
            _from = self.default_from_address

        params = [
            get_transaction_params(_from, to, gas, gas_price, value, data),
            block,
        ]
        response = self.make_request("eth_call", params)
        return response['result']

    def send_transaction(self, _from=None, to=None, gas=None, gas_price=None,
                         value=0, data=None):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_sendtransaction
        """
        if _from is None:
            _from = self.default_from_address

        params = get_transaction_params(_from, to, gas, gas_price, value, data)

        response = self.make_request("eth_sendTransaction", [params])
        return response['result']

    def get_transaction_receipt(self, txn_hash):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_gettransactionreceipt
        """
        response = self.make_request("eth_getTransactionReceipt", [txn_hash])
        return response['result']

    def get_transaction_by_hash(self, txn_hash):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_gettransactionbyhash
        """
        response = self.make_request("eth_getTransactionByHash", [txn_hash])
        return response['result']

    def get_block_number(self):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_blocknumber<F37>
        """
        response = self.make_request("eth_blockNumber", [])
        return int(response['result'], 16)

    def get_block_by_hash(self, block_hash, full_transactions=True):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_getblockbyhash
        """
        response = self.make_request("eth_getBlockByHash", [block_hash, full_transactions])
        return response['result']

    def get_block_by_number(self, block_number, full_transactions=True):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_getblockbynumber
        """
        if isinstance(block_number, numbers.Number):
            block_number_as_hex = hex(block_number)
        else:
            block_number_as_hex = block_number
        response = self.make_request(
            "eth_getBlockByNumber", [block_number_as_hex, full_transactions],
        )
        return response['result']

    def get_accounts(self):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_accounts
        """
        response = self.make_request("eth_accounts", [])
        return response['result']

    def new_filter(self, from_block=None, to_block=None, address=None, topics=None):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_newfilter
        Create a new filter object to be notified of changes in the
        state of the EVM through the logs.
        This command returns a filter ID that can be referenced by
        other commands to get log information.
        """
        params = construct_filter_args(from_block, to_block, address, topics)
        response = self.make_request("eth_newFilter", [params])
        return(response['result'])

    def new_block_filter(self):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_newblockfilter
        """
        response = self.make_request("eth_newBlockFilter", [])
        return(response['result'])

    def new_pending_transaction_filter(self):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_newpendingtransactionfilter
        """
        response = self.make_request("eth_newPendingTransactionFilter", [])
        return(response['result'])

    def uninstall_filter(self, filter_id):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_uninstallfilter
        Removes a filter by ID
        """
        if isinstance(filter_id, numbers.Number):
            filt_hex = hex(filter_id)
        else:
            filt_hex = filter_id

        response = self.make_request("eth_uninstallFilter", [filt_hex])
        return(response['result'])

    def get_filter_changes(self, filter_id):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_getfilterchanges
        """
        if isinstance(filter_id, numbers.Number):
            filt_hex = hex(filter_id)
        else:
            filt_hex = filter_id
        response = self.make_request("eth_getFilterChanges", [filt_hex])
        return(response['result'])

    def get_filter_logs(self, filter_id):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_getfilterlogs
        """
        if isinstance(filter_id, numbers.Number):
            filt_hex = hex(filter_id)
        else:
            filt_hex = filter_id
        response = self.make_request("eth_getFilterLogs", [filt_hex])
        return(response['result'])

    def get_logs(self, from_block=None, to_block=None, address=None, topics=None):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_getlogs
        """
        params = construct_filter_args(from_block, to_block, address, topics)
        response = self.make_request("eth_getLogs", [params])
        return(response['result'])
