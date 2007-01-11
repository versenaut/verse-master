#!/usr/bin/env python
#
# A sample template script to take the output from "client.py", and format it
# into a web page for publishing. Assumes we can run in a POSIX shell environment,
# and have input piped in on sys.stdin.
#
# A suitable command-line might be:
#
# ./client.py -q -duration=2 -n | ./pagebuilder.py >test.html
#
# Written by Emil Brink, PDC KTH in 2007. Released as public domain.
#

import sys
import time

def tokenize(s):
	tokens = []
	quote = False
	token = ""
	for c in s:
		if c == " " and not quote:	# Spaces separate tokens.
			if len(token) > 0:
				tokens += [token]
				token = ""
		elif c == '"':
			if quote:
				quote = False
			else:
				quote = True
		else:
			token += c
	if token != "" and not quote:
		tokens += [token]
	return tokens

def escape(s):
	es = ""
	for c in s:
		if c == '"':	es += "&quot;"
		elif c == '<':	es += "&lt;"
		elif c == '&':	es += "&amp;"
		else:		es += c
	return s

servers = []

for line in sys.stdin:
	servers += [line.strip()]

print """<http>
<head>
 <title>Verse Master Server Index</title>
 <style type="text/css">
  body { background-color: #ddddff; margin-left: 10%; margin-right: 10%; }
  table { border: thin solid #222244; }
  th { background-color: #222244; color: #ddddff; }
  tr.odd { background-color: #aaaacc; }
  tr.even { background-color: #eeeeff; }
 </style>
</head>

<body>
<h1>Verse Servers Currently Available</h1>
<p>
This page lists the public <a href="http://verse.blender.org/">Verse</a> servers that are
currently up and running. To use Verse applications, you always need a server to connect to.
However, you do not need to connect to a remote, "strange" server. The software needed to
run your own server locally (perhaps on your own desktop PC) is
<a href="http://www.uni-verse.org/">openly available</a>, and it does not require much from
your computer.
</p>
"""

print """<table align="center" width="80%" cellpadding="4" cellspacing="0">
<tr>
 <th align="left" width="35%">Server Address</th>
 <th align="left">Description</th>
</tr>
"""

cls = "even"
for s in servers:
	tok = tokenize(s)
	print "<tr class=\"%s\"><td><tt>%s</tt></td>" % (cls, tok[0])
	de = ""
	if len(tok) > 1:
		for t in tok[1:]:
			if t.startswith("DE="):
				de = escape(t[3:])
	print "<td>%s</td>" % de
	print "</tr>"

	if cls == "even":	cls = "odd"
	else:			cls = "even"
print "</table>"

print "<p>The above list was generated at %s, UTC, by quering the Verse master server.</p>" % time.strftime("%Y-%m-%d, %H:%M:%S", time.gmtime())

print """
<p>
Because Verse is not a standardized protocol known by web browsers, you cannot click the above
addresses. Instead, you need to copy the address to the Verse application of your choice. When
doing so, please don't forget the colon and the subsequent number, if present.
</p>

</body>
</html>
"""
