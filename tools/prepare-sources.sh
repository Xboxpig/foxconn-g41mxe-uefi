#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$project_root"
mkdir -p build
exec 9>build/.prepare.lock
flock 9
source_stamp="$(find src/coreboot/patches src/edk2/patches src/edk2/compat \
  src/edk2/csm/seabios.patch src/asus-ui/edk2-overlay src/boards/foxconn-g41mxe \
  tools/prepare-sources.sh source-lock.json -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum)"
if [[ -f build/.sources-ready ]] && [[ "$(<build/.sources-ready)" == "$source_stamp" ]]; then
  exit 0
fi
mkdir -p build/coreboot build/edk2 build/seabios
# Only these disposable build trees receive patches and board overlays.
for component in coreboot edk2; do
  test ! -L "build/$component"
  rsync -a --delete "src/$component/upstream/" "build/$component/"
  apply_args=()
  # Historical EDK files use mixed CRLF/LF; patch context may use LF.
  if [[ "$component" == edk2 ]]; then apply_args+=(--ignore-space-change); fi
  # Treat each generated tree as standalone: discovering the enclosing repo
  # makes git apply filter these upstream-relative patch paths as out of scope.
  GIT_CEILING_DIRECTORIES="$project_root/build" git -C "build/$component" apply \
    "${apply_args[@]}" "$project_root/src/$component/patches/common.patch"
  GIT_CEILING_DIRECTORIES="$project_root/build" git -C "build/$component" apply \
    "${apply_args[@]}" "$project_root/src/boards/foxconn-g41mxe/patches/$component.patch"
done
rsync -a src/edk2/compat/ build/edk2/
rsync -a src/asus-ui/edk2-overlay/ build/edk2/
rsync -a src/boards/foxconn-g41mxe/edk2-overlay/ build/edk2/
rsync -a src/boards/foxconn-g41mxe/coreboot-overlay/ build/coreboot/
test ! -L build/seabios
rsync -a --delete src/edk2/csm/seabios/ build/seabios/
GIT_CEILING_DIRECTORIES="$project_root/build" git -C build/seabios apply \
  "$project_root/src/edk2/csm/seabios.patch"
printf '%s\n' "$source_stamp" >build/.sources-ready
printf 'Prepared independent coreboot, EDK II and SeaBIOS build trees.\n'
