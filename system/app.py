# coding: utf-8

import os
import datetime
from flask import Flask
from Project.project import project_bp
from Task.tartask import task_bp
from Login.login import login_bp


app = Flask(__name__)
app.config['SECRET_KEY'] = 'you will never guess'
app.register_blueprint(login_bp)
app.register_blueprint(project_bp)
app.register_blueprint(task_bp)


if __name__=="__main__":
    app.run()

