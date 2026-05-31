import type { Message } from '../App'
import ReactMarkdown from 'react-markdown'

interface Props {
  message: Message
}

export default function MessageBubble({ message }: Props) {
  return (
    <div className={`message ${message.role}`}>
      {message.role === 'agent' ? (
        <div className="markdown-body">
          <ReactMarkdown>{message.text}</ReactMarkdown>
        </div>
      ) : (
        message.text
      )}
    </div>
  )
}
