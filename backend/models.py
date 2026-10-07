from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timezone


db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
        index=True,
    )
    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    organization = db.Column(db.String(150), nullable=True)
    is_active_account = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self) -> bool:
        return self.is_active_account

    def has_role(self, *roles: str) -> bool:
        return self.role in roles

class ScanLog(db.Model):
    __tablename__ = "scan_logs"

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=True)
    region = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)

    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    risk_score = db.Column(
     db.Integer,
     nullable=False,
     default=0,
    )
    risk_level = db.Column(
        db.String(20),
        nullable=True,
    )

    alert = db.Column(
        db.Text,
    )

    explanation = db.Column(
        db.Text,
        nullable=True,
    )

    recommendation = db.Column(
        db.Text,
        nullable=True,
    )
    alert = db.Column(
        db.String(255),
        nullable=True,
    )
    

    drug_id = db.Column(
        db.String(50),
        nullable=False,
        index=True,
    )

    qr_hash = db.Column(
        db.Text,
        nullable=False,
    )

    result = db.Column(
        db.String(30),
        nullable=False,
        index=True,
    )

    message = db.Column(
        db.String(255),
        nullable=True,
    )

    scan_time = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    ip_address = db.Column(
        db.String(100),
        nullable=True,
    )

    forwarded_ip = db.Column(
        db.String(100),
        nullable=True,
    )

    user_agent = db.Column(
        db.Text,
        nullable=True,
    )

    device = db.Column(
        db.String(100),
        nullable=True,
    )

    browser = db.Column(
        db.String(100),
        nullable=True,
    )

    operating_system = db.Column(
        db.String(100),
        nullable=True,
    )

    city = db.Column(
        db.String(100),
        nullable=True,
    )

    region = db.Column(
        db.String(100),
        nullable=True,
    )

    country = db.Column(
        db.String(100),
        nullable=True,
    )

    latitude = db.Column(
        db.Float,
        nullable=True,
    )

    longitude = db.Column(
        db.Float,
        nullable=True,
    )