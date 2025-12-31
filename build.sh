#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Download and install TA-Lib C Library
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
make install
cd ..

# 2. Clean up source files to save space
rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# 3. Install Python dependencies
# We set include/library paths so the pip install can see the C headers
export TA_INCLUDE_PATH="/usr/include"
export TA_LIBRARY_PATH="/usr/lib"

pip install --upgrade pip
pip install -r requirements.txt
