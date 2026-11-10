import sys, struct
station=int(sys.argv[1]); wtbl=int(sys.argv[2]); mac=bytes.fromhex(sys.argv[3].replace(':',''))
b=bytearray(200)
b[0]=station; b[1]=0x10; b[2:8]=mac; b[0x0c]=1; b[0x0d]=0x0a
b[0x12]=1; b[0x14]=2; b[0x17]=1
struct.pack_into('<I', b, 0x18, 0x9f63)
struct.pack_into('<H', b, 0x28, 0x006f)
struct.pack_into('<I', b, 0x24, 1)
struct.pack_into('<I', b, 0x38, 0x00360cbf)
b[0x3c:0x44] = bytes.fromhex('8003faff0000faff')
b[0x30]=3; b[0x36]=wtbl; b[0x37]=0xff; b[0x44]=3; b[0x7d]=1
print(b.hex())
