/** @file
  Registers the ASUS Setup HII packages without dispatching the donor driver.

  The donor PE image is stored in a RAW FFS section.  Only its HII resource is
  copied into the HII database with a local, allowlisted ConfigAccess driver.
  Browser actions never invoke donor hardware callbacks.

  SPDX-License-Identifier: BSD-2-Clause-Patent
**/

#include <Uefi.h>

#include <IndustryStandard/PeImage.h>
#include <Library/BaseMemoryLib.h>
#include <Library/DebugLib.h>
#include <Library/DxeServicesLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Protocol/HiiDatabase.h>
#include <Uefi/UefiInternalFormRepresentation.h>

#define RESOURCE_DIRECTORY_FLAG  BIT31
#define RESOURCE_OFFSET_MASK     MAX_UINT32 >> 1
#define ASUS_HII_RESOURCE_ID     1
#define ASUS_HII_LANGUAGE_ID     0x409

VOID G41BindHiiSensors (EFI_HII_HANDLE Hii);
EFI_STATUS G41InstallHiiConfig (EFI_HANDLE *Driver);

STATIC EFI_GUID  mAsusSetupRawFileGuid = {
  0x6f7c8b8f, 0x0f64, 0x4baa,
  { 0x95, 0xee, 0x06, 0xf7, 0x49, 0xd7, 0x3e, 0x9b }
};

STATIC EFI_GUID  mAsusSetupPackageListGuid = {
  0x899407d7, 0x99fe, 0x43d8,
  { 0x9a, 0x21, 0x79, 0xec, 0x32, 0x8c, 0xac, 0x21 }
};

typedef struct {
  CONST UINT8    *Image;
  UINTN          ImageSize;
  UINTN          SectionTableOffset;
  UINT16         NumberOfSections;
} PE_IMAGE_VIEW;

STATIC
BOOLEAN
RangeIsValid (
  IN UINTN  Offset,
  IN UINTN  Length,
  IN UINTN  BufferSize
  )
{
  return (Offset <= BufferSize) && (Length <= BufferSize - Offset);
}

STATIC
UINT16
ReadUint16 (
  IN CONST UINT8  *Buffer
  )
{
  UINT16  Value;

  CopyMem (&Value, Buffer, sizeof (Value));
  return Value;
}

STATIC
UINT32
ReadUint32 (
  IN CONST UINT8  *Buffer
  )
{
  UINT32  Value;

  CopyMem (&Value, Buffer, sizeof (Value));
  return Value;
}

STATIC
BOOLEAN
RvaToFileOffset (
  IN  CONST PE_IMAGE_VIEW  *View,
  IN  UINT32               Rva,
  IN  UINTN                Length,
  OUT UINTN                *FileOffset,
  OUT UINTN                *SectionIndex OPTIONAL
  )
{
  UINTN        Index;
  UINTN        HeaderOffset;
  CONST UINT8  *Header;
  UINT32       VirtualAddress;
  UINT32       RawSize;
  UINT32       RawOffset;
  UINTN        Delta;

  for (Index = 0; Index < View->NumberOfSections; Index++) {
    HeaderOffset = View->SectionTableOffset +
                   Index * EFI_IMAGE_SIZEOF_SECTION_HEADER;
    Header         = View->Image + HeaderOffset;
    VirtualAddress = ReadUint32 (Header + 12);
    RawSize        = ReadUint32 (Header + 16);
    RawOffset      = ReadUint32 (Header + 20);
    if (Rva < VirtualAddress) {
      continue;
    }

    Delta = (UINTN)Rva - VirtualAddress;
    if ((Delta > RawSize) || (Length > RawSize - Delta) ||
        !RangeIsValid (RawOffset, RawSize, View->ImageSize) ||
        !RangeIsValid ((UINTN)RawOffset + Delta, Length, View->ImageSize))
    {
      continue;
    }

    *FileOffset = (UINTN)RawOffset + Delta;
    if (SectionIndex != NULL) {
      *SectionIndex = Index;
    }

    return TRUE;
  }

  return FALSE;
}

STATIC
EFI_STATUS
OpenPeImage (
  IN  CONST UINT8    *Image,
  IN  UINTN          ImageSize,
  OUT PE_IMAGE_VIEW  *View,
  OUT UINT32         *ResourceRva,
  OUT UINT32         *ResourceSize
  )
{
  UINTN   PeOffset;
  UINTN   FileHeaderOffset;
  UINTN   OptionalHeaderOffset;
  UINTN   SectionTableSize;
  UINT16  OptionalHeaderSize;
  UINT32  NumberOfRvaAndSizes;

  if (!RangeIsValid (0, sizeof (EFI_IMAGE_DOS_HEADER), ImageSize) ||
      (ReadUint16 (Image) != EFI_IMAGE_DOS_SIGNATURE))
  {
    return EFI_COMPROMISED_DATA;
  }

  PeOffset = ReadUint32 (Image + OFFSET_OF (EFI_IMAGE_DOS_HEADER, e_lfanew));
  if (!RangeIsValid (
         PeOffset,
         sizeof (UINT32) + sizeof (EFI_IMAGE_FILE_HEADER),
         ImageSize
         ) ||
      (ReadUint32 (Image + PeOffset) != EFI_IMAGE_NT_SIGNATURE))
  {
    return EFI_COMPROMISED_DATA;
  }

  FileHeaderOffset     = PeOffset + sizeof (UINT32);
  View->NumberOfSections = ReadUint16 (Image + FileHeaderOffset + 2);
  OptionalHeaderSize   = ReadUint16 (Image + FileHeaderOffset + 16);
  OptionalHeaderOffset = FileHeaderOffset + sizeof (EFI_IMAGE_FILE_HEADER);
  if ((View->NumberOfSections == 0) ||
      !RangeIsValid (OptionalHeaderOffset, OptionalHeaderSize, ImageSize) ||
      (OptionalHeaderSize < sizeof (EFI_IMAGE_OPTIONAL_HEADER64)) ||
      (ReadUint16 (Image + OptionalHeaderOffset) !=
       EFI_IMAGE_NT_OPTIONAL_HDR64_MAGIC))
  {
    return EFI_COMPROMISED_DATA;
  }

  NumberOfRvaAndSizes = ReadUint32 (Image + OptionalHeaderOffset + 108);
  if (NumberOfRvaAndSizes <= EFI_IMAGE_DIRECTORY_ENTRY_RESOURCE) {
    return EFI_NOT_FOUND;
  }

  *ResourceRva  = ReadUint32 (
                    Image + OptionalHeaderOffset + 112 +
                    EFI_IMAGE_DIRECTORY_ENTRY_RESOURCE *
                    sizeof (EFI_IMAGE_DATA_DIRECTORY)
                    );
  *ResourceSize = ReadUint32 (
                    Image + OptionalHeaderOffset + 116 +
                    EFI_IMAGE_DIRECTORY_ENTRY_RESOURCE *
                    sizeof (EFI_IMAGE_DATA_DIRECTORY)
                    );
  if ((*ResourceRva == 0) || (*ResourceSize < sizeof (EFI_IMAGE_RESOURCE_DIRECTORY))) {
    return EFI_NOT_FOUND;
  }

  View->Image              = Image;
  View->ImageSize          = ImageSize;
  View->SectionTableOffset = OptionalHeaderOffset + OptionalHeaderSize;
  SectionTableSize         =
    (UINTN)View->NumberOfSections * EFI_IMAGE_SIZEOF_SECTION_HEADER;
  if (!RangeIsValid (View->SectionTableOffset, SectionTableSize, ImageSize)) {
    return EFI_COMPROMISED_DATA;
  }

  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
GetResourceDirectory (
  IN  CONST UINT8  *Resource,
  IN  UINTN        ResourceSize,
  IN  UINT32       DirectoryOffset,
  OUT UINTN        *EntryOffset,
  OUT UINT16       *NamedCount,
  OUT UINT16       *IdCount
  )
{
  UINTN  Count;

  if (!RangeIsValid (
         DirectoryOffset,
         sizeof (EFI_IMAGE_RESOURCE_DIRECTORY),
         ResourceSize
         ))
  {
    return EFI_COMPROMISED_DATA;
  }

  *NamedCount = ReadUint16 (Resource + DirectoryOffset + 12);
  *IdCount    = ReadUint16 (Resource + DirectoryOffset + 14);
  Count       = (UINTN)*NamedCount + *IdCount;
  *EntryOffset = DirectoryOffset + sizeof (EFI_IMAGE_RESOURCE_DIRECTORY);
  if (!RangeIsValid (
         *EntryOffset,
         Count * sizeof (EFI_IMAGE_RESOURCE_DIRECTORY_ENTRY),
         ResourceSize
         ))
  {
    return EFI_COMPROMISED_DATA;
  }

  return EFI_SUCCESS;
}

STATIC
BOOLEAN
IsHiiResourceName (
  IN CONST UINT8  *Resource,
  IN UINTN        ResourceSize,
  IN UINT32       Name
  )
{
  UINTN  Offset;
  UINT16 Length;

  if ((Name & RESOURCE_DIRECTORY_FLAG) == 0) {
    return FALSE;
  }

  Offset = Name & RESOURCE_OFFSET_MASK;
  if (!RangeIsValid (Offset, sizeof (UINT16), ResourceSize)) {
    return FALSE;
  }

  Length = ReadUint16 (Resource + Offset);
  return (Length == 3) &&
         RangeIsValid (Offset + sizeof (UINT16), Length * sizeof (CHAR16), ResourceSize) &&
         (ReadUint16 (Resource + Offset + 2) == L'H') &&
         (ReadUint16 (Resource + Offset + 4) == L'I') &&
         (ReadUint16 (Resource + Offset + 6) == L'I');
}

STATIC
EFI_STATUS
FindNamedHiiDirectory (
  IN  CONST UINT8  *Resource,
  IN  UINTN        ResourceSize,
  OUT UINT32       *DirectoryOffset
  )
{
  EFI_STATUS  Status;
  UINTN       EntryOffset;
  UINT16      NamedCount;
  UINT16      IdCount;
  UINTN       Index;
  UINT32      Name;
  UINT32      Target;

  Status = GetResourceDirectory (
             Resource,
             ResourceSize,
             0,
             &EntryOffset,
             &NamedCount,
             &IdCount
             );
  if (EFI_ERROR (Status)) {
    return Status;
  }

  for (Index = 0; Index < NamedCount; Index++) {
    Name   = ReadUint32 (Resource + EntryOffset + Index * 8);
    Target = ReadUint32 (Resource + EntryOffset + Index * 8 + 4);
    if (IsHiiResourceName (Resource, ResourceSize, Name)) {
      if ((Target & RESOURCE_DIRECTORY_FLAG) == 0) {
        return EFI_COMPROMISED_DATA;
      }

      *DirectoryOffset = Target & RESOURCE_OFFSET_MASK;
      return EFI_SUCCESS;
    }
  }

  return EFI_NOT_FOUND;
}

STATIC
EFI_STATUS
FindIdDirectory (
  IN  CONST UINT8  *Resource,
  IN  UINTN        ResourceSize,
  IN  UINT32       ParentOffset,
  IN  UINT32       Id,
  OUT UINT32       *DirectoryOffset
  )
{
  EFI_STATUS  Status;
  UINTN       EntryOffset;
  UINT16      NamedCount;
  UINT16      IdCount;
  UINTN       Index;
  UINT32      Name;
  UINT32      Target;

  Status = GetResourceDirectory (
             Resource,
             ResourceSize,
             ParentOffset,
             &EntryOffset,
             &NamedCount,
             &IdCount
             );
  if (EFI_ERROR (Status)) {
    return Status;
  }

  EntryOffset += (UINTN)NamedCount * sizeof (EFI_IMAGE_RESOURCE_DIRECTORY_ENTRY);
  for (Index = 0; Index < IdCount; Index++) {
    Name   = ReadUint32 (Resource + EntryOffset + Index * 8);
    Target = ReadUint32 (Resource + EntryOffset + Index * 8 + 4);
    if ((Name == Id) && ((Target & RESOURCE_DIRECTORY_FLAG) != 0)) {
      *DirectoryOffset = Target & RESOURCE_OFFSET_MASK;
      return EFI_SUCCESS;
    }
  }

  return EFI_NOT_FOUND;
}

STATIC
EFI_STATUS
FindIdDataEntry (
  IN  CONST UINT8  *Resource,
  IN  UINTN        ResourceSize,
  IN  UINT32       ParentOffset,
  IN  UINT32       Id,
  OUT UINT32       *DataEntryOffset
  )
{
  EFI_STATUS  Status;
  UINTN       EntryOffset;
  UINT16      NamedCount;
  UINT16      IdCount;
  UINTN       Index;
  UINT32      Name;
  UINT32      Target;

  Status = GetResourceDirectory (
             Resource,
             ResourceSize,
             ParentOffset,
             &EntryOffset,
             &NamedCount,
             &IdCount
             );
  if (EFI_ERROR (Status)) {
    return Status;
  }

  EntryOffset += (UINTN)NamedCount * sizeof (EFI_IMAGE_RESOURCE_DIRECTORY_ENTRY);
  for (Index = 0; Index < IdCount; Index++) {
    Name   = ReadUint32 (Resource + EntryOffset + Index * 8);
    Target = ReadUint32 (Resource + EntryOffset + Index * 8 + 4);
    if ((Name == Id) && ((Target & RESOURCE_DIRECTORY_FLAG) == 0)) {
      if (!RangeIsValid (
             Target,
             sizeof (EFI_IMAGE_RESOURCE_DATA_ENTRY),
             ResourceSize
             ))
      {
        return EFI_COMPROMISED_DATA;
      }

      *DataEntryOffset = Target;
      return EFI_SUCCESS;
    }
  }

  return EFI_NOT_FOUND;
}

STATIC
EFI_STATUS
ValidatePackageList (
  IN CONST UINT8  *PackageList,
  IN UINTN        PackageListSize
  )
{
  UINTN    Offset;
  UINT32   Header;
  UINT32   Length;
  UINT8    Type;
  BOOLEAN  HasForms;
  BOOLEAN  HasStrings;

  if ((PackageListSize < sizeof (EFI_HII_PACKAGE_LIST_HEADER) + sizeof (UINT32)) ||
      !CompareGuid ((CONST EFI_GUID *)PackageList, &mAsusSetupPackageListGuid) ||
      (ReadUint32 (PackageList + sizeof (EFI_GUID)) != PackageListSize))
  {
    return EFI_COMPROMISED_DATA;
  }

  Offset     = sizeof (EFI_HII_PACKAGE_LIST_HEADER);
  HasForms   = FALSE;
  HasStrings = FALSE;
  while (Offset < PackageListSize) {
    if (!RangeIsValid (Offset, sizeof (UINT32), PackageListSize)) {
      return EFI_COMPROMISED_DATA;
    }

    Header = ReadUint32 (PackageList + Offset);
    Length = Header & 0x00ffffff;
    Type   = (UINT8)(Header >> 24);
    if ((Length < sizeof (UINT32)) ||
        !RangeIsValid (Offset, Length, PackageListSize))
    {
      return EFI_COMPROMISED_DATA;
    }

    if (Type == EFI_HII_PACKAGE_END) {
      return ((Length == sizeof (UINT32)) &&
              (Offset + Length == PackageListSize) &&
              HasForms && HasStrings) ? EFI_SUCCESS : EFI_COMPROMISED_DATA;
    }

    HasForms   |= (Type == EFI_HII_PACKAGE_FORMS);
    HasStrings |= (Type == EFI_HII_PACKAGE_STRINGS);
    Offset     += Length;
  }

  return EFI_COMPROMISED_DATA;
}

STATIC
EFI_STATUS
FindAsusPackageList (
  IN  CONST UINT8  *Image,
  IN  UINTN        ImageSize,
  OUT CONST UINT8  **PackageList,
  OUT UINTN        *PackageListSize
  )
{
  EFI_STATUS     Status;
  PE_IMAGE_VIEW  View;
  UINT32         ResourceRva;
  UINT32         ResourceSize;
  UINTN          ResourceOffset;
  UINTN          ResourceSection;
  CONST UINT8    *SectionHeader;
  CONST UINT8    *Resource;
  UINT32         TypeDirectory;
  UINT32         NameDirectory;
  UINT32         DataEntryOffset;
  UINT32         DataRva;
  UINT32         DataSize;
  UINTN          DataOffset;

  Status = OpenPeImage (
             Image,
             ImageSize,
             &View,
             &ResourceRva,
             &ResourceSize
             );
  if (EFI_ERROR (Status)) {
    return Status;
  }

  if (!RvaToFileOffset (
         &View,
         ResourceRva,
         ResourceSize,
         &ResourceOffset,
         &ResourceSection
         ))
  {
    return EFI_COMPROMISED_DATA;
  }

  SectionHeader = Image + View.SectionTableOffset +
                  ResourceSection * EFI_IMAGE_SIZEOF_SECTION_HEADER;
  if (CompareMem (SectionHeader, ".rsrc\0\0\0", EFI_IMAGE_SIZEOF_SHORT_NAME) != 0) {
    return EFI_COMPROMISED_DATA;
  }

  Resource = Image + ResourceOffset;
  Status   = FindNamedHiiDirectory (
               Resource,
               ResourceSize,
               &TypeDirectory
               );
  if (!EFI_ERROR (Status)) {
    Status = FindIdDirectory (
               Resource,
               ResourceSize,
               TypeDirectory,
               ASUS_HII_RESOURCE_ID,
               &NameDirectory
               );
  }

  if (!EFI_ERROR (Status)) {
    Status = FindIdDataEntry (
               Resource,
               ResourceSize,
               NameDirectory,
               ASUS_HII_LANGUAGE_ID,
               &DataEntryOffset
               );
  }

  if (EFI_ERROR (Status)) {
    return Status;
  }

  DataRva  = ReadUint32 (Resource + DataEntryOffset);
  DataSize = ReadUint32 (Resource + DataEntryOffset + 4);
  if ((DataRva < ResourceRva) ||
      (DataRva - ResourceRva > ResourceSize) ||
      (DataSize > ResourceSize - (DataRva - ResourceRva)) ||
      !RvaToFileOffset (&View, DataRva, DataSize, &DataOffset, NULL))
  {
    return EFI_COMPROMISED_DATA;
  }

  Status = ValidatePackageList (Image + DataOffset, DataSize);
  if (EFI_ERROR (Status)) {
    return Status;
  }

  *PackageList     = Image + DataOffset;
  *PackageListSize = DataSize;
  return EFI_SUCCESS;
}

EFI_STATUS
EFIAPI
AsusSetupHiiEntryPoint (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_STATUS                 Status;
  VOID                       *RawImage;
  UINTN                      RawImageSize;
  CONST UINT8                *PackageList;
  UINTN                      PackageListSize;
  EFI_HII_DATABASE_PROTOCOL  *HiiDatabase;
  EFI_HII_HANDLE             HiiHandle;
  EFI_HANDLE                 Driver;

  (VOID)ImageHandle;
  (VOID)SystemTable;
  RawImage = NULL;
  Status   = GetSectionFromAnyFv (
               &mAsusSetupRawFileGuid,
               EFI_SECTION_RAW,
               0,
               &RawImage,
               &RawImageSize
               );
  if (EFI_ERROR (Status)) {
    DEBUG ((DEBUG_ERROR, "ASUS HII data: RAW donor not found: %r\n", Status));
    return Status;
  }

  Status = FindAsusPackageList (
             RawImage,
             RawImageSize,
             &PackageList,
             &PackageListSize
             );
  if (EFI_ERROR (Status)) {
    DEBUG ((DEBUG_ERROR, "ASUS HII data: invalid donor resource: %r\n", Status));
    FreePool (RawImage);
    return Status;
  }

  Status = gBS->LocateProtocol (
                  &gEfiHiiDatabaseProtocolGuid,
                  NULL,
                  (VOID **)&HiiDatabase
                  );
  if (!EFI_ERROR (Status)) {
    Status = G41InstallHiiConfig (&Driver);
  }
  if (!EFI_ERROR (Status)) {
    HiiHandle = NULL;
    Status = HiiDatabase->NewPackageList (
                            HiiDatabase,
                            (CONST EFI_HII_PACKAGE_LIST_HEADER *)PackageList,
                            Driver,
                            &HiiHandle
                            );
  }

  DEBUG ((
    EFI_ERROR (Status) ? DEBUG_ERROR : DEBUG_INFO,
    "ASUS HII data: registered %u-byte package list with G41 ConfigAccess: %r\n",
    (UINT32)PackageListSize,
    Status
    ));
  if (!EFI_ERROR (Status)) {
    G41BindHiiSensors (HiiHandle);
  }
  FreePool (RawImage);
  return Status;
}
