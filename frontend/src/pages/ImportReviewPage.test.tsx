// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ImportReviewPage from './ImportReviewPage'
import { api } from '../lib/api'

vi.mock('../lib/api', async importOriginal => ({
  ...await importOriginal<typeof import('../lib/api')>(),
  api: { uploadMany: vi.fn(), post: vi.fn() },
}))
const totals = { net_worth_cents: 10000, total_assets_cents: 10000, total_liabilities_cents: 0 }
const ready = () => ({ token: 'token', review_id: 'revision', files: ['a.csv'], members: ['峰峰', '贤贤', '家庭公共'],
  mappings: {}, evidence: [], groups: [{ key: 'loan', account_name: '借款', source_member: '峰峰',
    member_name: null, account_type: 'receivable', needs_review: true, direction_unclear: true,
    months: ['2026-04'], sources: ['a.csv · 第2行'] }],
  months: [{ month: '2026-04', source_sheet: null, source_date: '2026-04-15', snapshot_id: null,
    status: 'needs_review', errors: [], warnings: [], calculated_summary: totals, entries: [] }],
})
function mount() { return render(<MemoryRouter><ImportReviewPage /></MemoryRouter>) }
beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

describe('联合导入核对', () => {
  it('uploads related files for preview only, requires resolved mapping and an explicit commit', async () => {
    const user = userEvent.setup()
    vi.mocked(api.uploadMany).mockResolvedValue(ready())
    const view = mount()
    await user.upload(view.container.querySelector('input[type=file]')!, [
      new File(['a'], 'a.xlsx'), new File(['b'], 'b.md'), new File(['c'], 'c.md'),
    ])
    await screen.findByText('1 个账户需要确认。原表没有标明成员的项目不会自动归入家庭公共。')
    expect(api.uploadMany).toHaveBeenCalledTimes(1)
    expect(api.post).not.toHaveBeenCalled()
    const button = screen.getByRole('button', { name: '确认保存所选月份' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    await user.selectOptions(screen.getByLabelText('借款 所属成员'), '贤贤')
    await user.selectOptions(screen.getByLabelText('借款 账户类型'), 'other_liability')
    const reviewed = ready(); reviewed.months[0].status = 'new'; reviewed.groups[0].needs_review = false
    reviewed.groups[0].member_name = '贤贤' as never
    vi.mocked(api.post).mockResolvedValueOnce(reviewed)
    await user.click(screen.getByRole('button', { name: '应用选择并重新核对' }))
    await waitFor(() => expect(button.disabled).toBe(false))
    expect(api.post).toHaveBeenCalledWith('/import/batch/review', expect.objectContaining({ mappings: {
      loan: { member_name: '贤贤', account_type: 'other_liability' },
    } }))
    vi.mocked(api.post).mockResolvedValueOnce({ applied_months: ['2026-04'], success_rows: 1, backup_filename: 'backup.db' })
    await user.click(button)
    await screen.findByText('已保存 1 个月份')
    expect(api.post).toHaveBeenCalledWith('/import/batch/confirm', { token: 'token', review_id: 'revision', months: ['2026-04'] })
  })
  it('keeps errors with the selected files and does not commit when the service is offline', async () => {
    vi.mocked(api.uploadMany).mockRejectedValue(new TypeError('Failed to fetch'))
    const user = userEvent.setup(); const view = mount()
    await user.upload(view.container.querySelector('input[type=file]')!, new File(['a'], 'a.md'))
    await screen.findByRole('alert')
    expect(screen.getByText('a.md')).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()
  })
  it('blocks over-sized files before sending them', async () => {
    const file = new File(['x'], 'big.xlsx'); Object.defineProperty(file, 'size', { value: 21 * 1024 * 1024 })
    const user = userEvent.setup(); const view = mount()
    await user.upload(view.container.querySelector('input[type=file]')!, file)
    await screen.findByRole('alert')
    expect(api.uploadMany).not.toHaveBeenCalled()
  })
})
