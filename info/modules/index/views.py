import info.constants
import info.utils.common
from info.models import News, Category, User
from info.utils.response_code import RET
from . import index_blu
from flask import render_template, jsonify
from flask import current_app
from flask import session, request, g
from info.utils.common import user_login_data, news_list_click


@index_blu.route("/newslist")
def news_list():
    """
    获取指定分类的新闻列表
    1. 获取参数
    2. 校验参数
    3. 查询数据
    4. 返回数据
    :return:
    """
    # 1.获取参数
    args_dict = request.args
    page = args_dict.get("page", "1")
    per_page = args_dict.get("per_page", 10)
    category_id = args_dict.get("cid", "1")
    # 校验参数
    try:
        page = int(page)
        category_id = int(category_id)
        per_page = int(per_page)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    # 3. 查询数据并分页

    filters = [News.status == 0]
    # 如果分类id不为1，那么添加分类id的过滤
    if category_id != 1:
        # print(category_id)
        filters.append(info.models.News.category_id == category_id)
    try:
        paginate = News.query.filter(*filters).order_by(News.create_time.desc()).paginate(page, per_page, False)

        # 获取查询出来的数据
        items = paginate.items

        # 获取到总页数
        total_page = paginate.pages

        current_page = paginate.page

    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据查询失败")

    news_li = []
    for news in items:
        news_li.append(news.to_basic_dict())
    # 4. 返回数据
    return jsonify(errno=RET.OK, errmsg="OK", totalPage=total_page, currentPage=current_page, newsList=news_li,
                   cid=category_id)


@index_blu.route("/")
@user_login_data
@news_list_click
def index():
    # 新闻排行

    # 获取新闻分类数据
    categories = Category.query.all()
    # 定义列表保存分类数据
    categories_dicts = []

    for category in categories:
        # 拼接内容
        categories_dicts.append(category.to_dict())

    data = {
        "user_info": g.user.to_dict() if g.user else None,
        "click_news_list": g.click_news_list,
        "categories": categories_dicts
    }
    return render_template('news/index.html', data=data)


@index_blu.route('/favicon.ico')
def favicon():
    return current_app.send_static_file('news/favicon.ico')


