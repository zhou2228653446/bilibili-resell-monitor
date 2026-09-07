# -*- coding: utf-8 -*-
"""Android 平台数据目录适配层。

安卓上应用没有文件系统任意写权限，__file__ 所在目录也是只读的，
必须把数据文件放到应用私有目录（App.user_data_dir）。
桌面端/服务端不受影响（返回 None，沿用原 BASE_DIR 逻辑）。
"""
import os
import sys

IS_ANDROID = sys.platform == "android"


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
    """按平台返回数据文件绝对路径。非安卓返回 filename 本身（保持原行为）。"""
    data_dir = get_data_dir()
    if data_dir is None:
        return filename
    return os.path.join(data_dir, filename)
