from flask import Blueprint, url_for, redirect, render_template, request, session
from model import db

login_bp = Blueprint(
    'login',
    __name__,
    template_folder='templates',
    static_folder='static')


# 登陆界面
@login_bp.route('/',methods=['GET',])
def index():
    if 'username' in session:
        # 返回的模板中可以重定向至‘/<username>’,内容为该用户项目列表
        return redirect(url_for('.project_list', username=session['username']))
    else:
        session.clear()
        return redirect(url_for('.to_login'))
# OIDC返回后进行验证
@login_bp.route('/login',methods=['GET',])
def to_login():
    return render_template('login.html')   


@login_bp.route('/login',methods=['POST',])
def login():
    #login the user
    session['username'] = request.form['name']
    return redirect(url_for('.index'))      
  

@login_bp.route('/logout',methods=['GET',])
def logout():
    session.clear()
    return redirect(url_for('.to_login'))
# 项目列表//url必须传变量给函数形参,有按钮可以跳转至add_project
@login_bp.route('/<username>',methods=['GET',])
def project_list(username):
    if 'username' not in session:
        return redirect(url_for('.index'))
    elif session['username']!=username:
        return u"authorization refused!" 
    else:
        cursor = db.pro_collection.find({'project_member.username': username})
        user = []
        for pro in cursor:
            project = pro['project_name']
            permission = 'member'
            if pro['project_owner']==session['username']:
                permission = 'owner'
            user.append({'project': project, 'permission': permission})
        return render_template('user_project.html',user=user)    


