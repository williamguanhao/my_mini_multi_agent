class GraphError(Exception):
    """Base graph execution error."""


class GraphExecutionLimit(GraphError):
    """Graph exceeded the configured step limit."""


class InvalidRoute(GraphError):
    """Router selected a route that does not exist."""


class NoRoute(GraphError):
    """No valid route could be selected."""


class MultipleRoutes(GraphError):
    """Multiple routes were selected when exactly one was required."""