/** @file Native G41/ICH7 PIRQ table and PCI bridge swizzling.
  SPDX-License-Identifier: BSD-2-Clause
**/
#include "LegacyPlatform.h"

#define ROUTE_COUNT 32
#define PCI_IRQ_MASK 0x0E20 // IRQ5,9,10,11; exclude ISA/IDE IRQs.

#pragma pack(1)
STATIC struct {
  EFI_LEGACY_PIRQ_TABLE_HEADER Header;
  EFI_LEGACY_IRQ_ROUTING_ENTRY Entry[ROUTE_COUNT];
} mPirq;
#pragma pack()

STATIC BOOLEAN mRoutingReady;
STATIC BOOLEAN mG41;
STATIC UINT8 mParentBus[256];
STATIC UINT8 mParentDev[256];
STATIC BOOLEAN mParentValid[256];
STATIC EFI_LEGACY_IRQ_PRIORITY_TABLE_ENTRY mIrqPriority[] = {
  {11, 0}, {10, 0}, {9, 0}, {5, 0}
};
STATIC CONST UINT8 mPirqReg[] = {0x60, 0x61, 0x62, 0x63, 0x68, 0x69, 0x6A, 0x6B};

STATIC
EFI_STATUS
BuildRouting (VOID)
{
  EFI_STATUS Status;
  EFI_HANDLE *Handles;
  UINTN Count;
  UINTN Index;
  UINTN Segment;
  UINTN Bus;
  UINTN Device;
  UINTN Function;
  EFI_PCI_IO_PROTOCOL *PciIo;
  UINT8 Class[3];
  UINT8 Secondary;
  UINT32 Rcba;
  UINT16 Route;
  UINTN Pin;
  UINTN Link;

  if (mRoutingReady) {
    return EFI_SUCCESS;
  }
  ZeroMem (&mPirq, sizeof (mPirq));
  mG41 = PciRead16 (PCI_LIB_ADDRESS (0, 0, 0, 2)) == 0x2E30;
  Rcba = PciRead32 (PCI_LIB_ADDRESS (0, 31, 0, 0xF0));
  if ((Rcba & 1) == 0) {
    return EFI_DEVICE_ERROR;
  }
  Rcba &= 0xFFFFC000;
  mPirq.Header.Signature = EFI_LEGACY_PIRQ_TABLE_SIGNATURE;
  mPirq.Header.MajorVersion = 1;
  mPirq.Header.TableSize = sizeof (mPirq);
  mPirq.Header.Bus = 0;
  mPirq.Header.DevFun = 31 << 3;
  mPirq.Header.CompatibleVid = 0x8086;
  mPirq.Header.CompatibleDid = PciRead16 (PCI_LIB_ADDRESS (0, 31, 0, 2));
  for (Device = 0; Device < ROUTE_COUNT; Device++) {
    mPirq.Entry[Device].Device = (UINT8)(Device << 3);
    // G41 routing matches coreboot's RCBA-based ACPI _PRT generation.
    Route = 0x3210;
    if (mG41 && Device >= 27) {
      Route = MmioRead16 (Rcba + 0x3140 + (31 - Device) * 2);
    }
    for (Pin = 0; Pin < 4; Pin++) {
      if (mG41) {
        Link = (Route >> (Pin * 4)) & 7;
      } else {
        // QEMU ich9_cc_init uses E..H for ordinary root slots. Integrated
        // slots use live RCBA routing; D30 is fixed E..H in the Q35 model.
        if (Device == 30) {
          Link = Pin + 4;
        } else if (Device >= 25) {
          UINTN Offset = Device == 25 ? 0x3150 :
                         (Device == 26 ? 0x314C : 0x3140 + (31 - Device) * 2);
          Link = (MmioRead16 (Rcba + Offset) >> (Pin * 4)) & 7;
        } else {
          Link = ((Device + Pin) & 3) + 4;
        }
      }
      mPirq.Entry[Device].PirqEntry[Pin].Pirq = mPirqReg[Link];
      mPirq.Entry[Device].PirqEntry[Pin].IrqMask = PCI_IRQ_MASK;
    }
  }
  Status = gBS->LocateHandleBuffer (ByProtocol, &gEfiPciIoProtocolGuid,
                                  NULL, &Count, &Handles);
  if (EFI_ERROR (Status)) {
    return Status;
  }
  ZeroMem (mParentValid, sizeof (mParentValid));
  for (Index = 0; Index < Count; Index++) {
    Status = gBS->HandleProtocol (Handles[Index], &gEfiPciIoProtocolGuid, (VOID **)&PciIo);
    if (EFI_ERROR (Status)) {
      continue;
    }
    Status = PciIo->GetLocation (PciIo, &Segment, &Bus, &Device, &Function);
    if (EFI_ERROR (Status) || Segment != 0 || Bus > 255) {
      continue;
    }
    Status = PciIo->Pci.Read (PciIo, EfiPciIoWidthUint8, 9, 3, Class);
    if (EFI_ERROR (Status) || Class[2] != 6 || Class[1] != 4) {
      continue;
    }
    Status = PciIo->Pci.Read (PciIo, EfiPciIoWidthUint8, 0x19, 1, &Secondary);
    if (!EFI_ERROR (Status) && Secondary != 0 && Secondary != Bus) {
      mParentBus[Secondary] = (UINT8)Bus;
      mParentDev[Secondary] = (UINT8)Device;
      mParentValid[Secondary] = TRUE;
    }
  }
  FreePool (Handles);
  mPirq.Header.Checksum = CalculateCheckSum8 ((UINT8 *)&mPirq, sizeof (mPirq));
  mRoutingReady = TRUE;
  return EFI_SUCCESS;
}

EFI_STATUS EFIAPI
G41GetRoutingTable (
  IN EFI_LEGACY_BIOS_PLATFORM_PROTOCOL *This,
  OUT VOID **RoutingTable, OUT UINTN *RoutingTableEntries,
  OUT VOID **LocalPirqTable OPTIONAL, OUT UINTN *PirqTableSize OPTIONAL,
  OUT VOID **LocalIrqPriorityTable OPTIONAL,
  OUT UINTN *IrqPriorityTableEntries OPTIONAL
  )
{
  EFI_STATUS Status;
  if (RoutingTable == NULL || RoutingTableEntries == NULL ||
      (LocalPirqTable != NULL && PirqTableSize == NULL) ||
      (LocalIrqPriorityTable != NULL && IrqPriorityTableEntries == NULL)) {
    return EFI_INVALID_PARAMETER;
  }
  Status = BuildRouting ();
  if (EFI_ERROR (Status)) {
    return Status;
  }
  *RoutingTable = mPirq.Entry;
  *RoutingTableEntries = ROUTE_COUNT;
  if (LocalPirqTable != NULL) {
    *LocalPirqTable = &mPirq;
    *PirqTableSize = sizeof (mPirq);
  }
  if (LocalIrqPriorityTable != NULL) {
    *LocalIrqPriorityTable = mIrqPriority;
    *IrqPriorityTableEntries = ARRAY_SIZE (mIrqPriority);
  }
  return EFI_SUCCESS;
}

EFI_STATUS EFIAPI
G41TranslatePirq (
  IN EFI_LEGACY_BIOS_PLATFORM_PROTOCOL *This,
  IN UINTN Bus, IN UINTN Device, IN UINTN Function,
  IN OUT UINT8 *Pirq, OUT UINT8 *PciIrq
  )
{
  EFI_STATUS Status;
  UINTN Depth;
  UINTN Link;
  UINT8 Pin;
  UINT8 Reg;
  UINT8 Irq;

  if (Pirq == NULL || PciIrq == NULL || *Pirq > 3 ||
      Bus > 255 || Device > 0xF8 || (Device & 7) != 0 || Function > 7) {
    return EFI_INVALID_PARAMETER;
  }
  // Framework LegacyBiosDxe passes the device number in PCI devfn encoding.
  Device >>= 3;
  Status = BuildRouting ();
  if (EFI_ERROR (Status)) {
    return Status;
  }
  Pin = *Pirq;
  for (Depth = 0; Bus != 0 && Depth < 256; Depth++) {
    if (!mParentValid[Bus]) {
      return EFI_NOT_FOUND;
    }
    Pin = (UINT8)((Pin + Device) & 3);
    Device = mParentDev[Bus];
    Bus = mParentBus[Bus];
  }
  if (Bus != 0) {
    return EFI_DEVICE_ERROR;
  }
  Reg = mPirq.Entry[Device].PirqEntry[Pin].Pirq;
  for (Link = 0; Link < ARRAY_SIZE (mPirqReg); Link++) {
    if (mPirqReg[Link] == Reg) {
      break;
    }
  }
  if (Link == ARRAY_SIZE (mPirqReg)) {
    return EFI_NOT_FOUND;
  }
  Irq = PciRead8 (PCI_LIB_ADDRESS (0, 31, 0, Reg));
  // Preserve the board route if active. Select a safe PCI IRQ only if disabled.
  if ((Irq & 0x80) != 0 || (Irq & 0xF) == 0) {
    Irq = 11;
    PciWrite8 (PCI_LIB_ADDRESS (0, 31, 0, Reg), Irq);
  }
  Irq &= 0xF;
  if (((1U << Irq) & 0xDEF8) == 0) {
    return EFI_DEVICE_ERROR;
  }
  IoOr8 (0x4D0 + Irq / 8, (UINT8)(1U << (Irq & 7)));
  *Pirq = (UINT8)Link;
  *PciIrq = Irq;
  return EFI_SUCCESS;
}
