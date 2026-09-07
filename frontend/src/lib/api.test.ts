import { describe, expect, it } from 'vitest'
import { ApiError, errorMessage } from './api'

describe('api error messages', () => {
  it('formats FastAPI validation detail arrays', () => {
    const error = new ApiError(422, [{ msg: '文件字段缺失' }, { msg: '格式无效' }])
    expect(errorMessage(error)).toBe('文件字段缺失；格式无效')
  })

  it('turns a failed fetch into a local service hint', () => {
    expect(errorMessage(new TypeError('Failed to fetch'))).toBe(
      '无法连接本地服务，请确认 FamilyLedger 仍在运行后重试',
    )
  })
})
