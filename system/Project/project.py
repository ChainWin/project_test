import logging
import uuid, random, string
from flask import Blueprint, url_for, render_template, request, session, redirect
from model import db
from datetime import datetime

project_bp = Blueprint(
    'project',
    __name__,
    template_folder='templates',
    url_prefix='/project')

logger = logging.getLogger("table")
logger.setLevel(logging.DEBUG)
hdr = logging.FileHandler('span.log')
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
hdr.setFormatter(formatter)
logger.addHandler(hdr)

#项目详情//将当前项目名称和项目所有者传给函数
@project_bp.route('/<pro_name>')
def project_info(pro_name):
    if 'username' not in session:
        return redirect(url_for('login.index'))

    #判断是否存在该项目以及是否有权限查看（通过pro集合）

    project = db.pro_collection.find_one({'project_name': pro_name,
                                          'project_member.username': session['username']})
    if project is None:
        return u'the project not exist or you have no authorization'    
    illustration = project['illustration']
    owner_name = project['project_owner']
    address = project['git_address']
    token = project['read_only_token']
    time = project['time']
    install_machine = project['install_machine']    

    pro_info = [pro_name, illustration, owner_name, address, token, time, 
               install_machine]
    if session['username']==owner_name:
        return render_template('pro_info1.html', pro_info=pro_info)   
    else:
        return render_template('pro_info2.html', pro_info=pro_info)


#增加项目成员//url未定义，需要将当前用户和项目名称传给函数
@project_bp.route('/newproject', methods=['GET', ])
def to_add():
    if 'username' not in session:
        return redirect(url_for('login.index'))
    else:
        return render_template('add_project.html', error=None)
    


@project_bp.route('/newproject', methods=['POST', ])
def add_project_member():
    if 'username' not in session:
        return redirect(url_for('login.index'))
    error = None
    username = session['username']
    proname = request.form['project_name']
    illustration = request.form['illustration']
    address = request.form['git_address']
    token = None

    #判断是否有read_only_token传入 
    if 'read_only_token' in request.form:
        token = request.form['read_only_token']

    #类型判断函数还未定义 
    '''
    if type_judge(proname, address, illustration) is False:    
        error = 'insert type is not right, please try again'
        return render_template('add_project.html', error)
    '''
    project = db.pro_collection.find_one({'project_name': proname})
    if project is not None:
        error = 'the project has been existed!'   
        return render_template('add_project.html',error=error)
    else:
        db.pro_collection.insert_one({'project_name': proname, 'illustration': illustration, 
                                    'git_address': address, 'read_only_token': token,
                                    'project_owner': username,'project_member': [{'username': username, 'permission': 'owner'}],
                                    'time': datetime.now(), 'install_machine': [], 'task': []})  
        #创建索引：
        db.pro_collection.create_index([('project_name', 1),('project_owner', 1),
                                       ('project_member.username', 1)]) 
        return redirect(url_for('.project_info', pro_name=proname))


#修改项目详情//html 文件还未写
@project_bp.route('/<pro_name>/modify',methods=['GET',])
def to_modify_project(pro_name):
    if 'username' not in session:
        return redirect(url_for('login.index'))

    #判断是否存在该项目以及是否有权限修改（通过user集合）
    project = db.pro_collection.find_one({'project_name': pro_name,
                                        'project_owner': session['username']})
    if project is None:
        return u'the project not exist or you have no authorization'


    project_member = project['project_member']
    return render_template('project_modify.html', project_member = project_member)

    
#还未进行类型检查和限定    
@project_bp.route('/<pro_name>/modify',methods=['POST',])
def modify_project(pro_name):
    if  'illustration' in request.form:
        illustration = request.form['illustration']
        db.pro_collection.update_one({'project_name': pro_name},
                                     {'$set': {'illustration': illustration}})  
    if 'git_address' in request.form:
        git_address = request.form['git_address']
        if git_address != '':
            db.pro_collection.update_one({'project_name': pro_name},
                                        {'$set': {'git_address': git_address}})
    if 'token' in request.form:
        token = request.form['token']
        if token != '':
            db.pro_collection.update_one({'project_name': pro_name},
                                        {'$set': {'read_only_token': token}})


    #转移项目所有权：
    if 'new_owner' in request.form:
        new_owner = request.form['new_owner']
        if new_owner!=session['username']:
            db.pro_collection.update_one({'project_name': pro_name},
                                        {'$set': {'project_owner': new_owner}})
            db.pro_collection.update_one({'project_name': pro_name, 'project_member.username': session['username']},
                                        {'$set': {'project_member.$.permission': 'owner'}})
            db.pro_collection.update_one({'project_name': pro_name, 'project_member.username': new_owner},
                                        {'$set': {'project_member.$.permission': 'member'}})

    #新增和删除成员(需要在list中进行查找，效率会不会比较低？)
    if ('new_member' in request.form) and (request.form['new_member']!=''):
        new_member = request.form['new_member']
        project = db.pro_collection.find_one({'project_name': pro_name,
                                              'project_member.username': new_member})
        if project is None:
            db.pro_collection.update_one({'project_name': pro_name},
                                         {'$push': {'project_member': {'$each': 
                                        [{'username': new_member, 'permission': 'member'}]}}})
                                           

    if 'delete' in request.form:
        delete_member = request.form['delete']
        db.pro_collection.update_one({'project_name': pro_name},
                                     {'$pull': {'project_member':
                                     {'username': delete_member, 'permission': 'member'} }})
    return redirect(url_for('.project_info', pro_name=pro_name)) 
    
     

 
#显示现有打包机并提供新增打包机页面//
@project_bp.route('/<pro_name>/manage_install_machine/',methods=['GET',])
def to_manage_install_machine(pro_name):
    if 'username' not in session:
        return redirect(url_for('login.index'))
    #判断是否存在该项目以及是否有权限修改（通过user集合）
    project = db.pro_collection.find_one({'project_name': pro_name,
                                        'project_owner': session['username']})
    if project is None:
        return u'the project not exist or you have no authorization'   
    
    install_machine = project['install_machine']
    return render_template('install_machine.html', install_machine=install_machine)
    


#打包机管理
@project_bp.route('/<pro_name>/manage_install_machine/',methods=['POST',])
def manage_install_machine(pro_name):
    if 'delete' in request.form:
        token = request.form['delete']
        db.pro_collection.update_one({'project_name': pro_name},
                                     {'$pull': {'install_machine': {'token': token}}})
    if 'add' in request.form:
        token = uuid.uuid4().hex
        key=''.join(random.sample(string.ascii_letters + string.digits, 8))     
        status = 'free'
        db.pro_collection.update_one({'project_name': pro_name},
                                    {'$push': {'install_machine': {'$each':
                                    [{'token': token, 'key': key, 'status': status}]}}})
        db.pro_collection.create_index([('install_machine.token', 1)])
    return redirect(url_for('.project_info', pro_name=pro_name))        



