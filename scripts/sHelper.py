import sys
import selectors
import json
import io
import struct

class Message:
    def __init__(self, selector, sock, addr, gameList):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self._recv_buffer = b""
        self._send_buffer = b""
        self._jsonheader_len = None
        self.jsonheader = None
        self.request = None
        self.response_created = False
        self.closing = False
        self.connected = False
        self.updateOpp = {}
        self.clientID = None
        self.gameState = [[0,0,0],[0,0,0],[0,0,0]]
        for g in list(gameList):
            if gameList[g] == 'Empty': 
                self.clientID = g
                gameList[g+1] = 'Empty'
                gameList[g] = {'Waiting':self}
            if g>0 and type(gameList[g-1]) is dict and type(gameList[g]) is dict:
                temp = gameList[g-1].get('Waiting')
                gameList[g-1] = gameList[g].get('Waiting')
                gameList[g] = temp
                self.connected = True
                gameList[g].connected = True

    def process_move(self, move, value):
        try: moveInt = int(move)
        except ValueError:
            return False
        if not (moveInt >= 0 and moveInt <=9): return False
        if moveInt - 3 < 1: row = 0
        elif moveInt - 6 < 1: row = 1
        else: row = 2
        if moveInt % 3 == 1: column = 0
        elif moveInt % 3 == 2: column = 1
        else: column = 2
        if self.gameState[row][column] == 1 or self.gameState[row][column] == 2: return False
        else: self.gameState[row][column] = value
        return True
    
    def _set_selector_events_mask(self, mode):
        # Set selector to listen for 'r', 'w', or 'rw'
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw":
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Invalid events mask mode {repr(mode)}.")
        self.selector.modify(self.sock, events, data=self)

    def process_events(self, mask):
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            self.write()
        retVal = self.updateOpp
        self.updateOpp = {}
        return retVal

    def read(self):
        # Try to read from socket into buffer
        self._read()

        # Process headers and content
        if self._jsonheader_len is None:
            self.process_protoheader()

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()

        if self.jsonheader:
            if self.request is None:
                self.process_request()

        self._jsonheader_len = None

    def _read(self):
        try:
            # Read from the socket
            data = self.sock.recv(4096)
        except BlockingIOError:
            pass
        else:
            if data:
                # Add data to buffer to be processed
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer closed.")

    # First part of header (2 bytes) contains the length of the JSON header
    def process_protoheader(self):
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(">H", self._recv_buffer[:hdrlen])[0] # Get length of the JSON header
            self._recv_buffer = self._recv_buffer[hdrlen:] # Remove the processed information from the buffer

    def process_jsonheader(self):
        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen:
            self.jsonheader = self._json_decode(self._recv_buffer[:hdrlen], "utf-8") # Get the JSON header
            self._recv_buffer = self._recv_buffer[hdrlen:] # Remove the processed information from the buffer

            # Check that all required header fields were received successfully
            for reqhdr in ("byteorder", "content-length", "content-type", "content-encoding"):
                if reqhdr not in self.jsonheader:
                    raise ValueError(f'Missing required header "{reqhdr}".')

    def process_request(self):
        content_len = self.jsonheader["content-length"]
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len] # Get the content
        self._recv_buffer = self._recv_buffer[content_len:] # Remove the content from the buffer
        if self.jsonheader["content-type"] == "text/json":
            encoding = self.jsonheader["content-encoding"]
            self.request = self._json_decode(data, encoding)
            print("received request", repr(self.request), "from", self.addr)
        else:
            # Binary or unknown content-type
            self.request = data
            print(
                f'received {self.jsonheader["content-type"]} request from',
                self.addr,
            )
        # Set selector to listen for write events
        #self._set_selector_events_mask("rw")
        self._set_selector_events_mask("w")

    def write(self):
        # Create response if needed
        if self.request:
            if not self.response_created:
                self.create_response()

        # Attempt to write from buffer to socket
        self._write()

        # Update states
        self.response_created = False
        self.jsonheader = None
        self.request = None

    def create_response(self):
        if self.jsonheader["content-type"] == "text/json":
            response = self._create_response_json_content()
        else:
            # Binary or unknown content-type
            response = self._create_response_binary_content()
        message = self._create_message(**response) # Package response with appropriate headers
        self.response_created = True # Update state
        self._send_buffer += message # Add response to buffer

    def _create_response_json_content(self):
        # Determine desired action and respond accordingly
        action = self.request.get("action")
        content_encoding = "utf-8"
        if action == "join":
            mssge = self.request.get("value")
            if self.connected == True: 
                content = {"join": "Success","result": 'Second'}
                self.updateOpp = {'join': 'Success','result':'First','ID': self.clientID}
            else: content = {"join": "Waiting","result": mssge}
        elif action == "move":
            mssge = self.request.get("value")
            validMove = self.process_move(mssge, 1)
            if validMove:
                content = {"result": 'moveSuccess','move': mssge}
                self.updateOpp = {'result': 'oppMove','move': mssge,'ID': self.clientID}
            else: content = {'result': 'moveFail'}
        elif action == "chat":
            mssge = self.request.get("value")
            content = {"result": mssge}
            self.updateOpp = {'chat': mssge, 'ID': self.clientID}
        elif action == "quit":
            mssge = self.request.get("value")
            content = {"exit": "Confirmed Exit","result": mssge}
            self.closing = True
            if self.connected == True: self.updateOpp = {'exit': 'Opponent Exited', 'ID': self.clientID}
        else:
            content = {"result": f'Error: invalid action "{action}".'}
        content_encoding = "utf-8"
        response = {
            "content_bytes": self._json_encode(content, content_encoding),
            "content_type": "text/json",
            "content_encoding": content_encoding
        }
        return response

    def _create_response_binary_content(self):
        # For binary content repeat message back
        retVal = b"Request received by server: " + self.request
        response = {
            "content_bytes": retVal,
            "content_type": "binary/custom-server-binary-type",
            "content_encoding": "binary",
        }
        return response

    def _create_message(self, *, content_bytes, content_type, content_encoding):
        # Setup header format
        jsonheader = {
            "byteorder": sys.byteorder,
            "content-type": content_type,
            "content-encoding": content_encoding,
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8") # Call encode function to create header content
        message_hdr = struct.pack(">H", len(jsonheader_bytes)) # Use pack() to turn the header length into bytes
        message = message_hdr + jsonheader_bytes + content_bytes # Concatenate message with header length and content
        return message

    def _write(self):
        if self._send_buffer:
            # Log data being sent
            print("sending", repr(self._send_buffer), "to", self.addr)
            try:
                # Write to the socket
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]
                # Close when the buffer is drained after successful send() call(s)
                if sent and not self._send_buffer:
                    #self._set_selector_events_mask("rw")
                    self._set_selector_events_mask("r")
                if self.closing:
                    self.close()

    def write_update(self, content):
        if content.get('result') == 'oppMove': self.process_move(content.get('move'), 2)
        self._set_selector_events_mask("w")
        response = {
            "content_bytes": self._json_encode(content, "utf-8"),
            "content_type": "text/json",
            "content_encoding": "utf-8"
        }
        message = self._create_message(**response) # Package response with appropriate headers
        self._send_buffer += message # Add response to buffer

        # Attempt to write from buffer to socket
        self._write()
    
    def _json_encode(self, obj, encoding):
        # Use encoding to turn JSON header into bytes
        return json.dumps(obj, ensure_ascii=False).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        # Use encoding to unpack JSON header
        tiow = io.TextIOWrapper(io.BytesIO(json_bytes), encoding=encoding, newline="")
        obj = json.load(tiow)
        tiow.close()
        return obj

    def close(self):
        # Log and clean up socket
        print("closing connection to", self.addr)
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            print(
                f"error: selector.unregister() exception for",
                f"{self.addr}: {repr(e)}",
            )

        try:
            self.sock.close()
        except OSError as e:
            print(
                f"error: socket.close() exception for",
                f"{self.addr}: {repr(e)}",
            )
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None