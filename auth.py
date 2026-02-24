from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from models import User
from extensions import db
import re  # ✅ BUG #13 FIX: Added for password validation


# ✅ BUG #13 FIX: Password strength validation function
def validate_password(password):
    """
    Validates password strength against security rules.
    Returns: (is_valid: bool, errors: list)
    
    Rules:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 number
    - At least 1 special character
    """
    errors = []

    if len(password) < 8:
        errors.append("At least 8 characters long")

    if not re.search(r'[A-Z]', password):
        errors.append("At least 1 uppercase letter (A-Z)")

    if not re.search(r'[a-z]', password):
        errors.append("At least 1 lowercase letter (a-z)")

    if not re.search(r'\d', password):
        errors.append("At least 1 number (0-9)")

    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-\[\]\/\\]', password):
        errors.append("At least 1 special character (!@#$%^&*)")

    return len(errors) == 0, errors


def register_auth_routes(app):

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")

            user = User.query.filter_by(email=email).first()

            if user and check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for("home"))
            else:
                flash("Invalid email or password", "error")

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    # ✅ BUG #13 FIX: API endpoint to validate password strength in real-time
    @app.route("/validate-password", methods=["POST"])
    def validate_password_api():
        """
        Real-time password validation for frontend strength indicator.
        Returns password strength and list of failed requirements.
        """
        data = request.get_json()
        password = data.get("password", "")

        is_valid, errors = validate_password(password)

        # Calculate strength score (0-4)
        checks = {
            "length": len(password) >= 8,
            "uppercase": bool(re.search(r'[A-Z]', password)),
            "lowercase": bool(re.search(r'[a-z]', password)),
            "number": bool(re.search(r'\d', password)),
            "special": bool(re.search(r'[!@#$%^&*(),.?":{}|<>_\-\[\]\/\\]', password))
        }

        score = sum(checks.values())

        if score <= 2:
            strength = "weak"
        elif score == 3:
            strength = "fair"
        elif score == 4:
            strength = "good"
        else:
            strength = "strong"

        return jsonify({
            "is_valid": is_valid,
            "strength": strength,
            "score": score,
            "checks": checks,
            "errors": errors
        })