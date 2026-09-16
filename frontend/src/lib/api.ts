// Client HTTP central : base locale, JWT et gestion uniforme des sessions expirées.
import axios from 'axios'
export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api/v1', timeout: 15000 })
api.interceptors.request.use(config => { const token = localStorage.getItem('soremed_token'); if (token) config.headers.Authorization = `Bearer ${token}`; return config })
api.interceptors.response.use(response => response, error => { if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) { localStorage.removeItem('soremed_token'); window.location.assign('/login') } return Promise.reject(error) })

