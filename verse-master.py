#!/usr/bin/env python
#
# A Verse Master Server. Maintains a list of announced servers, and can send that list
# to interested clients upon request. The list entries time out if not refreshed.
#

import getopt
import sys
import time

import verse as v

VERSION = "0.3"
VERSE_PORT = 4950
LIST_PERIOD = 0.5	# Period between successive list packets to a single client.

class Database:

	MAX_AGE = 0.5 * 60.0

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
			print "ListJob created for", ip, "with", len(packets), "packets of data"

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

		def add(self, ip, packets):
			if len(packets) > 0:	# No point in sending out an empty list.
				j = Database.ListJob(ip, packets)
				self.jobs += [j]

		def flush(self):
			for j in self.jobs:
				if j.flush():
					print "ListJob to", j.ip, "completed after", j.age(), "seconds"
					self.jobs.remove(j)

	def __init__(self, port = 5666, talk = True):
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

	def _is_tag(self, string):
		"""Validate a string as being a valid tag name."""
		if string[0].islower():
			for x in string[1:]:
				if not (x.islower() or x.isdigit() or x == '_'):
					return False
			return True
		return False

	def announce(self, ip, args = None):
		try:
			e = self.servers[ip]
		except:
			e = Database.Entry(ip)
			self.servers[e.key] = e
		e.touch()
		if args != None:
			pa = self._parse(args)
			if pa != None and pa.has_key("DE"):
				e.set_desc(desc = pa["DE"])	# Replace any previous description.
			if pa != None and pa.has_key("TA"):
				tags = pa["TA"].split(",")
				e.tags = [ t for t in tags if self._is_tag(t) ]	# Replaces any old tags.
		if self.talk:
			print "Added/updated entry for", e.key

	def _parse_get_tags(self, tags):
		"""Parse a list of tags, which can include minus to exclude a tag. Returns a pair
		   of lists of tags to include and exclude. Inclusion wins, since it filters more."""
		incl = []
		excl = []
		for t in tags.split(","):
			print "looking at", t
			if t[0] == '-':
				if self._is_tag(t[1:]):
					excl += [t[1:]]
			else:
				if self._is_tag(t):
					incl += [t]
		# At this point, we need to filter out any self-contradicting items. For instance,
		# if you ask for "foo,-foo", foo wins since that filters harder.
		excl = [e for e in excl if not e in incl]
   		return (incl, excl)

	def _build_list(self, what, incl, excl):
		"""Build a list of MS:LIST packets, according to the given parameters."""
		packets = []
		pack = "MS:LIST"
		
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
			if now - e.time >= self.MAX_AGE:
				print "Dropping", e.key, "as it has expired"
				del self.servers[e.key]
		if self.talk and now - self.talked_last > 10.0:
			print "There are now %u unique servers registered" % len(self.servers)
			self.talked_last = now

	def _cb_ping(self, address, message):
		if message.startswith("MS:ANNOUNCE"):
			self.announce(address, message[12:])
		elif message.startswith("MS:GET"):
			self.get(address, message[6:])
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

	# Prime the database with some fake entries. :)
	for a in xrange(100):
		db.announce("127.0.0.1:%u" % (4951 + a))

	while 1:
		db.flush()
		db.clean()
		v.callback_update(2500)
