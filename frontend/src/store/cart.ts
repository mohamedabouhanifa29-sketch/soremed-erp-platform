// Panier client persistant dans le navigateur local.
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Product } from '../types'
export interface CartItem { product:Product; quantity:number }
interface CartState { items:CartItem[]; add:(product:Product)=>void; quantity:(id:number,value:number)=>void; remove:(id:number)=>void; clear:()=>void }
export const useCart=create<CartState>()(persist((set)=>({items:[],add:product=>set(state=>{const found=state.items.find(x=>x.product.id===product.id);return {items:found?state.items.map(x=>x.product.id===product.id?{...x,quantity:Math.min(x.quantity+1,product.stock)}:x):[...state.items,{product,quantity:1}]}}),quantity:(id,value)=>set(state=>({items:state.items.map(x=>x.product.id===id?{...x,quantity:Math.max(1,Math.min(value,x.product.stock))}:x)})),remove:id=>set(state=>({items:state.items.filter(x=>x.product.id!==id)})),clear:()=>set({items:[]})}),{name:'soremed-client-cart'}))
