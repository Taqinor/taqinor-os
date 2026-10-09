import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import FactureRow from './FactureRow'

/* AFAC10 — la ligne facture LIT `encaissable` / `motif_non_encaissable`
   (contrat facture_encaissable.json) : plus de règle JS locale. */

const ICI = dirname(fileURLToPath(import.meta.url))
const CONTRAT = JSON.parse(readFileSync(join(
  ICI, '..', '..', '..', '..', '..', 'backend', 'django_core', 'apps', 'facturation',
  'contract_samples', 'facture_encaissable.json'), 'utf8'))

const ctx = {
  selectedIds: [], toggleSelect: () => {},
  pdfGenerating: {}, pdfDownloading: {}, waBusy: {}, payLinkBusy: {}, dgiBusy: {},
  actionId: null, histoCache: {}, canManage: true, isAdmin: true,
}

function rendre(facture) {
  return render(
    <MemoryRouter>
      <table><tbody><FactureRow f={{ client: 1, client_nom: 'X', ...facture }} ctx={ctx} /></tbody></table>
    </MemoryRouter>,
  )
}

describe('FactureRow — AFAC10 : actions d’encaissement pilotées par le serveur', () => {
  it('une facture émise encaissable montre Encaisser et Payer en ligne', () => {
    rendre(CONTRAT.exemple)
    expect(screen.getByRole('button', { name: /Encaisser/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Payer en ligne/ })).toBeInTheDocument()
  })

  it('brouillon sans Encaisser ni Payer en ligne, motif en infobulle d’Émettre', () => {
    rendre(CONTRAT.exemple_brouillon)
    expect(screen.queryByRole('button', { name: /Encaisser/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Payer en ligne/ })).toBeNull()
    const emettre = screen.getByRole('button', { name: /Émettre/ })
    expect(emettre).toHaveAttribute('title', CONTRAT.exemple_brouillon.motif_non_encaissable)
  })

  it('facture soldée : aucune action d’encaissement', () => {
    rendre(CONTRAT.exemple_soldee)
    expect(screen.queryByRole('button', { name: /Encaisser/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Payer en ligne/ })).toBeNull()
  })

  it('la règle JS locale a disparu des sites d’encaissement', () => {
    const src = readFileSync(join(ICI, 'FactureRow.jsx'), 'utf8')
    expect(src).not.toMatch(/montant_du \?\? 0\) > 0 && f\.statut !== 'annulee'/)
    expect(src).toMatch(/f\.encaissable !== false && \(\s*<DropdownMenuItem/)
  })
})
