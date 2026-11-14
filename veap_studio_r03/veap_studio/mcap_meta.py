"""Minimal defensive MCAP container metadata reader; does not decode ROS messages.

Reads top-level records and uses summary statistics where present. No decompression.
The official 'mcap' Python reader is required for actual message decoding.
"""
import struct
from pathlib import Path
MAGIC=b'\x89MCAP0\r\n'

def probe(path):
    path=Path(path)
    size=path.stat().st_size
    if size<36: raise ValueError('MCAP file too short')
    topics={};stats=None; chunks=0; message_count=0; footer=False; data_end=False
    def getstr(raw,pos):
        if pos+4>len(raw):raise ValueError('invalid MCAP string')
        n=struct.unpack_from('<I',raw,pos)[0];pos+=4
        if n>100000 or pos+n>len(raw):raise ValueError('oversized/malformed MCAP string')
        return raw[pos:pos+n].decode('utf-8','replace'),pos+n
    with path.open('rb') as f:
        if f.read(8)!=MAGIC:raise ValueError('invalid MCAP start magic')
        f.seek(size-8)
        if f.read(8)!=MAGIC:raise ValueError('missing MCAP terminal magic (possibly truncated)')
        f.seek(8)
        if f.read(1)!=b'\x01':raise ValueError('MCAP Header record not found')
        f.seek(8)
        while f.tell()<size-8:
            head=f.read(9)
            if len(head)!=9:raise ValueError('truncated MCAP record header')
            op=head[0]; n=struct.unpack_from('<Q',head,1)[0]
            if n>size-8-f.tell():raise ValueError('MCAP record length exceeds file')
            if op==0x04 and n<=200_000: # Channel
                raw=f.read(n)
                if len(raw)>=4:
                    channel_id,schema_id=struct.unpack_from('<HH',raw,0)
                    try:topic,p=getstr(raw,4);enc,p=getstr(raw,p)
                    except ValueError: topic,enc='malformed','unknown'
                    topics[str(channel_id)]={'topic':topic,'encoding':enc,'schema_id':schema_id}
            elif op==0x0B and n>=42 and n<=200_000: # Statistics
                raw=f.read(n)
                stats={'message_count':struct.unpack_from('<Q',raw,0)[0],
                       'channel_count':struct.unpack_from('<I',raw,10)[0],
                       'start_ns':struct.unpack_from('<Q',raw,26)[0],
                       'end_ns':struct.unpack_from('<Q',raw,34)[0] if len(raw)>=42 else None}
            else:
                f.seek(n,1)
            if op==0x0F:data_end=True
            if op==0x05:message_count+=1
            if op==0x06:chunks+=1
            if op==0x02: footer=True;break
        if not footer:raise ValueError('MCAP Footer record not found')
        if not data_end:raise ValueError('MCAP Data End record not found')
        if f.tell()!=size-8:raise ValueError('unexpected bytes after MCAP Footer')
    return {'format':'MCAP','container_valid':True,'channels':list(topics.values()),'chunk_count':chunks,
            'direct_message_records':message_count,'statistics':stats,
            'decode_status':'NOT_DECODED; install official mcap/ROS2 adapter to extract messages',
            'metadata_completeness':'PARTIAL' if not topics and chunks else 'TOP_LEVEL_ONLY',
            'source_authenticity':'UNATTESTED'}
