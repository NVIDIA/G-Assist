#include "Dmi.h"
#include <assert.h>

struct RawSMBIOSData
{
    BYTE	Used20CallingMethod;
    BYTE	SMBIOSMajorVersion;
    BYTE	SMBIOSMinorVersion;
    BYTE	DmiRevision;
    DWORD	Length;
    BYTE	SMBIOSTableData[];
};

typedef  UINT (WINAPI *LPFN_GetSystemFirmwareTable)(
    DWORD FirmwareTableProviderSignature,
    DWORD FirmwareTableID,
    PVOID pFirmwareTableBuffer,
    DWORD BufferSize
);

LPFN_GetSystemFirmwareTable
fnGetSystemFirmwareTable = (LPFN_GetSystemFirmwareTable)GetProcAddress(
GetModuleHandleA("Kernel32.dll"),"GetSystemFirmwareTable");


class DmiHelp
{
public:

   DmiHelp(MapMemFun map, UnmapMemFun unmap);
   virtual ~DmiHelp();

   bool Open(void);
   void Close(void);
   bool IsOpen(void) const;

   bool IsDone(void) const;
   void Next(void);

   int   GetType(void) const;
   void* GetBaseAddress(void) const;
   const char* GetString(int index);

protected:

   virtual void* GetDmiBase(DWORD& size) = 0;
   virtual void Release(void){ }

private:

   BYTE* FindNextType(BYTE* base) const;
   bool  IsOutOfBoundary(BYTE* mem) const;


protected:

   MapMemFun    MapMem;
   UnmapMemFun  UnmapMem;

private:


   BYTE*   m_dmiBase;
   BYTE*   m_curTypeBase;
   DWORD    m_dmiSize;
};


DmiHelp::DmiHelp(MapMemFun map, UnmapMemFun unmap)
   : MapMem(map)
   , UnmapMem(unmap)
   , m_curTypeBase(NULL)
   , m_dmiBase(NULL)
{

}


DmiHelp::~DmiHelp()
{
    m_dmiBase     = NULL;
    m_curTypeBase = NULL;
}

bool DmiHelp::Open(void)
{
   assert( !IsOpen() );

   m_dmiBase = (BYTE*) GetDmiBase(m_dmiSize);
   if (m_dmiBase == NULL)
   {
       Release();
       return false;
   }
   else
   {
       m_curTypeBase = m_dmiBase;
       return true;
   }
}

void DmiHelp::Close(void)
{
    Release();
    m_dmiBase     = NULL;
    m_curTypeBase = NULL;
}

bool DmiHelp::IsOpen(void) const
{
   return m_dmiBase != NULL;
}

bool DmiHelp::IsDone(void) const
{
   assert(IsOpen());

   return IsOutOfBoundary(m_curTypeBase);
}

void DmiHelp::Next(void)
{
   assert(IsOpen() );

   m_curTypeBase = FindNextType(m_curTypeBase);
}

int DmiHelp::GetType(void) const
{
   assert( !IsDone() );

   return *m_curTypeBase;
}

void* DmiHelp::GetBaseAddress(void) const
{
   assert( !IsDone() );

   return m_curTypeBase;
}

const char* DmiHelp::GetString(int index)
{
   assert( !IsDone() );

   if (index <= 0)
      return "";

   int   num = 0;
	BYTE* base = m_curTypeBase + *(m_curTypeBase + 1);

	while (num < index-1)
	{
      while ( *base != '\0')
         ++base;
      ++base;
      ++num;
	}

   return (const char*) base;
}


BYTE* FindNextString(BYTE* base)
{
	while (*base)
		++base;

	return (base+1);
}

BYTE* DmiHelp::FindNextType(BYTE* base) const
{
  BYTE length = *(base + 1);

  base = base + length;

  base = FindNextString(base);

  while ( *base != '\0' )
  {
  	base = FindNextString(base);
  }
  ++base;

   return base;
}

bool  DmiHelp::IsOutOfBoundary(BYTE* mem) const
{
   return (*m_curTypeBase == 127 || mem >= m_dmiBase +  m_dmiSize );
}


class DmiHelpByAPI: public DmiHelp
{
    typedef DmiHelp super_t;

public:

   DmiHelpByAPI(MapMemFun map, UnmapMemFun unmap);
   virtual ~DmiHelpByAPI();

protected:

   void* GetDmiBase(DWORD& size);
   void  Release(void);

private:
   BYTE*   m_base;
};


DmiHelpByAPI::DmiHelpByAPI(MapMemFun map, UnmapMemFun unmap)
    :super_t(map, unmap)
{
}


DmiHelpByAPI::~DmiHelpByAPI()
{
    Release();
}

void* DmiHelpByAPI::GetDmiBase(DWORD& size)
{
    DWORD iSignature =             'R';
    iSignature = iSignature << 8 | 'S';
    iSignature = iSignature << 8 | 'M';
    iSignature = iSignature << 8 | 'B';

    size = fnGetSystemFirmwareTable(iSignature, 0, 0, 0);
    m_base = new BYTE[size];

    size = fnGetSystemFirmwareTable(iSignature, 0, m_base, size);
    RawSMBIOSData* dmi = (RawSMBIOSData*)m_base;
    return dmi->SMBIOSTableData;
}


void DmiHelpByAPI::Release(void)
{
    delete m_base;
    m_base = NULL;
}


DmiReader::DmiReader(void)
	:m_help(NULL)
{
	if (fnGetSystemFirmwareTable)
	{
		m_help = new DmiHelpByAPI(NULL, NULL);
    }

}

DmiReader::DmiReader(MapMemFun map, UnmapMemFun unmap)
	:m_help(NULL)
{
    if (fnGetSystemFirmwareTable)
    {
        m_help = new DmiHelpByAPI(map, unmap);
    }
}


DmiReader::~DmiReader()
{
    if (m_help != NULL)
    {
        delete m_help;
        m_help = NULL;
    }
}


bool DmiReader::Open(void)
{
    if (m_help != NULL)
    {
        return m_help->Open();
    }
    else
        return false;
}

void DmiReader::Close(void)
{
    m_help->Close();
}

bool DmiReader::IsDone(void) const
{
    return m_help->IsDone();
}

void DmiReader::Next(void)
{
    return m_help->Next();
}

int DmiReader::GetType(void) const
{
    return m_help->GetType();
}

void* DmiReader::GetBaseAddress(void) const
{
    return m_help->GetBaseAddress();
}

const char* DmiReader::GetString(int index)
{
    return m_help->GetString(index);
}