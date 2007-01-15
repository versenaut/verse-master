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

print """<!doctype HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
 <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1"/>
 <title>Verse Servers Currently Available</title>
 <style type="text/css">
  body { background-color: white; margin-left: 10%; margin-right: 10%; }
  table { border: thin solid #222244; }
  th { background-color: #222244; color: #ddddff; }
  tr.odd { background-color: #aaaacc; }
  tr.even { background-color: #eeeeff; }
  img { border: none; }

  h1 { margin: 0px; }

  div.main { background-color: #ddddff; padding: 1em; border: thin solid #222244;}
  div.foot { text-align: right; font-size: 5px; }
 </style>
</head>

<body>
<a href="http://verse.blender.org/" border="0"><img src="http://verse.blender.org/cms/fileadmin/verse/gfx/verse_banner.png"/></a>
<div class="main">
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
 <th align="center" width="10%">Index</th>
 <th align="left" width="35%">Server Address</th>
 <th align="left">Description</th>
</tr>
"""

i = 0
for s in servers:
	tok = tokenize(s)
	print "<tr class=\"%s\"><td align=\"right\">%u</td><td><tt><a href=\"verse://%s\">%s</a></tt></td>" % (["even", "odd"][i & 1], i, tok[0], tok[0])
	de = ""
	if len(tok) > 1:
		for t in tok[1:]:
			if t.startswith("DE="):
				de = escape(t[3:])
	print "<td>%s</td>" % de
	print "</tr>"

	i += 1

print "</table>"

extra = ""
if i == 0:
	extra = "Perhaps the master server itself is down? Not good ..."
print "<p><b>%u</b> servers available, total. %s" % (i, extra)

print "<p>The above list was generated at %s (UTC), by quering the Verse master server at <tt>master.uni-verse.org</tt>.</p>" % time.strftime("%Y-%m-%d, %H:%M:%S", time.gmtime())

print """
<p>
Verse is not a standardized URI protocol, understood by web browsers. The server column above still contains
links with a verse: protocol type, since it might be useful to some. If clicking these addresses cannot be
made to work for you, you need to copy down the address text and manually input it in the Verse applications
you want to use. If doing so, please make sure you include the full address, especially if it ends in a colon
and a number (a port number specification).
</p>
<p>
Some links that might be of interest:
</p>
<ul>
<li><a href="http://www.uni-verse.org/">www.uni-verse.org</a>, the main site for the Uni-Verse project that currently funds Verse development.
<li><a href="http://mediawiki.blender.org/index.php/Uni-Verse:Main">Uni-Verse Documentation Wiki</a>, with end-user documentation for many programs released by the Uni-Verse consortium.
<li><a href="http://verse.blender.org/">verse.blender.org</a>, the main Verse web site. Contains information for developers.
</ul>
</div>
<div class="foot"><a href="http://projects.blender.org/viewcvs/viewcvs.cgi/verse-master/pagebuilder.py?rev=HEAD&cvsroot=verse&content-type=text/vnd.viewcvs-markup">Pagebuilder</a> by Emil Brink</div>
</body>
</html>
"""
