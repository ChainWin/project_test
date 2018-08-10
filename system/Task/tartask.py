# coding: utf-8

from urllib import parse
import json
import logging
import hmac
import hashlib
import base64
from model import db
from bson import ObjectId
from datetime import datetime
from flask import Blueprint, url_for, render_template, redirect, session, request, Response


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

def task_type_check(**vardict):
    if ('proname' in vardict) and (len(vardict['proname'])>20):
        return False
    if 'token' in vardict:
        if len(vardict['token']) is not 32:
            return False
        try:
            token = int(vardict['token'], 16)
        except Exception as e:
            return False
    if ('illustration' in vardict) and (len(vardict['illustration'])>80):
        return False
    if 'time_out' in vardict:
        try:
            time_out = int(vardict['time_out'])
        except Exception as e:
            return False
    if 'task_id' in vardict:
        try:
            token = ObjectId(vardict['task_id'])
        except Exception as e:
            return False 
    if 'result_status' in vardict:
        try:
            result_status = int(vardict['result_status'])
        except Exception as e:
            return False
    return True

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

    return render_template('add_task.html', pro_name=pro_name)


@task_bp.route('/<pro_name>/add',methods=['POST', ])
def add_task(pro_name):
    branch = request.form['branch']
    illustration = request.form['illustration']
    time_out = request.form['time_out']
    if task_type_check(illustration=illustration, time_out=time_out) is False:
        return u'input type error'
    time_out = int(time_out)
    time_out = time_out*60*1000
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
                                             'result':{'description': None, 'log_url': None,
                                             'url': None, 'result_status': None}}],
                                     '$sort':{'time': -1}
                                             }
                                           }
                                 })
    db.pro_collection.create_index([('task.time', 1), ('task.id', 1)])
    return redirect(url_for('.task_status', pro_name=pro_name, ID=ID))


#查看打包任务状态
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
    task_dict['time'] = task_dict['time'].strftime('%b-%d-%Y %H:%M:%S')
    task_dict['project_name'] = pro_name
    task_dict['time_out'] /= 60000
    if task_dict['status']=='succeed' or task_dict['status']=='failed':
        return render_template('task_result.html', task=task_dict)
    elif session['username']==project['project_owner'] or session['username']==task_dict['operator']:
        return render_template('task_status.html', task=task_dict)
    else:
        return render_template('task_result.html', task=task_dict)


@task_bp.route('/<pro_name>/<ID>/', methods=['POST', ])
def task_reset(pro_name, ID):
    ID = ObjectId(ID)
    if 'withdraw' in request.form:
        db.pro_collection.update({'project_name': pro_name},
                                     {'$pull': {'task': {'id': ID, 'status': 'waiting'} }})
    elif 'reset' in request.form:
        db.pro_collection.update({'project_name': pro_name, 'task.id': ID},
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

    task_List = project['task']
    return render_template('task_list.html', task_List=task_List, pro_name=pro_name)    


def set_InstallMachine_status(project, token, status):
    db.pro_collection.update_one({'project_name': project, 'install_machine.token': token},
                                 {'$set': {'install_machine.$.status': status}})

#打包机获取一个任务/url未定义
@task_bp.route('/getTask/', methods=['POST', ])
def get_task():
    task = None
    token = request.json['token']
    project = request.json['project']
    signature = request.json['signature']
    if task_type_check(token=token, pro_name=project) is False:
        task = {'error': 'the input information type not right'}
        return Response(json.dumps(task),  mimetype='application/json')
    install_machine_dict = db.pro_collection.find({'project_name': project},
                                         { 'git_address': 1,
                                           'read_only_token':1,
                                           'install_machine': {'$elemMatch': {'token': token}}
                                          })
    if install_machine_dict is None:
        task = {'error': 'the project  not exist'}
        return Response(json.dumps(task),  mimetype='application/json')

    git_address = install_machine_dict[0]['git_address']
    read_only_token = install_machine_dict[0]['read_only_token']
            
    if 'install_machine' not in install_machine_dict[0]:
        task = {'error': 'the install_machine not exist'}
        return Response(json.dumps(task),  mimetype='application/json')
    install_machine_list = install_machine_dict[0]['install_machine']

    install_machine = install_machine_list[0]
    key = install_machine['key']

    value = {'project': project, 'token': token}
    strToSign = parse.urlencode(value)
    digest = hmac.new(bytes(key, encoding='utf-8'),
                 bytes(strToSign, encoding='utf-8'), digestmod=hashlib.sha256).digest()
    signature_cmp = base64.b64encode(digest).decode()
    if signature_cmp!=signature:
        task = {'error': 'signature not right!'}
        return Response(json.dumps(task), mimetype='application/json') 

    if install_machine['status']=='busy':
        task = {'error': 'the install machine is busy'}
        return Response(json.dumps(task), mimetype='application/json')

    #更新任务状态：执行中
    result = db.pro_collection.find_and_modify(query={'project_name': project, 'task.status': 'waiting'},
            update={'$set': {'task.$.status': 'executing'}})    
    if result is None:
        task = {'empty': 'there is no waiting task'}
        return Response(json.dumps(task), mimetype='application/json')
    
    #更新打包机状态：忙碌
    db.pro_collection.update_one({'project_name': project, 'install_machine.token': token},
                                 {'$set': {'install_machine.$.status': 'busy'}}) 
    task_list = result['task']
    task = (item for item in task_list if item["status"] == "waiting").__next__()
    delever = {'git_address': git_address, 'task_id': str(task['id']), 'branch': task['branch'],
               'time_out': task['time_out'], 'file': task['file']}
    if read_only_token is not None:
        delever['read_only_token'] = read_only_token
    return Response(json.dumps(delever), mimetype='application/json')


#打包结果
@task_bp.route('/result/', methods=['POST', ])
def submit_result():
    project = request.json['project']
    token = request.json['token']
    task_id = request.json['task_id']
    signature = request.json['signature']
    result_status = request.json['result_status']
    description = request.json['description']
    if task_type_check(token=token, pro_name=project, task_id=task_id,
                       result_status=result_status) is False:
        task = {'error': 'the client response information type not right'}
        return Response(json.dumps(task), mimetype='application/json')
    value = {'project': project, 'token': token, 'task_id': task_id,
             'description': description, 'result_status': result_status}
    #如果成功，应该返回一个结果url
    log_contents = None
    if 'log_contents' in request.json:
        log_contents = request.json['log_contents']
        value['log_contents'] = log_contents
    url=None
    if 'result_url' in request.json:
        url = request.json['result_url']
        value['result_url'] = url

    #验证签名：
    pro_dict = db.pro_collection.find({'project_name': project},
                                      {
                                       'install_machine': {'$elemMatch': {'token': token}},
                                       'task': {'$elemMatch': {'id': ObjectId(task_id)}}
                                      })
    if pro_dict is None:
        result = {'error': 'the project  not exist'}
        return Response(json.dumps(result), mimetype='application/json')

    #验证签名：
    if 'install_machine' not in pro_dict[0]:
        result = {'error': 'the install_machine not exist'}
        return Response(json.dumps(result), mimetype='application/json')
    install_machine_list = pro_dict[0]['install_machine']
    install_machine = install_machine_list[0]
    key = install_machine['key']
    strToSign = parse.urlencode(value)
    digest = hmac.new(bytes(key, encoding='utf-8'),
                      bytes(strToSign, encoding='utf-8'), digestmod=hashlib.sha256).digest()
    signature_cmp = base64.b64encode(digest).decode()
    if signature_cmp!=signature:
        result = {'error': 'signature not right!'}
        return Response(json.dumps(result), mimetype='application/json')

     #更新打包机状态
    db.pro_collection.update_one({'project_name':project, 'install_machine.token': token},
                                 {'$set': {'install_machine.$.status': 'free'}})

    if result_status==0 and ('result_url' not in request.json):
        result = {'error': 'succeed without url!'}
        return Response(json.dumps(result), mimetype='application/json')

 
    #验证打包任务状态：
    if 'task' not in pro_dict[0]:
        result = {'error': 'the task not exist'}
        return Response(json.dumps(result), mimetype='application/json')
    task_list = pro_dict[0]['task']
    task = task_list[0]
    if result_status == 0:
        status = 'succeed'
    else:
        status = 'failed'   
    if task['status'] != 'executing':
        if task['status']=='waiting':
            status = 'waiting'
            description = 'the task has been reseted'
            result_status = 1
            log_contents = None
            url = None
        #打包超时：
        else:
            status = 'time out'
            description = 'the task has been time-out'
            result_status = 1
            log_contents = None
            url = None 
        
    #更新打包任务状态并返回打包结果
    db.pro_collection.update_one({'project_name': project, 'task.id': ObjectId(task_id)},
                                  {'$set': {
                                       'task.$.status': status,
                                       'task.$.result.result_status': result_status,
                                       'task.$.result.description': description,
                                       'task.$.result.log_contents': log_contents,
                                       'task.$.result.url': url
                                    }
                                  })

    result = {'succeed': 'the building result has been upload'}
    return Response(json.dumps(result), mimetype='application/json')

@task_bp.route('/time_out')
def time_out():
    status = "time_out"
    db.pro_collection.update_many({"task.time_out": {'$lt': 'ISODate()'-"task.time"}},
                                  {'$set': {
                                       'task.$.status': status,
                                    }
                                  })
    


        
