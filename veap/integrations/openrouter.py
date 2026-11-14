"""Optional read-only task-analysis expert; NEVER used as ground truth.

Requires an explicit CLI request and OPENROUTER_API_KEY. Sends only the selected
public scenario specification to OpenRouter. Does not issue robot commands.
"""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from typing import Any
from ..spec import Scenario

URL = "https://openrouter.ai/api/v1/chat/completions"


def review_scenario(scenario: Scenario, model: str | None = None) -> dict[str,Any]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = model or os.getenv("OPENROUTER_MODEL")
    if not api_key or not model:
        raise RuntimeError("Explicit OPENROUTER_API_KEY and OPENROUTER_MODEL required")
    if not (1 <= len(model) <= 150) or not all(c.isalnum() or c in "-._/" for c in model):
        raise ValueError("invalid model slug")
    messages = [
        {"role":"system","content":"You are an advisory benchmark-review agent. Return concise JSON with keys risk_notes (array of strings), evaluator_gaps (array of strings), recommended_tests (array of strings). No commands, no unverifiable evidence claims. This output is advisory only, not an oracle."},
        {"role":"user","content":"Identify validity risks in this public toy-simulator task definition; do not claim real-world assurance:\n" + scenario.model_dump_json()}
    ]
    payload = json.dumps({"model":model,"messages":messages,"temperature":0,
                          "max_tokens":500,"response_format":{"type":"json_object"}}).encode()
    req = urllib.request.Request(URL,data=payload,headers={
        "Authorization":"Bearer " + api_key,"Content-Type":"application/json",
        "X-Title":"VEAP Research Review"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            raw = response.read(150_000)
    except (urllib.error.HTTPError,urllib.error.URLError) as e:
        raise RuntimeError("External model request failed (no automatic retry)") from e
    body=json.loads(raw)
    try:
        content=body["choices"][0]["message"]["content"]
        result=json.loads(content)
    except (KeyError,ValueError,TypeError,IndexError) as e:
        raise ValueError("External model did not return valid JSON") from e
    if not isinstance(result,dict) or any(not isinstance(result.get(k),list) for k in ("risk_notes","evaluator_gaps","recommended_tests")):
        raise ValueError("Advisory response schema failed")
    normalized={k:[str(v)[:500] for v in result[k][:10]] for k in ("risk_notes","evaluator_gaps","recommended_tests")}
    return {"advisory_only":True,"not_part_of_benchmark":True,"model":model,
            "review":normalized,"usage":body.get("usage",{})}
