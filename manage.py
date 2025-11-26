from flask import Flask
from flask_migrate import Migrate
from app import app, db   # import app & db from your app.py

migrate = Migrate(app, db)

# Expose app to Flask CLI
@app.shell_context_processor
def make_shell_context():
    return {"db": db, "app": app}
