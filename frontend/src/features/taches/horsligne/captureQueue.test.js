import { createElement as h } from 'react'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { memoryStore } from '../../../lib/offlineOutbox'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/tachesApi', async (original) => ({
  ...(await original()),
  saisieRapide: vi.fn(),
  terminerTache: vi.fn(),
  planifierTache: vi.fn(),
}))

const api = await import('../../../api/tachesApi')
const {
  abandonner, brancherRejeu, creerFile, definirCompteFile, enfilerAjout, enfilerCoche, enfilerPhrase, enfilerReport, etatFile,
  garderLaMienne, prendreLAutre, remplacerFile, rejouerFile,
} = await import('./captureQueue')
const { default: CoquilleTaches } = await import('../coquille/CoquilleTaches')
const { reinitialiserGestes } = await import('../lib/gestes')
const { derniereSynchro, ecrireJournee, lireJournee, viderCache, viderCacheALaDeconnexion, cleCache } = await import('./cacheJournee')

/* TCH100 — la file d'envoi hors ligne : 3 ops (ajouter, cocher, reporter) rejouées après `online` ; l'op d'un autre
   compte est jetée (donnees.md inv. 31) ; un 409 `conflit_version` reste en file et se règle (Garder la mienne /
   Prendre l'autre) ; une coupure en plein rejeu laisse la file intacte ; file et cache sont vidés à la déconnexion. */

const LIGNE = { index: 0, collage: 0, client_id: 'c1:0', titre: 'Appeler Karim', jour_prevu: '2026-11-18' }
const REPORT = { jour_prevu: '2026-11-19', moment: '', heure_debut: null, quelque_jour: false, lock_version: 3 }
const erreurHttp = (status, data) => ({ response: { status, data } })

let file
function enLigne(valeur) {
  Object.defineProperty(window.navigator, 'onLine', { value: valeur, configurable: true })
}

beforeEach(() => {
  file = creerFile({ store: memoryStore() })
  remplacerFile(file)
  definirCompteFile(7, 1)
  enLigne(true)
  api.saisieRapide.mockResolvedValue({ data: {} })
  api.terminerTache.mockResolvedValue({ data: {} })
  api.planifierTache.mockReset()
  api.planifierTache.mockResolvedValue({ data: {} })
  window.localStorage.clear()
})
afterEach(() => { vi.clearAllMocks(); remplacerFile(null); definirCompteFile(null); window.localStorage.clear() })

async function mettreTroisOpsHorsLigne() {
  enLigne(false)
  await enfilerAjout([LIGNE])
  await enfilerCoche(41)
  await enfilerReport(42, REPORT)
  expect(await file.count()).toBe(3)
}

describe('TCH100 — file d\'envoi : rejeu au retour du réseau', () => {
  it('3 ops mises en file hors ligne sont rejouées dans l\'ordre après `online`, avec le propriétaire attendu', async () => {
    const retirer = brancherRejeu({ f: file })
    await mettreTroisOpsHorsLigne()
    expect(api.saisieRapide).not.toHaveBeenCalled()

    enLigne(true)
    window.dispatchEvent(new Event('online'))
    await vi.waitFor(async () => expect(await file.count()).toBe(0))
    retirer()

    expect(await file.pending()).toEqual([])
    expect(api.saisieRapide).toHaveBeenCalledWith(
      { lignes: [LIGNE], apercu: false },
      { proprietaire: 7, cle: expect.any(String) },
    )
    expect(api.terminerTache).toHaveBeenCalledWith(41, {}, { proprietaire: 7 })
    expect(api.planifierTache).toHaveBeenCalledWith(42, REPORT, { proprietaire: 7 })
    expect(api.saisieRapide.mock.invocationCallOrder[0]).toBeLessThan(api.terminerTache.mock.invocationCallOrder[0])
    expect(api.terminerTache.mock.invocationCallOrder[0]).toBeLessThan(api.planifierTache.mock.invocationCallOrder[0])
  })

  it('l\'Idempotency-Key du rejeu d\'un ajout est le client_op_id de l\'op (rejeu sans doublon)', async () => {
    const id = await enfilerAjout([LIGNE])
    await rejouerFile(file)
    expect(api.saisieRapide.mock.calls[0][1].cle).toBe(id)
  })

  it('hors ligne ou sans compte, rien n\'est rejoué et la file reste', async () => {
    await enfilerCoche(41)
    enLigne(false)
    expect(await rejouerFile(file)).toBeNull()
    enLigne(true)
    definirCompteFile(null)
    expect(await rejouerFile(file)).toBeNull()
    expect(api.terminerTache).not.toHaveBeenCalled()
    expect(await file.count()).toBe(1)
  })

  it('une coupure en plein rejeu laisse la file intacte, sans rien marquer en erreur', async () => {
    await mettreTroisOpsHorsLigne()
    enLigne(true)
    api.planifierTache.mockRejectedValue(new Error('Network Error'))
    await rejouerFile(file)
    const restantes = await file.pending()
    expect(restantes).toHaveLength(3)
    expect(restantes.some((op) => op.serverError)).toBe(false)
    // le réseau revient : le rejeu aboutit, les envois déjà passés repartent avec la même clé
    api.planifierTache.mockResolvedValue({ data: {} })
    await rejouerFile(file)
    expect(await file.count()).toBe(0)
  })
})

describe('R2-008a — hors ligne, la PHRASE part en file : le serveur la lit au rejeu', () => {
  const lue = (titre, champs) => ({ data: { projets_communs: [], projets_nouveaux: [], lignes: [{
    ...exempleContrat('taches', 'saisie_apercu').lignes[0], index: 0, collage: 0, titre, jetons: [], alertes: [], champs,
  }] } })
  const creations = () => api.saisieRapide.mock.calls.filter(([c]) => c.apercu === false)

  it('« Test ce soir » hors ligne → au retour : aperçu de la phrase puis création de « Test » ce soir, une seule fois', async () => {
    api.saisieRapide.mockImplementation((corps) => Promise.resolve(corps.apercu
      ? lue('Test', { priorite: 0, jour_prevu: '2026-11-17', moment: 'soir' }) : { data: {} }))
    enLigne(false)
    const id = await enfilerPhrase({ textes: ['Test ce soir'], cid: 'k1', contexte: { projetId: 3, sectionId: 8 } })
    enLigne(true)
    await rejouerFile(file)
    expect(api.saisieRapide).toHaveBeenNthCalledWith(1, { texte: 'Test ce soir', ignorer: [], apercu: true }, { proprietaire: 7, cle: null })
    expect(creations()).toHaveLength(1)
    const [corps, options] = creations()[0]
    expect(corps.lignes).toEqual([expect.objectContaining({
      client_id: 'k1:0', titre: 'Test', jour_prevu: '2026-11-17', moment: 'soir', projet_id: 3, section_id: 8,
    })])
    expect(options).toEqual({ proprietaire: 7, cle: id })
    expect(await file.count()).toBe(0)
    // un second rejeu ne recrée rien : la file est vide
    await rejouerFile(file)
    expect(creations()).toHaveLength(1)
  })

  it('le jour de DÉPART de l\'écran cède à la date lue ; un Quand choisi à la main l\'emporte', async () => {
    api.saisieRapide.mockImplementation((corps) => Promise.resolve(corps.apercu
      ? lue('Appeler', { priorite: 0, jour_prevu: '2026-11-18' }) : { data: {} }))
    await enfilerPhrase({ textes: ['Appeler demain'], cid: 'k2', quandDefaut: { jour_prevu: '2026-11-17', moment: '', heure_debut: null, quelque_jour: false } })
    await enfilerPhrase({ textes: ['Appeler demain'], cid: 'k3', quand: { jour_prevu: null, moment: '', heure_debut: null, quelque_jour: true } })
    await rejouerFile(file)
    expect(creations().map(([c]) => [c.lignes[0].jour_prevu, Boolean(c.lignes[0].quelque_jour)]))
      .toEqual([['2026-11-18', false], [null, true]])
  })

  it('une coupure pendant l\'aperçu du rejeu laisse la phrase en file ; rien n\'est créé', async () => {
    api.saisieRapide.mockRejectedValue(new Error('Network Error'))
    await enfilerPhrase({ textes: ['Test ce soir'], cid: 'k4' })
    await rejouerFile(file)
    expect(creations()).toHaveLength(0)
    const [op] = await file.pending()
    expect(op.serverError ?? null).toBeNull()
  })

  it('une op ANCIENNE (format `lignes`, déjà en file sur un appareil) se rejoue toujours telle quelle', async () => {
    await file.enqueue('ajouter', { type: 'ajouter', corps: { lignes: [LIGNE] }, userId: 7, companyId: 1 }, { queuedAt: '2026-11-16T10:00:00Z' })
    await rejouerFile(file)
    expect(api.saisieRapide).toHaveBeenCalledTimes(1)
    expect(api.saisieRapide).toHaveBeenCalledWith({ lignes: [LIGNE], apercu: false }, { proprietaire: 7, cle: expect.any(String) })
    expect(await file.count()).toBe(0)
  })
})

describe('TCH100 — file d\'envoi : autre compte (invariant 31)', () => {
  it('une op faite par le compte 7 n\'est JAMAIS envoyée quand le compte courant est le 8 : jetée', async () => {
    await enfilerCoche(41)
    definirCompteFile(8, 1)
    const surJetees = vi.fn()
    const retirer = brancherRejeu({ surJetees, f: file })
    window.dispatchEvent(new Event('online'))
    await vi.waitFor(() => expect(surJetees).toHaveBeenCalledWith(1))
    retirer()
    expect(api.terminerTache).not.toHaveBeenCalled()
    expect(await file.count()).toBe(0)
  })

  it('un 409 `autre_compte` du serveur jette l\'op, sans la marquer en erreur', async () => {
    await enfilerCoche(41)
    api.terminerTache.mockRejectedValue(erreurHttp(409, { detail: 'Autre compte.', code: 'autre_compte' }))
    const res = await rejouerFile(file)
    expect(res.jetees).toHaveLength(1)
    expect(await file.count()).toBe(0)
  })
})

describe('TCH100 — file d\'envoi : conflit entre appareils', () => {
  const actuel = exempleContrat('taches', 'tache')

  beforeEach(() => {
    api.planifierTache.mockRejectedValueOnce(erreurHttp(409, {
      detail: 'Cet enregistrement a été modifié par quelqu\'un d\'autre depuis son ouverture.',
      code: 'conflit_version', lock_version: 5, actuel,
    }))
  })

  it('un 409 `conflit_version` garde l\'op en file et rend le conflit à l\'écran (jamais écrasé)', async () => {
    await enfilerReport(42, REPORT)
    await rejouerFile(file)
    const etat = await etatFile(file)
    expect(etat.conflits).toEqual([expect.objectContaining({ lockVersion: 5, actuel })])
    expect(etat.refusees).toEqual([])
    expect(await file.count()).toBe(1)
  })

  it('« Garder la mienne » renvoie la même action avec le lock_version de l\'autre appareil', async () => {
    await enfilerReport(42, REPORT)
    await rejouerFile(file)
    const [{ opId }] = (await etatFile(file)).conflits
    await garderLaMienne(opId, file)
    await rejouerFile(file)
    expect(api.planifierTache).toHaveBeenLastCalledWith(42, { ...REPORT, lock_version: 5 }, { proprietaire: 7 })
    expect(await file.count()).toBe(0)
  })

  it('« Prendre l\'autre » retire l\'op et rend l\'état `actuel` de l\'autre appareil', async () => {
    await enfilerReport(42, REPORT)
    await rejouerFile(file)
    const [{ opId }] = (await etatFile(file)).conflits
    expect(await prendreLAutre(opId, file)).toEqual(actuel)
    expect(await file.count()).toBe(0)
    expect(api.planifierTache).toHaveBeenCalledTimes(1)
  })

  it('un refus 400 reste en file, marqué avec son message, jusqu\'à un abandon explicite', async () => {
    api.terminerTache.mockRejectedValue(erreurHttp(400, { detail: 'Tâche annulée.' }))
    const id = await enfilerCoche(41)
    await rejouerFile(file)
    const [op] = await file.pending()
    expect(op.serverError).toBe('Tâche annulée.')
    expect((await etatFile(file)).refusees).toHaveLength(1)
    await abandonner(id, file)
    expect(await file.count()).toBe(0)
  })
})

describe('TCH100 — cache par compte et par jour, vidé à la déconnexion', () => {
  const MAINTENANT = new Date('2026-11-17T15:02:00')

  it('une journée par compte : un autre jour remplace le précédent, un autre compte n\'est jamais lu', () => {
    expect(ecrireJournee(7, '2026-11-16', { a: 1 }, MAINTENANT)).toBe(true)
    expect(ecrireJournee(7, '2026-11-17', { a: 2 }, MAINTENANT)).toBe(true)
    expect(ecrireJournee(8, '2026-11-17', { a: 3 }, MAINTENANT)).toBe(true)
    expect(lireJournee(7, '2026-11-16')).toBeNull()
    expect(lireJournee(7, '2026-11-17').donnees).toEqual({ a: 2 })
    expect(lireJournee(8, '2026-11-17').donnees).toEqual({ a: 3 })
    expect(window.localStorage.getItem(cleCache(7, '2026-11-17'))).not.toBeNull()
  })

  it('« dernière synchro » est l\'heure de la dernière lecture gardée pour CE compte', () => {
    expect(derniereSynchro(7)).toBeNull()
    ecrireJournee(7, '2026-11-17', {}, MAINTENANT)
    expect(derniereSynchro(7)).toBe('15:02')
    expect(derniereSynchro(8)).toBeNull()
  })

  it('`taqinor:auth-logout` vide le cache et la file', async () => {
    ecrireJournee(7, '2026-11-17', {}, MAINTENANT)
    await enfilerCoche(41)
    const retirerCache = viderCacheALaDeconnexion()
    const retirer = brancherRejeu({ f: file })
    window.dispatchEvent(new Event('taqinor:auth-logout'))
    await vi.waitFor(async () => expect(await file.count()).toBe(0))
    expect(lireJournee(7, '2026-11-17')).toBeNull()
    retirer()
    retirerCache()
  })

  it('le stockage refusé ne casse rien : on lit « rien »', () => {
    const espion = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('plein') })
    expect(ecrireJournee(7, '2026-11-17', {}, MAINTENANT)).toBe(false)
    espion.mockRestore()
    expect(viderCache()).toBe(0)
  })
})

describe('TCH100 — dans la coquille', () => {
  const magasin = { getState: () => ({ auth: { user: { id: 7, active_company_id: 1 } } }), subscribe: () => () => {}, dispatch: () => {} }
  const monter = (enfants = null) => render(
    h(Provider, { store: magasin },
      h(MemoryRouter, { initialEntries: ['/taches/aujourdhui'] },
        h(CoquilleTaches, { ecran: 'aujourdhui', titre: "Aujourd'hui" }, enfants))),
  )
  beforeEach(() => { reinitialiserGestes() })
  afterEach(() => { reinitialiserGestes() })

  it('hors ligne : « Hors ligne · dernière synchro à 15:02 » (heure du cache du compte) et « En attente d\'envoi (2) »', async () => {
    ecrireJournee(7, '2026-11-17', {}, new Date('2026-11-17T15:02:00'))
    enLigne(false)
    await enfilerCoche(41)
    await enfilerReport(42, REPORT)
    monter()
    expect(await screen.findByText(/Hors ligne · dernière synchro à 15:02/)).toBeInTheDocument()
    expect(await screen.findByText("En attente d'envoi (2)")).toBeInTheDocument()
    expect(api.terminerTache).not.toHaveBeenCalled()
  })

  it('en ligne, la file se rejoue à l\'ouverture de l\'écran et le compteur disparaît', async () => {
    await enfilerCoche(41)
    monter()
    await vi.waitFor(() => expect(api.terminerTache).toHaveBeenCalledWith(41, {}, { proprietaire: 7 }))
    await vi.waitFor(() => expect(screen.queryByText(/En attente d'envoi/)).toBeNull())
  })

  it('hors ligne, un geste marqué `data-necessite-reseau` est grisé : rien ne part, « Possible une fois connecté »', async () => {
    const geste = vi.fn()
    enLigne(false)
    const { unmount } = monter(h('button', { type: 'button', 'data-necessite-reseau': '', onClick: geste }, 'Étiqueter'))
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Étiqueter' }))
    expect(geste).not.toHaveBeenCalled()
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Possible une fois connecté')
    unmount()

    enLigne(true)
    monter(h('button', { type: 'button', 'data-necessite-reseau': '', onClick: geste }, 'Étiqueter'))
    await user.click(screen.getByRole('button', { name: 'Étiqueter' }))
    expect(geste).toHaveBeenCalledTimes(1)
  })

  it('un conflit d\'une op en file se règle par le bandeau : « Garder la mienne » renvoie avec la version de l\'autre', async () => {
    api.planifierTache.mockRejectedValueOnce(erreurHttp(409, {
      detail: 'Modifiée.', code: 'conflit_version', lock_version: 5, actuel: exempleContrat('taches', 'tache'),
    }))
    await enfilerReport(42, REPORT)
    monter()
    const bandeau = await screen.findByRole('group', { name: 'Conflit entre appareils' })
    expect(bandeau).toHaveTextContent('Modifiée sur ton autre appareil à 10:42')
    await userEvent.setup().click(within(bandeau).getByRole('button', { name: 'Garder la mienne' }))
    await vi.waitFor(() => expect(api.planifierTache).toHaveBeenLastCalledWith(42, { ...REPORT, lock_version: 5 }, { proprietaire: 7 }))
    await vi.waitFor(() => expect(screen.queryByRole('group', { name: 'Conflit entre appareils' })).toBeNull())
  })
})
