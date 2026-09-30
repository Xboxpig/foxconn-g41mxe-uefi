#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$project_root"
bash tools/prepare-sources.sh
export PYTHONPATH="$project_root/src/asus-ui/tools:$project_root/src/boards/foxconn-g41mxe/asus-ui"
export PYTHONDONTWRITEBYTECODE=1
python tests/unit/test_harness_fixtures.py
python tests/unit/test_g41_platform_ui_v5.py
python tests/unit/test_g41_csm_ui.py
python tests/unit/test_it8720_modes.py
mkdir -p build/tests
cc -Wall -Wextra -Werror -fsanitize=address,undefined tests/unit/test_g41_sensors.c -o build/tests/sensors
build/tests/sensors
cc -Wall -Wextra -Werror tests/unit/test_g41_policy.c -o build/tests/policy
build/tests/policy
edk_flags=(-I build/edk2/MdePkg/Include -I build/edk2/MdePkg/Include/X64
           -I build/edk2/MdeModulePkg/Include -fshort-wchar -Wno-unused-parameter -DG41_NATIVE_CSM)
cc "${edk_flags[@]}" tests/unit/test_csm_policy.c -o build/tests/csm-policy
build/tests/csm-policy
cc "${edk_flags[@]}" -ffunction-sections -fdata-sections -Wl,--gc-sections \
  tests/unit/test_g41_native_config.c -o build/tests/config-access
build/tests/config-access
python tools/verify-rtm.py
