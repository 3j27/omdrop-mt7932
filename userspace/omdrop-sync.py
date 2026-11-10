#!/usr/bin/env python3
"""Build the element 9 (sync master) file for one peer MAC."""
import struct
import sys

mac = bytes.fromhex(sys.argv[1].replace(":", ""))
payload = (1).to_bytes(4, "little") + mac + bytes(20)
sys.stdout.buffer.write(struct.pack("<III", len(payload), 9, len(payload)) + payload)
