import os
import socket
import tempfile
import time

from leaky.fd_tracker import FDS, UNCLOSED_TIMEOUT


def test_file_tracking():
    os.environ['DEBUG'] = '1'
    import leaky.fd_tracker  # noqa

    # Test file tracking
    with tempfile.NamedTemporaryFile() as f:
        file_id = id(f)
        assert file_id in FDS
    assert file_id not in FDS


def test_socket_tracking():
    os.environ['DEBUG'] = '1'
    import leaky.fd_tracker  # noqa

    # Test socket tracking
    sock = socket.socket()
    sock_id = id(sock)
    assert sock_id in FDS
    sock.close()
    assert sock_id not in FDS


def test_unclosed_detection():
    os.environ['DEBUG'] = '1'
    import leaky.fd_tracker  # noqa

    # Create an unclosed file
    f = tempfile.NamedTemporaryFile()
    file_id = id(f)

    # Wait for the unclosed timeout
    time.sleep(UNCLOSED_TIMEOUT + 1)

    # The file should be detected as unclosed and removed from tracking
    assert file_id not in FDS

    # Clean up
    f.close()