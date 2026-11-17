import { beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat, documentContrat } from '../test/fixtures/contractSamples'

vi.mock('./axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const api = (await import('./axios')).default
const client = await import('./tachesApi')

/* TCH42 — chaque fonction du client est EXÉCUTÉE avec un axios simulé et appelle EXACTEMENT
   la méthode et le chemin de la table ci-dessous (api.md §3) ; aucun fichier source n'est lu. */

// [fonction, méthode, chemin de api.md SANS requête, échantillon de réponse]
const ATTENDU = [
  ['lireAujourdhui', 'GET', 'aujourdhui/', 'aujourdhui'],
  ['lireAilleurs', 'GET', 'aujourdhui/ailleurs/', 'ailleurs'],
  ['lireBadge', 'GET', 'badge/', 'badge'],
  ['marquerVu', 'POST', 'vu/', 'vu'],
  ['proposerJournee', 'GET', 'journee/proposition/', 'journee_proposition'],
  ['lirePriorites', 'GET', 'journee/priorites/', 'priorites'],
  ['lirePoint', 'GET', 'journee/point/', 'point'],
  ['garderJournee', 'POST', 'journee/planifier/', 'journee_ecrite'],
  ['marquerEssentiel', 'POST', 'journee/essentiel/', 'tache_ecrite'],
  ['alleger', 'POST', 'journee/alleger/', 'journee_ecrite'],
  ['lireCloture', 'GET', 'journee/cloture/', 'journee_cloture'],
  ['cloturerJournee', 'POST', 'journee/cloturer/', 'journee_cloturee'],
  ['lireAgenda', 'GET', 'agenda/', 'agenda'],
  ['rechercher', 'GET', 'recherche/', 'recherche'],
  ['saisieRapide', 'POST', 'saisie-rapide/', 'saisie_rapide'],
  ['capturer', 'POST', 'capture/', 'capture'],
  ['listerTaches', 'GET', 'taches/'],
  ['creerTache', 'POST', 'taches/', 'tache_ecrite'],
  ['lireTache', 'GET', 'taches/{}/', 'tache'],
  ['modifierTache', 'PATCH', 'taches/{}/', 'tache_ecrite'],
  ['supprimerTache', 'DELETE', 'taches/{}/'],
  ['planifierTache', 'POST', 'taches/{}/planifier/', 'tache_ecrite'],
  ['terminerTache', 'POST', 'taches/{}/terminer/', 'tache_ecrite'],
  ['rouvrirTache', 'POST', 'taches/{}/rouvrir/'],
  ['trancherTache', 'POST', 'taches/{}/trancher/'],
  ['sauterTache', 'POST', 'taches/{}/sauter/'],
  ['attendreTache', 'POST', 'taches/{}/attendre/'],
  ['recevoirTache', 'POST', 'taches/{}/recu/'],
  ['reordonnerTache', 'POST', 'taches/{}/reordonner/'],
  ['restaurerTache', 'POST', 'taches/{}/restaurer/'],
  ['poserRappel', 'POST', 'taches/{}/rappels/', 'tache_ecrite'],
  ['apercuChangement', 'POST', 'taches/{}/changement/apercu/', 'tache_changement'],
  ['traiterLot', 'POST', 'taches/lot/', 'lot'],
  ['lierActivite', 'POST', 'taches/lier-activite/', 'lier_activite'],
  ['convertirActivites', 'POST', 'convertir-activite/', 'convertir_activite'],
  ['retirerRappel', 'DELETE', 'rappels/{}/'],
  ['repeterRappel', 'POST', 'rappels/{}/repeter/', 'rappel_repeter'],
  ['modifierRecurrence', 'PATCH', 'recurrences/{}/'],
  ['ajouterPoint', 'POST', 'checklist/'],
  ['modifierPoint', 'PATCH', 'checklist/{}/'],
  ['retirerPoint', 'DELETE', 'checklist/{}/'],
  ['reordonnerPoint', 'POST', 'checklist/{}/reordonner/'],
  ['listerEtiquettes', 'GET', 'etiquettes/', 'etiquettes'],
  ['creerEtiquette', 'POST', 'etiquettes/'],
  ['modifierEtiquette', 'PATCH', 'etiquettes/{}/'],
  ['supprimerEtiquette', 'DELETE', 'etiquettes/{}/'],
  ['listerVues', 'GET', 'vues/', 'vues'],
  ['creerVue', 'POST', 'vues/'],
  ['modifierVue', 'PATCH', 'vues/{}/'],
  ['supprimerVue', 'DELETE', 'vues/{}/'],
  ['listerSupprimees', 'GET', 'supprimees/', 'supprimees'],
  ['listerGestes', 'GET', 'gestes/', 'gestes'],
  ['annulerGeste', 'POST', 'gestes/{}/annuler/', 'geste_annuler'],
  ['listerSuggestions', 'GET', 'suggestions/', 'suggestions'],
  ['accepterSuggestion', 'POST', 'suggestions/{}/accepter/', 'tache_ecrite'],
  ['refuserSuggestion', 'POST', 'suggestions/{}/refuser/', 'suggestion_refusee'],
  ['listerProjets', 'GET', 'projets/', 'projets_liste'],
  ['creerProjet', 'POST', 'projets/', 'projet_ecrit'],
  ['lireProjet', 'GET', 'projets/{}/', 'projet'],
  ['modifierProjet', 'PATCH', 'projets/{}/', 'projet'],
  ['supprimerProjet', 'DELETE', 'projets/{}/'],
  ['reordonnerProjet', 'POST', 'projets/{}/reordonner/'],
  ['trierProjetsParPriorite', 'POST', 'projets/trier-par-priorite/'],
  ['lireVueProjet', 'GET', 'projets/{}/vue/', 'projet_vue'],
  ['apercuPlanification', 'POST', 'projets/{}/planification/apercu/', 'planification_apercu'],
  ['planifierProjet', 'POST', 'projets/{}/planification/', 'planification'],
  ['decalerProjet', 'POST', 'projets/{}/decaler/', 'decalage'],
  ['terminerProjet', 'POST', 'projets/{}/terminer/', 'projet_ecrit'],
  ['rouvrirProjet', 'POST', 'projets/{}/rouvrir/', 'projet_ecrit'],
  ['restaurerProjet', 'POST', 'projets/{}/restaurer/', 'projet_ecrit'],
  ['dupliquerProjet', 'POST', 'projets/{}/dupliquer/', 'modele_instancier'],
  ['enregistrerModele', 'POST', 'projets/{}/enregistrer-modele/', 'modele'],
  ['creerSection', 'POST', 'sections/'],
  ['modifierSection', 'PATCH', 'sections/{}/'],
  ['supprimerSection', 'DELETE', 'sections/{}/'],
  ['reordonnerSection', 'POST', 'sections/{}/reordonner/'],
  ['listerModeles', 'GET', 'modeles/', 'modeles_liste'],
  ['lireModele', 'GET', 'modeles/{}/'],
  ['renommerModele', 'PATCH', 'modeles/{}/'],
  ['supprimerModele', 'DELETE', 'modeles/{}/'],
  ['instancierModele', 'POST', 'modeles/{}/instancier/', 'modele_instancier'],
  ['lireRevue', 'GET', 'revue/projets/', 'revue_projets'],
  ['deciderRevue', 'PUT', 'revue/projets/{}/', 'revue_decision'],
  ['lireRythme', 'GET', 'rythme/', 'rythme'],
  ['poserMode', 'POST', 'rythme/', 'rythme'],
  ['repondreProposition', 'POST', 'rythme/propositions/{}/repondre/', 'proposition_repondue'],
  ['poserPreference', 'POST', 'preferences/', 'rythme'],
  ['retirerPreference', 'DELETE', 'preferences/{}/', 'rythme'],
  ['lireReglages', 'GET', 'reglages/', 'reglages'],
  ['modifierReglages', 'PATCH', 'reglages/', 'reglages'],
  ['lireReglagesSociete', 'GET', 'reglages-societe/', 'reglages_societe'],
  ['modifierReglagesSociete', 'PATCH', 'reglages-societe/', 'reglages_societe'],
  ['listerJetons', 'GET', 'jetons/', 'jetons_liste'],
  ['creerJeton', 'POST', 'jetons/', 'jeton'],
  ['revoquerJeton', 'POST', 'jetons/{}/revoquer/'],
  ['testerNotification', 'POST', 'mon-iphone/test-notification/'],
  ['lireTuile', 'GET', 'tuile/', 'tuile'],
  ['lireFlux', 'GET', 'flux/{}.ics'],
  ['lireEnteteCoach', 'GET', 'coach/entete/', 'coach_entete'],
  ['exporterMesDonnees', 'GET', 'mes-donnees/', 'mes_donnees'],
  ['toutEffacer', 'POST', 'tout-effacer/', 'tout_effacer'],
  ['listerAgendasExternes', 'GET', 'agendas-externes/', 'agendas_externes'],
  ['ajouterAgendaExterne', 'POST', 'agendas-externes/', 'agenda_externe'],
  ['modifierAgendaExterne', 'PATCH', 'agendas-externes/{}/', 'agenda_externe'],
  ['retirerAgendaExterne', 'DELETE', 'agendas-externes/{}/'],
  ['rafraichirAgendaExterne', 'POST', 'agendas-externes/{}/rafraichir/', 'agenda_externe'],
]

const normaliser = (url) => url.replace(/^\/taches\//, '').replace(/ID/g, '{}')

beforeEach(() => {
  vi.clearAllMocks()
  client.definirProprietaire(null)
  for (const m of ['get', 'post', 'patch', 'put', 'delete']) api[m].mockResolvedValue({ data: {} })
})

describe('TCH42 — une fonction par route de api.md §3', () => {
  it('le tableau attendu porte les 106 routes, chacune une seule fois', () => {
    expect(ATTENDU).toHaveLength(106)
    const attendu = ATTENDU.map(([, methode, chemin]) => `${methode} ${chemin}`)
    expect(new Set(attendu).size).toBe(106)
    expect(new Set(ATTENDU.map(([nom]) => nom)).size).toBe(106)
  })

  it.each(ATTENDU)('%s : %s %s', async (nom, methode, chemin, contrat) => {
    expect(typeof client[nom]).toBe('function')
    const verbe = methode.toLowerCase()
    const donnees = contrat ? exempleContrat('taches', contrat) : { ok: true }
    api[verbe].mockResolvedValue({ data: donnees })
    const jeton = nom === 'capturer' ? ['tqc_exemple'] : []
    const ids = (chemin.match(/\{\}/g) ?? []).map(() => 'ID')
    const args = nom === 'capturer' ? [{ titre: 't' }, ...jeton]
      : (nom === 'lireTuile' || nom === 'lireFlux') ? ['ID'] : [...ids, { x: 1 }]
    const reponse = await client[nom](...args)
    expect(api[verbe]).toHaveBeenCalledTimes(1)
    const appel = api[verbe].mock.calls[0]
    expect(normaliser(appel[0])).toBe(chemin)
    expect(appel[0].startsWith('/taches/')).toBe(true)
    expect(reponse.data).toEqual(donnees)
  })
})

describe('TCH42 — conventions', () => {
  it('une écriture « K » porte une Idempotency-Key générée, rejouable, ou omise par cle:null', async () => {
    await client.creerProjet({ nom: 'A' })
    const cle = api.post.mock.calls[0][2].headers['Idempotency-Key']
    expect(cle).toMatch(/\S{8,}/)
    await client.creerProjet({ nom: 'A' }, { cle: 'rejeu-1' })
    expect(api.post.mock.calls[1][2].headers['Idempotency-Key']).toBe('rejeu-1')
    await client.creerProjet({ nom: 'A' }, { cle: null })
    expect(api.post.mock.calls[2][2]).toBeUndefined()
    // une écriture qui n'a pas de « K » n'en envoie jamais
    await client.creerEtiquette({ nom: 'x' })
    expect(api.post.mock.calls[3]).toHaveLength(2)
  })

  it('proprietaire_attendu est posé au corps de saisie-rapide, planifier et terminer', async () => {
    client.definirProprietaire(7)
    await client.saisieRapide({ textes: ['a'], apercu: true })
    expect(api.post.mock.calls[0][1]).toMatchObject({ textes: ['a'], proprietaire_attendu: 7 })
    await client.planifierTache(20, { jour_prevu: '2026-11-19', lock_version: 4 })
    expect(api.post.mock.calls[1][1]).toMatchObject({ jour_prevu: '2026-11-19', lock_version: 4, proprietaire_attendu: 7 })
    await client.terminerTache(20)
    expect(api.post.mock.calls[2][1]).toEqual({ proprietaire_attendu: 7 })
    // un corps qui le porte déjà, ou aucun propriétaire connu : rien n'est écrasé ni ajouté
    await client.terminerTache(20, { proprietaire_attendu: 9 })
    expect(api.post.mock.calls[3][1]).toEqual({ proprietaire_attendu: 9 })
    client.definirProprietaire(null)
    await client.terminerTache(20)
    expect(api.post.mock.calls[4][1]).toEqual({})
  })

  it('les trois routes à jeton envoient le jeton, jamais le cookie seul', async () => {
    await client.capturer({ titre: 'appeler' }, 'tqc_abc')
    expect(api.post.mock.calls[0][2].headers.Authorization).toBe('Bearer tqc_abc')
    await client.lireTuile('tqt_abc')
    expect(api.get.mock.calls[0][1].headers.Authorization).toBe('Bearer tqt_abc')
    await client.lireFlux('tqf_abc')
    expect(api.get.mock.calls[1][0]).toBe('/taches/flux/tqf_abc.ics')
  })

  it('les paramètres de requête passent par params', async () => {
    await client.lireAujourdhui({ jour: '2026-11-17', tout: 1 })
    expect(api.get).toHaveBeenCalledWith('/taches/aujourdhui/', { params: { jour: '2026-11-17', tout: 1 } })
    await client.lireVueProjet(3, { vue: 'tableau' })
    expect(api.get).toHaveBeenLastCalledWith('/taches/projets/3/vue/', { params: { vue: 'tableau' } })
  })
})

describe('TCH42 — codes 409 distingués (erreurs.json)', () => {
  const erreurs = documentContrat('taches', 'erreurs').exemple

  it('conflit_version rend le lock_version courant et la tâche actuelle', () => {
    const e = client.classerErreur({ response: { status: 409, data: erreurs.conflit_version } })
    expect(e.code).toBe('conflit_version')
    expect(e.lockVersion).toBe(5)
    expect(e.actuel).toMatchObject({ type: 'tache', id: 20 })
    expect(client.estConflitVersion({ response: { status: 409, data: erreurs.conflit_version } })).toBe(true)
  })

  it('chaque autre 409 garde son code ; un 409 sans code reste un conflit', () => {
    for (const code of client.CODES_409) {
      expect(client.classerErreur({ response: { status: 409, data: { code, detail: 'x' } } }).code).toBe(code)
    }
    expect(client.estAutreCompte({ response: { status: 409, data: { code: 'autre_compte' } } })).toBe(true)
    expect(client.classerErreur({ response: { status: 409, data: {} } }).code).toBe('conflit')
    expect(client.classerErreur({ response: { status: 409, data: { code: 'idempotency_en_cours' } } }).code)
      .toBe('idempotency_en_cours')
  })

  it('400 rend les champs fautifs ; 404, 429 et réseau sont distincts', () => {
    const e400 = client.classerErreur({ response: { status: 400, data: erreurs.champ } })
    expect(e400).toMatchObject({ code: 'validation', champs: { projet_id: ['Projet inexistant.'] } })
    const parLigne = client.classerErreur({ response: { status: 400, data: erreurs.par_ligne } })
    expect(parLigne.champs.lignes['3'].titre[0]).toMatch(/titre est vide/)
    expect(client.classerErreur({ response: { status: 404, data: erreurs.introuvable } }).code).toBe('introuvable')
    expect(client.classerErreur({ response: { status: 429, data: {} } }).code).toBe('limite')
    expect(client.classerErreur(new Error('Network Error')).code).toBe('reseau')
  })
})

describe('TCH42 — listes paginées lues en entier', () => {
  it.each([
    ['listerToutesLesTaches', '/taches/taches/'],
    ['listerTousLesProjets', '/taches/projets/'],
    ['listerToutesLesEtiquettes', '/taches/etiquettes/'],
    ['listerTousLesModeles', '/taches/modeles/'],
  ])('%s suit toutes les pages de %s', async (nom, url) => {
    const page = (n) => ({ data: { count: 3, next: n < 2 ? 'x' : null, previous: null, results: n < 2 ? [{ id: 1 }, { id: 2 }] : [{ id: 3 }] } })
    api.get.mockImplementation((_chemin, { params }) => Promise.resolve(page(params.page)))
    const lignes = await client[nom]({ vue: 'boite' })
    expect(lignes.map((l) => l.id)).toEqual([1, 2, 3])
    expect(api.get.mock.calls.every(([chemin, { params }]) => chemin === url && params.vue === 'boite')).toBe(true)
  })
})
