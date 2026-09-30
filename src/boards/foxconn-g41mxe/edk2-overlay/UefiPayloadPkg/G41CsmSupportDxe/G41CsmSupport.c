/** @file G41/ICH7 and Q35 native CSM platform entry.
  SPDX-License-Identifier: BSD-2-Clause
**/
#include <Uefi.h>
#include <Library/DebugLib.h>
#include <Library/PciLib.h>
#include <Library/G41CsmPolicy.h>
#include "CsmSupportLib.h"

EFI_STATUS
EFIAPI
G41CsmSupportEntry (
  IN EFI_HANDLE ImageHandle,
  IN EFI_SYSTEM_TABLE *SystemTable
  )
{
  EFI_STATUS Status;
  UINT32 Host;
  UINT32 Lpc;
  UINT32 Enabled;
  UINT32 Policy;

  Host = PciRead32 (PCI_LIB_ADDRESS (0, 0, 0, 0));
  Lpc = PciRead32 (PCI_LIB_ADDRESS (0, 31, 0, 0));
  if (!((Host == 0x2E308086 && Lpc == 0x27B88086) ||
        (Host == 0x29C08086 && Lpc == 0x29188086))) {
    DEBUG ((DEBUG_ERROR, "CSM: unsupported host/LPC %08x/%08x\n", Host, Lpc));
    return EFI_UNSUPPORTED;
  }
  Enabled = G41CsmReadOption (L"csm_enable", 0, 1);
#ifdef G41_CSM_TEST
  Enabled = 1;
#endif
  Policy = Enabled ? 1 | (G41CsmReadOption (L"boot_device_control", 0, 2) << 8) : 0;
  Status = gRT->SetVariable (L"G41CsmActivePolicy", (EFI_GUID *)&mG41CsmNvGuid,
                            EFI_VARIABLE_BOOTSERVICE_ACCESS, sizeof (Policy), &Policy);
  if (EFI_ERROR (Status)) {
    return Status;
  }
  if (!Enabled) {
    DEBUG ((DEBUG_INFO, "CSM: disabled by saved policy; no legacy platform protocols\n"));
    return EFI_SUCCESS;
  }
  Status = LegacyRegionInit ();
  if (EFI_ERROR (Status)) {
    return Status;
  }
  Status = LegacyInterruptInstall ();
  if (EFI_ERROR (Status)) {
    return Status;
  }
  Status = LegacyBiosPlatformInstall ();
  DEBUG ((DEBUG_INFO, "CSM: G41/Q35 platform protocols installed: %r\n", Status));
  return Status;
}
