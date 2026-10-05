# Canonical models live in apps.api.models. This module re-exports them so
# both 'from models import X' and 'from apps.api.models import X' resolve
# to a single table definition (defining tables twice crashes SQLAlchemy).
from apps.api.models import *
from apps.api.database import Base, engine, AsyncSessionLocal
