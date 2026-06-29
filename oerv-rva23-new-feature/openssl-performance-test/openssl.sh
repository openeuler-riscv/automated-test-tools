#!/bin/bash
set -euo pipefail
OUTPUT="output.txt"
OUTPUT_ZBB="output_zbb.txt"

# clear file
> "$OUTPUT"
> "$OUTPUT_ZBB"

export OPENSSL_riscvcap=rv64gc
openssl speed md5 | tee -a "${OUTPUT}"

export OPENSSL_riscvcap=rv64gc_zbb
openssl speed md5 | tee -a "${OUTPUT_ZBB}"

export OPENSSL_riscvcap=rv64gc
openssl speed sha256 | tee -a "${OUTPUT}"
openssl speed sha512 | tee -a "${OUTPUT}"

export OPENSSL_riscvcap=rv64gc_zbb
openssl speed sha256 | tee -a "${OUTPUT_ZBB}"
openssl speed sha512 | tee -a "${OUTPUT_ZBB}"

# compare test result
python3 compare_result.py