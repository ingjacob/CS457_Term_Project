import sys
import socket
import selectors
import traceback
import struct

import cHelper

sel = selectors.DefaultSelector()

# Use arguments to generate request content
def create_request(action, value):
    if action == "hello":
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action, value=value),
        )
    else:
        return dict(
            type="binary/custom-client-binary-type",
            encoding="binary",
            content=bytes(action + value, encoding="utf-8"),
        )

def start_connection(host, port, request):
    # Initialize host IP and port number, then create TCP socket
    addr = (host, port)
    print("starting connection to", addr) # Log connection start
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)

    # Connect
    sock.connect_ex(addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE

    # Create message object and set up selector
    message = cHelper.Message(sel, sock, addr, request)
    sel.register(sock, events, data=message)

# Handle incorrect number of command-line arguments
if len(sys.argv) != 5:
    print("Incorrect number of arguments, usage:", sys.argv[0], "<host> <port> <action> <value>")
    sys.exit(1)

# Initialize necessary variables
host, port = sys.argv[1], int(sys.argv[2])
action, value = sys.argv[3], sys.argv[4]

# Call function using command-line arguments
request = create_request(action, value)
start_connection(host, port, request)

try:
    while True:
        events = sel.select(timeout=1)
        for key, mask in events:
            message = key.data
            try:
                message.process_events(mask)
            except Exception:
                # Log exception and kill connection
                print(
                    "main: error: exception for",
                    f"{message.addr}:\n{traceback.format_exc()}",
                )
                message.close()
        # Check for a socket being monitored to continue.
        if not sel.get_map():
            break
except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")
finally:
    sel.close()