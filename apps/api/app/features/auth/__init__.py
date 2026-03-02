"""Auth feature module."""

__all__ = ["router"]


def __getattr__(name: str):
	if name == "router":
		from .router import router

		return router
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
