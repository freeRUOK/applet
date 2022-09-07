# --*-- Encoding:UTF-8 --*--
#! filename:zdclient.py

# * 2651688427
# 实现了和争渡网交互

import requests
import bs4
import json
import copy

# 载入配置
def loadConfig():
  # 打开配置文件，解析json数据，关闭配置文件
  fp = open("./config.json")
  config = json.load(fp)
  fp.close()
  return config

__config = loadConfig()

# 获取某个配置项目
def getConfig(name):
  return copy.deepcopy(__config[name]) # 深拷贝

# 设置某个配置项目
def setConfig(name, value):
  value = copy.deepcopy(value)
  __config.update({name: value})
  # 打开配置文件， 把配置信息写入到文件，关闭文件
  fp = open("./config.json", "wt")
  json.dump(__config, fp)
  fp.close()


# 过略文本
def redress(text):
  soup = bs4.BeautifulSoup(text, "lxml")
  text = soup.get_text()
  return text


# 提交get请求
def get(path, queryStr):
  url = __config["url"]
  res = requests.get("{}{}?{}".format(url, path, queryStr)) # http请求
  if res.status_code == 200:
    content = json.loads(res.content.decode()) # 解码，json解析
    if content["status"] == 1: # 没有错误
      return content["message"]
    else:
      return None

  else:
    return None


# 获取主题列表
def getThread(page=1):
  queryStr = "appkey={}&format=json".format(__config["app_id"]["appkey"]) # 构造查询字符串
  result = get("index-index-orderby-tid-page-{}.htm".format(page), queryStr) # 提交请求
  result.update({"index": 0})
  for thread in result["threadlist"]:
    if thread["top"] != "0":
      result.update({"index": result.get("index") + 1})
    else:
      break

  # 对获取的主题生成格式化字符串
  for thread in result["threadlist"]:
    thread["fmt"] = "{}\n{}发布于{}\n".format(thread["subject"], thread["username"], thread["dateline_fmt"])
    thread["fmt"] += "{}次围观， {}次回复\n".format(thread["views"], int(thread["posts"]) - 1)
    thread["fmt"] += "{}最后回复于: {}\n".format(thread["lastusername"], thread["lastpost_fmt"])

  if result["page"] != 1:
    result["threadlist"].append({"fmt": "上一页", "pageNumber": result["page"] - 1})

  result["threadlist"].append({"fmt": "下一页", "pageNumber": result["page"] + 1})
  result["threadlist"].append({"fmt": "跳转翻页", "pageNumber": 0})
  result["threadlist"].append({"fmt": "刷新本页", "pageNumber": result["page"]})

  return result


# 获取某主题的详细内容
def getPost(tid, page=1):
  queryStr = "appkey={}&format=json".format(__config["app_id"]["appkey"])
  result = get("thread-{}-page-{}.htm".format(tid, page), queryStr)

  # 生成格式化字符串
  for post in result["postlist"]:
    if page == 1 and post["floor"] == 1:
      content = "楼主{}说：\n".format(post["username"])
    else:
      content = "{}楼{}说：\n".format(post["floor"], post["username"])

    content += "{}\n\n发布于:{}".format(redress(post["message"]), post["dateline_fmt"])
    post["fmt"] = content

  if result["page"] == 1:
    if int(result["thread"]["posts"]) <= 20:
      result["postlist"].append({"fmt": "刷新当前页", "pageNumber": result["page"]})
    else:
      result["postlist"].append({"fmt": "下一页", "pageNumber": result["page"] + 1})
      result["postlist"].append({"fmt": "跳转翻页", "pageNumber": 0})

  elif result["page"] > 1 and result["page"] < result["totalpage"]:
    result["postlist"].append({"fmt": "上一页", "pageNumber": result["page"] - 1})
    result["postlist"].append({"fmt": "下一页", "pageNumber": result["page"] + 1})
    result["postlist"].append({"fmt": "跳转翻页", "pageNumber": 0})
  else:
    result["postlist"].append({"fmt": "上一页", "pageNumber": result["page"] - 1})
    result["postlist"].append({"fmt": "刷新当前页", "pageNumber": result["page"]})
    result["postlist"].append({"fmt": "跳转翻页", "pageNumber": 0})

  return result


# post请求，用户登录，发表主题，回复主题都需要
def post(path, data):
  # 加上appkey和seckey
  data.update({"appkey": __config["app_id"]["appkey"], 
    "seckey": __config["app_id"]["seckey"]})

  res = requests.post("{}{}".format(__config["url"], path), data=data, json=True) # http POST请求
  if res.status_code == 200:
    content = json.loads(res.content.decode())
    if content["status"] == 1:
      return content
    else:
      return None

  else:
    return None
