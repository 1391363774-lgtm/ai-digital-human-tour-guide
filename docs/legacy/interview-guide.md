# 工程讲解与练习

现阶段可如实介绍：这是团队的景区导览原型，使用 FastAPI/Vue，把资料检索、模型回答和语音展示连接起来；目前正通过 AI 辅助补充异常和取消测试。local_hash 是无模型的确定性向量，不可称语义模型。生产规模、真实用户指标尚无证据。

## SSE 核心问题

`async def` 不会自动把同步网络读取变成非阻塞。模型每次等待网络都应让出事件循环，数据库同步工作则顺序送到工作线程。代码见 `backend/app/api/routes/chat.py` 和 `backend/app/services/llm_client.py`。

TCP 字节块不等于一个汉字，也不等于一个 SSE 事件。`frontend/src/api/stream.ts` 先增量解码 UTF-8，再按行和空行组成事件；`api/chat.ts` 检查业务字段和 done。提前断线不能当成功。

一次回答可以 completed/refused/partial/failed/cancelled。部分正文应保留用于排错和用户查看，但不能伪装成功或把另一个模型答案直接拼上去。`Message.status` 与迁移 0004 体现这个选择。

30—60 分钟练习（未认定本人完成）：建立自己的分支，给 SSE 测试增加“同一流中 request_id 改变”和“等待 reader.read 时取消”两条回归；展示失败→修复/通过，并解释取消如何到达 reader 和后端。不要只截图绿色测试，保留你自己的 diff 和讲解。

可使用的简历措辞：在团队景区数字人原型上，借助 AI 辅助实现并审查流式协议、失败状态和离线回归；具体个人负责范围以本人提交与讲解核验为准。
本人实际完成练习后才可写的模板：本人负责【源码范围】，复现【失败场景】，补充【本人编写测试】，在【实际环境】验证【实际结果】。未知数字保留【待补充】，不写生产提升。

## 两分钟项目介绍（能力归属保持真实）

这是团队的景区导览应用原型，服务游客讲解和管理员资料维护。FastAPI 负责资料、检索、模型、会话和语音接口，Vue 显示字幕、引用和数字人。SQL 保存文档/片段/会话，Chroma 是可选向量索引；local_hash 是确定性散列，不是训练好的中文语义模型。DeepSeek/Qwen 按配置顺序切换，没有 Key 时是资料摘录，不是离线大模型。

本轮借助 AI 辅助补齐工程失败路径：空流切换但部分回答不拼接；异步 HTTP 让慢流期间其他请求推进；SQL 版本和可重试向量清理处理知识变更；前端将文本生成和音频播放分开管理，用有界队列、取消信号和请求 ID 防止重播/旧请求污染。口型只是实际音量驱动，静音闭嘴，不声称音素同步。无 Key 演示与离线测试可以现场运行。真实云模型、声音听感、生产规模以及本人独立掌握情况，需要另行验证，不能拿自动测试替代。

## 一个请求的完整路径

`AvatarView.askAvatar` → `api/chat.streamChatMessage`（游客凭据/AbortSignal）→ `routes/chat.chat_stream` → 工作线程中的 `ChatService.prepare_stream`（会话归属、检索、prompt）→ async LLM 流 → source/text/error/done → 前端分句/队列 → `/api/speech/tts` → AudioPlayer 等 ended。finally 关闭资源并记录回答终态。引用从 SQL 当前片段生成，而非凭模型自己写链接。

## 三次关键取舍

1. 模型网络改异步，SQL 工作顺序放线程池；不让同一个 Session 并行跨线程，不靠线程池包装阻塞 socket 来假装取消。
2. SQL 为权威，向量失败可降词法，物理删除通过持久清理队列重试；接受小型索引写锁成本，不宣称 SQL/Chroma 原子事务。
3. 先逐段有界播报和实际音量口型，牺牲一些合成并行度换可解释生命周期；没有可靠音素时间戳就不展示假对齐。

## 十个追问及源码入口

1. 为什么 async def 还可能卡住？同步 readline 不主动让出循环。看 `backend/app/services/llm_client.py::achat_stream`，对比保留的同步方法及并发探针。
2. HTTP 200/流正常结束为什么也失败？有效文本必须非空白，空流触发备用；看 `FailoverLLMClient` 和 `test_llm_failover.py`。
3. 为什么首段后不切换？第二模型的回答并不是前一段续写；保留 partial/error。看 `routes/chat.py` 和 `test_stream_contract.py`。
4. 停止按钮怎么传到底层？AbortController → reader.cancel/fetch → 后端断连 → 上游 aclose；音频队列独立 cancel。看 `api/stream.ts`、`audio/speech-queue.ts`、`core/streaming.py`。
5. 读到的 SQL 对象可同时丢给两个线程吗？Session 不是并发工作单元；本实现顺序工作线程调用，模型网络不同时操作它。看 `routes/chat.py::prepare`。
6. 清本机缓存够吗？别的 worker 仍持旧缓存。共享 SQL revision 进入 key，老请求只能写老版本；看 `core/knowledge_revision.py`、`rag_service.py`。
7. 删了 SQL，为何 Chroma 还能返回旧片段？两者不共享事务。检索核对 SQL ID/内容，旧向量进入 pending cleanup；看 `knowledge_index_service.py`、`test_index_consistency.py`。
8. 为什么不叫精准口型同步？RMS 只有声音强弱，没有音素类别/时间标签；看 `audio/energy-mouth.ts`、`audio/audio-player.ts`。
9. 100 题测什么 bug？关键词事实遗漏、数字误匹配、景点检索错误、越界不拒答等代理行为；不是每题一个 bug，关键词通过仍可能幻觉。看 `scripts/eval_qa_accuracy.py` 和 `test_eval_scoring.py`。
10. 管理 key/游客 key 是完整权限体系吗？不是。游客 key 是持有者凭据，没有账号登录/找回/到期；管理员 key 不应放 VITE 构建产物。看 `core/access.py`、`api/access.ts`；公网仍需更多保护。

## 30—60 分钟现场练习（未完成记录）

- 异步与 HTTP：自己改一个读取超时配置，补首段前/后的测试，解释为什么两种 fallback 行为不同；只用 mock，不调用收费服务。
- SQL 与 Git：自己的分支补“知识更新事务回滚，版本不变”断言，展示 `git diff` 和测试；不要把 agent 现成提交署成个人独立实现。
- 播放排错：自己加“等待播放时页面退出”的断言，说明 listener、URL、队列各由谁释放；用诊断面板演示，不把 stop cleanup 当实际停声延迟。

每项验收是本人 diff + 运行输出 + 口头解释。工程推进不等待练习，但个人贡献状态独立记录。现在可写“参与团队景区 AI 应用，使用 AI 辅助迭代并建立离线可靠性测试”，具体职责仍需真实经历支撑；完成本人实践后才写“本人复现并修复【问题】，补充【测试】，在【环境】验证【结果】”。不得写生产用户量、性能提升百分比、独立研发 Coding Agent 或未经测量的音素准确度。
