# --*-- Encoding: UTF-8 --*--
# * Author： 2651688427@qq.com<FreeRUOK>
# * date： 2024-05
# * description: 一个使用MongoDB数据库的简单个人记账小程序

from typing import Set, List, Dict, Any, Union, Optional, Tuple, Callable
from pprint import pprint
from enum import Enum
from pathlib import Path
import re
import calendar
from datetime import datetime, date, timedelta
import json
import logging
from typing_extensions import Annotated
import typer
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId
from pydantic import ConfigDict, BaseModel, Field
from pydantic.functional_validators import BeforeValidator
import psutil
import chardet

MONGO_CONFIG_PATH = "./mongo_config.json"


def err_process(err: Exception):
    """
    统一处理在程序的其他部分没有适当处理的错误
    """
    if isinstance(err, PyMongoError):
        logging.critical(f"MongoDB数据库严重错误： {err}")
        exit(-1)
    elif isinstance(err, ParseMoneyLogError):
        logging.critical(f"解析错误： {err}")
        exit(-1)

    elif isinstance(err, KeyboardInterrupt):
        logging.info("应用程序已经终止运行")
        exit(0)

    raise err


def parse_timestamp(dt_str: str) -> int:
    dt_values = [int(it) for it in re.split(r"\.|T|:|-|\s", dt_str)]

    dt = datetime(*dt_values[:6])
    return int(dt.timestamp() * 1000)


def user_input(prompt: Union[str, List[str]], line_total: int = 1):
    """
    装饰器 获取用户通过stdin输入的数据， 返回适当的数据
    如果没有合适的数据返回None
    """

    def outwrapper(fun: Callable[..., Any]):
        def wrapper(*args, **kwargs):
            if isinstance(prompt, list) and len(prompt) != line_total:
                raise ValueError(
                    f"缺少提示， prompt如果是list类型， 必须和line_total长度相等\n prompt[List] len: {len(prompt)}, total_line: {line_total}"
                )

            try:
                lines = []
                for i in range(line_total):
                    inner_prompt = prompt[i] if isinstance(prompt, list) else prompt

                    lines.append(input(inner_prompt).strip())
            except (EOFError, KeyboardInterrupt):
                return None

            if not lines:
                return None

            return fun(*args, lines=lines, **kwargs)

        return wrapper

    return outwrapper


@user_input("确认操作 yes Or No")
def confirm(lines: List[str]) -> bool:
    result = lines[0].lower()
    return result in ["y", "yes", "ok", "好", "好的", "确定"]


class MoneyType(str, Enum):
    """
    账单类型 全部 所得 或者 支出
    """

    all = "all"
    income = "income"
    outlay = "outlay"


class SortMode(str, Enum):
    """
    如何给查询的账单排序， 金额升序 金额逆序 日期升序 日期逆序
    """

    raw = "raw"
    money = "money"
    date = "date"
    money_reverse = "money_reverse"
    date_reverse = "date_reverse"

    def build(self, moneyType: MoneyType = MoneyType.all) -> Dict[str, int]:
        """
        根据排序选项生成MongoDB排序条件
        """
        if self == SortMode.money or self == SortMode.money_reverse:
            if moneyType == MoneyType.outlay:
                return {"money": -1 if self == SortMode.money_reverse else 1}

            return {"money": 1 if self == SortMode.money_reverse else -1}

        elif self == SortMode.date or self == SortMode.date_reverse:
            return {"time_line": 1 if self == SortMode.date else -1}
        else:
            return {}


class Sequel(str, Enum):
    """
    如何处理查询结果 直接打印 求 总和 总数 平均 或者转换到json/csv格式字符串\n
    此外可以对查询到的账单做删除更新等操作
    这样一个查询命令干完了所有的事情
    """

    print = "print"
    size = "size"
    total = "total"
    average = "average"
    json = "json"
    csv = "csv"
    remove = "remove"
    update = "update"


PyObjectId = Annotated[str, BeforeValidator(str)]  # MongoDB的id


class TimeQueryMode(str, Enum):
    """
    定义时间戳查询模式，
    为了实现方便查询模式和查询字符串两者强耦合
    """

    day = "day"
    month = "month"
    year = "year"
    range = "range"


class TimeQueryRangeType(str, Enum):
    """
    这个枚举有内部自动设置， 外部调用者无需关心
    根据是TimeQueryMode的值和查询字符串
    """

    literal = "literal"  # 直接指定日期和时间
    include_now = "include_now"  # 时间戳结束点是当前日期时间
    context_base_unit = (
        "context_base_unit"  # TimeQueryMode的值非range的情况下采用其值作为基本单位
    )


class TimeRangeStamp:
    """
    分析TimeQueryMode和一段查询字符串构造两个时间戳
    """

    def __init__(self, queryMode: TimeQueryMode, pattern: str = ""):
        """
        接受两个参数\n
        * queryMode 日期的查询模式
        * pattern 给日期查询模式提供的字符串查询标志\n
        具体查看相关代码
        """
        self.queryMode = queryMode
        self.rangeType = TimeQueryRangeType.literal
        if pattern[0] == "-" or pattern[0] == "=":
            self.rangeType = (
                TimeQueryRangeType.include_now
                if pattern[0] == "="
                else TimeQueryRangeType.context_base_unit
            )
            pattern = pattern[1:]

        self.pattern = [
            int(i)
            for i in filter(lambda e: e != "", re.split(r"\s|-|/|[年月日]", pattern))
        ]

    def __call__(self) -> Tuple[float, float]:
        """
        返回开始时间戳和结束时间戳
        """
        if len(self.pattern) == 1 and self.rangeType == TimeQueryRangeType.literal:
            raise LookupError("Invalid parameter")

        if self.queryMode == TimeQueryMode.day:
            begin, end = self.parse_day()
        elif self.queryMode == TimeQueryMode.month:
            begin, end = self.parse_month()
        elif self.queryMode == TimeQueryMode.year:
            begin, end = self.parse_year()
        else:
            begin, end = self.parse_range()

        if begin > end:
            raise LookupError("The time range cannot be reversed")

        return (int(begin.timestamp() * 1000), int(end.timestamp() * 1000))

    def parse_day(self) -> Tuple[datetime, datetime]:
        now = datetime.now()
        begin = now - timedelta(days=self.pattern[0])
        begin = datetime(begin.year, begin.month, begin.day)
        if self.rangeType == TimeQueryRangeType.context_base_unit:
            end = begin + timedelta(days=1) - timedelta(microseconds=1)
        else:
            end = now

        return (begin, end)

    def parse_month(self) -> Tuple[datetime, datetime]:
        now = datetime.now()
        total_month = self.pattern[0]
        target_year, target_month = (
            now.year - total_month // 12,
            12 + (now.month - total_month % 12),
        )
        target_month = target_month if target_month <= 12 else target_month - 12
        target_year = target_year if now.month >= target_month else target_year - 1
        begin = datetime(target_year, target_month, 1)
        if self.rangeType == TimeQueryRangeType.context_base_unit:
            max_day = calendar.monthrange(begin.year, begin.month)[1]
            end = datetime(begin.year, begin.month, max_day, 23, 59, 59, 1000)
        else:
            end = now

        return (begin, end)

    def parse_year(self) -> Tuple[datetime, datetime]:
        now = datetime.now()
        target_year = now.year - self.pattern[0]
        begin = datetime(target_year, 1, 1)
        if self.rangeType == TimeQueryRangeType.context_base_unit:
            end = datetime(target_year, 12, 31, 23, 59, 59, 1000)
        else:
            end = now

        return (begin, end)

    def parse_range(self) -> Tuple[datetime, datetime]:
        if self.rangeType != TimeQueryRangeType.literal:
            raise LookupError("Option range must be used together with Query literal")

        length = len(self.pattern)
        if length < 1 or length > 6 or length % 2 == 1:
            raise LookupError("Incorrect time range or format")

        now = datetime.now()
        pattern = self.pattern
        if length == 6:
            begin = datetime(pattern[0], pattern[1], pattern[2])
            end = datetime(pattern[3], pattern[4], pattern[5], 23, 59, 59, 1000)
        elif length == 4:
            begin = datetime(now.year, pattern[0], pattern[1])
            end = datetime(now.year, pattern[2], pattern[3], 23, 59, 59, 1000)
        else:
            begin = datetime(now.year, now.month, pattern[0])
            end = datetime(now.year, now.month, pattern[1], 23, 59, 59, 1000)

        return (begin, end)


class ConditionType(str, Enum):
    operator = "operator"
    number = "number"
    range = "range"


class Condition:
    def __init__(self, tokens: List[str], cType: ConditionType):
        self.tokens: List[str] = tokens
        self.cType: ConditionType = cType

    def build(self, moneyType: MoneyType = MoneyType.all) -> Dict[str, Any]:
        if self.cType == ConditionType.range:
            begin, end = float(self.tokens[0]), float(self.tokens[2])
            return (
                {"money": {"$gte": begin, "$lte": end}}
                if moneyType != MoneyType.outlay
                else {"money": {"$lte": -begin, "$gte": -end}}
            )
        elif self.cType == ConditionType.number:
            val = float(self.tokens[0])
            val = -val if moneyType == MoneyType.outlay else val
            return {"money": val}
        else:
            operators = {">": "$gt", ">=": "$gte", "<": "$lt", "<=": "$lte"}
            if moneyType != MoneyType.outlay:
                return {"money": {operators[self.tokens[0]]: float(self.tokens[1])}}

            operators = {">": "$lt", ">=": "$lte", "<": "$gt", "<=": "$gte"}
            operator, val = operators[self.tokens[0]], -float(self.tokens[1])
            if operator == "$gt" or operator == "$gte":
                return {"money": {operator: val, "$lt": 0}}

            return {"money": {operator: val}}

    def __str__(self) -> str:
        return f"tokens: <{' '.join(self.tokens)}>\ntype: {self.cType}"


def parse_condition(raw_str: str) -> Condition:
    re_express = {
        re.compile(r"^(-*[0-9]+)\s*(-)\s*(-*[0-9]+)$"): ConditionType.range,
        re.compile(r"^-*[0-9]{1,}\.*[0-9]+$"): ConditionType.number,
        re.compile(r"^(<|<=|>|>=)\s*(-*[0-9]+)$"): ConditionType.operator,
    }
    for express, cType in re_express.items():
        if (result := express.match(raw_str.strip())) is not None:
            tokens = list(
                (result.group(),) if len(result.groups()) == 0 else result.groups()
            )
            condition = Condition(tokens=tokens, cType=cType)
            return condition

    raise typer.BadParameter(f"Invalid Condition: {raw_str}")


class MoneyLog(BaseModel):
    """
    表示一个账单 包括 金额 多个标签 发生时间戳， 此外有个可选的MongoDB id
    """

    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    money: float = Field(...)
    tags: Set[str] = Field(...)
    time_line: int = Field(...)
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    def fmt(self) -> str:
        """
        友好可读的形式格式化账单
        """

        money = (
            f"所得 {self.money:.2f}￥"
            if self.money >= 0
            else f"支出 {+self.money:.2f}￥"
        )
        tags = "  ".join(self.tags)
        return f"{money} {self.timestamp_fmt()} 标签： <{tags}>"

    def timestamp_fmt(self) -> str:
        """
        把时间戳格式化为友好可读的字符串
        """
        now = datetime.now()
        dt = datetime.fromtimestamp(self.time_line / 1000)
        year = "" if now.year == dt.year else f"{dt.year}年"
        month = "" if now.month == dt.month else f"{dt.month}月"
        day = "" if now.day == dt.day else f"{dt.day}日"
        fmt = f"{year}{month}{day} {dt.hour}点{dt.minute}分"
        return fmt


class ParseMoneyLogError(Exception):
    pass


def check_value(obj: Any, name: str) -> Any:
    if obj is None:
        raise ParseMoneyLogError("解析为MoneyLog对象的时候出错, 没有提供默认的可用对象")
    else:
        return getattr(obj, name)


def parseMoneyLog(
    lines: List[str], is_throw: bool = True, default_money: Union[MoneyLog, None] = None
) -> Union[MoneyLog, None]:
    """
    解析用户通过stdin输入的字符串， 返回一个MoneyLog对象
    如果输入无效字段用默认提供的MoneyLog字段来替换
    """
    try:
        newMoney = float(lines[0])
    except ValueError:
        if is_throw:
            newMoney = check_value(default_money, "money")
        else:
            return None

    try:
        newTags = set(filter(lambda it: len(it) != 0, re.split(r"\s+|;", lines[1])))
        if len(newTags) == 0:
            raise ValueError("Tags Length As Zero.")

    except ValueError:
        if is_throw:
            newTags = check_value(default_money, "tags")
        else:
            return None

    try:
        newTime_line = parse_timestamp(lines[2])
    except ValueError:
        if is_throw:
            newTime_line = check_value(default_money, "time_line")
        else:
            return None

    newId = default_money.id if default_money is not None else None
    return MoneyLog(_id=newId, money=newMoney, tags=newTags, time_line=newTime_line)


@user_input(
    ["输入金额： ", "输入标签（用空格隔开）： ", "输入日期时间： "], line_total=3
)
def inputMoneyLog(
    lines: List[str], default_money: Union[MoneyLog, None] = None
) -> Union[MoneyLog, None]:
    return parseMoneyLog(lines=lines, default_money=default_money)


class MoneyLogCollection(BaseModel):
    """
    把账单集合包装起来， 统一处理
    """

    moneyLogs: List[MoneyLog]

    def processSequel(self, sequel: Sequel):
        """
                处理查询到的数据集， 包括打印 求和 求平均 转换到json/csv\n
        此外更新或者删除账单
        """

        if sequel == Sequel.print:
            self.showAll()
        elif sequel == Sequel.total or sequel == Sequel.average:
            total = sum([it.money for it in self.moneyLogs])
            if sequel == Sequel.total:
                print(f"总计： {total:.2f}￥")
            else:
                firstDate = date.fromtimestamp(
                    min([it.time_line for it in self.moneyLogs]) / 1000
                )
                firstTime = datetime(firstDate.year, firstDate.month, firstDate.day)
                lastTime = datetime.fromtimestamp(
                    max([it.time_line for it in self.moneyLogs]) / 1000
                )
                days = (lastTime - firstTime).days + 1

                print(f"在{days}天内每日平均为： {(total/days):2f}￥")

        elif sequel == Sequel.size:
            print(f"总共有 {len(self.moneyLogs)} 条账单")
        elif sequel == Sequel.json or sequel == Sequel.csv:
            json = list(
                (
                    it.model_dump(mode="json", include={"money", "tags", "time_line"})
                    for it in self.moneyLogs
                )
            )
            for ml in json:
                ml.update(
                    {"time_line": f"{datetime.fromtimestamp(ml['time_line'] / 1000)}"}
                )
            with open(f"./moneyLogs.{sequel}", "w", encoding="UTF-8") as fp:
                if sequel == Sequel.json:
                    pprint(json, stream=fp)
                else:
                    csv_content = "\n".join(
                        (
                            f"{it['money']},{';'.join(it['tags'])},{it['time_line']}"
                            for it in json
                        )
                    )

                    fp.write(csv_content)

        elif sequel == Sequel.remove:
            self.deleteOne()
        elif sequel == Sequel.update:
            self.updateOne()

    def showAll(self, showIndex: bool = False):
        """
        打印账单集合到屏幕上
        """
        pos = 1
        for moneyLog in self.moneyLogs:
            indexStr = f"{pos}. --- " if showIndex else ""
            print(f"{indexStr}{moneyLog.fmt()}")
            pos += 1

    @user_input("请输入账单序号， 回车提交")
    def get(self, lines: List[str]) -> Union[MoneyLog, None]:
        """
        让用户通过索引选择一个账单
        """

        try:
            index = int(lines[0])
            return self.moneyLogs[index - 1]
        except (IndexError, ValueError):
            return None

    def deleteOne(self):
        """
        从底层数据库里删除一个账单
        """
        print("删除一条账单")
        self.showAll(True)
        if (moneyLog := self.get()) is not None:
            print(f"即将彻底删除账单： \n{moneyLog.fmt()}\n不可恢复")
            if confirm():
                if MongoConnection().delete(moneyLog.id):
                    print("删除完成")
                else:
                    print("删除失败")
        else:
            print("不是有效的序号， 删除已取消")

    def updateOne(self):
        """
        在底层数据库里更新一个账单
        """
        print("修改一条账单")
        self.showAll(True)

        if (moneyLog := self.get()) is not None:
            print(
                f"将要修改的账单： \n{moneyLog.fmt()}\n按照提示输入新值， 留空则不修改"
            )

            newMoneyLog = inputMoneyLog(default_money=moneyLog)
            if newMoneyLog is None or newMoneyLog == moneyLog:
                print("账单保持不变")
                return

            print(f"账单即将修改为： \n{newMoneyLog.fmt()}")
            if confirm():
                if (
                    resultMoneyLog := MongoConnection().updateOne(
                        newMoneyLog=newMoneyLog
                    )
                ) is not None:
                    print(f"修改成功， 最新账单:\n{resultMoneyLog.fmt()}")
                else:
                    print("修改失败")
        else:
            print("不是有效的序号， 操作已取消")


class MongoConnection:
    """
    定义mongoDB数据库连接， 并提供了若干常用方法
    """

    def __init__(self):
        """
        初始化数据库连接， 定义数据库名称和集合
        """
        if not self.__is_running():
            raise PyMongoError("MongoDB Server Is Not Running")
        try:
            fp = Path(MONGO_CONFIG_PATH).open()
            config = json.load(fp)
        except (FileNotFoundError, json.JSONDecodeError):
            print(
                "找不到MongoDB配置文件或配置文件已经损坏\n请运行 `python money.py config-mongodb` 命令初始化一个配置文件"
            )
            exit(-1)

        self.db_cli = MongoClient(config["host"])

        self.db = self.db_cli[config["db_name"]]
        self.collection = self.db[config["collection_name"]]

    def __is_running(self) -> bool:
        try:
            mongoService = psutil.win_service_get("MongoDB")
            return mongoService.status() == "running"
        except psutil.NoSuchProcess:
            return False

    def insert(self, moneyLog: Union[MoneyLog, None]) -> Union[MoneyLog, None]:
        """
        插入一个新的账单
        """
        if moneyLog is None:
            return None
        try:
            result = self.collection.insert_one(
                moneyLog.model_dump(mode="json", by_alias=True, exclude=set(["id"]))
            )

            if (result.acknowledged) and (
                newItem := self.collection.find_one({"_id": result.inserted_id})
            ) is not None:
                return MoneyLog(**newItem)
        except PyMongoError as e:
            err_process(e)

        return None

    def find(
        self, query: Dict[str, Any] = {}, sortMode: Dict[str, int] = {}
    ) -> Union[MoneyLogCollection, None]:
        """
        根据给定条件查询数据库
        """
        try:
            if (cursor := self.collection.find(query)) is not None:
                if sortMode != {}:
                    cursor.sort(sortMode)

                return MoneyLogCollection(moneyLogs=cursor)
        except PyMongoError as e:
            err_process(e)

        return None

    def delete(self, id: PyObjectId) -> bool:
        """
        从mongoDB里删除一条记录
        """
        try:
            if (
                result := self.collection.delete_one({"_id": ObjectId(id)})
            ) is not None:
                return result.deleted_count != 0
        except PyMongoError as e:
            err_process(e)

        return False

    def updateOne(self, newMoneyLog: MoneyLog) -> Union[MoneyLog, None]:
        """
        从MongoDB数据库里更新一条记录
        """
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(newMoneyLog.id)},
                {"$set": newMoneyLog.model_dump(mode="json", exclude=set(["id"]))},
            )

            if (result.modified_count == 1) and (
                newItem := self.collection.find_one({"_id": ObjectId(newMoneyLog.id)})
            ) is not None:
                return MoneyLog(**newItem)
        except PyMongoError as e:
            err_process(e)

        return None


# 初始化cli应用程序
app = typer.Typer()


@app.callback()
def callback():
    """
    * 一个简单的个人记账程序\n
    * 后端直接和MongoDB数据库交互\n
    """
    pass


@app.command()
def config_mongodb(
    host: str = "mongodb://localhost:27017",
    db_name: str = "money_db",
    collection_name: str = "money_log",
):
    """
    写入一个MongoDB配置文件\n
    不检查MongoDB服务的运行状态， 运行此命令后确保MongoDB服务正常运行\n\n

    host: MongoDB数据库主机名称， 默认本地机器的27017端口\n
    db_name 数据库名称 默认： money_db\n
    collection_name 应用程序使用的文档集合的名称 默认 money_log\n
    """
    with open(MONGO_CONFIG_PATH, "wt") as fp:
        config = {"host": host, "db_name": db_name, "collection_name": collection_name}
        json.dump(config, fp)
        print(f"MongoDB配置已经写入到程序同一个目录下的{MONGO_CONFIG_PATH}文件里")


@app.command()
def add(
    money: float,
    tags: Annotated[str, typer.Option("--tags", "-t", default_factory="日常支出")],
    when: Annotated[
        datetime, typer.Option("--when", "-w", default_factory=datetime.now())
    ],
    income: Annotated[bool, typer.Option("--income", "-i")] = False,
):
    """
    * 添加一个账单记录  \n  \n
    * 第一个参数账单金额 必须  \n
    * --tags 账单标签 用英文双引号括起来并且空格隔开的多个文本描述 默认 日常支出  \n
    * --when 账单发生的时间 格式参见下面的说明 默认当前日期和时间  \n
    * --income 是否为所得 默认为 否  \n
    """
    if not income:
        money = -money

    tagSet = set(filter(lambda it: len(it) != 0, tags.split(" ")))
    ml = MoneyLog(money=money, tags=tagSet, time_line=int(when.timestamp() * 1000))
    newMoneyLog = MongoConnection().insert(ml)
    if newMoneyLog is not None:
        print(f"成功新增： \n{newMoneyLog.fmt()}")
    else:
        print("添加新账单失败。")


@app.command()
def query(
    timeMode: Annotated[
        TimeQueryMode, typer.Option("--time-mode", "-tm")
    ] = TimeQueryMode.month,
    timeString: Annotated[str, typer.Option("--time-string", "-ts")] = "=0",
    condition: Annotated[
        Optional[Condition], typer.Option("--condition", "-c", parser=parse_condition)
    ] = None,
    moneyType: Annotated[
        MoneyType, typer.Option("--money-type", "-mt")
    ] = MoneyType.all,
    tags: Annotated[str, typer.Option("--tags", "-t")] = "",
    sortMode: Annotated[SortMode, typer.Option("--sort-mode", "-sm")] = SortMode.raw,
    sequel: Annotated[Sequel, typer.Option("--sequel", "-s")] = Sequel.print,
):
    """
    * 根据给定条件查询账单， 查询到的账单可以进一步处理\n\n

    * --time-mode 参数 时间模式 可以是  year, month, day 或 range, 默认为 month\n
    * --time-string 参数 时间模式的字符串标志， 默认为： -0 当月一号到当前\n
    通常来说--time-mode range 后可以指定某个时间段 如： \n
    * --time-mode range --time-string 2024-04-01 2024-04-30 \n
    开始时间和结束时间都不可省略， 如果省略年份或月份使用当前日期， \n
    如果开始日期省略年份或月份， 那么结束日期也必须省略\n
    可以使用  year month 或 day 跟随一个值设定对应的日期： 如\n
    -time-mode year --time-string 2024 // 2024年\n
    --time-mode month --time-string 5 // 当年5月\n
    --time-mode day --time-string 5 // 当年当月5日\n\n

    也可以使用一个“-”或“=”后跟随一个整数间接指定某日期 如：\n
    --time-mode year --time-string -2 // 两年之前到12月31日 \n
    --time-mode year --time-string =2 // 两年之前到当前 \n
    --time-mode month --time-string -3 // 三个月之前到月末 \n
    --time-mode month --time-string =3 // 三个月之前到当前 \n
    --time-mode day --time-string -5 // 五天前 \n
    --time-mode day --time-string =5 // 五天前到当前 \n\n

    --condition 查询条件， 可以使用比较运算符和账单的money字段做比较筛选符合条件的账单记录\n
    如： --condition "> 100" 查询money的值大于100的账单\n
    --condition "0 - 100" 筛选账单money值为0到100之间的记录\n
    备注： 查询条件必须使用双引号括起来， 可以使用的条件运算符有： \n
    > 大于 < 小于 >= 大于或等于 <= 小于或等于 x - y 在x到y的范围内\n\n

    * --money-type 账单类型 默认为 all 所有账单 可以是如下值：\n
    all 所有 income 所得 outla 支出\n\n

    * --tags 账单标签可以是用双引号括起来的多个标签， 标签之间用空格隔开\n\n

    --sort-mode 排序模式 默认为raw， 不排序\n
    排序模式包括：\n
    money金额从小到大排序 money_reverse 金额从大到小排序\n
    date日期从前往后排序 date_reverse 日期从后往前排序\n\n

    * --sequel 如何处理账单， 默认为： print 打印到屏幕\n
    可以是如下值： print 打印 size 总数 total 求和 average 求平均\n
    json导出为json文件， csv 导出为csv文件\n
    导出的文件保存在同一个目录下\n
    update 在查询到的账单里选择一条记录修改\n
    remove 在查询到的账单里选择一条记录删除\n\n

    """

    begin_timestamp, end_timestamp = TimeRangeStamp(timeMode, timeString)()
    query: Dict[str, Any] = {
        "time_line": {"$gte": begin_timestamp, "$lte": end_timestamp}
    }
    if moneyType != MoneyType.all:
        query.update(
            {"money": {("$gt" if moneyType == MoneyType.income else "$lt"): 0}}
        )
    if condition is not None:
        query.update(condition.build(moneyType=moneyType))

    tagSet: Set[str] = set(filter(lambda it: len(it) != 0, tags.split(" ")))

    if len(tagSet) != 0:
        query.update({"tags": {"$in": list(tagSet)}})

    if (mls := MongoConnection().find(query, sortMode=sortMode.build())) is not None:
        mls.processSequel(sequel)


@app.command()
def mass(path: Path):
    """
    从指定文件里导入账单\n
    path .csv文件， 后续支持更多文件
    """

    if (not path.exists()) or (not path.is_file()):
        raise typer.BadParameter(
            f"{path} 的内容不可读取， 请检查文件是否存在， 是否有可读权限"
        )

    buffer = path.read_bytes()
    encoding = chardet.detect(buffer)["encoding"]

    content = buffer.decode(encoding=encoding if encoding else "UTF-8")
    if path.suffix == ".csv":
        moneyCollection = MoneyLogCollection(
            moneyLogs=list(
                (
                    parseMoneyLog(lines=lines, is_throw=True)
                    for it in content.splitlines()
                    if (lines := it.split(",")).__len__() == 3
                )
            )
        )
    elif path.suffix == ".json":
        content = content.replace("'", '"')
        pyDict = json.loads(content)
        for it in pyDict:
            it.update({"time_line": parse_timestamp(it["time_line"])})

        moneyCollection = MoneyLogCollection(moneyLogs=pyDict)

    else:
        print("暂时不支持该文件格式的账单导入")
        exit(0)

    mongoConnection = MongoConnection()
    for ml in moneyCollection.moneyLogs:
        if ml is None:
            continue
        if newMoneyLog := mongoConnection.insert(ml):
            print(f"导入成功， \n{newMoneyLog.fmt()}")
        else:
            print(f"导入失败， \n{ml.fmt()}")

    print("请你子西核对， 程序可能忽略了， 不符合格式要求的账单记录")


if __name__ == "__main__":
    try:
        app()
    except Exception as e:
        err_process(e)
