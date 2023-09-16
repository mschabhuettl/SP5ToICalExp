from flask import Flask
import os


def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY='your-secret-key',
        UPLOAD_FOLDER=os.path.join(app.instance_path, 'uploads'),
        ALLOWED_EXTENSIONS=set(['pdf'])
    )

    from . import views
    app.register_blueprint(views.bp)

    return app
