import type { ReactNode } from 'react'

/**
 * A short, self-contained message attached to an action or a block.
 *
 * The tone decides the colour and nothing else; the text always says what
 * happened or what is about to happen. Only a failure is a live region, so a
 * persistent warning is not read out again every time the block re-renders.
 */
export default function Notice({
  tone,
  children,
}: {
  tone: 'info' | 'warning' | 'error' | 'success'
  children: ReactNode
}) {
  return (
    <div className={`notice notice--${tone}`} role={tone === 'error' ? 'alert' : undefined}>
      {children}
    </div>
  )
}
