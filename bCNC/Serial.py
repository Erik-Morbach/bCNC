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
		pass

	def flushInput(self):
		self.serial.flushInput()

	def flush(self):
		self.serial.flush()

	def write(self, data):
		if not self.activeEcc:
			self.serial.write(data)
			return
		outData = bytes()
		for w in data:
			outData += ecc.encodeOne(1).to_bytes(2, 'big')
			outData += ecc.encodeOne(w).to_bytes(2, 'big')
		self.serial.write(outData)
	
	def in_waiting(self):
		return self.serial.in_waiting

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
		if not self.activeEcc:
			return self.serial.read(n)
		data = bytes()
		recieved = self.serial.read(n)
		for w in recieved:
			data += self._readChar(w)
		return data
