import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XFLT23 — pré-remplissage OCR d'un reçu de station sur le formulaire de
   plein. On vérifie que le fichier est envoyé à `pleins.ocr` et que les
   champs renvoyés pré-remplissent le formulaire, sans réseau réel. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const ocr = vi.fn(() => Promise.resolve({
  data: { champs: { date_plein: '2026-07-01', quantite: 45.2, prix_total: 520.5, station: 'Afriquia' } },
}))
const pleinsCreate = vi.fn(() => Promise.resolve({ data: { id: 1 } }))

vi.mock('../../api/flotteApi', () => ({
  default: {
    pleins: { ocr: (...args) => ocr(...args), create: (...args) => pleinsCreate(...args) },
  },
}))

import PleinDialog from './PleinDialog'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(<ThemeProvider>{ui}</ThemeProvider>)
}

describe('PleinDialog OCR (XFLT23)', () => {
  it('envoie la photo à pleins.ocr et pré-remplit les champs renvoyés', async () => {
    const user = userEvent.setup()
    withProviders(
      <PleinDialog vehicules={[{ id: 1, immatriculation: '12345-A-6' }]} onClose={() => {}} onSaved={() => {}} />,
    )

    const file = new File(['recu'], 'recu.jpg', { type: 'image/jpeg' })
    const input = document.querySelector('input[type="file"]')
    await user.upload(input, file)

    await waitFor(() => expect(ocr).toHaveBeenCalled())
    const formDataArg = ocr.mock.calls[0][0]
    expect(formDataArg.get('photo')).toBe(file)

    await waitFor(() => expect(screen.getByLabelText('Station')).toHaveValue('Afriquia'))
    expect(screen.getByLabelText('Date du plein')).toHaveValue('2026-07-01')
    expect(screen.getByLabelText('Coût total (MAD)')).toHaveValue(520.5)
  })
})
