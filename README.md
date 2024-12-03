# Tic-Tac-Toe Game Example

This is a simple Tic-Tac-Toe game implemented using Python and sockets.

**How to play:**
1. **Start the server:** Run the `server.py` script. Usage: python3 server.py -p \<port\>
2. **Connect clients:** Run the `client.py` script on two different terminals. Usage: python3 client.py -i \<host ip\> -p \<port\>
3. **Send messages** After requesting a username from the terminal keyboard input, the client code will connect to the server. After two clients are connected they take turn making game moves.
4. **Play the game:** When it is a client's turn the terminal will request an Action and a Value. To make a game move enter 'move' as the Action, and a number 1-9 as the Value. To send a chat to the opponent enter 'chat' as the Action, and the message as the Value. To exit the game before it is finished enter 'quit' as the Action, and the reason for quitting as the Value.
5. **Exiting** When the game is finished both clients will automatically close their connection. Both clients will also close the connection when one client chooses to quit.

**Technologies used:**
* Python
* Sockets
