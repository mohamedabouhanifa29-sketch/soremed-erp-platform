// Isole le chatbot afin qu'une erreur ne puisse jamais masquer la page métier.
import { Component, type ErrorInfo, type ReactNode } from 'react'
interface Props {children:ReactNode}
interface State {failed:boolean}
export class ChatErrorBoundary extends Component<Props,State>{state:State={failed:false};static getDerivedStateFromError():State{return {failed:true}}componentDidCatch(error:Error,info:ErrorInfo){console.error('Assistant SOREMED indisponible',error,info)}render(){return this.state.failed?<div className="chat-boundary-error" role="status">Le chatbot est temporairement indisponible.</div>:this.props.children}}
