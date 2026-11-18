import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReactReduxContext } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { memoryStore } from '../../lib/offlineOutbox'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'
import { creerFile, definirCompteFile, remplacerFile } from '../../features/taches/horsligne/captureQueue'

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const api = (await import('../../api/axios')).default
const { default: Aujourdhui } = await import('./Aujourdhui')

/* TCH76 — l'écran Aujourd'hui rend `aujourdhui.json` : sections dans l'ordre de regles.md §4.1,
   liste gardée sur un rafraîchissement en échec, actions grisées hors ligne, squelette après 1 s,
   rendez-vous externes en lecture seule, état vide « Colle ou dicte tes listes ». */

const donnees = () => structuredClone(exempleContrat('taches', 'aujourdhui'))
const echecReseau = () => Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' })

function servir(reponse) {
  api.get.mockImplementation((url) => {
    if (url === '/taches/aujourdhui/') return typeof reponse === 'function' ? reponse() : Promise.resolve({ data: reponse })
    return Promise.reject(new Error(`appel inattendu : GET ${url}`))
  })
}

function monter(url = '/taches/aujourdhui') {
  return render(<MemoryRouter initialEntries={[url]}><Aujourdhui /></MemoryRouter>)
}

function fixerEnLigne(valeur) {
  Object.defineProperty(window.navigator, 'onLine', { value: valeur, configurable: true })
  act(() => { window.dispatchEvent(new Event(valeur ? 'online' : 'offline')) })
}

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
  fixerEnLigne(true)
})
afterEach(() => { vi.useRealTimers() })

describe('TCH76 — ordre vertical et contenu des sections', () => {
  it('rend Essentiel, Toute la journée, Prévu, Ce soir puis les repliés, dans cet ordre', async () => {
    servir(donnees())
    const { container } = monter()
    await screen.findByText('Devis Settat')
    const reperes = [...container.querySelectorAll('.section-titre, .bande-journee, .replie')]
      .map((n) => n.textContent.replace(/\s+/g, ' ').trim())
    expect(reperes[0]).toBe('Essentiel')
    expect(reperes.slice(1, 3).every((t) => t.endsWith('Toute la journée'))).toBe(true)
    expect(reperes.slice(3)).toEqual([
      'Prévu', 'Ce soir', "Proposé pour aujourd'hui", 'À revoir1', "En attente1· 1 en attente d'une autre tâche", 'Faites1', "Ailleurs dans l'ERP",
    ])
  })

  it('met les lignes à leur place : essentiel, rendez-vous à son heure, activité ERP, relances', async () => {
    servir(donnees())
    const { container } = monter()
    await screen.findByText('Devis Settat')
    const essentiel = container.querySelector('.section.premiere')
    expect(within(essentiel).getByText('Devis Settat')).toBeInTheDocument()
    expect(within(essentiel).getByRole('checkbox', { name: /Essentielle : Devis Settat/ })).toBeChecked()
    const prevu = [...container.querySelectorAll('.section')].find((s) => s.textContent.startsWith('Prévu'))
    const titres = [...prevu.querySelectorAll('.titre')].map((t) => t.textContent)
    expect(titres).toEqual(['11:00–12:00 Réunion banque', 'Timbres', 'Rappeler Benali', 'Suivi des relances : 5'])
    expect(within(prevu).getByText('Activité ERP')).toBeInTheDocument()
    expect(container.querySelector('.bande-journee b')).toHaveTextContent('Visite — Karim Benali')
  })

  it('un rendez-vous d\'un agenda externe est en lecture seule : ni case, ni geste', async () => {
    servir(donnees())
    const { container } = monter()
    await screen.findByText('Devis Settat')
    const rdv = container.querySelector('[data-ligne="rdv:2-9f2c1a7b"]')
    expect(rdv).toHaveTextContent('Microsoft 365')
    expect(within(rdv).queryByRole('checkbox')).toBeNull()
    expect(within(rdv).queryByRole('button')).toBeNull()
  })

  it('le sous-titre est le jour long, « Jour non travaillé » un jour chômé', async () => {
    servir({ ...donnees(), jour_ouvre: false })
    monter()
    expect(await screen.findByText('Jour non travaillé')).toBeInTheDocument()
  })

  it('les repliés se déplient au toucher et nomment leurs lignes', async () => {
    servir(donnees())
    monter()
    await screen.findByText('Devis Settat')
    expect(screen.queryByText('Retour Lydec')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /^En attente/ }))
    expect(screen.getByText('Retour Lydec')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^Faites/ }))
    expect(screen.getByText('Dossier subvention')).toBeInTheDocument()
  })

  it('plus de trois activités ERP sans heure : une ligne repliable « n activités ERP »', async () => {
    const d = donnees()
    const activite = d.journee.find((i) => i.type === 'activite')
    d.journee = [d.journee[0], ...[1, 2, 3, 4].map((n) => ({ ...activite, id: 200 + n, titre: `Activité ${n}` }))]
    servir(d)
    monter()
    await screen.findByText('Devis Settat')
    expect(screen.queryByText('Activité 1')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: '4 activités ERP' }))
    expect(screen.getByText('Activité 1')).toBeInTheDocument()
  })
})

describe('TCH76 — états : chargement, erreur, hors ligne, vide', () => {
  it('affiche le squelette seulement après 1 s, jamais avant', async () => {
    vi.useFakeTimers()
    let finir
    servir(() => new Promise((resolu) => { finir = () => resolu({ data: donnees() }) }))
    monter()
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    expect(screen.getByRole('status', { name: 'Chargement' })).toBeInTheDocument()
    await act(async () => { finir(); await vi.advanceTimersByTimeAsync(0) })
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
    expect(screen.getByText('Devis Settat')).toBeInTheDocument()
  })

  it('un rafraîchissement en échec GARDE la liste : « Pas à jour · 09:12 » et Réessayer', async () => {
    servir(donnees())
    monter()
    await screen.findByText('Devis Settat')
    servir(() => Promise.reject(echecReseau()))
    act(() => { window.dispatchEvent(new Event('focus')) })
    expect(await screen.findByText('Pas à jour · 09:12')).toBeInTheDocument()
    expect(screen.getByText('Devis Settat')).toBeInTheDocument()
    servir(donnees())
    await userEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    await waitFor(() => expect(screen.queryByText(/Pas à jour/)).toBeNull())
    expect(screen.getByText('Devis Settat')).toBeInTheDocument()
  })

  it('relit au retour du focus', async () => {
    servir(donnees())
    monter()
    await screen.findByText('Devis Settat')
    expect(api.get).toHaveBeenCalledTimes(1)
    act(() => { window.dispatchEvent(new Event('focus')) })
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))
  })

  it('hors ligne : la lecture reste, l\'en-tête le dit ; un geste qui exige le réseau dit « Possible une fois connecté »', async () => {
    servir(donnees())
    monter()
    await screen.findByText('Devis Settat')
    api.post.mockClear()
    fixerEnLigne(false)
    expect(screen.getByText(/Hors ligne · dernière synchro à 09:12/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Garder c/ }))
    expect(api.post).not.toHaveBeenCalled()
    await waitFor(() => expect(screen.getAllByRole('status').some((n) => n.textContent.includes('Possible une fois connecté'))).toBe(true))
  })

  describe('Raccord F2 — file hors ligne et cache du jour (TCH100)', () => {
    const store = { getState: () => ({ auth: { user: { id: 42, active_company_id: 7 } } }) }
    const monterConnecte = () => render(
      <ReactReduxContext.Provider value={{ store }}>
        <MemoryRouter initialEntries={['/taches/aujourdhui']}><Aujourdhui /></MemoryRouter>
      </ReactReduxContext.Provider>,
    )
    let file
    beforeEach(() => {
      window.localStorage.clear()
      file = creerFile({ store: memoryStore() })
      remplacerFile(file)
    })
    afterEach(() => { remplacerFile(null); definirCompteFile(null); window.localStorage.clear() })

    it('cocher et reporter hors ligne partent dans la file : la ligne change tout de suite, « Partira dès le retour du réseau »', async () => {
      servir(donnees())
      monterConnecte()
      await screen.findByText('Devis Settat')
      api.post.mockClear()
      fixerEnLigne(false)
      await userEvent.click(screen.getByRole('checkbox', { name: 'Marquer « Timbres » comme faite' }))
      await waitFor(() => expect(screen.getByRole('checkbox', { name: 'Marquer « Timbres » comme faite' })).toBeChecked())
      expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Partira dès le retour du réseau')
      await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Devis Settat »' }))
      await userEvent.click(await screen.findByRole('menuitem', { name: /^Reporter à/ }))
      await waitFor(async () => expect((await file.pending()).map((op) => op.op_type)).toEqual(['cocher', 'reporter']))
      const [, report] = await file.pending()
      expect(report.payload.corps).toMatchObject({ jour_prevu: donnees().prochain_jour_ouvre, lock_version: expect.any(Number) })
      expect(api.post).not.toHaveBeenCalled()
    })

    it('un brouillon de saisie gardé : la carte « Ta saisie de tout à l\'heure t\'attend. » ; Reprendre ouvre la saisie', async () => {
      window.localStorage.setItem('taches:brouillon:7:42', JSON.stringify({ texte: 'Appeler le notaire', quand: null }))
      servir(donnees())
      const ouverture = vi.fn()
      window.addEventListener('taqinor:taches:saisir', ouverture)
      monterConnecte()
      const carte = await screen.findByRole('region', { name: 'Brouillon' })
      expect(carte).toHaveTextContent("Ta saisie de tout à l'heure t'attend.")
      await userEvent.click(within(carte).getByRole('button', { name: 'Reprendre' }))
      expect(ouverture).toHaveBeenCalledTimes(1)
      expect(await screen.findByRole('textbox', { name: 'Ajouter une tâche' })).toHaveValue('Appeler le notaire')
      window.removeEventListener('taqinor:taches:saisir', ouverture)
    })

    it('une création ailleurs (`taqinor:taches:creees`) relit la journée une fois', async () => {
      servir(donnees())
      monterConnecte()
      await screen.findByText('Devis Settat')
      const avant = api.get.mock.calls.length
      act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:creees', { detail: { creees: [] } })) })
      await waitFor(() => expect(api.get.mock.calls.length).toBe(avant + 1))
    })

    it('ouvert sans réseau, l\'écran lit la journée gardée dans le cache du compte au lieu de rester vide', async () => {
      // Le cache est PAR JOUR : écrit sous le `jour` servi, relu sous le jour de l'appareil. L'horloge du test est
      // donc celle du jour de l'échantillon (seule `Date` est figée : les attentes asynchrones gardent leurs minuteurs).
      vi.useFakeTimers({ toFake: ['Date'] })
      vi.setSystemTime(new Date(`${donnees().jour}T10:00:00Z`))
      try {
        servir(donnees())
        const { unmount } = monterConnecte()
        await screen.findByText('Devis Settat')
        unmount()
        servir(() => Promise.reject(echecReseau()))
        monterConnecte()
        expect(await screen.findByText('Devis Settat')).toBeInTheDocument()
        expect(screen.getByText(/^Pas à jour · \d\d:\d\d$/)).toBeInTheDocument()
      } finally {
        vi.useRealTimers()
      }
    })

    it('le cache d\'un autre jour n\'est jamais montré comme la journée d\'aujourd\'hui', async () => {
      vi.useFakeTimers({ toFake: ['Date'] })
      vi.setSystemTime(new Date(`${donnees().jour}T10:00:00Z`))
      try {
        servir(donnees())
        const { unmount } = monterConnecte()
        await screen.findByText('Devis Settat')
        unmount()
        vi.setSystemTime(new Date(new Date(`${donnees().jour}T10:00:00Z`).getTime() + 24 * 3600 * 1000))
        servir(() => Promise.reject(echecReseau()))
        monterConnecte()
        // l'état d'échec est rendu (« Réessayer ») : la lecture a échoué ET le cache a été consulté
        expect(await screen.findByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
        expect(screen.queryByText('Devis Settat')).toBeNull()
      } finally {
        vi.useRealTimers()
      }
    })
  })

  it('aucune tâche : « Colle ou dicte tes listes » et Coller mes listes ouvre la saisie', async () => {
    const d = donnees()
    Object.assign(d, {
      essentiel: [], obligations: [], rendez_vous: [], journee: [], ce_soir: [], a_decider: [], en_attente: [], faites: [],
      a_trier: { boite_reception: 0, bloquees: 0, suggestions: 0, a_convertir: 0 },
      propose: { replie: false, pour_objectif: [], reste_nb: 0, charge: null, suite_par_projet: null },
    })
    servir(d)
    const ouverture = vi.fn()
    window.addEventListener('taqinor:taches:saisir', ouverture)
    monter()
    const phrase = await screen.findByText('Colle ou dicte tes listes : je les range par projet.')
    // passe visuelle n° 20 — espace INSÉCABLE avant « : » (maquette ecran-aujourdhui-vide.html) : jamais « : » en tête de ligne
    expect(phrase.textContent).toBe('Colle ou dicte tes listes : je les range par projet.')
    await userEvent.click(screen.getByRole('button', { name: 'Coller mes listes' }))
    expect(ouverture).toHaveBeenCalledTimes(1)
    window.removeEventListener('taqinor:taches:saisir', ouverture)
  })

  it('rien de gardé, des tâches à trier : la phrase et Trier', async () => {
    const d = donnees()
    Object.assign(d, {
      essentiel: [], obligations: [], rendez_vous: [], journee: [], ce_soir: [], a_decider: [], en_attente: [], faites: [],
      a_trier: { boite_reception: 3, bloquees: 0, suggestions: 0, a_convertir: 0 },
      propose: { replie: false, pour_objectif: [], reste_nb: 0, charge: null, suite_par_projet: null },
    })
    servir(d)
    monter()
    expect(await screen.findByText("Rien de prévu aujourd'hui. 3 tâches attendent dans À trier.")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trier' })).toBeInTheDocument()
  })
})

describe('TCH76 — gestes optimistes', () => {
  it('cocher une tâche : terminer/ part, la ligne reste barrée, le toast propose Annuler', async () => {
    servir(donnees())
    api.post.mockResolvedValue({ data: { ...exempleContrat('taches', 'tache_ecrite'), geste_id: 77, progression: null } })
    monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Marquer « Timbres » comme faite' }))
    await waitFor(() => expect(api.post.mock.calls.map((c) => c[0])).toContain('/taches/taches/42/terminer/'))
    expect(await screen.findByRole('button', { name: 'Annuler' })).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('Raccord F2 — ⋯ → En attente de… pose l\'attente sans ouvrir la fiche ; la ligne quitte la journée, Annuler la remet', async () => {
    servir(donnees())
    api.post.mockImplementation((url) => Promise.resolve({ data: url.endsWith('/attendre/') ? { ...exempleContrat('taches', 'tache_ecrite'), geste_id: 88 } : {} }))
    monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Timbres »' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'En attente de…' }))
    const feuille = await screen.findByRole('dialog', { name: 'En attente de…' })
    await userEvent.type(within(feuille).getByLabelText('De qui ou de quoi ?'), 'Lydec')
    await userEvent.click(within(feuille).getByRole('button', { name: 'En attente' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/42/attendre/', { en_attente_de: 'Lydec' }))
    expect(screen.queryByText('Timbres')).toBeNull()
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('En attente de : Lydec')
    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/gestes/88/annuler/', {}))
    expect(await screen.findByText('Timbres')).toBeInTheDocument()
    // la journée n'est jamais relue ; seule la tâche remise l'est (sa version change à l'annulation, F4 revue #7)
    expect(api.get.mock.calls.filter(([url]) => url === '/taches/aujourdhui/')).toHaveLength(1)
  })

  it('F4 revue #7 — Reporter, « Annuler », reporter encore : la requête porte la version RENDUE par le serveur (jamais « Cette tâche a changé »)', async () => {
    const d = donnees()
    const serveur = { verrou: d.journee.find((i) => i.id === 42).lock_version }
    api.get.mockImplementation((url) => {
      if (url === '/taches/aujourdhui/') return Promise.resolve({ data: d })
      if (url === '/taches/taches/42/') return Promise.resolve({ data: { ...exempleContrat('taches', 'tache_ecrite').tache, id: 42, lock_version: serveur.verrou } })
      return Promise.reject(new Error(`appel inattendu : GET ${url}`))
    })
    api.post.mockImplementation((url, corps) => {
      if (url === '/taches/taches/42/planifier/') {
        if (corps.lock_version !== serveur.verrou) return Promise.reject(Object.assign(new Error('http'), { response: { status: 409, data: { code: 'conflit_version', detail: 'Modifiée ailleurs.' } } }))
        serveur.verrou += 1
        const ecrite = exempleContrat('taches', 'tache_ecrite')
        return Promise.resolve({ data: { ...ecrite, tache: { ...ecrite.tache, id: 42, lock_version: serveur.verrou }, geste_id: 60 } })
      }
      if (url === '/taches/gestes/60/annuler/') { serveur.verrou += 1; return Promise.resolve({ data: { restaurees: [{ objet: 'tache', id: 42 }], conflits: [], deja: false } }) }
      return Promise.resolve({ data: {} })
    })
    monter()
    await screen.findByText('Devis Settat')
    const reporter = async () => {
      await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Timbres »' }))
      await userEvent.click(await screen.findByRole('menuitem', { name: /^Reporter à/ }))
    }
    await reporter()
    await userEvent.click(await screen.findByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/gestes/60/annuler/', {}))
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/taches/taches/42/'))
    await reporter()
    await waitFor(() => expect(api.post.mock.calls.filter(([url]) => url.endsWith('/planifier/'))).toHaveLength(2))
    expect(api.post.mock.calls.filter(([url]) => url.endsWith('/planifier/'))[1][1].lock_version).toBe(3) // version 1 → écriture 2 → annulation 3
    expect(screen.queryByText(/Cette tâche a changé/)).toBeNull()
  })

  it('Raccord F2 — la `progression` rendue par une écriture (reporter) met la progression à jour sans relire la journée', async () => {
    const d = donnees()
    servir(d)
    const ecrite = exempleContrat('taches', 'tache_ecrite')
    api.post.mockResolvedValue({ data: { ...ecrite, geste_id: 70, progression: { ...d.progression, faites: 2 } } })
    monter()
    await screen.findByText('Devis Settat')
    expect(screen.getByRole('button', { name: /^1 sur \d+ faites/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Timbres »' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: /^Reporter à/ }))
    expect(await screen.findByRole('button', { name: /^2 sur \d+ faites/ })).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('une activité ERP cochée close dans l\'ERP, sans Annuler', async () => {
    const d = donnees()
    d.journee.find((i) => i.type === 'activite').peut_cloturer = true
    servir(d)
    api.post.mockResolvedValue({ data: {} })
    monter()
    await screen.findByText('Devis Settat')
    fireEvent.click(screen.getByRole('checkbox', { name: 'Marquer « Rappeler Benali » comme faite' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/records/activities/101/done/', {}))
    expect(await screen.findByText("Close dans l'ERP")).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Annuler' })).toBeNull()
  })
})

describe('F2 acceptation (S5) — un refus 409 nommé (textes.md §2.16) se VOIT, pas seulement au lecteur d\'écran', () => {
  it('carte du moment : 409 `proposition_expiree` → la carte part et « Cette proposition a expiré. » s\'affiche', async () => {
    servir(donnees())
    const expiree = exempleContrat('taches', 'erreurs').proposition_expiree
    api.post.mockImplementation((url) => (url.endsWith('/repondre/')
      ? Promise.reject(Object.assign(new Error('409'), { response: { status: 409, data: expiree } }))
      : Promise.resolve({ data: {} })))
    monter()
    await userEvent.click(await screen.findByRole('button', { name: 'Monter à 6' }))
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Cette proposition a expiré.')
    expect(screen.queryByRole('button', { name: 'Monter à 6' })).toBeNull()
  })
})

describe('F2 acceptation (P144.1) — le bandeau de conflit dit l\'heure servie par la réponse 409', () => {
  it('Reporter refusé par un 409 `conflit_version` : « Modifiée sur ton autre appareil à 10:42 »', async () => {
    servir(donnees())
    const conflit = exempleContrat('taches', 'erreurs').conflit_version
    api.post.mockImplementation((url) => (url.endsWith('/planifier/')
      ? Promise.reject(Object.assign(new Error('409'), { response: { status: 409, data: conflit } }))
      : Promise.resolve({ data: {} })))
    monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Timbres »' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: /^Reporter à/ }))
    expect(await screen.findByRole('group', { name: 'Conflit entre appareils' })).toHaveTextContent('Modifiée sur ton autre appareil à 10:42')
  })
})

describe('F2 acceptation (P144.3) — clavier : une feuille ouverte par une touche se valide par Entrée', () => {
  /** Focalise le titre d'une ligne, comme `j` le fait. */
  const focaliser = (id) => act(() => { document.querySelector(`[data-ligne="tache:${id}"] .ligne-corps-bouton`).focus() })

  it('`d` ouvre « Choisir un jour » sur le jour nommé de Reporter ; Entrée reporte (spec-7 §5)', async () => {
    servir(donnees())
    api.post.mockResolvedValue({ data: { ...exempleContrat('taches', 'tache_ecrite'), geste_id: 71, progression: null } })
    monter()
    await screen.findByText('Timbres')
    focaliser(42)
    await userEvent.keyboard('d')
    const feuille = await screen.findByRole('dialog', { name: 'Choisir un jour' })
    expect(within(feuille).getByLabelText('Jour')).toHaveValue('2026-11-19')
    expect(within(feuille).getByRole('button', { name: 'Reporter à jeu. 19' })).toHaveFocus()
    await userEvent.keyboard('{Enter}')
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/42/planifier/', { jour_prevu: '2026-11-19', lock_version: expect.anything() }))
    expect(screen.queryByRole('dialog', { name: 'Choisir un jour' })).toBeNull()
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Reportée à jeu. 19')
  })

  it('`m` ouvre « Déplacer vers… » sur un AUTRE projet que le sien ; Entrée déplace', async () => {
    servir(donnees())
    const autres = { results: [{ id: 3, nom: 'Ventes', couleur: 'indigo', priorite: 1 }, { id: 7, nom: 'Salon', couleur: 'vert', priorite: 2 }], next: null, count: 2 }
    api.get.mockImplementation((url) => Promise.resolve({ data: url === '/taches/projets/' ? autres : donnees() }))
    api.post.mockResolvedValue({ data: { geste_id: 72, refusees: [] } })
    monter()
    await screen.findByText('Devis Settat')
    focaliser(20)
    await userEvent.keyboard('m')
    const feuille = await screen.findByRole('dialog', { name: 'Déplacer vers…' })
    expect(within(feuille).getByRole('combobox', { name: 'Chercher un projet' })).toHaveFocus()
    // Entrée frappée avant même l'arrivée de la liste des projets : elle n'est pas perdue
    await userEvent.keyboard('{Enter}')
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/lot/', expect.objectContaining({
      ids: [20], action: 'deplacer', valeurs: { projet_id: 7 },
    }), expect.anything()))
  })
})
