# Super Browser Runtime

The browser-provider dependency graph comes from the committed, hash-verified
`requirements-runtime.lock`. Its three direct packages are pinned to the
versions used by the operator:

- `playwright==1.60.0`
- `browserbase==1.13.0`
- `browser-use-sdk==3.8.4`

Super Browser's bounded JSON-RPC server is implemented in its own source and
does not import a second MCP SDK. The image installs Playwright Chromium during
the build. Super Browser source is loaded from `/opt/super-browser/src` through
`PYTHONPATH`, matching the live MCP launch pattern. Change package versions only
through a reviewed lock regeneration and image rebuild; do not install
replacements inside a running operator.
