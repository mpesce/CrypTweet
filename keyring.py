#
# A database of RSA public keys
# Which is the core of Plexus, in its way.
#
# Each row in the database has three fields: Twitter screen name, Twitter id, and the public key (JSON-ized)
#
import os, sqlite3, json, logging
import rsa

# Starter entries for the database of public keys
#
e1 = {"uname": "cryptw__t", "id": "1", "pubkey": '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAi/Tc1XAIO0VsY0VDbuuyqVvSLDBebpihOi4B0gvF8KG5Wfw5EGTh
xoRY4plleE3mZcy1UxGhu970CT5XoM2gRaisXN61/RC+YmQF6QyVdQHkRHxMzHI1
41avoW0AiUNFkvfDDKqB0VQHWPfDXJ7pcWELEBPNJrzn2vxUEJwx04Ztgo2ehMYc
AUiPG2HPqlFjtnlMsdI4MqTADvqnSlOppSdpJ3Z37dMmicL7MFPmeL1BOJ152/eQ
L+HMXQvwzJJrT8u5qff5r3MAC8pEKGqQO1Zcsf+T6J1y+Cm2qOKwk7QAF67YnZlF
Q+wTsBORiSjegKeq6K6aXVVQY3BMGk37bwIDAQAB
-----END RSA PUBLIC KEY-----'''}

# Generate the name of the keyfile
#
def get_db_name(is_usb=False):
	fn = os.path.join(os.path.expanduser('~'),'.cryptweet-keys.db')
	return fn

def get_key_by_name(name):

	# Open the database and return a key matching a Twitter username
	db_fn = get_db_name()
	if os.path.isfile(db_fn):
		conn = sqlite3.connect(db_fn, timeout=15)		# open key database
		c = conn.cursor()
		c.execute("select * from keys where uname=?", (name,))
		row = c.fetchone()	# Get the first match -- should be the only one
		if row == None:		# No matches
			retkey = None
		else:
			retkey = rsa.PublicKey.load_pkcs1(row[2],format='PEM')
		c.close()			# close key database
	else:
		logging.error("Key database does not exist!")
		retkey = None
	return retkey	

def get_key_by_id(the_id):

	# Open the database and return a key matching a Twitter user ID
	db_fn = get_db_name()
	if os.path.isfile(db_fn):
		conn = sqlite3.connect(db_fn, timeout=15)		# open key database
		c = conn.cursor()
		c.execute("select * from keys where id=?", (the_id,))
		row = c.fetchone()	# Get the first match -- should be the only one
		if row == None:		# No matches
			retkey = None
		else:
			retkey = rsa.PublicKey.load_pkcs1(row[2],format='PEM')
		c.close()			# close key database
	else:
		logging.error("Key database does not exist!")
		retkey = None
	return retkey

#
# Add a key to the database
# Returns True if it worked, False otherwise
# If the key already exists, will put the updated copy into the database
#
def add_key(uname, the_id, pubkey):

	# Open the database and return a key matching a Twitter user ID
	db_fn = get_db_name()
	if os.path.isfile(db_fn):
		conn = sqlite3.connect(db_fn, timeout=15)		# open key database
		c = conn.cursor()
		data = (uname, int(the_id), pubkey.save_pkcs1(format='PEM'))
		try:
			c.execute('select * from keys where uname=?', (uname,))	# Does record already exist?
			row = c.fetchone()
			if row != None:
				c.execute('update keys SET id = ?, pubkey =? WHERE uname=?', (data[1], data[2], data[0])) # modify it
				#print 'updating...'
			else:
				c.execute('insert into keys values (?,?,?)', data)	# create new record
				#print 'inserting...'
			conn.commit()		# Commit changes
			retval = True
		except:
			retval = False
		c.close()			# close key database
	else:
		logging.error("Key database does not exist!")
		retval = False
	return retval

# Setup the key database from scratch
# If it already exists, complain and do nothing
# Use one seed key - @cryptw__t - to start things off
#
def setup_key_db():
	db_fn = get_db_name()
	if os.path.isfile(db_fn):
		print "Key database already exists, not initializing.  Delete it & run again to reinitialize it."
		print "Dumping the key database"
		conn = sqlite3.connect(db_fn)
		c = conn.cursor()
		c.execute('select * from keys order by uname')
		print
		print "Database contents:"
		print
		for row in c:
			print row
		c.close()

	else:
		conn = sqlite3.connect(db_fn)

		# Now create the table
		c = conn.cursor()
		c.execute('''create table keys (uname text primary key, id integer, pubkey text)''')

		if add_key(e1['uname'], e1['id'], rsa.PublicKey.load_pkcs1(e1['pubkey'], format='PEM')) == False:
			print 'Failed add_key'

		# Second test to see if modification works
		if add_key(e1['uname'], e1['id'], rsa.PublicKey.load_pkcs1(e1['pubkey'], format='PEM')) == False:  
			print 'Failed UPDATE add_key'

		# Dump the table to check to see if everything is alright
		c.execute('select * from keys order by uname')
		print
		print "Database contents:"
		print
		for row in c:
			print row

		# And run a quick test
		n = ("cryptw__t",)
		c.execute('select * from keys where uname=?', n)
		print
		print "Search results on %s:" % n
		print
		for row in c:
			print row

		c.close()	
		

# When run from the command line, it sets up the database file
#
if __name__ == '__main__':
	setup_key_db()


	
