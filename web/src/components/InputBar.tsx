import { useRef, useState } from 'react'

interface Props {
  onSend: (text: string) => void
  disabled: boolean
}

export default function InputBar({ onSend, disabled }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function handleSend() {
    const q = value.trim()
    if (!q || disabled) return
    setValue('')
    resetHeight()
    onSend(q)
  }

  function resetHeight() {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setValue(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="input-bar">
      <textarea
        ref={textareaRef}
        rows={1}
        placeholder="输入问题，按 Enter 发送，Shift+Enter 换行"
        value={value}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      <button onClick={handleSend} disabled={disabled || !value.trim()}>
        发送
      </button>
    </div>
  )
}
