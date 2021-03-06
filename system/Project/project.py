import logging
import uuid, random, string
import pymongo
from flask import Blueprint, url_for, render_template, request, session, redirect
from model import db
from datetime import datetime
from authenticate import login_required

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

def pro_type_check(**vardict):
    if ('proname' in vardict) and (len(vardict['proname'])>20):
        return False
    if 'address' in vardict:
        if (not vardict['address'].startswith('https://nanny.netease.com/')) or (not 
            vardict['address'].endswith('.git')):
            return False          
    if ('illustration' in vardict) and (len(vardict['illustration'])>50):
        return False
    if 'token' in vardict:
        if len(vardict['token']) is not 40:
            return False
        try:
            token = int(vardict['token'], 16)
        except Exception as e:
            return False
    if ('member' in vardict) and (len(vardict['member'])>20):
        return False         
    return True

#项目详情//
@project_bp.route('/<pro_name>')
@login_required
def project_info(pro_name):

    #判断是否存在该项目以及是否有权限查看（通过pro集合）

    project = db.pro_collection.find_one({'project_name': pro_name,
                                          'project_member.username': session['username']})
    if project is None:
        return u'the project not exist or you have no authorization'    
    illustration = project['illustration']
    owner_name = project['project_owner']
    address = project['git_address']
    token = project['read_only_token']
    time = project['time'].strftime('%b-%d-%Y %H:%M:%S')
    install_machine = project['install_machine']    

    pro_info = [pro_name, illustration, owner_name, address, token, time, 
               install_machine]
    if project['task']:
        task = project['task'][-1]
        task['time'] = task['time'].strftime('%b-%d-%Y %H:%M:%S')
        pro_info.append(task)
    return render_template('pro_info.html', pro_info=pro_info)   


#增加项目成员//url未定义，需要将当前用户和项目名称传给函数
@project_bp.route('/newproject', methods=['GET', ])
@login_required
def to_add():
    return render_template('add_project.html', error=None)


@project_bp.route('/newproject', methods=['POST', ])
@login_required
def add_project_member():
    error = None
    username = session['username']
    proname = request.form['project_name']
    illustration = request.form['illustration']
    address = request.form['git_address']
    token = None

    #判断是否有read_only_token传入 
    if 'read_only_token' in request.form and request.form['read_only_token'] is not '':
        token = request.form['read_only_token']
        pro_type = pro_type_check(proname=proname, address=address,
                                  illustration=illustration, token=token)
    else:
        pro_type =pro_type_check(proname=proname, address=address, illustration=illustration)

    #类型判断
    if pro_type is False:    
        error = 'insert type is not right, please try again'
        return render_template('add_project.html', error=error)

    try:
        db.pro_collection.insert({'project_name': proname, 'illustration': illustration, 
                                    'git_address': address, 'read_only_token': token,
                                    'project_owner': username,'project_member': [{'username': username, 'permission': 'owner'}],
                                    'time': datetime.now(), 'install_machine': [], 'task': []})  
    except pymongo.errors.DuplicateKeyError:
        error = 'the project has been existed!'   
        return render_template('add_project.html',error=error)
        #创建索引：
    db.pro_collection.create_index([('project_owner', 1),('project_member.username', 1)]) 
    return redirect(url_for('.project_info', pro_name=proname))


#修改项目详情//
@project_bp.route('/<pro_name>/modify',methods=['GET',])
@login_required
def to_modify_project(pro_name):
    #判断是否存在该项目以及是否有权限修改（通过user集合）
    project = db.pro_collection.find_one({'project_name': pro_name,
                                        'project_owner': session['username']})
    if project is None:
        return u'the project not exist or you have no authorization'


    project_member = project['project_member']
    return render_template('project_modify.html', project_member = project_member,
                           project_name=pro_name)

    
@project_bp.route('/<pro_name>/modify',methods=['POST',])
def modify_project(pro_name):
    if  'illustration' in request.form and request.form['illustration'] != '':
        illustration = request.form['illustration']
        if pro_type_check(illustration=illustration) is False:
            return u'illustration content can not longer than 50'
        db.pro_collection.update_one({'project_name': pro_name},
                                     {'$set': {'illustration': illustration}})  

    if 'git_address' in request.form and request.form['git_address'] != '':
        git_address = request.form['git_address']
        if pro_type_check(address=git_address) is False:
            return u'git address type not right'
        db.pro_collection.update_one({'project_name': pro_name},
                                     {'$set': {'git_address': git_address}})

    if 'token' in request.form and request.form['token'] != '':
        token = request.form['token']
        if pro_type_check(token=token) is False:
            return u'the token type not right'
        db.pro_collection.update_one({'project_name': pro_name},
                                     {'$set': {'read_only_token': token}})


    #转移项目所有权：
    if 'new_owner' in request.form:
        new_owner = request.form['new_owner']
        if new_owner!=session['username']:
            db.pro_collection.update_one({'project_name': pro_name},
                                        {'$set': {'project_owner': new_owner}})
            db.pro_collection.update_one({'project_name': pro_name, 'project_member.username': new_owner},
                                        {'$set': {'project_member.$.permission': 'owner'}})
            db.pro_collection.update_one({'project_name': pro_name, 'project_member.username': session['username']},
                                        {'$set': {'project_member.$.permission': 'member'}})

    #新增和删除成员
    if ('new_member' in request.form) and (request.form['new_member']!=''):
        new_member = request.form['new_member']
        if pro_type_check(member=new_member) is False:
            return u'the new member\'s name type not right'
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
@login_required
def to_manage_install_machine(pro_name):
    #判断是否存在该项目以及是否有权限修改（通过user集合）
    project = db.pro_collection.find_one({'project_name': pro_name,
                                        'project_owner': session['username']})
    if project is None:
        return u'the project not exist or you have no authorization'   
    
    install_machine = project['install_machine']
    return render_template('install_machine.html', install_machine=install_machine)
    


#打包机管理
@project_bp.route('/<pro_name>/manage_install_machine/',methods=['POST',])
@login_required
def manage_install_machine(pro_name):
    if 'delete' in request.form:
        token = request.form['delete']
        db.pro_collection.update({'project_name': pro_name},
                                 {'$pull': {'install_machine': {'token': token}}})
    if 'add' in request.form:
        token = uuid.uuid4().hex
        key=''.join(random.sample(string.ascii_letters + string.digits, 8))     
        status = 'free'
        db.pro_collection.update({'project_name': pro_name},
                                 {'$push': {'install_machine': {'$each':
                                [{'token': token, 'key': key, 'status': status}]}}})
        db.pro_collection.create_index([('install_machine.token', 1)])
    return redirect(url_for('.project_info', pro_name=pro_name))        


