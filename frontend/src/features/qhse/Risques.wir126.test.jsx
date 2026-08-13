import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR126 — les onglets de Risques.jsx (Permis & LOTO, Incidents en priorité)
   étaient lecture seule alors que le backend supporte création + cycle de vie
   testés (PermisTravail créer/valider/clôturer, ConsignationLoto créer/
   déconsigner, Incident créer — débloque la chaîne d'escalade déjà testée
   côté serveur, AnalyseIncident.genererCapa). On vérifie que chaque onglet
   prioritaire expose désormais ses actions d'écriture de bout en bout.
   Réseau mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (typeof Element.prototype.hasPointerCapture === 'undefined') {
    Element.prototype.hasPointerCapture = () => false
  }
  if (typeof Element.prototype.scrollIntoView === 'undefined') {
    Element.prototype.scrollIntoView = () => {}
  }
})

const {
  empty, permisCreate, permisValider, permisCloturer, lotoCreate,
  lotoDeconsigner, incidentCreate, genererCapa,
} = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  permisCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  permisValider: vi.fn(() => Promise.resolve({ data: {} })),
  permisCloturer: vi.fn(() => Promise.resolve({ data: {} })),
  lotoCreate: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
  lotoDeconsigner: vi.fn(() => Promise.resolve({ data: {} })),
  incidentCreate: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
  genererCapa: vi.fn(() => Promise.resolve({ data: {} })),
}))

const PERMIS_ROW = {
  id: 10, reference: 'PT-000010', titre: 'Soudure toiture', type_permis: 'point_chaud',
  type_permis_display: 'Point chaud', statut: 'brouillon', date_fin: null,
}
const LOTO_ROW = {
  id: 20, reference: 'LOTO-000020', equipement: 'TGBT chantier',
  point_consignation: 'Disjoncteur principal', statut: 'consignee',
}

vi.mock('../../api/qhseApi', () => ({
  default: {
    evaluationsRisque: { list: empty },
    risquesOpportunites: { list: empty, revuesDues: empty },
    permisTravail: {
      list: vi.fn(() => Promise.resolve({ data: [PERMIS_ROW] })),
      create: (...a) => permisCreate(...a),
      valider: (...a) => permisValider(...a),
      cloturer: (...a) => permisCloturer(...a),
    },
    consignationsLoto: {
      list: vi.fn(() => Promise.resolve({ data: [LOTO_ROW] })),
      create: (...a) => lotoCreate(...a),
      deconsigner: (...a) => lotoDeconsigner(...a),
    },
    inductionsSecurite: { list: empty },
    plansUrgence: { list: empty },
    secouristes: { list: empty },
    exercicesUrgence: { list: empty },
    incidents: {
      list: empty,
      create: (...a) => incidentCreate(...a),
    },
    declarationsCnss: { list: empty },
    analysesIncident: {
      list: vi.fn(() => Promise.resolve({
        data: [{ id: 30, incident_reference: 'INC-000030', methode_display: '5 pourquoi', nb_causes: 1, nb_capa: 0, statut_display: 'Ouverte' }],
      })),
      genererCapa: (...a) => genererCapa(...a),
    },
    observationsSecurite: { list: empty },
    liensSignalement: { list: empty },
    signalementsPublics: { list: empty },
  },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

import Risques from './Risques'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

beforeEach(() => { vi.clearAllMocks() })

describe('Risques — Permis & LOTO (WIR126)', () => {
  it('propose de créer un permis de travail et l\'envoie au serveur', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Permis & LOTO' }))

    // DataTable rend à la fois la table desktop et le repli carte mobile
    // (CSS seul, `dt-desktop:hidden` — les deux existent dans le DOM en
    // jsdom) : getAllByText, même patron que qhse.render.test.jsx.
    await waitFor(() => expect(screen.getAllByText('Soudure toiture').length).toBeGreaterThan(0))
    await user.click(screen.getByRole('button', { name: /Nouveau permis/ }))

    await user.type(screen.getByLabelText('Titre'), 'Travail en hauteur toiture')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(permisCreate).toHaveBeenCalledWith(
      expect.objectContaining({ titre: 'Travail en hauteur toiture', type_permis: 'hauteur' }),
    ))
  })

  it('un permis brouillon peut être validé puis clôturé', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Permis & LOTO' }))
    await waitFor(() => expect(screen.getAllByText('Soudure toiture').length).toBeGreaterThan(0))

    // RowActions rend le bouton à la fois côté table desktop et carte
    // mobile (même patron que le texte de ligne ci-dessus) : premier match.
    await user.click(screen.getAllByRole('button', { name: 'Valider' })[0])
    await waitFor(() => expect(permisValider).toHaveBeenCalledWith(10))

    await user.click(screen.getAllByRole('button', { name: 'Clôturer' })[0])
    await waitFor(() => expect(permisCloturer).toHaveBeenCalledWith(10))
  })

  it('propose de créer une consignation LOTO rattachée à un permis', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Permis & LOTO' }))
    await waitFor(() => expect(screen.getAllByText('TGBT chantier').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Nouvelle consignation/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Équipement'), 'Armoire électrique')
    await user.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(lotoCreate).toHaveBeenCalledWith(
      expect.objectContaining({ permis: 10, equipement: 'Armoire électrique' }),
    ))
  })

  it('une consignation consignée peut être déconsignée', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Permis & LOTO' }))
    await waitFor(() => expect(screen.getAllByText('TGBT chantier').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Déconsigner' })[0])
    await waitFor(() => expect(lotoDeconsigner).toHaveBeenCalledWith(20))
  })
})

describe('Risques — Incidents (WIR126)', () => {
  it('propose de déclarer un incident et l\'envoie au serveur (débloque l\'escalade)', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Incidents' }))

    await user.click(await screen.findByRole('button', { name: /Déclarer un incident/ }))
    await user.type(screen.getByLabelText('Titre'), 'Chute d\'objet')
    await user.click(screen.getByRole('button', { name: 'Déclarer' }))

    await waitFor(() => expect(incidentCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        titre: 'Chute d\'objet', type_incident: 'incident', gravite: 'mineure',
      }),
    ))
  })

  it('une analyse d\'incident peut générer une CAPA', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Incidents' }))
    await waitFor(() => expect(screen.getAllByText('INC-000030').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Générer CAPA' })[0])
    await waitFor(() => expect(genererCapa).toHaveBeenCalledWith(30))
  })
})
