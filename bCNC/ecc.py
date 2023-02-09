import random

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
    errorIndex = 0
    if (val&1) ^ ((val>>2)&1) ^ ((val>>4)&1) ^ ((val>>6)&1):
        errorIndex += 1
    if (val&1) ^ ((val>>1)&1) ^ ((val>>4)&1) ^ ((val>>5)&1):
        errorIndex += 2
    if (val&1) ^ ((val>>1)&1) ^ ((val>>2)&1) ^ ((val>>3)&1):
        errorIndex += 4

    if errorIndex>0:
        val ^= 1<<(7-errorIndex);
    return (val&1) | (val&2) | (val&4) | ((val&16)>>1)


# return 2 bytes
def _encode(val):
    first = val>>4;
    second = val&(0b1111);
    return (_singleEncode(first) << 8) | _singleEncode(second);

def decodeOne(val):
    return (_decode(val>>8)<<4) | _decode(val&0xff);

def encodeOne(val):
    return _encode(val);


if __name__ == "__main__":
    while 1:
        for i in range(0,0xff):
            data = i
            encoded = encodeOne(data)
            for i in range(0,16): # TODO: Not correcting properly
                if random.randint(0,10000) <= 10:
                    encoded ^= 1<<i
                    break
            decoded = decodeOne(encoded)
            if(bin(decoded)!=bin(data)):
                print("{} -> {} -> {}".format(bin(data), bin(encoded), bin(decoded)))
                print("ERROOO")
    print("Certinho")

