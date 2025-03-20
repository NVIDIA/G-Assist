Quickstart (See below)
Architecture block diagram – mermaid ? markdown friendly
APIs how to access service 
C++ RISE APIs register, request
What do I need, how they work
To help , we’ve created a python binding (no node binding)
Example to show how to talk to service (Ron has with RISE chat gui or python gui)
Jordi’s C++ sample app (clean it up)
extending system assistant (Plugins)
Technical details
Needs to be catered to users who just want to start
Format for plugin
Communication pipe - what goes in, what goes out
Point to hello world plugin 
How to address plugins
Manifest
Language (zero-shot fn calling) - manifest
Plugin name
LLm picks best function based on query 
First plugin example
Gemini Python Plugin
How to write the initialize function
Explore more - point to other plugins 


Everything in the same repo
Plugins 
Examples
Templates
Plugin Builder
Purpose of experimental 
Please review the files 
Know how to read code , know structure of plugin
Bindings 

Quickstart
Rely on single one
Get python binding
Pip install …
Do not involve GPT builder (too advanced)
Hello world plugin (2-3 functions)
Hello vs goodbye functions
A plugin that rise core cannot answer 
Extend custom functionality 
