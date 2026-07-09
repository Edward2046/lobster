import { useEffect, useRef } from 'react'
import type { Message } from '../App'
import MessageBubble from './MessageBubble'

interface Props {
  messages: Message[]
}

export default function ChatWindow({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="chat-window">
      {messages.length === 0 && (
        <div className="empty-hint">
          <h2 className="greeting">你好，我能帮你做点什么？</h2>
          <p>问我天气、财经资讯、财报日历，或让我帮你管理定时任务……</p>
        </div>
      )}
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
