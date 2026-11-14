"""Evidence-gap triage: candidate causes, NEVER definitive causal attribution."""
from __future__ import annotations

CANDIDATES={
 'REQUIRED_TOPIC_MISSING':['recorder_selection','ROS2_namespace_or_remap','sensor_or_driver','message_transport'],
 'TOPIC_GAP':['sensor_driver','transport_or_DDS','recording_host_overload','clock_discontinuity'],
 'TIME_REVERSED':['clock_reset','bag_merge_or_sorting','transport_reordering'],
 'TYPE_MISMATCH':['contract_mapping_error','message_schema_change','topic_remap'],
 'HEADER_CLOCK_GAP':['unsynchronised_clocks','processing_latency','timestamp_driver_error'],
 'HEADER_TIMESTAMP_MISSING':['metadata_only_ingestion','message_header_not_decoded','sensor_has_no_header'],
 'FRAME_MISMATCH':['TF_configuration','sensor_calibration','frame_naming_error'],
 'EMPTY_RECORDING':['recorder_failure','topic_selection','empty_data_source'],
}

def triage(errors: list[dict]) -> list[dict]:
    return [{
        'observed_error_code':str(err.get('code','UNKNOWN')),
        'channel':err.get('channel'),
        'candidate_causes':CANDIDATES.get(str(err.get('code')),['unclassified']),
        'attribution_status':'HYPOTHESIS_ONLY',
        'verified_root_cause':None,
    } for err in errors]
