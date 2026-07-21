<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { listSpots } from '../api/spot'
import type { ScenicSpot } from '../types/spot'

interface KnownLocation {
  keywords: string[]
  latitude: number
  longitude: number
  address: string
  mapX: number
  mapY: number
}

const GUIDE_MAP_SRC = '/assets/maps/lingshan-guide.png'
const PUBLIC_MAP_URL = 'https://www.openstreetmap.org/#map=17/31.416667/120.100000'
const REALTIME_MAP_URL = 'https://www.openstreetmap.org/export/embed.html?bbox=120.0900%2C31.4100%2C120.1100%2C31.4260&layer=mapnik&marker=31.416667%2C120.100000'
const LINGSHAN_LOCATION = {
  latitude: 31.416667,
  longitude: 120.1,
  address: '江苏省无锡市滨湖区马山灵山路1号',
}

const GUIDE_DURATION_MINUTES: Record<string, number> = {
  灵山胜境: 240,
  灵山大佛: 60,
  祥符禅寺: 40,
  九龙灌浴: 25,
  灵山梵宫: 75,
  五印坛城: 50,
  佛教文化博览馆: 45,
  百子戏弥勒: 15,
  佛足坛: 15,
  菩提大道: 20,
  阿育王柱: 15,
  灵山大照壁: 10,
  五明桥: 10,
  五智门: 15,
  降魔成道: 15,
  拈花湾禅意小镇: 240,
  拈花广场: 20,
  拈花塔: 25,
  香月花街: 60,
  拈花堂: 50,
  五灯湖: 45,
  梵天花海: 45,
  妙音台: 35,
  微笑广场: 20,
}

const GUIDE_MAP_POINTS: Record<string, { mapX: number; mapY: number; width?: number; height?: number }> = {
  '无尽意斋': { mapX: 4.4, mapY: 24.1, width: 3.0, height: 9.0 },
  '灵山大佛': { mapX: 18.9, mapY: 18.5, width: 3.0, height: 9.0 },
  '佛教文化博览馆': { mapX: 95.1, mapY: 46.7, width: 3.0, height: 9.0 },
  '祥符禅寺': { mapX: 27.1, mapY: 33.5, width: 3.0, height: 9.0 },
  '阿育王柱': { mapX: 29.9, mapY: 46.1, width: 3.0, height: 9.0 },
  '百子戏弥勒': { mapX: 41.3, mapY: 38.0, width: 3.0, height: 9.0 },
  '降魔浮雕': { mapX: 74.7, mapY: 82.2, width: 3.0, height: 9.0 },
  '九龙灌浴': { mapX: 28.4, mapY: 56.1, width: 3.0, height: 9.0 },
  '佛足坛': { mapX: 29.2, mapY: 67.0, width: 3.0, height: 9.0 },
  '菩提大道': { mapX: 25.0, mapY: 59.1, width: 3.0, height: 9.0 },
  '五智门': { mapX: 36.2, mapY: 73.4, width: 3.0, height: 9.0 },
  '灵山大照壁': { mapX: 36.5, mapY: 50.7, width: 3.0, height: 9.0 },
  '五明桥': { mapX: 39.8, mapY: 78.1, width: 3.0, height: 9.0 },
  '灵山梵宫': { mapX: 84.3, mapY: 39.6, width: 3.0, height: 9.0 },
  '五印坛城': { mapX: 60.3, mapY: 60.1, width: 3.0, height: 9.0 },
  '曼飞龙塔': { mapX: 93.9, mapY: 55.8, width: 3.0, height: 9.0 },
}

const KNOWN_LOCATIONS: KnownLocation[] = [
  {
    keywords: ['灵山胜境', '灵山景区'],
    ...LINGSHAN_LOCATION,
    mapX: 38,
    mapY: 82,
  },
  {
    keywords: ['灵山大佛', '大佛'],
    latitude: 31.4218,
    longitude: 120.1002,
    address: '灵山胜境景区北部，祥符禅寺后方',
    mapX: 25,
    mapY: 18,
  },
  {
    keywords: ['祥符禅寺', '祥符寺'],
    latitude: 31.4205,
    longitude: 120.0999,
    address: '灵山胜境景区北部',
    mapX: 35,
    mapY: 34,
  },
  {
    keywords: ['九龙灌浴'],
    latitude: 31.4179,
    longitude: 120.1001,
    address: '灵山胜境景区中轴线中心区域',
    mapX: 38,
    mapY: 55,
  },
  {
    keywords: ['灵山梵宫', '梵宫'],
    latitude: 31.4181,
    longitude: 120.1026,
    address: '灵山胜境景区东北部',
    mapX: 72,
    mapY: 44,
  },
  {
    keywords: ['五印坛城'],
    latitude: 31.4168,
    longitude: 120.103,
    address: '灵山胜境景区东南部',
    mapX: 58,
    mapY: 64,
  },
  {
    keywords: ['拈花湾', '禅意小镇'],
    latitude: 31.4249,
    longitude: 120.0638,
    address: '江苏省无锡市滨湖区马山环山西路68号',
    mapX: 86,
    mapY: 58,
  },
  {
    keywords: ['检票口', '入口', '游客中心'],
    latitude: 31.4146,
    longitude: 120.0998,
    address: '灵山胜境游客入口与检票口区域',
    mapX: 39,
    mapY: 89,
  },
  {
    keywords: ['佛足坛'],
    latitude: 31.4156,
    longitude: 120.0999,
    address: '灵山胜境中轴线南段',
    mapX: 37,
    mapY: 72,
  },
  {
    keywords: ['菩提大道'],
    latitude: 31.4164,
    longitude: 120.0999,
    address: '灵山胜境中轴线，九龙灌浴南侧',
    mapX: 35,
    mapY: 64,
  },
  {
    keywords: ['阿育王柱'],
    latitude: 31.4192,
    longitude: 120.1002,
    address: '九龙灌浴北侧',
    mapX: 34,
    mapY: 26,
  },
  {
    keywords: ['百子戏弥勒', '弥勒'],
    latitude: 31.4188,
    longitude: 120.1013,
    address: '阿育王柱与祥符禅寺之间',
    mapX: 47,
    mapY: 40,
  },
]

const spots = ref<ScenicSpot[]>([])
const keyword = ref('')
const selected = ref<ScenicSpot | null>(null)
const loading = ref(false)
const locating = ref(false)
const userLocation = ref<{ latitude: number; longitude: number } | null>(null)
const mapMode = ref<'realtime' | 'guide'>('realtime')

onMounted(refresh)

const visibleSpots = computed(() => {
  const query = keyword.value.trim()
  if (!query) return spots.value
  return spots.value.filter((spot) => {
    return [spot.name, spot.code, spot.category, spot.location].some((value) => value?.includes(query))
  })
})

const positionedSpots = computed(() => {
  const items = visibleSpots.value.map(enrichSpotLocation)
  const withCoordinates = items.filter((item) => item.latitude !== null && item.longitude !== null)
  if (withCoordinates.length >= 2) {
    const latitudes = withCoordinates.map((item) => item.latitude as number)
    const longitudes = withCoordinates.map((item) => item.longitude as number)
    const minLat = Math.min(...latitudes)
    const maxLat = Math.max(...latitudes)
    const minLng = Math.min(...longitudes)
    const maxLng = Math.max(...longitudes)
    return items.map((item) => {
      const x = normalize(item.longitude, minLng, maxLng)
      const y = 100 - normalize(item.latitude, minLat, maxLat)
      return { ...item, x, y }
    })
  }
  return items.map((item) => ({ ...item, x: 50, y: 50 }))
})

const selectedLocation = computed(() => selected.value ? enrichSpotLocation(selected.value) : null)
const selectedMapUrl = computed(() => selectedLocation.value ? osmMapUrl(selectedLocation.value) : osmMapUrl())
const selectedNavigationUrl = computed(() => selectedLocation.value ? osmDirectionsUrl(selectedLocation.value) : osmDirectionsUrl())
const selectedAmapUrl = computed(() => selectedLocation.value ? amapMarkerUrl(selectedLocation.value) : amapMarkerUrl())
const userNavigationUrl = computed(() => {
  const target = selectedLocation.value
  if (!target || !userLocation.value) return ''
  return `https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${userLocation.value.latitude},${userLocation.value.longitude};${target.latitude},${target.longitude}`
})

async function refresh() {
  loading.value = true
  try {
    spots.value = await listSpots()
    selected.value = spots.value[0] || null
  } finally {
    loading.value = false
  }
}

function normalize(value: number, min: number, max: number) {
  if (max === min) return 50
  return 8 + ((value - min) / (max - min)) * 84
}

function enrichSpotLocation(spot: ScenicSpot) {
  const known = findKnownLocation(spot)
  const guidePoint = GUIDE_MAP_POINTS[spot.name]
  const hasMapPoint = Boolean(guidePoint || known || (spot.latitude !== null && spot.longitude !== null))
  const latitude = spot.latitude ?? known?.latitude ?? LINGSHAN_LOCATION.latitude
  const longitude = spot.longitude ?? known?.longitude ?? LINGSHAN_LOCATION.longitude
  return {
    spot,
    latitude,
    longitude,
    address: spot.location || known?.address || LINGSHAN_LOCATION.address,
    mapX: guidePoint?.mapX ?? known?.mapX ?? (hasMapPoint ? coordinateToGuideX(longitude) : 92),
    mapY: guidePoint?.mapY ?? known?.mapY ?? (hasMapPoint ? coordinateToGuideY(latitude) : 92),
    hotspotWidth: guidePoint?.width ?? 3.2,
    hotspotHeight: guidePoint?.height ?? Math.min(Math.max(spot.name.length * 2.2 + 2, 7), 16),
    source: guidePoint ? '2D 导览图精确点位' : spot.latitude !== null && spot.longitude !== null ? '数据库坐标' : known ? '景区真实位置兜底' : '其他景点区域',
  }
}

function findKnownLocation(spot: ScenicSpot) {
  const text = `${spot.name}${spot.code}${spot.location || ''}${spot.description || ''}`
  return KNOWN_LOCATIONS.find((item) => item.keywords.some((keyword) => text.includes(keyword)))
}

function coordinateToGuideX(longitude: number) {
  return Math.max(8, Math.min(92, 38 + (longitude - LINGSHAN_LOCATION.longitude) * 1800))
}

function coordinateToGuideY(latitude: number) {
  return Math.max(10, Math.min(90, 82 - (latitude - LINGSHAN_LOCATION.latitude) * 1800))
}

function osmMapUrl(location = selectedLocation.value) {
  const target = location || {
    spot: { name: '灵山胜境' } as ScenicSpot,
    latitude: LINGSHAN_LOCATION.latitude,
    longitude: LINGSHAN_LOCATION.longitude,
  }
  return `https://www.openstreetmap.org/?mlat=${target.latitude}&mlon=${target.longitude}#map=17/${target.latitude}/${target.longitude}`
}

function osmDirectionsUrl(location = selectedLocation.value) {
  const target = location || {
    latitude: LINGSHAN_LOCATION.latitude,
    longitude: LINGSHAN_LOCATION.longitude,
  }
  return `https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=;${target.latitude},${target.longitude}`
}

function amapMarkerUrl(location = selectedLocation.value) {
  const target = location || {
    spot: { name: '灵山胜境' } as ScenicSpot,
    latitude: LINGSHAN_LOCATION.latitude,
    longitude: LINGSHAN_LOCATION.longitude,
  }
  return `https://uri.amap.com/marker?position=${target.longitude},${target.latitude}&name=${encodeURIComponent(target.spot.name)}&src=scenic-ai-guide&coordinate=gaode&callnative=0`
}

function recommendedDurationMinutes(spot: ScenicSpot) {
  if (spot.recommended_duration_minutes) return spot.recommended_duration_minutes
  const exact = GUIDE_DURATION_MINUTES[spot.name]
  if (exact) return exact
  const text = `${spot.name} ${spot.category || ''} ${spot.core_function || ''} ${spot.open_info || ''}`
  if (text.includes('每场时长约15分钟')) return 25
  if (text.includes('每场时长约20分钟')) return 35
  if (text.includes('每场时长约30分钟')) return 45
  if (text.includes('每场时长约40分钟')) return 50
  if (text.includes('小镇')) return 180
  if (text.includes('博览馆') || text.includes('展厅') || text.includes('艺术')) return 45
  if (text.includes('演艺') || text.includes('表演') || text.includes('动态')) return 30
  if (text.includes('寺') || text.includes('佛') || text.includes('坛城')) return 40
  if (text.includes('广场') || text.includes('大道') || text.includes('桥') || text.includes('壁')) return 15
  return 25
}

function durationLabel(spot: ScenicSpot) {
  const minutes = recommendedDurationMinutes(spot)
  return `${spot.recommended_duration_minutes ? '' : '约 '}${minutes} 分钟`
}

function markerLabel(name: string) {
  return name.replace('灵山', '').replace('佛教文化', '佛博').slice(0, 3)
}

function locateMe() {
  if (!navigator.geolocation) {
    window.alert('当前浏览器不支持定位，请直接使用地图导航。')
    return
  }
  locating.value = true
  navigator.geolocation.getCurrentPosition(
    (position) => {
      userLocation.value = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
      }
      locating.value = false
    },
    () => {
      locating.value = false
      window.alert('定位失败，请检查浏览器定位权限。')
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
  )
}
</script>

<template>
  <main class="map-page">
    <header>
      <div>
        <p class="eyebrow">景区地图</p>
        <h1>灵山胜境导览图</h1>
        <p>默认使用实时电子地图与定位导航；静态 2D 导览图作为景区内路线和景点关系参考。</p>
      </div>
      <nav>
        <RouterLink to="/chat">问 AI 导游</RouterLink>
        <RouterLink to="/routes">路线推荐</RouterLink>
        <RouterLink to="/">首页</RouterLink>
      </nav>
    </header>

    <section class="layout">
      <aside class="panel">
        <div class="toolbar">
          <input v-model="keyword" placeholder="搜索景点、分类或位置" />
          <button @click="refresh">{{ loading ? '加载中...' : '刷新' }}</button>
        </div>
        <article
          v-for="spot in visibleSpots"
          :key="spot.id"
          class="spot-card"
          :class="{ active: selected?.id === spot.id }"
          @click="selected = spot"
        >
          <strong>{{ spot.name }}</strong>
          <p>{{ spot.category || '综合景点' }} · {{ durationLabel(spot) }}</p>
        </article>
        <p v-if="!visibleSpots.length" class="empty">暂无匹配景点</p>
      </aside>

      <section class="map-panel">
        <div class="map-switch">
          <button :class="{ active: mapMode === 'realtime' }" @click="mapMode = 'realtime'">实时地图</button>
          <button :class="{ active: mapMode === 'guide' }" @click="mapMode = 'guide'">2D 导览图</button>
          <span>GPS 弱或室内定位不准时，可切换 2D 导览图并按入口-中轴线-大佛方向人工校准。</span>
        </div>

        <div v-if="mapMode === 'realtime'" class="realtime-map">
          <iframe :src="REALTIME_MAP_URL" title="灵山胜境实时电子地图"></iframe>
          <div class="realtime-overlay">
            <strong>实时地图与导航兜底</strong>
            <p>页面内使用免登录 OSM 地图；如果你提供高德地图链接，我可以继续替换为你指定的免登录高德入口。</p>
            <div class="actions">
              <a :href="PUBLIC_MAP_URL" target="_blank" rel="noreferrer">打开 OSM 地图</a>
              <a :href="selectedAmapUrl" target="_blank" rel="noreferrer">高德免登录查看</a>
              <a :href="selectedMapUrl" target="_blank" rel="noreferrer">OpenStreetMap 定位</a>
              <button type="button" class="link-button" @click="locateMe">{{ locating ? '定位中...' : '获取我的位置' }}</button>
            </div>
          </div>
        </div>

        <div v-else class="map-canvas">
          <img class="guide-map" :src="GUIDE_MAP_SRC" alt="灵山胜境 2D 导览图" />
          <button
            v-for="item in positionedSpots"
            :key="item.spot.id"
            class="marker"
            :class="{ active: selected?.id === item.spot.id }"
            :style="{
              left: `${item.mapX}%`,
              top: `${item.mapY}%`,
              width: `${item.hotspotWidth}%`,
              height: `${item.hotspotHeight}%`,
            }"
            :title="item.spot.name"
            :aria-label="`查看${item.spot.name}`"
            :data-label="item.spot.name"
            @click="selected = item.spot"
          >
            <span class="marker-text">{{ markerLabel(item.spot.name) }}</span>
          </button>
          <span class="map-label north">景区 2D 导览图</span>
        </div>

        <article v-if="selected" class="detail">
          <p class="eyebrow">{{ selected.code }} · {{ selected.category || '综合景点' }}</p>
          <h2>{{ selected.name }}</h2>
          <p>{{ selected.description || selected.core_function || '暂无详细介绍' }}</p>
          <p class="muted">位置：{{ selectedLocation?.address || '江苏省无锡市滨湖区马山灵山路1号' }}</p>
          <p class="muted">
            坐标：{{ selectedLocation?.latitude.toFixed(6) }}, {{ selectedLocation?.longitude.toFixed(6) }}
            · {{ selectedLocation?.source }}
          </p>
          <p class="muted">推荐游玩时间：{{ durationLabel(selected) }}</p>
          <p class="muted">亮点：{{ selected.highlights || '待补充' }}</p>
          <div class="actions">
            <RouterLink :to="`/chat?question=${encodeURIComponent('请介绍' + selected.name)}`">询问导游</RouterLink>
            <RouterLink to="/routes">生成路线</RouterLink>
            <a :href="selectedAmapUrl" target="_blank" rel="noreferrer">高德免登录查看</a>
            <a :href="PUBLIC_MAP_URL" target="_blank" rel="noreferrer">打开 OSM 地图</a>
            <a :href="selectedMapUrl" target="_blank" rel="noreferrer">OpenStreetMap 查看</a>
            <a :href="selectedNavigationUrl" target="_blank" rel="noreferrer">路线导航</a>
            <button type="button" class="link-button" @click="locateMe">{{ locating ? '定位中...' : '获取我的位置' }}</button>
            <a v-if="userNavigationUrl" :href="userNavigationUrl" target="_blank" rel="noreferrer">从我的位置导航</a>
          </div>
          <p v-if="userLocation" class="muted">
            我的位置：{{ userLocation.latitude.toFixed(6) }}, {{ userLocation.longitude.toFixed(6) }}
          </p>
        </article>
      </section>
    </section>
  </main>
</template>

<style scoped>
.map-page {
  min-height: 100vh;
  padding: 24px;
  background: #f6f7fb;
  color: #1f2937;
}

header,
.layout {
  max-width: 1180px;
  margin: 0 auto 22px;
}

header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #8b5e34;
  font-weight: 700;
}

nav,
.actions,
.toolbar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

nav a,
.actions a {
  color: #8b5e34;
  text-decoration: none;
  font-weight: 700;
}

.layout {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 20px;
}

.panel,
.map-panel,
.detail {
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 14px 36px rgb(15 23 42 / 8%);
}

.panel {
  padding: 18px;
  align-self: start;
}

input {
  flex: 1;
  min-width: 180px;
  border: 1px solid #d0d5dd;
  border-radius: 12px;
  padding: 10px;
  font: inherit;
}

button {
  border: 0;
  cursor: pointer;
}

.toolbar button {
  border-radius: 12px;
  background: #8b5e34;
  color: white;
  padding: 0 14px;
}

.spot-card {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 12px;
  margin-top: 12px;
  cursor: pointer;
}

.spot-card.active {
  border-color: #8b5e34;
  background: #fff7ed;
}

.spot-card p,
.muted,
.empty {
  color: #667085;
}

.map-panel {
  padding: 20px;
}

.map-switch {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
  color: #667085;
  font-size: 13px;
}

.map-switch button {
  border-radius: 999px;
  padding: 8px 14px;
  color: #8b5e34;
  background: #fff7ed;
  font-weight: 800;
}

.map-switch button.active {
  color: #ffffff;
  background: #8b5e34;
}

.realtime-map {
  position: relative;
  min-height: 640px;
  overflow: hidden;
  border: 1px solid #bfdbfe;
  border-radius: 18px;
  background: #eef2ff;
}

.realtime-map iframe {
  display: block;
  width: 100%;
  height: 640px;
  border: 0;
}

.realtime-overlay {
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 18px;
  padding: 14px;
  border-radius: 16px;
  background: rgb(255 255 255 / 92%);
  box-shadow: 0 12px 30px rgb(15 23 42 / 14%);
}

.realtime-overlay p {
  margin: 6px 0 10px;
  color: #667085;
}

.map-canvas {
  position: relative;
  overflow: hidden;
  border-radius: 18px;
  background: #eef7cf;
  border: 1px solid #bfdbfe;
}

.guide-map {
  display: block;
  width: 100%;
  height: auto;
  user-select: none;
}

.marker {
  position: absolute;
  transform: translate(-50%, -50%);
  min-width: 28px;
  min-height: 56px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: #ffffff;
  font-size: 10px;
  box-shadow: none;
  z-index: 2;
  transform-origin: center;
  transition: background 120ms ease, border-color 120ms ease, box-shadow 120ms ease, scale 120ms ease;
  opacity: 1;
}

.marker::before {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 12px;
  height: 12px;
  border: 2px solid rgb(255 255 255 / 80%);
  border-radius: 50%;
  background: rgb(139 94 52 / 40%);
  box-shadow: 0 2px 8px rgb(15 23 42 / 18%);
  content: "";
  transform: translate(-50%, -50%);
}

.marker::after {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 6px);
  transform: translateX(-50%);
  padding: 4px 8px;
  border-radius: 999px;
  color: #8b5e34;
  background: rgb(255 255 255 / 94%);
  box-shadow: 0 6px 16px rgb(15 23 42 / 14%);
  content: attr(data-label);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 120ms ease;
}

.marker:hover,
.marker.active {
  border-color: rgb(139 94 52 / 72%);
  background: rgb(255 247 237 / 20%);
  box-shadow: inset 0 0 0 1px rgb(255 255 255 / 45%), 0 0 0 2px rgb(139 94 52 / 10%);
  scale: 1.06;
  z-index: 4;
}

.marker:hover::before,
.marker.active::before {
  width: 18px;
  height: 18px;
  background: rgb(180 35 24 / 82%);
}

.marker:hover::after,
.marker.active::after {
  opacity: 1;
}

.marker-text {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 30px;
  color: #ffffff;
  font-size: 10px;
  font-weight: 800;
  line-height: 1.1;
  pointer-events: none;
  text-align: center;
  text-shadow: 0 1px 3px rgb(0 0 0 / 45%);
  transform: translate(-50%, -50%);
}

.map-label {
  position: absolute;
  padding: 6px 10px;
  border-radius: 12px;
  color: #8b5e34;
  background: rgb(255 255 255 / 72%);
  box-shadow: 0 6px 14px rgb(15 23 42 / 8%);
  font-size: 13px;
  font-weight: 800;
  z-index: 2;
}

.north {
  left: 28px;
  top: 24px;
}

.coord-badge {
  position: absolute;
  z-index: 2;
  right: 18px;
  bottom: 18px;
  padding: 8px 12px;
  border-radius: 999px;
  color: #1f2937;
  background: rgb(255 255 255 / 88%);
  box-shadow: 0 8px 20px rgb(15 23 42 / 14%);
  font-size: 13px;
  font-weight: 700;
}

.detail {
  margin-top: 18px;
  padding: 18px;
}

.link-button {
  height: auto;
  padding: 0;
  color: #8b5e34;
  background: transparent;
  font: inherit;
  font-weight: 700;
}

@media (max-width: 920px) {
  header,
  .layout {
    display: block;
  }

  .panel {
    margin-bottom: 16px;
  }
}
</style>
