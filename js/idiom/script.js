/* idiom/webapps/script.js 
* 2651688427@qq.com */

// 需要的自定义事件标识符
const EVENT_PLAYER_INPUT = "eventPlayerInput";
const EVENT_IDIOM_LOAD_SUCCESS = "eventIdiomLoadSuccess";
const EVENT_SKIP = "eventSkip";
const EVENT_REPLAY_IDIOM = "eventReplayIdiom";

// 下载成语数据到本地
function download() {
  axios.get("/idiom/idiom_dict.json")
    .then((response) => successLoad(response)) 
    .catch((err) => failLoad(err));
}

// 提供成语数据查询服务
function Idiom(idiomData) {
  this.headTable = new Map();
  this.tailTable = new Map();
  this.allIdiom = new Array();
  for (let item of idiomData) {
    let headPinyin = pinyinPro.pinyin(item.charAt(0), {toneType: "none"});
    if (this.headTable.has(headPinyin)) {
      this.headTable.get(headPinyin).push(this.allIdiom.length);
    } else {
      this.headTable.set(headPinyin, [this.allIdiom.length, ]);
    }
    let tailPinyin = pinyinPro.pinyin(item.charAt(item.length - 1), {toneType: "none"});
    if (this.tailTable.has(tailPinyin)) {
      this.tailTable.get(tailPinyin).push(this.allIdiom.length);
    } else {
      this.tailTable.set(tailPinyin, [this.allIdiom.length, ]);
    }
    this.allIdiom.push(item);
  }

  // 随机获取一个指定拼音开头的成语
  this.headRandom = function (pinyin) {
    if (this.headTable.has(pinyin.toLowerCase())) {
      let table = this.headTable.get(pinyin);
      return this.allIdiom[table[Math.floor(Math.random() * table.length)]];
  } else {
    return null;
  }
  }

  // 随机获取一个指定拼音结尾的成语
  this.tailRandom = function (pinyin) {
    if (this.tailTable.has(pinyin)) {
      let table = this.tailTable.get(pinyin);
      return this.allIdiom[table[Math.floor(Math.random() * table.length)]];
    } else {
      return null;
    }
  }

  // 获取随机成语
  this.random = function () {
    return this.allIdiom[Math.floor(Math.random() * this.allIdiom.length)];
  }

  // 判断给定词语是否成语, 数据不完整， 仅供参考
  this.isIdiom = function (idiom) {
    return this.allIdiom.indexOf(idiom) !== -1;
  }
}

// 游戏状态管理器
function GameManager() {
  this.idiom = null;
  this.ttsEngine = new TTSEngine();
  this.backIdiom = null;
  this.turn = {computer: {score: 0}, 
    person: {score: 0}}

  document.getElementById("score").innerHTML = `人类： ${this.turn.person.score}分 <-----------> 计算机： ${this.turn.computer.score}分`;
  document.addEventListener(EVENT_IDIOM_LOAD_SUCCESS, (e) => {
    this.idiom = e.detail;
    this.ttsEngine.speak("欢迎来到成语接龙， 同音字皆可！");
    if (Math.floor(Math.random() * 2) === 0) {
      this.ttsEngine.speak("我先来");
      this.computerPlayer();
    } else {
      this.ttsEngine.speak("你先来！");
    }
  });

  document.addEventListener(EVENT_PLAYER_INPUT, (e) => {
    if (this.idiom === null) {
      this.ttsEngine.speak("所需资源不存在， 请稍后！");
      return;
    }

    let input = e.detail.trim();
    this.personPlayer(input);
  });

  document.addEventListener(EVENT_SKIP, (e) => {
    this.ttsEngine.speak(`${this.backIdiom}跳过!`);
    this.turn.person.score += -5;
    document.getElementById("score").innerHTML = `人类： ${this.turn.person.score}分 <-----------> 计算机： ${this.turn.computer.score}分`;
    this.computerPlayer();
  });

  document.addEventListener(EVENT_REPLAY_IDIOM, (e) => this.ttsEngine.speak(`当前成语${this.backIdiom}`));

  // 机器一方的游戏逻辑
  this.computerPlayer = function () {
    if (this.backIdiom === null) {
      let newIdiom = this.idiom.random();
      this.ttsEngine.speak(newIdiom);
      this.backIdiom = newIdiom;
      this.turn.computer.score += 10;
      document.getElementById("score").innerHTML = `人类： ${this.turn.person.score}分 <-----------> 计算机： ${this.turn.computer.score}分`;
    } else {
      let newIdiom = this.idiom.headRandom(pinyinPro.pinyin(this.backIdiom.charAt(this.backIdiom.length - 1), {toneType: "none"}));
      if (newIdiom !== null) {
        this.turn.computer.score += 10;
        document.getElementById("score").innerHTML = `人类： ${this.turn.person.score}分 <-----------> 计算机： ${this.turn.computer.score}分`;
        this.ttsEngine.speak(`那么我来接${newIdiom}`);
        this.backIdiom = newIdiom;
        this.addIdiom("计算机", newIdiom);
      } else {
        this.turn.computer.score += -5;
        document.getElementById("score").innerHTML = `人类： ${this.turn.person.score}分 <-----------> 计算机： ${this.turn.computer.score}分`;
        this.ttsEngine.speak(`你说${input}, 我认输， 我不服重新开始。`);
        this.backIdiom = null;
      }
    }
  }

  // 人类一方的游戏逻辑
  this.personPlayer = function (input) {
    if (this.backIdiom === null) {
      if (this.idiom.isIdiom(input)) {
        this.ttsEngine.speak(`你说${input}, 该轮到我了`);
        this.backIdiom = input;
        this.addIdiom("人类", input);
        this.turn.person.score += 10;
        document.getElementById("score").innerHTML = `人类： ${this.turn.person.score}分 <-----------> 计算机： ${this.turn.computer.score}分`;
        this.computerPlayer();
      } else {
        this.ttsEngine.speak(`你说的似乎不是成语， 请你重新说一个${this.backIdiom}`);
        this.turn.person.score += -1;
          document.getElementById("score").innerHTML = `人类： ${this.turn.person.score}分 <-----------> 计算机： ${this.turn.computer.score}分`;
      }
    } else {
      if (!this.idiom.isIdiom(input)) {
        this.ttsEngine.speak(`${input}好像不是成语， 换一个${this.backIdiom}`);
        this.turn.person.score += -1;
        document.getElementById("score").innerHTML = `人类： ${this.turn.person.score}分 <-----------> 计算机： ${this.turn.computer.score}分`;
        return;
      }
      let inputPinyin = pinyinPro.pinyin(input.charAt(0), {toneType: "none"});
      let backPinyin = pinyinPro.pinyin(this.backIdiom.charAt(this.backIdiom.length - 1), {toneType: "none"});
      if (inputPinyin === backPinyin) {
        this.turn.person.score += 10;
        document.getElementById("score").innerHTML = `人类： ${this.turn.person.score}分 <-----------> 计算机： ${this.turn.computer.score}分`;
        this.ttsEngine.speak(`${input}, 很好， `);
        this.backIdiom = input;
        this.addIdiom("人类", input);
        this.computerPlayer();
      } else {
        this.turn.person.score += -3;
        document.getElementById("score").innerHTML = `人类： ${this.turn.person.score}分 <-----------> 计算机： ${this.turn.computer.score}分`;
        this.ttsEngine.speak(`不对， 我说的是${this.backIdiom}, 而你接的是${input}， 再来一次`);
      }
    }
  }

  this.addIdiom = function (name, idiom) {
    let ul = document.getElementById("idiom-content");
    let li = document.createElement("li");
    let textNode = document.createTextNode(`${name}: ${idiom}`);
    li.appendChild(textNode);
    ul.appendChild(li);
  }
}

// 简单调用浏览器语音合成接口
function TTSEngine() {
  this.utter = new SpeechSynthesisUtterance();
  this.speak = function (text) {
    this.utter.text = text;
    speechSynthesis.speak(this.utter);
  }
}

// 下载成语数据成功后调用的函数， 主要任务是初始化游戏和UI
function successLoad(response) {
  if (response.status === 200) {
    document.dispatchEvent(new CustomEvent(EVENT_IDIOM_LOAD_SUCCESS, {detail: new Idiom(response.data)}));
    document.getElementById("idiom").addEventListener("keydown", (e) => {
      if (e.keyCode === 13 && e.target.value) {
        document.dispatchEvent(new CustomEvent(EVENT_PLAYER_INPUT, {detail: e.target.value}));
        e.target.value = "";
      } else if (e.keyCode === 8 && e.ctrlKey) {
        document.dispatchEvent(new Event(EVENT_SKIP));
      } else if (e.keyCode === 13 && e.altKey) {
        document.dispatchEvent(new Event(EVENT_REPLAY_IDIOM));
      }
    });
  } else {
    failLoad();
  }
}

// 下载成语数据失败或者初始化过程中出错之后调用的函数
function failLoad(err) {
alert(err);
  let div = document.getElementById("app");
  div.innerHTML = `<h1>应用程序不可用</h1><p>加载游戏资源失败， 请稍后在刷新页面， 或与开发者联系.........</p>`;
}

let gameManager = new GameManager();
download();
