# Mini Agent

A lightweight AI agent framework with tool execution, memory, and evaluation capabilities.

- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md) · Learning notes: [LEARNING_PATH.md](LEARNING_PATH.md)
- Learning notebooks: [`notebooks/`](notebooks/) — one per improvement, runnable with fakes (no API key)

## Features

- **LLM Integration**: Supports multiple LLM providers (MiniMax, OpenAI, OpenRouter)
- **Tool System**: Extensible tool registry with built-in tools
- **Memory**: SQLite-based persistent memory for sessions
- **Retrieval**: Semantic search over conversation history
- **Tracing**: Built-in tracing for debugging and evaluation

## Project Structure

```
mini_agent/
├── agent.py          # Main agent logic
├── gateway.py       # LLM communication layer
├── runtime.py       # Tool execution engine
├── session.py       # Session management
├── memory.py        # SQLite memory storage
├── retrieval.py     # Message retrieval & search
├── registry.py      # Tool registry
├── tracer.py       # Tracing/logging
├── config.py       # Configuration
├── main.py         # CLI entry point
├── run_eval.py     # Evaluation runner
├── llm/            # LLM adapters
│   ├── minimax.py
│   ├── openai.py
│   └── openrouter.py
├── tools/          # Built-in tools
│   ├── time.py
│   ├── calculator.py
│   ├── save_note.py
│   └── read_notes.py
└── eval/           # Evaluation framework
    ├── cases.py
    ├── runner.py
    └── case.py
```

## Architecture Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Input                                     │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Agent.run(user_input)                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Session.add_user_message(user_input)                             │   │
│  │ 2. Retriever.retrieve(session, query)                              │   │
│  │    ├── Memory.get_recent_messages()  ──► SQLite                    │   │
│  │    └── Memory.search_messages()      ──► SQLite                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Gateway.chat(messages, tools)                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ LLM.ask()  ──► MiniMax / OpenAI / OpenRouter                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
                                  │
                                  ▼
                         ┌───────────────┐
                         │ LLM Response  │
                         │ - content     │
                         │ - tool_calls  │
                         └───────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
            ┌───────────────┐           ┌───────────────┐
            │ No tool_calls │           │ Has tool_calls │
            │ (Final Answer)│           │ (Continue loop)│
            └───────────────┘           └───────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Runtime.execute(tool_call)                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Registry.get(tool_name)                                         │   │
│  │ 2. Validate arguments against tool schema                           │   │
│  │ 3. Tool.execute(arguments)                                         │   │
│  │ 4. Return {success, content}                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Session.add_tool_message(tool_call_id, tool_name, content)                │
│  └── Memory.add_message()  ──► SQLite                                     │
                                  │
                                  ▼
                         (Loop back to Gateway)
```

## Data Flow

```
User Input
    │
    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Session    │────►│   Memory     │◄────│  SQLite DB   │
│  (current    │     │  (retrieve)  │     │  (storage)   │
│   state)     │     └──────────────┘     └──────────────┘
└──────────────┘            │
        │                   ▼
        │            ┌──────────────┐
        │            │  Retriever   │
        │            │ (merge recent│
        │            │  + relevant) │
        │            └──────────────┘
        │                   │
        ▼                   ▼
┌──────────────────────────────────────────────┐
│           Messages to LLM                     │
│  [system, user, assistant, tool, ...]       │
└──────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────┐
│           LLM Response                        │
│  - content: "Hello"                          │
│  - tool_calls: [ToolCall(id, name, args)]    │
└──────────────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
   Final Answer          Tool Execution
                             │
                             ▼
                    ┌────────────────┐
                    │     Tool       │
                    │ - get_time     │
                    │ - calculator   │
                    │ - save_note    │
                    │ - read_notes   │
                    └────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │ Tool Result    │
                    │ (stored in     │
                    │  session)      │
                    └────────────────┘
```

## Installation

```bash
# Install dependencies
uv sync

# Or install in development mode
uv pip install -e .
```

## Configuration

Create a `.env` file:

```env
MINIMAX_API_KEY=your-api-key-here
MINI_MODEL=MiniMax-M2.5
```

## Usage

### CLI Mode

```bash
uv run mini-agent
```

### Evaluation Mode

```bash
uv run agent-eval
```

## Available Tools

| Tool | Description |
|------|-------------|
| `get_time` | Get current local time |
| `calculator` | Evaluate arithmetic expressions |
| `save_note` | Save information to long-term memory |
| `read_notes` | Search saved notes by keyword |

## Extending Tools

Create a new tool by subclassing `Tool`:

```python
from mini_agent.tool import Tool

class MyTool(Tool):
    @property
    def name(self):
        return "my_tool"

    @property
    def description(self):
        return "What my tool does"

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "arg1": {"type": "string", "description": "Description"}
            },
            "required": ["arg1"]
        }

    def execute(self, arguments):
        # Your logic here
        return result
```

## Adding New LLM Providers

Implement the `BaseLLM` interface:

```python
from mini_agent.llm.base import BaseLLM, LLMResponse, ToolCall

class MyLLM(BaseLLM):
    def ask(self, messages, tools=None):
        # Call your LLM
        return LLMResponse(
            content="response text",
            tool_calls=[ToolCall(id="...", name="...", arguments="{}")]
        )
```
