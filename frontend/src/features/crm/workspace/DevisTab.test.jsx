import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { initState } from './draftCore'
import DevisTab, { devisTrackCurrent, missingFieldTarget, waArmed } from './DevisTab'

/* LW21/LW22 — `DevisTab` : cartes devis (StatusPill statut devis, total TTC
   `.num`, actions facture/chantier busy-par-id), CTA « Devis automatique »
   (prêt → bouton + menu ; pas prêt → champs manquants cliquables), barre
   WhatsApp multi-devis FR/Darija (état `wa` fourni par le parent — ici des
   props contrôlées, comme le fera réellement ContextRail). */

const { genererFacture, createFromDevis, whatsappDevis } = vi.hoisted(() => ({
  genererFacture: vi.fn(() => Promise.resolve({ data: { reference: 'FAC-1', type_facture_display: 'Facture' } })),
  createFromDevis: vi.fn(() => Promise.resolve({ data: { reference: 'CHT-1' } })),
  whatsappDevis: vi.fn(() => Promise.resolve({
    data: { message: 'Bonjour, voici votre devis', links: [{ devis_id: 1, reference: 'DEV-1', url: 'https://x/1' }], wa_url: 'https://wa.me/212600000000?text=x' },
  })),
}))
vi.mock('../../../api/ventesApi', () => ({ default: { genererFacture } }))
vi.mock('../../../api/installationsApi', () => ({ default: { createFromDevis } }))
vi.mock('../../../api/crmApi', () => ({ default: { whatsappDevis } }))

beforeAll(() => {
  if (!window.HTMLElement.prototype.scrollIntoView) window.HTMLElement.prototype.scrollIntoView = () => {}
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const leadState = (leadOverrides = {}) => initState({
  lead: {
    id: 7, nom: 'Karim', telephone: '0612345678', whatsapp: '',
    devis: [], devis_auto: { pret: true, manquants: [], message: null },
    ...leadOverrides,
  },
  mode: 'edit',
})

const waState = (overrides = {}) => ({ selected: [], langue: 'fr', preview: null, ...overrides })

function renderTab(props = {}) {
  const onAction = vi.fn()
  const onWaToggle = vi.fn()
  const onWaLangue = vi.fn()
  const onWaPreview = vi.fn()
  const onWaReset = vi.fn()
  const utils = render(
    <DevisTab
      state={leadState()}
      onAction={onAction}
      wa={waState()}
      onWaToggle={onWaToggle}
      onWaLangue={onWaLangue}
      onWaPreview={onWaPreview}
      onWaReset={onWaReset}
      {...props}
    />,
  )
  return { ...utils, onAction, onWaToggle, onWaLangue, onWaPreview, onWaReset }
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

  it('waArmed : numéro invalide ou sélection vide → jamais armé', () => {
    expect(waArmed('0612345678', 1)).toBe(true)
    expect(waArmed('0612345678', 0)).toBe(false)
    expect(waArmed('123', 1)).toBe(false)
    expect(waArmed('', 1)).toBe(false)
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

describe('LW22 — WhatsApp multi-devis', () => {
  const devis1 = {
    id: 1, reference: 'DEV-1', statut: 'envoye', total_ttc: '5000',
    date_creation: '2026-01-01', chantier: null,
  }

  it('case à cocher appelle onWaToggle(id)', async () => {
    const user = userEvent.setup()
    const { onWaToggle } = renderTab({ state: leadState({ devis: [devis1] }) })
    await user.click(screen.getByRole('checkbox', { name: /Sélectionner DEV-1/ }))
    expect(onWaToggle).toHaveBeenCalledWith(1)
  })

  it('numéro invalide → bouton désactivé avec hint « Numéro invalide »', () => {
    renderTab({
      state: leadState({ telephone: '123', devis: [devis1] }),
      wa: waState({ selected: [1] }),
    })
    expect(screen.getByRole('button', { name: /Envoyer par WhatsApp/ })).toBeDisabled()
    expect(screen.getByText('Numéro invalide')).toBeInTheDocument()
  })

  it('aucun numéro → hint dédié, bouton désactivé', () => {
    renderTab({ state: leadState({ telephone: '', whatsapp: '', devis: [devis1] }) })
    expect(screen.getByRole('button', { name: /Envoyer par WhatsApp/ })).toBeDisabled()
    expect(screen.getByText('Aucun numéro de téléphone')).toBeInTheDocument()
  })

  it('numéro valide + sélection non vide → armé, envoi ouvre l\'aperçu (onWaPreview) avant wa.me', async () => {
    const user = userEvent.setup()
    const { onWaPreview } = renderTab({
      state: leadState({ telephone: '0612345678', devis: [devis1] }),
      wa: waState({ selected: [1] }),
    })
    const btn = screen.getByRole('button', { name: /Envoyer par WhatsApp/ })
    expect(btn).toBeEnabled()
    await user.click(btn)
    await waitFor(() => expect(whatsappDevis).toHaveBeenCalledWith(7, { devis_ids: [1], langue: 'fr' }))
    await waitFor(() => expect(onWaPreview).toHaveBeenCalledWith({
      message: 'Bonjour, voici votre devis',
      links: [{ devis_id: 1, reference: 'DEV-1', url: 'https://x/1' }],
      wa_url: 'https://wa.me/212600000000?text=x',
    }))
  })

  it('aperçu affiché → « Ouvrir WhatsApp » ouvre wa.me puis réinitialise la sélection', async () => {
    const user = userEvent.setup()
    window.open = vi.fn(() => ({}))
    const { onWaReset } = renderTab({
      state: leadState({ telephone: '0612345678', devis: [devis1] }),
      wa: waState({ selected: [1], preview: { message: 'Bonjour', links: [], wa_url: 'https://wa.me/212600000000?text=x' } }),
    })
    expect(screen.getByText('Aperçu du message WhatsApp')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    expect(window.open).toHaveBeenCalledWith('https://wa.me/212600000000?text=x', '_blank', 'noopener')
    expect(onWaReset).toHaveBeenCalled()
  })

  it('langue FR/Darija appelle onWaLangue', async () => {
    const user = userEvent.setup()
    const { onWaLangue } = renderTab({ state: leadState({ devis: [devis1] }) })
    await user.click(screen.getByRole('button', { name: 'Darija' }))
    expect(onWaLangue).toHaveBeenCalledWith('darija')
  })
})
