from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:

    route: str

    edge: object