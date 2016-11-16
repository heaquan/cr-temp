# Html － Crysadm 管理员界面
__author__ = 'powergx'
from flask import request, Response, render_template, session, url_for, redirect
from crysadm import app, r_session
from auth import requires_admin, requires_auth
import json
from util import hash_password
from datetime import datetime
import re
import random
from message import send_msg

# 系统管理 => 用户管理
@app.route('/admin/user')
@requires_admin
def admin_user():
    recent_login_users = []
    users = list()

    for b_user in r_session.mget(*['user:%s' % name.decode('utf-8') for name in sorted(r_session.smembers('users'))]):
        if b_user is None:
            continue
        user = json.loads(b_user.decode('utf-8'))
        if user.get('login_as_time') is not None:
            if (datetime.now() - datetime.strptime(user.get('login_as_time'), '%Y-%m-%d %H:%M:%S')).days < 3:
                recent_login_users.append(user)
        user['is_online'] = r_session.exists('user:%s:is_online' % user.get('username')) # 临时寄存数据
        users.append(user)

    return render_template('admin_user.html',
                           recent_login_users=sorted(recent_login_users, key=lambda k: k['login_as_time'],
                                                     reverse=True),
                           users=users)

# 系统管理 => 通知管理
@app.route('/admin/message')
@requires_admin
def admin_message():
    return render_template('admin_message.html')

# 系统管理 => 邀请管理
@app.route('/admin/invitation')
@requires_admin
def admin_invitation():
    pub_inv_codes = r_session.smembers('public_invitation_codes')

    inv_codes = r_session.smembers('invitation_codes')
    return render_template('admin_invitation.html', inv_codes=inv_codes, public_inv_codes=pub_inv_codes)

# 系统管理 => 邀请管理 => 生成邀请码
@app.route('/generate/inv_code', methods=['POST'])
@requires_admin
def generate_inv_code():
    _chars = "0123456789ABCDEF"
    r_session.smembers('invitation_codes')

    for i in range(0, 30 - r_session.scard('invitation_codes')):
        r_session.sadd('invitation_codes', ''.join(random.sample(_chars, 10)))

    return redirect(url_for('admin_invitation'))

# 系统管理 => 邀请管理 => 生成公开邀请码
@app.route('/generate/pub_inv_code', methods=['POST'])
@requires_admin
def generate_pub_inv_code():
    _chars = "0123456789ABCDEF"
    r_session.smembers('public_invitation_codes')

    for i in range(0, 15 - r_session.scard('public_invitation_codes')):
        key = ''.join(random.sample(_chars, 10))
        r_session.sadd('public_invitation_codes', key)

    return redirect(url_for('admin_invitation'))

# 系统管理 => 用户管理 => 登陆其它用户
@app.route('/admin/login_as/<username>', methods=['POST'])
@requires_admin
def generate_login_as(username):
    user_info = r_session.get('%s:%s' % ('user', username))

    user = json.loads(user_info.decode('utf-8'))
    user['login_as_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if user.get('log_as_body') is not None:
        if len(user.get('log_as_body')) > 0:
            r_session.set('%s:%s' % ('record', username), json.dumps(dict(diary=user.get('log_as_body')))) # 创建新通道,转移原本日记
            user['log_as_body'] = []

    if r_session.get('%s:%s' % ('record', username)) is None:
        r_session.set('%s:%s' % ('record', username), json.dumps(dict(diary=[]))) # 创建缺失的日记

    r_session.set('%s:%s' % ('user', username), json.dumps(user))
    session['admin_user_info'] = session.get('user_info')
    session['user_info'] = user

    return redirect(url_for('dashboard'))

# 系统管理 => 用户管理 => 编辑用户资料
@app.route('/admin_user/<username>')
@requires_admin
def admin_user_management(username):
    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None

    user = json.loads(r_session.get('user:%s' % username).decode('utf-8'))

    return render_template('user_management.html', user=user, err_msg=err_msg)

# 系统管理 => 用户管理 => 编辑用户资料 => 修改密码
@app.route('/admin/change_password/<username>', methods=['POST'])
@requires_admin
def admin_change_password(username):
    n_password = request.values.get('new_password')

    if len(n_password) < 8:
        session['error_message'] = '密码必须8位以上.'
        return redirect(url_for(endpoint='admin_user_management', username=username))

    user_key = '%s:%s' % ('user', username)
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    user_info['password'] = hash_password(n_password)
    r_session.set(user_key, json.dumps(user_info))

    return redirect(url_for(endpoint='admin_user_management', username=username))

# 系统管理 => 用户管理 => 编辑用户资料 => 修改其它属性
@app.route('/admin/change_property/<field>/<value>/<username>', methods=['POST'])
@requires_admin
def admin_change_property(field, value, username):
    user_key = '%s:%s' % ('user', username)
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    if field == 'is_admin':
        user_info['is_admin'] = True if value == '1' else False
    elif field == 'active':
        user_info['active'] = True if value == '1' else False
    elif field == 'auto_column':
        user_info['auto_column'] = True if value == '1' else False
    elif field == 'auto_collect':
        user_info['auto_collect'] = True if value == '1' else False
    elif field == 'auto_drawcash':
        user_info['auto_drawcash'] = True if value == '1' else False
    elif field == 'auto_giftbox':
        user_info['auto_giftbox'] = True if value == '1' else False
    elif field == 'auto_searcht':
        user_info['auto_searcht'] = True if value == '1' else False
    elif field == 'auto_revenge':
        user_info['auto_revenge'] = True if value == '1' else False
    elif field == 'auto_getaward':
        user_info['auto_getaward'] = True if value == '1' else False
    elif field.endswith('_interval'):
        try:
            if int(str(request.values.get(field))) >= 1:
                user_info[field] = int(str(request.values.get(field)))
                r_session.set(user_key, json.dumps(user_info))
        except ValueError:
            print(ValueError)
        return redirect(url_for('system_config'))
    elif field.find('_mail_') != -1:
        session['action'] = 'info'
        user_info[field] = str(request.values.get(field))
        r_session.set(user_key, json.dumps(user_info))
        return redirect(url_for('system_config'))
    r_session.set(user_key, json.dumps(user_info))

    return redirect(url_for(endpoint='admin_user_management', username=username))

# 系统管理 => 用户管理 => 编辑用户资料 => 提示信息
@app.route('/admin/change_user_info/<username>', methods=['POST'])
@requires_admin
def admin_change_user_info(username):
    max_account_no = request.values.get('max_account_no')

    r = r"^[1-9]\d*$"

    if re.match(r, max_account_no) is None:
        session['error_message'] = '迅雷账号限制必须为整数.'
        return redirect(url_for(endpoint='admin_user_management', username=username))

    if not 0 < int(max_account_no) < 101:
        session['error_message'] = '迅雷账号限制必须为 1~100.'
        return redirect(url_for(endpoint='admin_user_management', username=username))

    user_key = '%s:%s' % ('user', username)
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    user_info['max_account_no'] = int(max_account_no)

    r_session.set(user_key, json.dumps(user_info))

    return redirect(url_for(endpoint='admin_user_management', username=username))

# 系统管理 => 用户管理 => 删除用户
@app.route('/admin/del_user/<username>', methods=['GET'])
@requires_admin
def admin_del_user(username):
    if r_session.get('%s:%s' % ('user', username)) is None:
        session['error_message'] = '账号不存在'
        return redirect(url_for(endpoint='admin_user', username=username))

    # do del user
    r_session.delete('%s:%s' % ('user', username))
    r_session.delete('%s:%s' % ('record', username))
    r_session.srem('users', username)
    for b_account_id in r_session.smembers('accounts:' + username):
        account_id = b_account_id.decode('utf-8')
        r_session.delete('account:%s:%s' % (username, account_id))
        r_session.delete('account:%s:%s:data' % (username, account_id))
    r_session.delete('accounts:' + username)

    for key in r_session.keys('user_data:%s:*' % username):
        r_session.delete(key.decode('utf-8'))

    return redirect(url_for('admin_user'))

# 系统管理 => 用户管理 => 无用户？
@app.route('/none_user')
@requires_admin
def none_user():
    none_xlAcct = list()
    none_active_xlAcct = list()
    for b_user in r_session.smembers('users'):
        username = b_user.decode('utf-8')

        if r_session.smembers('accounts:' + username) is None or len(r_session.smembers('accounts:' + username)) == 0:
            none_xlAcct.append(username)
        has_active_account = False
        for b_xl_account in r_session.smembers('accounts:' + username):
            xl_account = b_xl_account.decode('utf-8')
            account = json.loads(r_session.get('account:%s:%s' % (username, xl_account)).decode('utf-8'))
            if account.get('active'):
                has_active_account = True
                break
        if not has_active_account:
            none_active_xlAcct.append(username)

    return json.dumps(dict(none_xlAcct=none_xlAcct, none_active_xlAcct=none_active_xlAcct))

# 系统管理 -> 用户管理 -> 删除无矿机的用户
@app.route('/admin/clear_no_device_user', methods=['POST'])
@requires_admin
def admin_clear_no_device_user():
    for b_user in r_session.smembers('users'):
        username = b_user.decode('utf-8')
        accounts_count = r_session.smembers('accounts:%s' % username)
        if accounts_count is None or len(accounts_count) == 0:
             admin_del_user(username)
        return redirect(url_for('admin_user'))

# 系统管理 => 用户管理 => 删除无用户？
@app.route('/del_none_user', methods=['POST'])
@requires_admin
def del_none_user():
    none_active_xlAcct = list()
    for b_user in r_session.smembers('users'):
        username = b_user.decode('utf-8')

        if r_session.smembers('accounts:' + username) is None or len(r_session.smembers('accounts:' + username)) == 0:
            admin_del_user(username)
        has_active_account = False
        for b_xl_account in r_session.smembers('accounts:' + username):
            xl_account = b_xl_account.decode('utf-8')
            account = json.loads(r_session.get('account:%s:%s' % (username, xl_account)).decode('utf-8'))
            if account.get('active'):
                has_active_account = True
                break
        if not has_active_account:
            none_active_xlAcct.append(username)
            admin_del_user(username)
    return redirect(url_for('admin_user'))

# 系统管理 => 通知管理 => 发送通知
@app.route('/admin/message/send', methods=['POST'])
@requires_admin
def admin_message_send():
    to = request.values.get('to')
    subject = request.values.get('subject')
    summary = request.values.get('summary')
    content = request.values.get('content')

    if subject == '':
        session['error_message'] = '标题为必填。'
        return redirect(url_for('admin_message'))

    if to == '':
        session['error_message'] = '收件方必填。'
        return redirect(url_for('admin_message'))

    if summary == '':
        session['error_message'] = '简介必填'
        return redirect(url_for('admin_message'))

    send_content = '{:<30}'.format(summary) + content
    if to == 'all':
        for b_username in r_session.smembers('users'):
            send_msg(b_username.decode('utf-8'), subject, send_content, 3600 * 24 * 7)

    else:
        send_msg(to, subject, send_content, 3600 * 24)

    return redirect(url_for(endpoint='admin_message'))

@app.route('/admin/test_email', methods=['POST'])
@requires_admin
def test_email():
    from mailsand import send_email
    from mailsand import validateEmail
    config_key = '%s:%s' % ('user', 'system')
    config_info = json.loads(r_session.get(config_key).decode('utf-8'))

    user = session.get('user_info')
    user_key = '%s:%s' % ('user', user.get('username'))
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    session['action'] = 'info'
    if 'email' not in user_info.keys() or not validateEmail(user_info["email"]):
       session['error_message']='该账户的提醒邮件地址设置不正确，无法测试'
       return redirect(url_for('system_config'))
    mail = dict()
    mail['to'] = user_info['email']
    mail['subject'] = '云监工-测试邮件'
    mail['text'] = '这只是一个测试邮件，你更应该关注的不是这里面写了什么。不是么？'
    send_email(mail,config_info)
    return redirect(url_for('system_config'))


@app.route('/admin/settings')
@requires_admin
def system_config():
    config_key = '%s:%s' % ('user', 'system')
    config_info = json.loads(r_session.get(config_key).decode('utf-8'))

    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None
    action = None
    if session.get('action') is not None:
        action = session.get('action')
        session['action'] = None

    return render_template('admin_settings.html', user_info=config_info, err_msg=err_msg, action=action)

# 站长交流
@app.route('/talk')
@requires_admin
def admin_talk():

    return render_template('talk.html')

# 站点监控 => 站点记录
@app.route('/guest')
@requires_admin
def admin_guest():
    guest_as = []

    guest_key = 'guest'
    if r_session.get(guest_key) is None:
        r_session.set(guest_key, json.dumps(dict(diary=[])))
    guest_info = json.loads(r_session.get(guest_key).decode('utf-8'))

    for row in guest_info.get('diary'):
        if (datetime.now() - datetime.strptime(row.get('time'), '%Y-%m-%d %H:%M:%S')).days < 2:
            guest_as.append(row)
    guest_as.reverse()

    return render_template('guest.html', guest_as=guest_as)

# 系统管理 => 删除站点记录
@app.route('/guest/delete')
@requires_admin
def admin_guest_delete():

    guest_key = 'guest'
    guest_info = json.loads(r_session.get(guest_key).decode('utf-8'))

    guest_info['diary'] = []

    r_session.set(guest_key, json.dumps(guest_info))

    return redirect(url_for('admin_guest'))

# 站点监控 => 邀请记录
@app.route('/guest/invitation')
@requires_admin
def guest_invitation():
    public_as = []

    public_key = 'invitation'
    if r_session.get(public_key) is None:
        r_session.set(public_key, json.dumps(dict(diary=[])))
    public_info = json.loads(r_session.get(public_key).decode('utf-8'))

    for row in public_info.get('diary'):
        if (datetime.now() - datetime.strptime(row.get('time'), '%Y-%m-%d %H:%M:%S')).days < 7:
            public_as.append(row)
    public_as.reverse()

    return render_template('guest_invitation.html', public_as=public_as)

# 站点监控 => 删除邀请记录
@app.route('/guest/invitation/delete')
@requires_admin
def guest_invitation_delete():

    public_key = 'invitation'
    public_info = json.loads(r_session.get(public_key).decode('utf-8'))

    public_info['diary'] = []

    r_session.set(public_key, json.dumps(public_info))

    return redirect(url_for('guest_invitation'))

# 系统管理 => 关于
@app.route('/about')
@requires_admin
def admin_about():
    import platform
    version = '当前版本：2016-07-15'
    return render_template('about.html', platform=platform, version=version)
