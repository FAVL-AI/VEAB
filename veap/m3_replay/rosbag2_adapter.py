"""Optional read-only ROS 2 Humble / rosbag2 MCAP reader.

Must be run with the ROS 2 Python interpreter after sourcing /opt/ros/humble/setup.bash.
No rclpy node is constructed, no subscription or publisher, no /cmd_vel writes.
Serialized ROS messages are not deserialized in this stage; hence sensor
header clocks, TF frame graph and physical provenance are *not* validated.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterator
from .core import RECORD_SCHEMA, ContractError


def iter_rosbag2_mcap(uri: str | Path, *, decode_headers: bool = False) -> Iterator[dict]:
    path = Path(uri)
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        import rosbag2_py  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            'rosbag2_py not available in this Python environment. '
            'Use: source /opt/ros/humble/setup.bash; /usr/bin/python3 -m veap.m3_replay.cli ...'
        ) from exc
    if decode_headers:
        try:
            from rclpy.serialization import deserialize_message
            from rosidl_runtime_py.utilities import get_message
        except ImportError as exc:
            raise RuntimeError('ROS2 message deserialization packages unavailable') from exc
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(path), storage_id='mcap'),
        rosbag2_py.ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'),
    )
    topics = {t.name: t.type for t in reader.get_all_topics_and_types()}
    classes = {name: get_message(kind) for name,kind in topics.items()} if decode_headers else {}
    while reader.has_next():
        topic, serialized_data, receive_timestamp_ns = reader.read_next()
        item = {
            'schema_version':RECORD_SCHEMA,
            'topic':topic,
            'ros_type':topics[topic],
            'log_time_ns':int(receive_timestamp_ns),
            # Header clock/frame absent until explicitly decoded from ROS2 message.
        }
        if decode_headers:
            try:
                message = deserialize_message(serialized_data, classes[topic])
                header = getattr(message, 'header', None)
                if header is None and hasattr(message, 'transforms'):
                    transforms = list(message.transforms)
                    header = transforms[0].header if transforms else None
                if header is not None:
                    stamp = getattr(header, 'stamp', None)
                    if stamp is not None:
                        item['header_stamp_ns'] = int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
                    item['frame_id'] = str(getattr(header, 'frame_id', ''))
            except (ValueError, AttributeError, RuntimeError, TypeError) as exc:
                raise RuntimeError(f'Cannot decode ROS2 message on {topic}: {exc}') from exc
        yield item


def require_rosbag_input(uri: str | Path) -> str:
    path = Path(uri)
    if not path.exists():
        raise ContractError(f'bag not found: {path}')
    if path.is_file() and path.suffix.lower() != '.mcap':
        raise ContractError('use MCAP input or a rosbag2 directory containing MCAP')
    return str(path)
