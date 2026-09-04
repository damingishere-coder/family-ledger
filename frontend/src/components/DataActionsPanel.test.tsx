// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DataActionsPanel from './DataActionsPanel'
import type { ImportPreview, ImportRecord } from '../types'

const PREVIEW: ImportPreview = {
  source_filename: 'history.md',
  source_type: 'markdown',
  detected_encoding: 'utf-8-sig',
  total_snapshots: 1,
  total_rows: 4,
  importable_rows: 4,
  duplicate_snapshots: 0,
  blocked_snapshots: 0,
  ignored_snapshots: 0,
  warning_rows: 0,
  warnings: [],
  snapshots: [{
    snapshot_date: '2025-12-31',
    source_date: '2025-12-25',
    row_count: 4,
    will_skip: false,
    layout: 'markdown-horizontal',
    source_sheet: null,
    status: 'importable',
    blocking_errors: [],
    source_summary: {},
    calculated_summary: {
      total_assets_cents: 0,
      total_liabilities_cents: 0,
      net_worth_cents: 0,
      investment_assets_cents: 0,
      completed_entries: 0,
      total_entries: 4,
    },
    differences: [],
    warnings: [],
  }],
}

const IMPORT_RESULT: ImportRecord = {
  id: 1,
  source_filename: 'history.md',
  source_type: 'markdown',
  imported_at: '2026-09-01T12:00:00+08:00',
  status: 'success',
  total_rows: 4,
  success_rows: 4,
  warning_rows: 0,
  error_rows: 0,
  report: { warnings: [], errors: [] },
}

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Unprocessable Entity',
    json: async () => payload,
  } as Response
}

describe('DataActionsPanel import flow', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('shows parsing, previews without writing, then imports only after confirmation', async () => {
    let resolvePreview: ((response: Response) => void) | undefined
    let resolveImport: ((response: Response) => void) | undefined
    fetchMock
      .mockReturnValueOnce(new Promise<Response>((resolve) => { resolvePreview = resolve }))
      .mockReturnValueOnce(new Promise<Response>((resolve) => { resolveImport = resolve }))
    const onChanged = vi.fn()
    const { container } = render(<DataActionsPanel onChanged={onChanged} />)
    const input = container.querySelectorAll<HTMLInputElement>('input[type="file"]')[0]
    const file = new File(['# history'], 'history.md', { type: 'text/markdown' })

    fireEvent.change(input, { target: { files: [file] } })
    expect(await screen.findByText('正在解析文件，请稍候…')).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/import/legacy/preview')
    expect(onChanged).not.toHaveBeenCalled()

    resolvePreview?.(jsonResponse(PREVIEW))
    expect(await screen.findByRole('button', { name: '确认导入' })).toBeTruthy()
    expect(screen.getByText('4 行')).toBeTruthy()
    expect(screen.getByText(/4 行 · 可导入/)).toBeTruthy()
    expect(screen.getByText(/计算汇总：资产/)).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('button', { name: '确认导入' }))
    expect(await screen.findByText('正在写入本地数据库…')).toBeTruthy()
    expect(onChanged).not.toHaveBeenCalled()
    resolveImport?.(jsonResponse(IMPORT_RESULT))
    expect(await screen.findByText('文件已经导入并记录')).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[1][0]).toBe('/api/import/legacy')
    expect(onChanged).toHaveBeenCalledTimes(1)
  })

  it('keeps a readable preview error beside the selected file', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'Excel 文件损坏或不是有效的 XLSX/XLSM 工作簿' }, 422))
    const { container } = render(<DataActionsPanel />)
    const input = container.querySelectorAll<HTMLInputElement>('input[type="file"]')[1]
    const file = new File(['broken'], 'broken.xlsx')

    fireEvent.change(input, { target: { files: [file] } })

    expect(await screen.findByText('Excel 文件损坏或不是有效的 XLSX/XLSM 工作簿')).toBeTruthy()
    expect(screen.getByRole('button', { name: '重新选择' })).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('keeps a local service disconnect beside the selected file', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    const { container } = render(<DataActionsPanel />)
    const input = container.querySelectorAll<HTMLInputElement>('input[type="file"]')[0]

    fireEvent.change(input, { target: { files: [new File(['ok'], 'history.md')] } })

    expect(
      await screen.findByText('无法连接本地服务，请确认 FamilyLedger 仍在运行后重试'),
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: '重新选择' })).toBeTruthy()
  })

  it('cancels after preview without calling the import endpoint', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(PREVIEW))
    const { container } = render(<DataActionsPanel />)
    const input = container.querySelectorAll<HTMLInputElement>('input[type="file"]')[0]

    fireEvent.change(input, { target: { files: [new File(['ok'], 'history.md')] } })
    expect(await screen.findByRole('button', { name: '确认导入' })).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: '取消' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('rejects files over 20MB before making a request', async () => {
    const { container } = render(<DataActionsPanel />)
    const input = container.querySelectorAll<HTMLInputElement>('input[type="file"]')[0]
    const file = new File(['large'], 'large.md')
    Object.defineProperty(file, 'size', { value: 20 * 1024 * 1024 + 1 })

    fireEvent.change(input, { target: { files: [file] } })

    expect(await screen.findByText('文件超过 20MB 限制')).toBeTruthy()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
