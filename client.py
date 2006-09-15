#!/usr/bin/env python
#
# A testing client for the Verse master server.
#

import sys

import verse as v

def cb_ping(host, msg):
	print "Got '%s'" % msg, "from", host, "( len", len(msg), ")"

if __name__ == "__main__":

#	v.set_port(4590)
	v.callback_set(v.SEND_PING,	cb_ping)

	if len(sys.argv) == 0 or sys.argv[1] == "announce":
		v.send_ping("localhost:5666", "MS:ANNOUNCE")
	elif len(sys.argv) >= 1 and sys.argv[1] == "list":
		v.send_ping("localhost:5666", "MS:GET IP=\"DE\"")

	while 1:
		v.callback_update(250000)
