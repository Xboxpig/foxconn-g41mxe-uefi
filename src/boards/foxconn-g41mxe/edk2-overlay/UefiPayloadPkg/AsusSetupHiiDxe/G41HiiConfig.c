/** @file
  ConfigAccess for the reviewed G41 settings, never donor hardware callbacks.
  SPDX-License-Identifier: BSD-2-Clause-Patent
**/
#include <Uefi.h>
#include <Guid/GlobalVariable.h>
#include <Protocol/DevicePath.h>
#include <Protocol/HiiConfigAccess.h>
#include <Protocol/HiiConfigRouting.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/DebugLib.h>
#include <Library/HiiLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/PrintLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiRuntimeServicesTableLib.h>

typedef struct {
  CHAR16 *Name;
  EFI_GUID Guid;
  UINTN Size;
} G41_STORE;

typedef struct {
  CHAR16 *Name;
  UINT8 Default;
  UINT16 AllowedMask;
} G41_NATIVE_OPTION;
#include "G41NativeOptions.h"

STATIC EFI_GUID mCorebootNvGuid =
  {0xceae4c1d,0x335b,0x4685,{0xa4,0xa0,0xfc,0x4a,0x94,0xee,0xa0,0x85}};

STATIC G41_STORE mStores[] = {
  {L"SaSetup", {0x72c5e28c,0x7783,0x43a1,{0x87,0x67,0xfa,0xd7,0x3f,0xcc,0xaf,0xa4}}, 1282},
  {L"AsusQFanSetupData", {0xec87d643,0xeba4,0x4bb5,{0xa1,0xe5,0x3f,0x3e,0x36,0xb2,0x0d,0xa9}}, 144},
  {L"Timeout", EFI_GLOBAL_VARIABLE, 2},
  {L"BootOrder", EFI_GLOBAL_VARIABLE, 1282},
  {L"G41PlatformData", G41_PLATFORM_GUID, G41_PLATFORM_BUFFER_SIZE},
};
STATIC EFI_HII_CONFIG_ROUTING_PROTOCOL *mRouting;
STATIC EFI_HANDLE mDriver;
STATIC struct {
  VENDOR_DEVICE_PATH Vendor;
  EFI_DEVICE_PATH_PROTOCOL End;
} mPath = {
  {{HARDWARE_DEVICE_PATH, HW_VENDOR_DP, {sizeof (VENDOR_DEVICE_PATH), 0}},
   {0x899407d7,0x99fe,0x43d8,{0x9a,0x21,0x79,0xec,0x32,0x8c,0xac,0x21}}},
  {END_DEVICE_PATH_TYPE, END_ENTIRE_DEVICE_PATH_SUBTYPE, {sizeof (EFI_DEVICE_PATH_PROTOCOL), 0}}
};

STATIC G41_STORE *FindStore (EFI_STRING Config)
{
  UINTN Index;
  for (Index = 0; Index < ARRAY_SIZE (mStores); Index++) {
    if (HiiIsConfigHdrMatch (Config, &mStores[Index].Guid, mStores[Index].Name)) {
      return &mStores[Index];
    }
  }
  return NULL;
}

STATIC EFI_STATUS ReadStore (G41_STORE *Store, UINT8 *Buffer)
{
  EFI_STATUS Status;
  UINTN Index, NativeSize;
  UINT32 Value;
  UINTN Size = (Store == &mStores[3]) ? 1282 : Store->Size;
  ZeroMem (Buffer, Size);
  if (Store == &mStores[4]) {
    // The UI buffer is not an NVRAM variable. coreboot consumes one UINT32
    // per option under its own GUID; never write the donor CPU/PCH stores.
    for (Index = 0; Index < ARRAY_SIZE (mNativeOptions); Index++) {
      NativeSize = sizeof (Value);
      Status = gRT->GetVariable (mNativeOptions[Index].Name, &mCorebootNvGuid,
                                NULL, &NativeSize, &Value);
      Buffer[Index] = mNativeOptions[Index].Default;
      if (!EFI_ERROR (Status) && NativeSize == sizeof (Value) && Value < 16 &&
          (mNativeOptions[Index].AllowedMask & (1U << Value)) != 0) {
        Buffer[Index] = (UINT8)Value;
      } else if (Status != EFI_NOT_FOUND) {
        DEBUG ((DEBUG_WARN, "G41 ConfigAccess: invalid %s; using safe default\n",
                mNativeOptions[Index].Name));
      }
    }
    return EFI_SUCCESS;
  }
  Status = gRT->GetVariable (Store->Name, &Store->Guid, NULL, &Size, Buffer);
  if (Store == &mStores[3]) {
    if (!EFI_ERROR (Status) && (Size != 0) && (Size % 2 == 0)) {
      Store->Size = Size;
      return EFI_SUCCESS;
    }
    return EFI_ERROR (Status) ? Status : EFI_COMPROMISED_DATA;
  }
  if (Status == EFI_NOT_FOUND) {
    if (Store == &mStores[1]) {
      Buffer[0] = Buffer[0x18] = 3;  // PWM; never default to fan stop.
    } else if (Store == &mStores[2]) {
      Buffer[0] = 5;
    }
    return EFI_SUCCESS;
  }
  return (!EFI_ERROR (Status) && Size != Store->Size) ? EFI_COMPROMISED_DATA : Status;
}

STATIC EFI_STATUS EFIAPI Extract (
  CONST EFI_HII_CONFIG_ACCESS_PROTOCOL *This, CONST EFI_STRING Request,
  EFI_STRING *Progress, EFI_STRING *Results)
{
  G41_STORE *Store;
  UINT8 Buffer[1282];
  EFI_STRING FullRequest;
  EFI_STATUS Status;
  UINTN Size;
  if (Progress == NULL || Results == NULL) {
    return EFI_INVALID_PARAMETER;
  }
  *Progress = Request;
  *Results = NULL;
  if (Request == NULL || (Store = FindStore (Request)) == NULL) {
    return EFI_NOT_FOUND;
  }
  Status = ReadStore (Store, Buffer);
  if (EFI_ERROR (Status)) {
    return Status;
  }
  FullRequest = Request;
  if (StrStr (Request, L"&OFFSET=") == NULL) {
    Size = StrSize (Request) + 128 * sizeof (CHAR16);
    FullRequest = AllocateZeroPool (Size);
    if (FullRequest == NULL) {
      return EFI_OUT_OF_RESOURCES;
    }
    UnicodeSPrint (FullRequest, Size, L"%s&OFFSET=0&WIDTH=%016LX", Request, (UINT64)Store->Size);
  }
  Status = mRouting->BlockToConfig (mRouting, FullRequest, Buffer,
                                    Store->Size, Results, Progress);
  if (FullRequest != Request) {
    *Progress = Request + StrLen (Request);
    FreePool (FullRequest);
  }
  return Status;
}

STATIC EFI_STATUS EFIAPI Route (
  CONST EFI_HII_CONFIG_ACCESS_PROTOCOL *This, CONST EFI_STRING Configuration,
  EFI_STRING *Progress)
{
  G41_STORE *Store;
  UINT8 Current[1282], Proposed[1282];
  UINTN Size, Index, Other;
  EFI_STATUS Status;
  UINT16 Rate;
  UINT32 NativeValue;
  UINT32 NativeAttributes[G41_PLATFORM_BUFFER_SIZE];
  BOOLEAN NativeChanged[G41_PLATFORM_BUFFER_SIZE];
  STATIC CONST UINT8 FanOffsets[] = {0, 8, 0x18, 0x20};
  if (Configuration == NULL || Progress == NULL) {
    return EFI_INVALID_PARAMETER;
  }
  *Progress = Configuration;
  Store = FindStore (Configuration);
  if (Store == NULL) {
    return EFI_NOT_FOUND;
  }
  Status = ReadStore (Store, Current);
  if (EFI_ERROR (Status)) {
    return Status;
  }
  CopyMem (Proposed, Current, Store->Size);
  Size = Store->Size;
  Status = mRouting->ConfigToBlock (mRouting, Configuration, Proposed, &Size, Progress);
  if (EFI_ERROR (Status)) {
    return Status;
  }
  if (Store == &mStores[4]) {
    // Validate the entire response before applying any of its fields.
    for (Index = 0; Index < ARRAY_SIZE (mNativeOptions); Index++) {
      if (Proposed[Index] >= 16 ||
          (mNativeOptions[Index].AllowedMask & (1U << Proposed[Index])) == 0) {
        return EFI_INVALID_PARAMETER;
      }
    }
    for (Index = ARRAY_SIZE (mNativeOptions); Index < Store->Size; Index++) {
      if (Proposed[Index] != 0) {
        return EFI_INVALID_PARAMETER;
      }
    }
    // CFR creates NV|BS variables; old tools may also set RT. UEFI forbids
    // changing an existing variable's attributes without deleting it first.
    // Preserve either supported form, and preflight all changes before writes.
    for (Index = 0; Index < ARRAY_SIZE (mNativeOptions); Index++) {
      NativeAttributes[Index] = EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_BOOTSERVICE_ACCESS;
      NativeValue = MAX_UINT32;
      Size = sizeof (NativeValue);
      Status = gRT->GetVariable (mNativeOptions[Index].Name, &mCorebootNvGuid,
                                &NativeAttributes[Index], &Size, &NativeValue);
      if (Status == EFI_NOT_FOUND) {
        NativeChanged[Index] = Proposed[Index] != Current[Index];
      } else if (Status == EFI_BUFFER_TOO_SMALL || !EFI_ERROR (Status)) {
        NativeChanged[Index] = Size != sizeof (NativeValue) || NativeValue != Proposed[Index];
      } else {
        return Status;
      }
      if ((NativeAttributes[Index] & ~EFI_VARIABLE_RUNTIME_ACCESS) !=
          (EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_BOOTSERVICE_ACCESS)) {
        return EFI_WRITE_PROTECTED;
      }
    }
    for (Index = 0; Index < ARRAY_SIZE (mNativeOptions); Index++) {
      if (!NativeChanged[Index]) {
        continue;
      }
      NativeValue = Proposed[Index];
      Status = gRT->SetVariable (mNativeOptions[Index].Name, &mCorebootNvGuid,
                                NativeAttributes[Index], sizeof (NativeValue), &NativeValue);
      DEBUG ((DEBUG_INFO, "G41 ConfigAccess: saved %s=%u: %r\n",
              mNativeOptions[Index].Name, NativeValue, Status));
      if (EFI_ERROR (Status)) {
        return Status;
      }
    }
    return EFI_SUCCESS;
  } else if (Store == &mStores[0]) {
    CopyMem (&Rate, Proposed + 0x18e, 2);
    if (Rate != 0 && Rate != 1067 && Rate != 1333) {
      return EFI_INVALID_PARAMETER;
    }
    CopyMem (Current + 0x18e, Proposed + 0x18e, 2);
  } else if (Store == &mStores[1]) {
    if ((Proposed[0] != 0 && Proposed[0] != 1 && Proposed[0] != 3) ||
        (Proposed[0x18] != 0 && Proposed[0x18] != 1 && Proposed[0x18] != 3) ||
        Proposed[8] > 2 || Proposed[0x20] > 2) {
      return EFI_INVALID_PARAMETER;
    }
    for (Index = 0; Index < ARRAY_SIZE (FanOffsets); Index++) {
      Current[FanOffsets[Index]] = Proposed[FanOffsets[Index]];
    }
  } else if (Store == &mStores[3]) {
    // The donor's single-entry BootOrder control edits the first UINT16.
    // Move that existing entry to the front; never duplicate or drop others.
    if (Store->Size > 2 && CompareMem (Current + 2, Proposed + 2, Store->Size - 2) == 0) {
      for (Index = 0; Index < Store->Size; Index += 2) {
        if (CompareMem (Current + Index, Proposed, 2) == 0) {
          CopyMem (Current + Index, Current, 2);
          CopyMem (Current, Proposed, 2);
          break;
        }
      }
      if (Index == Store->Size) {
        return EFI_INVALID_PARAMETER;
      }
    } else {
      // A full drag/reorder response must be a permutation of saved entries.
      for (Index = 0; Index < Store->Size; Index += 2) {
        for (Other = 0; Other < Store->Size; Other += 2) {
          if (CompareMem (Current + Index, Proposed + Other, 2) == 0) {
            break;
          }
        }
        if (Other == Store->Size) {
          return EFI_INVALID_PARAMETER;
        }
      }
      CopyMem (Current, Proposed, Store->Size);
    }
  } else {
    CopyMem (Current, Proposed, Store->Size);
  }
  Status = gRT->SetVariable (Store->Name, &Store->Guid,
                            EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_BOOTSERVICE_ACCESS |
                            EFI_VARIABLE_RUNTIME_ACCESS, Store->Size, Current);
  DEBUG ((DEBUG_INFO, "G41 ConfigAccess: saved %s size=%u: %r\n", Store->Name,
          (UINT32)Store->Size, Status));
  return Status;
}

STATIC EFI_STATUS EFIAPI Callback (
  CONST EFI_HII_CONFIG_ACCESS_PROTOCOL *This, EFI_BROWSER_ACTION Action,
  EFI_QUESTION_ID QuestionId, UINT8 Type, EFI_IFR_TYPE_VALUE *Value,
  EFI_BROWSER_ACTION_REQUEST *ActionRequest)
{
  // Hardware configuration is applied by coreboot on the next boot.
  return EFI_UNSUPPORTED;
}
STATIC EFI_HII_CONFIG_ACCESS_PROTOCOL mAccess = {Extract, Route, Callback};

EFI_STATUS G41InstallHiiConfig (EFI_HANDLE *Driver)
{
  EFI_STATUS Status;
  Status = gBS->LocateProtocol (&gEfiHiiConfigRoutingProtocolGuid, NULL, (VOID **)&mRouting);
  if (EFI_ERROR (Status)) {
    return Status;
  }
  Status = gBS->InstallMultipleProtocolInterfaces (&mDriver,
    &gEfiDevicePathProtocolGuid, &mPath,
    &gEfiHiiConfigAccessProtocolGuid, &mAccess, NULL);
  *Driver = mDriver;
  return Status;
}
