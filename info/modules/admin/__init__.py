from flask import Blueprint, url_for
from flask import session, redirect, request
from info import user_login_data

admin_blu = Blueprint('admin', __name__, url_prefix="/admin")

from . import views


@admin_blu.before_request
@user_login_data
def before_request():

    if not request.url.endswith(url_for("admin.admin_login")):
        user_id = session.get("user_id", None)
        is_admin = session.get("is_admin", False)
        if (not user_id) or (not is_admin):
            return redirect("/")
