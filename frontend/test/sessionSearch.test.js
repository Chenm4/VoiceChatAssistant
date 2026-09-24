import test from 'node:test'
import assert from 'node:assert/strict'
import { createSessionSearch, messageText, matchSnippet } from '../src/utils/sessionSearch.js'
const sessions = [{id:'a',title:'项目讨论',updated_at:1,message_count:2}, {id:'b',title:'其他话题',updated_at:1,message_count:1}]
test('matches bodies and parallel answers, not configuration or system prompts', async () => {
  const search = createSessionSearch(async id => ({messages: id === 'a' ? [
    {role:'user',content:'如何使用 Redis 缓存？'},
    {role:'assistant',content:'',parallel_models:[{content:'可以采用读写分离'}]},
    {role:'system',content:'秘密提示'}
  ] : [{role:'assistant',content:'只有普通回答'}],session_config:{system_prompt:'秘密提示'}}))
  assert.equal((await search(sessions,'redis')).matches[0].matchType,'content')
  assert.equal((await search(sessions,'读写分离')).matches[0].id,'a')
  assert.equal((await search(sessions,'秘密提示')).matches.length,0)
  assert.equal((await search(sessions,'项目')).matches[0].matchType,'title')
})
test('reuses text cache, invalidates updated conversations, keeps result order', async () => {
  let calls = 0
  const search = createSessionSearch(async () => {calls++; return {messages:[{role:'assistant',content:'关键词'}]}})
  assert.deepEqual((await search(sessions,'关键词')).matches.map(s=>s.id),['a','b'])
  await search(sessions,'关键')
  assert.equal(calls,2)
  await search([{...sessions[0],updated_at:2},sessions[1]],'关键')
  assert.equal(calls,3)
})
test('reports partial failures and retries them', async () => {
  let fail = true
  const search = createSessionSearch(async id => {if (id === 'b' && fail) throw Error('offline');return {messages:[{role:'user',content:'needle'}]}})
  assert.equal((await search(sessions,'needle')).failures,1)
  fail=false
  assert.equal((await search(sessions,'needle')).matches.length,2)
})
test('aborted searches stop fetching and do not poison cache', async () => {
  const controller = new AbortController()
  let calls=0
  const search=createSessionSearch(async()=>{calls++; controller.abort(); return {messages:[{role:'user',content:'needle'}]}})
  const result=await search(sessions,'needle',controller.signal)
  assert.equal(result.matches.length,0)
  assert.ok(calls<=2)
})
test('literal matching, trimmed queries and bounded snippets', async () => {
  assert.equal(matchSnippet('before <script> after','<script>'),'before <script> after')
  assert.equal(matchSnippet('中文消息','缺失'),null)
  assert.ok(matchSnippet('a'.repeat(500)+'needle'+'b'.repeat(500),'needle').length<100)
  assert.equal(messageText([{role:'user',content:'用户'},{role:'assistant',models:[{content:'回答'}]}]),'用户\n回答')
  const search=createSessionSearch(async()=>{throw Error('should not fetch')})
  assert.equal((await search(sessions,'   ')).failures,0)
})
