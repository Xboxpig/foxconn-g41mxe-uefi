#!/usr/bin/env bash
# RTM is immutable. Every rebuild goes to build/artifacts, never releases/.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$project_root"
case "${1:-}" in
  '') repack_only=false ;;
  --repack-only) repack_only=true ;;
  *) printf 'Usage: %s [--repack-only]\n' "$0" >&2; exit 2 ;;
esac
bash tools/prepare-sources.sh
mkdir -p build/artifacts
make -C build/coreboot/util/cbfstool -j16
if "$repack_only"; then
  payload="$project_root/releases/g41mxe-rtm1/support/UEFIPAYLOAD.fd"
else
  csm_output="$project_root/build/seabios-csm/"
  make -C build/seabios OUT="$csm_output" \
    KCONFIG_CONFIG="$project_root/src/boards/foxconn-g41mxe/configs/seabios-csm.config" -j16
  mkdir -p build/asus-ui
  PYTHONPATH="$project_root/src/asus-ui/tools" python \
    src/boards/foxconn-g41mxe/asus-ui/patch_g41_platform_ui.py \
    src/asus-ui/assets --native-csm --output-dir build/asus-ui \
    --header-output build/edk2/UefiPayloadPkg/AsusSetupHiiDxe/G41NativeOptions.h
  make -C build/edk2/BaseTools -j16
  (
    export WORKSPACE="$project_root/build/edk-workspace"
    export PACKAGES_PATH="$project_root/build/edk2"
    export EDK_TOOLS_PATH="$PACKAGES_PATH/BaseTools"
    mkdir -p "$WORKSPACE"
    cd "$WORKSPACE"
    # EDK's setup script references optional unset environment variables.
    set +u
    source "$PACKAGES_PATH/edksetup.sh" >/dev/null
    set -u
    build -n 16 -a IA32 -a X64 -b RELEASE -p UefiPayloadPkg/UefiPayloadPkg.dsc -t GCC \
      -D BOOTLOADER=COREBOOT -q -s -D BOOT_MANAGER_ESCAPE=TRUE -D CPU_TIMER_LIB_ENABLE=FALSE \
      --pcd gEfiMdePkgTokenSpaceGuid.PcdPciExpressBaseAddress=0xe0000000 \
      --pcd gEfiMdePkgTokenSpaceGuid.PcdPciExpressBaseSize=0x10000000 \
      -D PS2_KEYBOARD_ENABLE=TRUE -D PLATFORM_BOOT_TIMEOUT=5 -D SIO_BUS_ENABLE=TRUE \
      -D SD_MMC_TIMEOUT=10000 -D PRIORITIZE_INTERNAL=TRUE -D TIMER_SUPPORT=LAPIC \
      -D NETWORK_IPXE=TRUE --pcd 'gUefiPayloadPkgTokenSpaceGuid.PcdiPXEOptionName=LiPXE Network Boot' \
      -D LVGL_ENABLE=TRUE --pcd gEfiMdeModulePkgTokenSpaceGuid.PcdConOutRow=0 \
      --pcd gEfiMdeModulePkgTokenSpaceGuid.PcdConOutColumn=0 \
      --pcd gEfiMdeModulePkgTokenSpaceGuid.PcdSetupConOutRow=0 \
      --pcd gEfiMdeModulePkgTokenSpaceGuid.PcdSetupConOutColumn=0 \
      --pcd gEfiMdeModulePkgTokenSpaceGuid.PcdAcpiDefaultOemId=COREv4 \
      --pcd gUefiCpuPkgTokenSpaceGuid.PcdFirstTimeWakeUpAPsBySipi=FALSE \
      --pcd gEfiMdeModulePkgTokenSpaceGuid.PcdSmbiosVersion=0x0300 \
      --pcd gEfiMdeModulePkgTokenSpaceGuid.PcdSmbiosDocRev=0x0 \
      -D ASUS_AMITSE_LAB=TRUE -D ASUS_SETUP_PAGE_LAB=TRUE -D ASUS_SETUP_HII_DATA_ONLY=TRUE \
      -D G41MXE_FAST_SETUP=TRUE -D G41MXE_SETUP_TRACE=FALSE \
      -D ASUS_SETUP_BINARY="$project_root/build/asus-ui/Setup-g41-v6-csm.efi" \
      -D ASUS_AMITSE_BINARY="$project_root/build/asus-ui/AMITSE-g41-v6-csm.efi" \
      --pcd gEfiMdePkgTokenSpaceGuid.PcdDebugPropertyMask=0x02 \
      -D VARIABLE_SUPPORT=SMMSTORE -D DISABLE_SERIAL_TERMINAL=TRUE \
      -D SERIAL_DRIVER_ENABLE=FALSE -D USE_CBMEM_FOR_CONSOLE=TRUE \
      --pcd gEfiMdeModulePkgTokenSpaceGuid.PcdMaxVariableSize=0x8000 \
      -D G41_NATIVE_CSM=TRUE -D G41_CSM_TEST=FALSE \
      -D CSM16_BINARY="$csm_output/Csm16.bin" -D BUILD_ARCH=X64
  )
  payload="$project_root/build/edk-workspace/Build/UefiPayloadPkgX64/RELEASE_GCC/FV/UEFIPAYLOAD.fd"
fi
candidate="$project_root/build/artifacts/g41mxe-rebuilt-16m.rom"
cp releases/g41mxe-rtm1/support/coreboot-v5-base.rom "$candidate"
cbfstool="$project_root/build/coreboot/util/cbfstool/cbfstool"
"$cbfstool" "$candidate" remove -n fallback/payload
"$cbfstool" "$candidate" add-payload -n fallback/payload -f "$payload" -c lzma
sha256sum "$candidate"
