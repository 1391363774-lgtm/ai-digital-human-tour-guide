import { apiClient, unwrap } from './client'

export interface MultimodalCapability {
  provider: string
  model: string
  configured: boolean
  input_modes: string[]
  purpose: string
}

export interface MultimodalAnswer {
  answer: string
  provider: string
  model: string
  configured: boolean
}

export function getMultimodalCapability() {
  return unwrap<MultimodalCapability>(apiClient.get('/api/multimodal/capability'))
}

export function askImageQuestion(image: File, question: string) {
  const form = new FormData()
  form.append('image', image)
  form.append('question', question)
  return unwrap<MultimodalAnswer>(apiClient.post('/api/multimodal/image-question', form))
}
