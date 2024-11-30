import sys
import socket
import selectors
import traceback
import struct
import os

import cHelper

sel = selectors.DefaultSelector()

# Use arguments to generate request content
def create_request(action, value):
    if action == "join" or action == "move" or action == "chat" or action == "quit":
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

def start_connection(host, port):
    # Initialize host IP and port number, then create TCP socket
    addr = (host, port)
    print("starting connection to", addr) # Log connection start
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)

    # Connect
    sock.connect_ex(addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE

    # Create message object and set up selector
    message = cHelper.Message(sel, sock, addr, create_request("join", "temp"))
    sel.register(sock, events, data=message)

def show_board(state):
    print('\n ' + state[0][0] + ' │ ' + state[0][1] + ' │ ' + state[0][2] + ' ')
    print('───┼───┼───')
    print(' ' + state[1][0] + ' │ ' + state[1][1] + ' │ ' + state[1][2] + ' ')
    print('───┼───┼───')
    print(' ' + state[2][0] + ' │ ' + state[2][1] + ' │ ' + state[2][2] + ' \n')
    
def handleWin(winChecker):
    if winChecker == None: return True
    if winChecker == 'Win':
        print('You win')
        return False
    if winChecker == 'OppWin':
        print('Opponent wins')
        return False
    if winChecker == 'Tie':
        print('Tie game')
        return False

# Handle incorrect number of command-line arguments
if len(sys.argv) != 3:
    print("Incorrect number of arguments, usage:", sys.argv[0], "<host> <port>")
    sys.exit(1)

# Initialize necessary variables
host, port = sys.argv[1], int(sys.argv[2])
printBool, startBool, exitBool = False, True, True
winChecker = None

# Get client username
username = input("Please enter a username to connect: ")

# Call function using command-line arguments
start_connection(host, port)

# Start connection with join message
try:
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
except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")

# Loop to keep connection alive
try:
    while exitBool:
        events = sel.select(timeout=1)
        for key, mask in events:
            message = key.data
            if mask & selectors.EVENT_WRITE:
                if startBool:
                    os.system('clear')
                    print("Username: " + username)
                    print("---Waiting for opponent---")
                    startBool = False
                if not message.waiting:
                    os.system('clear')
                    print("Username: " + username)
                    print("---Your turn---")
                    show_board(gameState)
                    action = input("Action: ")
                    value = input("Value: ")
                    message.set_req(create_request(action,value))
                    printBool = True
                if message.waiting and printBool:
                    os.system('clear')
                    print("Username: " + username)
                    print("---Opponent's turn---")
                    show_board(gameState)
                    printBool = False
            try:
                gameState, winChecker = message.process_events(mask)
                exitBool = handleWin(winChecker)
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