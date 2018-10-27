import datetime
import time
from info.utils.response_code import RET
from datetime import timedelta, datetime
from flask import session, g
from flask import current_app, redirect, url_for
from flask import request
from flask import render_template, jsonify
from info import constants, db
from info import user_login_data
from info.models import User, News, Category
from info.modules.admin import admin_blu
from info.utils.image_storage import storage


@admin_blu.route("/login", methods=["GET", "POST"])
@user_login_data
def admin_login():
    if request.method == "GET":
        user_id = session.get("user_id", None)
        is_admin = session.get("is_admin", False)
        if user_id and is_admin:
            return redirect(url_for("admin.admin_index"))
        return render_template("admin/login.html")
    username = request.form.get("username")
    password = request.form.get("password")
    if not all([username, password]):
        return render_template("admin/login.html", errmsg="参数不足")

    try:
        users = User.query.filter(User.mobile == username).first()
    except Exception as e:
        current_app.logger.error(e)
        return render_template("admin/login.html", errmsg="查询错误")

    if not users:
        return render_template("admin/login.html", errmsg="用户不存在")

    if not users.check_password(password):
        return render_template("admin/login.html", errmsg="密码错误")

    if not users.is_admin:
        return render_template("admin/login.html", errmsg="用户权限错误")

    session["user_id"] = users.id
    session["nick_name"] = users.nick_name
    session["mobile"] = users.mobile
    session["is_admin"] = True

    return redirect(url_for("admin.admin_index"))


@admin_blu.route("/index")
@user_login_data
def admin_index():
    user = g.user
    return render_template("admin/index.html", user=user.to_dict())


@admin_blu.route('/user_count')
def user_count():
    # 查询总人数
    total_count = 0
    try:
        total_count = User.query.filter(User.is_admin == False).count()
    except Exception as e:
        current_app.logger.error(e)

    # 查询月新增数
    mon_count = 0
    try:
        now = time.localtime()
        mon_begin = '%d-%02d-01' % (now.tm_year, now.tm_mon)
        mon_begin_date = datetime.strptime(mon_begin, "%Y-%m-%d")
        mon_count = User.query.filter(User.is_admin == False, User.create_time >= mon_begin_date).count()
    except Exception as e:
        current_app.logger.error(e)
    # 查询日新增数
    day_count = 0
    try:
        day_begin = "%d-%02d-%02d" % (now.tm_year, now.tm_mon, now.tm_mday)
        day_begin_date = datetime.strptime(day_begin, "%Y-%m-%d")
        day_count = User.query.filter(User.is_admin == False, User.create_time >= day_begin_date).count()
    except Exception as e:
        current_app.logger.error(e)

    # 查询图表信息
    # 获取到当天00:00:00时间
    now_date = datetime.strptime(datetime.now().strftime("%Y-%m-%d"), "%Y-%m-%d")

    # 定义空数组，保存数据
    active_date = []
    active_count = []

    # 依次添加数据，再反转

    for i in range(0, 31):
        begin_date = now_date - timedelta(days=i)
        end_date = now_date + timedelta(days=1)
        active_date.append(begin_date.strftime("%Y-%m-%d"))
        count = 0
        try:
            count = User.query.filter(User.is_admin == False, User.last_login >= day_begin,
                                      User.last_login < end_date).count()
        except Exception as e:
            current_app.logger.error(e)

        active_count.append(count)

    active_count.reverse()
    active_date.reverse()

    data = {
        "total_count": total_count,
        "mon_count": mon_count,
        "day_count": day_count,
        "active_date": active_date,
        "active_count": active_count
    }
    return render_template("admin/user_count.html", data=data)


@admin_blu.route("/user_list")
def user_list():
    """获取用户列表"""
    page = request.args.get("p", 1)
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

        paginate = User.query.filter(User.is_admin == False) \
            .order_by(User.last_login.desc()) \
            .paginate(page, constants.ADMIN_USER_PAGE_MAX_COUNT, False)
        # 获取分页数据
        collections = paginate.items
        current_page = paginate.page
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    # 收藏列表
    collection_dict_list = []
    for user in collections:
        collection_dict_list.append(user.to_admin_dict())

    data = {
        "total_page": total_page,
        "current_page": current_page,
        "users": collection_dict_list
    }

    return render_template("admin/user_list.html", data=data)


@admin_blu.route("/news_review")
def news_review():
    """返回待审核新闻列表"""
    page = request.args.get("p", 1)
    keywords = request.args.get("keywords", "")
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
        filters = [News.status != 0]
        if keywords:
            filters.append(News.contains(keywords))

        paginate = News.query.filter(*filters) \
            .order_by(News.create_time.desc()). \
            paginate(page, constants.ADMIN_NEWS_PAGE_MAX_COUNT, False)
        # 获取分页数据
        collections = paginate.items
        current_page = paginate.page
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    # 列表
    collection_dict_list = []
    for news in collections:
        collection_dict_list.append(news.to_review_dict())

    data = {
        "total_page": total_page,
        "current_page": current_page,
        "news_list": collection_dict_list
    }

    return render_template("admin/news_review.html", data=data)


@admin_blu.route("/news_review_detail")
def news_review_detail():
    """新闻审核"""
    # if request.method == "GET":
    news_id = request.args.get("news_id")
    if not news_id:
        return render_template("admin/news_review_detail.html", data={"errmsg": "未查询到此新闻"})
    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)

    if not news:
        return render_template("admin/news_review_detail.html", data={"errmsg": "未查询到此新闻"})

    data = {
        "news": news.to_dict()
    }
    return render_template("admin/news_review_detail.html", data=data)


@admin_blu.route("/news_review_add", methods=["POST"])
def news_review_add():
    news_id = request.json.get("news_id")
    action = request.json.get("action")

    if not all([news_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    if action not in ("accept", "reject"):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)

    if not news:
        return jsonify(errno=RET.NODATA, errmsg="未查询到数据")

    if action == "accept":
        news.status = 0
    else:
        reason = request.json.get("reason")

        if not reason:
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

        news.reason = reason
        news.status = -1

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="数据保存失败")
    return jsonify(errno=RET.OK, errmsg="操作成功")


@admin_blu.route("/news_edit")
def news_edit():
    # 新闻编辑
    page = request.args.get("p", 1)
    keywords = request.args.get("keywords", "")
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
        filters = [News.status != 0]
        if keywords:
            filters.append(News.contains(keywords))

        paginate = News.query.filter(*filters) \
            .order_by(News.create_time.desc()). \
            paginate(page, constants.ADMIN_NEWS_PAGE_MAX_COUNT, False)
        # 获取分页数据
        collections = paginate.items
        current_page = paginate.page
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    # 收藏列表
    collection_dict_list = []
    for news in collections:
        collection_dict_list.append(news.to_review_dict())

    data = {
        "total_page": total_page,
        "current_page": current_page,
        "news_list": collection_dict_list
    }
    return render_template("admin/news_edit.html", data=data)


@admin_blu.route("/news_edit_detail", methods=["GET", "POST"])
def news_edit_detail():
    """新闻编辑详情"""
    if request.method == "GET":
        news_id = request.args.get("news_id")
        if not news_id:
            return render_template("admin/news_edit_detail.html", data={"errmsg": "未查询到此新闻"})
        news = None
        try:
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)

        if not news:
            return render_template("admin/news_edit_detail.html", data={"errmsg": "未查询到此新闻"})

        categories = Category.query.all()
        categories_li = []
        for category in categories:
            c_dict = category.to_dict()
            c_dict["is_selected"] = False
            if category.id == news.category_id:
                c_dict["is_selected"] = True
            categories_li.append(c_dict)

        categories_li.pop(0)

        data = {
            "news": news.to_dict(),
            "categories": categories_li
        }
        return render_template("admin/news_edit_detail.html", data=data)
        # 获取参数
    news_id = request.form.get("news_id")
    title = request.form.get("title")
    category_id = request.form.get("category_id")
    digest = request.form.get("digest")
    index_image = request.files.get("index_image")
    content = request.form.get("content")

    if not all([title, news_id, category_id, digest, content]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)

    if not news:
        return jsonify(errno=RET.NODATA, errmsg="未查询到新闻数据")

    if index_image:
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
        news.index_image_url = constants.QINIU_DOMIN_PREFIX + url

    news.title = title
    news.digest = digest
    news.content = content
    news.category_id = category_id

    # 保存到数据库
    try:
        db.session.add(news)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")
    return jsonify(errno=RET.OK, errmsg="发布成功，等待审核")


@admin_blu.route("/news_category")
def news_type():
    categories = Category.query.all()
    categories_li = []

    for category in categories:
        cate_dict = category.to_dict()
        categories_li.append(cate_dict)

    categories_li.pop(0)

    return render_template("admin/news_type.html", data={"categories": categories_li})


@admin_blu.route("/add_category", methods=["POST"])
def add_category():
    """修改或者添加分类"""
    category_id = request.json.get("id")
    category_name = request.json.get("name")

    if not category_name:
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    # 判断是否有分类id
    if category_id:
        try:
            category = Category.query.get(category_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询数据失败")
        if not category:
            return jsonify(errno=RET.NODATA, errmsg="未查询到分类信息")

        category.name = category_name
    else:
        # 如果没有分类id，则是添加分类
        category = Category()
        category.name = category_name
        db.session.add(category)
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")
    return jsonify(errno=RET.OK, errmsg="保存数据成功")
