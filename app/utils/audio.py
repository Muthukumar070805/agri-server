import struct
import numpy as np


ULAW_BIAS = 0x84
ULAW_STEP_LOOKUP = [
    0,
    0,
    1,
    1,
    2,
    2,
    3,
    3,
    4,
    4,
    5,
    5,
    6,
    6,
    7,
    7,
    8,
    8,
    9,
    9,
    10,
    10,
    11,
    11,
    12,
    12,
    13,
    13,
    14,
    14,
    15,
    15,
    16,
    16,
    17,
    17,
    18,
    18,
    19,
    19,
    20,
    20,
    21,
    21,
    22,
    22,
    23,
    23,
    24,
    24,
    25,
    25,
    26,
    26,
    27,
    27,
    28,
    28,
    29,
    29,
    30,
    30,
    31,
    31,
    32,
    32,
    33,
    33,
    34,
    34,
    35,
    35,
    36,
    36,
    37,
    37,
    38,
    38,
    39,
    39,
    40,
    40,
    41,
    41,
    42,
    42,
    43,
    43,
    44,
    44,
    45,
    45,
    46,
    46,
    47,
    47,
    48,
    48,
    49,
    49,
    50,
    50,
    51,
    51,
    52,
    52,
    53,
    53,
    54,
    54,
    55,
    55,
    56,
    56,
    57,
    57,
    58,
    58,
    59,
    59,
    60,
    60,
    61,
    61,
    62,
    62,
    63,
    63,
]


def ulaw_decode(ulaw_byte: int) -> int:
    ulaw_byte = ~ulaw_byte
    sign = (ulaw_byte & 0x80) >> 7
    exponent = ULAW_STEP_LOOKUP[ulaw_byte & 0x7F]
    sample = (exponent << 1) + 1 + ((exponent << 1) & (ulaw_byte & 0x0F))
    return -sample if sign else sample


def ulaw_to_pcm(ulaw_bytes: bytes) -> bytes:
    pcm_values = [ulaw_decode(b) for b in ulaw_bytes]
    return struct.pack("<" + "h" * len(pcm_values), *pcm_values)


def pcm_to_ulaw(pcm_bytes: bytes) -> bytes:
    num_samples = len(pcm_bytes) // 2
    samples = struct.unpack("<" + "h" * num_samples, pcm_bytes)
    return b"".join(struct.pack("B", linear2ulaw(s)) for s in samples)


def linear2ulaw(sample: int) -> int:
    if sample < 0:
        sample = -sample
        mask = 0x7F
    else:
        mask = 0xFF
    sample = min(sample, 0x3FFF)
    sample += ULAW_BIAS
    if sample >= 0x4000:
        clip = 0x3FFF - sample
        if clip > 255:
            clip = 255
        elif clip > 239:
            clip = 239
        exponent = (clip >> 8) & 0x07 if clip > 31 else 0
        ulaw = ((sample >> (exponent + 4)) & 0x0F) | (exponent << 4)
        return (mask ^ ulaw) & 0xFF
    for exp in range(7, -1, -1):
        if sample >= ULAW_BIAS << exp:
            exponent = exp
            break
    mantissa = (sample >> (exponent + 3)) & 0x0F
    ulaw = (exponent << 4) | mantissa
    return (mask ^ ulaw) & 0xFF


def resample(src: bytes, src_rate: int, dst_rate: int) -> bytes:
    if src_rate == dst_rate:
        return src
    num_samples = len(src) // 2
    samples = np.array(struct.unpack("<" + "h" * num_samples, src), dtype=np.float32)
    num_dst = int(num_samples * dst_rate / src_rate)
    indices = np.linspace(0, num_samples - 1, num_dst)
    resampled = np.interp(indices, np.arange(num_samples), samples).astype(np.int16)
    return struct.pack("<" + "h" * len(resampled), *resampled)


def compute_rms(ulaw_bytes: bytes) -> float:
    if not ulaw_bytes:
        return 0.0
    pcm = ulaw_to_pcm(ulaw_bytes)
    n = len(pcm) // 2
    samples = np.array(struct.unpack("<" + "h" * n, pcm), dtype=np.float32)
    return float(np.sqrt(np.mean(samples**2)))
