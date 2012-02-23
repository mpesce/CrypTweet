#!/usr/bin/python
#
"""This small script will try to start/stop the daemon
   Based upon whether the daemon is already running."""

import os
from optparse import OptionParser
import ctwww

pid_fn = os.path.join(os.path.expanduser('~'),'.cryptweet-webserver-pid')
options = None
arguments = None

def parse_options():
	""" Parse all of the command line options, return them as a tuple (options, arguments)"""

	# First thing, parse the command-line options, if any.
	usage = "usage: %prog [options]"
	parser = OptionParser(usage=usage)
	parser.add_option("-p", "--port", dest="portnum", help="port number (default is port 8080)")
	parser.add_option("-n", "--name", dest="hostname", help="hostname (default is localhost)")
	(o,a) = parser.parse_args()
	return (o,a)

def doit():
	"""All the work is done here.
	Check to see if the daemon is running.
	If it is not running, start it.
	If it is running, stop it."""

	if os.path.isfile(pid_fn):	# pid exists, we're running
		ctwww.stop_it()
		print 'CrypTweet webserver stopped.'
	else:
		global options, arguments
		print 'CrypTweet webserver starting...'
		ctwww.start_it(options, arguments)

if __name__ == '__main__':
	(options, arguments) = parse_options()
	doit()
