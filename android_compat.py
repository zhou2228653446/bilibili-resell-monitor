# -*- coding: utf-8 -*-
"""Android 平台数据目录适配层。

安卓上应用没有文件系统任意写权限，__file__ 所在目录也是只读的，
必须把数据文件放到应用私有目录（App.user_data_dir）。
桌面端/服务端不受影响（返回 None，沿用原 BASE_DIR 逻辑）。
"""
import os
import sys

IS_ANDROID = sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ or "ANDROID_ENTRYPOINT" in os.environ


def get_data_dir():
    """返回安卓端可写数据目录；非安卓平台返回 None（调用方沿用原路径）。"""
    if not IS_ANDROID:
        return None
    try:
        from jnius import autoclass

        Activity = autoclass("org.kivy.android.PythonActivity")
        return Activity.mActivity.getFilesDir().getAbsolutePath()
    except Exception:
        # python-for-android 也提供环境变量兜底
        home = os.environ.get("HOME") or os.environ.get("ANDROID_APP_PATH")
        if home:
            return home
        return None


def get_out_path(filename):
    """按平台返回数据文件绝对路径。优先查找已有数据，兼顾安卓只读打包目录与私有可写目录。"""
    data_dir = get_data_dir()
    if data_dir is not None:
        target = os.path.join(data_dir, filename)
        if os.path.exists(target):
            return target
        # 若可写目录暂无，检查 APK 解包出的 app 只读资源目录
        app_dir = os.path.dirname(os.path.abspath(__file__))
        app_target = os.path.join(app_dir, filename)
        if os.path.exists(app_target):
            return app_target
        return target
    if os.path.exists(filename):
        return os.path.abspath(filename)
    parent_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", filename)
    if os.path.exists(parent_path):
        return os.path.abspath(parent_path)
    return filename
