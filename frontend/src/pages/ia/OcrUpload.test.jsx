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

// AAPV60 — créations (facture d'achat, lead) mockées : on lit les champs envoyés.
vi.mock('../../api/stockApi', () => ({
  default: {
    factureFournisseurDepuisOcr: vi.fn(() => Promise.resolve({
      data: { id: 7, reference: 'FF-1', fournisseur: null },
    })),
    getSuggestionsBcfFacture: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../api/publicapiApi', () => ({
  default: { ocrToCrm: vi.fn(() => Promise.resolve({ data: { lead_id: 1 } })) },
}))

import iaApi from '../../api/iaApi'
import stockApi from '../../api/stockApi'
import publicapiApi from '../../api/publicapiApi'
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

  it('la création de facture envoie les valeurs CORRIGÉES', async () => {
    // AAPV60 — extraction TTC seule : HT / TVA offerts à la correction, et
    // « Créer facture d'achat » / « Créer un lead » envoient editedFields.
    iaApi.processDocument.mockImplementationOnce(() => Promise.resolve({
      data: {
        texte_brut: 'Facture', type_document: 'facture', confiance: 0.9,
        donnees_structurees: { fournisseur: 'ACME', montant_ttc: 12000 },
      },
    }))
    const store = makeStore()
    render(<Provider store={store}><MemoryRouter><OcrUpload /></MemoryRouter></Provider>)
    await uploadFile()

    const ht = await screen.findByTestId('ocr-field-montant_ht')
    await userEvent.type(ht, '10000')
    await userEvent.type(screen.getByTestId('ocr-field-montant_tva'), '2000')

    await userEvent.click(screen.getByRole('button', { name: /Créer facture d'achat/ }))
    expect(stockApi.factureFournisseurDepuisOcr).toHaveBeenCalledWith(
      expect.objectContaining({
        fields: expect.objectContaining({
          montant_ht: '10000', montant_tva: '2000', montant_ttc: 12000,
        }),
      }),
    )
    await userEvent.click(screen.getByRole('button', { name: /Créer un lead/ }))
    expect(publicapiApi.ocrToCrm).toHaveBeenCalledWith(
      expect.objectContaining({ fields: expect.objectContaining({ montant_ht: '10000' }) }),
    )
  })
})
