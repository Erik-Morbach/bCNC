import random
encodeTable = [0]*256
decodeTable = [0]*256

# encode the first 4 bits of this value
def _singleEncode(val): # TODO: LookUpTable
    data = 0
    data = (val&1) | (val&2) | (val&4) | ((val&8)<<1)

    data |= ((val&1) ^ ((val>>1)&1) ^ ((val>>2)&1)) << 3;
    data |= ((val&1) ^ ((val>>1)&1) ^ ((val>>3)&1)) << 5;
    data |= ((val&1) ^ ((val>>2)&1) ^ ((val>>3)&1)) << 6;

    for i in range(0,7):
        data ^= ((data>>i)&1)<<7

    return data;

# return 4 bits
def _decode(val):
    if decodeTable[val] != 0: return decodeTable[val]
    errorIndex = 0
    if (val&1) ^ ((val>>2)&1) ^ ((val>>4)&1) ^ ((val>>6)&1):
        errorIndex += 1
    if (val&1) ^ ((val>>1)&1) ^ ((val>>4)&1) ^ ((val>>5)&1):
        errorIndex += 2
    if (val&1) ^ ((val>>1)&1) ^ ((val>>2)&1) ^ ((val>>3)&1):
        errorIndex += 4

    if errorIndex>0:
        val ^= 1<<(7-errorIndex);
    decodeTable[val] = (val&1) | (val&2) | (val&4) | ((val&16)>>1)
    return decodeTable[val]


# return 2 bytes
def _encode(val):
    if encodeTable[val] != 0: return encodeTable[val]
    first = val>>4;
    second = val&(0b1111);
    encodeTable[val] = (_singleEncode(first) << 8) | _singleEncode(second);
    return encodeTable[val]

def decodeOne(val):
    return (_decode(val>>8)<<4) | _decode(val&0xff);

def encodeOne(val):
    return _encode(val);


if __name__ == "__main__":
    used = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x08, 0x09, 0x0A, 0x0D, 0x11, 0x13, 0x15, 0x1A, 0x18, 0x19, 0x1B, 0x7F, ord('\n'), ord('\r'), 0x14, 0x18, 0x19, ord('?'), ord('~'), ord('!'), ord('%'), 0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x87, 0x88, 0x89, 0x8A, 0x8B, 0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0x9B, 0x9C, 0x9D, 0x9E, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6]
    for i in range(ord('a'), ord('z')+1):
        used += [i]
    for i in range(ord('A'), ord('Z')+1):
        used += [i]
    print("Used chars {}".format(len(used)))
    values = [0]*255
    for w in used:
        w = int(w)
        v = encodeOne(w)
        values[v % 255] = 1
        values[v >> 8] = 1
    for id, v in enumerate(values):
        if v:
            continue
        print("{} -> {}".format(id, v))

    while 1:
        for i in range(0, 0xff):
            data = i
            encoded = encodeOne(data)
            for i in range(0, 16):  # TODO: Not correcting properly
                if random.randint(0, 10000) <= 10:
                    encoded ^= 1 << i
                    break
            decoded = decodeOne(encoded)
            if bin(decoded) != bin(data):
                print("{} -> {} -> {}".format(bin(data), bin(encoded),
                                              bin(decoded)))
                print("ERROOO")
    print("Certinho")
