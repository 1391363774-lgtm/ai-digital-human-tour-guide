import { apiClient, unwrap } from './client'

export interface AvatarConfigPayload {
  avatar: {
    name: string
    engine: 'image3d' | 'live2d' | 'svg' | string
    avatarImage: string
    greeting: string
    appearance: {
      hairColor: string
      hairStyle: string
      eyeColor: string
      skinColor: string
      outfitStyle: string
      outfitPrimary: string
      outfitAccent: string
      accessories: string[]
    }
    voice: {
      provider: string
      voiceName: string
      label: string
      rate: number
    }
    image3d: {
      landmarks: Record<string, number>
    }
    live2d?: {
      modelUrl: string
      idleMotionGroup: string
      expressions: string[]
      modelMap?: Record<string, string>
    }
    background?: Record<string, string>
  }
}

export interface AvatarModelOption {
  name: string
  label: string
  url: string
}

export function getAvatarConfig() {
  return unwrap<AvatarConfigPayload>(apiClient.get('/api/admin/avatar/config'))
}

export function getAvatarModels() {
  return unwrap<AvatarModelOption[]>(apiClient.get('/api/admin/avatar/models'))
}

export function updateAvatarConfig(payload: AvatarConfigPayload) {
  return unwrap<AvatarConfigPayload>(apiClient.put('/api/admin/avatar/config', payload))
}
