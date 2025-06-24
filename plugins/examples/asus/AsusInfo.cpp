#include "AsusInfo.h"

AsusInfo::AsusInfo()
{
}
AsusInfo::~AsusInfo()
{
}

bool AsusInfo::checkASUSModel(void)
{
	DmiReader dmi;

	if (!dmi.Open())
		return false;

	while (!dmi.IsDone())
	{
		if (dmi.GetType() == 2)
		{
			DMI_TYPE2* base = (DMI_TYPE2*)dmi.GetBaseAddress();
			std::string name = dmi.GetString(base->Manufacturer);
			if (ToUpperCaseStr(name.c_str()).find(ASUS_MOTHERBOARD) != std::string::npos)
			{
				dmi.Close();
				return true;
			}
		}
		dmi.Next();
	}
	dmi.Close();

	return false;
}


std::string AsusInfo::getBIOSVersion(void)
{
	DmiReader dmi;
	std::string ver = "";

	if (!dmi.Open())
		return "";

	while (!dmi.IsDone())
	{
		if (dmi.GetType() == 0)
		{
			DMI_TYPE0* base = (DMI_TYPE0*)dmi.GetBaseAddress();
			ver = dmi.GetString(base->BIOS_Version);
			break;
		}
		dmi.Next();
	}
	dmi.Close();
	return ver;
}

std::string AsusInfo::ToUpperCaseStr(const char* type)
{
	std::string Str = "";

	Str = std::string(type);
	std::transform(Str.begin(), Str.end(), Str.begin(), ::toupper);

	return Str;
}

std::string AsusInfo::getModelName(void)
{
	DmiReader dmi;
	std::string name = "";

	if (!dmi.Open())
		return "";

	while (!dmi.IsDone())
	{
		if (dmi.GetType() == 2)
		{
			DMI_TYPE2* base = (DMI_TYPE2*)dmi.GetBaseAddress();
			name = dmi.GetString(base->ProductName);
			break;
		}
		dmi.Next();
	}
	dmi.Close();
	return name;
}
