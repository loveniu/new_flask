from info.models import Category, News, User
from info.utils.image_storage import storage
from flask import redirect, session
from . import profile_blu
from info.utils.common import user_login_data
from flask import request, g, render_template, abort
from info import db
from flask import current_app, jsonify
from info.utils.response_code import RET
from info import constants


@profile_blu.route("/info")
@user_login_data
def get_user_info():
    user = g.user
    if not user:
        return redirect("/")

    data = {
        "user_info": user.to_dict()
    }
    return render_template("news/user.html", data=data)


@profile_blu.route("pic_info", methods=["GET", "POST"])
@user_login_data
def pic_info():
    # 更换头像
    user = g.user
    if request.method == "GET":
        data = {
            "user_info": user.to_dict()
        }
        return render_template("news/user_pic_info.html", data=data)
    try:
        avatar_file = request.files.get("avatar").read()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="读取文件出错")
    # 上传文件
    try:
        url = storage(avatar_file)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="上传图片错误")

        # 将头像信息更新到当前用户的模型中
        # 设置用户模型相关数据
    user.avatar_url = url
    # 将数据保存到数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存用户数据错误")

    return jsonify(errno=RET.OK, errmsg="OK", data={'avatar_url': constants.QINIU_DOMIN_PREFIX + url})


@profile_blu.route("base_info", methods=["GET", "POST"])
@user_login_data
def base_info():
    """
      用户基本信息
      1. 获取用户登录信息
      2. 获取到传入参数
      3. 更新并保存数据
      4. 返回结果
      :return:
      """
    if request.method == "GET":
        data = {
            "user_info": g.user.to_dict()
        }
        return render_template("news/user_base_info.html", data=data)

    data_dict = request.json
    nick_name = data_dict.get("nick_name")
    gender = data_dict.get("gender")
    signature = data_dict.get("signature")

    if not all([nick_name, gender, signature]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

    if gender not in (['MAN', 'WOMAN']):
        return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

    # 更新并保存数据

    g.user.nick_name = nick_name
    g.user.gender = gender
    g.user.signature = signature

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")

    # 将 session 中保存的数据进行实时更新
    session["nick_name"] = nick_name
    session["signature"] = signature
    session["gender"] = gender
    return jsonify(errno=RET.OK, errmsg="更新成功")


@profile_blu.route("pass_info", methods=["GET", "POST"])
@user_login_data
def pass_info():
    """密码修改"""
    if request.method == "GET":
        return render_template("news/user_pass_info.html")
    # 参数获取
    old_password = request.json.get("old_password")
    new_password = request.json.get("new_password")

    if not all([old_password, new_password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

    if not g.user.check_password(old_password):
        return jsonify(errno=RET.PWDERR, errmsg="原密码错误")

    # 更新数据
    g.user.password = new_password

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")
    return jsonify(errno=RET.OK, errmsg="保存成功")


@profile_blu.route("collection")
@user_login_data
def user_collection():
    # 新闻收藏
    # 获取参数
    page = request.args.get("page", 1)
    try:
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        page = 1

    collections = []
    current_page = 1
    total_page = 1

    try:
        # 进行分页数据查询
        paginate = g.user.collection_news.paginate(page, constants.USER_COLLECTION_MAX_NEWS, False)
        # 获取分页数据
        collections = paginate.items
        current_page = paginate.page
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    # 收藏列表
    collection_dict_list = []
    for news in collections:
        collection_dict_list.append(news.to_basic_dict())

    data = {
        "total_page": total_page,
        "current_page": current_page,
        "collections": collection_dict_list
    }

    return render_template("news/user_collection.html", data=data)


@profile_blu.route("/news_release", methods=["GET", "POST"])
@user_login_data
def news_release():
    # 新闻发布
    if request.method == "GET":
        categories = []
        try:
            categories = Category.query.all()
        except Exception as e:
            current_app.logger.error(e)
        # 定义列表保存分类数据
        categories_dict = []
        for category in categories:
            cate_dict = category.to_dict()
            categories_dict.append(cate_dict)
        # 移除`最新`分类
        categories_dict.pop(0)

        return render_template("news/user_news_release.html", data={"categories": categories_dict})

    # 获取参数
    title = request.form.get("title")
    source = "个人发布"
    category_id = request.form.get("category_id")
    digest = request.form.get("digest")
    index_image = request.files.get("index_image")
    content = request.form.get("content")

    if not all([title, source, category_id, digest, index_image, content]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

    try:
        avatar_file = index_image.read()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="读取文件出错")

    try:
        url = storage(avatar_file)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="上传图片错误")

    news = News()
    news.source = source
    news.title = title
    news.digest = digest
    news.content = content
    news.index_image_url = constants.QINIU_DOMIN_PREFIX + url
    news.category_id = int(category_id)
    news.user_id = int(g.user.id)
    # 1代表待审核状态
    news.status = 1

    # 保存到数据库
    try:
        db.session.add(news)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")
    return jsonify(errno=RET.OK, errmsg="发布成功，等待审核")


@profile_blu.route("/news_list")
@user_login_data
def news_list():
    # 新闻列表
    page = request.args.get("page", 1)
    try:
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        page = 1

    collections = []
    current_page = 1
    total_page = 1

    try:
        # 进行分页数据查询
        paginate = News.query.filter(News.user_id == g.user.id).paginate(page, constants.USER_COLLECTION_MAX_NEWS,
                                                                         False)
        # 获取分页数据
        collections = paginate.items
        current_page = paginate.page
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    # 收藏列表
    news_list = []
    for news in collections:
        news_list.append(news.to_basic_dict())

    data = {
        "total_page": total_page,
        "current_page": current_page,
        "news_list": news_list
    }

    return render_template("news/user_news_list.html", data=data)


@profile_blu.route("/user_follow")
@user_login_data
def user_follow():
    # 我的关注
    # 获取参数
    page = request.args.get("page", 1)
    try:
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        page = 1

    follows = []
    current_page = 1
    total_page = 1

    try:
        # 进行分页数据查询
        paginate = g.user.followed.paginate(page, constants.USER_FOLLOWED_MAX_COUNT, False)
        # 获取分页数据
        follows = paginate.items
        current_page = paginate.page
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    # 收藏列表
    follow_dict_list = []
    for follows_user in follows:
        follow_dict_list.append(follows_user.to_dict())

    data = {
        "total_page": total_page,
        "current_page": current_page,
        "users": follow_dict_list
    }

    return render_template("news/user_follow.html", data=data)


@profile_blu.route("/other_info")
@user_login_data
def other_info():
    """查看其他用户信息"""
    user = g.user

    # 获取其他用户id
    user_id = request.args.get("id")
    if not user_id:
        abort(404)
    # 查询用户模型
    other = None

    try:
        other = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)

    if not other:
        abort(404)

    # 判断当前登录用户是否关注过该用户

    is_followed = False

    if g.user:
        if other in g.user.followed:
            is_followed = True

    # 组织数据，并返回

    data = {
        "user_info": user.to_dict(),
        "other_info": other.to_dict(),
        "is_followed": is_followed
    }

    return render_template("news/other.html", data=data)


@profile_blu.route("/other_news_list")
def other_news_list():
    # 获取参数
    page = request.args.get("p", 1)
    user_id = request.args.get("user_id")

    try:
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    if not all([page, user_id]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据查询错误")

    if not user:
        return jsonify(errno=RET.NODATA, errmsg="用户不存在")

    try:
        # 进行分页数据查询
        paginate = News.query.filter(News.user_id == user.id).paginate(page, constants.USER_FOLLOWED_MAX_COUNT, False)
        # 获取分页数据
        news_li = paginate.items

        current_page = paginate.page

        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    # 收藏列表
    news_dict_li = []
    for news_item in news_li:
        news_dict_li.append(news_item.to_review_dict())

    data = {
        "total_page": total_page,
        "current_page": current_page,
        "news_list": news_dict_li
    }

    return jsonify(errno=RET.OK, errmsg="OK", data=data)
