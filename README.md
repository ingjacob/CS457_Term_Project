# Tic-Tac-Toe Game Example

This is a simple Tic-Tac-Toe game implemented using Python and sockets.

**How to play:**
1. **Start the server:** Run the `server.py` script. Usage: python3 server.py \<host\> \<port\>
2. **Connect client:** Run the `client.py` script. Usage: python3 client.py \<host\> \<port\>
3. **Send messages** The client command line will prompt the user for an Action and a Value to send to the server. This prompt will not appear until another client has also connected to the server (the two clients will be connected as opponents). Defined actions are: join, move, chat, quit. Any other action will result in a binary message being sent (as opposed to a json). The server will notify a client when: an opponent joins, an opponent leaves, a chat message is sent from the opponent.
4. **Play the game:** Players take turns entering their moves. The first player to get three in a row wins! (Not yet implemented)

**Technologies used:**
* Python
* Sockets

**Additional resources:**
* [Link to Python documentation]
* [Link to sockets tutorial]
