#!/usr/bin/env python3
"""TCP relay on the Studio: the Mac's AirDrop connection to the advertised
address is looped back here and forwarded to the Neo's receiver."""
import os
import socket
import threading

LISTEN = os.environ.get("OMDROP_LISTEN", "::")
PORT = int(os.environ.get("OMDROP_PORT", "8771"))
TARGET_IP = os.environ.get("OMDROP_TARGET_IP")
if not TARGET_IP:
    raise SystemExit("set OMDROP_TARGET_IP to the Neo LAN address")
TARGET = (TARGET_IP, int(os.environ.get("OMDROP_TARGET_PORT", "8771")))


def pipe(a, b):
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except OSError:
        pass
    finally:
        try:
            b.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def handle(client):
    try:
        upstream = socket.create_connection(TARGET, 5)
    except OSError as e:
        print("upstream failed", e, flush=True)
        client.close()
        return
    print("relay", client.getpeername(), "->", TARGET, flush=True)
    threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
    pipe(upstream, client)
    client.close()


def main():
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((LISTEN, PORT))
    s.listen(32)
    print("relay listening on [%s]:%d -> %s:%d" % (LISTEN, PORT, *TARGET),
          flush=True)
    while True:
        client, _ = s.accept()
        threading.Thread(target=handle, args=(client,), daemon=True).start()


if __name__ == "__main__":
    main()
