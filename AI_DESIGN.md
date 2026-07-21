# AI 设计

## LLM 设计

- 主模型：DeepSeek
- 备用模型：Qwen
- 切换方式：通过环境变量 `LLM_PROVIDER` 控制
- 无可用 API Key 时使用 `LocalFallbackLLMClient`，保证问答链路可演示。

## RAG 流水线

文档收集 → 清洗 → 分块 → Embedding → 向量存储 → 相似度检索 → 上下文构建 → LLM 生成。

当前 Embedding 使用本地确定性向量作为降级方案，优先保证检索、索引和演示稳定。后续可替换为 BGE-M3 等多语言向量模型。

## Prompt 原则

- 只基于已检索资料回答景区事实问题。
- 无依据时说明暂未在知识库中找到。
- 输出风格应像景区导游，避免客服式生硬回答。
- 对景区无关问题触发拒答，避免导游角色漂移。

## 准确率评测

| 测试集 | 问题数 | 准确率 | 日期 |
|---|---:|---:|---|
| `data/eval/qa_testset.json` | 100 | 待运行 | 2026-07-15 |

评测命令：

```powershell
python scripts/eval_qa_accuracy.py --base-url http://localhost:8000
```

## 延迟评测

| 阶段 | 平均耗时 | P95 |
|---|---:|---:|
| 待测试 | - | - |

## 语音与数字人

- ASR：后端协议兼容 faster-whisper；缺模型或依赖时返回清晰错误，前端回退文本输入。
- TTS：后端提供统一协议；默认 `browser` 模式，由浏览器语音合成播报。
- 数字人 MVP：前端 2D 数字人页面承载讲解、字幕和语音播放。

## 实时数字人增强

LiveTalking、MuseTalk 等实时口型同步方案作为增强项，不进入 MVP 强依赖。建议以独立服务接入：

| 层级 | MVP 当前实现 | 增强接入方式 |
|---|---|---|
| 文本生成 | `/api/chat/messages` | 继续复用 |
| 语音合成 | `/api/speech/tts` 浏览器降级 | 替换为云 TTS 或本地 TTS |
| 数字人渲染 | Vue 2D 页面 | 独立 GPU 服务输出视频流 |
| 前端播放 | 字幕 + 音频 | WebRTC 或 HLS 播放 |

增强服务不得阻塞核心问答、路线、反馈和大屏功能。若 GPU 服务不可用，前端保持 2D 数字人和浏览器 TTS。
