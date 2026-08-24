from .node import Node
from .edge import Edge
from .state import GraphState
from .router import Router
from .exceptions import (
    InvalidRoute,
    NoRoute,
    MultipleRoutes,
)

class Graph:

    START = "__start__"
    END = "__end__"

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._routers: dict[str, Router] = {}

    # ---------------------------------------------------------
    # Nodes
    # ---------------------------------------------------------
     
    def add_node(
            self,
            name: str,
            node: Node
    ):
        if name in self.nodes:
            raise ValueError(
                f"Node already exists: {name}"
            )

        self.nodes[name] = node

        return self


    # ---------------------------------------------------------
    # Edges
    # ---------------------------------------------------------

    def add_edge(
            self,
            source: str,
            target: str,
            route: str | None = None,
            name: str | None=None,
            condition=None,
    ):
        self.edges.append(
            Edge(
                source=source,
                target=target,
                route=route,
                condition=condition,
                name=name,
            )
        )

        return self

    # ---------------------------------------------------------
    # Lookup
    # ---------------------------------------------------------
    
    def get_node(
            self,
            name: str,
    ):
        if name not in self.nodes:
            raise ValueError(
                f"Unknown node:{name}"
            )
        return self.nodes[name]

    # def get_next_nodes(
    #         self, 
    #         source: str, 
    #         state
    # ):
    #     return [
    #         edge.target
    #         for edge in self.edges
    #         if edge.source == source
    #         and edge.should_traverse(state)
    #     ]

    # def get_next_node(
    #         self,
    #         source: str,
    #         state,
    # ):
    #     candidates = self.get_next_nodes(
    #         source=source,
    #         state=state,
    #     )

    #     if len(candidates) == 0:

    #         raise RuntimeError(
    #             f"No valid edge from "
    #             f"'{source}'."
    #         )

    #     if len(candidates) > 1:

    #         raise RuntimeError(
    #             f"Multiple valid edges from "
    #             f"'{source}': {candidates}"
    #         )

    #     return candidates[0]

    def get_next_edge(
        self,
        source: str,
        state,
    ):
        
        # -----------------------------------------
        # Conditional router
        # -----------------------------------------

        if source in self._routers:

            router = self._routers[source]

            route_name = router.route(state)

            candidates = [
                edge
                for edge in self.edges
                if (
                    edge.source == source
                    and edge.name == route_name
                )
            ]

            if not candidates:
                raise InvalidRoute(
                    f"Router returned unknown route "
                    f"'{route_name}' from '{source}'."
                )

            if len(candidates) > 1:
                raise MultipleRoutes(
                    f"Multiple edges found for "
                    f"route '{route_name}'."
                )

            return candidates[0]

        # -----------------------------------------
        # Normal edges
        # -----------------------------------------

        candidates = [
            edge
            for edge in self.edges
            if (
                edge.source == source
                and edge.should_traverse(state)
            )
        ]

        if not candidates:
            raise NoRoute(
                f"No valid edge from '{source}'."
            )

        if len(candidates) > 1:
            raise MultipleRoutes(
                f"Multiple valid edges from "
                f"'{source}': "
                f"{[edge.target for edge in candidates]}"
            )

        return candidates[0]

    def get_next_node(
        self,
        source: str,
        state,
    ):

        edge = self.get_next_edge(
            source,
            state,
        )

        return edge.target

    def add_conditional_edges(
        self,
        source: str,
        router: Router,
        routes: dict[str, str],
    ):
        """
        Add state-dependent routing from a node.

        routes maps:

            route name → target node
        """

        for route_name, target in routes.items():

            self.add_edge(
                source=source,
                target=target,
                route=route_name,
                name=route_name,
            )

        self._routers[source] = router

        return self

    def select_route(
        self,
        source: str,
        state: GraphState,
    ):
        router = self._routers.get(source)

        if router is None:
            return None

        return router.route(state)