"""Reproduces the 'Unknown node: __end__' bug in graph/executor.py.

A node whose outgoing edge resolves to Graph.END should terminate the run,
not be looked up as a real node.

Loads modules via importlib to bypass the empty graph/__init__.py and
the fact that executor.py does `from state import GraphState` (which only
works when state/ is a top-level package on sys.path).
"""

import importlib.util
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
GRAPH_DIR = ROOT / "graph"


def _ensure_package():
    if "graph_pkg" not in sys.modules:
        pkg = types.ModuleType("graph_pkg")
        pkg.__path__ = [str(GRAPH_DIR)]
        sys.modules["graph_pkg"] = pkg


def _load(mod_name: str, file_name: str):
    _ensure_package()
    full_name = f"graph_pkg.{mod_name}"
    spec = importlib.util.spec_from_file_location(
        full_name, str(GRAPH_DIR / file_name)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    setattr(sys.modules["graph_pkg"], mod_name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def graph_pkg():
    """Load graph modules once per test module via importlib."""
    state = _load("state", "state.py")
    edge = _load("edge", "edge.py")
    node = _load("node", "node.py")
    graph_mod = _load("graph", "graph.py")

    # executor.py does `from graph import Graph` and `from state import GraphState`.
    sys.modules["graph"] = graph_mod
    sys.modules["state"] = state

    executor = _load("executor", "executor.py")

    return {
        "Graph": graph_mod.Graph,
        "GraphExecutor": executor.GraphExecutor,
        "GraphState": state.GraphState,
        "Node": node.Node,
    }


def _make_identity_node_class(Node):
    class IdentityNode(Node):
        def __init__(self, name):
            self.name = name

        def execute(self, state):
            return state

    return IdentityNode


def test_edge_to_end_terminates_without_lookup_error(graph_pkg):
    IdentityNode = _make_identity_node_class(graph_pkg["Node"])

    g = graph_pkg["Graph"]()
    g.add_node("only", IdentityNode("only"))
    g.add_edge(g.START, "only")
    g.add_edge("only", g.END)

    executor = graph_pkg["GraphExecutor"]()
    final = executor.run(g, run_id="test-run-end")

    assert final.finished is True
    assert final.current_node == g.END


def test_two_node_chain_ending_at_end_terminates(graph_pkg):
    IdentityNode = _make_identity_node_class(graph_pkg["Node"])

    g = graph_pkg["Graph"]()
    g.add_node("a", IdentityNode("a"))
    g.add_node("b", IdentityNode("b"))
    g.add_edge(g.START, "a")
    g.add_edge("a", "b")
    g.add_edge("b", g.END)

    executor = graph_pkg["GraphExecutor"]()
    final = executor.run(g, run_id="test-run-chain")

    assert final.finished is True
    assert final.current_node == g.END
    assert final.step == 2
