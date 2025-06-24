#include "AsusFanControl.h"

AsusFanControl::AsusFanControl()
{
}

AsusFanControl::~AsusFanControl()
{
}

bool AsusFanControl::getFanMode(const json& params, std::string& strmode, std::string& modestring)
{
	const std::string MODE = "mode";
	auto it = params.find(MODE);
	if (it == params.end() || !it->is_string())
	{
		return false;
	}

	std::string clr = toLowerCase(params[MODE]);
	modestring = clr;
	std::string sMode = "";
	try
	{
		mapModeValue(clr, strmode);
	}
	catch (const std::out_of_range&)
	{
		strmode = clr;
		return false;
	}

	return true;
}

int AsusFanControl::SendCmdToFanXpertPage(std::string FanMode)
{
	if (FanMode == "")
		return 0;

	bool result = false;
	std::string payload_1 = R"({"command":"broadcastEvent","target":{"role":"deviceService","deviceType":"50","pid":"2dfe216d-3481-4684-ad4d-2566bd7cfe4f"},"msg":{"cmd":"20002","mode":)";
	std::string payload_2 = R"(,"receiver":{"role":"agent"}}})";
	std::string payload = payload_1 + R"(")" + FanMode + R"(")" + payload_2;

	WebSocketClient ws_client(("ws://127.0.0.1:" + getFrameworkHttpPort() + "/?role=agent").c_str(), payload);
	ws_client.start();

	if (ws_client.wait_for_status_change(5))
	{
		result = ws_client.m_message_received;
	}
	ws_client.close();

	if (result)
	{
		return 2;
	}
	else
	{
		return 0;
	}
}

void AsusFanControl::mapModeValue(const std::string strMode, std::string& iMode)
{
	static const std::map<std::string, std::string> modeMap
	{
		{ "full speed", "0"},
		{ "turbo",		"1"},
		{ "standard",	"2"},
		{ "normal",		"2"},
		{ "silent",		"3"}
	};

	iMode = modeMap.at(strMode);
}

std::string AsusFanControl::toLowerCase(std::string s)
{
	std::string lower = std::move(s);
	std::transform(lower.begin(), lower.end(), lower.begin(),
		[](unsigned char c) { return std::tolower(c); });
	return lower;
}

std::wstring AsusFanControl::utf8_to_wstring(const std::string& utf8_str)
{
	int wide_len = ::MultiByteToWideChar(CP_UTF8, 0, utf8_str.c_str(), -1, nullptr, 0);
	std::wstring wide_str(wide_len, L'\0');
	::MultiByteToWideChar(CP_UTF8, 0, utf8_str.c_str(), -1, &wide_str[0], wide_len);
	return wide_str;
}

std::string AsusFanControl::wstring_to_utf8(const std::wstring& wide_str)
{
	int utf8_len = ::WideCharToMultiByte(CP_UTF8, 0, wide_str.c_str(), -1, nullptr, 0, nullptr, nullptr);
	std::string utf8_str(utf8_len, '\0');
	::WideCharToMultiByte(CP_UTF8, 0, wide_str.c_str(), -1, &utf8_str[0], utf8_len, nullptr, nullptr);
	return utf8_str;
}

std::string AsusFanControl::getFrameworkHttpPort()
{
	HKEY hKey = NULL;
	wchar_t wszHttpPort[512] = { 0 };
	DWORD dwSize = 512;
	std::wstring wsPort = L"1042";

	RegOpenKeyEx(HKEY_LOCAL_MACHINE, L"SOFTWARE\\ASUS\\ArmouryDevice", 0, KEY_READ | KEY_WOW64_32KEY, &hKey);
	if (hKey != NULL)
	{
		ULONG ulResult = RegQueryValueEx(hKey, L"HTTPPort", 0, NULL, (LPBYTE)wszHttpPort, &dwSize);
		if (ERROR_SUCCESS == ulResult) {
			RegCloseKey(hKey);
			hKey = NULL;
			wsPort = wszHttpPort;
		}
		RegCloseKey(hKey);
	}

	return wstring_to_utf8(wsPort);
}

std::string AsusFanControl::GetUWPVersion(PCWSTR pcszPackageName)
{
	std::wstring cmd = L"";
	std::wstring getVerParam = L"";

	std::string version = "";
	size_t pos;

	SECURITY_ATTRIBUTES saAttr;
	saAttr.nLength = sizeof(SECURITY_ATTRIBUTES);
	saAttr.bInheritHandle = TRUE;
	saAttr.lpSecurityDescriptor = NULL;

	HANDLE hStdOutRead, hStdOutWrite;

	if (!CreatePipe(&hStdOutRead, &hStdOutWrite, &saAttr, 0))
	{
		goto END;
	}

	if (!SetHandleInformation(hStdOutRead, HANDLE_FLAG_INHERIT, 0))
	{
		CloseHandle(hStdOutRead);
		CloseHandle(hStdOutWrite);
		goto END;
	}

	if (!pcszPackageName)
	{
		goto END;
	}

	getVerParam = LR"("(get-appxpackage -Name )";
	getVerParam += pcszPackageName;
	getVerParam += LR"().Version")";

	cmd = L"Powershell ";
	cmd += getVerParam;

	STARTUPINFO si;
	ZeroMemory(&si, sizeof(STARTUPINFO));
	si.cb = sizeof(STARTUPINFO);
	si.hStdOutput = hStdOutWrite;
	si.hStdError = hStdOutWrite;
	si.dwFlags |= STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
	si.wShowWindow = SW_HIDE;

	PROCESS_INFORMATION pi;
	ZeroMemory(&pi, sizeof(pi));

	if (!CreateProcess(NULL, &cmd[0], NULL, NULL, true, 0, NULL, NULL, &si, &pi))
	{
		CloseHandle(hStdOutRead);
		CloseHandle(hStdOutWrite);
		goto END;
	}

	CloseHandle(hStdOutWrite);

	DWORD dwRead;
	CHAR chBuf[4096];

	while (ReadFile(hStdOutRead, chBuf, sizeof(chBuf) - 1, &dwRead, NULL) && dwRead > 0)
	{
		chBuf[dwRead] = '\0';
		version += chBuf;
	}

	CloseHandle(hStdOutRead);
	CloseHandle(pi.hProcess);
	CloseHandle(pi.hThread);

	pos = version.find('\r');
	if (std::string::npos != pos)
	{
		version = version.replace(pos, 1, "");
	}

	pos = version.find('\n');
	if (std::string::npos != pos)
	{
		version = version.replace(pos, 1, "");
	}

	if (version.empty())
	{
		version = "";
	}

END:
	return version;
}

bool AsusFanControl::IsACInstalled(void)
{
	std::string AC_Version;

	PCWSTR pcszPackageName = L"B9ECED6F.ArmouryCrate";
	AC_Version = GetUWPVersion(pcszPackageName);

	return !AC_Version.empty();
}
