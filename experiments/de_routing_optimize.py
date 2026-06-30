from __future__ import annotations

"""Legacy compatibility wrapper for the archived DE routing search.

DE is not used in the RAIR-RAG main experiments. This wrapper exists only so
older commands that referenced `experiments.de_routing_optimize` still resolve.
"""

from experiments.archived.de_routing_optimize import main


if __name__ == "__main__":
    main()
