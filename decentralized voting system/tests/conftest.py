import threading
import time
import pytest
from openballot.ledger import Ledger
from openballot.node import NodeServer, NodeHandler
from openballot.citizens import citizen_manager


@pytest.fixture(scope="module")
def running_server():
    citizen_manager.persistence_file = None
    ledger = Ledger()
    ledger.create_genesis_block()
    server = NodeServer(("127.0.0.1", 0), NodeHandler, ledger=ledger, difficulty=1)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    base_url = f"http://127.0.0.1:{port}"
    yield base_url, ledger
    server.shutdown()
    server.server_close()
