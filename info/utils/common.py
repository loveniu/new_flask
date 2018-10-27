import functools

from flask import session, current_app, g

import info.constants


def do_index_class(index):
    """自定义过滤器，过滤点击排序html的class"""
    if index == 0:
        return "first"
    elif index == 1:
        return "second"
    elif index == 2:
        return "third"
    else:
        return ""


def user_login_data(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        user_id = None
        try:
            user_id = session.get("user_id")
        except Exception as e:
            current_app.logger.error(e)
        # 通过id获取用户信息
        user = None
        if user_id:
            try:
                from info.models import User
                user = User.query.get(user_id)
            except Exception as e:
                current_app.logger.error(e)
        g.user = user
        return f(*args, **kwargs)

    return wrapper


def news_list_click(function):
    @functools.wraps(function)
    def wraps(*args, **kwargs):
        import info.models
        news_lists = []
        try:
            news_lists = info.models.News.query.order_by(info.models.News.clicks.desc()).limit(
                info.constants.CLICK_RANK_MAX_NEWS)
        except Exception as e:
            current_app.logger.error(e)

        click_news_list = []
        for news in news_lists if news_lists else []:
            click_news_list.append(news.to_basic_dict())
        # try:
        #     news = info.News.query.get(news_id)
        # except Exception as e:
        #     current_app.logger.error(e)

        g.click_news_list = click_news_list
        return function(*args, **kwargs)

    return wraps
