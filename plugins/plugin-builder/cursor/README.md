# Cursor Guide for G-Assist Plugin Builders

Place `.cursorrules` files from this directory into your Cursor workspace when you want the IDE to walk you through creating a new plugin that follows NVIDIA’s latest conventions.

## How to use

1. Copy `plugins/plugin-builder/cursor/.cursorrules` into the root of your Cursor workspace (or symlink it). Cursor reads it automatically.
2. Open the `plugin-builder` folder in Cursor. The rules prompt Cursor to:
   - Interview you about the plugin’s name, purpose, APIs, functions, onboarding, passthrough, and persistence.
   - Clone the canonical template from `ssh://git@gitlab-master.nvidia.com:12051/rise/g-assist-plugins-page.git` (`plugins/templates/python`) and duplicate it into `plugins/examples/<plugin_name>`.
   - Update `plugin.py`, `manifest.json`, `config.json`, README, and generate a plugin-specific `.cursorrules`.
   - Remind you to run `setup_and_build.bat` and validate JSON.
3. Follow the prompts Cursor provides—each step includes ready-to-run commands so you can copy/paste into a terminal.

## Why keep the rules here?

This folder acts as the authoritative source for Cursor automation. When the template evolves, update the `.cursorrules` and README here so every developer gets the same guided workflow without scattering duplicate files around the repo.

