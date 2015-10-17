#!/usr/bin/python

"""
Script for creating an ssl port forward tunnel.

Usage example:
on server:
>>> tunnel.py --local 127.0.0.1:1234 --remote 5.5.5.5:88 --key mykey.key --cert mycert.crt --cacert cert.ca --server
on client:
>>> tunnel.py --local 127.0.0.1:1234 --remote 5.5.5.5:88 --key mykey.key --cert mycert.crt --cacert cert.ca
"""
import socket, select, ssl
import sys, threading, argparse
import pprint

globConfig = {
    "serverMode": False,
    "remotehost": "ircs.overthewire.org",
    "remoteport": 6697,
    "localhost": "127.0.0.1",
    "localport": 1234,

    "cert": None,
    "key": None,
    "cacert": None,
}

def connectBackend():
    print "Connecting to %s %s" % (globConfig["remotehost"], globConfig["remoteport"])
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    outsock = None
    
    if globConfig["serverMode"]:
	outsock = sock
    else:
	outsock = ssl.wrap_socket(sock, 
	    keyfile=globConfig["key"], 
	    certfile=globConfig["cert"],
	    ca_certs=globConfig["cacert"], 
	    cert_reqs=ssl.CERT_REQUIRED,
	    ssl_version=ssl.PROTOCOL_TLSv1)

    outsock.connect((globConfig["remotehost"], globConfig["remoteport"]))
    return outsock

def acceptFrontend(sock):
    clientsock = sock.accept()[0]
    if globConfig["serverMode"]:
	sslsock = ssl.wrap_socket(clientsock, 
	    server_side=True,
	    keyfile=globConfig["key"], 
	    certfile=globConfig["cert"],
	    ca_certs=globConfig["cacert"], 
	    cert_reqs=ssl.CERT_REQUIRED,
	    ssl_version=ssl.PROTOCOL_TLSv1)
	return sslsock
    else:
	return clientsock

def server():
    dock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    dock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    dock_socket.bind((globConfig["localhost"], globConfig["localport"]))
    dock_socket.listen(5)
    while True:
	client_socket = None
	server_socket = None
	try:
	    client_socket = acceptFrontend(dock_socket)
	    server_socket = connectBackend()
	    thread = ForwardingThread(client_socket, server_socket)
	    thread.daemon = True
	    thread.start()
	except Exception,e:
	    if client_socket:
		client_socket.close()
	    if server_socket:
		server_socket.close()
	    print "There was an exception :( %s" % e

class ForwardingThread(threading.Thread):
    def __init__(self, clientsock, serversock):
        threading.Thread.__init__(self)
        self.clientsock = clientsock
        self.serversock = serversock

    def run(self):
	allsocks = [self.clientsock, self.serversock]

	while True:
	    readable, writable, exceptional = select.select(allsocks, [], allsocks)

	    if self.clientsock in readable:
		string = self.clientsock.recv(1000)
		if string:
		    self.serversock.sendall(string)
		else:
		    print "client closed"
		    self.clientsock.close()
		    self.serversock.close()
		    return

	    if self.serversock in readable:
		string = self.serversock.recv(1000)
		if string:
		    self.clientsock.sendall(string)
		else:
		    print "server closed"
		    self.serversock.close()
		    self.clientsock.close()
		    return

	    if self.clientsock in exceptional or self.serversock in exceptional:
		self.clientsock.close()
		self.serversock.close()
		return


def parseOpts():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--local", help="local bind address. e.g. 127.0.0.1:1234", required=True)
    parser.add_argument("-r", "--remote", help="remote connect address. e.g. 31.3.3.7:22", required=True)
    parser.add_argument("-k", "--key", help="private key for this endpoint", required=False)
    parser.add_argument("-c", "--cert", help="certificate for this endpoint", required=False)
    parser.add_argument("--cacert", help="CA certificate to authenticate the other side against", required=False)
    parser.add_argument("--server", action="store_true", help="indicates this side is the server endpoint")
    args = parser.parse_args()

    if args.local:
	a,b = args.local.split(":")
	globConfig["localhost"], globConfig["localport"] = a, int(b)

    if args.remote:
	a,b = args.remote.split(":")
	globConfig["remotehost"], globConfig["remoteport"] = a, int(b)

    if args.key:
	globConfig["key"] = args.key
    if args.cert:
	globConfig["cert"] = args.cert
    if args.cacert:
	globConfig["cacert"] = args.cacert
    if args.server:
	globConfig["serverMode"] = True


if __name__ == '__main__':
    parseOpts()
    server()
