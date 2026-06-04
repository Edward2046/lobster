import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Message, ThinkingStep } from '../App'

const STEP_ICONS: Record<string, string> = {
  plan: '📋',
  thought: '💭',
  code: '💻',
  observation: '🔍',
}

function truncate(text: string, limit: number) {
  return text.length > limit ? text.slice(0, limit) + '…' : text
}

/** 打字机效果：active=true 时逐字符展开，否则直接展示全文 */
function useTypewriter(fullText: string, active: boolean) {
  const [displayed, setDisplayed] = useState(active ? '' : fullText)
  const [done, setDone] = useState(!active)
  const startedRef = useRef(false)

  useEffect(() => {
    // 已经动画过，或者不需要动画，直接展示全文
    if (!active || startedRef.current) {
      setDisplayed(fullText)
      setDone(true)
      return
    }
    startedRef.current = true
    setDisplayed('')
    setDone(false)

    let pos = 0
    const CHUNK = 6 // 每帧展示字符数，约 60fps × 6 = 360 字/秒
    const timer = setInterval(() => {
      pos = Math.min(pos + CHUNK, fullText.length)
      setDisplayed(fullText.slice(0, pos))
      if (pos >= fullText.length) {
        clearInterval(timer)
        setDone(true)
      }
    }, 16)

    return () => clearInterval(timer)
  }, [fullText, active])

  return { displayed, done }
}

interface StepsProps {
  steps: ThinkingStep[]
  open: boolean
  onToggle: () => void
  isLoading: boolean
}

function ThinkingSteps({ steps, open, onToggle, isLoading }: StepsProps) {
  return (
    <div className="thinking-section">
      <button className="thinking-toggle" onClick={onToggle}>
        <span className={`toggle-icon ${open ? 'open' : ''}`}>▶</span>
        {isLoading
          ? `思考过程${steps.length > 0 ? ` · ${steps.length} 步` : ''}`
          : `思考过程 · ${steps.length} 步`}
      </button>
      {open && steps.length > 0 && (
        <div className="thinking-steps">
          {steps.map((step, i) => (
            <div key={i} className={`thinking-step step-${step.kind}`}>
              <span className="step-icon">{STEP_ICONS[step.kind] ?? '•'}</span>
              <span className="step-text">{truncate(step.text, 200)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

interface Props {
  message: Message
}

export default function MessageBubble({ message }: Props) {
  const { displayed, done } = useTypewriter(message.text, message.streaming === true)
  const [stepsOpen, setStepsOpen] = useState(true)

  // 打字机跑完后，延迟折叠思考步骤
  useEffect(() => {
    if (message.role === 'agent' && done) {
      const t = setTimeout(() => setStepsOpen(false), 1200)
      return () => clearTimeout(t)
    }
  }, [message.role, done])

  if (message.role === 'user') {
    return <div className="message user">{message.text}</div>
  }

  if (message.role === 'error') {
    return <div className="message error">{message.text}</div>
  }

  const steps = message.steps ?? []
  const isLoading = message.role === 'loading'

  return (
    <div className={`message ${isLoading ? 'loading' : 'agent'}`}>
      {/* 思考中动画点 */}
      {isLoading && (
        <div className="thinking-header">
          <div className="thinking-dots">
            <span /><span /><span />
          </div>
          <span className="thinking-label">思考中</span>
        </div>
      )}

      {/* 思考步骤折叠区 */}
      {(steps.length > 0 || isLoading) && (
        <ThinkingSteps
          steps={steps}
          open={stepsOpen}
          onToggle={() => setStepsOpen((o) => !o)}
          isLoading={isLoading}
        />
      )}

      {/* 最终答案（带打字机效果） */}
      {!isLoading && (
        <>
          {steps.length > 0 && <hr className="thinking-divider" />}
          <div className={`markdown-body${!done ? ' streaming' : ''}`}>
            <ReactMarkdown>{displayed}</ReactMarkdown>
          </div>
        </>
      )}
    </div>
  )
}
