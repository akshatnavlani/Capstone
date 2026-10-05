"""Let the model-side tests import transformers on machines where Application
Control blocks one unused scipy file (see ml/_scipy_compat.py)."""
from ml._scipy_compat import avoid_blocked_scipy_solver

avoid_blocked_scipy_solver()
