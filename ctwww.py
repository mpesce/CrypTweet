#!/usr/local/bin/python
#
# CrypTweet standalone web application.  Should work both desktop and mobile.
#
"""
ctwww runs a webserver which provides an interface to CrypTweet.

Homepage and documentation: http://plexusproject.org/cryptweet/

Copyright (c) 2012, Mark Pesce.
License: MIT (see LICENSE for details)
"""

__author__ = 'Mark Pesce'
__version__ = '0.03.dev'
__license__ = 'MIT'

import os, sys, json, logging, urllib2, base64, time 
from optparse import OptionParser
import txrx, websetup, keyring
import bottle, twitter, rsa, daemon

portnum = 8080		# Default port number
hostname = "localhost"	# No place like home
public_keyserver = "plexusproject.org"		# This may change
oauth_fn = os.path.join(os.path.expanduser('~'),'.cryptweet-oauth')	# OAuth credentials
basedir = os.getcwd()		# Need this for bottlepy to find its templates.
logging_fn = os.path.join(os.path.expanduser('~'),'.cryptweet-weblog')

def get_oauth_tokens(fn):
	""" Given a filename, return our OAuth tokens """
	if os.path.isfile(oauth_fn):  # Does the token file exist?
		tokens = twitter.oauth.read_token_file(oauth_fn)
		return tokens
	return None

def parse_options():
	""" Parse all of the command line options, return them as a tuple (options, arguments)"""

	# First thing, parse the command-line options, if any.
	usage = "usage: %prog start|stop|nodaemon [options]"
	parser = OptionParser(usage=usage)
	parser.add_option("-p", "--port", dest="portnum", help="port number (default is port 8080)")
	parser.add_option("-n", "--name", dest="hostname", help="hostname (default is localhost)")
	(o,a) = parser.parse_args()
	return (o,a)

def setup_webserver():
	"""Establish all of the routes for the webserver functionality.
	Have a look through the bottle documentation at http://bottlepy.org/ for details on how this works."""
	pubkey = None
	@bottle.route('/')
	def root():
		"""Serve up the root webpage, or the setup page, if we're not setup"""		
		if websetup.check_twitter_auth() is False:
			if websetup.make_twitter_auth() is False:
				return "OAuth failure."
		return bottle.template('newroot')

	@bottle.route('/image/<filename>')
	def send_image(filename):
		whole_thingy = 'www/media/%s' % (filename, )
		image = open(whole_thingy, 'r')
		return image

	@bottle.route('/action', method='POST')		# Reading or Sending?
	def take_action():
		readme = bottle.request.forms.read
		sendme = bottle.request.forms.send
		if readme:
			logging.debug('READ action')
			return bottle.template('getpass')
		elif sendme:
			logging.debug('SEND action')
			return bottle.template('pickuser')
		else:
			return "We got nutthin"

	@bottle.route('/read')
	def read_action():
		return bottle.template('getpass')

	@bottle.route('/send')
	def send_action():
		return bottle.template('pickuser')

	@bottle.route('/pickuser', method='POST')
	def pickuser():
		global pubkey
		uname = bottle.request.forms.uname
		force_lookup = bottle.request.forms.force_lookup
		logging.debug(force_lookup)
		if force_lookup == 'on':
			pubkey = None
			logging.debug("Forcing public key retreival from server")
		else:
			pubkey = keyring.get_key_by_name(uname)
		if pubkey:
			return bottle.template('sendmsg', user=uname)
		else:
			pubkey = txrx.key_from_server(uname)
			if pubkey:
				#return 'Found the public key for %s in the keyserver, adding to local keyring...' % (uname, )
				# Add the key to our local list of keys
				keyring.add_key(uname, 8118, pubkey)
				return bottle.template('sendmsg', user=uname)
			else:
				return bottle.template('nouser', user=uname)

	@bottle.route('/sendmsg', method='POST')
	def sendmsg():
		msg_text = bottle.request.forms.msg		
		uname = bottle.request.forms.uname
		result = txrx.send_cryptweet(uname, msg_text)		# OK, have at it.
		if result[0]:
			return bottle.template('sendok', user=uname)
		else:
			return bottle.template('sendfail', err=result[1])

	@bottle.route('/getmsgs', method='POST')
	def getmsgs():
		p1 = bottle.request.forms.pass1
		p2 = bottle.request.forms.pass2
		p3 = bottle.request.forms.pass3
		p4 = bottle.request.forms.pass4
		howmany = bottle.request.forms.howmany
		#logging.debug(howmany)
		(success, msglist) = txrx.get_cryptweets(p1, p2, p3, p4, howmany)
		if success:
			return bottle.template('showmsgs', msglist=msglist)
		else:
			return bottle.template('getfail', err=msglist)

def run_webserver():
	"""Starts the webserver up.
	This function will block until a KeyBoardInterrupt exception is caught"""
	global hostname, portnum
	#bottle.debug(True)	# While in development, we want the data
	bottle.run(host=hostname, port=portnum) 
	logging.info("Exiting server.")

class CTWebDaemon(daemon.Daemon):
	def run(self):
		os.chdir(basedir)	# Correctly set the working directory.
		setup_webserver()
		run_webserver()

def start_it(options, a):
	global portnum, hostname
	logging.basicConfig(filename=logging_fn, level=logging.DEBUG, 
		format='%(asctime)s - %(levelname)s - %(message)s')
	if options.portnum:
		if (int(options.portnum) > 0) & (int(options.portnum) < 65536):	# Within legal boundaries?
			portnum = options.portnum
		else:
			logging.warning("Port %s illegal, using port 8080 for server." % (options.portnum,))
	if options.hostname:
		hostname = options.hostname
	startstr = "Webserver daemon starting."
	logging.debug(startstr)
	dmon = CTWebDaemon(pidfile=os.path.join(os.path.expanduser('~'),'.cryptweet-webserver-pid'))
	dmon.start()

def stop_it():
	logging.basicConfig(filename=logging_fn, level=logging.DEBUG, 
		format='%(asctime)s - %(levelname)s - %(message)s')
	logging.info("Webserver daemon stopping.")
	dmon = CTWebDaemon(pidfile=os.path.join(os.path.expanduser('~'),'.cryptweet-webserver-pid'))
	dmon.stop()

if __name__ == '__main__':

	(options, args) = parse_options()
	if options.portnum:
		if (int(options.portnum) > 0) & (int(options.portnum) < 65536):	# Within legal boundaries?
			portnum = options.portnum
		else:
			logging.warning("Port %s illegal, using port 8080 for server." % (options.portnum,))
	if options.hostname:
		hostname = options.hostname

	if len(sys.argv) >= 2:

		if 'start' == sys.argv[1]:
			logging.basicConfig(filename=logging_fn, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
			startstr = "Webserver daemon starting."
			logging.debug(startstr)
			dmon = CTWebDaemon(pidfile=os.path.join(os.path.expanduser('~'),'.cryptweet-webserver-pid')) # Create daemon
			dmon.start()

		elif 'stop' == sys.argv[1]:
			logging.basicConfig(filename=logging_fn, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
			logging.info("Webserver daemon stopping.")
			dmon = CTWebDaemon(pidfile=os.path.join(os.path.expanduser('~'),'.cryptweet-webserver-pid')) # Create daemon
			dmon.stop()


		elif 'nodaemon' == sys.argv[1]:
			"""Main entry point when invoked from the command line"""
			logging.basicConfig(level=logging.DEBUG,format='%(asctime)s - %(levelname)s - %(message)s')
			setup_webserver()
			run_webserver()
		else:
			print "usage: ctwww.py start|stop|nodaemon [options]"

	else:
		print "usage: ctwww.py start|stop|nodaemon [options]"


