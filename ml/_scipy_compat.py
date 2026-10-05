"""Work around a Windows Application Control block on one scipy file.

On some team machines the policy blocks scipy's `_bglu_dense` DLL, which only
the revised-simplex linear-programming solver needs. `scipy.optimize` imports
it unconditionally, so `scipy.stats` and `transformers` (which imports
`scipy.optimize` for an object-detection loss) fail to import, even though
this project never calls that solver.

`avoid_blocked_scipy_solver()` first tries the normal import and changes
nothing when it works. Only if it fails with this block does it register a
stand-in for that one solver module, so the rest of scipy.optimize loads. The
policy itself is not touched and the blocked file is never loaded. Call it
before importing transformers or scipy.stats.
"""
from __future__ import annotations

import sys
import types

_STUB = "scipy.optimize._linprog_rs"


def avoid_blocked_scipy_solver() -> bool:
    """Returns True if the stand-in was needed and installed."""
    try:
        import scipy.optimize  # noqa: F401
        return False
    except ImportError:
        for name in [m for m in sys.modules if m == "scipy.optimize" or m.startswith("scipy.optimize.")]:
            del sys.modules[name]
        stub = types.ModuleType(_STUB)

        def _linprog_rs(*args, **kwargs):
            raise NotImplementedError("scipy's revised-simplex solver is not loaded on this machine")

        stub._linprog_rs = _linprog_rs
        sys.modules[_STUB] = stub
        import scipy.optimize  # noqa: F401
        return True
