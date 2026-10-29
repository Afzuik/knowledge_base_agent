import { useEffect, useState } from 'react'
import { getHealth } from '../api'

export function useBackendHealth() {
  const [state, setState] = useState<'checking' | 'online' | 'offline'>('checking')
  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 5000)
    let active = true
    getHealth(controller.signal)
      .then((health) => {
        if (active) setState(health.status === 'ok' ? 'online' : 'offline')
      })
      .catch(() => { if (active) setState('offline') })
      .finally(() => window.clearTimeout(timeout))
    return () => { active = false; controller.abort(); window.clearTimeout(timeout) }
  }, [])
  return state
}
