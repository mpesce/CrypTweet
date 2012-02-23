#!/usr/local/bin/python
#
# Transmit and receive cryptweet module for standalone web application.  
# Should work both desktop and mobile.
#
"""
txrx manages all the communications with Twitter, and encyption/decryption of tweets.

Homepage and documentation: http://plexusproject.org/cryptweet/

Copyright (c) 2012, Mark Pesce.
License: MIT (see LICENSE for details)
"""

__author__ = 'Mark Pesce'
__version__ = '0.04.dev'
__license__ = 'MIT'

import os, sys, json, logging, urllib2, base64, time, hashlib, string 
import keyring, packet
import twitter, rsa, pyDes

public_keyserver = "plexusproject.org"		# This may change
oauth_fn = os.path.join(os.path.expanduser('~'),'.cryptweet-oauth')	# OAuth credentials

def get_oauth_tokens(fn):
	""" Given a filename, return our OAuth tokens """
	if os.path.isfile(oauth_fn):  # Does the token file exist?
		tokens = twitter.oauth.read_token_file(oauth_fn)
		return tokens
	return None

# Try to get a key from the public keyserver
# If it's not accessible, attempt to fail gracefully.
#
def key_from_server(uname):
	""" Try to get a key from the public keyserver
	If it's not available, attempt to fail gracefully, returning NONE"""

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
		logging.error("Failed urlopen in key_from_server")
		return None
	return retkey	

def open_twitter():
	"""Do the basic OAuth dance with twitter"""
	# Establish a connection to Twitter
	fn = oauth_fn

	con_secret = "pG9hrZAUURqyDTfBbJcgAMdpemBmgAdZDL92ErVELY"
	con_key = "JwCegsVjfjfK0GvsQkpUw"

	# Get the file with our OAuth tokens
	if os.path.isfile(fn):  # Does the token file exist?
		tokens = twitter.oauth.read_token_file(fn)
	else:                   # If not, do authorization, create file
		logging.error('No Twitter authorization; you need to run cryptweet-setup.')
		return None

	retval = twitter.Twitter(auth = twitter.OAuth(token=tokens[0],
							token_secret=tokens[1],
							consumer_secret=con_secret, 
							consumer_key=con_key))
	return retval


def packetize_msg(msg):
	"""Packetize an encrypted message
	It becomes 3 strings, returned in a tuple."""

	# Packetize the encrypted message (should be done by packet.Packet, eventually)
	# We rely on the fact that these messages should be 344 characters in length.
	# If that changes all of this will break.  Possibly.
	#
	sequence_number = int((time.time() * 10) % 1000000)  # Generate sequence number from time, should be relatively unique

	top_half = msg[0:127]
	middle_half = msg[127:255]
	bottom_half = msg[255:]

	seq1 = str(sequence_number) + ".1:" + top_half
	seq2 = str(sequence_number) + ".2:" + middle_half
	seq3 = str(sequence_number) + ".3:" + bottom_half

	return (seq1, seq2, seq3)

def send_cryptweet(uname, msg):
	"""Basically all of cttx.py in a single function.
	Ain't programming grand?
	Will return a tuple (success, error data), which will be None if no error thrown"""

	msg = msg.encode('ascii', 'ignore')	# Convert to ASCII
	if len(msg) > 140:
		logging.warning('DMs are limited to 140 characters -- message truncated!')
		msg = msg[0:139]	# Truncate the message

	# Encrypt message, and transform to base64 representation for transmission
	pubkey = keyring.get_key_by_name(uname)
	if pubkey is None:
		return (False, "No public key!")
	#logging.debug("Public key %s" % (pubkey, ))
	#logging.debug("Message is %s" % (msg, ))

	crypt_msg = rsa.encrypt(msg, pubkey)
	crypt_msg_64 = base64.b64encode(crypt_msg)
	sequence = packetize_msg(crypt_msg_64)
	tw = open_twitter()
	success = False
	if tw != None:
		logging.debug("Sending encrypted DM...")
		try:
			result = tw.direct_messages.new(user=uname, text=sequence[0])
			result = tw.direct_messages.new(user=uname, text=sequence[1])
			result = tw.direct_messages.new(user=uname, text=sequence[2])
			success = True

		except twitter.TwitterError as e:
			logging.error('Could not send the DM.  Is it possible %s is not following you?' % (uname,))
			logging.error(e)

		except twitter.TwitterHTTPError as e:
			logging.error('Could not communicate with Twitter.  Please try again later.')
			logging.error(e)
		
		except:			# Not sure what's gone wrong here.
			logging.error('You got some other kind of error: %s' % (sys.exc_info(),))
			e = sys.exc_info()

	if success:
		return (True, None)
	else:
		return (False, e)

def decode_private_key(p1, p2, p3, p4):
	"""Given the four passwords, return the private key, or None if decryption fails"""

	# Before anything else, let's get the four passwords.
	whole_pass = p3+p1+p2+p4   # Concatenate the passwords

	#
	# Create a 48-bit has based on the string of the passwords
	# Then, based on the value of bit 7 of the last byte,
	# Use either the upper or low half of the hash value
	# Because TripleDES requires a 24-bit seed key thingy.
	#
	scram = hashlib.sha384(whole_pass).digest()
	hi_lo = ord(scram[47]) & 0x80  # Use the hash to figure out which half to use
	if hi_lo:
		scram_half = scram[:24]
	else:
		scram_half = scram[24:]

	# Create a TripleDES encryptor for the key 
	k = pyDes.triple_des(scram_half, pyDes.CBC, "\0\0\0\0\0\0\0\0", pad=None, padmode=pyDes.PAD_PKCS5)  # Create encryptor

	privkey_fn = os.path.join(os.path.expanduser('~'),'.cryptweet-privkey-sec') # Path to secure private keyfile
	privkey_encrypted_file = open(privkey_fn, "rb")		# Must be binary for Win7 compatibility
	privkey_encrypted = privkey_encrypted_file.read()
	privkey_encrypted_file.close()	

	# Decrypt the file, if we can, then convert it to an object
	try:
		privkey_pem = k.decrypt(privkey_encrypted)
		privkey = rsa.PrivateKey.load_pkcs1(privkey_pem, format='PEM') # @sylmobile bug reported 12 Feb
	except:
		logging.warning("Encryption failure -- bad passwords?")
		return None

	return privkey

# 
# Return tuple (True, sequence id, frame number, data) if this DM begins with a sequence value
#
def test_dm_sequence(dm_text):

	parts = string.split(dm_text,'.')	# Should start with a sequence id followed by a period separator
	if len(parts) < 2:		# Not in there at all?
		return (False,)		# Nup, bail
	try:
		seq_id = int(parts[0])	# Test for integerness
	except ValueError:
		return (False,)		# Not an integer, bail

	rest = string.split(parts[1],':') # Should be there if there's a sequence number
	if len(rest) < 2:		# Not in there at all?
		return (False,)		# Nup, bail
	try:
		frame_num = int(rest[0])	# Test for integerness
	except ValueError:
		return (False,)		# Not an integer, bail

	return (True, seq_id, frame_num, rest[1])

def get_cryptweets(p1, p2, p3, p4, quenta):
	"""Get the decrypted messages, if any.
	Returns a tuple (success, list_of_msgs)"""

	#
	# Setup to receive and assemble packets.  Read in the private key.
	#
	pa = packet.PacketAssembler()
	private_key = decode_private_key(p1, p2, p3, p4)
	if private_key is None:
		return (False, "Failed to authenticate private key.")

	# Let's get some DMs
	#
	#print 'Getting DMs from %d...' % (last_id,)
	logging.debug("Getting DMs...")
	twapi = open_twitter()
	try:
		results = twapi.direct_messages(count=quenta)
	except twitter.TwitterError as e:
		logging.error("Could not retrieve Direct Messages from Twitter.")
		logging.error(e)
		return (False, e)
	except twitter.TwitterHTTPError as e:
		logging.error("Having a problem communicating with Twitter.")
		logging.error(e)
		return (False, e)
	logging.debug("DMs received.")

	for message in results:
		#print message['sender']['screen_name']
		#print message['id'], message['text']
		is_msg = test_dm_sequence(message['text'])
		if is_msg[0]:
			#print 'Match on id %d' % (message['id'])
			pa.addPacket(sequence_id=is_msg[1],
					frame_number=is_msg[2], 
					user_name = message['sender']['screen_name'],
					size=3, 
					data=is_msg[3], created=message['created_at'])

	msg_list = []
	pic_list = {}

	for pkt in pa.packets:
		if pkt.areWeThereYet():		# Is the packet completed?

			crypt64_msg = pkt.getString()
			#print pkt.id, pkt.getString()
			try:
				crypt_msg = base64.standard_b64decode(crypt64_msg)
				try:
					msg = rsa.decrypt(crypt_msg, private_key)

				except rsa.DecryptionError:
					return (False, "Could not decrypt message -- incorrect private key?")

				# If we've already got the picture, don't add it again
				if pkt.uname in pic_list:
					pic_url = pic_list[pkt.uname]
				else:

					# Do a Twitter lookup for the user, return URL for photo
					try:
						#logging.debug("Fetching image URL for %s" % (pkt.uname,))
						user_data = twapi.users.lookup(screen_name=pkt.uname)
						#logging.debug(user_data[0]['profile_image_url'])
					except twitter.TwitterError as e:
						logging.error('Error retrieving user data from Twitter.')
						logging.error(e)
						user_data = None
					except twitter.TwitterHTMLError as e:
						logging.error('Error communicating with Twitter.')
						logging.error(e)
						user_data = None
				
					# If there is user data, extract the profile image URL to send back
					if user_data:
						pic_url = user_data[0]['profile_image_url']
						pic_list[pkt.uname] = pic_url	# Add to dictionary
						#logging.debug("Adding %s with picture url of %s" % (pkt.uname, pic_url))
					else:
						pic_url = None
				msg_list.append(((pkt.uname, pic_url, pkt.created), msg))

			except TypeError:
				return (False, "Decode error, could not decrypt message")

	return (True, msg_list)



