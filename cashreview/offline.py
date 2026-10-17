"""Process-local network guard; no operating-system security/network changes."""
import socket


def deny_network(allowed_loopback_ports=()):
    allowed=frozenset(allowed_loopback_ports)
    if any(type(p) is not int or not 1<=p<=65535 for p in allowed):raise ValueError('Invalid loopback port')
    original_connect=socket.socket.connect;original_connect_ex=socket.socket.connect_ex
    original_create=socket.create_connection;original_resolve=socket.getaddrinfo
    def denied(*args,**kwargs): raise RuntimeError("Network is disabled inside inference worker")
    def permitted(address):
        if not isinstance(address,tuple) or len(address)<2:return False
        host,port=address[:2]
        return host in ('127.0.0.1','::1',b'127.0.0.1',b'::1') and type(port) is int and port in allowed
    def connect(sock,address):
        if not permitted(address):return denied()
        return original_connect(sock,address)
    def connect_ex(sock,address):
        if not permitted(address):return denied()
        return original_connect_ex(sock,address)
    def create(address,*args,**kwargs):
        if not permitted(address):return denied()
        return original_create(address,*args,**kwargs)
    def resolve(host,port,*args,**kwargs):
        if not permitted((host,port)):return denied()
        return original_resolve(host,port,*args,**kwargs)
    socket.socket.connect=connect
    socket.socket.connect_ex=connect_ex
    socket.create_connection=create
    socket.getaddrinfo=resolve
