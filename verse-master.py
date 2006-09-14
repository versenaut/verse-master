#!/usr/bin/env python
#
# A Verse Master Server. Maintains a list of announced servers, and can send that list
# to interested clients upon request. The list entries time out if not refreshed.
#

import getopt
import sys
import time

import verse as v

VERSION = "0.2"

class Database:

	MAX_AGE = 2.5 * 60.0

	class Entry:
		def __init__(self, ip):
			self.ip = ip
			self.touch()		# Heh.

		def touch(self):
			self.time = time.time()

	def __init__(self, port = 5666, talk = True):
		self.servers = {}
		self.talk = talk
		self.talked_last = time.time()
		if self.talk:
			print "Listening to port %u, ready for use." % port
		v.set_port(port)
		v.callback_set(v.SEND_PING,	self._cb_ping)

	def announce(self, ip):
		try:
			e = self.servers[ip]
			e.touch()
		except:
			e = Database.Entry(ip)
			self.servers[ip] = e
		if self.talk:
			print "Added/updated entry for", e.ip

	def list(self, ip):
		msg = "MS:LIST"
		for s in self.servers.values():
			if len(msg) + len(s.ip) + 1 > 1400:
				v.send_ping(ip, msg)
				msg = "MS:LIST"
			msg += " " + s.ip
		if len(msg) > 0:
			v.send_ping(ip, msg)

	def clean(self):
		"""Throw out servers that haven't pinged us in a while."""
		i = 0
		now = time.time()
		for e in self.servers.values():
			if now - e.time >= self.MAX_AGE:
				print "Dropping", e.ip, "as it has expired"
				del self.servers[e.ip]
		if self.talk and now - self.talked_last > 10.0:
			print "There are now %u unique servers registered" % len(self.servers)
			self.talked_last = now


	def _cb_ping(self, address, message):
		if message == "MS:ANNOUNCE":
			self.announce(address)
		elif message == "MS:LIST":
			self.list(address)
		else:
			print "Master server ignoring unknown ping '%s' from %s" % (message, address)

def usage():
	print "Verse Master Server, for keeping track of where Verse servers"
	print "are running. See <http://verse.blender.org/> for more on Verse."
	print "Options:"
	print " -h or --help\t\tThis text."
	print " -p PORT or --port=PORT\tSet port number to listen to."
	print " -q or --quiet\t\tDisable status messages."
	print " -v or --version\tPrint version number and exit."

if __name__ == "__main__":
	try:
		opts, args = getopt.getopt(sys.argv[1:], "hp:qv", ["help", "quiet", "port", "version"])
	except getopt.GetoptError:
		usage()
		sys.exit(2)
	talk = True
	port = 5666
	for o, a in opts:
		if o in ["-h", "--help"]:
			usage()
			sys.exit()
		elif o in ["-q", "--quiet"]:
			talk = False
		elif o in ["-p", "--port"]:
			port = int(a)
		elif o in ["-v", "--version"]:
			print VERSION
			sys.exit()

	print "Verse Master Server v%s by Emil Brink (c) 2005 PDC, KTH." % VERSION
	print "Licensed under the BSD License."

	db = Database(port, talk)

	while 1:
		db.clean()
		v.callback_update(250000)
