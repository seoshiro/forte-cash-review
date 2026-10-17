"""Process-local network guard; no operating-system security/network changes."""
import socket


def deny_network():
    def denied(*args,**kwargs): raise RuntimeError("Network is disabled inside inference worker")
    socket.socket.connect=denied
    socket.socket.connect_ex=denied
    socket.create_connection=denied
    socket.getaddrinfo=denied
