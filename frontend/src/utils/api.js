/**
 * API 请求工具
 */

import axios from 'axios'
import { apiUrl } from './apiUrl.js'
import { authHeaders, sessionExpired } from './auth.js'

const api = axios.create({
  baseURL: apiUrl('/api'),
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    Object.assign(config.headers, authHeaders())
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    if (error.response?.status === 401) sessionExpired()
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export default api
