#include "nvapi.h"  // This is the header file for the static library functions

extern "C" __declspec(dllexport) int register_rise_callback(NV_RISE_CALLBACK_SETTINGS* pCallbackSettings)
{
    return NvAPI_RegisterRiseCallback(pCallbackSettings);  // Call the function from the static library
}

extern "C" __declspec(dllexport) int request_rise(NV_REQUEST_RISE_SETTINGS* requestContent)
{
    return NvAPI_RequestRise(requestContent);  // Call the function from the static library
}