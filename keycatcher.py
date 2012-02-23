#!/usr/bin/python
#
# The keycatcher is a server process that catches public keys as they get mentioned in @cryptw__t's stream.
#
import os, sys, string, time, json, logging
import packet, keyring, daemon
import twitter, rsa

logging_fn = os.path.join(os.path.expanduser('~'),'.cryptweet-keycatcher-log')

class KeyCatcherDaemon(daemon.Daemon):

	def run(self):
		logging.debug("KeyServerDaemon.run")
		tw = open_twitter()
		if tw:
			logging.debug('Twitter is open, we seem to be fine.')
			pq = packet.PacketAssembler()
			new_low_id = None

			# Do this until further notice
			while True:
				old_low_id = new_low_id
				if one_pass(pq, tw, start_id=new_low_id):
					(pq, new_low_id) = trim_packets(pq)
					if new_low_id:
						logging.debug("New high water mark %d" % (new_low_id,))
					else:
						if old_low_id:
							new_low_id = old_low_id		# Don't allow id to reset
				time.sleep(30)		# Check every 30 seconds

# 
# Return tuple (True, sequence id, frame number, data) if this DM begins with a sequence value
#
def test_mention_sequence(astr):

	# First discard the @mention, which should be everything up to the first space
	after_mention = string.split(astr," ", 1)
	if len(after_mention) < 2:	# No space?
		return (False,)

	parts = string.split(after_mention[1],'.')	# Should start with a sequence id followed by a period separator
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

	#Establish an API connection
	twapi = twitter.Twitter(auth = twitter.OAuth(token=tokens[0],
							token_secret=tokens[1],
							consumer_secret=con_secret, 
							consumer_key=con_key))

	# Let's put this to the test by trying to get our user data.
	try:	
		result = twapi.account.verify_credentials()
		twitter_id = result['id']
		twitter_handle = result['screen_name']
		logging.debug('Good, we seem to be authorized for username %s with id %d' % (twitter_handle, int(twitter_id)))

	except TwitterError:		# Something bad happening, abort, abort!
		print "Call failed, we don't seem to be authorized with these credentials.  Deleting..."
		return None	
	return twapi

# Prune the packets in the packet assembler
# Done or not, wait 15 minutes and delete a packet
# Returns a replacement PacketAssembler object, and an id count value 
#
def trim_packets(pq):

	AGE_LIMIT = 30				# 30 seconds for testing, should be longer
	nq = packet.PacketAssembler()		# This is what we'll return with
	curr = time.time()
	new_low_id = None

	for pkt in pq.packets:		# Iterate through the packets
		if new_low_id == None:
			new_low_id = pkt.twitter_id
		else:
			if new_low_id < pkt.twitter_id:
				new_low_id = pkt.twitter_id	# Keep the high water mark

		age = pkt.when		# When was the packet created?
		if (curr - pkt.when) > AGE_LIMIT:
			logging.debug('Deleting packet created at %d' % (pkt.when,))
		else:
			nq.packets.append(pkt)		# Add the packet to the new queue of packets

	# We have packets, so what's the lowest twitter id amongst all the packets?
	if len(nq.packets) > 0:	# No packets in assembler?
		new_low_id = None
		for pkt in nq.packets:
			if new_low_id == None:
				new_low_id = pkt.twitter_id
			else:
				if new_low_id > pkt.twitter_id:
					new_low_id = pkt.twitter_id

	return (nq, new_low_id)

# Do a single pass with the server
# Read in the mentions timeline, process it
# And get out again
#
def one_pass(pq, tw, start_id=None):

	# Ok, grab up the last 200 mentions - which is as many as Twitter will allow, apparently.
	#
	logging.debug('Requesting mentions timeline...')
	try:
		if start_id:
			mentions = tw.statuses.mentions(since_id=start_id)
		else:
			mentions = tw.statuses.mentions(count=20)
	except:
		logging.debug('We got an error from Twitter, sorry.')
		return False

	# Now grab the highest ID in that set, which becomes the new last_id value
	for mention in mentions:
		seq = test_mention_sequence(mention['text'])  # Attempt to dissassemble packet
		if (seq[0]):				# Valid sequence?
			logging.debug("We appear to have a sequence with id %d" % (mention['id'],))
			pq.addPacket(seq[1], seq[2], user_name=mention['user']['screen_name'], 
					data=seq[3], size=4, twid=mention['id'])

	# Now go through the PacketAssembler and fish out the assembled packets, if any.
	for pkt in pq.packets:
		if pkt.areWeThereYet():
			#print pkt.getString()
			f = json.loads(pkt.getString())
			uname = f[0]
			the_id = f[1]
			pubkey = rsa.PublicKey.load_pkcs1(f[2], format='PEM')
			keyring.add_key(pkt.uname, the_id, pubkey)
			logging.info("Key for %s added and twitter id of %d..." % (pkt.uname, pkt.twitter_id))
			pkt.processed = True		# This key has been processed and we know this
	return True


if __name__ == '__main__':

	if len(sys.argv) == 2:
		if 'start' == sys.argv[1]:
			logging.basicConfig(filename=logging_fn, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
			startstr = "Keycatcher daemon starting."
			logging.debug(startstr)
			dmon = KeyCatcherDaemon(pidfile=os.path.join(os.path.expanduser('~'),'.cryptweet-keycatcher-pid')) # Create daemon
			dmon.start()

		elif 'stop' == sys.argv[1]:
			logging.basicConfig(filename=logging_fn, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
			logging.info("Keycatcher daemon stopping.")
			dmon = KeyCatcherDaemon(pidfile=os.path.join(os.path.expanduser('~'),'.cryptweet-keycatcher-pid')) # Create daemon
			dmon.stop()

		elif 'nodaemon' == sys.argv[1]:

			logging.basicConfig(level=logging.DEBUG,format='%(asctime)s - %(levelname)s - %(message)s')
			tw = open_twitter()
			if tw:
				logging.debug('Twitter is open, we seem to be fine.')
				pq = packet.PacketAssembler()
				new_low_id = None

				# Do this until further notice
				while True:
					try:
						old_low_id = new_low_id
						if one_pass(pq, tw, start_id=new_low_id):
							(pq, new_low_id) = trim_packets(pq)
							if new_low_id:
								logging.debug("New high water mark %d" % (new_low_id,))
							else:
								if old_low_id:
									new_low_id = old_low_id		# Don't allow id to reset
						time.sleep(30)		# Check every 30 seconds
					except KeyboardInterrupt:
						logging.debug('Shutting down.')
						sys.exit(0)
		else:
			print "usage %s start | stop | nodaemon" % (sys.argv[0],)
			sys.exit(2)
	else:
		print "usage %s start | stop | nodaemon" % (sys.argv[0],)
		sys.exit(2)

