#include <iostream>
#include <string>
#include <thread>
#include <future>
#include "nvapi.h"

// JSON library - you can use a different one if preferred
#include "nlohmann/json.hpp"

/*
 * This is a very simple C++ code to be used as an example for RISE Clients. Please check README for proper build & test. 
 */

// Constants and global variables
const size_t MAX_CONTENT_LENGTH = 4096;  // Maximum length for RISE requests

// Global promise pointers for synchronization
std::promise<void>* g_responsePromise = nullptr;  // Changed from prom_ptr for better naming
std::promise<void> g_riseReadyPromise;  // Changed from rise_ready for better naming

/**
 * @brief Callback function for RISE communications
 * 
 * This callback handles all responses from the RISE backend, including:
 * - Download progress updates
 * - Download confirmation requests
 * - RISE ready notifications
 * - Text and graph content responses
 * 
 * @param pData Pointer to callback data structure containing response information
 */
void RiseCompletionUpdate(NV_RISE_CALLBACK_DATA_V1* pData)
{
    // RISE is downloading dependencies, keep the user updated
    if (pData->contentType == NV_RISE_CONTENT_TYPE_PROGRESS_UPDATE)
    {
        std::cout << "Download progress update: " << pData->content << std::endl;
        return;
    }

    // RISE needs user confirmation to download, we send it right away in this sample app
    // If the user doesn't want to download, nothing is sent down to NVTOPPS.
    if (pData->contentType == NV_RISE_CONTENT_TYPE_DOWNLOAD_REQUEST)
    {
        NV_REQUEST_RISE_SETTINGS payload = { 0 };
        payload.version = NV_REQUEST_RISE_SETTINGS_VER1;
        payload.contentType = NV_RISE_CONTENT_TYPE_DOWNLOAD_REQUEST;
        payload.completed = NV_TRUE;

        auto status = NvAPI_RequestRise(&payload);
        if (status != NVAPI_OK)
        {
            return;
        } 
    }

    // That's the indication that RISE is ready to receive requests
    if (pData->contentType == NV_RISE_CONTENT_TYPE_READY)
    {
        g_riseReadyPromise.set_value();
        return;
    }

    if (pData->contentType == NV_RISE_CONTENT_TYPE_TEXT || pData->contentType == NV_RISE_CONTENT_TYPE_GRAPH)
    {
        // For this sample code, we just print whatever content we receive (as of today it can be text, graph data, or installation completion percentage)
        std::string contentUpdate = "";

        int i = 0;
        while (pData->content[i])
        {
            contentUpdate += pData->content[i];
            i++;
        }
        std::cout << contentUpdate;
    }

    // That's the indication that a user request is completed.
    if (pData->completed && pData->contentType == NV_RISE_CONTENT_TYPE_TEXT)
    {
        if(g_responsePromise)
            g_responsePromise->set_value();
        return;
    }
}

/**
 * @brief Initialize RISE and handle user interactions
 * 
 * @param argc Command line argument count
 * @param argv Command line arguments
 * @return int Exit status code
 */
int main(int argc, char* argv[])
{
    std::cout << "Starting RISE sample client" << std::endl;

    // Mandatory to use RISE
    auto status = NvAPI_Initialize();
    if (status != NVAPI_OK)
    {
        std::cout << "Error occurred while initializing NVAPI" << std::to_string(status) << std::endl;
        return EXIT_FAILURE;
    }

    // Configure and register RISE callback
    NV_RISE_CALLBACK_SETTINGS_V1 callbackSettings = { 0 };
    callbackSettings.version = NV_RISE_CALLBACK_SETTINGS_VER;
    callbackSettings.callback = RiseCompletionUpdate;

    // This register lets RISE know how to issue notifications back to the client, and also turns on the backend if it was not already.
    // After this call is successful, callback notifications are going to be triggered to indicate backend status (ready, installing, ...)
    status = NvAPI_RegisterRiseCallback(&callbackSettings);
    if (status != NVAPI_OK)
    {
        std::cout << "Error received: " << status << std::endl;
        std::cin.get();
        return EXIT_FAILURE;
    }

    // Wait for RISE to be ready
    g_riseReadyPromise.get_future().get();
    std::cout << "RISE is ready for queries" << std::endl;

    // Simple loop to let user ask for assistance, throttled by a promise
    //future set to prevent the user from requesting a new query when a previous one is still being processed.
    while (1)
    {
        std::promise<void> prom;
        g_responsePromise = &prom;
        std::future<void> responseFuture = prom.get_future();

        // Get user input
        std::string request;
        std::cout << "\nInsert your query (type 'exit' to quit): ";
        std::getline(std::cin, request);
        std::cout << std::endl;

        if (request == "exit") {
            break;
        }

        // Prepare and send request
        nlohmann::json requestJson;
        requestJson["prompt"] = request;
        std::string requestJsonStr = requestJson.dump();

        // Validate request length
        if (requestJsonStr.length() >= MAX_CONTENT_LENGTH) {
            std::cerr << "Error: Request too long (max " << MAX_CONTENT_LENGTH - 1 << " characters)" << std::endl;
            continue;
        }

        // Send request to RISE
        NV_REQUEST_RISE_SETTINGS payload = { 0 };
        payload.version = NV_REQUEST_RISE_SETTINGS_VER1;
        const char* req_cstr = requestJsonStr.c_str();
        strncpy_s(payload.content, requestJsonStr.c_str(), strlen(req_cstr) + 1);
        payload.contentType = NV_RISE_CONTENT_TYPE_TEXT;
        payload.completed = NV_TRUE;

        // Perform the call down to RISE.
        status = NvAPI_RequestRise(&payload);
        if (status != NVAPI_OK)
        {
            std::cout << "The request was not issued successfully: " << status << std::endl;
            return EXIT_FAILURE;
        }
        
        responseFuture.get();

        std::cout << std::endl;
    }

    return EXIT_SUCCESS;
}