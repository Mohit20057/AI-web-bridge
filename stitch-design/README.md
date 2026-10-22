# Stitch Design Companion

This is a separate companion to AI Web Bridge for creating and implementing UI
designs with Google Stitch. It uses Google's Stitch MCP service with a Stitch
API key; it does not use the signed-in browser profiles or provider adapters
from AI Web Bridge.

## Setup

Set `STITCH_API_KEY` in your shell, or create a private `.env` file in this
folder with that setting. Do not commit the key. The Stitch client also accepts
an API key directly when needed.

The reusable workflow is in `SKILL.md`. The `scripts` folder contains the
client and asset downloader, and `references` contains the design prompt
template. Generated designs are saved into the project you are working on.

Google lists Stitch as a beta MCP service. Its availability, tools, and
authentication requirements can change; consult the [Google Cloud MCP service
catalog](https://docs.cloud.google.com/mcp/supported-products) before setup.
