import axios from 'axios'

export const apiTargetLabel =
  'http://10.7.3.50:8181'

export const http = axios.create({
  baseURL: '',
  timeout: 30000,
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') {
      error.message = detail
    }
    return Promise.reject(error)
  },
)


