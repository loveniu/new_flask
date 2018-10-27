from flask import current_app, abort, jsonify
from flask import request, g, render_template
from info import db
from info.utils.response_code import RET
from info.utils.common import user_login_data, news_list_click
from info.models import News, Comment, CommentLike, User
from . import news_blu


@news_blu.route("/<int:news_id>")
@user_login_data
@news_list_click
def news_detail(news_id):
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        abort(404)
    if not news:
        # 返回数据未找到的页面
        abort(404)
    news.clicks += 1
    # 新闻排行

    # 当前登录用户是否关注当前新闻作者
    is_followed = False
    # print(news.user.followers.filter(User.id == g.user.id).count() > 0)

    # 判断是否收藏该新闻
    is_collected = False
    if g.user:
        if news in g.user.collection_news:
            is_collected = True
        if news.user:
            if news.user in g.user.followed:
                is_followed = True

    # 获取当前新闻的评论
    comments = None
    try:
        comments = Comment.query.filter(Comment.news_id == news_id).order_by(Comment.create_time.desc()).all()
    except Exception as e:
        current_app.logger.error(e)

    comment_like_ids = []
    if g.user:
        try:
            comment_ids = [comment.id for comment in comments]
            # 取到当前用户在当前新闻的所有评论点赞的记录
            if len(comment_ids) > 0:
                comment_likes = CommentLike.query.filter(CommentLike.comment_id.in_(comment_ids),
                                                         CommentLike.user_id == g.user.id).all()
                # 取出记录中所有的评论id
                comment_like_ids = [comment_like.comment_id for comment_like in comment_likes]

        except Exception as e:
            current_app.logger.error(e)

    comment_list = []
    for items in comments if comments else []:
        comment_dict = items.to_dict()
        comment_dict["is_like"] = False
        try:
            # 判断用户是否点赞该评论
            if g.user.id and items.id in comment_like_ids:
                comment_dict["is_like"] = True
        except Exception as e:
            current_app.logger.error(e)
        comment_list.append(comment_dict)

    data = {
        "is_followed": is_followed,
        'is_collected': is_collected,
        "user_info": g.user.to_dict() if g.user else None,
        "news": news.to_dict(),
        "click_news_list": g.click_news_list,
        "comments": comment_list
    }
    return render_template("news/detail.html", data=data)


@news_blu.route("/news_collect", methods=["POST"])
@user_login_data
def news_collect():
    """新闻收藏"""
    user = g.user
    json_data = request.json
    news_id = json_data.get("news_id")
    action = json_data.get("action")

    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    if not news_id:
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    if action not in ("collect", "cancel_collect"):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

    if not news:
        return jsonify(errno=RET.NODATA, errmsg="新闻数据不存在")

    if action == "collect":
        user.collection_news.append(news)
    else:
        user.collection_news.remove(news)

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存失败")
    return jsonify(errno=RET.OK, errmsg="操作成功")


@news_blu.route("/news_comment", methods=["POST"])
@user_login_data
def add_news_comment():
    """添加评论"""
    user = g.user
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
    json_data = request.json
    news_id = json_data.get("news_id")
    comment_str = json_data.get("comment")
    parent_id = json_data.get("parent_id")

    if not all([news_id, comment_str]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

    if not news:
        return jsonify(errno=RET.NODATA, errmsg="新闻不存在")

    comment = Comment()
    comment.user_id = user.id
    comment.news_id = news_id
    comment.content = comment_str
    if parent_id:
        comment.parent_id = parent_id

    try:
        db.session.add(comment)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="保存评论失败")
    return jsonify(errno=RET.OK, errmsg="评论成功", data=comment.to_dict())


@news_blu.route("/comment_like", methods=["POST"])
@user_login_data
def set_comment_like():
    """评论点赞"""

    if not g.user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    comment_id = request.json.get("comment_id")
    news_id = request.json.get("news_id")
    action = request.json.get("action")

    if not all([news_id, comment_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    if action not in ("add", "remove"):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    try:
        comment_id = int(comment_id)
        news_id = int(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 查询评论数据
    try:
        comment = Comment.query.get(comment_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

    if not comment:
        return jsonify(errno=RET.NODATA, errmsg="评论数据不存在")

    if action == "add":
        comment_like = CommentLike.query.filter_by(comment_id=comment_id, user_id=g.user.id).first()

        if not comment_like:
            comment_like = CommentLike()
            comment_like.comment_id = comment_id
            comment_like.user_id = g.user.id
            db.session.add(comment_like)

            comment.like_count += 1
    # 删除点赞
    else:
        comment_like = CommentLike.query.filter_by(comment_id=comment_id, user_id=g.user.id).first()

        if comment_like:
            db.session.delete(comment_like)

            comment.like_count -= 1

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="操作失败")
    return jsonify(errno=RET.OK, errmsg="操作成功")


@news_blu.route("/followed_user", methods=["POST"])
@user_login_data
def followed_user():
    """关注/取消关注用户"""
    if not g.user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    user_id = request.json.get("user_id")
    action = request.json.get("action")

    if not all([user_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    if action not in ("follow", "unfollow"):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 查询到关注的用户信息
    try:
        target_user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据库失败")

    if not target_user:
        return jsonify(errno=RET.NODATA, errmsg="未查询到用户数据")

    # if action == "follow":
    #     if target_user.followers.filter(User.id == g.user.id).count()>0:
    #         return jsonify(errno=RET.DATAEXIST, errmsg="当前已关注")
    #     target_user.followers.append(g.user)
    # else:
    #     if target_user.followers.filter(User.id == g.user.id).count()>0:
    #         target_user.followers.remove(g.user)

    if action == "follow":
        if target_user not in g.user.followed:
            g.user.followed.append(target_user)
        else:
            return jsonify(errno=RET.DATAEXIST, errmsg="用户已被关注")
    else:
        if target_user in g.user.followed:
            g.user.followed.remove(target_user)
        else:
            return jsonify(errno=RET.DATAEXIST, errmsg="用户未被关注")
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据保存错误")

    return jsonify(errno=RET.OK, errmsg="操作成功")

