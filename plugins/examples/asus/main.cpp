#include "AsusPlugin.h"

int main()
{
    HANDLE commandPipe = GetStdHandle(STD_INPUT_HANDLE);
    HANDLE responsePipe = GetStdHandle(STD_OUTPUT_HANDLE);

    if (commandPipe == INVALID_HANDLE_VALUE || commandPipe == NULL ||
        responsePipe == INVALID_HANDLE_VALUE || responsePipe == NULL)
    {
        return 0;
    }

    AsusPlugin plugin(commandPipe, responsePipe);

    return plugin.run();

}