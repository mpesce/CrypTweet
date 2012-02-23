# HTTP-based keyserver for Cryptweet
#
import os, sys, time, string, BaseHTTPServer, json, logging
import daemon, rsa, keyring

HOST_NAME = 'localhost'
PORT_NUMBER = 8118			# That'll be the port for the keyserver
logging_fn = os.path.join(os.path.expanduser('~'),'.cryptweet-keyserver-log')

class KeyServer():
	def __init__(self):
		logging.debug("KeyServer.__init__")
		self.httpd = BaseHTTPServer.HTTPServer((HOST_NAME, PORT_NUMBER), MyHandler)
		return

class KeyServerDaemon(daemon.Daemon):
	def __init__(self, pidfile, ks=None):
		logging.debug("KeyServerDaemon.__init__")
		daemon.Daemon.__init__(self, pidfile)
		self.the_server = ks
		return

	def run(self):
		logging.debug("KeyServerDaemon.run")
		self.the_server.serve_forever()
		logging.debug("KeyServerDaemon.run returned from serve_forever()")

class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	def do_HEAD(s):
		s.send_response(200)
		s.send_header("Content-type", "text/html")
		s.end_headers
	def do_GET(s):
		s.send_response(200)
		s.send_header("Content-type", "text/html")
		s.end_headers()
		parts = string.split(s.path,'/')  # Strip aw
		uname = parts[1]
		if uname == 'favicon.ico':
			return
		logging.info("Requesting public key for %s" % (uname,))
		key = keyring.get_key_by_name(uname)
		if key == None:
			s.wfile.write(json.dumps("{}"))
			logging.info("Public key not found.")
		else:
			s.wfile.write(json.dumps(key.save_pkcs1(format='PEM')))	
			logging.info("Public key found, returning JSON string.")	

def do_server():
	server_class = BaseHTTPServer.HTTPServer
	httpd = server_class((HOST_NAME, PORT_NUMBER), MyHandler)
	print time.asctime(), "Server starts"
	try:
		httpd.serve_forever()
	except KeyboardInterrupt:
		pass
	httpd.server_close()
	print time.asctime(), "Server stops"

if __name__ == "__main__":

	if len(sys.argv) == 2:
		if 'start' == sys.argv[1]:
			logging.basicConfig(filename=logging_fn, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
			# Start the server
			srv = KeyServer()  # needs to be the external IP address if it's to work properly
			startstr = "Ceep server running on %s:%s" % (HOST_NAME, str(PORT_NUMBER))
			logging.debug(startstr)
			dmon = KeyServerDaemon(pidfile=os.path.join(os.path.expanduser('~'),'.cryptweet-keyserver-pid'), ks=srv.httpd) # Create daemon
			dmon.start()

		elif 'stop' == sys.argv[1]:
			logging.basicConfig(filename=logging_fn, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
			logging.info("Stopping server")
			dmon = KeyServerDaemon(pidfile=os.path.join(os.path.expanduser('~'),'.cryptweet-keyserver-pid')) # Create daemon
			dmon.stop()

		elif 'nodaemon' == sys.argv[1]:
			logging.basicConfig(level=logging.DEBUG,format='%(asctime)s - %(levelname)s - %(message)s')
			# Start the server
			srv = KeyServer()  # needs to be the external IP address if it's to work properly
			startstr = "Ceep server running on %s:%s" % (HOST_NAME, str(PORT_NUMBER))
			logging.debug(startstr)
			try:
				srv.httpd.serve_forever()
			except KeyboardInterrupt:
				logging.critical("Received a keyboard interrupt, exiting...")
				srv.httpd.server_close()
		else:
			print("Unknown command")
	else:
		print "usage %s start | stop | nodaemon" % (sys.argv[0],)
		sys.exit(2)

