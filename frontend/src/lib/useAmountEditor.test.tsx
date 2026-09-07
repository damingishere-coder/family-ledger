// @vitest-environment jsdom
import { useEffect } from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, Link, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useAmountEditor, useSaveBeforeLeave } from './useAmountEditor'
import { api } from './api'
import type { Snapshot } from '../types'

vi.mock('./api', async importOriginal => ({ ...await importOriginal<typeof import('./api')>(), api: { put: vi.fn() } }))
const data = (cents = 10000) => ({ id: 1, snapshot_date: '2026-04-30', entries: [{
  id: 1, member_name: '峰峰', account_name: '微信', amount_cents: cents,
}] }) as Snapshot
function Editor() {
  const editor = useAmountEditor()
  useSaveBeforeLeave(editor.dirty, editor.saveAll)
  useEffect(() => editor.initialize(data()), [editor.initialize])
  return <><input aria-label="金额" value={editor.values[1] ?? ''} onChange={e => editor.changeValue(1, e.target.value, false)} />
    <button onClick={() => void editor.saveAll()}>保存</button><p>{editor.error}</p><Link to="/next">离开</Link></>
}
function mount() {
  return render(<RouterProvider router={createMemoryRouter([
    { path: '/', element: <Editor /> }, { path: '/next', element: <p>下一页</p> },
  ])} />)
}
const NativeRequest = Request
beforeEach(() => {
  vi.clearAllMocks()
  // jsdom's AbortSignal is a different realm from Node's native Request.
  // Navigation cancellation is not under test here; keep real routing behavior.
  vi.stubGlobal('Request', class extends NativeRequest {
    constructor(input: RequestInfo | URL, init?: RequestInit) { super(input, { ...init, signal: undefined }) }
  })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('saves pending amounts before leaving the page', async () => {
  vi.mocked(api.put).mockResolvedValue(data(25000))
  const user = userEvent.setup(); mount()
  await user.clear(screen.getByLabelText('金额')); await user.type(screen.getByLabelText('金额'), '250')
  await user.click(screen.getByText('离开'))
  await screen.findByText('下一页')
  expect(api.put).toHaveBeenCalledWith('/snapshots/1/entries', { entries: [{ id: 1, amount_cents: 25000, expected_amount_cents: 10000 }] })
})
it('stays on the page and retains input when saving fails', async () => {
  vi.mocked(api.put).mockRejectedValue(new Error('模拟网络失败'))
  const user = userEvent.setup(); mount()
  await user.clear(screen.getByLabelText('金额')); await user.type(screen.getByLabelText('金额'), '250')
  await user.click(screen.getByText('离开'))
  await screen.findByText('模拟网络失败')
  expect((screen.getByLabelText('金额') as HTMLInputElement).value).toBe('250')
  expect(screen.queryByText('下一页')).toBeNull()
})
it('serializes overlapping saves and compares against the last acknowledged amount', async () => {
  let resolveFirst!: (value: Snapshot) => void
  vi.mocked(api.put).mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve as typeof resolveFirst }))
    .mockResolvedValueOnce(data(30000))
  const user = userEvent.setup(); mount()
  await user.clear(screen.getByLabelText('金额')); await user.type(screen.getByLabelText('金额'), '200')
  await user.click(screen.getByText('保存'))
  await user.clear(screen.getByLabelText('金额')); await user.type(screen.getByLabelText('金额'), '300')
  await user.click(screen.getByText('保存'))
  expect(api.put).toHaveBeenCalledTimes(1)
  resolveFirst(data(20000))
  await waitFor(() => expect(api.put).toHaveBeenCalledTimes(2))
  expect(api.put).toHaveBeenLastCalledWith('/snapshots/1/entries', { entries: [{ id: 1, amount_cents: 30000, expected_amount_cents: 20000 }] })
})
