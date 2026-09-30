/** @file G41 native CSM policy, latched once per boot by the platform driver.
  SPDX-License-Identifier: BSD-2-Clause-Patent
**/
#pragma once
#include <Library/DevicePathLib.h>
#include <Library/UefiRuntimeServicesTableLib.h>

STATIC CONST EFI_GUID mG41CsmNvGuid =
  {0xceae4c1d,0x335b,0x4685,{0xa4,0xa0,0xfc,0x4a,0x94,0xee,0xa0,0x85}};

STATIC inline UINT32
G41CsmReadOption (CHAR16 *Name, UINT32 Default, UINT32 Maximum)
{
  EFI_STATUS Status;
  UINTN Size = sizeof (UINT32);
  UINT32 Value;
  Status = gRT->GetVariable (Name, (EFI_GUID *)&mG41CsmNvGuid, NULL, &Size, &Value);
  return !EFI_ERROR (Status) && Size == sizeof (Value) && Value <= Maximum ? Value : Default;
}

STATIC inline UINT32
G41CsmActivePolicy (VOID)
{
  UINT32 Policy = G41CsmReadOption (L"G41CsmActivePolicy", 0, 0x201);
  return Policy == 1 || Policy == 0x101 || Policy == 0x201 ? Policy : 0;
}

STATIC inline BOOLEAN
G41CsmIsLegacyPath (EFI_DEVICE_PATH_PROTOCOL *Path)
{
  return Path != NULL && DevicePathType (Path) == BBS_DEVICE_PATH &&
         DevicePathSubType (Path) == BBS_BBS_DP;
}

STATIC inline BOOLEAN
G41CsmBootAllowed (EFI_DEVICE_PATH_PROTOCOL *Path, UINT32 Attributes)
{
  UINT32 Policy = G41CsmActivePolicy ();
  BOOLEAN Legacy = G41CsmIsLegacyPath (Path);
  EFI_DEVICE_PATH_PROTOCOL *Node;

  if (Legacy) {
    return (Policy & 1) != 0 && (Policy >> 8) != 1;
  }
  // Setup, Shell and embedded firmware tools remain usable in every mode.
  for (Node = Path; Node != NULL && !IsDevicePathEnd (Node); Node = NextDevicePathNode (Node)) {
    if (DevicePathType (Node) == MEDIA_DEVICE_PATH &&
        DevicePathSubType (Node) == MEDIA_PIWG_FW_FILE_DP) {
      return TRUE;
    }
  }
  return (Attributes & LOAD_OPTION_CATEGORY) == LOAD_OPTION_CATEGORY_APP ||
         (Policy & 1) == 0 || (Policy >> 8) != 2;
}
