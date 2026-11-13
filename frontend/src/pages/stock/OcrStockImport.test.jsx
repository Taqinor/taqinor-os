import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   AERR88 — la quantité d'une ligne d'import OCR se laisse effacer et retaper
   (avant : `Math.max(1, parseInt(…) || 1)` remettait « 1 » à chaque frappe →
   effacer puis taper « 5 » donnait 15) ; « 2.5 » est refusé avec un message.
   Nouveau fichier car : aucun module de test de comportement pour
   OcrStockImport (seul entetes.apx24.test.mjs lit son source).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({ default: {} }))

import { LigneCard } from './OcrStockImport.jsx'

const LIGNE = {
  id: 0, ref_ocr: 'CAB-6', nom_ocr: 'Câble 6 mm²', quantite: 1, prix_unitaire: '',
  action: 'skip', produit_id: '', tva: null, update_tva: false,
  nouveau_nom: 'Câble 6 mm²', nouveau_sku: 'CAB-6', nouveau_prix_achat: '', nouveau_prix_vente: '',
  categorie_suggeree: null, categorie_source: null, categorie_action: 'none', categorie_id: '', categorie_nom_new: '',
}

function Harnais() {
  const [ligne, setLigne] = useState(LIGNE)
  return (
    <ThemeProvider>
      <LigneCard ligne={ligne} produits={[]} categories={[]} docType="facture_achat"
                 onChange={(patch) => setLigne((l) => ({ ...l, ...patch }))} />
    </ThemeProvider>
  )
}

describe('AERR88 — quantité d’une ligne OCR', () => {
  it('effacer puis taper 5 : 5', () => {
    render(<Harnais />)
    const champ = screen.getByLabelText('Qté')
    fireEvent.change(champ, { target: { value: '' } })
    expect(champ).toHaveValue(null)
    expect(screen.getByRole('alert').textContent).toMatch(/Nombre entier/)
    fireEvent.change(champ, { target: { value: '5' } })
    expect(champ).toHaveValue(5)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('2.5 : refusé avec un message, jamais 2', () => {
    render(<Harnais />)
    const champ = screen.getByLabelText('Qté')
    fireEvent.change(champ, { target: { value: '2.5' } })
    expect(champ).toHaveValue(2.5)
    expect(screen.getByRole('alert').textContent).toMatch(/Nombre entier/)
  })
})
