# SPDX-License-Identifier: GPL-3.0-or-later
"""A tiny DNS server for end-to-end tests: answers A queries for the names it is given, following CNAME chains, so a
browser started with --dns-server can load pages under real or made-up hostnames from a local web server."""

import socket
import socketserver
import struct
import threading


def encode_name(name: str) -> bytes:
    return b"".join(bytes([len(label)]) + label.encode() for label in name.rstrip(".").split(".")) + b"\0"


def decode_question(packet: bytes) -> tuple[str, int, int]:
    labels, offset = [], 12
    while packet[offset]:
        length = packet[offset]
        labels.append(packet[offset + 1:offset + 1 + length].decode())
        offset += 1 + length
    qtype, = struct.unpack("!H", packet[offset + 1:offset + 3])
    return ".".join(labels).lower(), qtype, offset + 5


def start(addresses: dict[str, str], cnames: dict[str, str] | None = None) -> tuple[socketserver.UDPServer, list[str]]:
    """Starts a server on 127.0.0.1 and returns it with the list it records queried names in."""
    cnames = cnames or {}
    queries: list[str] = []

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            packet, sock = self.request
            name, qtype, question_end = decode_question(packet)
            queries.append(name)
            answers, current = [], name
            while current in cnames:
                target = cnames[current]
                answers.append(encode_name(current) + struct.pack("!HHIH", 5, 1, 60, len(encode_name(target))) + encode_name(target))
                current = target
            known = current in addresses or bool(answers)
            if qtype == 1 and current in addresses:
                answers.append(encode_name(current) + struct.pack("!HHIH", 1, 1, 60, 4) + socket.inet_aton(addresses[current]))
            flags = 0x8180 if known else 0x8183  # NOERROR, or NXDOMAIN
            header = packet[:2] + struct.pack("!HHHHH", flags, 1, len(answers), 0, 0)
            sock.sendto(header + packet[12:question_end] + b"".join(answers), self.client_address)

    server = socketserver.ThreadingUDPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, queries
