/** @file Q35-only native CSM regression entry. Never include in a hardware ROM.
  SPDX-License-Identifier: BSD-2-Clause
**/
#include <PiDxe.h>
#include <Protocol/LegacyBios.h>
#include <Protocol/MpService.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiBootManagerLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/DevicePathLib.h>
#include <Library/DebugLib.h>

EFI_STATUS EFIAPI
CsmTestEntry (IN EFI_HANDLE ImageHandle, IN EFI_SYSTEM_TABLE *SystemTable)
{
  EFI_STATUS Status;
  EFI_LEGACY_BIOS_PROTOCOL *Legacy;
  EFI_MP_SERVICES_PROTOCOL *Mp;
  UINTN Total;
  UINTN Enabled;
  EFI_IA32_REGISTER_SET Reg;
  EFI_BOOT_MANAGER_LOAD_OPTION *Options;
  UINTN Count;
  UINTN Index;

  Status = gBS->LocateProtocol (&gEfiLegacyBiosProtocolGuid, NULL, (VOID **)&Legacy);
  DEBUG ((DEBUG_INFO, "CSMTEST: LegacyBios protocol %r\n", Status));
  if (EFI_ERROR (Status)) {
    return Status;
  }
  Status = gBS->LocateProtocol (&gEfiMpServiceProtocolGuid, NULL, (VOID **)&Mp);
  if (EFI_ERROR (Status)) {
    return Status;
  }
  Status = Mp->GetNumberOfProcessors (Mp, &Total, &Enabled);
  DEBUG ((DEBUG_INFO, "CSMTEST: CPU total=%u enabled=%u %r\n", Total, Enabled, Status));
  if (EFI_ERROR (Status) || Total != 4 || Enabled != 4) {
    return EFI_DEVICE_ERROR;
  }
  ZeroMem (&Reg, sizeof (Reg));
  if (Legacy->Int86 (Legacy, 0x12, &Reg)) {
    return EFI_DEVICE_ERROR;
  }
  DEBUG ((DEBUG_INFO, "CSMTEST: INT12 conventional memory=%u KiB\n", Reg.X.AX));
  EfiBootManagerConnectAll ();
  EfiBootManagerRefreshAllBootOption ();
  Options = EfiBootManagerGetLoadOptions (&Count, LoadOptionTypeBoot);
  for (Index = 0; Index < Count; Index++) {
    if (DevicePathType (Options[Index].FilePath) == BBS_DEVICE_PATH) {
      DEBUG ((DEBUG_INFO, "CSMTEST: BBS Boot%04x %s\n",
              Options[Index].OptionNumber, Options[Index].Description));
      EfiBootManagerBoot (&Options[Index]);
      Status = Options[Index].Status;
      DEBUG ((DEBUG_ERROR, "CSMTEST: legacy boot unexpectedly returned %r\n", Status));
      EfiBootManagerFreeLoadOptions (Options, Count);
      return EFI_DEVICE_ERROR;
    }
  }
  DEBUG ((DEBUG_ERROR, "CSMTEST: no BBS boot option\n"));
  EfiBootManagerFreeLoadOptions (Options, Count);
  return EFI_NOT_FOUND;
}
