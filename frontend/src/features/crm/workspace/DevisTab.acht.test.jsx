import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { initState } from './draftCore'
import DevisTab from './DevisTab'

/* ACHT5 — « Créer le chantier » n'est proposé que sur la TÊTE de chaîne
   active : une version remplacée (is_active=false) n'a jamais de chantier. */

vi.mock('../../../api/ventesApi', () => ({
  default: {
    shareLinkDevis: vi.fn(),
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    reviserDevis: vi.fn(),
  },
}))
vi.mock('../../../api/installationsApi', () => ({ default: { createFromDevis: vi.fn() } }))
vi.mock('../../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: { results: [], count: 0, next: null } })) },
}))
vi.mock('../../../api/crmApi', () => ({
  default: {
    whatsappDevis: vi.fn(),
    whatsappDevisApercu: vi.fn(),
    getLeadSalleVenteAnalytics: () => Promise.resolve({ data: null }),
  },
}))

beforeAll(() => {
  if (!window.HTMLElement.prototype.scrollIntoView) window.HTMLElement.prototype.scrollIntoView = () => {}
})
afterEach(cleanup)

const base = {
  statut: 'accepte', total_ttc: '15000', date_creation: '2026-01-05',
  option_acceptee: 'A', chantier: null, is_active: true,
}

function rendre(devis, wa = { selected: [], langue: 'fr', preview: null }) {
  const state = initState({
    lead: {
      id: 7, nom: 'Karim', telephone: '0612345678', whatsapp: '',
      devis, devis_auto: { pret: true, manquants: [], message: null },
    },
    mode: 'edit',
  })
  return render(
    <MemoryRouter>
      <DevisTab
        state={state} onAction={vi.fn()}
        wa={wa}
        onWaToggle={vi.fn()} onWaLangue={vi.fn()} onWaPreview={vi.fn()} onWaReset={vi.fn()}
      />
    </MemoryRouter>,
  )
}

describe('ACHT5 — création de chantier sur la tête de chaîne seulement', () => {
  it('pas de création sur version remplacée', () => {
    rendre([
      { ...base, id: 1, reference: 'DEV-V1', is_active: false, superseded_by: 2 },
      { ...base, id: 2, reference: 'DEV-V2', version: 2, chantier: { id: 5, reference: 'CHT-5' } },
    ])
    expect(screen.queryByRole('button', { name: /Créer le chantier/ })).toBeNull()
    expect(screen.getByRole('link', { name: /CHT-5/ })).toHaveAttribute('href', '/chantiers?id=5')
  })

  it('bouton gardé sur tête active', () => {
    rendre([{ ...base, id: 3, reference: 'DEV-V3' }])
    expect(screen.getByRole('button', { name: /Créer le chantier/ })).toBeInTheDocument()
  })
})

// T4-X1-010 — « Variante Darija » montrait le même français sans le dire, et le
// lien paraissait deux fois (dans le message ET dans une liste dessous).
describe('T4-X1-010 — aperçu WhatsApp : darija non rédigé, lien unique', () => {
  const apercu = (extra) => ({
    selected: [1], langue: 'fr',
    preview: {
      message: 'Bonjour X, voici votre devis : https://t/p/abc',
      links: [{ devis_id: 1, reference: 'DEV-1', url: 'https://t/p/abc' }],
      wa_url: 'https://wa.me/212600000000?text=x', langue_effective: 'fr', ...extra,
    },
  })

  it('darija sans texte rédigé : la phrase le dit, « Ouvrir WhatsApp » est grisé', () => {
    rendre([{ ...base, id: 1, reference: 'DEV-1', statut: 'envoye' }], { ...apercu(), langue: 'darija' })
    expect(screen.getByTestId('wa-darija-non-redige').textContent).toMatch(/Variante darija : texte non rédigé/)
    expect(screen.getByRole('button', { name: /Ouvrir WhatsApp/ })).toBeDisabled()
  })

  it('le lien n’est montré qu’une fois (dans le message), jamais répété dessous', () => {
    rendre([{ ...base, id: 1, reference: 'DEV-1', statut: 'envoye' }], apercu())
    expect(screen.getAllByText(/https:\/\/t\/p\/abc/)).toHaveLength(1)
    expect(screen.queryByTestId('wa-darija-non-redige')).toBeNull()
    expect(screen.getByRole('button', { name: /Ouvrir WhatsApp/ })).toBeEnabled()
  })
})

// D-ACAL-154 — la taille visée est PORTÉE par la fiche quand elle le fournit : la frappe remonte (le champ reste
// le seul éditeur) et le bouton « Devis automatique » envoie la valeur portée.
describe('D-ACAL-154 — taille visée portée par la fiche', () => {
  it('la frappe remonte, le bouton envoie la valeur portée', () => {
    const onAction = vi.fn()
    const onKwcCibleChange = vi.fn()
    const state = initState({
      lead: { id: 7, nom: 'Karim', telephone: '0612345678', devis: [], devis_auto: { pret: true, manquants: [], message: null } },
      mode: 'edit',
    })
    render(
      <MemoryRouter>
        <DevisTab
          state={state} onAction={onAction} wa={{ selected: [], langue: 'fr', preview: null }}
          onWaToggle={vi.fn()} onWaLangue={vi.fn()} onWaPreview={vi.fn()} onWaReset={vi.fn()}
          kwcCible="6.5" onKwcCibleChange={onKwcCibleChange}
        />
      </MemoryRouter>,
    )
    expect(screen.getByLabelText(/Puissance cible/)).toHaveValue(6.5)
    fireEvent.change(screen.getByLabelText(/Puissance cible/), { target: { value: '8' } })
    expect(onKwcCibleChange).toHaveBeenCalledWith('8')
    fireEvent.click(screen.getByRole('button', { name: /Devis automatique/ }))
    expect(onAction).toHaveBeenCalledWith('open-devis', { mode: 'auto', targetKwc: '6.5' })
  })
})
