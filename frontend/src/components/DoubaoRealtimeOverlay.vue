<template>
  <Teleport to="body">
    <aside ref="panel" class="doubao-overlay" :class="{ sized: size.height && !collapsed }" @pointerdown="startDrag" @pointermove="moveDrag" @pointerup="stopDrag" @pointercancel="stopDrag" @lostpointercapture="stopDrag" aria-label="豆包实时文字悬浮窗" :style="{ left: position.x + 'px', top: position.y + 'px', width: size.width + 'px', height: !collapsed && size.height ? size.height + 'px' : undefined, '--panel-opacity': opacity / 100 }">
      <header>
        <strong>豆包 · 实时文字</strong>
        <span class="status" :class="status" :title="statusLabel" :aria-label="statusLabel"></span>
        <button v-if="status === 'connecting' || status === 'connected'" class="stop" @click="cancel">停止生成</button>
        <label class="opacity" title="调整背景透明度">透明度<input type="range" min="25" max="100" v-model="opacity" aria-label="悬浮窗背景不透明度" /></label>
        <button @click="collapsed = !collapsed" :aria-label="collapsed ? '展开豆包悬浮窗' : '收起豆包悬浮窗'">{{ collapsed ? '展开' : '收起' }}</button>
        <button @click="$emit('close')" aria-label="关闭豆包悬浮窗" title="关闭豆包输出">×</button>
      </header>
      <div v-show="!collapsed" class="panel-body">
        <p v-if="!session" class="hint">请先选择或创建会话</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <section v-show="messages.length || recording" ref="transcript" class="transcript" aria-live="polite" @scroll="onTranscriptScroll" @wheel.passive="onTranscriptWheel" @touchstart.passive="followLatest = false">
          <div class="scroll-space" :style="{ height: scrollRoom + 'px' }" aria-hidden="true"></div>
          <article v-for="(message, index) in messages" :key="index" :class="message.role" :aria-label="message.role === 'user' ? (message.input === 'text' ? '输入问题' : '语音识别') : 'AI 回复'">
            <div v-if="message.role === 'assistant'" class="doubao-markdown" v-html="renderDoubaoMarkdown(message.text)"></div>
            <p v-else>{{ message.text }}</p>
          </article>
          <article v-if="recording" class="user" aria-label="正在识别，停止后提交"><p>{{ draft || '…' }}</p></article>
          <div ref="contentEnd" class="content-end" aria-hidden="true"></div>
          <div class="scroll-space" :style="{ height: scrollRoom + 'px' }" aria-hidden="true"></div>
        </section>
        <button v-if="!followLatest" class="follow-latest" @click="resumeFollowing">↓ 回到最新内容</button>
      </div>
      <button v-for="corner in corners" :key="corner.id" class="resize-handle" :class="corner.id"
        :aria-label="corner.label + '缩放悬浮窗'" :title="corner.label + '拖动调整宽高'"
        @pointerdown.stop.prevent="startResize($event, corner.id)" />
    </aside>
  </Teleport>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { resizeFloatingOverlay } from '../utils/overlayResize'
import { renderDoubaoMarkdown, transcriptLatestTop } from '../utils/doubaoTranscript'
import { DoubaoRealtime } from '../utils/doubaoRealtime'
const props = defineProps({ session: Object, recording: Boolean, draft: String })
const emit = defineEmits(['close', 'activity'])
const status = ref('idle'), error = ref('')
watch(status, value => emit('activity', value === 'connecting' || value === 'connected'), { immediate: true })
const messages = ref([]), transcript = ref(null), contentEnd = ref(null)
const scrollRoom = ref(280)
let transcriptObserver
const statusLabel = computed(() => props.recording ? '收音中，停止后提交' : ({ idle: '等待发送问题', connecting: '提交录音中', connected: '生成文字中' }[status.value]))
let client, assistantIndex = -1, lastReply = ''
const followLatest = ref(true)
function onTranscriptScroll() {
  const element = transcript.value
  if (!element) return
  followLatest.value = Math.abs(element.scrollTop - transcriptLatestTop(element, contentEnd.value)) <= 24
}
function onTranscriptWheel(event) {
  // Stop before the next render: a pending stream update must not undo the wheel.
  if (event.deltaY !== 0) followLatest.value = false
}
async function scroll() {
  await nextTick()
  if (!followLatest.value || collapsed.value) return
  const element = transcript.value
  // Smooth scrolling on every token creates animations that fight manual scrolling.
  if (element) element.scrollTop = transcriptLatestTop(element, contentEnd.value)
}
function resumeFollowing() { followLatest.value = true; scroll() }
function handle(message) {
  if (message.type === 'ready') status.value = 'connected'
  if (message.type === 'error') error.value = message.message
  const data = message.data || {}
  if (message.event === 550 && data.content) {
    if (assistantIndex < 0 || (data.reply_id && data.reply_id !== lastReply)) {
      assistantIndex = messages.value.length
      messages.value.push({ role: 'assistant', text: '' })
    }
    lastReply = data.reply_id || ''
    messages.value[assistantIndex].text += data.content
  }
  if (message.event === 559) {
    if (data.text && assistantIndex >= 0) messages.value[assistantIndex].text = data.text
    assistantIndex = -1
  }
  scroll()
}
function cancel() { client?.close(); client = null; status.value = 'idle' }
function submit(recording) {
  cancel()
  if (recording.session_id !== props.session?.id) return
  error.value = ''
  if (!recording.text?.trim()) return
  messages.value.push({ role: 'user', text: recording.text, input: recording.audio_file ? 'voice' : 'text' })
  assistantIndex = -1; lastReply = ''; status.value = 'connecting'
  const active = new DoubaoRealtime(message => { if (client === active) handle(message) }, () => { if (client === active) status.value = 'idle' })
  client = active
  try { active.start(recording) } catch (err) { error.value = err.message; cancel() }
  scroll()
}
defineExpose({ submit, cancel })
watch(() => props.draft, () => { if (props.recording) scroll() })
watch(() => props.recording, value => { if (value) { cancel(); error.value = ''; scroll() } })
watch(() => props.session?.id, () => { cancel(); messages.value = []; error.value = ''; followLatest.value = true })
watch(() => JSON.stringify(props.session?.session_config), () => {
  if (status.value !== 'idle') { cancel(); error.value = '提示词或场景已更新，下次提交使用最新设置' }
})
const collapsed = ref(false), opacity = ref(76)
watch(collapsed, async value => { if (!value) { await nextTick(); fitInViewport(); scroll() } })
const panel = ref(null)
const size = ref({ width: Math.min(460, window.innerWidth - 24), height: null })
const position = ref({ x: Math.max(12, window.innerWidth - 500), y: Math.min(170, Math.max(0, window.innerHeight - 40)) })
const hasContent = computed(() => messages.value.length > 0 || props.recording)
watch(hasContent, async value => {
  if (!value) return
  if (size.value.height && size.value.height < 140) size.value.height = Math.min(140, window.innerHeight)
  await nextTick()
  fitInViewport()
})
const corners = [{ id: 'nw', label: '左上角' }, { id: 'ne', label: '右上角' }, { id: 'sw', label: '左下角' }, { id: 'se', label: '右下角' }]
let drag = null
function startDrag(event) {
  if (drag || event.button !== 0 || event.pointerType === 'touch' || event.target.closest('button, input, label, a, select, textarea')) return
  const scroller = transcript.value
  if (scroller?.contains(event.target)) {
    const rect = scroller.getBoundingClientRect()
    if (event.clientX >= rect.right - 16) return
  }
  event.preventDefault()
  drag = { pointerId: event.pointerId, x: event.clientX - position.value.x, y: event.clientY - position.value.y }
  panel.value.setPointerCapture(event.pointerId)
}
function startResize(event, corner) {
  if (drag || event.button !== 0) return
  const rect = panel.value.getBoundingClientRect()
  drag = { pointerId: event.pointerId, corner, x: event.clientX, y: event.clientY,
    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height } }
  panel.value.setPointerCapture(event.pointerId)
}
function moveDrag(event) {
  if (!drag || event.pointerId !== drag.pointerId) return
  if (drag.corner) {
    const rect = resizeFloatingOverlay(drag.rect, drag.corner, event.clientX - drag.x, event.clientY - drag.y,
      { width: window.innerWidth, height: window.innerHeight }, collapsed.value)
    position.value = { x: rect.x, y: rect.y }
    const keepAutoHeight = !hasContent.value && !size.value.height && Math.abs(event.clientY - drag.y) < 3
    size.value = { width: rect.width, height: collapsed.value || keepAutoHeight ? size.value.height : rect.height }
    return
  }
  const rect = panel.value.getBoundingClientRect()
  position.value = { x: event.clientX - drag.x, y: event.clientY - drag.y }
}
function stopDrag(event) {
  if (!drag || event.pointerId !== drag.pointerId) return
  drag = null
  if (panel.value?.hasPointerCapture(event.pointerId)) panel.value.releasePointerCapture(event.pointerId)
}
function fitInViewport() {
  const rect = panel.value?.getBoundingClientRect()
  if (!rect) return
  size.value.width = Math.min(size.value.width, window.innerWidth)
  if (size.value.height) size.value.height = Math.min(size.value.height, window.innerHeight)
}
onMounted(() => {
  window.addEventListener('resize', fitInViewport)
  fitInViewport()
  transcriptObserver = new ResizeObserver(() => {
    const height = transcript.value?.clientHeight
    if (height) scrollRoom.value = height
    // Follow actual panel dimensions: expanding, errors and the follow button
    // can grow the window without a browser resize or drag event.
    fitInViewport()
    scroll()
  })
  if (transcript.value) transcriptObserver.observe(transcript.value)
  if (panel.value) transcriptObserver.observe(panel.value)
})
onBeforeUnmount(() => { transcriptObserver?.disconnect(); window.removeEventListener('resize', fitInViewport); cancel(); emit('activity', false) })

</script>
<style scoped>
.doubao-overlay { position: fixed; z-index: 1800; display: flex; flex-direction: column; box-sizing: border-box; max-width: 100vw; max-height: 100dvh; color: #303136; border: 1px solid #ffffffa6; border-radius: 12px; background: rgb(248 248 250 / var(--panel-opacity)); box-shadow: 0 12px 45px #20212826; backdrop-filter: blur(8px); overflow: hidden; user-select: none; -webkit-user-select: none; cursor: grab; }
.doubao-overlay:active { cursor: grabbing; }
header { flex-shrink: 0; display: flex; align-items: center; gap: 6px; padding: 6px 10px; min-height: 28px; white-space: nowrap; overflow-x: auto; }
header strong { font-size: 13px; flex-shrink: 0; } .status { width: 6px; height: 6px; border-radius: 50%; background: #98999e; flex-shrink: 0; } .status.connected { background: #686970; } .status.connecting { background: #c19b46; }
header button { border: 0; border-radius: 5px; background: transparent; cursor: pointer; color: #55565d; padding: 4px; font-size: 12px; flex-shrink: 0; } header button:hover { background: #70717822; } header button:disabled { opacity: .4; cursor: not-allowed; } header .stop { color: #ad3838; }
.panel-body { display: flex; flex-direction: column; min-height: 0; padding: 0 8px; } .sized .panel-body { flex: 1; } .opacity { margin-left: auto; display: flex; align-items: center; gap: 3px; font-size: 11px; cursor: default; } input[type=range] { width: 52px; margin: 0; accent-color: #696a72; cursor: pointer; }
.error { color: #ad3838; font-size: 12px; margin: 4px 2px; } .hint { font-size: 12px; margin: 4px 2px; }
.follow-latest { display: block; margin: 4px auto; border: 1px solid #70717855; border-radius: 12px; padding: 3px 10px; background: #ffffff90; color: #55565d; cursor: pointer; font-size: 12px; }
.transcript { overflow-anchor: none; height: 280px; max-height: 45vh; min-height: 0; overflow: auto; } .sized .transcript { flex: 1; height: auto; max-height: none; }
article { margin-bottom: 6px; padding: 6px 8px; border-radius: 8px; background: rgb(255 255 255 / 42%); } article.user { background: rgb(95 96 105 / 16%); } article p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; font-size: 15px; }
.scroll-space { flex-shrink: 0; pointer-events: none; }
.content-end { height: 0; }
.doubao-markdown { overflow-wrap: anywhere; font-size: 15px; line-height: 1.7; }
.doubao-markdown :deep(p) { margin: 0 0 8px; white-space: normal; }
.doubao-markdown :deep(h1), .doubao-markdown :deep(h2), .doubao-markdown :deep(h3), .doubao-markdown :deep(h4), .doubao-markdown :deep(h5), .doubao-markdown :deep(h6) { margin: 12px 0 6px; font-weight: 700; line-height: 1.4; }
.doubao-markdown :deep(h1) { font-size: 24px; }
.doubao-markdown :deep(h2) { font-size: 21px; }
.doubao-markdown :deep(h3) { font-size: 18px; }
.doubao-markdown :deep(h4), .doubao-markdown :deep(h5), .doubao-markdown :deep(h6) { font-size: 16px; }
.doubao-markdown :deep(ul), .doubao-markdown :deep(ol) { margin: 6px 0; padding-left: 24px; }
.doubao-markdown :deep(ul) { list-style: disc; }
.doubao-markdown :deep(ol) { list-style: decimal; }
.doubao-markdown :deep(pre) { overflow: auto; white-space: pre; padding: 10px; margin: 8px 0; border-radius: 6px; background: #30313612; }
.doubao-markdown :deep(code) { font-family: monospace; font-size: .9em; }
.doubao-markdown :deep(blockquote) { border-left: 3px solid #98999e; padding-left: 10px; margin: 8px 0; color: #60616a; }
.doubao-markdown :deep(a) { color: #245abb; text-decoration: underline; }
.doubao-markdown :deep(hr) { border: 0; border-top: 1px solid #98999e66; margin: 12px 0; }
.doubao-markdown :deep(table) { border-collapse: collapse; display: block; overflow: auto; }
.doubao-markdown :deep(th), .doubao-markdown :deep(td) { border: 1px solid #98999e66; padding: 4px 8px; }
.resize-handle { position: absolute; z-index: 2; width: 14px; height: 14px; padding: 0; border: 0; background: transparent; touch-action: none; }
.resize-handle::after { content: ''; position: absolute; inset: 3px; border-color: #77788080; border-style: solid; border-width: 0; }
.resize-handle:focus-visible { outline: 2px solid #696a72; outline-offset: -2px; }
.nw { top: 0; left: 0; cursor: nwse-resize; } .nw::after { border-top-width: 1px; border-left-width: 1px; }
.ne { top: 0; right: 0; cursor: nesw-resize; } .ne::after { border-top-width: 1px; border-right-width: 1px; }
.sw { bottom: 0; left: 0; cursor: nesw-resize; } .sw::after { border-bottom-width: 1px; border-left-width: 1px; }
.se { bottom: 0; right: 0; cursor: nwse-resize; } .se::after { border-bottom-width: 1px; border-right-width: 1px; }
</style>
