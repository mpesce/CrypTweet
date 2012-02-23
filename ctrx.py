#
# Receive the encrypted DMs and do our best to decrypt them
#
"""
ctrx receives encrypted Direct Messages.

Homepage and documentation: http://plexusproject.org/cryptweet/

Copyright (c) 2012, Mark Pesce.
License: MIT (see LICENSE for details)
"""

__author__ = 'Mark Pesce'
__version__ = '0.03.dev'
__license__ = 'MIT'

import os, sys, string, base64, getpass, hashlib
from optparse import OptionParser
import packet
import twitter, rsa, pyDes

# First thing, parse the command-line options, if any.
parser = OptionParser()
parser.add_option("-1", "--password1", dest="pass1", help="first password")
parser.add_option("-2", "--password2", dest="pass2", help="second password")
parser.add_option("-3", "--password3", dest="pass3", help="third password")
parser.add_option("-4", "--password4", dest="pass4", help="fourth password")
parser.add_option("-f", "--force", action="store_true", dest="force_dms", default=False, 
			help="Force retrieval of at least last 200 Direct Messages")
(options, args) = parser.parse_args()

def decode_private_key():

	# Before anything else, let's get the four passwords.
	print
	print "We need four passwords to decrypt your private key"
	print "Enter the words, one at a time, when prompted."
	print
	global options
	if options.pass1:
		p1 = options.pass1
	else:
		p1 = getpass.getpass("Password One: ")
	if options.pass2:
		p2 = options.pass2
	else: 
		p2 = getpass.getpass("Password Two: ")
	if options.pass3:
		p3 = options.pass3
	else:
		p3 = getpass.getpass("Password Three: ")
	if options.pass4:
		p4 = options.pass4
	else:
		p4 = getpass.getpass("Password Four: ")
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
	privkey_encrypted_file = open(privkey_fn, "r")
	privkey_encrypted = privkey_encrypted_file.read()
	privkey_encrypted_file.close()	

	# Decrypt the file, if we can, then convert it to an object
	try:
		privkey_pem = k.decrypt(privkey_encrypted)
		privkey = rsa.PrivateKey.load_pkcs1(privkey_pem, format='PEM') # @sylmobile bug reported 12 Feb
	except:
		print "Encryption failure -- bad passwords?"
		return None

	return privkey

#
# Serialize the highest read in status ID so we can read it in later
#
def write_id_file(filename, the_id):
	id_file = open(filename, 'w')
	id_file.writelines((str(the_id)))
    	id_file.close()

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

# Establish a connection to Twitter
oauth_fn = os.path.join(os.path.expanduser('~'),'.cryptweet-oauth')
id_fn = os.path.join(os.path.expanduser('~'),'.cryptweet-dm-id')

con_secret = "pG9hrZAUURqyDTfBbJcgAMdpemBmgAdZDL92ErVELY"
con_key = "JwCegsVjfjfK0GvsQkpUw"

# Get the file with our OAuth tokens
if os.path.isfile(oauth_fn):  # Does the token file exist?
        tokens = twitter.oauth.read_token_file(oauth_fn)
else:                   # If not, do authorization, create file
        print 'No Twitter authorization; you need to run cryptweet-setup.'
        sys.exit(-1)

# Get the file with the DM last_id
if os.path.isfile(id_fn):	# Does last_ID file exist?
	last_file = open(id_fn, "r")
	#print 
	last_id = int(last_file.readlines()[0])
else:
	last_id = 1
if options.force_dms:		# Do we force a read of the whole DM timeline?
	last_id = 1		# Yes, so start at the beginning.  Ish.

#Establish an API connection
twapi = twitter.Twitter(auth = twitter.OAuth(token=tokens[0],
						token_secret=tokens[1],
						consumer_secret=con_secret, 
						consumer_key=con_key))
#
# Setup to receive and assemble packets.  Read in the private key.
#
pa = packet.PacketAssembler()
private_key = None

# Let's get some DMs
#
#print 'Getting DMs from %d...' % (last_id,)
try:
	results = twapi.direct_messages(since_id = last_id, count=200)
except twitter.TwitterError as e:
	print "Could not retrieve Direct Messages from Twitter."
	print e
	sys.exit(2)
except twitter.TwitterHTTPError as e:
	print "Having a problem communicating with Twitter."
	print e
	sys.exit(3)

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
				data=is_msg[3])

	if message['id'] > last_id:
		last_id = message['id']		# Keep the last message current

msgs_read = False

for pkt in pa.packets:
	if pkt.areWeThereYet():		# Is the packet completed?
		while private_key == None:	# No private key, then go and get it.
			try:
				private_key = decode_private_key()
			except KeyboardInterrupt:
				print
				print 'Aborting.'
				sys.exit(0)

		crypt64_msg = pkt.getString()
		#print pkt.id, pkt.getString()
		try:
			crypt_msg = base64.standard_b64decode(crypt64_msg)
			try:
				msg = rsa.decrypt(crypt_msg, private_key)
				print pkt.uname + ':', msg
				msgs_read = True
			except rsa.DecryptionError:
				print "Could not decrypt message -- incorrect private key?"
		except TypeError:
			print "Decode error, could not decrypt message"


#print 'Writing %d as last_id to %s...' % (last_id, id_fn)
if msgs_read:
	write_id_file(id_fn, last_id)		# Only update the ID if we actually caught some messages



