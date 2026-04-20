"""
idea_cipher.py — IDEA (International Data Encryption Algorithm) implementation

Seaman PC's DataBase.dll encrypts .udb save files with IDEA in ECB mode.
- 64-bit (8-byte) block size
- 128-bit (16-byte) key stored as first 16 bytes of file
- Key generated randomly: srand(time(NULL)) + 8 × rand() → 8 × uint16 (LE)

Based on decompiled functions:
  FUN_1000b300 = key schedule (expand 8 uint16 → 52 uint16 subkeys)
  FUN_1000b430 = encrypt/decrypt block (4 uint16 in, 4 uint16 out, 52 subkeys)
  FUN_1000aec0 = inverse key schedule (52 encrypt subkeys → 52 decrypt subkeys)
  FUN_1000abb0 = encrypt file in-place
  FUN_1000b060 = decrypt file in-place

NOTE: Game uses LITTLE-ENDIAN uint16 throughout (x86 native byte order).
"""

import struct


def _mul(a, b):
    """IDEA multiplication: a ⊙ b mod (2^16 + 1), with 0 treated as 2^16."""
    if a == 0:
        a = 0x10000
    if b == 0:
        b = 0x10000
    r = (a * b) % 0x10001
    if r >= 0x10000:
        r = 0
    return r & 0xFFFF


def _add(a, b):
    """IDEA addition: (a + b) mod 2^16."""
    return (a + b) & 0xFFFF


def _mul_inv(a):
    """Multiplicative inverse of a mod (2^16 + 1). 0 represents 2^16."""
    if a <= 1:
        return a
    # Extended Euclidean algorithm for inverse mod 65537
    t, new_t = 0, 1
    r, new_r = 0x10001, a
    while new_r != 0:
        q = r // new_r
        t, new_t = new_t, t - q * new_t
        r, new_r = new_r, r - q * new_r
    if t < 0:
        t += 0x10001
    return t & 0xFFFF


def _add_inv(a):
    """Additive inverse of a mod 2^16."""
    return (0x10000 - a) & 0xFFFF


def expand_key(key_bytes):
    """
    IDEA key schedule: expand 16-byte key into 52 uint16 subkeys.
    Matches FUN_1000b300 in DataBase.dll.
    """
    assert len(key_bytes) == 16
    # Game stores key as 8 little-endian uint16 values
    k = list(struct.unpack('<8H', key_bytes))
    subkeys = []
    idx = 0
    for _ in range(52):
        subkeys.append(k[idx])
        idx += 1
        if idx >= 8:
            # Rotate: new[i] = (k[(i+1)%8] << 9) | (k[(i+2)%8] >> 7)
            new_k = [0] * 8
            for i in range(8):
                new_k[i] = ((k[(i + 1) % 8] << 9) | (k[(i + 2) % 8] >> 7)) & 0xFFFF
            k = new_k
            idx = 0
    return subkeys


def invert_subkeys(ek):
    """
    Compute IDEA decryption subkeys from encryption subkeys.
    Matches FUN_1000aec0 in DataBase.dll.
    """
    dk = [0] * 52
    # Output transformation (round 9) inverse
    dk[0] = _mul_inv(ek[48])
    dk[1] = _add_inv(ek[49])
    dk[2] = _add_inv(ek[50])
    dk[3] = _mul_inv(ek[51])
    # Rounds 8 down to 1
    p = 4
    for r in range(7, -1, -1):
        # MA subkeys (mixing step — unchanged)
        dk[p + 0] = ek[r * 6 + 4]
        dk[p + 1] = ek[r * 6 + 5]
        # Key-layer inverse
        dk[p + 2] = _mul_inv(ek[r * 6 + 0])
        if r > 0:
            # Inner rounds: add keys are SWAPPED
            dk[p + 3] = _add_inv(ek[r * 6 + 2])
            dk[p + 4] = _add_inv(ek[r * 6 + 1])
        else:
            # First round: add keys in original order
            dk[p + 3] = _add_inv(ek[r * 6 + 1])
            dk[p + 4] = _add_inv(ek[r * 6 + 2])
        dk[p + 5] = _mul_inv(ek[r * 6 + 3])
        p += 6
    return dk


def idea_crypt_block(block, subkeys):
    """
    IDEA encrypt or decrypt one 8-byte block.
    Matches FUN_1000b430 in DataBase.dll.
    Game uses LITTLE-ENDIAN uint16 values.
    """
    x1, x2, x3, x4 = struct.unpack('<4H', block)
    k = subkeys
    p = 0
    for _ in range(8):
        x1 = _mul(x1, k[p])
        x2 = _add(x2, k[p + 1])
        x3 = _add(x3, k[p + 2])
        x4 = _mul(x4, k[p + 3])
        t0 = x1 ^ x3
        t1 = x2 ^ x4
        t0 = _mul(t0, k[p + 4])
        t1 = _add(t0, t1)
        t1 = _mul(t1, k[p + 5])
        t0 = _add(t0, t1)
        x1 ^= t1
        x4 ^= t0
        t2 = x2 ^ t0
        x2 = x3 ^ t1
        x3 = t2
        p += 6
    # Output transformation
    y1 = _mul(x1, k[p])
    y2 = _add(x3, k[p + 1])  # x3, not x2 (undo implicit round swap)
    y3 = _add(x2, k[p + 2])  # x2, not x3
    y4 = _mul(x4, k[p + 3])
    return struct.pack('<4H', y1, y2, y3, y4)


def decrypt_udb(data):
    """
    Decrypt a .udb file.
    Format: [16-byte key][encrypted blocks (8 bytes each)]
    Last 4 bytes of decrypted plaintext = original file size stored as
    two LE uint16: [high_word][low_word] → orig_size = (high << 16) | low.
    Returns the decrypted plaintext (trimmed to original size).
    """
    if len(data) < 24:  # 16 key + at least 8 data
        raise ValueError("File too small: {0} bytes".format(len(data)))

    key = data[:16]
    ciphertext = data[16:]

    # Pad ciphertext to multiple of 8 if needed
    if len(ciphertext) % 8 != 0:
        ciphertext += b'\x00' * (8 - len(ciphertext) % 8)

    # Key schedule
    ek = expand_key(key)
    dk = invert_subkeys(ek)

    # Decrypt blocks
    plaintext = bytearray()
    for i in range(0, len(ciphertext), 8):
        block = ciphertext[i:i + 8]
        plaintext.extend(idea_crypt_block(block, dk))

    # Extract original file size from last 4 bytes
    # Stored as two LE uint16: [high_word, low_word]
    if len(plaintext) >= 4:
        high_word, low_word = struct.unpack('<HH', bytes(plaintext[-4:]))
        orig_size = (high_word << 16) | low_word
        if 0 < orig_size <= len(plaintext) - 4:
            return bytes(plaintext[:orig_size])

    # Fallback: strip trailing nulls and return
    return bytes(plaintext).rstrip(b'\x00')


def encrypt_udb(plaintext):
    """
    Encrypt plaintext data into .udb file format.
    Matches FUN_1000abb0 in DataBase.dll.
    Returns: [16-byte random key][encrypted blocks]
    """
    import time
    import random

    random.seed(int(time.time()))
    key = struct.pack('<8H', *[random.randint(0, 0xFFFF) for _ in range(8)])

    orig_size = len(plaintext)

    # Compute padded buffer size (matching game's algorithm)
    remainder = (orig_size - 4) & 7
    if remainder == 0:
        ivar7 = orig_size + 4
    else:
        ivar7 = (orig_size - remainder) + 12
    buf_size = ivar7 + 16  # game allocates iVar7 + 16

    # Build buffer: plaintext at start, size footer at end
    data = bytearray(buf_size)
    data[:orig_size] = plaintext
    # Store original size as two LE uint16 at the very end
    struct.pack_into('<HH', data, buf_size - 4,
                     (orig_size >> 16) & 0xFFFF, orig_size & 0xFFFF)

    # Key schedule
    ek = expand_key(key)

    # Encrypt ALL blocks (buf_size / 8)
    ciphertext = bytearray()
    for i in range(0, buf_size, 8):
        block = bytes(data[i:i + 8])
        ciphertext.extend(idea_crypt_block(block, ek))

    return key + bytes(ciphertext)


# ── Self-test ────────────────────────────────────────────────────────────────

def _test():
    """Verify encrypt/decrypt roundtrip."""
    test_data = b"Hello, Seaman PC Database!\x00\x00\x00"
    encrypted = encrypt_udb(test_data)
    decrypted = decrypt_udb(encrypted)
    assert decrypted == test_data, "Roundtrip failed:\n  got:    {0!r}\n  expect: {1!r}".format(decrypted, test_data)
    print("IDEA cipher self-test PASSED")


if __name__ == '__main__':
    _test()
