import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from '../src/App'

const flags = vi.hoisted(() => ({ allow: false }))
vi.mock('../src/hooks/useBackendHealth', () => ({ useBackendHealth: () => 'online' }))
vi.mock('../src/pages/NotebooksPage', () => ({ NotebooksPage: () => <div>HOME VIEW</div> }))
vi.mock('../src/pages/WorkbenchPage', async () => {
  const { useEffect } = await import('react')
  return { WorkbenchPage: ({ setNavigationGuard }: { setNavigationGuard: (guard: (() => boolean) | null) => void }) => {
    useEffect(() => { setNavigationGuard(() => flags.allow); return () => setNavigationGuard(null) }, [setNavigationGuard])
    return <div>EDITOR VIEW</div>
  } }
})
afterEach(() => { cleanup(); window.history.replaceState(null, '', '/'); flags.allow = false })
it('restores the active hash and editor when navigation is declined', async () => {
  const hash = '#/notebooks/' + 'a'.repeat(32)
  window.history.replaceState(null, '', '/' + hash)
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: '专题首页' }))
  await waitFor(() => expect(window.location.hash).toBe(hash))
  expect(screen.getByText('EDITOR VIEW')).toBeTruthy(); expect(screen.queryByText('HOME VIEW')).toBeNull()
})
it('navigates when leaving is allowed', async () => {
  flags.allow = true
  window.history.replaceState(null, '', '/#/notebooks/' + 'b'.repeat(32))
  render(<App />); fireEvent.click(screen.getByRole('button', { name: '专题首页' }))
  await screen.findByText('HOME VIEW')
})
