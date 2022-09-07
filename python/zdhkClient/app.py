# --*-- Encoding:UTF-8 --*--
#! filename:app.pyw

# * 2651688427
# 主程序

import wx
import ui

if __name__ == "__main__":
  app = wx.App(redirect=False) # 实例化wx应用程序
  window = ui.Window(wx.Frame(None, title="争渡网桌面客户端测试版")) # 实例化主窗口
  app.MainLoop() # 事件循环开始
