// État Zustand minimal de la session locale.
import { create } from 'zustand'
import type { User } from '../types'
interface AuthState { user:User|null; setUser:(user:User|null)=>void; logout:()=>void }
export const useAuth = create<AuthState>(set => ({ user:null, setUser:user=>set({user}), logout:()=>{localStorage.removeItem('soremed_token');set({user:null})} }))

