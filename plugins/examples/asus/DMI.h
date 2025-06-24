#ifndef __GS_DMI_H__
#define __GS_DMI_H__


#include <windows.h>


typedef PVOID (*MapMemFun)    (PVOID address, DWORD count);
typedef VOID  (*UnmapMemFun)  (PVOID address);

#pragma pack(push, r)
#pragma pack(1)

typedef struct _DMI_TYPE0_
{
	BYTE	Type;
	BYTE	Length;
	WORD	Handle;
	BYTE	Vendor;
	BYTE	BIOS_Version;
	WORD	BIOS_Address;
	BYTE	BIOS_ReleaseDate;
	BYTE	BIOS_ROM_Size;
	DWORD	BIOS_Char_Low;
	DWORD	BIOS_Char_High;
}DMI_TYPE0,*PDMI_TYPE0;


typedef struct _DMI_TYPE2_
{
	BYTE	Type;
	BYTE	Length;
	WORD	Handle;
	BYTE	Manufacturer;
	BYTE	ProductName;
	BYTE	Version;
	BYTE	SerialNumber;
	BYTE	AssetTag;
	BYTE	Feature;
	BYTE	Location;
	WORD	ChassisHandle;
	BYTE	BoardType;
	BYTE	ObjectHandleNum;
}DMI_TYPE2,*PDMI_TYPE2;


#pragma pack(pop, r)


class DmiHelp;

class DmiReader
{
public:

   DmiReader(void);
   DmiReader(MapMemFun map, UnmapMemFun unmap);
   ~DmiReader();

   bool Open(void);
   void Close(void);
   bool IsDone(void) const;
   void Next(void);
   int   GetType(void) const;
   void* GetBaseAddress(void) const;

   const char* GetString(int index);

private:

   DmiReader(const DmiReader& other);
   DmiReader& operator = (const DmiReader& other);

private:
    DmiHelp* m_help;

};

#endif