import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { useDirection } from '@radix-ui/react-direction'

/* NTI18N2 — RtlDirectionProvider doit propager `useI18n().dir` au contexte
   Radix `DirectionProvider`, pour que les primitives Radix (Tabs,
   DropdownMenu…) reçoivent la bonne direction pour leur logique interne
   (navigation clavier, orientation) — pas seulement `<html dir>`. */

const mockUseI18n = vi.fn()
vi.mock('./context', () => ({ useI18n: () => mockUseI18n() }))

import RtlDirectionProvider from './RtlDirectionProvider'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function Probe() {
  const dir = useDirection()
  return <span data-testid="dir">{dir}</span>
}

describe('NTI18N2 RtlDirectionProvider', () => {
  it('propage dir="rtl" au contexte Radix quand la locale est arabe', () => {
    mockUseI18n.mockReturnValue({ dir: 'rtl' })
    render(<RtlDirectionProvider><Probe /></RtlDirectionProvider>)
    expect(screen.getByTestId('dir')).toHaveTextContent('rtl')
  })

  it('propage dir="ltr" par défaut (FR/EN)', () => {
    mockUseI18n.mockReturnValue({ dir: 'ltr' })
    render(<RtlDirectionProvider><Probe /></RtlDirectionProvider>)
    expect(screen.getByTestId('dir')).toHaveTextContent('ltr')
  })

  it('rend bien ses enfants', () => {
    mockUseI18n.mockReturnValue({ dir: 'ltr' })
    render(<RtlDirectionProvider><div data-testid="child">contenu</div></RtlDirectionProvider>)
    expect(screen.getByTestId('child')).toBeInTheDocument()
  })
})
