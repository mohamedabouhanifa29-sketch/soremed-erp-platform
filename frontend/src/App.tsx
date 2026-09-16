// Routage séparé entre le back-office et le portail Client.
import { useEffect, useState, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { api } from './lib/api'
import { useAuth } from './store/auth'
import type { Role, User } from './types'
import { Layout } from './components/Layout'
import { ClientLayout } from './components/ClientLayout'
import { Loading } from './components/UI'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Resources from './pages/Resources'
import { AuditLog, Orders, Purchases, Reports, Settings, Suppliers } from './pages/Operations'
import Stock from './pages/Stock'
import { ClientCart, ClientOrders, ClientProfile } from './pages/ClientPortal'
import ClientProducts from './pages/ClientCatalog'
import ClientHome from './pages/ClientHome'
import ClientFavorites from './pages/ClientFavorites'
import PurchaseNew from './pages/PurchaseNew'
import OrderDetail from './pages/OrderDetail'
import Receipts from './pages/Receipts'
import Inventory from './pages/Inventory'
import Categories from './pages/Categories'
const titles:Record<string,string>={'/dashboard':'Tableau de bord','/users':'Utilisateurs','/clients':'Clients','/suppliers':'Fournisseurs','/products':'Produits','/categories':'Catégories','/purchases':'Achats fournisseurs','/purchases/new':'Nouvel achat fournisseur','/receipts':'Réceptions fournisseurs','/customer-orders':'Commandes clients','/stock/inventory':'Inventaire','/stock/movements':'Mouvements de stock','/stock/alerts':'Alertes stock','/reports':'Rapports','/audit':'Journal','/settings':'Paramètres'}
function Protected({children}:{children:ReactNode}){const token=localStorage.getItem('soremed_token'),user=useAuth(s=>s.user),setUser=useAuth(s=>s.setUser),[loading,setLoading]=useState(!!token&&!user);useEffect(()=>{if(token&&!user)api.get<User>('/auth/me').then(r=>setUser(r.data)).catch(()=>localStorage.removeItem('soremed_token')).finally(()=>setLoading(false))},[token,user,setUser]);if(!token)return <Navigate to="/login" replace/>;if(loading||!user)return <Loading/>;return <>{children}</>}
function Allowed({roles,children}:{roles:Role[];children:ReactNode}){const role=useAuth(s=>s.user?.role);if(role==='client'&&!roles.includes('client'))return <Navigate to="/client/produits" replace/>;return role&&roles.includes(role)?<>{children}</>:<Navigate to="/dashboard" replace/>}
function BackOffice(){const location=useLocation();return <Allowed roles={['admin','achats']}><Layout title={titles[location.pathname]||'SOREMED'}><Routes><Route path="/" element={<Navigate to="/dashboard" replace/>}/><Route path="/dashboard" element={<Dashboard/>}/><Route path="/users" element={<Allowed roles={['admin']}><Resources kind="users"/></Allowed>}/><Route path="/clients" element={<Allowed roles={['admin']}><Resources kind="clients"/></Allowed>}/><Route path="/suppliers" element={<Suppliers/>}/><Route path="/products" element={<Allowed roles={['admin']}><Resources kind="products"/></Allowed>}/><Route path="/categories" element={<Allowed roles={['admin']}><Categories/></Allowed>}/><Route path="/purchases" element={<Purchases/>}/><Route path="/purchases/new" element={<PurchaseNew/>}/><Route path="/receipts" element={<Receipts/>}/><Route path="/customer-orders" element={<Orders/>}/><Route path="/customer-orders/:id" element={<OrderDetail/>}/><Route path="/achats/commandes" element={<Navigate to="/customer-orders" replace/>}/><Route path="/stock" element={<Navigate to="/stock/inventory" replace/>}/><Route path="/stock/inventory" element={<Inventory/>}/><Route path="/stock/movements" element={<Stock/>}/><Route path="/stock/alerts" element={<Inventory/>}/><Route path="/reports" element={<Reports/>}/><Route path="/audit" element={<Allowed roles={['admin']}><AuditLog/></Allowed>}/><Route path="/settings" element={<Allowed roles={['admin']}><Settings/></Allowed>}/><Route path="*" element={<Navigate to="/dashboard" replace/>}/></Routes></Layout></Allowed>}
function ClientSpace(){return <Allowed roles={['client']}><ClientLayout><Routes><Route path="home" element={<ClientHome/>}/><Route path="products" element={<ClientProducts/>}/><Route path="products/:id" element={<ClientProducts/>}/><Route path="favorites" element={<ClientFavorites/>}/><Route path="cart" element={<ClientCart/>}/><Route path="orders" element={<ClientOrders/>}/><Route path="orders/:id" element={<ClientOrders/>}/><Route path="profile" element={<ClientProfile/>}/><Route path="produits" element={<Navigate to="../products" replace/>}/><Route path="panier" element={<Navigate to="../cart" replace/>}/><Route path="commandes" element={<Navigate to="../orders" replace/>}/><Route path="profil" element={<Navigate to="../profile" replace/>}/><Route path="*" element={<Navigate to="home" replace/>}/></Routes></ClientLayout></Allowed>}
export default function App(){return <Routes><Route path="/login" element={<Login/>}/><Route path="/register" element={<Register/>}/><Route path="/client/*" element={<Protected><ClientSpace/></Protected>}/><Route path="/*" element={<Protected><BackOffice/></Protected>}/></Routes>}
