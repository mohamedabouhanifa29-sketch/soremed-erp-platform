/** Portal modal volontairement simple, sans animation ni dépendance externe. */
import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type SimpleModalProps={open:boolean;title:string;onClose:()=>void;children:ReactNode}

export function SimpleModal({open,title,onClose,children}:SimpleModalProps){
  useEffect(()=>{
    if(!open)return
    const previousOverflow=document.body.style.overflow
    document.body.style.overflow='hidden'
    const handleKeyDown=(event:KeyboardEvent)=>{if(event.key==='Escape')onClose()}
    window.addEventListener('keydown',handleKeyDown)
    return()=>{document.body.style.overflow=previousOverflow;window.removeEventListener('keydown',handleKeyDown)}
  },[open,onClose])
  if(!open)return null
  return createPortal(<div className="simple-modal-root"><button type="button" className="simple-modal-overlay" onClick={onClose} aria-label="Fermer la fenêtre"/><section className="simple-modal-panel" role="dialog" aria-modal="true" aria-labelledby="simple-modal-title"><header className="simple-modal-header"><h2 id="simple-modal-title">{title}</h2><button type="button" className="simple-modal-close" onClick={onClose} aria-label="Fermer">×</button></header><div className="simple-modal-body">{children}</div></section></div>,document.body)
}
