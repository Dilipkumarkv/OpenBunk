import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { ToastContext, type ToastFn } from './toastContext'

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null)
  const timer = useRef<number | null>(null)

  const show = useCallback<ToastFn>((msg) => {
    setMessage(msg)
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setMessage(null), 2800)
  }, [])

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    },
    [],
  )

  return (
    <ToastContext.Provider value={show}>
      {children}
      {message !== null && (
        <div className="toast" role="status">
          {message}
        </div>
      )}
    </ToastContext.Provider>
  )
}
