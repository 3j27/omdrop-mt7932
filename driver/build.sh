#!/bin/bash
# Build the mt7932 module from a checked-out aurora-silicon/linux tree.
set -e
TREE=${1:?usage: build.sh /path/to/linux}
DIR="$TREE/drivers/net/wireless/mediatek/mt7932"
REL=$(uname -r)
LLVM_ARG=
if [ -x /usr/lib/llvm18/bin/clang ]; then
    LLVM_ARG="LLVM=/usr/lib/llvm18/bin/"
fi
make -C "/usr/lib/modules/$REL/build" $LLVM_ARG M="$DIR" modules
echo "built $DIR/mt7932-fullmac.ko for $REL"
