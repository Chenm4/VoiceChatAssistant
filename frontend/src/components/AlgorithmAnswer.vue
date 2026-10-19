<template>
  <template v-for="(part, index) in parts" :key="index">
    <div v-if="part.type === 'markdown'" class="markdown-body" v-html="renderMarkdown(part.text)"></div>
    <section v-else class="algorithm-card" @dblclick.stop>
      <header><strong>{{ part.language }} · 算法代码</strong><button type="button" @click="open(part)">放大查看</button></header>
      <pre @dblclick="open(part)"><code>{{ part.code }}</code></pre>
    </section>
  </template>
  <Teleport to="body">
    <dialog v-if="selected" ref="dialog" class="code-preview" aria-label="放大查看算法代码" @close="selected = null" @dblclick.stop>
      <header>
        <strong>{{ selected.language }} · 算法代码</strong>
        <div class="preview-actions">
          <button type="button" aria-label="缩小代码" :disabled="zoom <= 50" @click="resize(-25)">−</button>
          <button type="button" aria-label="重置缩放" @click="zoom = 150">{{ zoom }}%</button>
          <button type="button" aria-label="放大代码" :disabled="zoom >= 400" @click="resize(25)">＋</button>
          <button type="button" @click="copy">{{ copied ? '已复制' : '复制代码' }}</button>
          <button type="button" @click="dialog.close()">关闭</button>
        </div>
      </header>
      <p>滚轮查看上下内容，Shift + 滚轮横向查看；Ctrl / ⌘ + 滚轮缩放。Esc 关闭。</p>
      <div class="code-viewport" tabindex="0" aria-label="可滚动代码" @wheel="onWheel">
        <pre :style="{ fontSize: `${16 * zoom / 100}px` }"><code>{{ selected.code }}</code></pre>
      </div>
    </dialog>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { algorithmAnswerParts } from '../utils/algorithmAnswer'
import { renderMarkdown } from '../utils/markdown'
import { copyText } from '../utils/clipboard'

const props = defineProps({ content: { type: String, default: '' } })
const parts = computed(() => algorithmAnswerParts(props.content))
const selected = ref(null)
const dialog = ref(null)
const zoom = ref(150)
const copied = ref(false)
async function open(part) {
  selected.value = part
  zoom.value = 150
  copied.value = false
  await nextTick()
  dialog.value?.showModal()
}
function resize(delta) { zoom.value = Math.max(50, Math.min(400, zoom.value + delta)) }
function onWheel(event) {
  if (!event.ctrlKey && !event.metaKey) return
  event.preventDefault()
  resize(event.deltaY < 0 ? 10 : event.deltaY > 0 ? -10 : 0)
}
async function copy() {
  try {
    await copyText(selected.value.code)
    copied.value = true
  } catch { ElMessage.error('复制失败，请手动选择代码复制') }
}
</script>

<style scoped>
.algorithm-card { margin: 12px 0; border: 1px solid #b8c9e4; border-radius: 14px; overflow: hidden; background: #f7faff; color: #172b4d; }
header { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 16px; border-bottom: 1px solid #dce5f2; flex-wrap: wrap; }
button { border: 1px solid #aac0e2; background: white; color: #194b9f; border-radius: 8px; padding: 8px 12px; min-height: 40px; cursor: pointer; }
button:disabled { opacity: .4; cursor: default; }
button:focus-visible, .code-viewport:focus-visible { outline: 3px solid #2868e8; outline-offset: -3px; }
pre { margin: 0; padding: 20px; white-space: pre; tab-size: 4; font: 18px/1.65 ui-monospace, SFMono-Regular, Consolas, monospace; }
code { font: inherit; }
.algorithm-card pre { max-height: 440px; overflow: auto; cursor: zoom-in; }
.code-preview { width: 94vw; height: 90vh; max-width: 1600px; max-height: 94vh; padding: 0; border: 1px solid #b8c9e4; border-radius: 16px; background: #f7faff; color: #172b4d; box-shadow: 0 24px 90px #0005; }
.code-preview[open] { display: flex; flex-direction: column; }
.code-preview::backdrop { background: rgb(15 23 42 / 65%); }
.preview-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.code-preview p { margin: 8px 16px; font-size: 13px; color: #536787; }
.code-viewport { flex: 1; min-height: 0; overflow: auto; overscroll-behavior: contain; }
.code-viewport pre { min-width: max-content; }
</style>
