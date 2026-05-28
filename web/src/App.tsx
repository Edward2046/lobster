import { useState } from 'react'
import ChatWindow from './components/ChatWindow'
import InputBar from './components/InputBar'

export interface Message {
  id: number
  role: 'user' | 'agent' | 'error' | 'loading'
  text: string
}

let nextId = 1

export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)

  async function handleSend(question: string) {
    const userMsg: Message = { id: nextId++, role: 'user', text: question }
    const loadingMsg: Message = { id: nextId++, role: 'loading', text: '思考中…' }

    setMessages((prev) => [...prev, userMsg, loadingMsg])
    setLoading(true)

    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      const data = await res.json()
      const reply: Message = res.ok
        ? { id: nextId++, role: 'agent', text: data.answer }
        : { id: nextId++, role: 'error', text: `错误：${data.error || res.statusText}` }

      setMessages((prev) => [...prev.filter((m) => m.role !== 'loading'), reply])
    } catch {
      setMessages((prev) => [
        ...prev.filter((m) => m.role !== 'loading'),
        { id: nextId++, role: 'error', text: '无法连接到 Agent 服务，请确认 main.py 已启动。' },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <span className="logo">🦞</span>
        <h1>Lobster Agent</h1>
      </header>
      <ChatWindow messages={messages} />
      <InputBar onSend={handleSend} disabled={loading} />
    </div>
  )
}
