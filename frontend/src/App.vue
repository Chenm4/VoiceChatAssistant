<template>
  <div id="app" class="min-h-screen bg-gray-50">
    <ChatView v-if="currentView === 'chat'" @open-prompt-lab="currentView = 'prompt-lab'" />
    <PromptLabView v-else @back="currentView = 'chat'" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ChatView from './views/ChatView.vue'
import PromptLabView from './views/PromptLabView.vue'

const currentView = ref('chat')
</script>
