import random
import string

HEX_CHARS = "0123456789ABCDEF"
KEY_SIZE = 21


def _checksum(s: str) -> str:
    r = 0
    for ch in s:
        r += ord(ch) % 16
    return HEX_CHARS[r % 16]


def _random_char() -> str:
    n = random.randint(1, 100)
    if n <= 40:
        return random.choice(string.ascii_uppercase)
    if n <= 80:
        return random.choice(string.ascii_lowercase)
    return random.choice(string.digits)


def generate_flash_key() -> str:
    body_len = KEY_SIZE - (1 + 3)
    body = "".join(_random_char() for _ in range(body_len))
    return body + _checksum(body)
