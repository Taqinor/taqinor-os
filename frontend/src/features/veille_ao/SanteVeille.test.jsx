import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   VAO37 — Bandeau de santé + carte d'honnêteté « ce que la veille NE voit
   pas ». Deux blocs indissociables (préambule Groupe VAO — promettre
   l'exhaustivité serait faux dès le premier jour, l'erreur qui a coûté FRDISI).
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  sante: vi.fn(),
  create: vi.fn(),
  // WIR269 — l'appel agrege « d'ou vient le chiffre d'affaires » (VAO31).
  attribution: vi.fn(),
}))

vi.mock('../../api/veilleAoApi', () => ({
  default: {
    sante: mocks.sante,
    avis: { create: mocks.create },
    attribution: mocks.attribution,
  },
}))

import SanteVeille from './SanteVeille'
import { ageLabel } from './veilleAoShared'

const renderScreen = (props) => render(<ThemeProvider><SanteVeille {...props} /></ThemeProvider>)

const ATTRIBUTION_VIDE = {
  depuis: null, par_source: [], par_informateur: [],
  total: {
    cle: 'total', libelle: 'Total',
    avis: 0, retenus: 0, affaires: 0, gagnes: 0, perdus: 0, en_cours: 0,
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.attribution.mockResolvedValue({ data: ATTRIBUTION_VIDE })
})

describe('ageLabel (VAO37 Done= « l’âge de la dernière collecte est visible sans clic »)', () => {
  it('« à l’instant » sous 1 heure', () => {
    expect(ageLabel('2026-08-07T08:30:00', new Date('2026-08-07T08:45:00'))).toBe('à l’instant')
  })

  it('en heures sous 24 h', () => {
    expect(ageLabel('2026-08-07T02:00:00', new Date('2026-08-07T08:00:00'))).toBe('il y a 6 h')
  })

  it('en jours au-delà de 24 h', () => {
    expect(ageLabel('2026-08-04T06:00:00', new Date('2026-08-07T06:00:00'))).toBe('il y a 3 j')
  })

  it('null sans date ou avec une date invalide', () => {
    expect(ageLabel(null)).toBeNull()
    expect(ageLabel('pas une date')).toBeNull()
  })
})

describe('SanteVeille — bloc santé', () => {
  it('affiche la dernière collecte réussie ET son âge sans clic', async () => {
    mocks.sante.mockResolvedValue({
      data: {
        collecte_active: true, derniere_collecte_reussie: '2026-08-06T06:00:00',
        alarme_active: false, avis_examines_hier: 5,
      },
    })
    renderScreen()
    await waitFor(() => expect(mocks.sante).toHaveBeenCalled())
    expect(await screen.findByText('Dernière collecte réussie')).toBeInTheDocument()
    expect(screen.getByText(/il y a/)).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('VAO37 (Done=) — une alarme active est IMPOSSIBLE à manquer', async () => {
    mocks.sante.mockResolvedValue({
      data: { alarme_active: true, alarme_message: 'La veille ne ramène plus rien — vérifiez.' },
    })
    renderScreen()
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('La veille ne ramène plus rien')
    expect(screen.queryByText(/aucune alarme/)).not.toBeInTheDocument()
  })

  it('sans alarme, affiche « aucune alarme » et aucun role=alert', async () => {
    mocks.sante.mockResolvedValue({ data: { alarme_active: false, derniere_collecte_reussie: null } })
    renderScreen()
    expect(await screen.findByText(/aucune alarme/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('« Jamais » quand aucune collecte n’a encore réussi', async () => {
    mocks.sante.mockResolvedValue({ data: { alarme_active: false, derniere_collecte_reussie: null } })
    renderScreen()
    expect(await screen.findByText('Jamais')).toBeInTheDocument()
  })
})

describe('SanteVeille — carte d’honnêteté (VAO37 Done= « le texte est présent et testé »)', () => {
  beforeEach(() => {
    mocks.sante.mockResolvedValue({ data: { alarme_active: false } })
  })

  it('énonce ce que la veille couvre et ne couvre PAS, avec les chiffres du préambule Groupe VAO', async () => {
    renderScreen()
    expect(await screen.findByText('Ce que la veille automatique ne voit pas')).toBeInTheDocument()
    expect(screen.getByText(/65 à 75 %/)).toBeInTheDocument()
    expect(screen.getByText(/FRDISI/)).toBeInTheDocument()
    expect(screen.getByText(/15 à 25 %/)).toBeInTheDocument()
    expect(screen.getByText(/0 % détectable/)).toBeInTheDocument()
    expect(screen.getByText(/ONEE-Électricité \/ MASEN \/ OCP/)).toBeInTheDocument()
    expect(screen.getByText(/10 % du nombre mais la majorité de la valeur/)).toBeInTheDocument()
  })

  it('rappelle le bouton « Ajouter un avis » pour un AO reçu par WhatsApp', async () => {
    renderScreen()
    expect(await screen.findByText('Un AO reçu par WhatsApp, SMS ou appel ?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Ajouter un avis/ })).toBeInTheDocument()
  })
})

describe('SanteVeille — « Ajouter un avis » (VAO27)', () => {
  beforeEach(() => {
    mocks.sante.mockResolvedValue({ data: { alarme_active: false } })
  })

  it('informateur est le SEUL champ requis (400 FR sinon, aucun appel réseau)', async () => {
    renderScreen()
    fireEvent.click(await screen.findByRole('button', { name: /Ajouter un avis/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }))
    expect(await screen.findByText(/informateur requis/)).toBeInTheDocument()
    expect(mocks.create).not.toHaveBeenCalled()
  })

  it('avec un informateur choisi, crée l’avis avec source `tuyau_partenaire` et notifie le rafraîchissement', async () => {
    const user = userEvent.setup()
    mocks.create.mockResolvedValue({ data: { id: 9 } })
    const onAvisAjoute = vi.fn()
    renderScreen({ onAvisAjoute })

    fireEvent.click(await screen.findByRole('button', { name: /Ajouter un avis/ }))
    await user.click(screen.getByRole('combobox'))
    // Radix rend le libelle DANS le declencheur ET dans la liste : viser
    // l'OPTION, jamais le texte brut (sinon deux noeuds correspondent).
    fireEvent.click(await screen.findByRole('option', { name: 'Partenaire' }))
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }))

    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({ informateur: 'partenaire', source: 'tuyau_partenaire' }),
    ))
    await waitFor(() => expect(onAvisAjoute).toHaveBeenCalled())
  })
})

/* ============================================================================
   WIR269 — « D'où vient le chiffre d'affaires » (VAO31).
   ----------------------------------------------------------------------------
   L'endpoint agrégé existait, personne ne l'appelait : le constat CENTRAL de
   l'étude était illisible. La garde qui compte ici n'est pas « le tableau
   s'affiche » mais « aucun agrégat n'est recalculé à l'écran » — le total
   rendu est CELUI DU SERVEUR, même quand il ne correspond pas à la somme des
   lignes (cas volontairement testé : un écran qui « corrige » le serveur en
   silence est un écran qui ment).
   ========================================================================== */
const ligne = (cle, libelle, over = {}) => ({
  cle,
  libelle,
  avis: 0,
  retenus: 0,
  affaires: 0,
  gagnes: 0,
  perdus: 0,
  en_cours: 0,
  ...over,
})

const ATTRIBUTION = {
  depuis: null,
  par_source: [
    ligne('portail_officiel', 'Portail officiel', {
      avis: 120, retenus: 18, affaires: 12, gagnes: 3, perdus: 7, en_cours: 2,
    }),
    ligne('tuyau_partenaire', 'Tuyau partenaire', {
      avis: 9, retenus: 7, affaires: 6, gagnes: 4, perdus: 1, en_cours: 1,
    }),
  ],
  par_informateur: [
    ligne('partenaire', 'Partenaire', {
      avis: 6, retenus: 5, affaires: 5, gagnes: 3, perdus: 1, en_cours: 1,
    }),
    ligne('aucun', 'Aucun (collecte automatique)', {
      avis: 123, retenus: 20, affaires: 13, gagnes: 4, perdus: 7, en_cours: 2,
    }),
  ],
  // VOLONTAIREMENT différent de la somme des lignes ci-dessus : c'est le
  // chiffre du serveur, et c'est LUI qui doit s'afficher.
  total: ligne('total', 'Total', {
    avis: 131, retenus: 26, affaires: 19, gagnes: 8, perdus: 9, en_cours: 4,
  }),
}

describe('SanteVeille — d’où vient le chiffre d’affaires (WIR269/VAO31)', () => {
  it('appelle l’endpoint agrégé et rend les DEUX axes à égalité', async () => {
    mocks.sante.mockResolvedValue({ data: {} })
    mocks.attribution.mockResolvedValue({ data: ATTRIBUTION })
    renderScreen()

    await waitFor(() => expect(mocks.attribution).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('D’où vient le chiffre d’affaires')).toBeInTheDocument()

    const parSource = await waitFor(() => {
      const el = document.querySelector('[data-veille-attribution="source"]')
      expect(el).toBeTruthy()
      return el
    })
    const parInformateur = document.querySelector('[data-veille-attribution="informateur"]')
    expect(parInformateur).toBeTruthy()

    // Les libellés viennent du serveur, jamais d'une table locale.
    expect(parSource.textContent).toMatch(/Portail officiel/)
    expect(parInformateur.textContent).toMatch(/Aucun \(collecte automatique\)/)
  })

  it('rend le TOTAL DU SERVEUR, jamais une somme recalculée à l’écran', async () => {
    mocks.sante.mockResolvedValue({ data: {} })
    mocks.attribution.mockResolvedValue({ data: ATTRIBUTION })
    renderScreen()

    const total = await waitFor(() => {
      const el = document.querySelector('[data-veille-attribution-total]')
      expect(el).toBeTruthy()
      return el
    })
    const cellules = [...total.querySelectorAll('td')].map((td) => td.textContent)
    // Le payload sert 131/26/19/8/9/4 ; la somme des lignes « par source »
    // vaudrait 129/25/18/7/8/3. C'est le SERVEUR qui fait foi.
    expect(cellules).toEqual(['131', '26', '19', '8', '9', '4'])
    // Le total n'est rendu QU'UNE fois : les deux axes décrivent les mêmes
    // avis, les additionner les compterait deux fois.
    expect(document.querySelectorAll('[data-veille-attribution-total]')).toHaveLength(1)
  })

  it('sans canal mesuré, le dit au lieu d’un tableau vide qui a l’air juste', async () => {
    mocks.sante.mockResolvedValue({ data: {} })
    renderScreen()

    await waitFor(() => {
      expect(document.querySelector('[data-veille-attribution-vide="source"]')).toBeTruthy()
    })
    expect(document.querySelector('[data-veille-attribution-vide="informateur"]')).toBeTruthy()
    expect(document.querySelector('[data-veille-attribution-total]')).toBeNull()
  })
})
