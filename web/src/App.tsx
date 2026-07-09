import { useState } from 'react'
import ChatWindow from './components/ChatWindow'
import InputBar from './components/InputBar'

export interface ThinkingStep {
  kind: string
  text: string
  step: number
}

export interface Message {
  id: number
  role: 'user' | 'agent' | 'error' | 'loading'
  text: string
  steps?: ThinkingStep[]
  streaming?: boolean
}

let nextId = 1

const THINKING_EVENTS = new Set(['plan', 'thought', 'code', 'observation', 'step_error'])

function parseSSEChunk(
  buffer: string,
  chunk: string,
  onEvent: (event: string, payload: Record<string, unknown>) => void,
): string {
  buffer += chunk
  const parts = buffer.split('\n\n')
  const remaining = parts.pop() ?? ''
  for (const part of parts) {
    if (!part.trim()) continue
    let eventName = ''
    let dataStr = ''
    for (const line of part.split('\n')) {
      if (line.startsWith('event: ')) eventName = line.slice(7).trim()
      else if (line.startsWith('data: ')) dataStr = line.slice(6).trim()
    }
    if (eventName && dataStr) {
      try {
        onEvent(eventName, JSON.parse(dataStr))
      } catch {
        // ignore malformed data
      }
    }
  }
  return remaining
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)

  async function handleSend(question: string) {
    const userMsg: Message = { id: nextId++, role: 'user', text: question }
    const agentMsgId = nextId++
    const loadingMsg: Message = { id: agentMsgId, role: 'loading', text: '', steps: [] }

    setMessages((prev) => [...prev, userMsg, loadingMsg])
    setLoading(true)

    // 用闭包变量收集步骤，避免频繁 spread
    const pendingSteps: ThinkingStep[] = []

    try {
      const res = await fetch('/api/ask/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })

      if (!res.ok || !res.body) {
        const data = await res.json().catch(() => ({}))
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== agentMsgId),
          { id: nextId++, role: 'error', text: `错误：${(data as { error?: string }).error || res.statusText}` },
        ])
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const handleEvent = (event: string, payload: Record<string, unknown>) => {
        if (event === 'final') {
          const text = String(payload.text ?? '')
          setMessages((prev) =>
            prev.map((m) =>
              m.id === agentMsgId
                ? { ...m, role: 'agent', text, streaming: true, steps: [...pendingSteps] }
                : m,
            ),
          )
        } else if (THINKING_EVENTS.has(event)) {
          pendingSteps.push({
            kind: event,
            text: String(payload.text ?? ''),
            step: Number(payload.step ?? 0),
          })
          setMessages((prev) =>
            prev.map((m) =>
              m.id === agentMsgId && m.role === 'loading'
                ? { ...m, steps: [...pendingSteps] }
                : m,
            ),
          )
        } else if (event === 'error') {
          setMessages((prev) => [
            ...prev.filter((m) => m.id !== agentMsgId),
            { id: nextId++, role: 'error', text: `错误：${payload.text ?? '未知错误'}` },
          ])
        } else if (event === 'done') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === agentMsgId && m.role === 'loading'
                ? { ...m, role: 'error', text: '未收到回复' }
                : m,
            ),
          )
        }
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer = parseSSEChunk(buffer, decoder.decode(value, { stream: true }), handleEvent)
      }
    } catch {
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== agentMsgId),
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
        <div className="titles">
          <h1>Lobster Agent</h1>
          <span className="subtitle">你的本地智能助手 · 天气 · 财经 · 运维诊断</span>
        </div>
      </header>
      <ChatWindow messages={messages} />
      <InputBar onSend={handleSend} disabled={loading} />
    </div>
  )
}
