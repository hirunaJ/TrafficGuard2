from main import db  # Import your Flask app's db instance

def reset_db():
    # Drop all tables
    db.drop_all()
    print("All tables have been dropped.")

    # Recreate all tables based on the models
    db.create_all()
    print("All tables have been recreated.")

if __name__ == '__main__':
    reset_db()
