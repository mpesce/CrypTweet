#
# Send a single, RSA-encrypted DM to a given account
#
"""
cttx sends an encrypted DM to a Twitter user.

Homepage and documentation: http://plexusproject.org/cryptweet/

Copyright (c) 2012, Mark Pesce.
License: MIT (see LICENSE for details)
"""

__author__ = 'Mark Pesce'
__version__ = '0.03.dev'
__license__ = 'MIT'

import os, base64, time, sys, urllib2, json
from optparse import OptionParser
import rsa, twitter
import keyring

public_keyserver = 'plexusproject.org'		# This may change.  

# First thing, parse the command-line options, if any.
parser = OptionParser()
parser.add_option("-u", "--user", dest="uname", help="destination Twitter user name")
parser.add_option("-m", "--msg", dest="msg", help="Message text in quotes - maximum 140 characters")
parser.add_option("-f", "--force", action="store_true", dest="force_server", default=False, 
			help="Force search of keyserver for public key")
(options, args) = parser.parse_args()

# If we have a user name, use it.
uname = options.uname
msg = options.msg
force_srv = options.force_server

# Try to get a key from the public keyserver
# If it's not accessible, attempt to fail gracefully.
#
def key_from_server(uname):
	the_url = 'http://' + public_keyserver + ':8118/' + uname
	try:
		f = urllib2.urlopen(the_url)	# Open the URL
		data_json = f.read()			# Read in the data
		try:
			data = json.loads(data_json)	# Try to convert it to real object stuff
			try:
				retkey = rsa.PublicKey.load_pkcs1(data, format='PEM')  # Convert to public key object
			except:
				return None
		except:
			return None
	except:
		return None
	return retkey	

# Packetize an encrypted message
# It becomes 3 strings, returned in a tuple.
#
def packetize_msg(msg):

	# Packetize the encrypted message (should be done by packet.Packet, eventually)
	# We rely on the fact that these messages should be 344 characters in length.
	# If that changes all of this will break.  Possibly.
	#
	sequence_number = int((time.time() * 10) % 1000000)  # Generate sequence number from time, should be relatively unique

	top_half = crypt_msg_64[0:127]
	middle_half = crypt_msg_64[127:255]
	bottom_half = crypt_msg_64[255:]

	seq1 = str(sequence_number) + ".1:" + top_half
	seq2 = str(sequence_number) + ".2:" + middle_half
	seq3 = str(sequence_number) + ".3:" + bottom_half

	return (seq1, seq2, seq3)

# Do the basic OAuth dance with Twitter
#
def open_twitter():
	# Establish a connection to Twitter
	fn = os.path.join(os.path.expanduser('~'),'.cryptweet-oauth')

	con_secret = "pG9hrZAUURqyDTfBbJcgAMdpemBmgAdZDL92ErVELY"
	con_key = "JwCegsVjfjfK0GvsQkpUw"

	# Get the file with our OAuth tokens
	if os.path.isfile(fn):  # Does the token file exist?
		tokens = twitter.oauth.read_token_file(fn)
	else:                   # If not, do authorization, create file
		print 'No Twitter authorization; you need to run cryptweet-setup.'
		return None

	retval = twitter.Twitter(auth = twitter.OAuth(token=tokens[0],
							token_secret=tokens[1],
							consumer_secret=con_secret, 
							consumer_key=con_key))
	return retval

# 
# At this point we'll look into the local database of public keys
# To see if we can find one which matches the given username
# If not, we go out to the keyserver to see if it knows about it.
#
def get_key_by_name(uname):
	pubkey = keyring.get_key_by_name(uname)
	if pubkey == None:
		print "No matching public key, checking the keyserver..."
		pubkey = key_from_server(uname)
		if pubkey != None:
			print 'Found the public key in the keyserver, adding to local keyring...'
			# Add the key to our local list of keys
			keyring.add_key(uname, 8118, pubkey)
		else:
			print 'Could not find a public key for %s, aborting...' % (uname,)
			return None
	return pubkey

#
# Get the username.  Try to find a matching public key for encyrption.
#
success = False
if uname == None:
	uname = raw_input("Twitter Username of Recipient: ")

# If we're forced to, go to the keyserver
#
if force_srv:
	print 'Forcing a search of the keyserver...'
	pubkey = key_from_server(uname)
	if pubkey != None:
		print 'Found the public key in the keyserver, adding to local keyring...'
		# Add the key to our local list of keys
		keyring.add_key(uname, 8118, pubkey)
	else:
		print 'Could not find a public key for %s, aborting...' % (uname,)
		sys.exit(0)
else:
	pubkey = get_key_by_name(uname)		# Do we have a key matching that name?

# Now get the message text, encrypt it, and convert to base64 representation
#
if pubkey != None:
	if msg == None:
		msg = raw_input('Message to encode: ')
	if len(msg) > 140:
		print 'DMs are limited to 140 characters -- message truncated!'
		msg = msg[0:139]	# Truncate the message

	# Encrypt message, and transform to base64 representation for transmission
	crypt_msg = rsa.encrypt(msg, pubkey)
	crypt_msg_64 = base64.b64encode(crypt_msg)
	sequence = packetize_msg(crypt_msg_64)
	tw = open_twitter()
	if tw != None:
		print "Sending encrypted DM..."
		try:
			result = tw.direct_messages.new(user=uname, text=sequence[0])
			result = tw.direct_messages.new(user=uname, text=sequence[1])
			result = tw.direct_messages.new(user=uname, text=sequence[2])
			success = True

		except twitter.TwitterError as e:
			print 'Could not send the DM.  Is it possible %s is not following you?' % (uname,)
			print e

		except twitter.TwitterHTTPError as e:
			print 'Could not communicate with Twitter.  Please try again later.'
			print e
		
		except:			# Not sure what's gone wrong here.
			print 'You got some other kind of error: %s' % (sys.exc_info(),)
if success:
	print "Encrypted DM was sent to %s.  Good bye!" % (uname,)
else:
	print "The message was not sent.  Sorry."
