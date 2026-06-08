# 🤖 AI Agent Integration Guide

`allegro-cli` is designed to be easily integrated into any LLM-based agent (GPT-4, Claude, etc.) that supports tool calling (function calling).

## 🛠 Integration Strategy

Since `allegro-cli` is a command-line tool with a structured JSON output, the integration is straightforward:

1. **Tool Definition**: Provide the agent with the function signatures defined in `agent_specs/tools.json`.
2. **Execution**: When the agent calls a tool, map the function call to a shell command.
3. **Response**: Execute the command with `--format json --compact` and feed the JSON output back to the agent.

### Example Mapping

| Tool Call | Shell Command |
|----------|---------------|
| `allegro_search(query="laptop", smart=True)` | `allegro search "laptop" --smart --format json --compact` |
| `allegro_offer_details(offer_id="123")` | `allegro offer 123 --format json --compact` |
| `allegro_track_packages()` | `allegro packages --format json --compact` |

## 🌟 Advanced: MCP (Model Context Protocol)

For users of the Model Context Protocol (MCP), this tool can be wrapped in a simple MCP server. 

**Suggested Implementation:**
- Use the `@modelcontextprotocol/sdk`.
- Implement the `list_tools` handler using the definitions in `tools.json`.
- Implement the `call_tool` handler using `child_process.exec` to run the CLI commands.

## ⚠️ Important Notes for Developers

- **Authentication**: Ensure the environment where the agent runs has the `allegro` config initialized (via `allegro login`).
- **Token Efficiency**: Always use `--compact` to prevent the agent's context window from being flooded with redundant metadata.
- **Error Handling**: The CLI returns non-zero exit codes and JSON-formatted error messages when something goes wrong (e.g., `AuthenticationException`). Ensure your integration captures `stderr` and returns it to the agent for self-correction.
