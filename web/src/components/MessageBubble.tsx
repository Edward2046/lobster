import type { Message } from '../App'

interface Props {
  message: Message
}

export default function MessageBubble({ message }: Props) {
  return (
    <div className={`message ${message.role}`}>
      {message.text}
    </div>
  )
}
