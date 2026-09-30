/* Host test of the real boot-policy consumer. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#undef NULL
#include <Uefi.h>
#include <Library/G41CsmPolicy.h>

static EFI_RUNTIME_SERVICES runtime;
EFI_RUNTIME_SERVICES *gRT = &runtime;
static UINT32 active;
static UINTN variable_size = 4;
static EFI_STATUS read_status;

static EFI_STATUS EFIAPI read_variable (CHAR16 *Name, EFI_GUID *Guid,
  UINT32 *Attributes, UINTN *Size, VOID *Data)
{
  assert (!memcmp(Guid, &mG41CsmNvGuid, sizeof(*Guid)));
  if (EFI_ERROR(read_status)) return read_status;
  memcpy(Data, &active, 4);
  *Size = variable_size;
  return EFI_SUCCESS;
}

BOOLEAN EFIAPI IsDevicePathEnd (CONST VOID *Node)
{
  return ((CONST EFI_DEVICE_PATH_PROTOCOL *)Node)->Type == END_DEVICE_PATH_TYPE;
}
EFI_DEVICE_PATH_PROTOCOL *EFIAPI NextDevicePathNode (CONST VOID *Node)
{
  CONST EFI_DEVICE_PATH_PROTOCOL *Path = Node;
  return (EFI_DEVICE_PATH_PROTOCOL *)((UINT8 *)Node + Path->Length[0] + (Path->Length[1] << 8));
}
UINT8 EFIAPI DevicePathType (CONST VOID *Node)
{ return ((CONST EFI_DEVICE_PATH_PROTOCOL *)Node)->Type & 0x7f; }
UINT8 EFIAPI DevicePathSubType (CONST VOID *Node)
{ return ((CONST EFI_DEVICE_PATH_PROTOCOL *)Node)->SubType; }

int main (void)
{
  struct path { EFI_DEVICE_PATH_PROTOCOL node, end; } disk =
    {{MEDIA_DEVICE_PATH, MEDIA_HARDDRIVE_DP, {4, 0}}, {END_DEVICE_PATH_TYPE, END_ENTIRE_DEVICE_PATH_SUBTYPE, {4, 0}}};
  EFI_DEVICE_PATH_PROTOCOL legacy = {BBS_DEVICE_PATH, BBS_BBS_DP, {4, 0}};
  struct path tool = disk;
  tool.node.SubType = MEDIA_PIWG_FW_FILE_DP;
  runtime.GetVariable = read_variable;
  const UINT32 modes[] = {0, 1, 0x101, 0x201, 0x200, 0x102, 0xffffffff};
  for (UINTN i = 0; i < sizeof(modes)/sizeof(*modes); i++) {
    active = modes[i];
    assert (G41CsmBootAllowed(&legacy, LOAD_OPTION_ACTIVE) == (active == 1 || active == 0x201));
    assert (G41CsmBootAllowed(&disk.node, LOAD_OPTION_ACTIVE) == (active != 0x201));
    assert (G41CsmBootAllowed(&tool.node, LOAD_OPTION_ACTIVE));
    assert (G41CsmBootAllowed(&disk.node, LOAD_OPTION_CATEGORY_APP));
  }
  active = 1;
  variable_size = 3;
  assert (!G41CsmBootAllowed(&legacy, LOAD_OPTION_ACTIVE));
  variable_size = 4;
  read_status = EFI_NOT_FOUND;
  assert (!G41CsmBootAllowed(&legacy, LOAD_OPTION_ACTIVE));
  puts("PASS: native policy modes, tools exemption, malformed/missing policy fail closed");
}
