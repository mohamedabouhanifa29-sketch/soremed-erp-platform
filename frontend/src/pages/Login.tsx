// Connexion JWT avec une présentation dédiée, entièrement construite avec les assets locaux et CSS.
import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { AlertCircle, Eye, EyeOff, LoaderCircle } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../store/auth'
import type { User } from '../types'

function loginMessage(error:any):string {
  const detail=typeof error.response?.data?.detail==='string'?error.response.data.detail:''
  const normalized=detail.toLowerCase()
  if(normalized.includes('attente'))return 'Votre compte est en attente d’approbation par un administrateur.'
  if(normalized.includes('refus'))return 'Votre compte a été refusé.'
  if(normalized.includes('désactiv'))return 'Votre compte est désactivé.'
  if(normalized.includes('incorrect'))return 'Email ou mot de passe incorrect.'
  return 'Le serveur local est indisponible. Veuillez réessayer.'
}

export default function Login(){
  const navigate=useNavigate(),setUser=useAuth(s=>s.setUser)
  const [email,setEmail]=useState(()=>localStorage.getItem('soremed_remembered_email')||'')
  const [password,setPassword]=useState(''),[showPassword,setShowPassword]=useState(false),[remember,setRemember]=useState(Boolean(localStorage.getItem('soremed_remembered_email')))
  const [error,setError]=useState(''),[info,setInfo]=useState(''),[busy,setBusy]=useState(false)
  useEffect(()=>{
    document.body.classList.add('login-no-scroll')
    return ()=>document.body.classList.remove('login-no-scroll')
  },[])
  if(localStorage.getItem('soremed_token'))return <Navigate to="/" replace/>
  const submit=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError('');setInfo('');try{const {data}=await api.post('/auth/login',{email,password});localStorage.setItem('soremed_token',data.access_token);remember?localStorage.setItem('soremed_remembered_email',email):localStorage.removeItem('soremed_remembered_email');const current=await api.get<User>('/auth/me');setUser(current.data);navigate(current.data.role==='client'?'/client/home':'/dashboard',{replace:true})}catch(e:any){localStorage.removeItem('soremed_token');setError(loginMessage(e))}finally{setBusy(false)}}
  return <main className="login-page">
    <div className="login-shape login-shape-one"/><div className="login-shape login-shape-two"/><div className="login-shape login-shape-three"/><div className="login-shape login-shape-four"/>
    <header className="login-header"><Brand compact/><span className="login-header-caption">Plateforme de gestion</span></header>
    <section className="login-stage" aria-label="Connexion à la plateforme">
      <div className="login-card">
        <div className="login-card-brand"><Brand inverse/></div>
        <form className="login-form" onSubmit={submit}>
          <div className="login-form-heading"><p className="login-kicker">Accès sécurisé</p><h1>Connexion</h1><p>Identifiez-vous pour accéder à votre espace.</p></div>
          {error&&<div className="login-alert login-alert-error" role="alert"><AlertCircle size={18}/><span>{error}</span></div>}
          {info&&<div className="login-alert login-alert-info" role="status"><AlertCircle size={18}/><span>{info}</span></div>}
          <label className="login-field"><span>Adresse email</span><input type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="nom@exemple.com" required autoFocus/></label>
          <label className="login-field"><span>Mot de passe</span><div className="login-password"><input type={showPassword?'text':'password'} autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Votre mot de passe" required minLength={8}/><button type="button" onClick={()=>setShowPassword(value=>!value)} aria-label={showPassword?'Masquer le mot de passe':'Afficher le mot de passe'}>{showPassword?<EyeOff size={20}/>:<Eye size={20}/>}</button></div></label>
          <div className="login-options"><label className="login-remember"><input type="checkbox" checked={remember} onChange={e=>setRemember(e.target.checked)}/><span>Se souvenir de moi</span></label><button type="button" className="login-forgot" onClick={()=>{setError('');setInfo('Contactez votre administrateur local pour réinitialiser votre mot de passe.')}}>Mot de passe oublié ?</button></div>
          <button className="login-submit" disabled={busy}>{busy?<><LoaderCircle className="animate-spin" size={19}/>Connexion…</>:'Connexion'}</button>
          <Link className="login-register" to="/register">Créer un compte client</Link>
        </form>
      </div>
    </section>
  </main>
}

function Brand({compact=false,inverse=false}:{compact?:boolean;inverse?:boolean}){return <div className={`login-brand ${compact?'login-brand-compact':''} ${inverse?'login-brand-inverse':''}`} aria-label="SOREMED"><span className="login-brand-mark">S</span><span><strong>SOREMED</strong><small>Plateforme locale</small></span></div>}
