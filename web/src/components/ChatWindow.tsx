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
          <div className="icon">🦞</div>
          <p>问我任何问题，比如天气、财经资讯、财报日历……</p>
        </div>
      )}
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
