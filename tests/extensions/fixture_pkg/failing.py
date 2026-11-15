"""An extension whose setup raises."""


async def setup(bot: object) -> None:
    """Raise, so loading fails."""
    msg = "boom"
    raise RuntimeError(msg)
