/* Host regression harness for the actual firmware ConfigAccess implementation. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#undef NULL
#include "../../src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/AsusSetupHiiDxe/G41HiiConfig.c"

static UINT32 values[16];
static UINT32 attributes[16];
static BOOLEAN present[16];
static UINT8 proposal[16];
static UINTN writes, malformed = 99;
static EFI_STATUS write_status = EFI_SUCCESS;
static EFI_RUNTIME_SERVICES runtime;
EFI_RUNTIME_SERVICES *gRT = &runtime;

VOID *EFIAPI ZeroMem (VOID *Buffer, UINTN Size) { return memset (Buffer, 0, Size); }
VOID *EFIAPI CopyMem (VOID *Dst, CONST VOID *Src, UINTN Size) { return memcpy (Dst, Src, Size); }
INTN EFIAPI CompareMem (CONST VOID *A, CONST VOID *B, UINTN Size) { return memcmp (A, B, Size); }
VOID EFIAPI DebugPrint (UINTN Level, CONST CHAR8 *Format, ...) { }
BOOLEAN EFIAPI DebugPrintLevelEnabled (CONST UINTN Level) { return TRUE; }
BOOLEAN EFIAPI DebugPrintEnabled (VOID) { return TRUE; }

static UINTN option_index (CHAR16 *Name)
{
  UINTN Index;
  for (Index = 0; Index < ARRAY_SIZE (mNativeOptions); Index++) {
    UINTN Pos = 0;
    while (Name[Pos] && Name[Pos] == mNativeOptions[Index].Name[Pos]) Pos++;
    if (!Name[Pos] && !mNativeOptions[Index].Name[Pos]) return Index;
  }
  assert (0 && "Unexpected variable name");
  return 0;
}

BOOLEAN EFIAPI HiiIsConfigHdrMatch (CONST EFI_STRING Config, CONST EFI_GUID *Guid,
                                   CONST CHAR16 *Name)
{
  UINTN Index = 0;
  while (Config[Index] && Config[Index] == Name[Index]) Index++;
  return !Config[Index] && !Name[Index] &&
         memcmp (Guid, &mStores[4].Guid, sizeof (*Guid)) == 0;
}

static EFI_STATUS EFIAPI read_var (CHAR16 *Name, EFI_GUID *Guid, UINT32 *Attr,
                                   UINTN *Size, VOID *Data)
{
  UINTN Index = option_index (Name);
  assert (!memcmp (Guid, &mCorebootNvGuid, sizeof (*Guid)));
  if (!present[Index]) return EFI_NOT_FOUND;
  assert (*Size == sizeof (UINT32));
  if (Attr) *Attr = attributes[Index];
  *Size = Index == malformed ? 3 : sizeof (UINT32);
  memcpy (Data, &values[Index], sizeof (UINT32));
  return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI write_var (CHAR16 *Name, EFI_GUID *Guid, UINT32 Attr,
                                    UINTN Size, VOID *Data)
{
  UINTN Index = option_index (Name);
  assert (!memcmp (Guid, &mCorebootNvGuid, sizeof (*Guid)));
  assert (Size == sizeof (UINT32));
  assert ((Attr & ~EFI_VARIABLE_RUNTIME_ACCESS) ==
          (EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_BOOTSERVICE_ACCESS));
  if (present[Index]) assert (Attr == attributes[Index]);
  writes++;
  if (EFI_ERROR (write_status)) return write_status;
  memcpy (&values[Index], Data, Size);
  present[Index] = TRUE;
  attributes[Index] = Attr;
  return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI config_block (CONST EFI_HII_CONFIG_ROUTING_PROTOCOL *This,
                                      CONST EFI_STRING Config, UINT8 *Block,
                                      UINTN *Size, EFI_STRING *Progress)
{
  assert (*Size == sizeof (proposal));
  memcpy (Block, proposal, sizeof (proposal));
  return EFI_SUCCESS;
}

static EFI_STATUS route_proposal (VOID)
{
  EFI_STRING Progress;
  writes = 0;
  return Route (NULL, L"G41PlatformData", &Progress);
}

int main (void)
{
  EFI_HII_CONFIG_ROUTING_PROTOCOL Routing = {0};
  UINT8 Buffer[16];
  UINTN Index, Value, Tests = 0;
  Routing.ConfigToBlock = config_block;
  mRouting = &Routing;
  runtime.GetVariable = read_var;
  runtime.SetVariable = write_var;
  assert (ReadStore (&mStores[4], Buffer) == EFI_SUCCESS);
  for (Index = 0; Index < ARRAY_SIZE (mNativeOptions); Index++)
    assert (Buffer[Index] == mNativeOptions[Index].Default);
  memcpy (proposal, Buffer, sizeof (proposal));
  assert (route_proposal () == EFI_SUCCESS && writes == 0);
  Tests++;
  for (Index = 0; Index < ARRAY_SIZE (mNativeOptions); Index++) {
    for (Value = 0; Value < 16; Value++) {
      if (!(mNativeOptions[Index].AllowedMask & (1U << Value))) continue;
      assert (ReadStore (&mStores[4], proposal) == EFI_SUCCESS);
      BOOLEAN Changed = proposal[Index] != Value;
      proposal[Index] = Value;
      assert (route_proposal () == EFI_SUCCESS && writes == Changed);
      assert (ReadStore (&mStores[4], Buffer) == EFI_SUCCESS && Buffer[Index] == Value);
      Tests++;
    }
  }
  // Invalid SATA/AHCI, unsupported UMA codes and reserved bytes must cause no writes.
  for (Index = 0; Index < sizeof (proposal); Index++) {
    assert (ReadStore (&mStores[4], proposal) == EFI_SUCCESS);
    proposal[Index] = Index < ARRAY_SIZE (mNativeOptions) ? 16 : 1;
    assert (route_proposal () == EFI_INVALID_PARAMETER && writes == 0);
    Tests++;
  }
  assert (ReadStore (&mStores[4], proposal) == EFI_SUCCESS);
  proposal[2] = 5;
  assert (route_proposal () == EFI_INVALID_PARAMETER && writes == 0);
  proposal[2] = 6;
  proposal[3] = 0;
  assert (route_proposal () == EFI_INVALID_PARAMETER && writes == 0);
  values[0] = 255;
  assert (ReadStore (&mStores[4], Buffer) == EFI_SUCCESS && Buffer[0] == 1);
  values[0] = 0;
  malformed = 0;
  assert (ReadStore (&mStores[4], Buffer) == EFI_SUCCESS && Buffer[0] == 1);
  malformed = 99;
  assert (ReadStore (&mStores[4], proposal) == EFI_SUCCESS);
  proposal[0] ^= 1;
  write_status = EFI_DEVICE_ERROR;
  assert (route_proposal () == EFI_DEVICE_ERROR && writes == 1);
  Tests += 5;
  write_status = EFI_SUCCESS;
  attributes[0] |= EFI_VARIABLE_RUNTIME_ACCESS;
  assert (route_proposal () == EFI_SUCCESS && writes == 1);
  assert (attributes[0] & EFI_VARIABLE_RUNTIME_ACCESS);
  assert (ReadStore (&mStores[4], proposal) == EFI_SUCCESS);
  proposal[0] ^= 1;
  attributes[0] |= EFI_VARIABLE_AUTHENTICATED_WRITE_ACCESS;
  assert (route_proposal () == EFI_WRITE_PROTECTED && writes == 0);
  Tests += 2;
  printf ("PASS: %zu native ConfigAccess cases (defaults, every allowed value, UINT32 storage, invalid inputs, write failure)\n", (size_t)Tests);
  return 0;
}
