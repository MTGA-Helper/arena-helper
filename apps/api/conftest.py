# -*- coding: utf-8 -*-
"""
Pytest import setup for apps/api tests.

models.py uses the flat import ``from database import Base``. In the
production runtime that resolves to THIS directory's database.py, because
the API is launched as a script from apps/api (the script's directory is
sys.path[0]). The repo contains three different database.py files (repo
root, user-portal/, apps/api/), and pytest puts the repo root first, so
under pytest the flat import would otherwise bind the repo-root module —
whose import-time engine setup expects a live Postgres configuration.

To reproduce production resolution deterministically, this conftest
pre-binds the module name "database" to this directory's database.py
before any test module imports models. The repo root stays importable so
``apps.api.*`` package imports keep working.
"""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

if "database" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "database", os.path.join(_HERE, "database.py")
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["database"] = _module
    _spec.loader.exec_module(_module)
