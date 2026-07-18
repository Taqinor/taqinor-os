import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { initState } from './draftCore'
import DevisTab, { devisTrackCurrent, missingFieldTarget } from './DevisTab'

/* LW21 — `DevisTab` : cartes devis (StatusPill statut devis, total TTC
   `.num`, actions facture/chantier busy-par-id), CTA « Devis automatique »
   (prêt → bouton + menu ; pas prêt → champs manquants cliquables). La barre
   WhatsApp multi-devis (LW22) est testée dans son propre lot de tests, ajouté
   à ce même fichier par la tâche suivante. */

const { genererFacture, createFromDevis } = vi.hoisted(() => ({
  genererFacture: vi.fn(() => Promise.resolve({ data: { reference: 'FAC-1', type_facture_display: 'Facture' } })),
  createFromDevis: vi.fn(() => Promise.resolve({ data: { reference: 'CHT-1' } })),
}))
vi.mock('../../../api/ventesApi', () => ({ default: { genererFacture } }))
vi.mock('../../../api/installationsApi', () => ({ default: { createFromDevis } }))

beforeAll(() => {
  if (!window.HTMLElement.prototype.scrollIntoView) window.HTMLElement.prototype.scrollIntoView = () => {}
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const leadState = (leadOverrides = {}) => initState({
  lead: {
    id: 7, nom: 'Karim',
    devis: [], devis_auto: { pret: true, manquants: [], message: null },
    ...leadOverrides,
  },
  mode: 'edit',
})

function renderTab(props = {}) {
  const onAction = vi.fn()
  const utils = render(<DevisTab state={leadState()} onAction={onAction} {...props} />)
  return { ...utils, onAction }
}

describe('LW21 — logique pure (co-localisée, testable sans DOM)', () => {
  it('devisTrackCurrent : accepté sans chantier → "accepte" ; avec chantier → "chantier"', () => {
    expect(devisTrackCurrent({ chantier: null })).toBe('accepte')
    expect(devisTrackCurrent({ chantier: { id: 1, reference: 'CHT-1' } })).toBe('chantier')
  })

  it('missingFieldTarget mappe les libellés backend (devis_auto.py) vers les id lf-*', () => {
    expect(missingFieldTarget('facture hiver')).toEqual({ field: 'lf-facture-hiver', section: 'energie' })
    expect(missingFieldTarget('HMT')).toEqual({ field: 'lf-pompe-hmt', section: 'pompage' })
    expect(missingFieldTarget('inconnu')).toBeNull()
  })
})

describe('LW21 — CTA devis automatique', () => {
  it('devis_auto.pret → bouton primaire + menu remise/onepage/premium/édition', async () => {
    const user = userEvent.setup()
    const { onAction } = renderTab({ state: leadState({ devis_auto: { pret: true, manquants: [] } }) })
    await user.click(screen.getByRole('button', { name: /Devis automatique/ }))
    expect(onAction).toHaveBeenCalledWith('open-devis', 'auto')

    await user.click(screen.getByRole('button', { name: /Devis modifiable/ }))
    await user.click(screen.getByText('Remise %…'))
    expect(onAction).toHaveBeenCalledWith('open-devis', 'remise')
  })

  it('devis_auto pas prêt → liste des champs manquants cliquables (saute au champ du centre)', async () => {
    const user = userEvent.setup()
    const input = document.createElement('input')
    input.id = 'lf-facture-hiver'
    document.body.appendChild(input)
    const focusSpy = vi.spyOn(input, 'focus')
    try {
      renderTab({
        state: leadState({ devis_auto: { pret: false, manquants: ['facture hiver'], message: 'Manque : facture hiver' } }),
      })
      expect(screen.queryByRole('button', { name: /Devis automatique/ })).toBeNull()
      await user.click(screen.getByText('facture hiver'))
      expect(focusSpy).toHaveBeenCalled()
    } finally {
      input.remove()
    }
  })
})

describe('LW21 — cartes devis + actions facture/chantier', () => {
  const devisAccepte = {
    id: 1, reference: 'DEV-2026-001', statut: 'accepte', total_ttc: '15000',
    date_creation: '2026-01-05', option_acceptee: 'A', chantier: null,
  }

  it('carte rend référence, statut, total .num et « Générer la facture »/« Créer le chantier »', () => {
    renderTab({ state: leadState({ devis: [devisAccepte] }) })
    expect(screen.getByText('DEV-2026-001')).toBeInTheDocument()
    expect(screen.getByText('Accepté')).toBeInTheDocument()
    expect(document.querySelector('.num')).toHaveTextContent('15 000')
    expect(screen.getByRole('button', { name: /Générer la facture/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Créer le chantier/ })).toBeInTheDocument()
  })

  it('« Générer la facture » appelle ventesApi puis onAction(\'refresh\')', async () => {
    const user = userEvent.setup()
    const { onAction } = renderTab({ state: leadState({ devis: [devisAccepte] }) })
    await user.click(screen.getByRole('button', { name: /Générer la facture/ }))
    await waitFor(() => expect(genererFacture).toHaveBeenCalledWith(1))
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('refresh'))
    expect(await screen.findByText(/FAC-1 créée/)).toBeInTheDocument()
  })

  it('« Créer le chantier » appelle installationsApi puis onAction(\'refresh\')', async () => {
    const user = userEvent.setup()
    const { onAction } = renderTab({ state: leadState({ devis: [devisAccepte] }) })
    await user.click(screen.getByRole('button', { name: /Créer le chantier/ }))
    await waitFor(() => expect(createFromDevis).toHaveBeenCalledWith(1))
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('refresh'))
  })

  it('chantier déjà créé → référence affichée au lieu du bouton', () => {
    renderTab({ state: leadState({ devis: [{ ...devisAccepte, chantier: { id: 5, reference: 'CHT-2026-005' } }] }) })
    expect(screen.getByText(/CHT-2026-005/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Créer le chantier/ })).toBeNull()
  })

  it('devis brouillon : aucune action facture/chantier ni piste document', () => {
    renderTab({ state: leadState({ devis: [{ ...devisAccepte, statut: 'brouillon' }] }) })
    expect(screen.queryByRole('button', { name: /Générer la facture/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Créer le chantier/ })).toBeNull()
  })
})
