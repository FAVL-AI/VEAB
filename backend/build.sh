#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${ROOT_DIR}/bin"
mkdir -p "${BIN_DIR}"

echo "=== Building VEAP Native Backends ==="

# 1. Rust Verifier
echo "[1/3] Building Rust Verifier..."
if command -v cargo >/dev/null 2>&1; then
    cargo build --release --manifest-path "${ROOT_DIR}/rust_verifier/Cargo.toml"
    cp "${ROOT_DIR}/rust_verifier/target/release/veap-rust-verifier" "${BIN_DIR}/"
    echo "  -> ${BIN_DIR}/veap-rust-verifier built successfully."
else
    echo "  [WARN] cargo not found; skipping Rust verifier build."
fi

# 2. C++ Deterministic Physics Simulator
echo "[2/3] Building C++ Deterministic Simulator..."
if command -v clang++ >/dev/null 2>&1; then
    CXX=clang++ make -C "${ROOT_DIR}/cpp_engine"
    echo "  -> ${BIN_DIR}/veap-cpp-sim built successfully."
elif command -v g++ >/dev/null 2>&1; then
    CXX=g++ make -C "${ROOT_DIR}/cpp_engine"
    echo "  -> ${BIN_DIR}/veap-cpp-sim built successfully."
else
    echo "  [WARN] C++ compiler not found; skipping C++ simulator build."
fi

# 3. Go Concurrent Orchestrator
echo "[3/3] Building Go Concurrent Orchestrator..."
if command -v go >/dev/null 2>&1; then
    (cd "${ROOT_DIR}/go_orchestrator" && go build -o "${BIN_DIR}/veap-go-orchestrator" main.go)
    echo "  -> ${BIN_DIR}/veap-go-orchestrator built successfully."
elif command -v g++ >/dev/null 2>&1; then
    g++ -std=c++20 -O3 -Wall -Wextra -pthread "${ROOT_DIR}/go_orchestrator/fallback.cpp" -o "${BIN_DIR}/veap-go-orchestrator"
    echo "  -> ${BIN_DIR}/veap-go-orchestrator built via native C++20 fallback."
else
    echo "  [WARN] go not found; skipping Go orchestrator build."
fi

echo "=== Build Complete ==="
ls -lh "${BIN_DIR}"
