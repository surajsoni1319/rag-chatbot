from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_limiter import Limiter  # ✅ BUG #12 FIX
from flask_limiter.util import get_remote_address  # ✅ BUG #12 FIX
from flask_wtf.csrf import CSRFProtect  # ✅ BUG #14 FIX

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "login"
migrate = Migrate()
csrf = CSRFProtect()  # ✅ BUG #14 FIX: CSRF protection instance

# ✅ BUG #12 FIX: Rate limiter to prevent spam/DoS attacks
limiter = Limiter(
    key_func=get_remote_address,  # Rate limit by IP address
    default_limits=["200 per day", "50 per hour"],  # Global limits
    storage_uri="memory://",  # Use in-memory storage (upgrade to Redis for production)
    strategy="fixed-window"  # Simple fixed time window
)