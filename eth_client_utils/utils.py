import time


def wait_for_transaction(blockchain_client, txn_hash, max_wait=60, sleep_time=5):
    start = time.time()
    while True:
        txn_receipt = blockchain_client.get_transaction_receipt(txn_hash)
        if txn_receipt is not None:
            break
        elif time.time() > start + max_wait:
            raise ValueError("Could not get transaction receipt")
        time.sleep(sleep_time)
    return txn_receipt


def wait_for_block(blockchain_client, block_number, max_wait=60, sleep_time=5):
    start = time.time()
    while time.time() < start + max_wait:
        latest_block_number = blockchain_client.get_block_number()
        if latest_block_number >= block_number:
            break
        time.sleep(sleep_time)
    else:
        raise ValueError("Did not reach block")
    return blockchain_client.get_block_by_number(block_number)


def get_max_gas(blockchain_client):
    latest_block = blockchain_client.get_block_by_number('latest')
    max_gas_hex = latest_block['gasLimit']
    max_gas = int(max_gas_hex, 16)
    return max_gas
