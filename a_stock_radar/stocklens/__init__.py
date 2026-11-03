# -*- coding: utf-8 -*-
"""A股雷达 StockLens —— 纯 Python（仅标准库 + Kivy）实现的 A 股个股观察工具。

模块划分：
    config      常量与本地目录
    net         网络请求 + 磁盘缓存（断网可回退旧数据）
    eastmoney   东方财富公开接口封装（行情 / 资金 / 公告 / 新闻）
    models      数据模型
    analyzer    5/10/20/60 日汇总、异动识别、新闻公告关联评分
    service     数据装配（多线程拉取 → StockSnapshot）
    format      展示格式化
    store       自选股本地存储
    ui          Kivy 界面（安卓 APK 使用）
    webui       电脑端预览（标准库 HTTP 服务，可选）
"""

__version__ = "1.0.0"
