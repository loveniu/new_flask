import logging.handlers
from flask import Flask
from flask import g, render_template
from config import config
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_session import Session
import redis
import logging
from info.utils.common import user_login_data


db = SQLAlchemy()
redis_store = None


def create_app(config_name):
    setup_log(config_name)
    app = Flask(__name__)

    app.config.from_object(config[config_name])

    db.init_app(app)
    # 配置redis
    global redis_store
    redis_store = redis.StrictRedis(host=config[config_name].REDIS_HOST, port=config[config_name].REDIS_PORT,
                                    decode_responses=True)
    # 开启csrf保护
    CSRFProtect(app)
    # 设置session保存位置
    Session(app)

    @app.after_request
    def after_request(response):
        csrf_token = generate_csrf()
        response.set_cookie('csrf_token', csrf_token)
        return response

    # 注册蓝图 首页
    from info.modules.index import index_blu
    app.register_blueprint(index_blu)
    # 登陆注册模块
    from info.modules.passport import passport_blu
    app.register_blueprint(passport_blu)
    # 装饰器
    from info.utils.common import do_index_class
    app.add_template_filter(do_index_class, "indexClass")
    # 新闻详情
    from info.modules.news import news_blu
    app.register_blueprint(news_blu)
    # 个人中心
    from info.modules.profile import profile_blu
    app.register_blueprint(profile_blu)
    # 后台管理
    from info.modules.admin import admin_blu
    app.register_blueprint(admin_blu)

    @app.errorhandler(404)
    @user_login_data
    def page_not_found(e):
        data = {
            "user_info": g.user.to_dict() if g.user else None
        }
        return render_template("news/404.html", data=data)
    return app


def setup_log(config_name):
    # 设置日志的记录等级
    logging.basicConfig(level=config[config_name].LOG_LEVEL)  # 调试debug级
    # 创建日志记录器，指明日志保存的路径、每个日志文件的最大大小、保存的日志文件个数上限
    file_log_handler = logging.handlers.RotatingFileHandler("logs/logs", maxBytes=1024 * 1024 * 100, backupCount=10)
    # 创建日志记录的格式 日志等级 输入日志信息的文件名 行数 日志信息
    formatter = logging.Formatter('%(levelname)s %(filename)s:%(lineno)d %(message)s')
    # 为刚创建的日志记录器设置日志记录格式
    file_log_handler.setFormatter(formatter)
    # 为全局的日志工具对象（flask app使用的）添加日志记录器
    logging.getLogger().addHandler(file_log_handler)
