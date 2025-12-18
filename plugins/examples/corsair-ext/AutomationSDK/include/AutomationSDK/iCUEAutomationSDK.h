/******************************************************************************
**
** File iCUEAutomationSDK.h
** Copyright (c) 2025, Corsair Memory, Inc. All Rights Reserved.
**
** This file is part of iCUE Automation SDK.
**
******************************************************************************/

#pragma once

#include "icueautomationsdk_export.h"

#ifdef __cplusplus
extern "C" {
#endif

// maximum number of devices to be discovered
const unsigned int AUTOMATION_SDK_DEVICE_COUNT_MAX = 64;

// maximum number of items (i.e. Actions, Presets, Profiles, etc.) to be discoverd
const unsigned int AUTOMATION_SDK_ITEMS_COUNT_MAX = 128;

// medium string length
const unsigned int AUTOMATION_SDK_STRING_SIZE_M = 128;

typedef char AutomationSdkId[AUTOMATION_SDK_STRING_SIZE_M];

enum AutomationSdkErrorCode {
	Success = 0,
	Failure = 1,
	NotConnected = 2,
	InvalidArguments = 3,
	ResourceNotFound = 4,
};

enum AutomationSdkDpiStageIndex {
	Invalid = -1,
	Stage1 = 0,
	Stage2 = 1,
	Stage3 = 2,
	Stage4 = 3,
	Stage5 = 4,
	SniperStage = 5,
};

struct AutomationSdkProfile
{
	char name[AUTOMATION_SDK_STRING_SIZE_M];
	AutomationSdkId id;
};

struct AutomationSdkAction
{
	char name[AUTOMATION_SDK_STRING_SIZE_M];
	AutomationSdkId id;
};

struct AutomationSdkDevice
{
	char name[AUTOMATION_SDK_STRING_SIZE_M];
	AutomationSdkId id;
};

struct AutomationSdkCoolingPreset
{
	char name[AUTOMATION_SDK_STRING_SIZE_M];
	AutomationSdkId id;
};

struct AutomationSdkEqualizerPreset
{
	char name[AUTOMATION_SDK_STRING_SIZE_M];
	AutomationSdkId id;
};

struct AutomationSdkDpiPreset
{
	char name[AUTOMATION_SDK_STRING_SIZE_M];
	AutomationSdkId id;
};

struct AutomationSdkDpiStage
{
	char name[AUTOMATION_SDK_STRING_SIZE_M];
	AutomationSdkDpiStageIndex index = AutomationSdkDpiStageIndex::Invalid;
};

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkConnect(const AutomationSdkId clientId);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkDisconnect();

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkGetProfiles(AutomationSdkProfile *profiles,
												int maxSize,
												int *size);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkActivateProfile(const AutomationSdkId profileId);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkGetLibraryActions(AutomationSdkAction *actions,
													  int maxSize,
													  int *size);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkActivateLibraryAction(const AutomationSdkId actionId);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkGetCoolingDevices(AutomationSdkDevice *devices,
													  int maxSize,
													  int *size);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkGetCoolingPresets(const AutomationSdkId deviceId,
													  AutomationSdkCoolingPreset *presets,
													  int maxSize,
													  int *size);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkActivateCoolingPreset(const AutomationSdkId deviceId,
														  const AutomationSdkId presetId);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkGetEqualizerDevices(AutomationSdkDevice *devices,
														int maxSize,
														int *size);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkGetEqualizerPresets(const AutomationSdkId deviceId,
														AutomationSdkEqualizerPreset *presets,
														int maxSize,
														int *size);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkActivateEqualizerPreset(const AutomationSdkId deviceId,
															const AutomationSdkId presetId);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkGetDpiDevices(AutomationSdkDevice *devices,
												  int maxSize,
												  int *size);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkGetDpiPresets(const AutomationSdkId deviceId,
												  AutomationSdkDpiPreset *presets,
												  int maxSize,
												  int *size);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkGetDpiStages(const AutomationSdkId deviceId,
												 AutomationSdkDpiStage *stages,
												 int maxSize,
												 int *size);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkActivateDpiPreset(const AutomationSdkId deviceId,
													  const AutomationSdkId presetId);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkActivateDpiStage(const AutomationSdkId deviceId,
													 AutomationSdkDpiStageIndex stageIndex);

ICUEAUTOMATIONSDK_EXPORT
AutomationSdkErrorCode AutomationSdkSetDpiValue(const AutomationSdkId deviceId, int value);

#ifdef __cplusplus
} //exten "C"
#endif
