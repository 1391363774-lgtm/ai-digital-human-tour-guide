"""
灵山胜境AI数字人 - 知识库构建脚本
功能：读取知识库文档 -> 文本分块 -> 向量化 -> 存入Milvus
"""
import os
import json
import re
from typing import List, Dict

# ===== 配置 =====
KNOWLEDGE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "知识库", "灵山胜境完整知识库.md")
OUTPUT_CHUNKS = os.path.join(os.path.dirname(__file__), "knowledge_chunks.json")
CHUNK_SIZE = 500  # 每块最大字符数
CHUNK_OVERLAP = 50  # 重叠字符数

def read_markdown(file_path: str) -> str:
    """读取Markdown文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def split_by_sections(text: str) -> List[Dict]:
    """按标题分割文档为段落"""
    sections = []
    lines = text.split("\n")
    current_section = {"title": "概述", "content": "", "level": 0}
    
    for line in lines:
        if line.startswith("#"):
            # 保存上一个section
            if current_section["content"].strip():
                sections.append(current_section.copy())
            # 新section
            level = len(re.match(r"^#+", line).group())
            title = line.lstrip("#").strip()
            current_section = {"title": title, "content": "", "level": level}
        else:
            current_section["content"] += line + "\n"
    
    if current_section["content"].strip():
        sections.append(current_section)
    
    return sections

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """将文本分割为固定大小的块"""
    if len(text) <= chunk_size:
        return [text.strip()]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        # 尝试在句号、换行处断开
        if end < len(text):
            # 找最近的句号或换行
            for sep in ["\n", "。", "！", "？", ".", "!", "?"]:
                last_sep = text.rfind(sep, start, end)
                if last_sep > start:
                    end = last_sep + 1
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    
    return chunks

def build_knowledge_chunks(knowledge_file: str) -> List[Dict]:
    """构建知识库分块"""
    print(f"📖 读取知识库文件: {knowledge_file}")
    text = read_markdown(knowledge_file)
    print(f"   文件总长度: {len(text)} 字符")
    
    # 按标题分割
    sections = split_by_sections(text)
    print(f"   分割为 {len(sections)} 个章节")
    
    # 分块
    all_chunks = []
    for section in sections:
        chunks = chunk_text(section["content"])
        for i, chunk in enumerate(chunks):
            all_chunks.append({
                "id": f"{section['title']}_{i}",
                "title": section["title"],
                "content": chunk,
                "source": section["title"],
                "char_count": len(chunk)
            })
    
    print(f"   总计生成 {len(all_chunks)} 个知识块")
    return all_chunks

def analyze_chunks(chunks: List[Dict]):
    """分析知识块统计信息"""
    total_chars = sum(c["char_count"] for c in chunks)
    avg_chars = total_chars / len(chunks) if chunks else 0
    print(f"\n📊 知识库统计:")
    print(f"   总知识块数: {len(chunks)}")
    print(f"   总字符数: {total_chars}")
    print(f"   平均块长: {avg_chars:.0f} 字符")
    
    # 按来源分类统计
    categories = {}
    for chunk in chunks:
        cat = chunk["source"]
        categories[cat] = categories.get(cat, 0) + 1
    print(f"   分类数: {len(categories)}")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:10]:
        print(f"     - {cat}: {count}块")

def save_chunks(chunks: List[Dict], output_path: str):
    """保存分块结果为JSON"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"\n💾 分块结果已保存: {output_path}")

def vectorize_chunks(chunks: List[Dict]):
    """向量化知识块（需要BGE模型）"""
    print(f"\n🤖 开始向量化...")
    print(f"   (需要安装 sentence-transformers 和 BGE 模型)")
    print(f"   模型: BAAI/bge-large-zh-v1.5")
    # TODO: 接入BGE模型进行向量化
    # from sentence_transformers import SentenceTransformer
    # model = SentenceTransformer('BAAI/bge-large-zh-v1.5')
    # for chunk in chunks:
    #     chunk["embedding"] = model.encode(chunk["content"]).tolist()
    print(f"   [待实现] 请安装依赖后运行向量化")

def store_to_milvus(chunks: List[Dict]):
    """存入Milvus向量数据库"""
    print(f"\n💾 存入Milvus...")
    # TODO: 接入Milvus
    # from pymilvus import connections, Collection, Field, Schema, DataType
    print(f"   [待实现] 请配置Milvus连接后运行")

if __name__ == "__main__":
    print("=" * 60)
    print("  灵山胜境AI数字人 - 知识库构建工具")
    print("=" * 60)
    
    chunks = build_knowledge_chunks(KNOWLEDGE_FILE)
    analyze_chunks(chunks)
    save_chunks(chunks, OUTPUT_CHUNKS)
    
    # 向量化和存储（需要安装依赖）
    # vectorize_chunks(chunks)
    # store_to_milvus(chunks)
    
    print(f"\n✅ 知识库构建完成！")
