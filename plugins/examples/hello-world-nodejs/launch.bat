@echo off
:: Launch wrapper for Node.js G-Assist plugin
:: This allows the engine to launch the plugin without needing native Node.js support

node "%~dp0plugin.js"

