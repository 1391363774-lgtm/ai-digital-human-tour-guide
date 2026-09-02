"""生成100题问答评测集，覆盖事实/介绍/文化/对比/路线/改写/边界7大类。

用法：
    python scripts/generate_eval_dataset.py
"""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET = PROJECT_ROOT / "data" / "eval" / "qa_testset.json"

KEYWORD_ALIAS_GROUPS: dict[str, list[list[str]]] = {
    "F-012": [["30000", "3万", "三万"]],
    "F-014": [["12", "十二"]],
    "F-015": [["12", "十二"]],
    "F-021": [["8", "八"]],
    "F-023": [["12.8", "12吨"]],
    "F-027": [["1600", "1600亩"]],
    "F-029": [["101.5", "101"]],
    "F-032": [["6", "六"]],
}


# ──────────────────────────────────────────────
# 1. 事实型问题（35题）——可验证的数字、年代、尺寸、材料等
# ──────────────────────────────────────────────
FACTUAL: list[dict] = [
    {"id": "F-001", "question": "灵山大佛通高多少米？",
     "expected_keywords": ["88"], "spot_names": ["灵山大佛"], "difficulty": "easy"},
    {"id": "F-002", "question": "灵山大佛佛体本身有多高？",
     "expected_keywords": ["79"], "spot_names": ["灵山大佛"], "difficulty": "medium"},
    {"id": "F-003", "question": "灵山大佛的莲花座有多高？",
     "expected_keywords": ["9"], "spot_names": ["灵山大佛"], "difficulty": "hard"},
    {"id": "F-004", "question": "灵山大佛总共用了多少吨青铜？",
     "expected_keywords": ["725"], "spot_names": ["灵山大佛"], "difficulty": "medium"},
    {"id": "F-005", "question": "灵山大佛是哪一年建成开光的？",
     "expected_keywords": ["1997"], "spot_names": ["灵山大佛"], "difficulty": "medium"},
    {"id": "F-006", "question": "灵山大佛是什么材质铸造的？",
     "expected_keywords": ["青铜"], "spot_names": ["灵山大佛"], "difficulty": "easy"},
    {"id": "F-007", "question": "灵山大佛是哪尊佛的立像？",
     "expected_keywords": ["释迦牟尼"], "spot_names": ["灵山大佛"], "difficulty": "medium"},
    {"id": "F-008", "question": "九龙灌浴的雕塑总高度是多少？",
     "expected_keywords": ["27.2"], "spot_names": ["九龙灌浴"], "difficulty": "medium"},
    {"id": "F-009", "question": "九龙灌浴用了多少千克黄金？",
     "expected_keywords": ["18"], "spot_names": ["九龙灌浴"], "difficulty": "hard"},
    {"id": "F-010", "question": "九龙灌浴的太子佛塑像有多高？",
     "expected_keywords": ["7.2"], "spot_names": ["九龙灌浴"], "difficulty": "medium"},
    {"id": "F-011", "question": "九龙灌浴外围共有多少只凤凰？",
     "expected_keywords": ["72"], "spot_names": ["九龙灌浴"], "difficulty": "hard"},
    {"id": "F-012", "question": "灵山梵宫占地面积有多大？",
     "expected_keywords": ["30000", "3万", "三万"], "spot_names": ["灵山梵宫"], "difficulty": "medium"},
    {"id": "F-013", "question": "灵山梵宫是哪一年正式开放的？",
     "expected_keywords": ["2009"], "spot_names": ["灵山梵宫"], "difficulty": "medium"},
    {"id": "F-014", "question": "灵山梵宫廊厅两侧有多少幅油画？",
     "expected_keywords": ["12", "十二"], "spot_names": ["灵山梵宫"], "difficulty": "medium"},
    {"id": "F-015", "question": "灵山梵宫每幅油画有多高？",
     "expected_keywords": ["12", "十二"], "spot_names": ["灵山梵宫"], "difficulty": "hard"},
    {"id": "F-016", "question": "灵山梵宫圣坛面积有多大？",
     "expected_keywords": ["3500"], "spot_names": ["灵山梵宫"], "difficulty": "hard"},
    {"id": "F-017", "question": "灵山梵宫圣坛可以容纳多少人？",
     "expected_keywords": ["2000"], "spot_names": ["灵山梵宫"], "difficulty": "hard"},
    {"id": "F-018", "question": "五印坛城是哪一年建成的？",
     "expected_keywords": ["2011"], "spot_names": ["五印坛城"], "difficulty": "medium"},
    {"id": "F-019", "question": "五印坛城占地面积多少平方米？",
     "expected_keywords": ["5000"], "spot_names": ["五印坛城"], "difficulty": "hard"},
    {"id": "F-020", "question": "五印坛城建在什么上面？",
     "expected_keywords": ["香水海", "圆岛"], "spot_names": ["五印坛城"], "difficulty": "medium"},
    {"id": "F-021", "question": "五印坛城的山门有多高？",
     "expected_keywords": ["8", "八"], "spot_names": ["五印坛城"], "difficulty": "hard"},
    {"id": "F-022", "question": "五印坛城的山门仿照了哪里的建筑？",
     "expected_keywords": ["布达拉宫", "雪村"], "spot_names": ["五印坛城"], "difficulty": "medium"},
    {"id": "F-023", "question": "祥符禅寺的大钟有多重？",
     "expected_keywords": ["12.8", "12吨"], "spot_names": ["祥符禅寺"], "difficulty": "hard"},
    {"id": "F-024", "question": "祥符禅寺的大钟有多高？",
     "expected_keywords": ["3.8"], "spot_names": ["祥符禅寺"], "difficulty": "hard"},
    {"id": "F-025", "question": "祥符禅寺的历史可以追溯到哪个朝代？",
     "expected_keywords": ["唐"], "spot_names": ["祥符禅寺"], "difficulty": "medium"},
    {"id": "F-026", "question": "谁将此地命名为'小灵山'？",
     "expected_keywords": ["玄奘"], "spot_names": ["祥符禅寺", "灵山大佛"], "difficulty": "medium"},
    {"id": "F-027", "question": "拈花湾禅意小镇占地多少亩？",
     "expected_keywords": ["1600", "1600亩"], "spot_names": ["拈花湾禅意小镇", "拈花湾"], "difficulty": "medium"},
    {"id": "F-028", "question": "拈花湾禅意小镇以什么文化为主题？",
     "expected_keywords": ["禅意", "唐"], "spot_names": ["拈花湾禅意小镇"], "difficulty": "easy"},
    {"id": "F-029", "question": "灵山大佛加上三层台基总高度是多少？",
     "expected_keywords": ["101.5", "101"], "spot_names": ["灵山大佛"], "difficulty": "hard"},
    {"id": "F-030", "question": "九龙灌浴用了多少吨铜？",
     "expected_keywords": ["180"], "spot_names": ["九龙灌浴"], "difficulty": "hard"},
    {"id": "F-031", "question": "灵山梵宫的穹顶有多高？",
     "expected_keywords": ["30"], "spot_names": ["灵山梵宫"], "difficulty": "hard"},
    {"id": "F-032", "question": "九龙灌浴的莲花花瓣有多长？",
     "expected_keywords": ["6", "六"], "spot_names": ["九龙灌浴"], "difficulty": "hard"},
    {"id": "F-033", "question": "祥符禅寺大钟的口径有多大？",
     "expected_keywords": ["2.5"], "spot_names": ["祥符禅寺"], "difficulty": "hard"},
    {"id": "F-034", "question": "灵山胜境的大照壁上有谁的题字？",
     "expected_keywords": ["赵朴初"], "spot_names": ["灵山大照壁"], "difficulty": "medium"},
    {"id": "F-035", "question": "灵山大佛与国内其他哪几尊大佛并称五方五佛？",
     "expected_keywords": ["乐山", "天坛", "云冈", "龙门"], "spot_names": ["灵山大佛"], "difficulty": "hard"},
]

# ──────────────────────────────────────────────
# 2. 介绍型问题（15题）——请介绍某景点
# ──────────────────────────────────────────────
INTRO: list[dict] = [
    {"id": "I-001", "question": "请介绍一下灵山大佛。",
     "expected_keywords": ["88", "青铜", "释迦牟尼"], "spot_names": ["灵山大佛"], "difficulty": "easy"},
    {"id": "I-002", "question": "九龙灌浴是什么样的景观？",
     "expected_keywords": ["太子佛", "莲花", "九龙"], "spot_names": ["九龙灌浴"], "difficulty": "easy"},
    {"id": "I-003", "question": "灵山梵宫有什么特色？",
     "expected_keywords": ["油画", "圣坛", "艺术"], "spot_names": ["灵山梵宫"], "difficulty": "easy"},
    {"id": "I-004", "question": "五印坛城是什么样的建筑？",
     "expected_keywords": ["藏传", "坛城", "五方五佛"], "spot_names": ["五印坛城"], "difficulty": "medium"},
    {"id": "I-005", "question": "请介绍一下祥符禅寺。",
     "expected_keywords": ["玄奘", "唐代", "小灵山"], "spot_names": ["祥符禅寺"], "difficulty": "medium"},
    {"id": "I-006", "question": "拈花湾禅意小镇是什么样的地方？",
     "expected_keywords": ["禅意", "唐风", "休闲"], "spot_names": ["拈花湾禅意小镇"], "difficulty": "easy"},
    {"id": "I-007", "question": "灵山大照壁在哪里？有什么意义？",
     "expected_keywords": ["入口", "中轴线", "赵朴初"], "spot_names": ["灵山大照壁"], "difficulty": "medium"},
    {"id": "I-008", "question": "降魔成道讲述的是什么故事？",
     "expected_keywords": ["释迦牟尼", "成道", "降伏"], "spot_names": ["降魔成道"], "difficulty": "medium"},
    {"id": "I-009", "question": "佛足坛是什么？",
     "expected_keywords": ["佛足", "礼佛", "脚印"], "spot_names": ["佛足坛"], "difficulty": "medium"},
    {"id": "I-010", "question": "菩提大道有什么特别之处？",
     "expected_keywords": ["菩提", "朝圣", "大道"], "spot_names": ["菩提大道"], "difficulty": "medium"},
    {"id": "I-011", "question": "香月花街是做什么的？",
     "expected_keywords": ["商业", "休闲", "花街"], "spot_names": ["香月花街"], "difficulty": "easy"},
    {"id": "I-012", "question": "拈花塔有什么看点？",
     "expected_keywords": ["塔", "小镇", "打卡"], "spot_names": ["拈花塔"], "difficulty": "medium"},
    {"id": "I-013", "question": "微笑广场为什么叫这个名字？",
     "expected_keywords": ["微笑", "拈花微笑", "禅"], "spot_names": ["微笑广场"], "difficulty": "medium"},
    {"id": "I-014", "question": "妙音台是体验什么的地方？",
     "expected_keywords": ["音乐", "演艺", "灯光"], "spot_names": ["妙音台"], "difficulty": "medium"},
    {"id": "I-015", "question": "半山衔日是什么景观？",
     "expected_keywords": ["观景", "日落", "半山"], "spot_names": ["半山衔日"], "difficulty": "medium"},
]

# ──────────────────────────────────────────────
# 3. 文化型问题（10题）——佛教文化内涵、典故
# ──────────────────────────────────────────────
CULTURAL: list[dict] = [
    {"id": "C-001", "question": "灵山大佛的'五方五佛'格局是什么意思？",
     "expected_keywords": ["五方", "五佛", "乐山"], "spot_names": ["灵山大佛"], "difficulty": "hard"},
    {"id": "C-002", "question": "九龙灌浴再现了佛教中的什么故事？",
     "expected_keywords": ["诞生", "释迦牟尼", "太子"], "spot_names": ["九龙灌浴"], "difficulty": "medium"},
    {"id": "C-003", "question": "'小灵山'这个名字是怎么来的？",
     "expected_keywords": ["玄奘", "灵鹫山", "秦履峰"], "spot_names": ["祥符禅寺", "灵山大佛"], "difficulty": "medium"},
    {"id": "C-004", "question": "五印坛城的'坛城'在佛教中代表什么？",
     "expected_keywords": ["曼陀罗", "道场", "坛城"], "spot_names": ["五印坛城"], "difficulty": "hard"},
    {"id": "C-005", "question": "祥符禅寺的寺名是怎么来的？",
     "expected_keywords": ["宋真宗", "祥符", "北宋"], "spot_names": ["祥符禅寺"], "difficulty": "hard"},
    {"id": "C-006", "question": "拈花湾的'拈花'二字有什么典故？",
     "expected_keywords": ["拈花微笑", "禅", "迦叶"], "spot_names": ["拈花湾禅意小镇"], "difficulty": "hard"},
    {"id": "C-007", "question": "灵山梵宫顶部的五座莲花圣塔代表什么？",
     "expected_keywords": ["五方五佛", "莲花", "五座"], "spot_names": ["灵山梵宫"], "difficulty": "medium"},
    {"id": "C-008", "question": "降魔成道和九龙灌浴之间有什么文化联系？",
     "expected_keywords": ["释迦牟尼", "成道", "诞生"], "spot_names": ["降魔成道", "九龙灌浴"], "difficulty": "hard"},
    {"id": "C-009", "question": "五印坛城四门的守护瑞兽分别是什么？",
     "expected_keywords": ["马", "孔雀", "象", "共命鸟"], "spot_names": ["五印坛城"], "difficulty": "hard"},
    {"id": "C-010", "question": "灵山胜境为什么叫'灵山'？",
     "expected_keywords": ["玄奘", "小灵山", "灵鹫山"], "spot_names": ["灵山大佛", "祥符禅寺"], "difficulty": "medium"},
]

# ──────────────────────────────────────────────
# 4. 对比型问题（10题）——比较景点异同
# ──────────────────────────────────────────────
COMPARATIVE: list[dict] = [
    {"id": "P-001", "question": "灵山胜境和拈花湾在游览风格上有什么区别？",
     "expected_keywords": ["佛教", "禅意", "灵山", "拈花湾"], "spot_names": ["灵山大佛", "拈花湾禅意小镇"], "difficulty": "medium"},
    {"id": "P-002", "question": "灵山梵宫和五印坛城分别代表了什么佛教文化？",
     "expected_keywords": ["汉传", "藏传", "梵宫", "坛城"], "spot_names": ["灵山梵宫", "五印坛城"], "difficulty": "hard"},
    {"id": "P-003", "question": "九龙灌浴和降魔成道都是演艺景观，有什么不同？",
     "expected_keywords": ["诞生", "成道", "灌浴", "降魔"], "spot_names": ["九龙灌浴", "降魔成道"], "difficulty": "medium"},
    {"id": "P-004", "question": "灵山大佛和祥符禅寺是什么关系？",
     "expected_keywords": ["祥符禅寺", "后方", "大佛", "小灵山"], "spot_names": ["灵山大佛", "祥符禅寺"], "difficulty": "medium"},
    {"id": "P-005", "question": "拈花塔和香月花街哪个更适合拍照打卡？",
     "expected_keywords": ["拈花塔", "花街", "打卡"], "spot_names": ["拈花塔", "香月花街"], "difficulty": "easy"},
    {"id": "P-006", "question": "灵山梵宫的圣坛和九龙灌浴的表演哪个场面更大？",
     "expected_keywords": ["梵宫", "圣坛", "灌浴", "2000"], "spot_names": ["灵山梵宫", "九龙灌浴"], "difficulty": "hard"},
    {"id": "P-007", "question": "白天游灵山胜境和晚上游拈花湾，体验上有什么不同？",
     "expected_keywords": ["白天", "夜", "大佛", "灯光"], "spot_names": ["灵山大佛", "拈花湾禅意小镇"], "difficulty": "medium"},
    {"id": "P-008", "question": "五印坛城和灵山梵宫在建筑风格上有什么差异？",
     "expected_keywords": ["藏传", "菩提伽耶", "坛城", "梵宫"], "spot_names": ["五印坛城", "灵山梵宫"], "difficulty": "hard"},
    {"id": "P-009", "question": "灵山大照壁和佛足坛在游览动线上是什么关系？",
     "expected_keywords": ["照壁", "佛足", "入口", "中轴"], "spot_names": ["灵山大照壁", "佛足坛"], "difficulty": "medium"},
    {"id": "P-010", "question": "香月花街和妙音台哪个更适合体验禅意生活？",
     "expected_keywords": ["花街", "妙音台", "禅意", "商业"], "spot_names": ["香月花街", "妙音台"], "difficulty": "medium"},
]

# ──────────────────────────────────────────────
# 5. 路线型问题（10题）——游览规划
# ──────────────────────────────────────────────
ROUTE: list[dict] = [
    {"id": "R-001", "question": "如果只有半天时间，灵山胜境最值得看哪几个景点？",
     "expected_keywords": ["大佛", "灌浴", "梵宫", "路线"], "spot_names": ["灵山大佛", "九龙灌浴", "灵山梵宫"], "difficulty": "medium"},
    {"id": "R-002", "question": "带小孩的游客适合去灵山胜境的哪些景点？",
     "expected_keywords": ["灌浴", "小孩", "演艺", "互动"], "spot_names": ["九龙灌浴"], "difficulty": "medium"},
    {"id": "R-003", "question": "想看佛教艺术，应该怎么安排灵山胜境的游览路线？",
     "expected_keywords": ["梵宫", "坛城", "艺术", "博物馆"], "spot_names": ["灵山梵宫", "五印坛城"], "difficulty": "medium"},
    {"id": "R-004", "question": "晚上去拈花湾应该怎么玩？",
     "expected_keywords": ["夜", "灯光", "花街", "广场"], "spot_names": ["拈花湾禅意小镇", "香月花街", "微笑广场"], "difficulty": "medium"},
    {"id": "R-005", "question": "从灵山大照壁到灵山大佛，中间经过哪些景点？",
     "expected_keywords": ["照壁", "佛足", "菩提", "大佛"], "spot_names": ["灵山大照壁", "佛足坛", "菩提大道", "灵山大佛"], "difficulty": "medium"},
    {"id": "R-006", "question": "喜欢历史文化的游客，灵山胜境推荐什么路线？",
     "expected_keywords": ["历史", "祥符禅寺", "大佛", "文化"], "spot_names": ["祥符禅寺", "灵山大佛"], "difficulty": "medium"},
    {"id": "R-007", "question": "三天时间怎么安排灵山胜境和拈花湾的行程？",
     "expected_keywords": ["灵山", "拈花湾", "天", "路线"], "spot_names": ["灵山大佛", "拈花湾禅意小镇"], "difficulty": "medium"},
    {"id": "R-008", "question": "拈花湾禅意小镇里有哪些必去的打卡点？",
     "expected_keywords": ["拈花塔", "花街", "广场", "半山"], "spot_names": ["拈花塔", "香月花街", "微笑广场", "半山衔日"], "difficulty": "easy"},
    {"id": "R-009", "question": "老年人游览灵山胜境有什么建议？",
     "expected_keywords": ["路线", "休息", "大佛", "平缓"], "spot_names": ["灵山大佛"], "difficulty": "medium"},
    {"id": "R-010", "question": "灵山胜境的中轴线游览路线是怎样的？",
     "expected_keywords": ["照壁", "佛足", "菩提", "灌浴", "大佛"], "spot_names": ["灵山大照壁", "佛足坛", "菩提大道", "九龙灌浴", "灵山大佛"], "difficulty": "medium"},
]

# ──────────────────────────────────────────────
# 6. 改写型问题（10题）——同一信息换种问法，测试检索鲁棒性
# ──────────────────────────────────────────────
PARAPHRASE: list[dict] = [
    {"id": "PR-001", "question": "那个很高的大佛到底有多高啊？",
     "expected_keywords": ["88"], "spot_names": ["灵山大佛"], "difficulty": "medium"},
    {"id": "PR-002", "question": "莲花里面升起来的那个佛像表演是什么？",
     "expected_keywords": ["九龙灌浴", "太子佛", "诞生"], "spot_names": ["九龙灌浴"], "difficulty": "medium"},
    {"id": "PR-003", "question": "灵山里面那个金色的藏式建筑叫什么？",
     "expected_keywords": ["五印坛城", "藏传", "坛城"], "spot_names": ["五印坛城"], "difficulty": "medium"},
    {"id": "PR-004", "question": "听说灵山有个博物馆，在哪里？",
     "expected_keywords": ["梵宫", "博物馆", "廊厅"], "spot_names": ["灵山梵宫"], "difficulty": "medium"},
    {"id": "PR-005", "question": "那个大佛是用什么做的？",
     "expected_keywords": ["青铜"], "spot_names": ["灵山大佛"], "difficulty": "easy"},
    {"id": "PR-006", "question": "拈花湾晚上有什么好玩的？",
     "expected_keywords": ["灯光", "夜", "演艺", "花街"], "spot_names": ["拈花湾禅意小镇"], "difficulty": "easy"},
    {"id": "PR-007", "question": "玄奘和灵山有什么关系？",
     "expected_keywords": ["玄奘", "小灵山", "灵鹫山"], "spot_names": ["祥符禅寺", "灵山大佛"], "difficulty": "medium"},
    {"id": "PR-008", "question": "灵山最大的表演场地在哪里？能坐多少人？",
     "expected_keywords": ["梵宫", "圣坛", "2000"], "spot_names": ["灵山梵宫"], "difficulty": "hard"},
    {"id": "PR-009", "question": "那个塔在小镇的哪里？",
     "expected_keywords": ["拈花塔", "小镇"], "spot_names": ["拈花塔"], "difficulty": "easy"},
    {"id": "PR-010", "question": "灵山入口处那个墙是什么？",
     "expected_keywords": ["照壁", "入口", "赵朴初"], "spot_names": ["灵山大照壁"], "difficulty": "medium"},
]

# ──────────────────────────────────────────────
# 7. 边界型问题（10题）——与景区无关，应拒答或绕回
# ──────────────────────────────────────────────
BOUNDARY: list[dict] = [
    {"id": "B-001", "question": "今天无锡的天气怎么样？",
     "expected_keywords": [], "spot_names": [], "difficulty": "easy", "should_refuse": True},
    {"id": "B-002", "question": "帮我订一张去无锡的火车票。",
     "expected_keywords": [], "spot_names": [], "difficulty": "easy", "should_refuse": True},
    {"id": "B-003", "question": "灵山大佛附近有什么好吃的餐厅推荐？",
     "expected_keywords": [], "spot_names": [], "difficulty": "medium", "should_refuse": True},
    {"id": "B-004", "question": "你知道今天股市行情吗？",
     "expected_keywords": [], "spot_names": [], "difficulty": "easy", "should_refuse": True},
    {"id": "B-005", "question": "帮我写一首关于春天的诗。",
     "expected_keywords": [], "spot_names": [], "difficulty": "easy", "should_refuse": True},
    {"id": "B-006", "question": "灵山胜境门票多少钱？怎么买票？",
     "expected_keywords": [], "spot_names": [], "difficulty": "medium", "should_refuse": True},
    {"id": "B-007", "question": "从上海开车到灵山胜境要多久？",
     "expected_keywords": [], "spot_names": [], "difficulty": "medium", "should_refuse": True},
    {"id": "B-008", "question": "你能帮我算一道数学题吗？123乘以456等于多少？",
     "expected_keywords": [], "spot_names": [], "difficulty": "easy", "should_refuse": True},
    {"id": "B-009", "question": "灵山附近有什么酒店可以住？",
     "expected_keywords": [], "spot_names": [], "difficulty": "medium", "should_refuse": True},
    {"id": "B-010", "question": "你觉得佛教和道教哪个更好？",
     "expected_keywords": [], "spot_names": [], "difficulty": "hard", "should_refuse": True},
]


def build_dataset() -> list[dict]:
    dataset: list[dict] = []
    for group, category in [
        (FACTUAL, "factual"),
        (INTRO, "intro"),
        (CULTURAL, "cultural"),
        (COMPARATIVE, "comparative"),
        (ROUTE, "route"),
        (PARAPHRASE, "paraphrase"),
        (BOUNDARY, "boundary"),
    ]:
        for item in group:
            entry = {
                "id": item["id"],
                "question": item["question"],
                "expected_keywords": item["expected_keywords"],
                "category": category,
                "difficulty": item.get("difficulty", "medium"),
                "spot_names": item.get("spot_names", []),
                "should_refuse": item.get("should_refuse", False),
            }
            if item["id"] in KEYWORD_ALIAS_GROUPS:
                entry["expected_keyword_groups"] = KEYWORD_ALIAS_GROUPS[item["id"]]
            dataset.append(entry)
    return dataset


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    dataset = build_dataset()
    TARGET.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")

    # 统计
    from collections import Counter
    cat_counts = Counter(item["category"] for item in dataset)
    diff_counts = Counter(item["difficulty"] for item in dataset)
    refuse_count = sum(1 for item in dataset if item["should_refuse"])

    print(f"生成评测集：{TARGET}")
    print(f"总题数：{len(dataset)}")
    print(f"分类分布：{dict(cat_counts)}")
    print(f"难度分布：{dict(diff_counts)}")
    print(f"边界题（应拒答）：{refuse_count}")


if __name__ == "__main__":
    main()
