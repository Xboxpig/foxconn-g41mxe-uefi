/** @file
  QEMU-only compatibility protocol for the unmodified ASUS/AMI SMBIOS driver.

  SPDX-License-Identifier: BSD-2-Clause-Patent
**/

#include <Uefi.h>

#include <Library/DebugLib.h>
#include <Library/UefiBootServicesTableLib.h>

#define ASUS_AMI_COMPAT_METHOD_COUNT  14

EFI_STATUS G41InstallSensors (VOID);

typedef EFI_STATUS (EFIAPI *ASUS_AMI_COMPAT_METHOD)(VOID);

typedef struct {
  ASUS_AMI_COMPAT_METHOD    Method[ASUS_AMI_COMPAT_METHOD_COUNT];
} ASUS_AMI_COMPAT_PROTOCOL;

typedef struct {
  ASUS_AMI_COMPAT_METHOD    IsOcmrAvailable;
  ASUS_AMI_COMPAT_METHOD    UpdateOcmr;
  ASUS_AMI_COMPAT_METHOD    GetOcmrSelection;
  ASUS_AMI_COMPAT_METHOD    Reserved;
} ASUS_IDE_CONTROLLER_COMPAT_PROTOCOL;

STATIC EFI_GUID  mAsusAmiCompatProtocolGuid = {
  0x0903dd14, 0x2ca0, 0x458a,
  { 0xb5, 0xeb, 0x0c, 0x0c, 0xa3, 0x0d, 0x78, 0x5c }
};

STATIC EFI_GUID  mAsusIdeControllerProtocolGuid = {
  0x20e28787, 0xdf32, 0x4bda,
  { 0xb7, 0xe7, 0xcb, 0xbd, 0xa3, 0x37, 0x1e, 0xf8 }
};

STATIC EFI_GUID  mAsusAiCapabilityProtocolGuid = {
  0xa45414ba, 0x0172, 0x4283,
  { 0x9a, 0x1d, 0xa7, 0xb7, 0x71, 0x77, 0xbf, 0x29 }
};

STATIC
BOOLEAN
EFIAPI
AsusAiCapabilityUnavailable (
  VOID
  )
{
  // Donor AsusAIDxe tests MSR 0x194 bits 19:17. QEMU has no Z490 AI facility.
  return FALSE;
}

STATIC struct {
  BOOLEAN (EFIAPI *IsAvailable)(VOID);
} mAsusAiCapabilityProtocol = { AsusAiCapabilityUnavailable };

STATIC
EFI_STATUS
EFIAPI
AsusAmiCompatNoop (
  VOID
  )
{
  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
EFIAPI
AsusOcmrUnavailable (
  VOID
  )
{
  return EFI_SUCCESS;
}

STATIC ASUS_AMI_COMPAT_PROTOCOL  mAsusAmiCompatProtocol = {
  {
    AsusAmiCompatNoop,
    AsusAmiCompatNoop,
    AsusAmiCompatNoop,
    AsusAmiCompatNoop,
    AsusAmiCompatNoop,
    AsusAmiCompatNoop,
    AsusAmiCompatNoop,
    AsusAmiCompatNoop,
    AsusAmiCompatNoop,
    AsusAmiCompatNoop,
    AsusAmiCompatNoop,
    AsusAmiCompatNoop,
    AsusAmiCompatNoop,
    AsusAmiCompatNoop
  }
};

STATIC ASUS_IDE_CONTROLLER_COMPAT_PROTOCOL  mAsusIdeControllerProtocol = {
  AsusOcmrUnavailable,
  AsusAmiCompatNoop,
  AsusAmiCompatNoop,
  AsusAmiCompatNoop
};

EFI_STATUS
EFIAPI
AsusAmiCompatEntryPoint (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_HANDLE  AmiCompatHandle;
  EFI_HANDLE  IdeControllerHandle;
  EFI_HANDLE  AiCapabilityHandle;
  EFI_STATUS  AmiCompatStatus;
  EFI_STATUS  IdeControllerStatus;

  (VOID)ImageHandle;
  (VOID)SystemTable;
  AmiCompatHandle = NULL;
  AmiCompatStatus = gBS->InstallProtocolInterface (
                           &AmiCompatHandle,
                           &mAsusAmiCompatProtocolGuid,
                           EFI_NATIVE_INTERFACE,
                           &mAsusAmiCompatProtocol
                           );
  DEBUG ((DEBUG_INFO, "ASUS page lab: AMI compatibility protocol: %r\n", AmiCompatStatus));
  if (EFI_ERROR (AmiCompatStatus)) {
    return AmiCompatStatus;
  }

  IdeControllerHandle = NULL;
  IdeControllerStatus = gBS->InstallProtocolInterface (
                               &IdeControllerHandle,
                               &mAsusIdeControllerProtocolGuid,
                               EFI_NATIVE_INTERFACE,
                               &mAsusIdeControllerProtocol
                               );
  DEBUG ((DEBUG_INFO, "ASUS page lab: OCMR compatibility protocol: %r\n", IdeControllerStatus));
  if (EFI_ERROR (IdeControllerStatus)) {
    return IdeControllerStatus;
  }

  AiCapabilityHandle = NULL;
  AmiCompatStatus = gBS->InstallProtocolInterface (
                           &AiCapabilityHandle,
                           &mAsusAiCapabilityProtocolGuid,
                           EFI_NATIVE_INTERFACE,
                           &mAsusAiCapabilityProtocol
                           );
  DEBUG ((DEBUG_INFO, "ASUS page lab: AI capability protocol: %r\n", AmiCompatStatus));
  if (!EFI_ERROR (AmiCompatStatus)) {
    AmiCompatStatus = G41InstallSensors ();
    DEBUG ((DEBUG_INFO, "ASUS page lab: G41 HWM adapter: %r\n", AmiCompatStatus));
  }
  return AmiCompatStatus;
}
