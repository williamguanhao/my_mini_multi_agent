# Architecture Decisions

## Why doing this?
Following waku agent. This project is a step by step agent builder that helps understand each layer of agent harness. Later will explore loop and graphic ai agent design.
https://github.com/ShenSeanChen/waku-agent/tree/main/waku

## LLM Providers

We use MiniMax through its OpenAI-compatible API.

Reason:
- Familiar OpenAI SDK interface
- Still in the discription
- Keeps the LLM layer provider-independent
- Allows us to focus on agent architecture
---

## Agent Loop

The agent loop is responsible for:

1. Send messages to LLM
2. Inspect response
3. Detect tool calls
4. Execute tools
5. Append tool results
6. Call LLM again
7. Return final answer

---

## Tool Architecture

Tools are represented by a Tool object containing:

- name
- description
- parameters
- function

ToolRegistry maps tool names to Tool objects.

---

## Learning Strategy

We intentionally implement the mechanism manually before
introducing abstractions.

This allows us to understand what the framework abstractions
are hiding.

## Finance research

## Finance derivative pricing