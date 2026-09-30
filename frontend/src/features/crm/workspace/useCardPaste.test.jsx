import { describe, it, expect, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { renderHook, act } from '@testing-library/react'
import useCardPaste from './useCardPaste'

const HERE = dirname(fileURLToPath(import.meta.url))
const evt = (text) => ({ clipboardData: { getData: () => text } })

describe('useCardPaste (QJR638)', () => {
  it('coller une carte propose, appliquer écrit nom + téléphone puis efface', () => {
    const appliquer = vi.fn()
    const { result } = renderHook(() => useCardPaste(appliquer))
    act(() => result.current.onNomPaste(evt('Jean Dupont 0661234567')))
    expect(result.current.cardPaste).toBeTruthy()
    expect(appliquer).not.toHaveBeenCalled()
    act(() => result.current.applyCardPaste())
    expect(appliquer).toHaveBeenCalledTimes(1)
    const arg = appliquer.mock.calls[0][0]
    expect(arg.nom).toBeTruthy()
    expect(arg.telephone).toBeTruthy()
    expect(result.current.cardPaste).toBeNull()
  })

  it('annuler efface la proposition sans rien appliquer', () => {
    const appliquer = vi.fn()
    const { result } = renderHook(() => useCardPaste(appliquer))
    act(() => result.current.onNomPaste(evt('Jean Dupont 0661234567')))
    act(() => result.current.annuler())
    expect(result.current.cardPaste).toBeNull()
    expect(appliquer).not.toHaveBeenCalled()
  })

  it('garde de source : `const enumOptions` n\'est défini que dans enumOptions.js', () => {
    const dir = join(HERE, 'sections')
    for (const f of ['SectionEnergie.jsx', 'SectionPipeline.jsx', 'SectionSite.jsx']) {
      expect(readFileSync(join(dir, f), 'utf8')).not.toMatch(/const enumOptions\s*=/)
    }
    expect(readFileSync(join(dir, 'enumOptions.js'), 'utf8')).toMatch(/const enumOptions\s*=/)
  })
})
