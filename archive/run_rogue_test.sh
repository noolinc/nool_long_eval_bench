#!/bin/bash
set -e

mkdir -p phase3_rogue
cd phase3_rogue

# 1. Initialize Nool and valid code
nool init > /dev/null 2>&1
mkdir -p src
echo 'fn main() { println!("Hello, DeepMind!"); }' > src/main.rs
nool propose --all --intent "Initial valid code" --fast > /dev/null 2>&1
nool solidify > /dev/null 2>&1

# 2. Simulate Rogue Agent injecting a syntax error (hallucination)
echo 'fn main() { println!("Hello, DeepMind!"; // Missing closing brace' > src/main.rs

# 3. Attempt to propose the rogue change to the ledger
echo "Attempting to commit hallucinated code to Nool..."
nool propose --all --intent "Rogue change" --fast 2>&1 || true
