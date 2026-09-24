<template><component :is="icons[name] || icons['info-circle']" :size="size" :stroke-width="1.7" aria-hidden="true" class="app-icon" /></template>
<script setup>
import { Check, CheckCheck, ChevronLeft, ChevronRight, Columns2, Copy, Pencil, Maximize2, Info, RefreshCw, X, Trash2, MessagesSquare, CircleCheck, Settings, Database, KeyRound, Link, List, Plus, CirclePlus, Save, Mic, Square } from 'lucide-vue-next'
defineProps({ name: String, size: { type: [String, Number], default: '1em' } })
const icons = { check: Check, 'check-double': CheckCheck, 'chevron-left': ChevronLeft, 'chevron-right': ChevronRight, columns: Columns2, copy: Copy, edit: Pencil, expand: Maximize2, 'info-circle': Info, 'sync-alt': RefreshCw, times: X, trash: Trash2, comments: MessagesSquare, 'check-circle': CircleCheck, cog: Settings, database: Database, key: KeyRound, link: Link, list: List, plus: Plus, 'plus-circle': CirclePlus, save: Save, microphone: Mic, stop: Square }
</script>
<style scoped>.app-icon { display: inline-block; vertical-align: -.13em; flex-shrink: 0; }</style>
