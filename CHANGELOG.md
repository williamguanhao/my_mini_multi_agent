# Learning Changelog

Phase 1  ██████████   Refactor the existing Agent Loop
Phase 2  ░░░░░░░░░░   Make tracing first-class
Phase 3  ░░░░░░░░░░   Build the Graph Engine
Phase 4  ░░░░░░░░░░   Agent as Graph Node
Phase 5  ░░░░░░░░░░   Multi-Agent Runtime
Phase 6  ░░░░░░░░░░   Real Research Tools
Phase 7  ░░░░░░░░░░   Skills
Phase 8  ░░░░░░░░░░   Upgrade Memory + Eval
Phase 9  ░░░░░░░░░░   Integrate derivative pricing models
Phase 10 ░░░░░░░░░░   Build financial research & pricing agent


## Phase 1 — Refactor the existing Agent Loop

### Added
- refactore to agentloop
- adding agent state

                         User
                          │
                          ▼
                        Agent
                          │
                          ▼
                     AgentLoop
                          │
            ┌─────────────┼──────────────┐
            │             │              │
            ▼             ▼              ▼
        Retriever      Gateway        Runtime
            │             │              │
            ▼             ▼              ▼
         Session          LLM         Registry
            │                            │
            ▼                            ▼
          Memory                        Tool

### Learned

### Structural change

mini_agent/
├── agent.py.           <-New
├── agent_loop.py       <-New
├── agent_state.py      <-New
├── config.py
├── gateway.py
├── memory.py
├── session.py
├── retriever.py
├── runtime.py
├── registry.py  
├── tool.py       
├── main.py
├── run_eval.py        
├── tracer.py          
├── llm/
    ├── __init__.py
    ├── base.py
    ├── minimax.py
    ├── openai.py
    └── openrouter.py
├── eval/               
    ├── __init__.py     
    ├── case.py         
    ├── cases.py        
    └── runner.py       
└──  tools/           
    ├── __init__.py
    ├── time.py
    ├── calculator.py
    ├── save_note.py
    └── read_note.py

## Phase 2 — Make tracing first-class



## Phase 3 — Build the Graph Engine



## Phase 4 — Agent as Graph Node



## Phase 5 — Multi-Agent Runtime



## Phase 6 — Real Research Tools



## Phase 7 — Skills



## Phase 8 — Upgrade Memory + Eval



## Phase 9 — Integrate derivative pricing models



## Phase 9 — Build financial research & pricing agent



## Target

                         ┌───────────────┐
                         │    Gateway    │
                         └───────┬───────┘
                                 │
                                 ▼
                      ┌────────────────────┐
                      │    Agent Runtime   │
                      │                    │
                      │  Run / State /     │
                      │  Context / Trace   │
                      └─────────┬──────────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                │
               ▼                ▼                ▼
          Single Agent      Graph Agent      Multi-Agent
               │                │                │
               ▼                ▼                ▼
             Loop           Graph Engine     Agent Pool
               │                │                │
               └────────────────┼────────────────┘
                                │
                 ┌──────────────┼──────────────┐
                 │              │              │
                 ▼              ▼              ▼
               Tools         Memory         Skills
                 │              │              │
                 └──────────────┼──────────────┘
                                ▼
                              Trace
                                │
                                ▼
                              Eval

## Original

### Flow
                    User
                      │
                      ▼
                 Agent.run()
                      │
             ┌────────┴─────────┐
             │                  │
          Session            Retriever
             │                  │
             └────────┬─────────┘
                      ▼
                  Gateway
                      │
                      ▼
                     LLM
                      │
              ┌───────┴────────┐
              │                │
          final answer       tool call
                                 │
                                 ▼
                              Runtime
                                 │
                                 ▼
                              Registry
                                 │
                                 ▼
                               Tool
                                 │
                                 ▼
                          Tool result
                                 │
                                 └──────► LLM

### Original architecture

mini_agent/
├── agent.py
├── config.py
├── gateway.py
├── memory.py
├── session.py
├── retriever.py
├── runtime.py
├── registry.py        
├── main.py
├── run_eval.py        
├── tracer.py          
├── llm/
    ├── __init__.py
    ├── base.py
    ├── minimax.py
    ├── openai.py
    └── openrouter.py
├── eval/               
    ├── __init__.py     
    ├── case.py         
    ├── cases.py        
    └── runner.py       
└──  tools/           
    ├── __init__.py
    ├── time.py
    ├── calculator.py
    ├── save_note.py
    └── read_note.py

