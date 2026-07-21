import axios from 'axios'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 30000,
})

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export async function unwrap<T>(request: Promise<{ data: ApiResponse<T> }>): Promise<T> {
  try {
    const response = await request
    if (response.data.code !== 200) {
      throw new Error(response.data.message || '请求失败')
    }
    return response.data.data
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const detail = error.response?.data?.detail || error.response?.data?.message
      throw new Error(typeof detail === 'string' ? detail : error.message)
    }
    throw error
  }
}
