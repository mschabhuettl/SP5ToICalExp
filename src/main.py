import os
import sys  # Import sys module
import webbrowser
from threading import Timer
from flask import Flask
from app.views import bp as views_bp

# Constants
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}


def create_app():
    # Create upload folder if it doesn't exist
    upload_path = os.path.join(os.getcwd(), UPLOAD_FOLDER)
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)

    # Determine the template folder
    if getattr(sys, 'frozen', False):  # Check if the app is running as a bundled EXE
        template_folder = os.path.join(sys._MEIPASS, 'templates')
        app = Flask(__name__, template_folder=template_folder)
    else:
        app = Flask(__name__, template_folder='app/templates')

    # Set the secret key
    app.secret_key = os.urandom(24)

    # Configure app
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS

    # Register blueprints
    app.register_blueprint(views_bp)

    return app


# Function to open the web browser
def open_browser():
    webbrowser.open_new('http://127.0.0.1:5000/')


if __name__ == '__main__':
    app = create_app()

    # Open web browser 1 second after Flask server starts
    Timer(1, open_browser).start()

    # Run Flask app with debug set to False for production
    app.run(debug=False)
