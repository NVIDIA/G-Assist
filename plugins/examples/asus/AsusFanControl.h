#pragma once

#include "WSClient.h"
#include <Windows.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

class AsusFanControl
{
public:
	AsusFanControl();
	~AsusFanControl();
	
	bool getFanMode(const json& params, std::string &mode, std::string &modestring);
	int SendCmdToFanXpertPage(std::string FanMode);
	
private:
	std::wstring utf8_to_wstring(const std::string& utf8_str);
	std::string wstring_to_utf8(const std::wstring& wide_str);

	std::string getFrameworkHttpPort();

	void mapModeValue(const std::string strMode, std::string& iMode);

	std::string toLowerCase(std::string s);


	bool IsACInstalled(void);
	std::string GetUWPVersion(PCWSTR pcszPackageName);

};