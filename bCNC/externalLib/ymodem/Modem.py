import os
import sys
import time
import logging
import platform

from externalLib.ymodem.Protocol import Protocol

logging.basicConfig(level = logging.DEBUG, format = '%(message)s')

def crc16(data):
    crc = 0
    for w in data:
        x = (crc >> 8) ^ w
        x ^= x >> 4
        crc = (crc << 8) ^ (x << 12) ^ (x << 5) ^ x
        crc = crc & 0xffff
    return crc.to_bytes(2, 'big')


SOH = b'\x01'
STX = b'\x02'
EOT = b'\x04'
ACK = b'\x06'
NAK = b'\x15'
CAN = b'\x18'
CRC = b'\x43'

USE_LENGTH_FIELD    = 0b100000
USE_DATE_FIELD      = 0b010000
USE_MODE_FIELD      = 0b001000
USE_SN_FIELD        = 0b000100
ALLOW_1KBLK         = 0b000010
ALLOW_YMODEMG       = 0b000001

class Modem(Protocol):
    def __init__(self, serial):
        self.logger = logging.getLogger('Modem')
        self.serial = serial

    def abort(self, count=2, timeout=60):
        for _ in range(count):
            self.serial.write(CAN, timeout)

    def send(self, stream, retry=10, timeout=2, info=None):
        packet_size = 1024
        self.logger.debug('[Sender]: Waiting the mode request...')
        error_count = 0
        crc_mode = 1
        cancel = 0

        self.logger.debug("[Sender]: Preparing info block")

        packet_num = 0
        block = STX
        block += packet_num.to_bytes(1, 'big')
        block += (0xff - packet_num).to_bytes(1, 'big')
        packet_num+=1
        # [required] Name
        filepath = info["name"].encode()
        filepath = filepath.ljust(packet_size, b'\x00')
        for w in filepath:
            block += w.to_bytes(1, 'big')

        crc = crc16(filepath)
        block+=crc
        self.serial.timeout = timeout
        error_count = 0
        while True:
            self.serial.write(block)
            self.serial.flush()
            self.logger.debug("[Sender]: Info block sent")
            char = self.serial.read(1)
            if char == ACK:
                error_count = 0
                break

            self.logger.error("[Sender]: Error, expected ACK but got %r for info block", char)
            error_count += 1
            if error_count > retry:
                self.logger.error("[Sender]: Error, NAK received {} times, aborting...".format(error_count))
                self.abort(timeout=timeout)
                return False

        # Data packets
        self.logger.debug("[Sender]: Waiting the mode request...")
        error_count = 0
        crc_mode = 1
        cancel = 0
        while True:
            char = self.serial.read(1)
            if char:
                if char == NAK:
                    crc_mode = 0
                    self.logger.debug("[Sender]: Received checksum request (NAK)")
                    break
                elif char == CRC:
                    crc_mode = 1
                    self.logger.debug("[Sender]: Received CRC request (C/CRC)")
                    break
                elif char == CAN:
                    if cancel:
                        self.logger.info("[Sender]: Transmission cancelled (CAN)")
                        return False
                    else:
                        cancel = 1
                        self.logger.debug("[Sender]: Ready for transmission cancellation (CAN)")
                elif char == EOT:
                    self.logger.info("[Sender]: Transmission cancelled (EOT)")
                    return False
                else:
                    self.logger.error("[Sender]: Expected NAK, CRC, EOT or CAN but got %r", char)
            error_count += 1
            if error_count > retry:
                self.logger.info("[Sender]: Error, error_count reached {}, aborting...".format(retry))
                self.abort(timeout=timeout)
                return False

        error_count = 0
        success_count = 0
        total_packets = 0
        sequence = 1
        while True:
            data = stream.read(packet_size)
            if not data:
                self.logger.debug("[Sender]: Reached EOF")
                break
            total_packets += 1

            header = STX
            header += packet_num.to_bytes(1,'big')
            header += (0xff - packet_num).to_bytes(1,'big')
            data = data.encode().ljust(packet_size, b'\x00')
            crc = crc16(data)
            block = header
            block += data
            block += crc

            while True:
                self.serial.write(block)
                self.serial.flush()
                self.logger.debug("[Sender]: Block {} (Seq {}) sent".format(success_count, packet_num))
                char = self.serial.read(1)
                if char == ACK:
                    success_count += 1
                    error_count = 0
                    break

                self.logger.error('[Sender]: Error, expected ACK but got %r for block %d', char, packet_num)
                error_count += 1
                if error_count > retry:
                    self.logger.error("[Sender]: Error, NAK received {} times, aborting...".format(error_count))
                    self.abort(timeout=timeout)
                    return False
            packet_num += 1
            if packet_num > 0xff:
                packet_num = 0

        self.serial.write(EOT)
        self.logger.debug("[Sender]: EOT sent and awaiting ACK + C")
        
        while True:
            char = self.serial.read(1)
            if char == ACK:
                self.logger.debug("[Sender]: Received ACK")
                break
            else:
                self.logger.error("[Sender]: Error, expected NAK but got %r", char)
                error_count += 1
                if error_count > retry:
                    self.logger.warning("[Sender]: Warning, EOT was not NAKd, aborting transfer...")
                    self.abort(timeout=timeout)
                    return False

        self.logger.debug("[Sender]: awaiting C")

        while True:
            char = self.serial.read(1)
            if char == b'C':
                self.logger.debug("[Sender]: Received C")
                break
            else:
                self.logger.error("[Sender]: Error, expected ACK but got %r", char)
                error_count += 1
                if error_count > retry:
                    self.logger.warning("[Sender]: Warning, EOT was not ACKd, aborting transfer...")
                    self.abort(timeout=timeout)
                    return False

        self.logger.info("[Sender]: Transmission finished (ACK)")
        self.serial.flush()
        self.serial.timeout = 0.01
        while self.serial.read(1024):
            pass
        return True
