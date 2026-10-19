<template>
  <el-dialog :model-value="true" title="使用说明书" width="min(880px, 94vw)" top="5vh"
    class="user-guide-dialog" append-to-body destroy-on-close @close="$emit('close')">
    <div class="guide" @keydown.stop @keydown.esc="$emit('close')">
      <p class="guide-intro">按功能查阅，也可以搜索「右键」「快捷键」「截图」等关键词。</p>
      <input v-model="query" class="guide-search" placeholder="搜索功能或操作…" aria-label="搜索说明书" />
      <div class="guide-layout">
        <nav aria-label="说明书目录">
          <button v-for="section in sections" :key="section.title" @click="jump(section.title)">{{ section.title }}</button>
        </nav>
        <div ref="content" class="guide-content" tabindex="0" aria-label="功能说明">
          <section v-for="section in sections" :key="section.title" :data-section="section.title">
            <h3>{{ section.title }}</h3>
            <ul><li v-for="[label, description] in section.items" :key="label"><strong>{{ label }}</strong><p>{{ description }}</p></li></ul>
          </section>
          <p v-if="!sections.length" role="status">没有找到相关说明，试试更短的关键词。</p>
        </div>
      </div>
    </div>
  </el-dialog>
</template>
<script setup>
import { computed, ref } from 'vue'
import { userGuide } from '../content/userGuide'
defineEmits(['close'])
const query = ref(''), content = ref(null)
const sections = computed(() => {
  const term = query.value.trim().toLowerCase()
  return userGuide.map(section => ({ ...section, items: section.title.toLowerCase().includes(term)
    ? section.items : section.items.filter(item => item.join(' ').toLowerCase().includes(term)) })).filter(section => section.items.length)
})
function jump(title) {
  const section = [...content.value.querySelectorAll('section')].find(node => node.dataset.section === title)
  if (section) content.value.scrollTo({ top: section.offsetTop, behavior: 'smooth' })
}
</script>
<style scoped>
.guide-intro { margin: 0 0 14px; color: #64748b; font-size: 13px; }
.guide-search { width: 100%; padding: 11px 14px; border: 1px solid #dbe3ed; border-radius: 9px; color: #243247; background: #f8fafc; }
.guide-search:focus-visible, nav button:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.guide-layout { display: grid; grid-template-columns: 174px minmax(0, 1fr); gap: 24px; margin-top: 20px; }
nav { display: flex; flex-direction: column; gap: 3px; max-height: 60vh; overflow: auto; }
nav button { text-align: left; padding: 9px 10px; border-radius: 7px; font-size: 12px; color: #64748b; }
nav button:hover { color: #2563eb; background: #eff6ff; }
.guide-content { position: relative; max-height: 60vh; overflow: auto; overscroll-behavior: contain; padding-right: 12px; }
section + section { border-top: 1px solid #edf0f4; padding-top: 20px; margin-top: 24px; }
h3 { margin: 0 0 16px; font-size: 16px; color: #172b46; font-weight: 650; }
ul { padding-left: 18px; margin: 0; list-style: disc; }
li { padding-left: 3px; margin-bottom: 15px; font-size: 13px; line-height: 1.75; color: #526176; }
strong { font-weight: 600; color: #27384e; }
li p { margin: 3px 0 0; }
@media (max-width: 600px) {
  .guide-layout { grid-template-columns: minmax(0, 1fr); gap: 14px; }
  nav { flex-direction: row; max-height: none; white-space: nowrap; }
  nav button { flex-shrink: 0; }
  .guide-content { max-height: 52vh; }
}
</style>
