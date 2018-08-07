# coding: utf-8

import os
import datetime
from flask import Flask, render_template
from Project.project import project_bp
from Task.tartask import task_bp
from Login.login import login_bp


app = Flask(__name__)
app.config['SECRET_KEY'] = 'you will never guess'
app.register_blueprint(login_bp)
app.register_blueprint(project_bp)
app.register_blueprint(task_bp)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html')

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html')

if __name__=="__main__":
    app.run()

