#pragma once

#include <string>
#include "DMI.h"
#include <algorithm>

#define ASUS_MOTHERBOARD "ASUSTEK COMPUTER INC."

class AsusInfo
{
public:
	AsusInfo();
	~AsusInfo();
	std::string getModelName(void);
	bool checkASUSModel(void);
	std::string getBIOSVersion(void);

private:
	std::string ToUpperCaseStr(const char* type);
};