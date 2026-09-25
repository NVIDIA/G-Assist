# Third-party notices

The skill files in `skills/g-assist-mcp-skill/` (`SKILL.md`, `BENCHMARK.md`, and `evals/`) are NVIDIA-authored. This contribution does not copy third-party source into the repository and does not redistribute a third-party package.

## Separate-process dependency, not distributed

`plugins/examples/mcp-stdio-example/plugin.py` can launch `@modelcontextprotocol/server-filesystem` as a child process (`npx`). The package is not vendored here. Users install it themselves.

- Package: `@modelcontextprotocol/server-filesystem`
- Upstream: https://github.com/modelcontextprotocol/servers
- License file: https://github.com/modelcontextprotocol/servers/blob/main/LICENSE
- npm records the license as `SEE LICENSE IN LICENSE`. That upstream file describes a relicensing transition: new code and specification contributions are Apache-2.0, documentation excluding specifications is CC-BY-4.0, and contributions not yet relicensed remain MIT.

## Previously reviewed components

Other open-source components already in this repository were reviewed under OSRB 5262154 and 5044593. This skill contribution does not modify or redistribute them.
