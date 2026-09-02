# 灵山胜境 AI 导游问答评测包

## 这是什么

一套 100 题的问答评测集，用于测试 AI 导游系统对灵山胜境景区知识的回答准确率。

## 文件清单

```
评测包/
├── eval.py          ← 评测脚本（纯 Python，无需安装任何库）
├── qa_testset.json  ← 100 题评测数据集
└── README.txt       ← 本说明文件
```

## 评测集说明

共 100 题，覆盖 7 个类别：

| 类别 | 题数 | 说明 |
|------|------|------|
| factual | 35 | 事实型：数字、年份、尺寸等可验证信息 |
| intro | 15 | 介绍型：景点整体介绍 |
| cultural | 10 | 文化型：佛教文化、历史背景 |
| comparative | 10 | 对比型：多景点比较 |
| route | 10 | 路线型：游览路线推荐 |
| paraphrase | 10 | 改写型：口语化/同义改写提问 |
| boundary | 10 | 边界型：超范围问题（应拒答） |

## 运行要求

- Python 3.8 及以上
- 无需安装任何第三方库（仅用标准库）
- 你的 AI 需要有一个 HTTP API 接口

## 使用方法

### 方式一：OpenAI 兼容接口

如果你的 AI 是 OpenAI 兼容的 /v1/chat/completions 接口：

```
python eval.py --mode openai --api-url http://你的API地址/v1/chat/completions --api-key 你的key --model 模型名
```

示例：
```
python eval.py --mode openai --api-url https://api.deepseek.com/v1/chat/completions --api-key sk-xxx --model deepseek-chat
```

### 方式二：自定义 HTTP 接口

如果你的 AI 是自定义的 POST 接口（发 JSON、收 JSON）：

```
python eval.py --mode custom --api-url http://你的API地址/chat --question-field question --answer-field answer
```

参数说明：
- --question-field：请求中问题字段的名称（默认 question）
- --answer-field：响应中回答字段的路径（默认 answer）
  - 支持嵌套，如 data.answer 会从 {"data": {"answer": "..."}} 中取值
- --extra-fields：额外请求参数，格式 key=value,key2=value2

示例（请求体为 {"message": "问题", "top_k": 5}，返回 {"data": {"answer": "回答"}}）：
```
python eval.py --mode custom --api-url http://localhost:8000/api/chat --question-field message --answer-field data.answer --extra-fields top_k=5
```

### 其他选项

- --limit 10：只跑前 10 题快速测试
- --output report.json：指定输出文件名

## 评测结果

运行完成后会输出：

1. 终端打印汇总表（回答准确率、拒答正确率、分类别统计）
2. 生成 JSON 报告文件（默认 eval_report.json）

报告包含每道题的：问题、AI 回答、得分、是否通过、匹配到的关键词。

## 评分规则

- 事实型题目：按期望关键词组计算覆盖率；同组是同一事实的不同写法，命中任一写法即可
- 纯数字采用数值边界匹配，例如"9"不会误命中"1997"
- 边界型题目：回答中出现明确拒答语句才算正确，不把普通的“建议”二字视为拒答
- 通过线：关键词组覆盖率 ≥ 60% 算通过

## 使用边界

关键词得分是方便回归测试的代理指标，不等同于人工事实准确率。它不能识别回答中未标注的错误，也不能证明系统对其他景区的泛化能力。正式对外引用结果时，请同时记录模型、知识库版本、参数、日期和本评测脚本版本。
