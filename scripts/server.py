import sys
import socket
import selectors
import traceback

import sHelper

sel = selectors.DefaultSelector()
gameList = {0:'Empty'}

# Handle incorrect number of command-line arguments
if len(sys.argv) != 3:
    print("Incorrect number of arguments, usage:", sys.argv[0], "<host> <port>")
    sys.exit(1)

def accept_wrapper(sock):
    # Accept the incoming client connection
    conn, addr = sock.accept()
    print("accepted connection from", addr)
    conn.setblocking(False)

    # Create message object and wait for read event
    message = sHelper.Message(sel, conn, addr, gameList)
    sel.register(conn, selectors.EVENT_READ, data=message)

# Initialize host IP and port number, then create TCP socket
host, port = sys.argv[1], int(sys.argv[2])
lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Use REUSEADDR to avoid bind() exception: OSError: [Errno 48] Address already in use
lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Bind socket to specified port and wait for data to read
lsock.bind((host, port))
lsock.listen()
print("listening on", (host, port))
lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=None)

# Information to send to opponent
updateOpp = {}

# Loop to keep server running
try:
    while True:
        events = sel.select(timeout=None)
        for key, mask in events:
            if key.data is None:
                accept_wrapper(key.fileobj)
            else:
                message = key.data
                try:
                    updateOpp = message.process_events(mask)
                    #if updateOpp:
                    if updateOpp and not type(gameList.get(updateOpp.get('ID'))) is dict and not gameList.get(updateOpp.get('ID')).sock == None:
                        opponent = gameList.get(updateOpp.get('ID'))
                        del updateOpp['ID']
                        opponent.write_update(updateOpp)
                        updateOpp = {}
                except Exception:
                    # Log exception and kill connection
                    print(
                        "main: error: exception for",
                        f"{message.addr}:\n{traceback.format_exc()}",
                    )
                    message.close()
except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")
finally:
    sel.close()