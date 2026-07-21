<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ElMessage } from 'element-plus'
import { askImageQuestion, getMultimodalCapability, type MultimodalCapability } from '../api/multimodal'

const capability = ref<MultimodalCapability | null>(null)
const imageFile = ref<File | null>(null)
const imagePreview = ref('')
const question = ref('这张图可能是灵山胜境的哪个景点？请讲一下文化含义和游览建议。')
const answer = ref('')
const loading = ref(false)

onMounted(async () => {
  capability.value = await getMultimodalCapability()
})

function handleImageChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.error('请上传图片文件')
    return
  }
  imageFile.value = file
  imagePreview.value = URL.createObjectURL(file)
}

async function submit() {
  if (!imageFile.value) {
    ElMessage.warning('请先上传景区图片')
    return
  }
  loading.value = true
  answer.value = ''
  try {
    const result = await askImageQuestion(imageFile.value, question.value)
    answer.value = result.answer
    capability.value = {
      provider: result.provider,
      model: result.model,
      configured: result.configured,
      input_modes: ['image', 'text'],
      purpose: capability.value?.purpose || '景区图片识别、图文联合问答、文化讲解和路线建议',
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '多模态识别失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="vision-page">
    <header>
      <div>
        <p class="eyebrow">多模态大模型</p>
        <h1>拍照问 AI 导游</h1>
        <p>上传景区照片并输入问题，由视觉语言模型进行图片识别、文化讲解和路线建议。</p>
      </div>
      <nav>
        <RouterLink to="/avatar">数字人导游</RouterLink>
        <RouterLink to="/chat">文本问答</RouterLink>
        <RouterLink to="/">首页</RouterLink>
      </nav>
    </header>

    <section class="capability" v-if="capability">
      <strong>核心多模态模型：{{ capability.provider }} / {{ capability.model }}</strong>
      <span :class="{ ready: capability.configured }">
        {{ capability.configured ? '已配置，可调用图文大模型' : '未配置 API Key，演示环境会给出明确提示' }}
      </span>
      <p>{{ capability.purpose }}</p>
    </section>

    <section class="panel">
      <label class="upload">
        <input type="file" accept="image/*" @change="handleImageChange" />
        <span>{{ imageFile ? imageFile.name : '上传景区照片' }}</span>
      </label>

      <img v-if="imagePreview" :src="imagePreview" alt="上传的景区图片预览" class="preview" />

      <label class="question">
        <span>想问导游什么？</span>
        <textarea v-model="question" rows="4" />
      </label>

      <button :disabled="loading" @click="submit">
        {{ loading ? '识别中...' : '图文联合提问' }}
      </button>
    </section>

    <section v-if="answer" class="panel answer">
      <h2>AI 导游回答</h2>
      <p>{{ answer }}</p>
    </section>
  </main>
</template>

<style scoped>
.vision-page {
  min-height: 100vh;
  padding: 32px;
  background: #f6f1e8;
  color: #1f2937;
}

header,
.panel,
.capability {
  max-width: 980px;
  margin: 0 auto 18px;
}

header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
}

.eyebrow {
  color: #8b5e34;
  font-weight: 800;
}

nav {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

nav a,
button {
  border: 0;
  border-radius: 999px;
  padding: 10px 16px;
  color: #fff;
  background: #8b5e34;
  text-decoration: none;
  font-weight: 800;
}

.capability,
.panel {
  border-radius: 24px;
  padding: 22px;
  background: #fff;
  box-shadow: 0 18px 50px rgb(62 45 30 / 10%);
}

.capability span {
  display: inline-block;
  margin-left: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #fee2e2;
  color: #991b1b;
}

.capability span.ready {
  background: #dcfce7;
  color: #166534;
}

.upload {
  display: block;
  border: 2px dashed #d6c5ad;
  border-radius: 18px;
  padding: 24px;
  text-align: center;
  color: #8b5e34;
  font-weight: 800;
  cursor: pointer;
}

.upload input {
  display: none;
}

.preview {
  display: block;
  max-width: 100%;
  max-height: 420px;
  margin: 18px auto;
  border-radius: 18px;
  object-fit: contain;
}

.question {
  display: grid;
  gap: 8px;
  margin: 18px 0;
  color: #475467;
  font-weight: 700;
}

textarea {
  border: 1px solid #d6c5ad;
  border-radius: 16px;
  padding: 12px;
  font: inherit;
  resize: vertical;
}

button:disabled {
  opacity: 0.6;
}

.answer p {
  white-space: pre-wrap;
  line-height: 1.8;
}
</style>
