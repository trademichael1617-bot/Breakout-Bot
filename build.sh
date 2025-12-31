#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Download and Build TA-Lib C Library locally
if [ ! -d "ta-lib" ]; then
  wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
  tar -xzf ta-lib-0.4.0-src.tar.gz
fi

cd ta-lib/
# Use a local path for installation to avoid permission issues
./configure --prefix=$HOME/target
make
make install
cd ..

# 2. Tell Python where the library is located
export TA_INCLUDE_PATH=$HOME/target/include
export TA_LIBRARY_PATH=$HOME/target/lib
export LDFLAGS="-L$HOME/target/lib"
export CPPFLAGS="-I$HOME/target/include"

# 3. Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
