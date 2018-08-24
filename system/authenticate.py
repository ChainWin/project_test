from flask import Blueprint, url_for, redirect, session
from functools import wraps

authenticate_url = 'http://127.0.0.1:9090/'

'''  
class authenticate(object):
    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):          
        if 'username' not in session:
            return redirect(url_for(authenticate_url))
        return self.func(*args, **kwargs)
'''

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        from  Login.login import login_bp
        if 'username' not in session:
            return redirect(url_for('login.index'))
        return func(*args, **kwargs)
    return wrapper


#from  Login.login import login_bp
