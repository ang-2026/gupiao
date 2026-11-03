[app]

# 应用名称（安卓桌面显示）
title = A股雷达

# 包名：org.stocklens.stocklens
package.name = stocklens
package.domain = org.stocklens

# 源码目录（本文件所在目录）
source.dir = .

# 打进 APK 的文件类型（.otf 是内置中文字体）
source.include_exts = py,png,jpg,kv,atlas,ttf,otf,json,txt,md

version = 1.0.0

# 只依赖 Kivy + certifi（HTTPS 证书），全部数据接口都用标准库 urllib 访问
requirements = python3,kivy==2.3.1,certifi

# 图标与启动图
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png
presplash.color = #0B0F14

orientation = portrait
fullscreen = 0

# 只需要联网权限
android.permissions = INTERNET, ACCESS_NETWORK_STATE
android.api = 34
android.minapi = 23
android.archs = arm64-v8a
android.numeric_version = 1
android.private_storage = True
android.allow_backup = True
android.accept_sdk_license = True

# 调试包也允许明文？不需要，全部接口都是 HTTPS
android.debug_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
