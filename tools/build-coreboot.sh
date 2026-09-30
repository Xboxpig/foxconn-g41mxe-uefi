#!/usr/bin/env bash
# Optional full coreboot rebuild, consuming an externally built EDK II payload.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$project_root"
payload="${1:-$project_root/releases/g41mxe-rtm1/support/UEFIPAYLOAD.fd}"
payload="$(realpath -- "$payload")"
test -f "$payload"
bash tools/prepare-sources.sh
mkdir -p build/coreboot-rtm
cp src/boards/foxconn-g41mxe/configs/coreboot-original-v5.config build/coreboot-rtm/.config
# This copy is generated build state; the retained original configuration is not edited.
sed -i \
  -e 's/^CONFIG_PAYLOAD_EDK2=y/# CONFIG_PAYLOAD_EDK2 is not set/' \
  -e 's/^# CONFIG_PAYLOAD_ELF is not set/CONFIG_PAYLOAD_ELF=y/' \
  -e 's/^CONFIG_PXE=y/# CONFIG_PXE is not set/' \
  -e "s|^CONFIG_PAYLOAD_FILE=.*|CONFIG_PAYLOAD_FILE=\"$payload\"|" \
  -e "s|../g41mxe-bios/microcode-2015/|$project_root/src/boards/foxconn-g41mxe/assets/microcode/|g" \
  build/coreboot-rtm/.config
toolchain_bin="$project_root/toolchains/coreboot/xgcc/bin"
test -x "$toolchain_bin/i386-elf-gcc"
test -x "$toolchain_bin/iasl"
export PATH="$toolchain_bin:$PATH"
export UPDATED_SUBMODULES=1
# xcompile caches compiler discovery; use a distinct cache for this toolchain.
make_args=(obj="$project_root/build/coreboot-rtm"
  DOTCONFIG="$project_root/build/coreboot-rtm/.config"
  XGCCPATH="$toolchain_bin/"
  xcompile="$project_root/build/coreboot-rtm/xcompile-local")
make -C build/coreboot "${make_args[@]}" olddefconfig
make -C build/coreboot "${make_args[@]}" -j16
printf 'Full rebuild: %s/build/coreboot-rtm/coreboot.rom (not the accepted RTM binary)\n' "$project_root"
