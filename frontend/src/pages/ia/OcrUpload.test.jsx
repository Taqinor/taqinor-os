import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

// VX39 — mock du client IA : analyse + sauvegarde ne touchent pas le réseau.
vi.mock('../../api/iaApi', () => ({
  default: {
    processDocument: vi.fn(() => Promise.resolve({
      data: {
        texte_brut: 'Facture n°123',
        type_document: 'facture',
        confiance: 0.9,
        donnees_structurees: { numero: 'FA-2026-001', fournisseur: 'ACME' },
      },
    })),
    saveOcrDocument: vi.fn(() => Promise.resolve({ data: { id: 42 } })),
    getOcrDocuments: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

import iaApi from '../../api/iaApi'
import iaReducer from '../../features/ia/store/iaSlice'
import OcrUpload from './OcrUpload'

// jsdom ne fournit pas createObjectURL/revokeObjectURL.
beforeEach(() => {
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake-preview')
  globalThis.URL.revokeObjectURL = vi.fn()
  iaApi.processDocument.mockClear()
  iaApi.saveOcrDocument.mockClear()
})

function makeStore() {
  return configureStore({
    reducer: {
      ia: iaReducer,
      auth: (state = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => state,
    },
  })
}

async function uploadFile() {
  const file = new File(['contenu'], 'facture.png', { type: 'image/png' })
  const input = document.querySelector('input[type="file"]')
  await userEvent.upload(input, file)
}

describe('OcrUpload — AnalyseTab source + extraction éditable (VX39)', () => {
  it('affiche une table de champs éditables initialisée depuis le résultat OCR', async () => {
    const store = makeStore()
    render(<Provider store={store}><MemoryRouter><OcrUpload /></MemoryRouter></Provider>)
    await uploadFile()

    const numeroField = await screen.findByTestId('ocr-field-numero')
    const fournisseurField = screen.getByTestId('ocr-field-fournisseur')
    expect(numeroField).toHaveValue('FA-2026-001')
    expect(fournisseurField).toHaveValue('ACME')
    expect(screen.getByTestId('ocr-source-preview')).toBeInTheDocument()
  })

  it('la sauvegarde envoie les valeurs CORRIGÉES, pas les valeurs brutes', async () => {
    const store = makeStore()
    render(<Provider store={store}><MemoryRouter><OcrUpload /></MemoryRouter></Provider>)
    await uploadFile()

    const numeroField = await screen.findByTestId('ocr-field-numero')
    await userEvent.clear(numeroField)
    await userEvent.type(numeroField, 'FA-2026-999')

    await userEvent.click(screen.getByRole('button', { name: /Valider et enregistrer/ }))

    expect(iaApi.saveOcrDocument).toHaveBeenCalledWith(
      expect.objectContaining({
        donnees_structurees: expect.objectContaining({ numero: 'FA-2026-999', fournisseur: 'ACME' }),
      }),
    )
  })
})
