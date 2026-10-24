// AGNR19 — le lead et le client d'ARRIVÉE sont résolus PAR LEUR ID
// (`crmApi.getLead(id)`, `getClient(id)`), jamais cherchés dans une page de
// liste : `?lead=<plus ancien>` applique ce lead (factures comprises),
// `?client=<plus ancien>` le résout, un id inexistant est DIT.
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrArriveeParId.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, waitFor, fireEvent } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable } from './DevisGeneratorGoldenHarnais'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

// 60 enregistrements ; la LISTE ne sert que les 50 plus récents (page 1 d'un
// serveur qui ne pagine pas plus loin), le détail par id sert tout le monde.
const LEADS = Array.from({ length: 60 }, (_, k) => ({
  id: 60 - k, nom: `Lead${60 - k}`, prenom: '', societe: '',
  facture_hiver: 60 - k === 1 ? '1800' : null, ete_differente: false,
}))
const CLIENTS = Array.from({ length: 60 }, (_, k) => ({
  id: 60 - k, nom: `Client${60 - k}`, adresse: `Adresse ${60 - k}`, telephone: '',
}))
const parId = (items) => (id) => {
  const trouve = items.find((x) => String(x.id) === String(id))
  return trouve ? Promise.resolve({ data: trouve })
    : Promise.reject(Object.assign(new Error('404'), { response: { status: 404 } }))
}
const serveur = ({ crmApi }) => {
  crmApi.getLeads.mockResolvedValue({ data: LEADS.slice(0, 50) })
  crmApi.getClients.mockResolvedValue({ data: CLIENTS.slice(0, 50) })
  crmApi.getLead.mockImplementation(parId(LEADS))
  crmApi.getClient.mockImplementation(parId(CLIENTS))
}

cycleEcran({ date: DATE_FIGEE })

describe('AGNR19 — lead et client d’arrivée résolus par leur id', () => {
  it('?lead=<plus ancien> : lead affiché et factures appliquées', async () => {
    const vue = await monter('/ventes/devis/nouveau?lead=1', { avant: serveur })
    await waitFor(() => expect(vue.crmApi.getLead).toHaveBeenCalledWith('1'))
    await attendreStable(vue.container, act)
    expect(document.getElementById('gen-lead')?.textContent).toContain('Lead1')
    expect(document.getElementById('gen-hiver')?.value).toBe('1800')
  }, 60000)

  it('?lead=<id inexistant> : « Lead introuvable » au lieu d’un écran muet', async () => {
    const vue = await monter('/ventes/devis/nouveau?lead=999', { avant: serveur })
    await waitFor(() => expect(vue.crmApi.getLead).toHaveBeenCalledWith('999'))
    await attendreStable(vue.container, act)
    expect(document.body.textContent).toMatch(/Lead introuvable \(n° 999\)/)
  }, 60000)

  it('?client=<plus ancien> : client résolu (adresse affichée)', async () => {
    const vue = await monter('/ventes/devis/nouveau?client=1', { avant: serveur })
    await waitFor(() => expect(vue.crmApi.getClient).toHaveBeenCalledWith('1'))
    await attendreStable(vue.container, act)
    expect(document.getElementById('gen-adresse')?.value).toBe('Adresse 1')
  }, 60000)
})

// ADEV100 — un lead commercial ouvre le générateur PRÉ-REMPLI (valeurs éditables
// + badge de provenance LIBELLE_REPRIS_LEAD), sans rien écraser quand on rouvre un devis.
const LEAD_HOTEL = {
  id: 70, nom: 'Hotel70', prenom: '', societe: 'Hôtel Exemple', type_installation: 'commercial',
  categorie_commerciale: 'hotel', reponses_categorie: { chambres: 40, piscine: false },
  contrat_electricite: 'bt_patente', tension_raccordement: 'bt', raccordement: 'triphase',
  jours_ouverture: [1, 2, 3, 4, 5], heure_debut: 8, heure_fin: 18,
  type_surface: 'toiture', type_toiture: 'bac_acier', surface_toiture_m2: '650.00',
  conso_mensuelle_kwh: '6000.00', facture_hiver: null, ete_differente: false,
}

describe('ADEV100 — le générateur C&I est pré-rempli depuis le lead', () => {
  it('?lead=<commercial> : catégorie, réponses, contrat, phase, jours, heures, surface, kWh repris et éditables', async () => {
    const vue = await monter('/ventes/devis/nouveau?lead=70', {
      avant: ({ crmApi }) => {
        crmApi.getLeads.mockResolvedValue({ data: [LEAD_HOTEL] })
        crmApi.getLead.mockImplementation(parId([LEAD_HOTEL]))
        crmApi.getClients.mockResolvedValue({ data: [] })
      },
    })
    await attendreStable(vue.container, act)
    await waitFor(() => expect(document.querySelector('[data-testid="ci-repris-categorie"]')).not.toBeNull())
    for (const cle of ['contrat', 'phases', 'tension', 'joursOuverts', 'plages', 'surfaceUtile', 'typePose',
      'kwhAnnuel', 'reponses.chambres']) {
      expect(document.querySelector(`[data-testid="ci-repris-${cle}"]`), cle).not.toBeNull()
    }
    expect(document.getElementById('gen-ci-surface').value).toBe('650')
    expect(document.getElementById('gen-ci-kwh-annuel').value).toBe('72000')
    expect(document.getElementById('gen-tarif-contrat').value).toBe('bt_patente')
    expect(document.getElementById('gen-com-chambres').value).toBe('40')
    // éditable : une saisie retire le badge du champ
    const surface = document.getElementById('gen-ci-surface')
    expect(surface).not.toBeDisabled()
    fireEvent.change(surface, { target: { value: '700' } })
    await waitFor(() => expect(document.querySelector('[data-testid="ci-repris-surfaceUtile"]')).toBeNull())
    expect(document.getElementById('gen-ci-surface').value).toBe('700')
  }, 60000)
})
