// Cadre ERP commun : navigation métier groupée, barre supérieure et zone de travail.
import { useState, type ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { Activity, AlertTriangle, Boxes, ChevronDown, ClipboardCheck, Factory, FileBarChart, FolderTree, LayoutDashboard, LogOut, Menu, PackageCheck, PackagePlus, ReceiptText, Settings, ShoppingCart, Users, Warehouse, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useAuth } from '../store/auth'
import type { Role } from '../types'
import { ChatWidget } from './ChatWidget'

type LinkItem={to:string;label:string;icon:LucideIcon;roles:readonly Role[]}
type Group={label:string;links:LinkItem[]}
const groups:Group[]=[
  {label:'Pilotage',links:[{to:'/dashboard',label:'Tableau de bord',icon:LayoutDashboard,roles:['admin','achats']}]},
  {label:'Ventes',links:[{to:'/customer-orders',label:'Commandes clients',icon:ClipboardCheck,roles:['admin','achats']}]},
  {label:'Approvisionnement',links:[{to:'/suppliers',label:'Fournisseurs',icon:Factory,roles:['admin','achats']},{to:'/purchases',label:'Achats fournisseurs',icon:ShoppingCart,roles:['admin','achats']},{to:'/receipts',label:'Réceptions fournisseurs',icon:PackageCheck,roles:['admin','achats']}]},
  {label:'Catalogue',links:[{to:'/products',label:'Produits',icon:Boxes,roles:['admin']},{to:'/categories',label:'Catégories',icon:FolderTree,roles:['admin']}]},
  {label:'Stock',links:[{to:'/stock/inventory',label:'Inventaire',icon:Warehouse,roles:['admin','achats']},{to:'/stock/movements',label:'Mouvements',icon:PackagePlus,roles:['admin','achats']},{to:'/stock/alerts',label:'Alertes stock',icon:AlertTriangle,roles:['admin','achats']}]},
  {label:'Administration',links:[{to:'/reports',label:'Rapports',icon:FileBarChart,roles:['admin','achats']},{to:'/clients',label:'Clients',icon:ReceiptText,roles:['admin']},{to:'/users',label:'Utilisateurs',icon:Users,roles:['admin']},{to:'/audit',label:'Journal',icon:Activity,roles:['admin']},{to:'/settings',label:'Paramètres',icon:Settings,roles:['admin']}]},
]

export function Layout({children,title}:{children:ReactNode;title:string}){
 const [open,setOpen]=useState(false),user=useAuth(state=>state.user),logout=useAuth(state=>state.logout),navigate=useNavigate()
 const exit=()=>{logout();navigate('/login')}
 return <div className="app-shell">{open&&<button className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden" onClick={()=>setOpen(false)} aria-label="Fermer le menu"/>}<aside className={`app-sidebar ${open?'translate-x-0':'-translate-x-full'} lg:translate-x-0`}><div className="sidebar-brand"><div className="sidebar-brand-mark">S</div><div><strong>SOREMED</strong><span>ERP pharmaceutique</span></div><button className="lg:hidden" onClick={()=>setOpen(false)}><X/></button></div><nav className="sidebar-nav erp-sidebar-nav">{groups.map(group=>{const links=group.links.filter(link=>user&&link.roles.includes(user.role));return links.length?<section className="sidebar-group" key={group.label}><div className="sidebar-caption">{group.label}</div>{links.map(({to,label,icon:Icon})=><NavLink key={to} to={to} onClick={()=>setOpen(false)} className={({isActive})=>isActive?'active':''}><Icon size={18}/><span>{label}</span></NavLink>)}</section>:null})}</nav><div className="sidebar-footer"><span className="sidebar-status-dot"/><div><strong>Réseau sécurisé</strong><small>Application locale · ERP</small></div></div></aside><div className="app-workspace"><header className="app-topbar"><div className="topbar-title"><button className="mobile-menu lg:hidden" onClick={()=>setOpen(true)}><Menu size={20}/></button><div><span>Plateforme de gestion</span><h1>{title}</h1></div></div><div className="topbar-user"><div className="user-avatar">{user?.full_name?.charAt(0).toUpperCase()}</div><div className="user-meta"><strong>{user?.full_name}</strong><span>{user?.role==='achats'?'Service achats':user?.role}</span></div><ChevronDown size={15}/><button onClick={exit} className="logout-button" title="Déconnexion"><LogOut size={17}/><span>Déconnexion</span></button></div></header><main className="app-content">{children}</main></div><ChatWidget/></div>
}
