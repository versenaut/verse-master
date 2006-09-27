#!/usr/bin/env python
#
# A Verse Master Server. Maintains a list of announced servers, and can send that list
# to interested clients upon request. The list entries time out if not refreshed.
#

import getopt
import sys
import time

import verse as v

VERSION     = "0.4"
VERSE_PORT  = 4950

QUEUE_SIZE  = 512	# Number of outstanding DESCRIBE servers we have, at the most.
MAX_PER_IP  = 4		# Maximum number of servers allowed per IP address.
SERVER_TIMEOUT = 137.0	# Max time, in seconds, between ANNOUNCEs, or server is kicked.
LIST_PERIOD = 0.5	# Period between successive list packets to a single client.

def strip_ip(ip):
	"""Strips an IP:port address into just the IP, which is returned as a string."""
	if ip == None: return None
	if ":" in ip:
		colon = ip.index(":")
		return ip[:colon]
	return ip

def is_tag(string):
	"""Validate a string as being a valid tag name."""
	if string[0].islower():
		for x in string[1:]:
			if not (x.islower() or x.isdigit() or x == '_'):
				return False
		return True
	return False

class QueueEntry:
	def __init__(self, ip = None):
		self.ip = None
		self.justip = strip_ip(self.ip)
		self.time = None

	def update(self, ip):
		self.ip = ip
		self.justip = strip_ip(ip)
		self.time = time.time()
		v.send_ping(ip, "DESCRIBE DE,TA")	# Ask the server to describe itself to us.

	def clear(self):
		self.ip = None
		self.justip = None

	def is_valid(self):
		return self.ip != None

	def has_ip(self, ip):
		return self.justip == ip

	def has_address(self, ip):
		return self.ip == ip


class Queue:
	def __init__(self, size = QUEUE_SIZE):
		self.queue = [QueueEntry() for x in xrange(size)]
		self.next = 0
		self.load = 0

	def enqueue(self, ip):
		self.queue[self.next].update(ip)
		self.next += 1
		self.next %= len(self.queue)
		self.load += 1

	def unqueue(self, ip):
		for i in xrange(len(self.queue)):
			qe = self.queue[i]
			if qe.has_address(ip):
				self.queue[i].clear()
				self.load -= 1
				return True
		return False

	def contains(self, ip):
		"""Go through the entries list, and check if the given IP is there. Returns (boolean, count)."""
		short = strip_ip(ip)
		count = 0
		for e in self.queue:
			if e.ip == None: continue
			if e.has_address(ip):
				return (True, count)
			elif e.has_ip(short):
				count += 1
			else:
				print "No match for", e.ip
		return (False, count)

	def get_load(self):
		return self.load % len(self.queue)


class Database:
	class Entry:
		@classmethod
		def quote(cls, s):
			"""Quote a string to comply with the Master server protocol's quoting rules."""
			qs = ""
			for x in s:
				if x == '"': x = "\\\""
				elif x == "\\": x = "\\\\"
				qs += x
			return qs

		def __init__(self, ip):
	    		if ":" in ip:
				colon = ip.index(":")
				self.ip = ip[:colon]
				self.port = int(ip[colon+1:])
			else:
				self.ip = ip
				self.port = VERSE_PORT
			self.key = "%s:%u" % (self.ip, self.port)
			self.desc = ""
			self.tags = [ ]
			self.time = 0

		def set_desc(self, desc):
			self.desc = Database.Entry.quote(desc)

		def set_tags(self, tags):
			ts = tags.split(",")
			self.tags = [t for t in ts if is_tag(t)]	# Replace with any valid tags.
			print "tags now:", self.tags

		def touch(self):
			self.time = time.time()

		def filter_tags(self, incl = None, excl = None):
			"""Filters based on two lists of tags to include and exclude."""
			if incl != None:
				for i in incl:
					if not i in self.tags: return False
			if excl != None:
				for e in excl:
					if e in self.tags: return False
			return True

		def build_list(self, what):
			txt = " "
			if what.has_key("IP"):
				txt += "IP=" + self.ip
				if self.port != VERSE_PORT:
					txt += ":%u" % self.port
				if what.has_key("IP"):
					for w in what["IP"]:
						if w == "DE":
							txt += " DE=\"%s\"" % self.desc
			return txt

	class ListJob:
		"""A bunch of MS:LISTS packets, with a target address."""
		def __init__(self, ip, packets):
			self.ip = ip
			self.packets = packets
			self.time = time.time()
			self.start = self.time

		def flush(self):
			now = time.time()
			if now - self.time >= LIST_PERIOD:
				v.send_ping(self.ip, self.packets[0])
				self.packets = self.packets[1:]
				self.time = now
			return len(self.packets) == 0

		def age(self):
			return time.time() - self.start

	class ListJobs:
		"""A bunch of ListJob instances."""
		def __init__(self):
			self.jobs = []
			self.ip = None
			self.olen = 0

		def add(self, ip, packets):
			if len(packets) > 0:	# No point in sending out an empty list.
				j = Database.ListJob(ip, packets)
				self.jobs += [j]
				self.ip = ip
				self.olen = len(packets)

		def flush(self):
			for j in self.jobs:
				if j.flush():
					print "Sent", self.olen, "packets of MS:LIST data to", self.ip
					self.jobs.remove(j)

	def __init__(self, port = 5666, talk = True):
		"""Create new empty database and request handler. It's a ... mashup."""
		self.queue = Queue()
		self.servers = {}
		self.talk = talk
		self.talked_last = time.time()
		self.listjobs = Database.ListJobs()
		if self.talk:
			print "Listening to port %u, ready for use." % port
		v.set_port(port)
		v.callback_set(v.SEND_PING,	self._cb_ping)

	def _parse(self, cmd):
		"""Parse a received command into a dictionary of keyword=value pairs. Understands the
		   quoting rules for Verse master server commands. This is a bit hackish, maybe."""
		kw = { }
		i = 0
		l = len(cmd)
#		print "parsing '%s', %u chars" % (cmd, l)
		while i < l:
			here = cmd[i]
			if here.isspace():
				i += 1
				continue
			if here.isupper():
				key = ""
				while i < l and cmd[i].isupper():
					key += cmd[i]
					i += 1
				if cmd[i] == '=':
					i += 1
					v = ""
					if cmd[i] == '"':	# Quoted string?
						i += 1
						while i < l and not cmd[i] == '"':
							if cmd[i] == '\\':
								if i + 1 < l:
									i += 1
								else:
									print "Error in quoting, aborting"
									return None
							v += cmd[i]
							i += 1
						if i < l and cmd[i] == '"':
							i += 1		# Skip final quote.
						else:
							print "Missing final quote, aborting"
							return None
					else:
						while i < l and not cmd[i].isspace():
							if cmd[i] == '"' or cmd[i] == '\\':
								print "No quotes or backslashes in unquoted strings please, aborting"
								return None
							v += cmd[i]
							i += 1
					kw[key] = v
				else:
					print "Keyword '%s' not followed by equals sign, aborting" % key
					return None
			else:
				print "Expected upper-case key name, aborting"
				return None
		return kw

	# -----------------------------------------------------------------------------------------------------

	def announce(self, ip):
		"""Handle an incoming announce-message from (presumably) a Verse server somewhere."""
		# First, check if the server is already registered.
		if self.servers.has_key(ip):
			# Yes, so just touch the entry to keep it alive, don't reply.
			e = self.servers[ip]
			tl = SERVER_TIMEOUT - (time.time() - e.time)
			e.touch()
			if self.talk:
				print "Got ANNOUNCE from known server", ip, "updating entry (%.3f s left)" % tl
			return
		# If not found, go through the wait-queue, and see if we already have an outstanding
		# request to that particular server.
		(known, count) = self.queue.contains(ip)
		if count >= MAX_PER_IP:
			if self.talk:
				print "Ignoring ANNOUNCE from", ip + ", already have", count, "queued from the same IP"
			return
		# Check that there are not too many *registered* servers from this IP, either.
		adr = strip_ip(ip)
		for e in self.servers.values():
			if e.ip == adr:
				count += 1
			if count >= MAX_PER_IP:
				break
		if count >= MAX_PER_IP:
			if self.talk:
				print "Ignoring ANNOUNCE from", ip + ", already have", count, "queued or registered from that IP"
			return
		self.queue.enqueue(ip)
		if self.talk:
			print "Got ANNOUNCE from unknown server", ip +", queued (%u queued now)" % self.queue.get_load()

	def description(self, ip, tail):
		# Check if the IP is for a known server.
		if self.servers.has_key(ip):
			# Yes, so just touch the entry to keep it alive.
			e = self.servers[ip]
			e.touch()
			return
		# If unknown, see if it's in the queue of servers wanting in.
		if self.queue.unqueue(ip):
			e = Database.Entry(ip)
			self.servers[e.key] = e
			e.touch()
			pa = self._parse(tail)
			if pa != None and pa.has_key("DE"):
				e.set_desc(pa["DE"])
			if pa != None and pa.has_key("TA"):
				e.set_tags(pa["TA"])
			print "Registered server at", ip, "now %u registered" % len(self.servers)

	def _parse_get_tags(self, tags):
		"""Parse a list of tags, which can include minus to exclude a tag. Returns a pair
		   of lists of tags to include and exclude. Inclusion wins, since it filters more."""
		incl = []
		excl = []
		for t in tags.split(","):
			if t[0] == '-':
				if is_tag(t[1:]):
					excl += [t[1:]]
			else:
				if is_tag(t):
					incl += [t]
		# At this point, we need to filter out any self-contradicting items. For instance,
		# if you ask for "foo,-foo", foo wins since that filters harder.
		excl = [e for e in excl if not e in incl]
   		return (incl, excl)

	def _build_list(self, what, incl, excl):
		"""Build a list of MS:LIST packets, according to the given parameters."""
		packets = []
		pack = "MS:LIST"

#		print "building packet list,", len(self.servers.values()), "servers"		
		for e in self.servers.values():
			this = ""
			if e.filter_tags(incl, excl):
				h = e.build_list(what)
				if len(pack) + len(h) > 1390:
					packets += [pack]
					pack = "MS:LIST"
				pack += h
		if pack != "MS:LIST":
			packets += [pack]
		return packets

	def get(self, ip, args = None):
		what = { }
		incl = None
		excl = None
		if args != None:
			pa = self._parse(args)
			if pa.has_key("IP"):
				what["IP"] = [ f for f in pa["IP"].split(",") ]
			if pa.has_key("TA"):
				incl, excl = self._parse_get_tags(pa["TA"])
		packets = self._build_list(what, incl, excl)
		self.listjobs.add(ip, packets)

	def flush(self):
		self.listjobs.flush()

	def clean(self):
		"""Throw out servers that haven't pinged us in a while."""
		i = 0
		now = time.time()
		for e in self.servers.values():
			if now - e.time >= SERVER_TIMEOUT:
				print "Dropping", e.key + ", expired after %.1f seconds" % (now - e.time)
				del self.servers[e.key]
		if self.talk and now - self.talked_last > 10.0:
			print "There are now %u unique servers registered" % len(self.servers)
			self.talked_last = now

	def _cb_ping(self, address, message):
		if message.startswith("MS:ANNOUNCE"):
			self.announce(address)
		elif message.startswith("MS:GET"):
			self.get(address, message[6:])
		elif message.startswith("DESCRIPTION "):
			self.description(address, message[12:])
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
		opts, args = getopt.getopt(sys.argv[1:], "hp:qv", ["help", "quiet", "port=", "version"])
	except getopt.GetoptError:
		usage()
		sys.exit(2)
	talk = True
	port = VERSE_PORT	# By default, run the master server on the standard Verse port. Simplifies for clients.
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

	print "Verse Master Server v%s by Emil Brink (c) 2005-2006 PDC, KTH." % VERSION
	print "Licensed under the BSD License."

	db = Database(port, talk)

	while 1:
		db.flush()
		db.clean()
		v.callback_update(2500)
