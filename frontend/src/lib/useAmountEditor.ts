import { useCallback, useEffect, useRef, useState } from 'react'
import { useBeforeUnload, useBlocker } from 'react-router-dom'
import { api, errorMessage } from './api'
import { centsToInput, parseAmountToCents } from './money'
import type { Snapshot } from '../types'

export function useAmountEditor() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [values, setValues] = useState<Record<number, string>>({})
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState('草稿已就绪')
  const current = useRef<Snapshot | null>(null)
  const latestValues = useRef<Record<number, string>>({})
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const queue = useRef<Promise<boolean>>(Promise.resolve(true))
  const initialize = useCallback((data: Snapshot) => {
    current.current = data; setSnapshot(data)
    const initial = Object.fromEntries((data.entries ?? []).map(e => [e.id, centsToInput(e.amount_cents)]))
    latestValues.current = initial; setValues(initial); setError(''); setSaveStatus('内容已保存')
  }, [])
  const saveAll = useCallback((): Promise<boolean> => {
    if (timer.current) clearTimeout(timer.current)
    const task = async () => {
      const data = current.current
      if (!data) return true
      setSaving(true)
      try {
        const entries = (data.entries ?? []).map(e => {
          try { return { id: e.id, amount_cents: parseAmountToCents(latestValues.current[e.id] ?? ''), expected_amount_cents: e.amount_cents } }
          catch (reason) { throw new Error(`${e.member_name} ${e.account_name}：${errorMessage(reason)}`) }
        }).filter(e => e.amount_cents !== e.expected_amount_cents)
        if (entries.length) {
          setSaveStatus('正在保存…')
          const updated = await api.put<Snapshot>(`/snapshots/${data.id}/entries`, { entries })
          current.current = updated; setSnapshot(updated)
        }
        const pending = (current.current?.entries ?? []).some(e => {
          try { return parseAmountToCents(latestValues.current[e.id] ?? '') !== e.amount_cents } catch { return true }
        })
        setError(''); setSaveStatus(pending ? '有未保存的内容' : '全部内容已保存'); return true
      } catch (reason) {
        setError(errorMessage(reason)); setSaveStatus('保存失败，输入已保留'); return false
      } finally { setSaving(false) }
    }
    queue.current = queue.current.then(task, task)
    return queue.current
  }, [])
  const changeValue = useCallback((id: number, value: string, autoSave = true) => {
    latestValues.current = { ...latestValues.current, [id]: value }; setValues(latestValues.current)
    setSaveStatus('有未保存的内容')
    if (timer.current) clearTimeout(timer.current)
    if (autoSave) timer.current = setTimeout(() => void saveAll(), 550)
  }, [saveAll])
  const dirty = (snapshot?.entries ?? []).some(e => {
    try { return parseAmountToCents(values[e.id] ?? '') !== e.amount_cents } catch { return true }
  })
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])
  return { snapshot, values, error, setError, saving, saveStatus, initialize, changeValue, saveAll, dirty }
}

export function useSaveBeforeLeave(dirty: boolean, saveAll: () => Promise<boolean>) {
  const blocker = useBlocker(dirty)
  const attempting = useRef(false)
  const [leaving, setLeaving] = useState(false)
  useBeforeUnload(useCallback((event: BeforeUnloadEvent) => {
    if (dirty) { event.preventDefault(); event.returnValue = '' }
  }, [dirty]))
  useEffect(() => {
    if (blocker.state !== 'blocked' || attempting.current) return
    attempting.current = true; setLeaving(true)
    void saveAll().then(saved => { if (saved) blocker.proceed(); else blocker.reset() })
      .finally(() => { attempting.current = false; setLeaving(false) })
  }, [blocker, saveAll])
  return leaving
}
