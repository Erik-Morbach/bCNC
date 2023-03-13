import Utils
import serial
import ecc


class Serial:
	def __init__(self, *args, **kwargs) -> None:
		self.serial = serial.serial_for_url(*args, **kwargs)
		self.activeEcc = Utils.getBool("CNC", "ecc", True)
		self.inside = 0
		self.last = 0
		self.have = 0
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

	def read(self):
		n = max(self.serial.in_waiting,1)
		if not self.activeEcc:
			return self.serial.read(n)
		data = bytes()
		recieved = self.serial.read(n)
		for w in recieved:
			if w == 0x01:
				self.have = 0
				self.last = 0
				continue
			if not self.have:
				self.have = 1
				self.last = w
				continue
			value = (self.last<<8) + w
			data += ecc.decodeOne(value).to_bytes(1,'big')
			self.have = 0
		return data
