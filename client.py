#!/usr/bin/env python
#
# A testing client for the Verse master server.
#

import socket
import sys
import time

import verse as v

quiet = False
time0 = 0
time1 = 0

def address_to_ip(address):
	host = address
	port = None
	if ":" in address:
		ci = address.index(":")
		host = address[:ci]
		port = int(address[ci + 1:])
	ip = socket.gethostbyname(host)
	if port != None:
		return ip + ":%u" % port
	return ip
	

class Listener:
	def __init__(self):
		self.created = time.time()
		self.set_master("localhost:4950")
		self.single = False
		self.set_duration(10.0)
		self.set_raw(False)
		self.set_lookup(False)
		v.callback_set(v.SEND_PING, self._cb_ping)

	def set_master(self, ip):
		self.master = address_to_ip(ip)

	def set_duration(self, d):
		self.duration = d

	def set_raw(self, r):
		self.raw = r

	def set_lookup(self, l):
		self.lookup = l

	def had_enough(self):
		if self.duration < 0.0: return False
		return (time.time() - self.created) >= self.duration

	def send_get(self, tags = None):
		cmd = 'MS:GET IP="DE"'
		if tags != None:
			cmd += ' TA=%s' % tags
		if not quiet:
			print "Sending master server GET to", self.master, ": '%s'" % cmd
		v.send_ping(self.master, cmd)

	def _cb_ping(self, host, msg):
		global time1
		if host.startswith(self.master):
			if time1 == 0: time1 = time.time() - time0
			if not self.raw:
				entries = msg[7:].lstrip().split("IP=")
				for e in entries:
					if len(e) == 0: continue
					if self.lookup and " " in e:
						ss = e.index(" ")
						ip = e[:ss]
						ip.strip('"').strip()
						print socket.gethostbyaddr(ip)[0],
						e = e[ss + 1:]
					print e
			else:
				print msg
		else:
			print "Ping from unknown host at", host, ":", msg

def usage():
	print "Verse Master Server test client. Written 2006 by Emil Brink."
	print "Usage:"
	print " -duration=TIME\t\tRun for at most TIME seconds. Set to negative to disable."
	print " -h\t\t\tShow this usage information, and exit."
	print " -ip=IP[:PORT]\t\tSet the address for the master server."
	print " -n\t\t\tShow listed Verse servers by name, through a reverse look-up."
	print " -raw\t\t\tDisable interpretation of MS:LIST commands; show them as they are."
	print " -tags=TAGS\t\tSet tag filter to use. Example: -tags=open,sweden,-r6p0."
	print " -q\t\t\tBe quiet, only print actual list of responses"


def main(arg = None):
	global quiet, time0, time1

	if arg == None: arg = sys.argv

	listen = Listener()

	mode = 'get'
	tags = None

	listen.set_master("master.uni-verse.org:4950")

	for a in arg[1:]:
		if a.startswith("-duration="):
			try:	
				d = float(a[10:])
				listen.set_duration(d)
			except:	pass
		elif a.startswith("-ip="):
			listen.set_master(a[4:])
		elif a == "-h":
			usage()
			sys.exit()
		elif a == "-n":
			listen.set_lookup(True)
		elif a == "-raw":
			listen.set_raw(True)
		elif a.startswith("-tags="):
	    		tags = a[6:]
		elif a == "-q":
			quiet = True
		elif a[0] == '-':
			print "Unknown option", a

	if mode == 'get':
		listen.send_get(tags)
		time0 = time.time()

	while 1:
		v.callback_update(50000)
		if listen.had_enough(): break

	if not quiet and time1 > 0:
		print "Got first response after %.2f seconds" % time1

if __name__ == "__main__":
	main()
