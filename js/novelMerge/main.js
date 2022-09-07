/* novelMerge/main.js */
// * 2651688427@qq.com
// 实现一个小说合并脚本

// 脚本的主函数
function main()
{
  if (new RegExp("^\\/xs\\d+\\/$").test(location.pathname))
  {
    new Novel();
  }
}

// 下载网页数据
function download(url)
{
  return new Promise((resolve, reject) => 
  {
    let xhr = new XMLHttpRequest();
    xhr.onreadystatechange = () => 
    {
      if (xhr.readyState === 4)
      {
        if (xhr.status === 200)
        {
          resolve(xhr.responseText);
        }
        else
        {
          reject(new Error(`http ${xhr.status} ${xhr.statusText} - ${url}`));
        }
      }
    }
    xhr.open("GET", url, true);
    xhr.overrideMimeType(`Text/html; charset=${document.characterSet}`);  // 让返回的文档字符编码保持和当前文档一致， 
    xhr.send();
  });
}

// 获取url
function getTextURL(dom, className, urlText)
{
  for (let el of dom.getElementsByClassName(className)[0].getElementsByTagName("a"))
  {
    if (el.innerText.includes(urlText))
    {
      return el.getAttribute("href");
      break;
    }
  }
  return null;
}

// 所有关于小说的操作全部包含在这个对象里
function Novel()
{
  // 定义几个有用的事件
  const EVT_CHAPTER_MORE = "chapterMore";
  const EVT_CHAPTER_DONE = "chapterDone";
  const EVT_CONTENT_MORE = "contentMore";
  const EVT_CONTENT_DONE = "contentDone";
  const EVT_NOVEL_DONE = "novelDone"
  // 几个有用的属性
  this.chapters = new Map();  // 存放小说所有数据， key为章节序号整数类型， value里包含了本章节的所有有用信息， 对象
  this.escapeChapters = new Array(); // 保存没有URL的章节标题和序号
  this.chapterCount = -1;
  this.currentChapterCount = 0;
  this.main = document.createElement("div");  // 作为我们插件的主要节点插入到当前页面的DOM里， 而且所有的事件都绑定在了这个元素上
  this.table = document.createElement("table");  // 显示小说章节标题和URL
  this.downloadButton = document.createElement("button");

  // 初始化代码块， 最后运行
  this.init = () => 
  {
    this.downloadButton.innerHTML = "正在下载， 请稍后……";
    this.downloadButton.addEventListener("click", () => alert(`${this.currentChapterCount}/${this.chapterCount}, chapters:${this.chapters.size}, escape:${this.escapeChapters.length}`));  // 对下载按钮添加一个事件处理函数这里没有on前缀
    // 把按钮和表格加入到主节点， 然后把主节点加入到当前页面的body节点上
    this.main.appendChild(this.downloadButton);
  this.main.appendChild(this.table);
    document.body.appendChild(this.main);
    this.downloadButton.focus();

    // 触发EVT_CHAPTER_MORE事件， 而且传递小说章节列表的第一页的URL
    this.main.dispatchEvent(new CustomEvent(EVT_CHAPTER_MORE, {detail: getTextURL(document, "ablum_read", "正序")}));
  }

  // 处理EVT_CHAPTER_MORE事件
  this.main.addEventListener(EVT_CHAPTER_MORE, (e) => 
  {
    download(e.detail)
      .then((htmlDoc) => 
      {
        let dom = document.createElement("div");
        dom.innerHTML = htmlDoc;
        // 迭代所有的章节
        let chapterNum = -1;
        for (let el of dom.getElementsByClassName("chapter")[0].getElementsByTagName("li"))
        {
          let title = el.innerText;
          let url = el.getElementsByTagName("a")[0]?.getAttribute("href") ?? "/"
          chapterNum = parseInt(new RegExp("\\d+").exec(title)[0]);
          if (url === "/")
          {
            this.escapeChapters.push({title, chapterNum});
          }
          else
          {
            this.main.dispatchEvent(new CustomEvent(EVT_CONTENT_MORE, {detail: {url, chapterNum}}));
          }
        }
        let url = getTextURL(dom, "page", "下一页");
        // 如果有下一页继续触发EVT_CHAPTER_MORE事件， 相当于自己调用自己, 否则触发EVT_CHAPTER_DONE事件
        if (url)
        {
          this.main.dispatchEvent(new CustomEvent(EVT_CHAPTER_MORE, {detail: url}));
        }
        else
        {
          this.main.dispatchEvent(new CustomEvent(EVT_CHAPTER_DONE, {detail: chapterNum}));
        }
      })
      .catch(this.addError);
  });

  this.main.addEventListener(EVT_CHAPTER_DONE, (e) => 
  {
    this.chapterCount = e.detail;
  });

  this.main.addEventListener(EVT_CONTENT_MORE, (e) => 
  {
    let url = e.detail.url;
    let chapterNum = e.detail.chapterNum;
    download(url)
      .then((htmlDoc) => 
      {
        let content = null;
        if (this.chapters.has(chapterNum))
        {
          content = this.chapters.get(chapterNum);
        }
      else
        {
          content = {pages: []};
          this.chapters.set(chapterNum, content);
        }

        let dom = document.createElement("div");
        dom.innerHTML = htmlDoc;
        let text = dom.getElementsByClassName("nr_nr")[0]?.innerText + "\n";
        for (let el of dom.getElementsByTagName("script"))
        {
          if (el.innerText.includes(new RegExp("\\d+").exec(url)[0]))
          {
text += el.innerText + "\n";
            break;
          }
        }

        content.pages.push(this.filter(text));
        let nextURL = getTextURL(dom, "nr_title", "下一页");
        if (nextURL)
        {
          this.main.dispatchEvent(new CustomEvent(EVT_CONTENT_MORE, {detail: {url: nextURL, chapterNum}}));
        }
        else if ((url = getTextURL(dom, "nr_title", "下一章")))
        {
          content.nextChapterURL = url;
          content.title = dom.getElementsByTagName("title")[0]?.innerText.split("-")[0] ?? `第${e.detail.chapterNum}张`;
          this.main.dispatchEvent(new CustomEvent(EVT_CONTENT_DONE, {detail: e.detail.chapterNum}));
        }
      })
      .catch((err) => 
    {
      // 如果出错了就重新触发CONTENT_MORE事件
      this.main.dispatchEvent(new CustomEvent(EVT_CONTENT_MORE, {detail: {url, chapterNum}}));
    });
  });

  this.main.addEventListener(EVT_CONTENT_DONE, (e) => 
  {
    this.currentChapterCount += 1;
    let chapterNum = e.detail;
    let backChapter = this.chapters.get(chapterNum);
    let title = backChapter.title;
    let pageCount = `共${backChapter.pages.length}页`;
    let summary = backChapter.pages[1].substring(0);
    this.updateTable({title, pageCount, summary})
    if (this.escapeChapters.length !== 0 && this.currentChapterCount === this.chapters.size)
    {
      this.downloadEscape();
    }
    if (this.currentChapterCount === this.chapterCount)
    {
      this.main.dispatchEvent(new Event(EVT_NOVEL_DONE));
    }
  });

  this.downloadEscape = () => 
  {
    while (this.escapeChapters.length > 0)
    {
      let esc = this.escapeChapters.shift();
      let url = this.chapters.get(esc.chapterNum - 1)?.nextChapterURL;
      this.main.dispatchEvent(new CustomEvent(EVT_CONTENT_MORE, {detail: {url: url, chapterNum: esc.chapterNum}}));
    }
  }

  this.main.addEventListener(EVT_NOVEL_DONE, () => 
  {
    let downloadLink = this.makeFull();
    this.downloadButton.innerHTML = "下载全本";

    this.downloadButton.addEventListener("click", () => downloadLink.click());
  });

  this.makeFull = () => 
  {
    let chapterNums = Array.from(this.chapters.keys()).sort((x, y) => x - y);
    let novelContent = new Array();
    for (let num of chapterNums)
    {
      let chapter = this.chapters.get(num);
      let text = `\n${chapter.title}\n${chapter.pages.join("\n\n")}\n\n`;
      novelContent.push(text);
    }
    let blob = new Blob(novelContent);
    let url = URL.createObjectURL(blob);
    let a = document.createElement("a");
    a.href = url;
    a.download = `${document.title.split("_")[0]}.txt`;
    return a;
  }

  // 更新表格
  this.updateTable = (item, index = -1) => 
  {
    // 把章节标题和URL加入到表格里
    let row = null;
    if (index === -1)
    {
      row = this.table.insertRow();
    }
    else
    {
      row = this.table.insertRow(index);
    }
    row.insertCell().appendChild(document.createTextNode(item.title));
    row.insertCell().appendChild(document.createTextNode(item.pageCount));
    row.insertCell().appendChild(document.createTextNode(item.summary));
  }

  this.filter = (str) => 
  {
    let reg = new RegExp("<br/>|&nbsp;|www\\.dudu0\\.com|上一章|下一章|上一页|下一页|返回目录|最新网址|关闭+畅\\/读=,看完整内容。本章未完,请点击【|】继续阅读。|请关闭\\-畅\\*读\\/模式阅读。|关闭\\+畅\\/读=,看完整内容。本章未完,请点击【|document.getElementById.+=\\s", "gi");
    return str.replace(reg, "\n").replace(/\n{2, }/g, "\n");
  }

  this.addError = (err) => 
  {
    if (err instanceof TypeError)
    {
      throw err;
    }
    let el = document.getElementById("err");
    if (!el)
    {
      el = document.createElement("ul");
      el.id = "err";
      this.main.appendChild(el);
    }
    let li = document.createElement("li");
    li.appendChild(document.createTextNode(err));
    el.appendChild(li);
  }

  this.init();
}

main();
