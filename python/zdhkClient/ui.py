# --*-- Encoding:UTF-8 --*--
#! filename:ui.py

# * 2651688427
# 主要实现了图形用户界面

import wx # 使用pip install wxpython来安装
import zdclient

# 主界面
class Window(wx.Panel):
  def __init__(self, frame):
    wx.Panel.__init__(self, frame)
    self.frame = frame
    self.listBox = wx.ListBox(self) # 列表框，展示主题和回帖
    self.listBox.Bind(wx.EVT_KEY_UP, self.OnThreadListBoxKeyUp) # 绑定键盘松开某键世界处理函数
    self.listBox.Bind(wx.EVT_LISTBOX, self.OnListBox) # 绑定列表框当前选择项目改变事件处理函数
    self.loginBtn = wx.Button(self, label="登录(&L)")
    self.postBtn = wx.Button(self, label="发表新贴(&P)")
    self.postBtn.Bind(wx.EVT_BUTTON, self.OnPost)
    self.OnUserStatus() # 根据登录状态来改变， 参看详细定义部分

    self.frame.Show(True) # 显示主窗口

    self.curContent = zdclient.getThread() #  请求争渡网首页
    self.backContent = None # 用来备份主题贴子列表
    self.Display() # 列表框上展示首页的内容


  # 键盘松开某个按键
  def OnThreadListBoxKeyUp(self, event):
    listBox = event.GetEventObject()
    if event.GetKeyCode() == wx.WXK_RETURN and "threadlist" in self.curContent: # 在主题上按下回车
      try:
        self.backContent = self.curContent # 备份主题数据， 
        tid = self.curContent["threadlist"][self.listBox.Selection]["tid"] # 获取当前选择的主题的tid
        self.curContent = zdclient.getPost(tid = tid) # 获取某个主题的详细内容
      except KeyError:
        self.backContent = None
        pageNumber = self.curContent["threadlist"][self.curContent["index"]]["pageNumber"]
        if pageNumber == 0:
          numberInputDialog = NumberInputDialog(self.frame, title="输入页数", range=(1, 5000))
          if numberInputDialog.ShowModal() == wx.ID_OK:
            pageNumber = numberInputDialog.result

          numberInputDialog.Destroy()

        if pageNumber == 0:
          return

        self.curContent = zdclient.getThread(pageNumber)

      self.Display() # 在列表框上展示上面获取的内容
    elif event.GetKeyCode() == wx.WXK_RETURN and "postlist" in self.curContent: # 在内容上按下回车
      index = self.listBox.Selection
      if "pageNumber" in self.curContent["postlist"][index]:
        pageNumber = self.curContent["postlist"][index]["pageNumber"]
        if pageNumber == 0:
          numberInputDialog = NumberInputDialog(self.frame, title="输入页数跳转", range=(1, self.curContent["totalpage"]))
          if numberInputDialog.ShowModal() == wx.ID_OK:
            pageNumber = numberInputDialog.result

          numberInputDialog.Destroy()
          if pageNumber == 0:
            return

        self.curContent = zdclient.getPost(self.curContent["tid"], pageNumber)
        self.Display()
      else:
        contentDialog = ContentDialog(self.frame, self.listBox.GetStrings(), self.listBox.Selection)
        contentDialog.ShowModal()
        contentDialog.Destroy()

    elif event.GetKeyCode() == wx.WXK_BACK and (not self.backContent is None): # 按下退格键
      self.curContent = self.backContent # 从备份恢复数据
      self.backContent = None
      self.Display() # 直接在列表框上展示上面恢复的内容
    else:
      pass


  # 列表框选择项目改变
  def OnListBox(self, event):
    if "index" in self.curContent:
      self.curContent["index"] = self.listBox.Selection # 更新当前主题的索引， 这样从详细内容返回主题列表的时候焦点还在上次主题上，在display函数里设置


  # 展示内容
  def Display(self):
    if "threadlist" in self.curContent: # 主题
      list = "threadlist"
    else: # 详细
      list = "postlist"

    self.listBox.Clear() # 清空列表框
    for item in self.curContent[list]:
      self.listBox.Append(item["fmt"]) # 迭代器里更新内容

    if "index" in self.curContent:
      self.listBox.Selection = self.curContent["index"] # 设置上次浏览到的焦点
      self.postBtn.SetLabel("发表新帖(&P)")
    elif self.listBox.Count > 0:
      self.listBox.Selection = 0 # 设置默认焦点， 第一个项目
      self.postBtn.SetLabel("回复楼层(&R)")
    else:
      pass


  # 用户状态
  def OnUserStatus(self):
    user = zdclient.getConfig("user") # 获取用户信息
    if user is None: # 用户没有登录
      self.loginBtn.SetLabel("登录(&L)")
      self.loginBtn.Unbind(wx.EVT_BUTTON, handler = self.OnLogout) # 解除绑定， 注销函数
      self.loginBtn.Bind(wx.EVT_BUTTON, self.OnLogin) # 绑定用户登录函数
      self.postBtn.Show(False)
    else: # 用户已经登录
      self.loginBtn.SetLabel("{}， 注销登录(&I)".format(user["username"]))
      self.loginBtn.Unbind(wx.EVT_BUTTON, handler = self.OnLogin) # 解除绑定用户登录函数
      self.loginBtn.Bind(wx.EVT_BUTTON, self.OnLogout) # 绑定用户注销函数
      self.postBtn.Show(True)


  # 用户登录
  def OnLogin(self, event):
    userLoginDialog = UserLoginDialog(self.frame) # 创建用户登录对话框
    if userLoginDialog.ShowModal() == wx.ID_OK: # 显示模态对话框， 并且按下登录ok按钮的情况下
      zdclient.setConfig("user", userLoginDialog.result["message"]["user"]) # 设置用户信息，如果登录失败返回None， 这里抛出异常
      self.OnUserStatus() # 用户状态改变

    userLoginDialog.Destroy() # 销毁对话框


  # 用户注销
  def OnLogout(self, event):
    zdclient.setConfig("user", None) # 简单的重新设置为none就可以了
    self.OnUserStatus() # 用户状态改变


  # 发表新主题或者回复贴子
  def OnPost(self, event):
    postDialog = PostDialog(self.frame, self.curContent)
    res_id = postDialog.ShowModal()
    if res_id == wx.ID_OK:
      result = postDialog.result["message"]
      if "post" in result:
        self.curContent = zdclient.getPost(result["post"]["tid"], page = result["post"]["page"])
        self.Display()
        self.listBox.SetFocus()
        for i in range(len(self.curContent["postlist"]) - 1, 0, -1):
          if self.curContent["postlist"][i]["pid"] == result["post"]["pid"]:
            self.listBox.Selection = i
            break

      else:
        self.backContent = self.curContent
        self.curContent = zdclient.getThread(result["thread"]["tid"])
        self.Display()
        if self.listBox.Count > 0:
          self.listBox.Selection = 0

      print(postDialog.result)
    elif res_id == wx.ID_NO:
      wx.MessageBox("发表失败。", caption="错误：")
    else:
      pass

    postDialog.Destroy()



# 用户登录对话框
class UserLoginDialog(wx.Dialog):
  def __init__(self, frame):
    wx.Dialog.__init__(self, frame, id = -1, title="用户登录")
    self.label1 = wx.StaticText(self, label="争渡号/邮箱地址：")
    self.userNameText = wx.TextCtrl(self)
    wx.label2 = wx.StaticText(self, label="密码：")
    self.userPasswordText = wx.TextCtrl(self, style=wx.TE_PASSWORD)
    self.okBtn = wx.Button(self, id=wx.ID_OK, label="登录(&L)")
    self.okBtn.Bind(wx.EVT_BUTTON, self.OnOk) # 绑定登录函数，不要和OnLogin函数混淆，两个在不同的类里，一个打开一个对话框，真正负责用户登录的事OnOk函数
    self.cancelBtn = wx.Button(self, id=wx.ID_CANCEL, label="取消(&C)")

    self.result = None # 登录后的结果


  # 真正的用户登录
  def OnOk(self, event):
    email = self.userNameText.GetValue() # 获取Email
    password = self.userPasswordText.GetValue()
    if email == "" or password == "":
      self.userNameText.SetFocus() # 如果事空的直接跳到第一个编辑框上
      return

    # 构造提交服务器的字段， 这里三个， 在底层还需要appkey和seckey， 参考zdclient.post函数
    data = {"format": "json", 
      "email": email, 
      "password": password}

    self.result = zdclient.post("user-login.htm", data) # http提交登录请求
    self.EndModal(wx.ID_OK) # 结束模态对话框返回wx.ID_OK



# 发帖或者回帖对话框
class PostDialog(wx.Dialog):
  def __init__(self, frame, content):
    wx.Dialog.__init__(self, frame, id = -1, title="回复楼层")
    self.content = content
    self.result = None
    if "threadlist" in content:
      self.SetTitle("发表新贴子")
      self.subjectLabel = wx.StaticText(self, label="贴子标题：")
      self.subjectText = wx.TextCtrl(self)
      self.forumlist = zdclient.get("index-forumlist.htm", "format=json")
      self.forumLabel = wx.StaticText(self, label="板块：")
      self.forumComboBox = wx.ComboBox(self, style = wx.CB_READONLY)
      self.forumComboBox.Bind(wx.EVT_COMBOBOX, self.OnForumComboBox)

      self.typeLabel = wx.StaticText(self, label="分类：")
      self.typeComboBox = wx.ComboBox(self, style = wx.CB_READONLY)
      self.typeLabel.Show(False)
      self.typeComboBox.Show(False)

      for forum in self.forumlist:
        self.forumComboBox.Append(forum["name"])

      self.forumComboBox.Selection = 1

    self.contentLabel = wx.StaticText(self, label="正文：")
    self.messageText = wx.TextCtrl(self, size=(800, 800), style = wx.TE_MULTILINE)
    self.postBtn = wx.Button(self, id = wx.ID_OK, label="发布(&P)")
    self.postBtn.Bind(wx.EVT_BUTTON, self.OnPost)
    self.cancelBtn = wx.Button(self, id = wx.ID_CANCEL, label="取消(&C)")


  # 选择板块
  def OnForumComboBox(self, event):
    index = event.GetEventObject().Selection
    typeid1 = self.forumlist[index]["types"]["typeid1"]
    if len(typeid1) == 0:
      self.typeLabel.Show(False)
      self.typeComboBox.Show(False)
      return

    self.typeLabel.Show(True)
    self.typeComboBox.Show(True)
    self.typeComboBox.Clear()

    for i in range(1, len(typeid1)):
      self.typeComboBox.Append(typeid1[i]["name"])

    self.typeComboBox.Selection = 0


  # 按下发帖或回帖按钮
  def OnPost(self, event):
    subject = None
    message = None
    if "index" in self.content:
      subject = self.subjectText.GetValue()
      if not(len(subject) >= 5 and len(subject) <= 25):
        self.subjectText.SetFocus()
        return

    message = self.messageText.GetValue()
    if len(message) < 5:
      self.messageText.SetFocus()
      return

    subURL = None
    data = {"format": "json", "auth": zdclient.getConfig("user")["auth"]}
    if not subject is None:
      subURL = "post-thread.htm"
      forumIndex = self.forumComboBox.Selection
      data.update({"fid": self.forumlist[forumIndex]["fid"]})
      data.update({"typeid1": 0, "typeid2": 0, "typeid3": 0, "typeid4": 0})
      if len(self.forumlist[forumIndex]["types"]["typeid1"]) > 0:
        data.update({"typeid1": self.forumlist[forumIndex]["types"]["typeid1"][self.typeComboBox.Selection + 1]["id"]})

      data.update({"subject": subject})
    else:
      subURL = "post-post.htm"
      data.update({"fid": self.content["fid"], "tid": self.content["tid"]})

    data.update({"message": message})

    self.result = zdclient.post(subURL, data)
    if self.result is None:
      self.EndModal(wx.ID_NO)
    else:
      self.EndModal(wx.ID_OK)



# 输入数字对话框
class NumberInputDialog(wx.Dialog):
  def __init__(self, frame, title="请输入", range=(0, 100)):
    wx.Dialog.__init__(self, frame, id = -1, title=title)
    self.result = None
    self.range = range
    self.inputLabel = wx.StaticText(self, label="请输入{}-{}之间的数字：".format(range[0], range[1]))
    self.inputText = wx.TextCtrl(self)
    self.okBtn = wx.Button(self, id = wx.ID_OK, label="确定(&O)")
    self.okBtn.Bind(wx.EVT_BUTTON, self.OnOk)
    self.cancelBtn = wx.Button(self, id = wx.ID_CANCEL, label="取消(&C)")


  # 按下确定
  def OnOk(self, event):
    try:
      self.result = int(self.inputText.GetValue())
      if self.result >= self.range[0] and self.result <= self.range[1]:
        self.EndModal(wx.ID_OK)
      else:
        self.inputText.SetValue("")
        raise ValueError("Value Error")
    except:
      self.inputText.SetValue("")
      self.inputText.SetFocus()



# 详细内容对话框
class ContentDialog(wx.Dialog):
  def __init__(self, frame, datas, selection):
    wx.Dialog.__init__(self, frame, id = -1, title="内容")
    self.frame = frame
    self.datas = datas
    self.selection = selection
    self.contentText = wx.TextCtrl(self, size=(800, 800), value=self.datas[self.selection], style=wx.TE_MULTILINE | wx.TE_READONLY)
    self.allDisplayCheck = wx.CheckBox(self, label="显示全部(&A)")
    self.allDisplayCheck.Bind(wx.EVT_CHECKBOX, self.OnAllDisplayCheck)
    self.okBtn = wx.Button(self, id = wx.ID_OK, label="关闭(&C)")
    self.contentText.SetFocus()


  # 显示全部复选框
  def OnAllDisplayCheck(self, event):
    check = event.GetEventObject().GetValue()
    if check:
      content = "\n\n----------------\n\n".join(self.datas)
      self.contentText.SetValue(content + "\n\n")
    else:
      self.contentText.SetValue(self.datas[self.selection])

    self.contentText.SetFocus()
