"""Random selection helpers used by the spider."""

import logging
import random
from typing import List, Optional, Sequence, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


class RandomSelector:
    """Encapsulates every random decision made during a crawl.  """

    def __init__(self, seed: Optional[int] = None) -> None:
        """Create a selector. """
        self._rng = random.Random(seed)

    def pick_count(self, minimum: int, maximum: int, available: int) -> int:
        """Pick a random number between minimum and maximum."""
        upper = min(maximum, available)
        lower = min(minimum, upper)
        return self._rng.randint(lower, upper)

    def sample(self, items: Sequence[T], count: int) -> List[T]:
        
        """Randomly select ``count`` unique items without replacement."""

        if count >= len(items):
            if count > len(items):
                logger.warning(
                    "Requested %d items but only %d available; returning all.",
                    count,
                    len(items),
                )
            return list(items)
        return self._rng.sample(list(items), count)