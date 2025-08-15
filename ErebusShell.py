#!/usr/bin/env python3
"""
ErebusShell - Professional Shellcode Crypter & MalDev Toolkit
Handles encryption, obfuscation, and key management for shellcode
"""

import os
import sys
import hashlib
import random
import base64
import gzip
import json
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import secrets
import math
import struct

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import padding

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

# Version
VERSION = "2.0.0"


class Colors:
    """Terminal colors for output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class EncryptionMethod(Enum):
    """Supported encryption methods"""
    XOR = "xor"
    XOR_FEEDBACK = "xor_feedback"
    RC4 = "rc4"
    AES_CBC = "aes_cbc"
    AES_CTR = "aes_ctr"
    CHACHA20 = "chacha20"
    CUSTOM_FEISTEL = "feistel"
    LAYERED = "layered"


class ObfuscationMethod(Enum):
    """Supported obfuscation methods"""
    MAC = "mac"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    UUID = "uuid"
    BASE64 = "base64"
    BASE85 = "base85"
    HEX = "hex"


class OutputFormat(Enum):
    """Output format types"""
    C_ARRAY = "c"
    CSHARP_ARRAY = "csharp"
    PYTHON_ARRAY = "python"
    POWERSHELL_ARRAY = "powershell"
    RAW = "raw"
    HEX = "hex"
    BASE64 = "base64"


class ShellcodeCrypter:
    """Core encryption functionality for shellcode"""

    def __init__(self):
        self.keys_used = []  # Track all keys for session

    def calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data"""
        if not data:
            return 0.0

        frequency = {}
        for byte in data:
            frequency[byte] = frequency.get(byte, 0) + 1

        entropy = 0.0
        data_len = len(data)

        for count in frequency.values():
            probability = count / data_len
            if probability > 0:
                entropy -= probability * math.log2(probability)

        return entropy

    def generate_key(self, length: int = 16, readable: bool = False) -> bytes:
        """Generate cryptographically secure key"""
        if readable:
            # Generate ASCII printable key for easier handling
            chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            key = ''.join(secrets.choice(chars) for _ in range(length))
            return key.encode()
        else:
            return secrets.token_bytes(length)

    def xor_encrypt(self, data: bytes, key: bytes) -> bytes:
        """Simple XOR encryption"""
        return bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])

    def xor_with_feedback(self, data: bytes, key: bytes) -> bytes:
        """XOR with feedback - each byte affects the next"""
        result = bytearray()
        feedback = 0x5A

        for i, byte in enumerate(data):
            key_byte = key[i % len(key)]
            encrypted = byte ^ key_byte ^ feedback
            result.append(encrypted)
            feedback = encrypted

        return bytes(result)

    def rc4_encrypt(self, data: bytes, key: bytes) -> bytes:
        """RC4 stream cipher"""
        S = list(range(256))
        j = 0

        # Key Scheduling Algorithm
        for i in range(256):
            j = (j + S[i] + key[i % len(key)]) % 256
            S[i], S[j] = S[j], S[i]

        # Pseudo-Random Generation Algorithm
        i = j = 0
        result = bytearray()

        for byte in data:
            i = (i + 1) % 256
            j = (j + S[i]) % 256
            S[i], S[j] = S[j], S[i]
            k = S[(S[i] + S[j]) % 256]
            result.append(byte ^ k)

        return bytes(result)

    def custom_feistel(self, data: bytes, key: bytes, rounds: int = 16) -> bytes:
        """Custom Feistel network encryption"""
        # Pad to even length
        if len(data) % 2:
            data += b'\x00'

        result = bytearray(data)
        key_hash = hashlib.sha256(key).digest()

        for round_num in range(rounds):
            # Generate round key
            round_key = hashlib.sha256(key_hash + round_num.to_bytes(1, 'little')).digest()

            # Process blocks
            for i in range(0, len(result), 2):
                if i + 1 < len(result):
                    left = result[i]
                    right = result[i + 1]

                    # Feistel function
                    f_output = (right + round_key[i % 32]) & 0xFF
                    f_output = ((f_output << 3) | (f_output >> 5)) & 0xFF
                    f_output ^= round_key[(i + 1) % 32]

                    # Swap and XOR
                    result[i] = right
                    result[i + 1] = left ^ f_output

        return bytes(result)

    def aes_encrypt(self, data: bytes, key: bytes, mode: str = "cbc") -> Tuple[bytes, bytes]:
        """AES encryption with CBC or CTR mode"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library required for AES. Install: pip install cryptography")

        # Ensure 256-bit key
        if len(key) < 32:
            key = hashlib.sha256(key).digest()
        else:
            key = key[:32]

        if mode == "cbc":
            iv = os.urandom(16)
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(data) + padder.finalize()

            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            encrypted = encryptor.update(padded_data) + encryptor.finalize()
            return encrypted, iv

        elif mode == "ctr":
            nonce = os.urandom(16)
            cipher = Cipher(
                algorithms.AES(key),
                modes.CTR(nonce),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            encrypted = encryptor.update(data) + encryptor.finalize()
            return encrypted, nonce

    def chacha20_encrypt(self, data: bytes, key: bytes) -> Tuple[bytes, bytes]:
        """ChaCha20 stream cipher encryption"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library required for ChaCha20")

        # Ensure 256-bit key
        if len(key) < 32:
            key = hashlib.sha256(key).digest()
        else:
            key = key[:32]

        nonce = os.urandom(16)
        algorithm = algorithms.ChaCha20(key, nonce)
        cipher = Cipher(algorithm, mode=None, backend=default_backend())
        encryptor = cipher.encryptor()

        encrypted = encryptor.update(data) + encryptor.finalize()
        return encrypted, nonce

    def layered_encryption(self, data: bytes, master_key: bytes) -> Tuple[bytes, Dict[str, str]]:
        """Multi-layered encryption for maximum protection"""
        keys = {}

        # Layer 1: XOR with feedback
        layer1_key = hashlib.sha256(master_key + b"layer1").digest()[:16]
        data = self.xor_with_feedback(data, layer1_key)
        keys['layer1_xor_feedback'] = layer1_key.hex()

        # Layer 2: Custom Feistel
        layer2_key = hashlib.sha256(master_key + b"layer2").digest()[:16]
        data = self.custom_feistel(data, layer2_key, rounds=8)
        keys['layer2_feistel'] = layer2_key.hex()

        # Layer 3: RC4
        layer3_key = hashlib.sha256(master_key + b"layer3").digest()[:16]
        data = self.rc4_encrypt(data, layer3_key)
        keys['layer3_rc4'] = layer3_key.hex()

        return data, keys


class ShellcodeObfuscator:
    """Obfuscation techniques for shellcode"""

    @staticmethod
    def to_c_array(data: bytes, var_name: str = "shellcode") -> str:
        """Convert to C array format"""
        lines = [f"unsigned char {var_name}[] = {{"]

        for i in range(0, len(data), 16):
            hex_bytes = ', '.join([f'0x{b:02x}' for b in data[i:i + 16]])
            if i + 16 < len(data):
                hex_bytes += ','
            lines.append(f"    {hex_bytes}")

        lines.append("};")
        lines.append(f"unsigned int {var_name}_len = sizeof({var_name});")
        return '\n'.join(lines)

    @staticmethod
    def to_csharp_array(data: bytes, var_name: str = "shellcode") -> str:
        """Convert to C# array format"""
        lines = [f"byte[] {var_name} = new byte[{len(data)}] {{"]

        for i in range(0, len(data), 16):
            hex_bytes = ', '.join([f'0x{b:02x}' for b in data[i:i + 16]])
            if i + 16 < len(data):
                hex_bytes += ','
            lines.append(f"    {hex_bytes}")

        lines.append("};")
        return '\n'.join(lines)

    @staticmethod
    def to_python_array(data: bytes, var_name: str = "shellcode") -> str:
        """Convert to Python array format"""
        lines = [f"{var_name} = bytearray(["]

        for i in range(0, len(data), 16):
            hex_bytes = ', '.join([f'0x{b:02x}' for b in data[i:i + 16]])
            if i + 16 < len(data):
                hex_bytes += ','
            lines.append(f"    {hex_bytes}")

        lines.append("])")
        return '\n'.join(lines)

    @staticmethod
    def to_powershell_array(data: bytes, var_name: str = "$shellcode") -> str:
        """Convert to PowerShell array format"""
        lines = [f"[Byte[]] {var_name} = @("]

        for i in range(0, len(data), 16):
            hex_bytes = ', '.join([f'0x{b:02x}' for b in data[i:i + 16]])
            if i + 16 < len(data):
                hex_bytes += ','
            lines.append(f"    {hex_bytes}")

        lines.append(")")
        return '\n'.join(lines)

    @staticmethod
    def to_mac_addresses(data: bytes) -> List[str]:
        """Convert to MAC address format"""
        # Pad to multiple of 6
        while len(data) % 6 != 0:
            data += b'\x90'

        macs = []
        for i in range(0, len(data), 6):
            mac = '-'.join([f'{b:02X}' for b in data[i:i + 6]])
            macs.append(mac)
        return macs

    @staticmethod
    def to_ipv4_addresses(data: bytes) -> List[str]:
        """Convert to IPv4 address format"""
        # Pad to multiple of 4
        while len(data) % 4 != 0:
            data += b'\x90'

        ips = []
        for i in range(0, len(data), 4):
            ip = '.'.join([str(b) for b in data[i:i + 4]])
            ips.append(ip)
        return ips

    @staticmethod
    def to_ipv6_addresses(data: bytes) -> List[str]:
        """Convert to IPv6 address format"""
        # Pad to multiple of 16
        while len(data) % 16 != 0:
            data += b'\x90'

        ipv6s = []
        for i in range(0, len(data), 16):
            parts = []
            for j in range(0, 16, 2):
                if i + j + 1 < len(data):
                    part = f'{data[i + j]:02X}{data[i + j + 1]:02X}'
                else:
                    part = f'{data[i + j]:02X}00'
                parts.append(part)
            ipv6 = ':'.join(parts)
            ipv6s.append(ipv6)
        return ipv6s

    @staticmethod
    def to_uuid_strings(data: bytes) -> List[str]:
        """Convert to UUID format"""
        # Pad to multiple of 16
        while len(data) % 16 != 0:
            data += b'\x90'

        uuids = []
        for i in range(0, len(data), 16):
            chunk = data[i:i + 16]
            uuid = f'{chunk[0:4].hex().upper()}-'
            uuid += f'{chunk[4:6].hex().upper()}-'
            uuid += f'{chunk[6:8].hex().upper()}-'
            uuid += f'{chunk[8:10].hex().upper()}-'
            uuid += f'{chunk[10:16].hex().upper()}'
            uuids.append(uuid)
        return uuids


class APIHasher:
    """Generate API hashes for dynamic resolution"""

    @staticmethod
    def djb2_hash(data: str, encoding: str = 'ascii') -> int:
        """DJB2 hash algorithm"""
        hash_val = 5381
        for byte in data.encode(encoding):
            hash_val = ((hash_val << 5) + hash_val) + byte
            hash_val &= 0xFFFFFFFF
        return hash_val

    @staticmethod
    def ror13_hash(data: str, encoding: str = 'ascii') -> int:
        """ROR13 hash algorithm"""
        hash_val = 0
        for byte in data.encode(encoding):
            hash_val = ((hash_val >> 13) | (hash_val << 19)) + byte
            hash_val &= 0xFFFFFFFF
        return hash_val

    @staticmethod
    def fnv1a_hash(data: str, encoding: str = 'ascii') -> int:
        """FNV-1a hash algorithm"""
        hash_val = 0x811c9dc5
        for byte in data.encode(encoding):
            hash_val ^= byte
            hash_val = (hash_val * 0x01000193) & 0xFFFFFFFF
        return hash_val

    def generate_header(self, apis: List[str], algorithm: str = 'djb2') -> str:
        """Generate C header file with API hashes"""
        lines = [
            "// API Hashes Generated by ErebusShell",
            f"// Algorithm: {algorithm.upper()}",
            f"// Generated: {datetime.now().isoformat()}",
            "#pragma once\n"
        ]

        hash_func = getattr(self, f"{algorithm}_hash")

        for api in apis:
            # Handle both DLL and function names
            safe_name = api.upper().replace('.', '_').replace('-', '_')
            hash_val = hash_func(api)
            lines.append(f"#define HASH_{safe_name:<30} 0x{hash_val:08X}  // {api}")

        return '\n'.join(lines)


class KeyManager:
    """Manage encryption keys and metadata"""

    def __init__(self):
        self.keys_db = {}

    def store_key(self, identifier: str, key: bytes, metadata: Dict[str, Any]) -> None:
        """Store key with metadata"""
        self.keys_db[identifier] = {
            'key': key.hex(),
            'created': datetime.now().isoformat(),
            'metadata': metadata
        }

    def export_keys(self, filepath: str) -> None:
        """Export keys to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.keys_db, f, indent=2)

    def import_keys(self, filepath: str) -> None:
        """Import keys from JSON file"""
        with open(filepath, 'r') as f:
            self.keys_db = json.load(f)


def print_banner():
    """Print tool banner"""
    banner = f"""{Colors.CYAN}
╔══════════════════════════════════════════════════════════════╗
║               ErebusShell - Shellcode Crypter               ║
║                                    ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(banner)


def process_shellcode(args):
    """Main processing function"""

    # Initialize components
    crypter = ShellcodeCrypter()
    obfuscator = ShellcodeObfuscator()
    key_manager = KeyManager()

    # Read shellcode
    try:
        with open(args.input, 'rb') as f:
            shellcode = f.read()
    except Exception as e:
        print(f"{Colors.RED}[!] Error reading file: {e}{Colors.RESET}")
        sys.exit(1)

    print(f"{Colors.GREEN}[+] Loaded shellcode: {len(shellcode)} bytes{Colors.RESET}")

    # Calculate original entropy
    original_entropy = crypter.calculate_entropy(shellcode)
    print(f"{Colors.BLUE}[*] Original entropy: {original_entropy:.4f}{Colors.RESET}")

    # Compress if requested
    if args.compress:
        compressed = gzip.compress(shellcode, compresslevel=9)
        print(f"{Colors.YELLOW}[*] Compressed: {len(shellcode)} -> {len(compressed)} bytes{Colors.RESET}")
        shellcode = compressed

    # Generate or use provided key
    if args.key:
        key = bytes.fromhex(args.key)
        print(f"{Colors.CYAN}[*] Using provided key{Colors.RESET}")
    else:
        key = crypter.generate_key(args.key_size, args.readable_key)
        print(f"{Colors.CYAN}[*] Generated {args.key_size}-byte key: {key.hex()}{Colors.RESET}")

    # Encrypt based on method
    metadata = {
        'original_size': len(shellcode),
        'method': args.method,
        'timestamp': datetime.now().isoformat()
    }

    if args.method == 'xor':
        encrypted = crypter.xor_encrypt(shellcode, key)
    elif args.method == 'xor_feedback':
        encrypted = crypter.xor_with_feedback(shellcode, key)
    elif args.method == 'rc4':
        encrypted = crypter.rc4_encrypt(shellcode, key)
    elif args.method == 'feistel':
        encrypted = crypter.custom_feistel(shellcode, key)
    elif args.method == 'aes_cbc':
        encrypted, iv = crypter.aes_encrypt(shellcode, key, "cbc")
        metadata['iv'] = iv.hex()
    elif args.method == 'aes_ctr':
        encrypted, nonce = crypter.aes_encrypt(shellcode, key, "ctr")
        metadata['nonce'] = nonce.hex()
    elif args.method == 'chacha20':
        encrypted, nonce = crypter.chacha20_encrypt(shellcode, key)
        metadata['nonce'] = nonce.hex()
    elif args.method == 'layered':
        encrypted, layer_keys = crypter.layered_encryption(shellcode, key)
        metadata['layer_keys'] = layer_keys
    # Obfuscation methods
    elif args.method == 'mac':
        macs = obfuscator.to_mac_addresses(shellcode)
        encrypted = '\n'.join(macs).encode()
    elif args.method == 'ipv4':
        ips = obfuscator.to_ipv4_addresses(shellcode)
        encrypted = '\n'.join(ips).encode()
    elif args.method == 'ipv6':
        ipv6s = obfuscator.to_ipv6_addresses(shellcode)
        encrypted = '\n'.join(ipv6s).encode()
    elif args.method == 'uuid':
        uuids = obfuscator.to_uuid_strings(shellcode)
        encrypted = '\n'.join(uuids).encode()
    elif args.method == 'base64':
        encrypted = base64.b64encode(shellcode)
    elif args.method == 'base85':
        encrypted = base64.b85encode(shellcode)
    elif args.method == 'hex':
        encrypted = shellcode.hex().encode()
    else:
        encrypted = shellcode

    # Calculate final entropy
    final_entropy = crypter.calculate_entropy(encrypted)
    print(f"{Colors.BLUE}[*] Final entropy: {final_entropy:.4f}{Colors.RESET}")

    metadata['final_size'] = len(encrypted)
    metadata['entropy_change'] = final_entropy - original_entropy

    # Store key if identifier provided
    if args.key_id:
        key_manager.store_key(args.key_id, key, metadata)
        key_manager.export_keys(f"{args.key_id}_keys.json")
        print(f"{Colors.GREEN}[+] Key stored with ID: {args.key_id}{Colors.RESET}")

    # Format output
    if args.format == 'c':
        output = obfuscator.to_c_array(encrypted, args.var_name or "shellcode")
    elif args.format == 'csharp':
        output = obfuscator.to_csharp_array(encrypted, args.var_name or "shellcode")
    elif args.format == 'python':
        output = obfuscator.to_python_array(encrypted, args.var_name or "shellcode")
    elif args.format == 'powershell':
        output = obfuscator.to_powershell_array(encrypted, args.var_name or "$shellcode")
    elif args.format == 'hex':
        output = encrypted.hex()
    elif args.format == 'base64':
        output = base64.b64encode(encrypted).decode()
    else:  # raw
        output = encrypted

    # Save output
    if args.output:
        if isinstance(output, bytes):
            mode = 'wb'
        else:
            mode = 'w'

        with open(args.output, mode) as f:
            f.write(output)
        print(f"{Colors.GREEN}[+] Output saved to: {args.output}{Colors.RESET}")
    else:
        if isinstance(output, bytes):
            sys.stdout.buffer.write(output)
        else:
            print(output)

    # Save metadata
    if args.save_metadata:
        metadata_file = args.output + '.meta.json' if args.output else 'metadata.json'
        metadata['key'] = key.hex()
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"{Colors.GREEN}[+] Metadata saved to: {metadata_file}{Colors.RESET}")

    # Print summary
    print(f"\n{Colors.CYAN}=== Encryption Summary ==={Colors.RESET}")
    print(f"Method: {args.method}")
    print(f"Key: {key.hex()}")
    print(f"Original Size: {metadata['original_size']} bytes")
    print(f"Final Size: {metadata['final_size']} bytes")
    print(f"Entropy Change: {metadata['entropy_change']:.4f}")

    if 'iv' in metadata:
        print(f"IV: {metadata['iv']}")
    if 'nonce' in metadata:
        print(f"Nonce: {metadata['nonce']}")


def hash_apis(args):
    """Generate API hashes"""
    hasher = APIHasher()

    # Default APIs if no file provided
    default_apis = [
        'kernel32.dll', 'ntdll.dll', 'user32.dll', 'advapi32.dll',
        'VirtualAlloc', 'VirtualProtect', 'CreateThread',
        'LoadLibraryA', 'GetProcAddress', 'OpenProcess',
        'WriteProcessMemory', 'NtQuerySystemInformation'
    ]

    if args.api_file:
        with open(args.api_file, 'r') as f:
            apis = [line.strip() for line in f if line.strip()]
    else:
        apis = default_apis

    output = hasher.generate_header(apis, args.hash_algorithm)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"{Colors.GREEN}[+] API hashes saved to: {args.output}{Colors.RESET}")
    else:
        print(output)


def main():
    parser = argparse.ArgumentParser(
        description='ErebusShell - Professional Shellcode Crypter & MalDev Toolkit',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Encrypt command
    encrypt_parser = subparsers.add_parser('encrypt', help='Encrypt shellcode')
    encrypt_parser.add_argument('input', help='Input shellcode file')
    encrypt_parser.add_argument('method',
                                choices=['xor', 'xor_feedback', 'rc4', 'feistel',
                                         'aes_cbc', 'aes_ctr', 'chacha20', 'layered',
                                         'mac', 'ipv4', 'ipv6', 'uuid',
                                         'base64', 'base85', 'hex'],
                                help='Encryption or obfuscation method')
    encrypt_parser.add_argument('-o', '--output', help='Output file')
    encrypt_parser.add_argument('-f', '--format',
                                choices=['c', 'csharp', 'python', 'powershell', 'raw', 'hex', 'base64'],
                                default='c',
                                help='Output format (default: c)')
    encrypt_parser.add_argument('-k', '--key', help='Encryption key in hex')
    encrypt_parser.add_argument('--key-size', type=int, default=16,
                                help='Key size in bytes (default: 16)')
    encrypt_parser.add_argument('--readable-key', action='store_true',
                                help='Generate ASCII readable key')
    encrypt_parser.add_argument('--compress', action='store_true',
                                help='Compress before encryption')
    encrypt_parser.add_argument('--var-name', help='Variable name for array output')
    encrypt_parser.add_argument('--key-id', help='Identifier to store key')
    encrypt_parser.add_argument('--save-metadata', action='store_true',
                                help='Save encryption metadata to JSON')

    # Hash command
    hash_parser = subparsers.add_parser('hash', help='Generate API hashes')
    hash_parser.add_argument('--api-file', help='File containing API names')
    hash_parser.add_argument('--hash-algorithm',
                             choices=['djb2', 'ror13', 'fnv1a'],
                             default='djb2',
                             help='Hash algorithm (default: djb2)')
    hash_parser.add_argument('-o', '--output', help='Output header file')

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        print_banner()
        parser.print_help()
        sys.exit(0)

    # Execute command
    if args.command == 'encrypt':
        print_banner()
        process_shellcode(args)
    elif args.command == 'hash':
        hash_apis(args)


if __name__ == '__main__':
    main()