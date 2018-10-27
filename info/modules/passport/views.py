import random
import re
import logging
import datetime

from flask import session, current_app
from flask import make_response, request, jsonify
from info.lib.yuntongxun.sms import CCP
from info.models import User
from info import create_app, db
from info import constants
from info import redis_store
from info.utils.captcha.captcha import captcha
from info.utils.response_code import RET

from . import passport_blu


@passport_blu.route("/logout", methods=["POST"])
def logout():
    """
    清楚session中保存的登陆信息
    :return:
    """
    session.pop("user_id", None)
    session.pop("nick_name", None)
    session.pop("mobile", None)
    session.pop("is_admin", None)

    return jsonify(errno=RET.OK, errmsg="OK")


@passport_blu.route("/login", methods=["POST"])
def login():
    """
    用户登陆
    """
    # 获取参数
    args_data = request.json
    mobile = args_data.get("mobile")
    password = args_data.get('password')
    if not all([mobile, password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")
    # 验证手机号码
    if not (re.match("^1[3578][0-9]{9}$", mobile) or mobile == "admin"):
        return jsonify(errno=RET.DATAERR, errmsg='手机号不正确')

    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.errno(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")

    if not user:
        return jsonify(errno=RET.USERERR, errmsg="用户不存在")

    if not user.check_password(password):
        return jsonify(errno=RET.PWDERR, errmsg="密码错误")

    # 保存用户登录状态

    # 记录最后一次登录时间
    User.last_login = datetime.datetime.now()
    # try:
    #     db.session.commit()
    # except Exception as e:
    #     db.session.rollback()
    #     current_app.logger.errno(e)
    #     return jsonify(errno=RET.DATAERR, errmsg="数据保存错误")

    session["user_id"] = user.id
    session['nick_name'] = user.nick_name
    session['mobile'] = user.mobile

    # 6. 返回登陆结果
    return jsonify(errno=RET.OK, errmsg="登陆成功")


@passport_blu.route("/image_code")
def get_image_code():
    """
    获取图片验证码
    """

    # 1.获取参数
    code_id = request.args.get("imageCodeId")
    # 2.生成验证码
    name, text, image = captcha.generate_captcha()

    print(text)

    # 3.保存当前验证码
    try:
        redis_store.set('ImageCode_' + code_id, text, constants.IMAGE_CODE_REDIS_EXPIRES)
    except Exception as e:
        current_app.logger.errno(e)
        return make_response(jsonify(errno=RET.DATAERR, errmsg='保存图片验证码失败'))

    # 5.响应反回
    resp = make_response(image)
    resp.headers['Content-Type'] = 'image/jpg'

    return resp


@passport_blu.route("/smscode", methods=["POST"])
def send_ams():
    """
      1. 接收参数并判断是否有值
      2. 校验手机号是正确
      3. 通过传入的图片编码去redis中查询真实的图片验证码内容
      4. 进行验证码内容的比对
      5. 生成发送短信的内容并发送短信
      6. redis中保存短信验证码内容
      7. 返回发送成功的响应
      :return:
    """
    args_data = request.json
    mobile = args_data.get("mobile")
    image_code = args_data.get('image_code')
    image_code_id = args_data.get('image_code_id')
    # print(image_code_id)
    # 1.接收参数并判断是否有值
    if not all([mobile, image_code, image_code_id]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")
    # 2.校验手机号是正确
    # print(mobile)
    if not re.match("^1[3578][0-9]{9}$", mobile):
        return jsonify(errno=RET.DATAERR, errmsg='手机号不正确')
    # 3.通过传入的图片编码去redis中查询真实的图片验证码内容
    try:
        real_image_code = redis_store.get('ImageCode_' + image_code_id)
        # 如果能够取出来值，删除redis中缓存的内容
        # if real_image_code:
        #     real_image_code = real_image_code.decode()
        #     redis_store.delete('ImageCode_' + image_code_id)
    except Exception as e:
        current_app.logger.errno(e)
        return jsonify(errno=RET.DBERR, errmsg="获取图片验证码失败")
    # 判断验证码是否存在，已过期
    if not real_image_code:
        return jsonify(errno=RET.NODATA, errmsg="验证码已过期")

    # 4. 进行验证码内容的比对

    if real_image_code.lower() != image_code.lower():
        return jsonify(errno=RET.DATAERR, errmsg="验证码输入错误")
        # 4.1 校验该手机是否已经注册
    try:
        use = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.errno(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")
    if use:
        return jsonify(errno=RET.DATAEXIST, errmsg="该手机已被注册")
    # 5. 生成发送短信的内容并发送短信
    result = random.randint(0, 999999)
    sms_code = '%06d' % result
    current_app.logger.debug("短信验证码的内容：%s" % sms_code)
    result = CCP().send_template_sms(mobile, [sms_code, 5], "1")
    print(sms_code)
    if result != 0:
        return jsonify(errno=RET.THIRDERR, errmsg="发送短信失败")

    # 6.redis中保存短信验证码内容
    try:
        redis_store.set("sms_" + mobile, sms_code, constants.SMS_CODE_REDIS_EXPIRES)
    except Exception as e:
        current_app.logger.errno(e)
        return jsonify(errno=RET.DBERR, errmsg="保存短信验证码失败")
    # 7. 返回发送成功的响应
    return jsonify(errno=RET.OK, errmsg="发送成功")


@passport_blu.route("/register", methods=["POST"])
def register():
    """
    注册
    :return:
    """
    # 获取参数
    json_data = request.json
    mobile = json_data.get("mobile")
    smscode = json_data.get('smscode')
    password = json_data.get('password')
    print(mobile)
    if not all([mobile, smscode, password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")
    # 短信验证码
    try:
        real_sms_code = redis_store.get("sms_" + mobile)
    except Exception as e:
        current_app.logger.errno(e)
        return jsonify(errno=RET.DBERR, errmsg="获取本地验证码失败")
    print(real_sms_code)
    if not real_sms_code:
        return jsonify(errno=RET.DATAEXIST, errmsg="验证码已过期")
    if real_sms_code != smscode:
        return jsonify(errno=RET.DATAERR, errmsg="短信验证码错误")
    # 删除短信验证码
    try:
        redis_store.delete("sms_" + mobile)
    except Exception as e:
        create_app.logger.errno(e)
        # pass

    # 4. 初始化 user 模型，并设置数据

    user = User()
    user.nick_name = mobile
    user.mobile = mobile

    user.last_login = datetime.datetime.now()
    # 密码哈希加密
    user.password = password
    # 添加到数据库
    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.errno(e)
        return jsonify(errno=RET.DATAERR, errmsg="数据保存错误")
    # 5. 保存用户登录状态
    session["user_id"] = user.id
    session['nick_name'] = user.nick_name
    session['mobile'] = user.mobile
    # 6. 返回注册结果
    return jsonify(errno=RET.OK, errmsg="注册成功")
