import os
from app import app
from models import User, db
DEFAULT_USERS = [
    {
        "full_name": "System Administrator",
        "username": "admin",
        "email": "admin@pharmachain.local",
        "password": os.environ.get("PHARMACHAIN_ADMIN_PASSWORD", "ChangeMe-Admin"),
        "role": "ADMIN",
        "organization": "PharmaChain Administration",
    },
    {
        "full_name": "Manufacturer User",
        "username": "manufacturer",
        "email": "manufacturer@pharmachain.local",
        "password": os.environ.get("PHARMACHAIN_MANUFACTURER_PASSWORD", "ChangeMe-Manufacturer"),
        "role": "MANUFACTURER",
        "organization": "NovaCare Pharma",
    },
    {
        "full_name": "Distributor User",
        "username": "distributor",
        "email": "distributor@pharmachain.local",
        "password": os.environ.get("PHARMACHAIN_DISTRIBUTOR_PASSWORD", "ChangeMe-Distributor"),
        "role": "DISTRIBUTOR",
        "organization": "ABC Pharma Distributor",
    },
    {
        "full_name": "Retailer User",
        "username": "retailer",
        "email": "retailer@pharmachain.local",
        "password": os.environ.get("PHARMACHAIN_RETAILER_PASSWORD", "ChangeMe-Retailer"),
        "role": "RETAILER",
        "organization": "Community Pharmacy",
    },
    {
        "full_name": "Drug Regulator",
        "username": "regulator",
        "email": "regulator@pharmachain.local",
        "password": os.environ.get("PHARMACHAIN_REGULATOR_PASSWORD", "ChangeMe-Regulator"),
        "role": "REGULATOR",
        "organization": "Drug Regulatory Authority",
    },
    {
        "full_name": "Consumer User",
        "username": "consumer",
        "email": "consumer@pharmachain.local",
        "password": os.environ.get("PHARMACHAIN_CONSUMER_PASSWORD", "ChangeMe-Consumer"),
        "role": "CONSUMER",
        "organization": None,
    },
]


with app.app_context():
    db.create_all()

    for account in DEFAULT_USERS:
        existing_user = User.query.filter_by(
            username=account["username"],
        ).first()

        if existing_user:
            print(
                f"User already exists: "
                f"{account['username']}"
            )
            continue

        user = User(
            full_name=account["full_name"],
            username=account["username"],
            email=account["email"],
            role=account["role"],
            organization=account["organization"],
        )

        user.set_password(account["password"])

        db.session.add(user)

    db.session.commit()

    print("Default users created successfully.")