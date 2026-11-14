"""T02 comparator using one global Laplacian-variance threshold."""

from . import pipeline
from .common.context import RunContext


def run(ctx: RunContext) -> None:
    pipeline.run(ctx, baseline=True)
