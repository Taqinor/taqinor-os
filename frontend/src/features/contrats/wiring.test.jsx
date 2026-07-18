import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useParams } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* Tests de câblage du module Contrats (CONTRAT12-17 + XCTR17-21) : on vérifie
   que la fiche contrat expose bien les onglets Signatures / Approbation + la
   barre d'actions gardée (statuts-suivants → changer-statut), et que le module
   Location liste les ordres et déclenche la création. Les appels API sont
   mockés — hors réseau. jsdom ne fournit pas ResizeObserver. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const {
  changerStatut, signer, createOrdreLocation,
  createContrat, createModele, createClause,
} = vi.hoisted(() => ({
  changerStatut: vi.fn(() => Promise.resolve({ data: {} })),
  signer: vi.fn(() => Promise.resolve({ data: { contrat_signe: false } })),
  createOrdreLocation: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  // WIR9 — création directe d'un contrat/modèle/clause (société neuve, 0
  // ModeleContrat).
  createContrat: vi.fn(() => Promise.resolve({ data: { id: 42 } })),
  createModele: vi.fn(() => Promise.resolve({
    data: { id: 5, nom: 'O&M Standard', categorie: '', type_contrat_defaut: 'om', actif: true },
  })),
  createClause: vi.fn(() => Promise.resolve({
    data: { id: 9, titre: 'Confidentialité générale', type_clause: 'confidentialite', categorie: '', actif: true },
  })),
}))

vi.mock('../../api/contratsApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  const contrat = {
    id: 7, reference: 'CT-2026-07-0001', objet: 'Maintenance PV', statut: 'brouillon',
    type_contrat: 'maintenance', confidentialite: 'interne', montant: '12000.00', devise: 'MAD',
  }
  return {
    default: {
      getContrat: () => Promise.resolve({ data: contrat }),
      // WIR9 — ContratsList (une société neuve : un seul contrat déjà présent
      // pour ne pas dupliquer le bouton « Nouveau contrat » — voir le vide de
      // ListShell — l'assertion porte sur la CRÉATION, pas la liste vide).
      getContrats: () => Promise.resolve({ data: [contrat] }),
      createContrat,
      getParties: empty,
      getLiens: () => Promise.resolve({ data: [] }),
      getVersions: empty,
      getAvenants: empty,
      getResiliations: empty,
      // WIR9 — ModelesPage (bibliothèque partagée modèles/clauses).
      getModeles: empty,
      createModele,
      getClauses: empty,
      createClause,
      getHistorique: () => Promise.resolve({ data: [] }),
      getSignatures: () => Promise.resolve({ data: [] }),
      getEtapesApprobation: () => Promise.resolve({ data: [] }),
      getStatutsSuivants: () => Promise.resolve({ data: { statut: 'brouillon', suivants: ['en_approbation'] } }),
      changerStatut,
      signer,
      noter: () => Promise.resolve({ data: {} }),
      getPdf: () => Promise.resolve({ data: new Blob() }),
      lancerApprobation: empty,
      approuverEtape: () => Promise.resolve({ data: {} }),
      rejeterEtape: () => Promise.resolve({ data: {} }),
      renouveler: () => Promise.resolve({ data: {} }),
      creerAvenant: () => Promise.resolve({ data: {} }),
      resilier: () => Promise.resolve({ data: {} }),
      // Location
      getOrdresLocation: empty,
      ordresLocationEnRetard: empty,
      changerStatutOrdreLocation: () => Promise.resolve({ data: {} }),
      createOrdreLocation,
      cautionEncaisser: () => Promise.resolve({ data: {} }),
      cautionRestituer: () => Promise.resolve({ data: {} }),
      cautionRetenir: () => Promise.resolve({ data: {} }),
      cloturerOrdreLocation: () => Promise.resolve({ data: {} }),
      inspecterOrdreLocation: () => Promise.resolve({ data: {} }),
      getBonEnlevement: () => Promise.resolve({ data: new Blob() }),
      getBonRestitution: () => Promise.resolve({ data: new Blob() }),
    },
    contratsPortailApi: {
      mesContrats: empty,
      demander: () => Promise.resolve({ data: {} }),
    },
  }
})

vi.mock('../../api/stockApi', () => ({
  default: { getProduits: () => Promise.resolve({ data: [] }) },
}))
vi.mock('../../api/crmApi', () => ({
  default: { getClients: () => Promise.resolve({ data: [] }) },
}))

import ContratDetail from './ContratDetail'
import ContratsList from './ContratsList'
import ModelesPage from './ModelesPage'
import LocationPage from './LocationPage'
import { StatutLocation, StatutCautionLocation } from './locationStatus'

// WIR9 — stub minimal de la fiche contrat, juste pour prouver que la
// création depuis la liste navigue bien vers `/contrats/:id`.
function FicheStub() {
  const { id } = useParams()
  return <p>Fiche contrat #{id}</p>
}

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui, { path = '/contrats/7', route = '/contrats/:id' } = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ThemeProvider>
        <Routes>
          <Route path={route} element={ui} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ContratDetail — actions du cycle de vie (CONTRAT12-17)', () => {
  it('rend les onglets Signatures et Approbation', async () => {
    withProviders(<ContratDetail />)
    await waitFor(() => expect(screen.getByText('CT-2026-07-0001')).toBeInTheDocument())
    expect(screen.getByRole('tab', { name: /Signatures/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Approbation/ })).toBeInTheDocument()
  })

  it('propose une transition gardée depuis statuts-suivants et l’applique', async () => {
    withProviders(<ContratDetail />)
    await waitFor(() => expect(screen.getByText('CT-2026-07-0001')).toBeInTheDocument())
    const btn = await screen.findByRole('button', { name: /En approbation/ })
    fireEvent.click(btn)
    await waitFor(() => expect(changerStatut).toHaveBeenCalledWith('7', 'en_approbation'))
  })
})

describe('LocationPage — module de location (XCTR17)', () => {
  it('affiche le titre et le bouton de création', async () => {
    render(
      <MemoryRouter>
        <ThemeProvider><LocationPage /></ThemeProvider>
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('Location de matériel')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Nouvel ordre/ })).toBeInTheDocument()
  })
})

describe('Pastilles de statut de location', () => {
  it('mappe les statuts locaux de l’ordre et de la caution', () => {
    expect(StatutLocation.toneOf('reservee')).toBe('info')
    expect(StatutLocation.toneOf('enlevee')).toBe('success')
    expect(StatutLocation.toneOf('cloturee')).toBe('neutral')
    expect(StatutCautionLocation.toneOf('encaissee')).toBe('success')
    expect(StatutCautionLocation.toneOf('retenue_partielle')).toBe('warning')
  })
})

// WIR9 — une société neuve (0 ModeleContrat) doit pouvoir créer son premier
// contrat de bout en bout depuis l'UI : ni « Nouveau contrat » (ContratsList)
// ni « Nouveau modèle »/« Nouvelle clause » (ModelesPage) n'avaient de
// formulaire réel avant ce correctif (le clic renvoyait vers une bibliothèque
// vide ou un toast « à venir »).
describe('ContratsList — création directe d’un contrat (WIR9)', () => {
  it('crée un contrat depuis la liste puis ouvre sa fiche', async () => {
    render(
      <MemoryRouter initialEntries={['/contrats']}>
        <ThemeProvider>
          <Routes>
            <Route path="/contrats" element={<ContratsList />} />
            <Route path="/contrats/:id" element={<FicheStub />} />
          </Routes>
        </ThemeProvider>
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('Contrats')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Nouveau contrat/ }))
    // Label.required ajoute un « * » non décoratif (aria-hidden) — matcher
    // en préfixe pour rester robuste à sa présence.
    fireEvent.change(await screen.findByLabelText(/^Objet/), {
      target: { value: 'Maintenance annuelle onduleurs' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le contrat' }))

    await waitFor(() => expect(createContrat).toHaveBeenCalledWith({
      objet: 'Maintenance annuelle onduleurs', type_contrat: 'vente',
    }))
    await waitFor(() => expect(screen.getByText('Fiche contrat #42')).toBeInTheDocument())
  })
})

describe('ModelesPage — création directe modèle/clause (WIR9)', () => {
  it('crée un modèle de contrat depuis la bibliothèque vide', async () => {
    render(
      <MemoryRouter>
        <ThemeProvider><ModelesPage /></ThemeProvider>
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('Modèles (0)')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Nouveau modèle/ }))
    fireEvent.change(await screen.findByLabelText(/^Nom du modèle/), {
      target: { value: 'O&M Standard' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le modèle' }))

    await waitFor(() => expect(createModele).toHaveBeenCalledWith({
      nom: 'O&M Standard', type_contrat_defaut: 'vente',
    }))
    await waitFor(() => expect(screen.getByText('Modèles (1)')).toBeInTheDocument())
    expect(screen.getByText('O&M Standard')).toBeInTheDocument()
  })

  it('crée une clause réutilisable depuis la bibliothèque vide', async () => {
    render(
      <MemoryRouter>
        <ThemeProvider><ModelesPage /></ThemeProvider>
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('Modèles (0)')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('tab', { name: /Clauses/ }))

    fireEvent.click(await screen.findByRole('button', { name: /Nouvelle clause/ }))
    fireEvent.change(await screen.findByLabelText(/^Titre/), {
      target: { value: 'Confidentialité générale' },
    })
    fireEvent.change(screen.getByLabelText(/^Corps de la clause/), {
      target: { value: 'Les parties s’engagent à…' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Créer la clause' }))

    await waitFor(() => expect(createClause).toHaveBeenCalledWith({
      titre: 'Confidentialité générale', type_clause: 'generale',
      corps: 'Les parties s’engagent à…',
    }))
    await waitFor(() => expect(screen.getByText('Clauses (1)')).toBeInTheDocument())
    expect(screen.getByText('Confidentialité générale')).toBeInTheDocument()
  })
})
