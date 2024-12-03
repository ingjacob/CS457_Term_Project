import sys
import socket
import selectors
import traceback
import struct
import os
import argparse

import cHelper

# Create selector object to control socket connection
sel = selectors.DefaultSelector()

# Create argparse object to parse the IP Address and Port Number
parser = argparse.ArgumentParser()
parser.add_argument('-i', '--ip', required=True)
parser.add_argument('-p', '--port', type=int, required=True)
args = parser.parse_args()

# Use arguments to generate request content
def create_request(action, value, username):
    if action == "move" or action == "quit":
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action, value=value),
        )
    elif action == "chat":
        return dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action=action, value=username + ': ' + value),
        )
    else:
        return None

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
    message = cHelper.Message(sel, sock, addr, dict(
            type="text/json",
            encoding="utf-8",
            content=dict(action='join', value='temp'),
        ))
    sel.register(sock, events, data=message)

# Print function to show chat, board, and any error messages
def show_board(state, status, chatLog, username, error):
    os.system('clear')
    print('Username: ' + username)
    print('\n-Chat History-\n' + chatLog)
    print(status)
    print('\n ' + state[0][0] + ' │ ' + state[0][1] + ' │ ' + state[0][2] + ' ')
    print('───┼───┼───')
    print(' ' + state[1][0] + ' │ ' + state[1][1] + ' │ ' + state[1][2] + ' ')
    print('───┼───┼───')
    print(' ' + state[2][0] + ' │ ' + state[2][1] + ' │ ' + state[2][2] + ' \n')
    if error:
        print(error)
    
# Check if the game is over
def handleWin(winChecker):
    if winChecker == 'win':
        return 'You win'
    if winChecker == 'oppwin':
        return 'Opponent wins'
    if winChecker == 'tie' or winChecker == 'opptie':
        return 'Tie game'
    return 'Continue'

# Initialize necessary variables
host, port = args.ip, args.port
printBool, startBool, exitBool = False, True, True
chatLog = ''
winChecker, errorMessage = None, None

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
        request = None
        events = sel.select(timeout=1)
        for key, mask in events:
            message = key.data
            if mask & selectors.EVENT_WRITE:
                # If game has just started wait for opponent to connect, or for opponent to make the first move
                if startBool:
                    os.system('clear')
                    print("Username: " + username)
                    print("---Waiting for opponent---")
                    print(chatLog)
                    startBool = False
                # If it is currently this user's turn
                if not message.waiting:
                    # Loop until valid request is received
                    while not request:
                        # Handle invalid move
                        if message.invalidMove:
                            errorMessage = 'Invalid move, please enter a value 1-9 that has not already been played'
                            message.invalidMove = False
                        show_board(gameState,"---Your turn---",chatLog,username,errorMessage)

                        # Get action and value from user
                        action = input("Action: ")
                        value = input("Value: ")
                        if action == "chat":
                            # Update chatlog with user's message
                            chatLog += username + ': ' + value + '\n'
                        request = create_request(action,value,username)
                        if request:
                            message.set_req(request)
                            errorMessage = None
                        else:
                            errorMessage = 'Invalid command: ' + action + '\nValid actions: chat, move, quit'
                        printBool = True
                # If it is not currently this user's turn
                if message.waiting and printBool:
                    show_board(gameState,"---Opponent's turn---",chatLog,username,errorMessage)
                    printBool = False
            try:
                # Process any read or write events
                gameState, winChecker, newChat = message.process_events(mask)

                # Update chatlog with opponent's message
                if newChat:
                    chatLog += newChat + '\n'
                    printBool = True

                # Check for game end and handle end of game
                temp = handleWin(winChecker)
                if not temp == 'Continue':
                    exitBool = False
                    show_board(gameState,'---Game Over---',chatLog,username,errorMessage)
                    print(temp + '\n')
                    message.set_req(create_request("quit", "gameOver", username))
                    message.waiting = False
                    message.write()
                    message.close()
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