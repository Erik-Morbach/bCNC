import threading
import Utils
import serial
import ecc


class Serial:
	def __init__(self, *args, **kwargs) -> None:
		self.serial = serial.serial_for_url(*args, **kwargs)
		self.activeEcc = Utils.getBool("CNC", "ecc", True)
		self.inside = 0
		self.last = 0
		self.have = False
		self.shouldRead = False
		self.mtx = threading.Lock()
		pass

	def lock(self, msg):
		self.mtx.acquire(blocking=True)

	def unlock(self, msg):
		self.mtx.release()

	def flushInput(self):
		self.serial.flushInput()

	def flush(self):
		self.serial.flush()

	def write(self, data):
		outData = data
		if self.activeEcc:
			outData = bytes()
			for w in data:
				outData += ecc.encodeOne(1).to_bytes(2, 'big')
				outData += ecc.encodeOne(w).to_bytes(2, 'big')
		try:
			self.lock("write")
			self.serial.write(outData)
		except:
			raise serial.SerialException()
		finally:
			self.unlock("write")
	
	def in_waiting(self):
		if self.serial.readable():
			return self.serial.in_waiting
		else:
			return 0

	def _readChar(self, c):
		if not self.shouldRead:
			dc = ecc.decodeOne((self.last<<8) + c)
			self.last = c
			if dc != 0x01: return bytes()

			self.have = False
			self.last = 0
			self.shouldRead = True
			return bytes()

		if not self.have:
			self.last = c
			self.have = True
			return bytes()

		value = (self.last<<8) + c
		data = ecc.decodeOne(value).to_bytes(1,'big')
		self.have = False
		self.shouldRead = False
		self.last = 0
		return data


	def read(self):
		n = max(self.serial.in_waiting,1)
		recieved  = []
		if self.serial.readable():
			recieved = self.serial.read(n)

		if not self.activeEcc:
			return recieved

		data = bytes()
		for w in recieved:
			data += self._readChar(w)

		return data
