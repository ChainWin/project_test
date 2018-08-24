# coding: utf-8

from urllib import parse
import json
import logging
import hmac
import hashlib
import base64
from model import db
from authenticate import login_required
from bson import ObjectId
from datetime import datetime
from flask import Blueprint, url_for, render_template, redirect, session,\
                  request, Response, jsonify, make_response, abort


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
@login_required
def to_add_task(pro_name):
    #判断是否存在该项目以及是否有权限添加打包任务（通过pro集合）

   
    project = db.pro_collection.find_one({'project_name': pro_name,
                                          'project_member.username': session['username']})
    if project is None:
        return u'the project not exist or you have no authorization' 

    return render_template('add_task.html', pro_name=pro_name)


@task_bp.route('/<pro_name>/add',methods=['POST', ])
@login_required
def add_task(pro_name):
    branch = request.form['branch']
    illustration = request.form['illustration']
    time_out = request.form['time_out']
    file_content = request.form['file']
    if task_type_check(illustration=illustration, time_out=time_out) is False:
        return u'input type error'
    time_out = int(time_out)
    time_out = time_out*60*1000
    operator = session['username']
    time = datetime.now()
    status = 'waiting'
    ID = ObjectId()
    try:
       file_attachment = request.files['file_attachment'].stream.read()
       file_attachment = file_attachment.decode()
    except Exception as e:
       file_attachment = None
    if file_attachment:
        file_content = file_attachment
    db.pro_collection.update_one(
                                 {'project_name': pro_name},
                                 {
                                  '$push': {
                                     'task': {
                                    '$each':[{'branch': branch, 'illustration': illustration,
                                             'operator': operator,'time': time, 'id': ID,
                                             'time_out': time_out, 'status': status, 'file': file_content,
                                             'result':{'description': None, 'log_contents': None,
                                             'url': None, 'result_status': None}}],
                                     '$sort':{'time': 1}
                                             }
                                           }
                                 })
    db.pro_collection.create_index([('task.time', 1), ('task.id', 1)])
    return redirect(url_for('.task_status', pro_name=pro_name, ID=ID))


#查看打包任务状态
@task_bp.route('/<pro_name>/<ID>/')
@login_required
def task_status(pro_name, ID):
    #判断是否存在该项目以及是否有权限查看打包任务（通过pro集合）
    try:
        ID = ObjectId(ID)
        task = db.pro_collection.find({'project_name': pro_name, 'project_member.username': session['username']},
                                      {
                                      'project_owner': 1,
                                      'task': {'$elemMatch': {'id': ID}}
                                      })
        task = task[0]
    except Exception as e:
        abort(404)
    #判断该任务是否存在
    if 'task' not in task:
        return u'the task not exist '
    task_list = task['task']
    task_dict = task_list[0]
    task_dict['time'] = task_dict['time'].strftime('%b-%d-%Y %H:%M:%S')
    task_dict['project_name'] = pro_name
    task_dict['project_owner'] = task['project_owner']
    task_dict['time_out'] /= 60000
    if task_dict['result']['log_contents']:
        task_dict['result']['log_contents'] = True
    return render_template('task_result1.html', task=task_dict)


@task_bp.route('/<pro_name>/<ID>/', methods=['POST', ])
def task_reset(pro_name, ID):
    ID = ObjectId(ID)
    if 'withdraw' in request.form:
        db.pro_collection.update({'project_name': pro_name},
                                     {'$pull': {'task': {'id': ID, 'status': 'waiting'} }})
    elif 'reset' in request.form:
        db.pro_collection.update({'project_name': pro_name, 'task':{'$elemMatch': {'id': ID, 'status': 'executing'}}},
                                    {'$set': {'task.$.status': 'waiting'}}) 
    return redirect(url_for('.task_list', pro_name=pro_name))


#返回打包结果的log文件
@task_bp.route('/log/<pro_name>/<ID>')
def log_contents(pro_name,ID):
    filename = ID+'.log'
    ID = ObjectId(ID)
    try:
        cursor = db.pro_collection.find({'project_name': pro_name, 'project_member.username': session['username']},
                                        {
                                         'task': {'$elemMatch': {'id': ID}} 
                                        })
        for doc in cursor:
            log_contents = doc['task'][0]['result']['log_contents']
            response = make_response(log_contents)
            response.headers['Content-Disposition'] = "attachment; filename=\"%s\""%filename
            return response
    except Exception as e:
        return 'can not find the log'

@task_bp.route('/jsondata/<pro_name>', methods=['POST', 'GET'])
def infos(pro_name):
    project = db.pro_collection.find_one({'project_name': pro_name,
                                          'project_member.username': session['username']})
    if project is None:
        return u'the project not exist or you have no authorization'
    
    task_List = project['task']
    for task in task_List:
        task['time'] = task['time'].strftime('%b-%d-%Y %H:%M:%S')
        task['id']=str(task['id'])
        task.pop('file')
        task.pop('result')
    if request.method == 'GET':
        info = request.values
        limit = info.get('limit', 10)  # 每页显示的条数
        offset = info.get('offset', 0)  # 分片数，(页码-1)*limit，它表示一段数据的起点
        return jsonify({'total': len(task_List), 'rows': task_List[(-1-int(offset)):(-int(offset)-1 - int(limit)):-1]})
        # 注意total与rows是必须的两个参数，名字不能写错，total是数据的总长度，rows是每页要显示的数据,它是一个列表
        # 前端根本不需要指定total和rows这俩参数，他们已经封装在了bootstrap table里了


#查看打包任务列表//
@task_bp.route('/<pro_name>/list')
@login_required
def task_list(pro_name):
    return render_template('task_list3.html', pro_name=pro_name)    


def set_InstallMachine_status(project, token, status):
    db.pro_collection.update_one({'project_name': project, 'install_machine.token': token},
                                 {'$set': {'install_machine.$.status': status}})


def signature_verify(project, value, signature):
    if 'install_machine' not in project:
        return {'error': 'the install_machine not exist'}
    install_machine_list = project['install_machine']
    install_machine = install_machine_list[0]
    key = install_machine['key']
    strToSign = parse.urlencode(value)
    digest = hmac.new(bytes(key, encoding='utf-8'),
                 bytes(strToSign, encoding='utf-8'), digestmod=hashlib.sha256).digest()
    signature_cmp = base64.b64encode(digest).decode()
    if signature_cmp!=signature:
        return {'error': 'signature not right!'}
    return {'succeed': 'signature verify succeed'}


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
    value = {'project': project, 'token': token}
    try:
       pro_list = db.pro_collection.find({'project_name': project},
                                         { 'git_address': 1,
                                           'read_only_token':1,
                                           'install_machine': {'$elemMatch': {'token': token}}
                                          })
       pro_dict = pro_list[0]
    except Exception as e:
        task = {'error': 'the project  not exist'}
        return Response(json.dumps(task),  mimetype='application/json')
    git_address = pro_dict['git_address']
    read_only_token = pro_dict['read_only_token']
    # 签名验证
    task = signature_verify(pro_dict, value, signature)
    if 'error' in task:
        return Response(json.dumps(task), mimetype='application/json')
    if pro_dict['install_machine'][0]['status']=='busy':
        task = {'error': 'the install machine is busy'}
        return Response(json.dumps(task), mimetype='application/json')
    #更新任务状态：执行中
    result = db.pro_collection.find_and_modify(query={'project_name': project, 'task.status': 'waiting'},
            update={'$set': {'task.$.status': 'executing'}})    
    if result is None:
        task = {'empty': 'there is no waiting task'}
        return Response(json.dumps(task), mimetype='application/json')
    
    #更新打包机状态：忙碌
    set_InstallMachine_status(project, token, 'busy')
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
    try:
        pro_list = db.pro_collection.find({'project_name': project},
                                      {
                                       'install_machine': {'$elemMatch': {'token': token}},
                                       'task': {'$elemMatch': {'id': ObjectId(task_id)}}
                                      })
        pro_dict = pro_list[0]
    except Exception as e:
        result = {'error': 'the project  not exist'}
        return Response(json.dumps(result),  mimetype='application/json')
    #验证签名：
    result = signature_verify(pro_dict, value, signature)
    if 'error' in result:
        return Response(json.dumps(result), mimetype='application/json')
    #更新打包机状态
    set_InstallMachine_status(project, token, 'free')
 
    if result_status==0 and ('result_url' not in request.json):
        result_status = 1
        description = 'building result without url'

    #验证打包任务状态：
    if 'task' not in pro_dict:
        result = {'error': 'the task not exist'}
        return Response(json.dumps(result), mimetype='application/json')
    task_list = pro_dict['task']
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


def task_update(project_name, task):
    for index in task:
        ID = index['id']
        time = index['time']
        time_out = index['time_out']
        time_pass = ((datetime.now() - time).seconds * 1000 +
                     (datetime.now() - time).microseconds / 1000)
        if time_pass > time_out:
            db.pro_collection.update({
                         'project_name': project_name,
                         'task': {
                             '$elemMatch': {
                                 '$or': [
                                     {'id': ID, 'status': 'executing'},
                                     {'id': ID, 'status': 'waiting'}]}
                                 }},
                             {'$set': {'task.$.status': 'time out'}})


def time_out():
    cursor = db.pro_collection.aggregate([{
             '$project': {
                 'project_name': 1,
                 'task': {
                     '$filter': {
                         'input': '$task',
                         'as': 'task',
                         'cond': {
                            '$or': [
                                {'$eq': ['$$task.status', 'waiting']},
                                {'$eq': ['$$task.status', 'executing']}
                                 ]}}}}}])
    cursor = list(cursor)
    print(cursor)
    for index in cursor:
        project_name = index['project_name']
        task = index['task']
        task_update(project_name, task)
