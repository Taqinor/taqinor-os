import { describe, it, expect, afterEach } from 'vitest'
import {
  lireCookie, estUuidPlausible, cleEnregistrement, doitEnregistrer,
  enregistrerNavigateurEquipe, CLE_APPAREIL_ERP,
} from './appareilEquipe'

/* QJ-EQUIPE-3 — voir le commentaire d'en-tête de appareilEquipe.js pour le
   contexte. Les fonctions pures sont testées isolément ; l'effet
   (`enregistrerNavigateurEquipe`) reçoit un `api`/`storage` INJECTÉS (jamais
   de vi.mock du module crmApi) — exactement pour permettre ces tests sans
   toucher au réseau réel. */

function fakeStorage(initial = {}) {
  const store = { ...initial }
  return {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = v },
  }
}

describe('lireCookie', () => {
  it('lit un cookie présent parmi plusieurs', () => {
    expect(lireCookie('tq_appareil', 'a=1; tq_appareil=abc-123; autre=xyz')).toBe('abc-123')
  })

  it("renvoie '' si le cookie est absent", () => {
    expect(lireCookie('tq_appareil', 'a=1; autre=xyz')).toBe('')
  })

  it("renvoie '' sur une source vide", () => {
    expect(lireCookie('tq_appareil', '')).toBe('')
  })
})

describe('estUuidPlausible', () => {
  it('accepte un UUID valide, insensible à la casse', () => {
    expect(estUuidPlausible('550e8400-e29b-41d4-a716-446655440000')).toBe(true)
    expect(estUuidPlausible('550E8400-E29B-41D4-A716-446655440000')).toBe(true)
  })

  it('rejette une valeur qui ne ressemble pas à un UUID', () => {
    expect(estUuidPlausible('')).toBe(false)
    expect(estUuidPlausible('pas-un-uuid')).toBe(false)
    expect(estUuidPlausible(undefined)).toBe(false)
    expect(estUuidPlausible(123)).toBe(false)
  })
})

describe('doitEnregistrer', () => {
  it('vrai si jamais enregistré (absent)', () => {
    expect(doitEnregistrer(null)).toBe(true)
    expect(doitEnregistrer(undefined)).toBe(true)
    expect(doitEnregistrer('')).toBe(true)
  })

  it('vrai si la date stockée est illisible', () => {
    expect(doitEnregistrer('pas-une-date')).toBe(true)
  })

  it('faux si le dernier enregistrement a moins de 24 h', () => {
    const dernier = '2026-09-16T10:00:00Z'
    const maintenant = new Date('2026-09-16T20:00:00Z')
    expect(doitEnregistrer(dernier, maintenant)).toBe(false)
  })

  it('vrai si le dernier enregistrement a plus de 24 h', () => {
    const dernier = '2026-09-14T10:00:00Z'
    const maintenant = new Date('2026-09-16T10:00:01Z')
    expect(doitEnregistrer(dernier, maintenant)).toBe(true)
  })
})

describe('enregistrerNavigateurEquipe (effet best-effort)', () => {
  afterEach(() => {
    // Nettoie tout cookie posé par un test précédent (jsdom garde le même
    // document entre les tests d'un même fichier).
    document.cookie = 'tq_appareil=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/'
  })

  it('ne fait rien sans utilisateur connecté (pas d’appel API)', async () => {
    const api = { enregistrerNavigateurEquipe: () => Promise.resolve({ data: {} }) }
    let appels = 0
    const compte = { enregistrerNavigateurEquipe: (...args) => { appels += 1; return api.enregistrerNavigateurEquipe(...args) } }
    await enregistrerNavigateurEquipe(null, { api: compte, storage: fakeStorage() })
    await enregistrerNavigateurEquipe(undefined, { api: compte, storage: fakeStorage() })
    await enregistrerNavigateurEquipe({}, { api: compte, storage: fakeStorage() })
    expect(appels).toBe(0)
  })

  it('appelle l’API une fois, puis plus dans les 24 h, puis de nouveau après 24 h', async () => {
    let appels = 0
    const api = { enregistrerNavigateurEquipe: () => { appels += 1; return Promise.resolve({ data: {} }) } }
    const storage = fakeStorage()
    const user = { id: 42 }
    const t0 = new Date('2026-09-16T10:00:00Z')

    await enregistrerNavigateurEquipe(user, { api, storage, maintenant: t0 })
    expect(appels).toBe(1)

    // Rappel immédiat (même utilisateur, même poste) : pas de second appel.
    await enregistrerNavigateurEquipe(user, { api, storage, maintenant: t0 })
    expect(appels).toBe(1)

    // 25 h plus tard : la fenêtre de 24 h est dépassée, nouvel appel.
    const t1 = new Date(t0.getTime() + 25 * 60 * 60 * 1000)
    await enregistrerNavigateurEquipe(user, { api, storage, maintenant: t1 })
    expect(appels).toBe(2)
  })

  it('renvoie le cookie appareil existant (uuid) plutôt que d’en inventer un', async () => {
    const uuid = '11111111-1111-1111-1111-111111111111'
    document.cookie = `tq_appareil=${uuid}`
    let recu = null
    const api = { enregistrerNavigateurEquipe: (data) => { recu = data; return Promise.resolve({ data: {} }) } }
    await enregistrerNavigateurEquipe({ id: 7 }, { api, storage: fakeStorage() })
    expect(recu.appareil_id).toBe(uuid)
  })

  it('envoie appareil_id vide quand le cookie existant n’est pas un uuid plausible', async () => {
    document.cookie = 'tq_appareil=pas-un-uuid'
    let recu = null
    const api = { enregistrerNavigateurEquipe: (data) => { recu = data; return Promise.resolve({ data: {} }) } }
    await enregistrerNavigateurEquipe({ id: 8 }, { api, storage: fakeStorage() })
    expect(recu.appareil_id).toBe('')
  })

  it('sans cookie, renvoie l’identifiant attribué la dernière fois par le serveur (localStorage)', async () => {
    const uuid = '22222222-2222-4222-8222-222222222222'
    let recu = null
    const api = { enregistrerNavigateurEquipe: (data) => { recu = data; return Promise.resolve({ data: {} }) } }
    await enregistrerNavigateurEquipe({ id: 10 }, { api, storage: fakeStorage({ [CLE_APPAREIL_ERP]: uuid }) })
    expect(recu.appareil_id).toBe(uuid)
  })

  it('mémorise l’identifiant renvoyé par le serveur pour le prochain passage', async () => {
    const uuid = '33333333-3333-4333-8333-333333333333'
    const api = { enregistrerNavigateurEquipe: () => Promise.resolve({ data: { appareil_id: uuid } }) }
    const storage = fakeStorage()
    await enregistrerNavigateurEquipe({ id: 11 }, { api, storage })
    expect(storage.getItem(CLE_APPAREIL_ERP)).toBe(uuid)
  })

  it('avale un échec réseau sans throw, et ne pose pas la clé de rappel', async () => {
    const api = { enregistrerNavigateurEquipe: () => Promise.reject(new Error('réseau indisponible')) }
    const storage = fakeStorage()
    const user = { id: 9 }
    await expect(enregistrerNavigateurEquipe(user, { api, storage })).resolves.toBeUndefined()
    expect(storage.getItem(cleEnregistrement(9))).toBeNull()
  })
})
