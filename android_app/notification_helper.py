# -*- coding: utf-8 -*-
"""
Android 系统状态栏与通知栏通知助手
支持:
1. Android 8.0+ 官方 NotificationChannel (高优先级、横幅、震动)
2. Android 12+ PendingIntent FLAG_IMMUTABLE 兼容
3. Android 13+ (API 33+) POST_NOTIFICATIONS 动态权限申请
4. 桌面端 / Windows 优雅降级 (日志打印与弹窗提示)
"""
import sys
import time

from android_compat import IS_ANDROID


def request_notification_permission():
    """在 Android 13+ (API 33+) 上动态申请 POST_NOTIFICATIONS 运行时权限。"""
    if not IS_ANDROID:
        return
    try:
        from android.permissions import Permission, request_permissions

        if hasattr(Permission, "POST_NOTIFICATIONS"):
            request_permissions([Permission.POST_NOTIFICATIONS])
            print("[Notification] 已向系统申请 POST_NOTIFICATIONS 权限")
    except Exception as e:
        print(f"[Notification] 申请通知权限遇到异常: {e}")


def send_system_notification(
    title, message, subtext="哔哩捡漏监控", notif_id=1001
):
    """向 Android 系统通知栏推送一条高优先级通知，点击后唤醒并回到应用。"""
    print(f"[Notification] 准备推送系统通知: {title} - {message}")

    if not IS_ANDROID:
        print(f"[Desktop Fallback Notification] [{title}] {message}")
        return True

    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        context = PythonActivity.mActivity
        if not context:
            print("[Notification] mActivity 暂未就绪，取消推送")
            return False

        Context = autoclass("android.content.Context")
        NotificationManager = autoclass("android.app.NotificationManager")
        notification_service = context.getSystemService(
            Context.NOTIFICATION_SERVICE
        )

        channel_id = "bili_resell_alerts_v1"
        channel_name = "B站转售捡漏与降价提醒"

        # Android 8.0+ (API 26+) 必须创建 NotificationChannel
        try:
            NotificationChannel = autoclass("android.app.NotificationChannel")
            importance = NotificationManager.IMPORTANCE_HIGH
            channel = NotificationChannel(channel_id, channel_name, importance)
            channel.setDescription("实时推送低于市集成交价的超值好物与大幅降价商品")
            channel.enableVibration(True)
            channel.setShowBadge(True)
            notification_service.createNotificationChannel(channel)
        except Exception as ce:
            print(f"[Notification] NotificationChannel 初始化提示: {ce}")

        # 构造 Notification.Builder
        NotificationBuilder = autoclass("android.app.Notification$Builder")
        builder = NotificationBuilder(context, channel_id)

        # 文本与标题
        builder.setContentTitle(str(title))
        builder.setContentText(str(message))
        if subtext:
            builder.setSubText(str(subtext))

        # 大文本样式 (防止较长内容被系统截断)
        try:
            BigTextStyle = autoclass(
                "android.app.Notification$BigTextStyle"
            )
            big_style = BigTextStyle()
            big_style.setBigContentTitle(str(title))
            big_style.bigText(str(message))
            builder.setStyle(big_style)
        except Exception:
            pass

        # 设置小图标 (使用 App 自身图标)
        app_info = context.getApplicationInfo()
        icon_id = app_info.icon
        builder.setSmallIcon(icon_id)
        builder.setAutoCancel(True)
        builder.setWhen(int(time.time() * 1000))

        # 点击通知唤起应用 Intent
        Intent = autoclass("android.content.Intent")
        PendingIntent = autoclass("android.app.PendingIntent")
        intent = Intent(context, PythonActivity)
        intent.setFlags(
            Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP
        )

        # Android 12+ (API 31+) 必须指定 FLAG_IMMUTABLE (0x04000000)
        flags = PendingIntent.FLAG_UPDATE_CURRENT
        try:
            flags |= 0x04000000  # FLAG_IMMUTABLE
        except Exception:
            pass

        pending_intent = PendingIntent.getActivity(
            context, notif_id, intent, flags
        )
        builder.setContentIntent(pending_intent)

        # 发出通知
        notification = builder.build()
        notification_service.notify(notif_id, notification)
        print(f"[Notification] 成功弹出系统通知 ID={notif_id}")
        return True

    except Exception as e:
        print(f"[Notification] 推送系统通知失败: {e}", file=sys.stderr)
        return False
