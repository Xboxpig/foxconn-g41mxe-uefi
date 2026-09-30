/** @file
  G41-only HII readings. No donor Setup callback or guessed hardware writes.
  SPDX-License-Identifier: BSD-2-Clause-Patent
**/
#include <Uefi.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/HiiLib.h>
#include <Library/PrintLib.h>
#include <Library/UefiBootServicesTableLib.h>

STATIC EFI_GUID mHwmGuid = {
  0x78039142, 0x4378, 0x48ef, {0xbb, 0x5d, 0xf6, 0x3b, 0xf2, 0xc5, 0xde, 0xb5}
};

typedef struct {
  UINT32 (EFIAPI *Read)(UINT16 Id);
} G41_HWM_PROTOCOL;

typedef struct {
  UINT16 Id;
  UINT16 Token;
  UINT8  Unit;
  UINT32 Previous;
} G41_HII_READING;

STATIC G41_HII_READING mReadings[] = {
  {0x1fb3, 0x1fb3, 0, MAX_UINT32},
  {0x1fb9, 0x1fb9, 0, MAX_UINT32},
  {0x1fdf, 0x1fdf, 1, MAX_UINT32},
  {0x1fee, 0x1fee, 1, MAX_UINT32},
  {0x20cb, 0x20cb, 2, MAX_UINT32},
  {0x20cd, 0x20cd, 2, MAX_UINT32},
  {0x20cf, 0x20cf, 2, MAX_UINT32},
  {0x20d1, 0x20d1, 2, MAX_UINT32},
  {0x20d3, 0x20d3, 2, MAX_UINT32},
  {0x7000, 0x0266, 3, MAX_UINT32},
  {0x7003, 0x054a, 4, MAX_UINT32},
  {0x7004, 0x15dd, 5, MAX_UINT32},
};

STATIC EFI_HII_HANDLE mHii;
STATIC EFI_EVENT      mEvent;
STATIC G41_HWM_PROTOCOL *mHwm;

STATIC VOID EFIAPI
UpdateReadings (EFI_EVENT Event, VOID *Context)
{
  UINTN  Index;
  UINT32 Value;
  CHAR16 Buffer[64];
  EFI_STATUS Status;

  if (mHwm == NULL) {
    Status = gBS->LocateProtocol (&mHwmGuid, NULL, (VOID **)&mHwm);
    if (EFI_ERROR (Status)) {
      return;
    }
  }
  for (Index = 0; Index < ARRAY_SIZE (mReadings); Index++) {
    Value = mHwm->Read (mReadings[Index].Id | 0x8000);
    if (Value == mReadings[Index].Previous) {
      continue;
    }
    if (Value == 0x7fff) {
      UnicodeSPrint (Buffer, sizeof (Buffer), L"N/A");
    } else {
      switch (mReadings[Index].Unit) {
        case 0: UnicodeSPrint (Buffer, sizeof (Buffer), L"%u C", Value); break;
        case 1: UnicodeSPrint (Buffer, sizeof (Buffer), L"%u RPM", Value); break;
        case 2: UnicodeSPrint (Buffer, sizeof (Buffer), L"%u.%03u V", Value / 1000, Value % 1000); break;
        case 3: UnicodeSPrint (Buffer, sizeof (Buffer), L"%u MHz (ratio based)", Value); break;
        case 4: UnicodeSPrint (Buffer, sizeof (Buffer), L"%u MT/s", Value); break;
        default: UnicodeSPrint (Buffer, sizeof (Buffer), L"%u MB", Value); break;
      }
    }
    if (HiiSetString (mHii, mReadings[Index].Token, Buffer, NULL) != 0) {
      mReadings[Index].Previous = Value;
    }
  }
}

VOID
G41BindHiiSensors (EFI_HII_HANDLE Hii)
{
  UINT32 Registers[12];
  UINT32 MaxLeaf;
  UINTN  Index;
  CHAR16 Brand[49];

  mHii = Hii;
  AsmCpuid (0x80000000, &MaxLeaf, NULL, NULL, NULL);
  if (MaxLeaf >= 0x80000004) {
    for (Index = 0; Index < 3; Index++) {
      AsmCpuid (0x80000002 + (UINT32)Index, &Registers[Index*4],
                &Registers[Index*4+1], &Registers[Index*4+2], &Registers[Index*4+3]);
    }
    for (Index = 0; Index < 48; Index++) {
      Brand[Index] = ((UINT8 *)Registers)[Index];
    }
    Brand[48] = 0;
    HiiSetString (Hii, 0x261, Brand, NULL);
  }
  UpdateReadings (NULL, NULL);
  if (!EFI_ERROR (gBS->CreateEvent (EVT_TIMER | EVT_NOTIFY_SIGNAL, TPL_CALLBACK,
                                   UpdateReadings, NULL, &mEvent))) {
    gBS->SetTimer (mEvent, TimerPeriodic, 10000000);
  }
}
