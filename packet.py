#
# Packet object for doing things with packets.  Such as, you know, making them and reading them in.
# 
#
import time

class Packet:
	def __init__(self, sequence_id, user_name, size=6):
		self.when = time.time()			# Timestamp used to age packet
		self.created = None			# When was this message received?
		self.id = sequence_id
		self.twitter_id = None			# Track the twitter IDs, if you want to
		self.uname = user_name
		self.size = size
		self.ready = False			# Is this packet ready?
		self.processed = False			# Has this packet been digested?
		self.data = []
		creator = size
		while creator > 0:
			self.data.append('')		# Reserves space for the data to go into the array
			creator = creator - 1

	# Add sequence data to a packet
	def add(self, frame_number, data, twid=None, created=None):
		self.data[frame_number - 1] = data	# Not hard to do, really

		# If necessary, track the lowest twitter_id used by this packet
		if twid != None:
			if self.twitter_id == None:
				self.twitter_id = twid
			else:
				if self.twitter_id > twid:
					self.twitter_id = twid

		if created:
			self.created = created		# Keep track of when we were created
		self.ready = self.areWeThereYet()	# And set things appropriately
		#print self.data

	# Is the packet complete?  Is every sequence received?
	def areWeThereYet(self):
		check = self.size
		while check:
			if len(self.data[check - 1]) < 1:
				return False
			check = check - 1
		return True

	def getString(self):
		retval = ''
		adder = 0
		while (adder < self.size):
			retval = retval + self.data[adder]
			adder = adder + 1
		return retval

class PacketAssembler:
	def __init__(self):
		self.packets = []		# Packets being assembled

	def where(self, sequence_id):		# Returns position in array if packet_id is being assembled
		index = 1
		for e in self.packets:
			#print 'comparing %d to %d' % (sequence_id, e.id)
			if sequence_id == e.id:
				return index
			index = index + 1
		return False
	
	def addPacket(self, sequence_id, frame_number, user_name, data, twid=None, size=6, created=None):
		pos = self.where(sequence_id)
		#print 'pos %d' % (pos,)
		if pos:
			self.packets[pos-1].add(frame_number, data, twid)	# Add to existing packet
		else:
			self.packets.append(Packet(sequence_id, user_name, size))
			self.packets[len(self.packets)-1].add(frame_number, data, twid, created)	# Add to new packet

	def retrievePacket(self, sequence_id):
		pos = self.where(sequence_id)
		if pos:
			return self.packets[pos-1].getString()
		else:
			return False

	def deletePacket(self, sequence_id):
		pos = self.where(sequence_id)
		if pos:
			new_packets = []
			iter = 0
			while iter < len(self.packets):
				if (pos-1) == iter:
					#print 'skipping packet'
					iter = iter + 1
					continue
				else:
					new_packets.append(self.packets[iter])
				iter = iter + 1
			self.packets = new_packets

#	def dump(self):


# Unit tests.  No, seriously.
# Should produce the following output
'''['wow', '', '', '', '', '']
['wow', '', '', '', '', '']
['wow', 'woah', '', '', '', '']
['wow', '', '', '', 'wow', '']
['wow', '', 'wow', '', 'wow', '']
['wow', '', 'wow', 'wow', 'wow', '']
['wow', 'wow', 'wow', 'wow', 'wow', '']
['wow', 'wow', 'wow', 'wow', 'wow', 'wow']
wowwowwowwowwowwow
['wow', 'woah', '', '', '', '']
False'''
if __name__ == "__main__":
	q = PacketAssembler()
	q.addPacket(100210, 1, 'wow')
	q.addPacket(100220, 1, 'wow')
	q.addPacket(100220, 2, 'woah')
	q.addPacket(100210, 5, 'wow')
	q.addPacket(100210, 3, 'wow')
	q.addPacket(100210, 4, 'wow')
	q.addPacket(100210, 2, 'wow')
	q.addPacket(100210, 6, 'wow')
	print q.retrievePacket(100210)
	print q.packets[q.where(100210)].data
	q.deletePacket(100210)
	print q.retrievePacket(100210)


