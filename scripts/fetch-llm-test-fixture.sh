#!/usr/bin/env bash
# Download the pinned tiny GGUF used by real-backend LLM tests.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_DIR="${ROOT}/tests/fixtures"
DEST="${DEST_DIR}/stories15M-q4_0.gguf"
# Pinned ggml-org/tiny-llamas stories15M Q4_0 (~19 MiB).
URL="https://huggingface.co/ggml-org/tiny-llamas/resolve/def3e2dd70df35ecbf6403ea347de4c5977220c1/stories15M-q4_0.gguf"
EXPECTED_SHA256="6151b1929d7f5aa3385d9ddef3393e55587c0a55de661562322bc51dfda93a04"

mkdir -p "${DEST_DIR}"

if [[ -f "${DEST}" ]]; then
  ACTUAL="$(sha256sum "${DEST}" | awk '{print $1}')"
  if [[ "${ACTUAL}" == "${EXPECTED_SHA256}" ]]; then
    echo "LLM test fixture already present: ${DEST}"
    exit 0
  fi
  echo "Existing fixture checksum mismatch; re-downloading." >&2
  rm -f "${DEST}"
fi

echo "Downloading pinned tiny GGUF to ${DEST}"
curl -L --fail --retry 3 --output "${DEST}.partial" "${URL}"
ACTUAL="$(sha256sum "${DEST}.partial" | awk '{print $1}')"
if [[ "${ACTUAL}" != "${EXPECTED_SHA256}" ]]; then
  rm -f "${DEST}.partial"
  echo "Checksum mismatch for LLM test fixture." >&2
  echo "expected ${EXPECTED_SHA256}" >&2
  echo "actual   ${ACTUAL}" >&2
  exit 1
fi
mv "${DEST}.partial" "${DEST}"
echo "LLM test fixture ready: ${DEST}"
