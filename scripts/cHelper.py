import sys
import selectors
import json
import io
import struct

class Message:
    def __init__(self, selector, sock, addr, request):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self.request = request
        self._recv_buffer = b""
        self._send_buffer = b""
        self._request_queued = False
        self._jsonheader_len = None
        self.jsonheader = None
        self.response = None
        self.closing = False
        self.waiting = False
        self.gameState = [[0,0,0],[0,0,0],[0,0,0]]

    def set_req(self, request):
        self.request = request

    def _set_selector_events_mask(self, mode):
        # Set selector to listen for events: mode is 'r', 'w', or 'rw'
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
        if mask & selectors.EVENT_WRITE:
            self.write()
        if mask & selectors.EVENT_READ or mask & (selectors.EVENT_READ | selectors.EVENT_WRITE):
            self.read()
        #if mask & selectors.EVENT_WRITE or mask & (selectors.EVENT_READ | selectors.EVENT_WRITE):

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
            if self.response is None:
                self.process_response()

        self._jsonheader_len = None
        self.jsonheader = None
        #self.waiting = False

    def _read(self):
        try:
            # Read from the socket
            data = self.sock.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:
            if data:
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
            for reqhdr in ("byteorder", "content-length", "content-type", "content-encoding",):
                if reqhdr not in self.jsonheader:
                    raise ValueError(f'Missing required header "{reqhdr}".')

    def process_response(self):
        content_len = self.jsonheader["content-length"]
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len] # Get the content
        self._recv_buffer = self._recv_buffer[content_len:] # Remove the content from the buffer
        if self.jsonheader["content-type"] == "text/json":
            encoding = self.jsonheader["content-encoding"]
            self.response = self._json_decode(data, encoding)
            print("received response", repr(self.response), "from", self.addr)   # TESTING
            self._process_response_json_content()
        else:
            # Binary or unknown content-type
            self.response = data
            print(
                f'received {self.jsonheader["content-type"]} response from',
                self.addr,
            )
            self._process_response_binary_content()

        self.response = None

        # After reading and processing, listen for write events
        self._set_selector_events_mask("rw")
        #if self.waiting == True: self._set_selector_events_mask("r")
        #if self.waiting: self._set_selector_events_mask("rw")

        # Shut down when triggered
        if self.closing:
            self.close()

    def _process_response_json_content(self):
        # Print the response from the server
        content = self.response
        result = content.get("result")
        chat = content.get("chat")
        print(f"got result: {result}") # TESTING
        if chat: print(f"got chat: {chat}")
        if content.get("exit") == "Confirmed Exit":
            self.closing = True
        if content.get("join") == 'Waiting':
            self.waiting = True
        if content.get("join") == 'Success' and result == 'First':
            self.waiting = False
        if content.get('join') == 'Success' and result == 'Second':
            self.waiting = True
        if content.get('result') == 'oppMove':
            self.waiting = False
        if content.get('result') == 'moveSuccess':
            self.waiting = True
        if content.get('exit') == 'Opponent Exited':
            print('Opponent Exited, closing connection')
            self.closing = True

    def _process_response_binary_content(self):
        # Print the response from the server
        content = self.response
        print(f"got response: {repr(content)}")

    def write(self):
        if self.waiting: return
        if not self._request_queued:
            self.queue_request()

        # Attempt to write from buffer to socket
        self._write()

        if self._request_queued:
            if not self._send_buffer:
                # Set selector to listen for read events, we're done writing.
                self._set_selector_events_mask("r")

        self._request_queued = False # Update state

    def queue_request(self):
        # Set up variables for sending
        content = self.request["content"]
        content_type = self.request["type"]
        content_encoding = self.request["encoding"]

        # Check for JSON content
        if content_type == "text/json":
            req = {
                "content_bytes": self._json_encode(content, content_encoding),
                "content_type": content_type,
                "content_encoding": content_encoding,
            }
        else:
            req = {
                "content_bytes": content,
                "content_type": content_type,
                "content_encoding": content_encoding,
            }
        message = self._create_message(**req) # Package request with appropriate headers
        self._send_buffer += message # Add request to buffer
        self._request_queued = True # Update state

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
            # Log data send attempt
            print("sending", repr(self._send_buffer), "to", self.addr) # TESTING
            try:
                # Write to the socket
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]

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