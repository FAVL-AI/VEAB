"""Native backend wrappers for C++, Go, and Rust components."""
from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

BIN_DIR = Path(__file__).resolve().parent.parent / "backend" / "bin"
RUST_VERIFIER_BIN = BIN_DIR / "veap-rust-verifier"
CPP_SIM_BIN = BIN_DIR / "veap-cpp-sim"
GO_ORCHESTRATOR_BIN = BIN_DIR / "veap-go-orchestrator"


def has_rust_verifier() -> bool:
    return RUST_VERIFIER_BIN.exists() and bool(shutil.which(str(RUST_VERIFIER_BIN)))


def has_cpp_sim() -> bool:
    return CPP_SIM_BIN.exists() and bool(shutil.which(str(CPP_SIM_BIN)))


def has_go_orchestrator() -> bool:
    return GO_ORCHESTRATOR_BIN.exists() and bool(shutil.which(str(GO_ORCHESTRATOR_BIN)))


def run_rust_verifier(bundle_path: Path | str) -> dict[str, Any]:
    """Execute the Rust native verifier against an evidence bundle file."""
    if not has_rust_verifier():
        raise FileNotFoundError(f"Rust verifier binary not found at {RUST_VERIFIER_BIN}")
    
    cmd = [str(RUST_VERIFIER_BIN), str(bundle_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Rust verifier output invalid JSON: {proc.stdout} (err: {proc.stderr})") from err
    return data


def run_cpp_sim(
    shielded: bool = False,
    fault: str = "none",
    seed: int = 42
) -> dict[str, Any]:
    """Execute the C++ deterministic kinematic physics engine."""
    if not has_cpp_sim():
        raise FileNotFoundError(f"C++ simulator binary not found at {CPP_SIM_BIN}")
    
    cmd = [str(CPP_SIM_BIN), "--fault", fault, "--seed", str(seed)]
    if shielded:
        cmd.append("--shielded")
    
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def run_go_orchestrator(seeds: int = 20) -> dict[str, Any]:
    """Execute the Go high-throughput concurrent orchestrator."""
    if not has_go_orchestrator():
        raise FileNotFoundError(f"Go orchestrator binary not found at {GO_ORCHESTRATOR_BIN}")
    
    cmd = [str(GO_ORCHESTRATOR_BIN), "-seeds", str(seeds)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)

