/** @file
  Experimental G41MXE sensor provider for the ASUS HWM interface.
  No voltage, PWM, clock or memory-controller registers are written.
  SPDX-License-Identifier: BSD-2-Clause-Patent
**/
#ifndef G41_SENSORS_HOST_TEST
#include <Uefi.h>
#include <Library/BaseLib.h>
#include <Library/DebugLib.h>
#include <Library/IoLib.h>
#include <Library/PciLib.h>
#include <Library/TimerLib.h>
#include <Library/UefiBootServicesTableLib.h>
#endif

STATIC UINT16 mEcBase;
STATIC UINT64 mTempStart;
STATIC UINT64 mCounterMask;
STATIC UINT8 mTempReady;
STATIC EFI_GUID mHwmGuid = {
  0x78039142, 0x4378, 0x48ef, {0xbb, 0x5d, 0xf6, 0x3b, 0xf2, 0xc5, 0xde, 0xb5}
};

STATIC UINT8
ReadConfig (UINT8 Index)
{
  IoWrite8 (0x2e, Index);
  return IoRead8 (0x2f);
}

STATIC UINT8
ReadEc (UINT8 Index)
{
  IoWrite8 (mEcBase + 5, Index);
  return IoRead8 (mEcBase + 6);
}

STATIC VOID
ProbeEc (VOID)
{
  UINT16 Chip;
  UINT8 OldLdn;
  UINT8 Active;
  UINT16 Base;
  UINT64 CounterStart;

  mEcBase = 0;
  mTempReady = 0;
  mCounterMask = 0;
  // Never probe a Super I/O on an unrelated chipset, including Q35.
  if ((PciRead32 (PCI_LIB_ADDRESS (0, 0, 0, 0)) != 0x2e308086) ||
      (PciRead32 (PCI_LIB_ADDRESS (0, 31, 0, 0)) != 0x27b88086)) {
    DEBUG ((DEBUG_INFO, "G41 HWM: chipset absent; readings unavailable\n"));
    return;
  }
  IoWrite8 (0x2e, 0x87);
  IoWrite8 (0x2e, 0x01);
  IoWrite8 (0x2e, 0x55);
  IoWrite8 (0x2e, 0x55);
  Chip = (UINT16)((ReadConfig (0x20) << 8) | ReadConfig (0x21));
  OldLdn = ReadConfig (7);
  Base = 0;
  Active = 0;
  if (Chip == 0x8720) {
    IoWrite8 (0x2e, 7);
    IoWrite8 (0x2f, 4);
    Active = ReadConfig (0x30);
    Base = (UINT16)((ReadConfig (0x60) << 8) | ReadConfig (0x61));
    IoWrite8 (0x2e, 7);
    IoWrite8 (0x2f, OldLdn);
  }
  IoWrite8 (0x2e, 2);
  IoWrite8 (0x2f, 2);
  // Match this board's coreboot resource assignment; do not guess an address.
  if ((Chip == 0x8720) && ((Active & 1) != 0) && (Base == 0xa10)) {
    mEcBase = Base;
    if ((ReadEc (0x58) != 0x90) || ((ReadEc (0) & 1) == 0)) {
      mEcBase = 0;
    }
  }
  if (mEcBase != 0) {
    GetPerformanceCounterProperties (&CounterStart, &mCounterMask);
    // This payload uses an up-counting, power-of-two ACPI/TSC counter.
    if ((CounterStart != 0) || (mCounterMask == 0) ||
        ((mCounterMask & (mCounterMask + 1)) != 0)) {
      mCounterMask = 0;
    }
    mTempStart = GetPerformanceCounter ();
  }
  DEBUG ((DEBUG_INFO, "G41 HWM: SIO=%04x EC=%04x (read-only)\n", Chip, mEcBase));
}

STATIC UINT32
ReadFan (UINT8 Fan, UINT32 Unavailable)
{
  UINT8 High1;
  UINT8 High2;
  UINT8 Low;
  UINTN Retry;
  UINT16 Count;

  if ((ReadEc (0x0c) & (1U << Fan)) == 0) {
    return Unavailable; // 8-bit/divisor mode is not validated by this adapter.
  }
  for (Retry = 0; Retry < 3; Retry++) {
    High1 = ReadEc ((UINT8)(0x18 + Fan));
    Low = ReadEc ((UINT8)(0x0d + Fan));
    High2 = ReadEc ((UINT8)(0x18 + Fan));
    if (High1 == High2) {
      Count = (UINT16)((High1 << 8) | Low);
      if (Count == 0) {
        return Unavailable;
      }
      // Saturation means no tach pulses; it cannot distinguish a stopped fan
      // from an unplugged one. Keep 0 RPM for this real fault indication.
      return (Count == 0xffff) ? 0 : 1350000U / (Count * 2U);
    }
  }
  return Unavailable;
}

STATIC UINT32 EFIAPI
ReadCoreClock (UINT16 Id, UINT32 Unavailable)
{
  STATIC CONST UINT16 FsbTimesThree[8] = {800, 400, 600, 500, 1000, 300, 1200, 0};
  UINT32 Signature;
  UINT32 VendorB;
  UINT32 VendorC;
  UINT32 VendorD;
  UINT32 Fsb;
  UINT32 Ratio;
  UINT64 Status;

  AsmCpuid (0, &Signature, &VendorB, &VendorC, &VendorD);
  if ((VendorB != 0x756e6547) || (VendorD != 0x49656e69) || (VendorC != 0x6c65746e)) {
    return Unavailable;
  }
  AsmCpuid (1, &Signature, NULL, NULL, NULL);
  if (Signature != 0x10676) {
    return Unavailable; // Only the verified X5450 stepping is enabled.
  }
  Fsb = FsbTimesThree[AsmReadMsr64 (0xcd) & 7];
  Status = AsmReadMsr64 (0x198);
  Ratio = (UINT32)(Status >> 8) & 0x1f;
  if ((Fsb == 0) || (Ratio == 0) || ((Status & 0xc000) != 0)) {
    return Unavailable; // Half ratios and dynamic FSB need separate validation.
  }
  switch (Id) {
    case 0x7000: return (Fsb * Ratio + 1) / 3; // Nominal CPU MHz at current ratio.
    // Donor format uses value/10000 and value%10000 with "%d.%02d MHz".
    // Pack integer MHz and hundredths, not a linear frequency unit.
    case 0x7001: return (Fsb / 3) * 10000 + ((Fsb % 3) * 100) / 3;
    case 0x7002: return Ratio;
    default: return Unavailable;
  }
}

STATIC UINT32 EFIAPI
ReadMemoryInfo (UINT16 Id, UINT32 Unavailable)
{
  STATIC CONST UINT16 Rates[6] = {400, 533, 667, 800, 1067, 1333};
  UINTN Base;
  UINT8 Code;
  UINT32 Capacity;
  UINT16 Channel0;
  UINT16 Channel1;

  // Only the enabled BAR independently verified on this board is supported.
  if ((PciRead32 (PCI_LIB_ADDRESS (0, 0, 0, 0x48)) != 0xfed14001) ||
      (PciRead32 (PCI_LIB_ADDRESS (0, 0, 0, 0x4c)) != 0)) {
    return Unavailable;
  }
  Base = 0xfed14000;
  if (Id == 0x7003) {
    Code = (MmioRead8 (Base + 0xc00) >> 4) & 7;
    return (Code < 6) ? Rates[Code] : Unavailable;
  }
  if (Id == 0x7005) {
    return (MmioRead8 (Base + 0x1a8) & 4) ? 3 : 2;
  }
  // In stacked mode CH1 boundaries are doubled. Leave this unvalidated
  // mode unavailable rather than publishing a misleading installed capacity.
  if (MmioRead8 (Base + 0x111) & 2) {
    return Unavailable;
  }
  Channel0 = MmioRead16 (Base + 0x206);
  Channel1 = MmioRead16 (Base + 0x606);
  Capacity = ((UINT32)Channel0 + Channel1) * 64;
  return ((Capacity != 0) && (Capacity <= 8192)) ? Capacity : Unavailable;
}

STATIC UINT32 EFIAPI
ReadAsusSensor (UINT16 Id)
{
  UINT32 Value;
  EFI_TPL OldTpl;
  UINT8 Temperature;
  UINT8 VoltageRegister;
  UINT8 Raw;
  UINT32 Numerator;
  UINT32 Denominator;

  // The reviewed Setup adapter sets bit 15 to request its native N/A value.
  // Legacy AMITSE consumers still require separate graph/format adaptations.
  Value = (Id & 0x8000) ? 0x7fff : 0;
  Id &= 0x7fff;
  if (mEcBase == 0) {
    return Value;
  }
  OldTpl = gBS->RaiseTPL (TPL_HIGH_LEVEL);
  VoltageRegister = 0;
  Numerator = 1;
  Denominator = 1;
  switch (Id) {
    // Private display-only IDs; these are not donor HII string tokens.
    case 0x7000:
    case 0x7001:
    case 0x7002:
      Value = ReadCoreClock (Id, Value);
      break;
    case 0x7003:
    case 0x7004:
    case 0x7005:
      Value = ReadMemoryInfo (Id, Value);
      break;
    // TMPIN1 is the board's configured CPU fan-control source, not CPU DTS.
    case 0x1fb3:
      if ((ReadEc (0x51) & 0x09) == 0) {
        break; // Disabled channels can retain plausible stale readings.
      }
      Temperature = ReadEc (0x29);
      if (Temperature < 127) {
        Value = Temperature;
      }
      break;
    // P10 System Temperature: live A/B/A test confirmed TMPIN2 diode mode.
    // EC2A can retain 96 C for a conversion after changing EC51. Do not
    // block the UI; wait at least three seconds before publishing this source.
    case 0x1fb9:
      if (((ReadEc (0x51) & 0xd2) != 0x02) || ((ReadEc (0x55) & 0x80) != 0)) {
        mTempReady = 0;
        mTempStart = GetPerformanceCounter ();
        break;
      }
      if (!mTempReady && (mCounterMask != 0) &&
          (GetTimeInNanoSecond ((GetPerformanceCounter () - mTempStart) &
                               mCounterMask) >= 3000000000ULL)) {
        mTempReady = 1;
      }
      if (mTempReady) {
        Temperature = ReadEc (0x2a);
        if (Temperature < 127) {
          Value = Temperature;
        }
      }
      break;
    case 0x1fdf: Value = ReadFan (1, Value); break; // CPU is FAN2 on this board.
    case 0x1fee: Value = ReadFan (0, Value); break; // Chassis is FAN1.
    // P10 language tokens 0x30..0x34 link to these ADC tables and ratios.
    // The original formatter uses 16 mV steps and truncates fractional mV.
    case 0x20cb: VoltageRegister = 0x20; break;
    case 0x20d3: VoltageRegister = 0x21; break;
    case 0x20d1: VoltageRegister = 0x24; break;
    case 0x20cf: VoltageRegister = 0x23; Numerator = 168; Denominator = 100; break;
    case 0x20cd: VoltageRegister = 0x22; Numerator = 4; break;
    default: break; // No inferred rails or nonexistent headers.
  }
  if ((VoltageRegister != 0) &&
      ((ReadEc (0x50) & (1U << (VoltageRegister - 0x20))) != 0)) {
    Raw = ReadEc (VoltageRegister);
    // P10's availability callback rejects both disconnected/end-point codes.
    if ((Raw != 0) && (Raw != 0xff)) {
      Value = (UINT32)Raw * 16U * Numerator / Denominator;
    }
  }
  gBS->RestoreTPL (OldTpl);
  return Value;
}

EFI_STATUS
G41InstallSensors (VOID)
{
  STATIC struct { UINT32 (EFIAPI *Read)(UINT16 Id); } Protocol = {ReadAsusSensor};
  EFI_HANDLE Handle = NULL;
  ProbeEc ();
  return gBS->InstallProtocolInterface (&Handle, &mHwmGuid, EFI_NATIVE_INTERFACE, &Protocol);
}
