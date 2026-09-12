import type { CSSProperties, ReactNode } from 'react'
import { useInView } from '../hooks/useInView'

interface Props {
  children: ReactNode
  delay?: number
  className?: string
  as?: 'div' | 'section' | 'li' | 'article'
}

/** Scroll-reveal wrapper: fades/slides children in the first time they
 * enter the viewport. Pure CSS transition, no library. */
export default function Reveal({ children, delay = 0, className = '', as = 'div' }: Props) {
  const { ref, inView } = useInView<HTMLDivElement>()
  const Tag = as as 'div'
  const style: CSSProperties = delay ? { transitionDelay: `${delay}ms` } : {}
  return (
    <Tag ref={ref} className={`reveal ${inView ? 'reveal-in' : ''} ${className}`} style={style}>
      {children}
    </Tag>
  )
}
