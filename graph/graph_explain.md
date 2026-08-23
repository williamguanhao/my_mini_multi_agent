# Graph Design — Zero-to-Hero Walkthrough

## 0. The problem this solves

Imagine an agent that has to make decisions. Sometimes it should call a tool, sometimes it should ask the user, sometimes it should just answer. That's a **control-flow problem**: depending on what just happened, decide what to do next.

The simplest way to write this is a loop with `if/else`. That works for 3 branches. It gets ugly at 10. It becomes spaghetti at 30.

A **graph** is a different way to write the same thing — instead of `if/else` you draw a picture: each piece of work is a **box**, each possible transition is an **arrow**, and a small **decision-maker** picks which arrow to follow based on what just happened. The picture IS the program.

```
       ┌────────┐         ┌─────────┐
       │ think  │ ──────► │   act   │
       └────────┘         └─────────┘
            │                   │
            │ "I'm done"        │ result
            ▼                   ▼
         __end__           ┌──────────┐
                            │ observe  │
                            └──────────┘
```

That's it. The `graph/` folder is the engine that runs that picture.

---

## 1. The five pieces, in plain English

```
graph/
├── node.py       Node           ← a box of work
├── edge.py       Edge           ← an arrow between two boxes
├── state.py      GraphState     ← the shared notebook everyone reads/writes
├── router.py     Router         ← the decision-maker that picks an arrow
└── graph.py      Graph          ← the picture itself (boxes + arrows + router)
executor.py                      ← the runner that drives the picture
```

### 1.1 `Node` — a box of work (`node.py`)

```python
class Node(ABC):
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def execute(self, state) -> GraphState:
        ...
```

A node is just a thing with a `name` and an `execute()` method. The contract:

> "Given the shared notebook (`state`), do your work, write your results back into it, and hand the notebook back."

You write your own concrete nodes by subclassing:

```python
class ThinkNode(Node):
    def execute(self, state):
        # ask the LLM, write decision into state, return state
        ...

class ActNode(Node):
    def execute(self, state):
        # read decision from state, run the tool, write result into state
        ...
```

A node **never decides where to go next**. It only does work. Where-to-go-next is a separate concern.

---

### 1.2 `Edge` — an arrow between two boxes (`edge.py`)

```python
@dataclass
class Edge:
    source: str                # which node this arrow leaves from
    target: str                # which node this arrow goes to
    route:  str | None = None  # a tag identifying this arrow
    name:   str | None = None  # human-readable label
    condition: Callable | None = None   # optional gate: only follow if True
```

An edge has four fields, but only two matter at the start:
- `source` — which node the arrow leaves from
- `target` — which node it goes to

The other two are refinements:
- `route` is a tag (`"tool"`, `"end"`, `"retry"`) — used by routers (next section) to identify this specific arrow
- `condition` is a function `state → bool` — if you set it, the arrow is only followed when it returns True. If you don't, the arrow is always followed.

`should_traverse(state)` returns whether the gate is open.

---

### 1.3 `GraphState` — the shared notebook (`state.py`)

```python
@dataclass
class GraphState:
    values: dict[str, Any]    # <-- this is the notebook
    current_node: str | None
    step: int = 0
    finished: bool = False
    error: Exception | None = None
```

Every node reads and writes the same `state.values` dict. That's how nodes communicate — they don't call each other, they don't pass arguments. They all share the notebook.

Think of it like a **whiteboard** in a meeting room: anyone can read it, anyone can write on it, and at any moment it shows the current state of the conversation.

There's also bookkeeping fields:
- `current_node` — who's turn it is (set by the executor)
- `step` — how many node runs have happened
- `finished` — whether the run is done
- `error` — set if a node raised

`state.get(key, default)` and `state.set(key, value)` are conveniences for `state.values`.

---

### 1.4 `Router` — the decision-maker (`router.py`)

```python
class Router(ABC):
    @abstractmethod
    def route(self, state) -> str: ...

class FunctionRouter(Router):
    def __init__(self, function):
        self.function = function
    def route(self, state):
        return self.function(state)
```

A router is **just a function from state to a string** (a "route name"). It answers one question:

> "Given the current notebook, which arrow should I take?"

The most useful concrete implementation is `FunctionRouter`, which wraps any `lambda state: "some_string"` you give it.

```python
FunctionRouter(lambda state: "tool" if state.get("decision") == "tool" else "end")
```

That single line says: "if the notebook says `decision == tool`, the route-name is `tool`; otherwise the route-name is `end`."

There are also two dataclass siblings — `Route` and the abstract `Router` — but for now you only need `FunctionRouter`.

---

### 1.5 `Graph` — the picture itself (`graph.py`)

The `Graph` is just a container that holds three things:

```python
class Graph:
    START = "__start__"     # sentinel: where every run begins
    END   = "__end__"       # sentinel: where every run finishes

    def __init__(self):
        self.nodes:    dict[str, Node] = {}     # name → box
        self.edges:    list[Edge]      = []     # arrows
        self._routers: dict[str, Router] = {}   # source → decision-maker
```

Two **sentinels** are special strings that aren't real nodes:
- `__start__` — where the run begins (handled implicitly by the executor)
- `__end__` — where the run stops (the executor checks for it each loop)

You **never register** START or END as nodes. They're magic strings the executor recognizes.

---

## 2. Building a graph (the construction API)

There are three operations: **add a node**, **add an arrow**, or **add a conditional bundle**.

### 2.1 `add_node(name, node)` — drop a box on the canvas

```python
graph.add_node("think", ThinkNode())
graph.add_node("act",   ActNode(tools))
```

The `name` is just a label. The `node` is whatever object has an `execute(state)` method.

### 2.2 `add_edge(source, target, route, name=None, condition=None)` — draw an arrow

```python
graph.add_edge("think", "act", route="tool")
```

That says: "draw an arrow from `think` to `act`. Tag it with route-name `tool`."

In the current code, `route` is **required**. The signature is:

```python
def add_edge(self, source, target, route, name=None, condition=None):
```

If you want a "skip-the-decision, always go here" arrow (like `START → think`), you still have to provide a `route`:

```python
graph.add_edge(Graph.START, "think", route="entry")
```

### 2.3 `add_conditional_edges(source, router, routes)` — bundle several arrows under a router

This is sugar. It says:

> "I'm leaving `source` and I don't know yet which arrow to take. Use this router to decide. Here are the candidate arrows, each tagged with a different route-name."

```python
graph.add_conditional_edges(
    "agent",                                  # leaving node
    FunctionRouter(lambda s: "tool"),         # decision-maker
    {                                         # route-name → target
        "tool": "tool_node",
        "end":  Graph.END,
    },
)
```

Internally it does three things:
1. For each `(route_name, target)` in the dict, calls `add_edge(source, target, route=route_name, name=route_name)` — drawing all the candidate arrows.
2. Registers the router: `self._routers[source] = router`.

After that, every time the executor is about to leave `"agent"`, it asks the router "which route?" and follows that arrow.

---

## 3. Running the graph (the executor)

`GraphExecutor.run(graph, state, run_id, max_steps=100)` is the engine. The loop is small enough to read:

```python
current_node = Graph.START
for _ in range(max_steps):

    # 1. Which arrow do I take from here?
    edge = graph.get_next_edge(current_node, state)
    next_node = edge.target

    # 2. If it points at END, stop.
    if next_node == Graph.END:
        state.finished = True
        return state

    # 3. Otherwise, run the node.
    node = graph.get_node(next_node)
    state = node.execute(state)

    # 4. Move forward.
    current_node = next_node
```

The interesting call is **`get_next_edge`**. Here's what it does:

```python
def get_next_edge(self, source, state):
    router = self._routers[source]              # ask the registered decision-maker
    route_name = router.route(state)            #   "which arrow?" → "tool"

    candidates = [
        e for e in self.edges
        if e.source == source
        and e.route == route_name               # pick the arrow tagged with that name
    ]
    assert len(candidates) == 1, "0 or >1 match"
    return candidates[0]
```

If `source` has **no** router registered, `self._routers[source]` raises `KeyError`. That means: if a node has more than one outgoing arrow, you must have called `add_conditional_edges` for it.

---

## 4. Why this design? Three reasons

1. **You can read the program as a picture.** Adding a new branch is "draw a new arrow"; deleting a branch is "erase an arrow." No code surgery in a giant loop.

2. **Decision logic is isolated.** The router is one tiny function. Test it independently. Swap `FunctionRouter` for an LLM-backed router later without touching any node.

3. **The same graph can be observed from outside.** Every node start/end and every edge traversal publishes an event (`_node_started`, `_edge_traversed`, etc.). That's why the executor takes `event_bus` and `event_factory` — it's how the existing trace system plugs into the graph without the graph knowing about it.

---

## 5. A full worked example (the conditional routing test)

```python
from graph.node import Node
from graph.graph import Graph
from graph.router import FunctionRouter
from graph.state import GraphState


class DummyNode(Node):
    def execute(self, state):
        pass


graph = Graph()
graph.add_node("agent", DummyNode("agent"))      # box A
graph.add_node("tool",  DummyNode("tool"))       # box B

graph.add_conditional_edges(
    "agent",                                     # leaving A
    FunctionRouter(lambda state: "tool"),        # router always says "tool"
    {"tool": "tool", "end": Graph.END},          # two candidate arrows
)

# Run the query
edge = graph.get_next_edge("agent", GraphState())

assert edge.target == "tool"      # the picked arrow points at "tool"
assert edge.name   == "tool"      # and is tagged "tool"
```

### What happens, step by step

1. **Build**: graph has 2 boxes, 2 arrows, 1 router.
   - `nodes = {"agent": ..., "tool": ...}`
   - `edges = [Edge("agent","tool","tool","tool"), Edge("agent","__end__","end","end")]`
   - `_routers = {"agent": FunctionRouter(lambda s: "tool")}`

2. **Query**: `get_next_edge("agent", GraphState())`.
   - Looks up `self._routers["agent"]` → the router.
   - Calls `router.route(state)` → runs `lambda state: "tool"` → returns `"tool"`.
   - Filters edges where `source == "agent"` AND `route == "tool"` → exactly one match.
   - Returns that edge: `Edge("agent", "tool", route="tool", name="tool")`.

3. **Assertions**:
   - `edge.target == "tool"` ✓
   - `edge.name == "tool"` ✓

---

## 6. Quick reference — when to use what

| You want to… | Use |
|---|---|
| Drop a box on the canvas | `graph.add_node(name, node_instance)` |
| Always go A → B | `graph.add_edge(A, B, route="some_name")` |
| Go A → B only if `state` says so | `graph.add_edge(A, B, route="some_name", condition=lambda s: ...)` |
| Pick among A→B / A→C / A→END based on state | `graph.add_conditional_edges(A, Router(...), {"b": B, "c": C, "end": END})` |
| Run the whole picture | `GraphExecutor().run(graph, state, run_id="...")` |

That's the whole design. Five small files, one mental model.
