# coding: utf-8

import logging
import hmac
import hashlib
import base64
from model import db
from bson import ObjectId
from datetime import datetime
from flask import Blueprint, url_for, render_template, redirect, session, request


task_bp = Blueprint(
    'task',
    __name__,
    template_folder='templates',
    url_prefix='/task')


logger = logging.getLogger("table")
logger.setLevel(logging.DEBUG)
hdr = logging.FileHandler('span.log')
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
hdr.setFormatter(formatter)
logger.addHandler(hdr)

#新增打包任务//url未定义，需要当前用户和项目名作为形参
@task_bp.route('/<pro_name>/add',methods=['GET', ])
def to_add_task(pro_name):
    if 'username' not in session:
        return redirect(url_for('login.index'))

    #判断是否存在该项目以及是否有权限添加打包任务（通过pro集合）

   
    project = db.pro_collection.find_one({'project_name': pro_name,
                                          'project_member.username': session['username']})
    if project is None:
        return u'the project not exist or you have no authorization' 

    return render_template('add_task.html')


#还未进行数据类型检查
@task_bp.route('/<pro_name>/add',methods=['POST', ])
def add_task(pro_name):
    branch = request.form['branch']
    illustration = request.form['illustration']
    time_out = request.form['time_out']
    operator = session['username']
    time = datetime.now()
    status = 'waiting'
    ID = ObjectId()
    file_content = request.files['file'].stream.read()
    file_content = file_content.decode()
    db.pro_collection.update_one(
                                 {'project_name': pro_name},
                                 {
                                  '$push': {
                                     'task': {
                                    '$each':[{'branch': branch, 'illustration': illustration,
                                             'operator': operator,'time': time, 'id': ID,
                                             'time_out': time_out, 'status': status, 'file': file_content,
                                             'result':{'description': None, 'log_url': None, 'url': None}}],
                                     '$sort':{'time': -1}
                                             }
                                           }
                                 })
    db.pro_collection.create_index([('task.time', -1), ('task.id', 1)])
    return redirect(url_for('.task_status', pro_name=pro_name, ID=ID))


#查看打包任务状态，对ID类型没有进行限制
@task_bp.route('/<pro_name>/<ID>/')
def task_status(pro_name, ID):
    ID = ObjectId(ID)
    if 'username' not in session:
        return redirect(url_for('login.index'))

    #判断是否存在该项目以及是否有权限查看打包任务（通过pro集合）

    project = db.pro_collection.find_one({'project_name': pro_name,
                                          'project_member.username': session['username']})
    if project is None:
        return u'the project not exist or you have no authorization'

    task = db.pro_collection.find({'project_name': pro_name},
                                  {'task': {'$elemMatch': {'id': ID}}})
    #没有判断该任务是否存在
    if 'task' not in task[0]:
        return u'the task not exist '

    task_list = task[0]['task']
    task_dict = task_list[0]
    task_dict['project_name'] = pro_name
    if task_dict['status']=='succeed' or task_dict['status']=='error':
        return render_template('task_result.html', task=task_dict)
    elif session['username']==project['project_owner'] or session['username']==task_dict['operator']:
        return render_template('task_status.html', task=task_dict)
    else:
        return render_template('task_result.html', task=task_dict)


@task_bp.route('/<pro_name>/<ID>/', methods=['POST', ])
def task_reset(pro_name, ID):
    ID = ObjectId(ID)
    if 'withdraw' in request.form:
        db.pro_collection.update_one({'project_name': pro_name},
                                     {'$pull': {'task': {'id': ID, 'status': 'waiting'} }})
    elif 'reset' in request.form:
        db.pro_collection.update_one({'project_name': pro_name, 'task.id': ID},
                                      {'$set': {'task.$.status': 'waiting'}}) 
    return redirect(url_for('.task_status', pro_name=pro_name, ID=ID))


#查看打包任务列表//url未定义
@task_bp.route('/<pro_name>/list')
def task_list(pro_name):
    if 'username' not in session:
        return redirect(url_for('login.index'))

    #判断是否存在该项目以及是否有权限查看打包任务（通过pro集合）

    project = db.pro_collection.find_one({'project_name': pro_name,
                                          'project_member.username': session['username']})
    if project is None:
        return u'the project not exist or you have no authorization'

    task = db.pro_collection.find_one({'project_name': pro_name})      
    task_List = task['task']
    return render_template('task_list.html', task_List=task_List, pro_name=pro_name)    


#打包机获取一个任务/url未定义
@task_bp.route('/getTask/', methods=['POST', ])
def get_task():
    try:
        token = request.form['token']
        project = request.form['project']
        signature = request.form['signature']
    except ValueError:
        return 'get task error'
    install_machine_dict = db.pro_collection.find({'project_name': project},
                                             { 'git_address': 1,
                                               'install_machine': {'$elemMatch': {'token': token}}
                                             })
    if install_machine_dict is None:
        return "the project  not exist"
    git_address = install_machine_dict['git_address']
    install_machine_list = install_machine_dict['install_machine']
    if not install_machine_list:
        return "the install_machine not exist"
    install_machine = install_machine_list[0]
    key = install_machine['key']

    strToSign = project+token
    digest = hmac.new(bytes(key, encoding='utf-8'),
                      bytes(strToSign, encoding='utf-8'), digestmod=hashlib.sha256).digest()
    signature_cmp = base64.b64encode(digest).decode()
    if signature_cmp!=signature:
        return   "signature not right!"


    #应该将任务列表写到项目集合中，减少集合数目
    task_dict = db.task_collection.aggregate([
                                          {'$match': {'project_name': project}},
                                          {'$project': {
                                                    'task':  {
                                                       '$filter':{
                                                         'input': "$task",
                                                         'as' :"task",
                                                         'cond': {'$eq': ['$$task.status', "waiting"]}
                                                         }
                                                      }
                                            }
                                          }])
    task_list = task_dict['task']   
    if not task_list:
        return "there is no waiting task"
   
    task = task_list[-1]
    #更新任务状态：执行中
    db.task_collection.update_one({'project_name': project, 'task.id': task['id']},
                                  {'$set': {'task.$.status': 'executing'}})
    
    #更新打包机状态：忙碌
    db.pro_collection.update_one({'project_name': project, 'install_machine.token': token},
                                 {'$set': {'install_machine.$.status': 'busy'}}) 
    task['git_address'] = git_address
    return task

#打包结果
@task_bp.route('/result/')
def submit_result():
    try:
        token = request.form['token']
        project = request.form['project']
        task_id = request.form['task_id']
        signature = request.form['signature']
        result_status = request.form['result_status']
        description = request.form['description']
    except ValueError:
        return 'submit result error!'
    
    strToSign = project+token+task_id+result_status+description

    #如果成功，应该返回一个结果url
    log_url = None
    if 'log_url' in request.form:
        log_url = request.form['log_url']
        strToSign += log_url
    url=None
    if result_status=='succeed':
        try:
            url = request.form['url']
        except ValueError:
            return 'succeed without url!'
        strToSign += url

    #验证签名：
    install_machine_dict = db.pro_collection.find({'project_name': project},
                                             {'install_machine': {'$elemMatch': {'token': token}}
                                             })
    if install_machine_dict is None:
        return "the project  not exist"
    install_machine_list = install_machine_dict['install_machine']
    if not install_machine_list:
        return "the install_machine not exist"
    install_machine = install_machine_list[0]
    key = install_machine['key']
    digest = hmac.new(bytes(key, encoding='utf-8'),
                      bytes(strToSign, encoding='utf-8'), digestmod=hashlib.sha256).digest()
    signature_cmp = base64.b64encode(digest).decode()
    if signature_cmp!=signature:
        return   "signature not right!"
    
   
    #验证打包任务状态：
    task_dict = db.task_collection.find({'project_name': project},
                                        {'task': {'$elemMatch': {'id': task_id}}
                                       })
    task_list = task_dict['task']
    if not task_list:
        return 'the task not exist'
    task = task_list[0]
    if task['status'] != 'executing':
        if task['status']=='waiting':
            result_status = 'error'
            description = 'the task has been reseted'
            log_url = None
            url = None
        else:
            return 'task status error'
    
    #更新打包机状态
    db.pro_collection.update_one({'project_name':project, 'install_machine.token': token},
                                 {'$set': {'install_machine.$.status': 'free'}})

        
    #更新打包任务状态并返回打包结果
    '''
    result = {'description': description,
              'log_url': log_url,
              'url': url
             }
    '''
    db.task_collection.update_one({'project_name': project, 'task.id': task_id},
                                  {'$set': {
                                       'task.$.status': result_status,
                                       'task.$.result.description': description,
                                       'task.$.result.log_url': log_url,
                                       'task.$.result.url': url
                                     }
                                  })

    if task['status'] == 'waiting':
        return 'task has been reseted!'


        
