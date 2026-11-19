import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReactReduxContext } from 'react-redux'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { memoryStore } from '../../lib/offlineOutbox'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'
import { creerFile, definirCompteFile, enfilerAjout, remplacerFile } from '../../features/taches/horsligne/captureQueue'

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
      'Prévu', 'Ce soir', "Proposé pour aujourd'hui", 'À revoir1', 'En attente1· Bloquées 1', 'Faites1', "Ailleurs dans l'ERP",
    ])
  })

  it('passe visuelle n° 15 — bureau : la progression, PUIS « Ajouter une tâche » (maquette ecran-aujourdhui-matin.html)', async () => {
    servir(donnees())
    const { container } = monter()
    await screen.findByText('Devis Settat')
    const ordre = [...container.querySelectorAll('button.progression, .saisie-bureau, .section-titre')].map((n) => n.className)
    expect(ordre.slice(0, 2)).toEqual(['progression', 'saisie-bureau bureau-seul'])
    expect(container.querySelectorAll('.saisie-bureau')).toHaveLength(1)
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
  it('R3-025 — affiche le squelette seulement après 300 ms, jamais avant', async () => {
    vi.useFakeTimers()
    let finir
    servir(() => new Promise((resolu) => { finir = () => resolu({ data: donnees() }) }))
    monter()
    await act(async () => { await vi.advanceTimersByTimeAsync(290) })
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
    await act(async () => { await vi.advanceTimersByTimeAsync(10) })
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

    it('R3-025 — revenir sur Aujourd\'hui : la dernière journée connue est là AU MONTAGE (aucun squelette), puis se relit en silence', async () => {
      const { ecrireJournee } = await import('../../features/taches/horsligne/cacheJournee')
      const { aujourdhuiIso } = await import('../../features/taches/lib/textes')
      ecrireJournee(42, aujourdhuiIso(), donnees(), new Date())
      let lacher
      const porte = new Promise((r) => { lacher = r })
      const relue = donnees()
      relue.essentiel = [{ ...relue.essentiel[0], titre: 'Devis Settat (relu)' }]
      servir(() => porte.then(() => ({ data: relue })))
      monterConnecte()
      // la lecture est encore retenue : la liste du cache est déjà là, sans squelette
      expect(screen.getByText('Devis Settat')).toBeInTheDocument()
      expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
      // (« vu » part d'abord) : la relecture part ensuite, sans toast de l'ERP si elle échoue — le bandeau le dira
      await waitFor(() => expect(api.get).toHaveBeenCalledWith('/taches/aujourdhui/', expect.objectContaining({ suppressErrorToast: true })))
      expect(screen.getByText('Devis Settat')).toBeInTheDocument()
      await act(async () => { lacher() })
      expect(await screen.findByText('Devis Settat (relu)')).toBeInTheDocument()
    })

    it('R2-008b — une tâche ajoutée hors ligne apparaît tout de suite, grisée « En attente d’envoi » (lue dans la file)', async () => {
      servir(donnees())
      monterConnecte()
      await screen.findByText('Devis Settat')
      fixerEnLigne(false)
      definirCompteFile(42, 7)
      // l'ancienne forme (lignes lues) et la nouvelle (la phrase, analysée au rejeu — R2-008a) se lisent toutes deux
      await act(async () => {
        // posées directement dans le magasin (sans prévenir l'écran), puis un ajout par la voie normale, qui prévient
        await file.enqueue('ajouter', { type: 'ajouter', corps: { texte: 'Test ce soir' }, userId: 42, companyId: 7 }, { queuedAt: new Date().toISOString() })
        await file.enqueue('ajouter', { type: 'ajouter', corps: { texte: 'Pas à moi' }, userId: 99, companyId: 7 }, { queuedAt: new Date().toISOString() })
        await enfilerAjout([{ titre: 'Appeler le notaire', client_id: 'c-1' }], file)
      })
      const bloc = await screen.findByRole('region', { name: 'En attente d’envoi' })
      await waitFor(() => expect(within(bloc).getByText('Test ce soir')).toBeInTheDocument())
      expect(within(bloc).getByText('Appeler le notaire')).toBeInTheDocument()
      expect(within(bloc).queryByText('Pas à moi')).toBeNull() // une op d'un autre compte n'est jamais montrée
      expect(bloc.querySelectorAll('[data-en-file]')).toHaveLength(2)
      expect(within(bloc).queryByRole('checkbox')).toBeNull()
    })

    it('R2-008b — la phrase mise en file par la saisie (pli L1 : `corps.phrase.textes`) apparaît telle quelle', async () => {
      servir(donnees())
      monterConnecte()
      await screen.findByText('Devis Settat')
      fixerEnLigne(false)
      definirCompteFile(42, 7)
      await act(async () => {
        await file.enqueue('ajouter', { type: 'ajouter', corps: { phrase: { textes: ['Rappeler la banque ce soir'], cid: 'c-9' } }, userId: 42, companyId: 7 },
          { queuedAt: new Date().toISOString() })
        await enfilerAjout([{ titre: 'Appeler le notaire', client_id: 'c-1' }], file)
      })
      const bloc = await screen.findByRole('region', { name: 'En attente d’envoi' })
      await waitFor(() => expect(within(bloc).getByText('Rappeler la banque ce soir')).toBeInTheDocument())
    })

    it('R2-008b — décocher hors ligne : « Décocher attend le réseau » se VOIT, rien ne part, la case reste cochée', async () => {
      servir(donnees())
      monterConnecte()
      await screen.findByText('Devis Settat')
      api.post.mockClear()
      fixerEnLigne(false)
      await userEvent.click(screen.getByRole('button', { name: /^Faites/ }))
      const caseFaite = screen.getByRole('checkbox', { name: 'Marquer « Dossier subvention » comme faite' })
      await userEvent.click(caseFaite)
      expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Décocher attend le réseau')
      expect(caseFaite).toBeChecked()
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
      // R3-022 — la saisie ouverte porte déjà le brouillon : plus de « Reprendre » par-dessus
      expect(screen.queryByRole('region', { name: 'Brouillon' })).toBeNull()
      window.removeEventListener('taqinor:taches:saisir', ouverture)
      // à la fermeture (brouillon gardé), la carte revient
      act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:saisie-fermee')) })
      expect(await screen.findByRole('region', { name: 'Brouillon' })).toBeInTheDocument()
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
    const { container } = monter()
    const phrase = await screen.findByText('Colle ou dicte tes listes : je les range par projet.')
    // passe visuelle n° 20 — espace INSÉCABLE avant « : » (maquette ecran-aujourdhui-vide.html) : jamais « : » en tête de ligne
    expect(phrase.textContent).toBe('Colle ou dicte tes listes : je les range par projet.')
    await userEvent.click(screen.getByRole('button', { name: 'Coller mes listes' }))
    expect(ouverture).toHaveBeenCalledTimes(1)
    // journée vide : le bureau garde sa ligne « Ajouter une tâche » (le « + » du bureau), et elle ouvre la saisie
    const ligneBureau = container.querySelector('.saisie-bureau')
    expect(ligneBureau).toHaveTextContent('Ajouter une tâche')
    await userEvent.click(ligneBureau)
    expect(ouverture).toHaveBeenCalledTimes(2)
    window.removeEventListener('taqinor:taches:saisir', ouverture)
  })

  describe('R2-033 — « Coller mes listes » lit le presse-papiers', () => {
    const vide = () => Object.assign(donnees(), {
      essentiel: [], obligations: [], rendez_vous: [], journee: [], ce_soir: [], a_decider: [], en_attente: [], faites: [],
      a_trier: { boite_reception: 0, bloquees: 0, suggestions: 0, a_convertir: 0 },
      propose: { replie: false, pour_objectif: [], reste_nb: 0, charge: null, suite_par_projet: null },
    })
    const presse = (lire) => Object.defineProperty(window.navigator, 'clipboard', { value: { readText: lire }, configurable: true })
    // la saisie ouverte garde son brouillon (localStorage) : il prendrait la place de la carte du moment ensuite
    afterEach(() => { delete window.navigator.clipboard; window.localStorage.clear() })

    it('trois lignes copiées : la saisie s’ouvre AVEC elles (l’aperçu des listes), sans message', async () => {
      presse(vi.fn().mockResolvedValue('Salon\n- Stand\n- Kakémonos'))
      servir(vide())
      const ouverture = vi.fn()
      window.addEventListener('taqinor:taches:saisir', ouverture)
      monter()
      expect(await screen.findByText('ou touche + pour une tâche')).toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: 'Coller mes listes' }))
      await waitFor(() => expect(ouverture).toHaveBeenCalledTimes(1))
      expect(ouverture.mock.calls[0][0].detail).toEqual({ coller: true, texte: 'Salon\n- Stand\n- Kakémonos' })
      expect(screen.queryByText('Appuie longuement dans le champ puis Coller')).toBeNull()
      window.removeEventListener('taqinor:taches:saisir', ouverture)
    })

    it('lecture refusée : la saisie s’ouvre et le geste est dit « Appuie longuement dans le champ puis Coller »', async () => {
      presse(vi.fn().mockRejectedValue(Object.assign(new Error('refus'), { name: 'NotAllowedError' })))
      servir(vide())
      const ouverture = vi.fn()
      window.addEventListener('taqinor:taches:saisir', ouverture)
      monter()
      await userEvent.click(await screen.findByRole('button', { name: 'Coller mes listes' }))
      await waitFor(() => expect(ouverture).toHaveBeenCalledTimes(1))
      expect(ouverture.mock.calls[0][0].detail).toEqual({ coller: true })
      expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Appuie longuement dans le champ puis Coller')
      window.removeEventListener('taqinor:taches:saisir', ouverture)
    })
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

  it('Raccord F2 + R2-013 — ⋯ → En attente de… : la ligne passe dans « En attente » (2), Annuler la remet dans Prévu', async () => {
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
    const prevu = () => [...document.querySelectorAll('.section')].find((s) => s.textContent.startsWith('Prévu'))
    expect(prevu().querySelector('[data-ligne="tache:42"]')).toBeNull()
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('En attente de : Lydec')
    // R2-013 — la ligne PASSE dans « En attente » (compteur compris), sans relire la journée
    const enAttente = screen.getByRole('button', { name: /^En attente/ })
    expect(within(enAttente).getByText('2')).toBeInTheDocument()
    await userEvent.click(enAttente)
    expect(within(document.querySelector('.replies')).getByText('Timbres')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/gestes/88/annuler/', {}))
    await waitFor(() => expect(prevu().querySelector('[data-ligne="tache:42"]')).not.toBeNull())
    expect(within(screen.getByRole('button', { name: /^En attente/ })).getByText('1')).toBeInTheDocument()
    expect(document.querySelector('.replies [data-ligne="tache:42"]')).toBeNull()
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
    expect(screen.getByRole('button', { name: /^1 sur \d+[ .]/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Timbres »' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: /^Reporter à/ }))
    expect(await screen.findByRole('button', { name: /^2 sur \d+[ .]/ })).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  describe('R2-012 — la 4e étoile est refusée À L\'ÉCRAN, avant toute requête (étoile et menu)', () => {
    const PHRASE = "3 essentielles au plus — retire une étoile d'abord"
    const troisEtoiles = () => {
      const d = donnees()
      const autre = (id, titre) => ({ ...d.essentiel[0], id, titre, heure_debut: null })
      d.essentiel = [...d.essentiel, autre(301, 'Deuxième'), autre(302, 'Troisième')]
      return d
    }
    const appelsEtoile = () => api.post.mock.calls.filter(([url]) => url === '/taches/journee/essentiel/')

    it('l\'étoile vide d\'une ligne de Prévu : toast visible, aucune requête', async () => {
      servir(troisEtoiles())
      monter()
      await screen.findByText('Timbres')
      await userEvent.click(screen.getByRole('checkbox', { name: 'Essentielle : Timbres' }))
      expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent(PHRASE)
      expect(appelsEtoile()).toHaveLength(0)
    })

    it('le menu ⋯ > Essentielle : même refus, aucune requête', async () => {
      servir(troisEtoiles())
      monter()
      await screen.findByText('Timbres')
      await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Timbres »' }))
      await userEvent.click(await screen.findByRole('menuitem', { name: 'Essentielle' }))
      expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent(PHRASE)
      expect(appelsEtoile()).toHaveLength(0)
    })
  })

  describe('R2-011 — cocher, Annuler et reporter n\'attendent PAS le serveur (réponse retenue 2 s)', () => {
    const CASE = 'Marquer « Timbres » comme faite'
    const ecrite = (gesteId, extra = {}) => {
      const e = exempleContrat('taches', 'tache_ecrite')
      return { data: { ...e, tache: { ...e.tache, id: 42, statut: 'fait', lock_version: 2 }, geste_id: gesteId, progression: null, ...extra } }
    }
    /** `api.post` dont la réponse à `url` attend 2 s (minuteur factice) ; les autres répondent tout de suite. */
    function retarder(suffixe, reponse) {
      api.post.mockImplementation((url) => (url.endsWith(suffixe)
        ? new Promise((resolu, rejete) => setTimeout(() => (reponse instanceof Error ? rejete(reponse) : resolu(reponse)), 2000))
        : Promise.resolve(url.endsWith('/annuler/') ? { data: { restaurees: [{ objet: 'tache', id: 42 }], conflits: [], deja: false } } : { data: {} })))
    }
    async function monterLent({ figer = true } = {}) {
      servir(donnees())
      api.get.mockImplementation((url) => (url === '/taches/aujourdhui/' ? Promise.resolve({ data: donnees() })
        : url === '/taches/taches/42/' ? Promise.resolve({ data: { ...exempleContrat('taches', 'tache_ecrite').tache, id: 42, lock_version: 3 } })
          : Promise.reject(new Error(`appel inattendu : GET ${url}`))))
      monter()
      await screen.findByText('Devis Settat')
      if (figer) vi.useFakeTimers()
    }
    const attendre = (ms) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })
    const ligneTimbres = (container) => container.querySelector('[data-ligne="tache:42"]')

    it('cocher : barré, « 2 sur 5 » et le toast « Faite » AVANT la réponse ; la réponse ne change rien de visible', async () => {
      retarder('/terminer/', ecrite(80))
      await monterLent()
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(50)
      expect(screen.getByRole('checkbox', { name: CASE })).toBeChecked()
      expect(ligneTimbres(document).querySelector('.ligne.faite')).not.toBeNull() // barrée
      expect(screen.getByRole('button', { name: /^2 sur 5[ .]/ })).toBeInTheDocument()
      expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Faite')
      await attendre(2100)
      expect(screen.getByRole('checkbox', { name: CASE })).toBeChecked()
      expect(screen.getByRole('button', { name: /^2 sur 5[ .]/ })).toBeInTheDocument()
    })

    it('Annuler AVANT la réponse : la ligne et « 1 sur 5 » reviennent tout de suite, puis le geste rendu est annulé', async () => {
      retarder('/terminer/', ecrite(81))
      await monterLent()
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(50)
      fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
      await attendre(50)
      expect(screen.getByRole('checkbox', { name: CASE })).not.toBeChecked()
      expect(screen.getByRole('button', { name: /^1 sur 5[ .]/ })).toBeInTheDocument()
      expect(api.post).not.toHaveBeenCalledWith('/taches/gestes/81/annuler/', {})
      await attendre(2100)
      expect(api.post).toHaveBeenCalledWith('/taches/gestes/81/annuler/', {})
      expect(screen.getByRole('checkbox', { name: CASE })).not.toBeChecked()
      expect(screen.getByRole('button', { name: /^1 sur 5[ .]/ })).toBeInTheDocument()
    })

    it('le serveur refuse : la case et le compteur reviennent, et le refus s\'affiche', async () => {
      retarder('/terminer/', Object.assign(new Error('400'), { response: { status: 400, data: { detail: 'Tâche verrouillée.' } } }))
      await monterLent()
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(50)
      expect(screen.getByRole('checkbox', { name: CASE })).toBeChecked()
      await attendre(2100)
      expect(screen.getByRole('checkbox', { name: CASE })).not.toBeChecked()
      expect(screen.getByRole('button', { name: /^1 sur 5[ .]/ })).toBeInTheDocument()
      expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Tâche verrouillée.')
    })

    it('double toucher : décocher ferme le toast « Faite » et les deux écritures partent dans l\'ordre', async () => {
      retarder('/terminer/', ecrite(82))
      await monterLent()
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(50)
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(50)
      expect(screen.queryByRole('group', { name: 'Geste effectué' })).toBeNull()
      expect(screen.getByRole('checkbox', { name: CASE })).not.toBeChecked()
      expect(screen.getByRole('button', { name: /^1 sur 5[ .]/ })).toBeInTheDocument()
      await attendre(2100)
      const ecritures = api.post.mock.calls.map(([url]) => url).filter((url) => /\/42\/(terminer|rouvrir)\/$/.test(url))
      expect(ecritures).toEqual(['/taches/taches/42/terminer/', '/taches/taches/42/rouvrir/'])
      expect(ligneTimbres(document)).not.toBeNull()
      expect(screen.getByRole('checkbox', { name: CASE })).not.toBeChecked()
    })

    it('reporter : « → jeu. 19 » et le toast AU RELÂCHER, avant la réponse ; un refus les retire et le dit', async () => {
      retarder('/planifier/', Object.assign(new Error('500'), { response: { status: 500, data: { detail: 'Le serveur ne répond pas.' } } }))
      await monterLent({ figer: false })
      await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Timbres »' }))
      const reporter = await screen.findByRole('menuitem', { name: /^Reporter à/ })
      vi.useFakeTimers()
      fireEvent.click(reporter)
      await attendre(50)
      expect(ligneTimbres(document)).toHaveTextContent('→ jeu. 19')
      expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Reportée à jeu. 19')
      await attendre(2100)
      expect(ligneTimbres(document)).not.toHaveTextContent('→ jeu. 19')
      expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Le serveur ne répond pas.')
    })
  })

  describe('R2-010 — activité ERP cochée : envoi DIFFÉRÉ jusqu\'au départ du toast (choix C-9)', () => {
    const CASE = 'Marquer « Rappeler Benali » comme faite'
    const CLOSE = '/records/activities/101/done/'
    const appelsClose = () => api.post.mock.calls.filter(([url]) => url === CLOSE)
    async function monterActivite() {
      const d = donnees()
      d.journee.find((i) => i.type === 'activite').peut_cloturer = true
      servir(d)
      api.post.mockResolvedValue({ data: {} })
      const rendu = monter()
      await screen.findByText('Devis Settat')
      vi.useFakeTimers()
      return rendu
    }
    const attendre = (ms) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })

    it('cocher : la ligne passe cochée et le compteur +1 TOUT DE SUITE ; « Close dans l\'ERP · Annuler » ; rien ne part encore', async () => {
      await monterActivite()
      expect(screen.getByRole('button', { name: /^1 sur 5[ .]/ })).toBeInTheDocument()
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(0)
      expect(screen.getByRole('checkbox', { name: CASE })).toBeChecked()
      expect(screen.getByRole('button', { name: /^2 sur 5[ .]/ })).toBeInTheDocument()
      const toast = screen.getByRole('group', { name: 'Geste effectué' })
      expect(toast).toHaveTextContent("Close dans l'ERP")
      expect(within(toast).getByRole('button', { name: 'Annuler' })).toBeInTheDocument()
      expect(appelsClose()).toHaveLength(0)
    })

    it('Annuler : la ligne et le compteur reviennent, et RIEN ne part vers l\'ERP (même après le délai du toast)', async () => {
      await monterActivite()
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(0)
      fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
      await attendre(0)
      expect(screen.getByRole('checkbox', { name: CASE })).not.toBeChecked()
      expect(screen.getByRole('button', { name: /^1 sur 5[ .]/ })).toBeInTheDocument()
      await attendre(20000)
      expect(appelsClose()).toHaveLength(0)
    })

    it('sans Annuler : l\'activité est close à la disparition du toast (8 s), une seule fois, compteur juste sans relire', async () => {
      await monterActivite()
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(7900)
      expect(appelsClose()).toHaveLength(0)
      await attendre(200)
      expect(appelsClose()).toEqual([[CLOSE, {}]])
      await attendre(10000)
      expect(appelsClose()).toHaveLength(1)
      expect(screen.getByRole('checkbox', { name: CASE })).toBeChecked()
      expect(screen.getByRole('button', { name: /^2 sur 5[ .]/ })).toBeInTheDocument()
      expect(api.get.mock.calls.filter(([url]) => url === '/taches/aujourdhui/')).toHaveLength(1)
    })

    it('un autre geste remplace le toast : l\'activité part à ce moment-là (le toast a disparu)', async () => {
      await monterActivite()
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(0)
      fireEvent.click(screen.getByRole('checkbox', { name: 'Marquer « Timbres » comme faite' }))
      await attendre(0)
      expect(appelsClose()).toHaveLength(1)
    })

    it('l\'ERP refuse : la ligne et le compteur reviennent, et le refus s\'affiche', async () => {
      await monterActivite()
      api.post.mockImplementation((url) => (url === CLOSE
        ? Promise.reject(Object.assign(new Error('403'), { response: { status: 403, data: { detail: 'Action refusée.' } } }))
        : Promise.resolve({ data: {} })))
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(8100)
      expect(screen.getByRole('checkbox', { name: CASE })).not.toBeChecked()
      expect(screen.getByRole('button', { name: /^1 sur 5[ .]/ })).toBeInTheDocument()
      expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent("Pas close dans l'ERP : Action refusée.")
    })

    it('l\'onglet se ferme (`pagehide`) avant la fin du toast : la clôture part quand même, par un envoi qui survit à la page', async () => {
      const envoi = vi.fn(() => Promise.resolve({ ok: true, status: 200 }))
      vi.stubGlobal('fetch', envoi)
      try {
        await monterActivite()
        fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
        await attendre(0)
        act(() => { window.dispatchEvent(new Event('pagehide')) })
        await attendre(0)
        expect(envoi).toHaveBeenCalledTimes(1)
        const [url, options] = envoi.mock.calls[0]
        expect(url).toMatch(/\/api\/django\/records\/activities\/101\/done\/$/)
        expect(options).toMatchObject({ method: 'POST', keepalive: true, credentials: 'include' })
        // le toast est parti avec l'envoi : plus d'« Annuler » trompeur, et rien ne repart à son échéance
        expect(screen.queryByRole('button', { name: 'Annuler' })).toBeNull()
        await attendre(10000)
        expect(envoi).toHaveBeenCalledTimes(1)
        expect(appelsClose()).toHaveLength(0)
      } finally {
        vi.unstubAllGlobals()
      }
    })

    it('quitter l\'écran avant la fin du toast : la clôture part au démontage', async () => {
      const { unmount } = await monterActivite()
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(0)
      unmount()
      await attendre(0)
      expect(appelsClose()).toHaveLength(1)
    })

    it('décocher pendant le toast vaut Annuler : rien ne part', async () => {
      await monterActivite()
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(0)
      fireEvent.click(screen.getByRole('checkbox', { name: CASE }))
      await attendre(10000)
      expect(screen.getByRole('checkbox', { name: CASE })).not.toBeChecked()
      expect(appelsClose()).toHaveLength(0)
    })
  })
})

describe('Relecture adverse F4 — une essentielle faite est servie dans Essentiel ET dans Faites (regles.md §4.1 ligne 3, D-V1)', () => {
  /** L'échantillon, avec « Dossier subvention » (faite) portée par une ligne ★ : le serveur la sert dans les deux listes. */
  const journeeEssentielleFaite = () => {
    const d = donnees()
    const faite = { ...d.faites[0], essentielle: true }
    d.essentiel = [...d.essentiel, faite]
    d.faites = [faite]
    return d
  }
  const ecrite = (id, lockVersion, gesteId) => {
    const e = exempleContrat('taches', 'tache_ecrite')
    return { data: { ...e, tache: { ...e.tache, id, lock_version: lockVersion }, geste_id: gesteId, progression: null } }
  }
  const annulation = (id) => ({ data: { restaurees: [{ objet: 'tache', id }], conflits: [], deja: false } })
  const lignesDe = (zone, id) => (zone ? zone.querySelectorAll(`[data-ligne="tache:${id}"]`).length : 0)
  const zones = (container) => ({
    essentiel: container.querySelector('.section.premiere'),
    prevu: [...container.querySelectorAll('.section')].find((s) => s.textContent.startsWith('Prévu')),
    faites: container.querySelector('.replies'),
  })
  const ouvrirFaites = async () => userEvent.click(screen.getByRole('button', { name: /^Faites/ }))

  it('n° 1 — Supprimer une essentielle faite retire SES DEUX lignes ; Annuler remet les deux, chacune à sa place', async () => {
    servir(journeeEssentielleFaite())
    api.delete.mockResolvedValue({ data: { geste_id: 90 } })
    api.post.mockImplementation((url) => Promise.resolve(url === '/taches/gestes/90/annuler/' ? annulation(12) : { data: {} }))
    const { container } = monter()
    await screen.findByText('Devis Settat')
    await ouvrirFaites()
    expect(lignesDe(zones(container).essentiel, 12)).toBe(1)
    expect(lignesDe(zones(container).faites, 12)).toBe(1)
    await userEvent.click(screen.getAllByRole('button', { name: 'Actions pour « Dossier subvention »' })[0])
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Supprimer' }))
    const feuille = await screen.findByRole('dialog', { name: 'Supprimer' })
    await userEvent.click(within(feuille).getByRole('button', { name: 'Supprimer' }))
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/taches/taches/12/'))
    // aucune ligne fantôme : ni dans Essentiel, ni dans Faites
    expect(container.querySelectorAll('[data-ligne="tache:12"]')).toHaveLength(0)
    expect(screen.queryByRole('button', { name: /^Faites/ })).toBeNull()
    await userEvent.click(await screen.findByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/gestes/90/annuler/', {}))
    // les deux reviennent, chacune à son rang : Essentiel après « Devis Settat », et dans Faites
    await waitFor(() => expect(lignesDe(zones(container).essentiel, 12)).toBe(1))
    expect([...zones(container).essentiel.querySelectorAll('[data-ligne]')].map((n) => n.dataset.ligne)).toEqual(['tache:20', 'tache:12'])
    await ouvrirFaites()
    expect(lignesDe(zones(container).faites, 12)).toBe(1)
    expect(container.querySelectorAll('[data-ligne="tache:12"]')).toHaveLength(2)
  })

  it('n° 2 — ôter la ★ de la ligne barrée d\'Essentiel : elle quitte Essentiel SANS entrer dans Prévu, Faites perd sa ★ ; R2-027 : aucun toast', async () => {
    servir(journeeEssentielleFaite())
    api.post.mockImplementation((url) => Promise.resolve(url === '/taches/journee/essentiel/' ? ecrite(12, 6, 91) : { data: {} }))
    const { container } = monter()
    await screen.findByText('Devis Settat')
    await ouvrirFaites()
    await userEvent.click(within(zones(container).essentiel).getByRole('checkbox', { name: 'Essentielle : Dossier subvention' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/journee/essentiel/', { tache_id: 12, essentielle: false }))
    await waitFor(() => expect(lignesDe(zones(container).essentiel, 12)).toBe(0))
    // une faite sans ★ n'est QUE dans Faites (le serveur ne la sert jamais dans Prévu)
    expect(lignesDe(zones(container).prevu, 12)).toBe(0)
    const faite = zones(container).faites.querySelector('[data-ligne="tache:12"]')
    expect(faite).not.toBeNull()
    expect(within(faite).queryByRole('img', { name: 'Essentielle' })).toBeNull()
    // R2-027 — l'étoile vide suffit : pas de toast (retoucher l'étoile la remet)
    expect(screen.queryByRole('group', { name: 'Geste effectué' })).toBeNull()
  })

  it('n° 2 — remettre la ★ à une faite depuis Faites : elle apparaît AUSSI dans Essentiel, comme la relecture la servira ; R2-027 : aucun toast', async () => {
    servir(donnees())
    api.post.mockImplementation((url) => Promise.resolve(url === '/taches/journee/essentiel/' ? ecrite(12, 6, 92) : { data: {} }))
    const { container } = monter()
    await screen.findByText('Devis Settat')
    await ouvrirFaites()
    await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Dossier subvention »' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Essentielle' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/journee/essentiel/', { tache_id: 12, essentielle: true }))
    await waitFor(() => expect(lignesDe(zones(container).essentiel, 12)).toBe(1))
    expect(within(zones(container).essentiel).getByRole('checkbox', { name: 'Essentielle : Dossier subvention' })).toBeChecked()
    const faite = zones(container).faites.querySelector('[data-ligne="tache:12"]')
    expect(faite).not.toBeNull()
    expect(within(faite).getByRole('img', { name: 'Essentielle' })).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Geste effectué' })).toBeNull()
  })
})

describe('R2-019 / R2-035 — la progression compte ce que l\'écran montre, et se lit en une phrase', () => {
  it('R2-019 — reporter une ★ : « essentiel 0/2 » devient « essentiel 0/1 » tout de suite', async () => {
    const d = donnees()
    d.essentiel = [...d.essentiel, { ...d.essentiel[0], id: 23, titre: 'Payer la CNSS', heure_debut: null }]
    d.progression = { ...d.progression, essentiel_prevues: 2 }
    servir(d)
    api.post.mockResolvedValue({ data: { ...exempleContrat('taches', 'tache_ecrite'), geste_id: 73, progression: null } })
    monter()
    await screen.findByText('Devis Settat')
    expect(screen.getByRole('button', { name: /^1 sur 5 · essentiel 0\/2\./ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Payer la CNSS »' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: /^Reporter à/ }))
    expect(await screen.findByRole('button', { name: /^1 sur 5 · essentiel 0\/1\./ })).toBeInTheDocument()
    // Annuler : elle revient dans la journée affichée
    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(await screen.findByRole('button', { name: /^1 sur 5 · essentiel 0\/2\./ })).toBeInTheDocument()
  })

  it('R3-020 — au toucher : « 1 faite sur 5 », le temps contre le disponible ; ni « visées » ni « gardées » ni « (accepté) »', async () => {
    servir(donnees())
    monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('button', { name: /Détail de la journée$/ }))
    const detail = screen.getByRole('group', { name: 'Détail de la journée' })
    expect(detail).toHaveTextContent('1 faite sur 5')
    expect(detail).toHaveTextContent('Temps : 1 h 15 prévues pour 3 h disponibles · 1 sans durée')
    for (const absent of ['visée', 'gardée', 'accepté', 'Objectif du jour', 'Temps libre']) expect(detail).not.toHaveTextContent(absent)
  })

  it('R3-020 — « essentiel f/p » est celui que le serveur SERT (jamais recompté sur les lignes) ; une journée qui déborde le dit', async () => {
    const d = donnees()
    // trois ★ affichées, mais le serveur compte 1/2 (une gardée par son échéance, une reportée sans échéance…) : c'est lui qui dit
    d.essentiel = [...d.essentiel, { ...d.essentiel[0], id: 23, titre: 'Payer la CNSS', heure_debut: null }, { ...d.essentiel[0], id: 24, titre: 'Relire le bail', heure_debut: null }]
    d.progression = { ...d.progression, essentiel_faites: 1, essentiel_prevues: 2, minutes_prevues: 270, sans_estimation: 0, disponible_minutes: 240 }
    servir(d)
    const { container } = monter()
    await screen.findByText('Devis Settat')
    expect(container.querySelector('button.progression')).toHaveTextContent('1 sur 5 · essentiel 1/2')
    await userEvent.click(screen.getByRole('button', { name: /Détail de la journée$/ }))
    expect(screen.getByRole('group', { name: 'Détail de la journée' })).toHaveTextContent('Temps : 4 h 30 prévues pour 4 h disponibles · 30 min de trop')
  })

  it('R3-020 — cocher une ★ : « essentiel 1/1 » AU TOUCHER, puis la progression SERVIE par la réponse remplace tout', async () => {
    let lacher
    const porte = new Promise((r) => { lacher = r })
    const servie = { ...donnees().progression, faites: 2, essentiel_faites: 1, essentiel_prevues: 1, minutes_prevues: 15 }
    servir(donnees())
    api.post.mockImplementation((url) => (url === '/taches/taches/20/terminer/'
      ? porte.then(() => ({ data: { ...exempleContrat('taches', 'tache_ecrite'), geste_id: 75, progression: servie } }))
      : Promise.resolve({ data: {} })))
    const { container } = monter()
    await screen.findByText('Devis Settat')
    expect(container.querySelector('button.progression')).toHaveTextContent('1 sur 5 · essentiel 0/1')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Marquer « Devis Settat » comme faite' }))
    expect(container.querySelector('button.progression')).toHaveTextContent('2 sur 5 · essentiel 1/1') // la réponse est retenue
    await act(async () => { lacher() })
    await userEvent.click(screen.getByRole('button', { name: /Détail de la journée$/ }))
    expect(screen.getByRole('group', { name: 'Détail de la journée' })).toHaveTextContent('Temps : 15 min prévues pour 3 h disponibles')
  })

  it('R3-021 — reporter une tâche dont l\'échéance EST aujourd\'hui : la ligne reste et le dit ; « Repousser l\'échéance » envoie `echeance`', async () => {
    const d = donnees()
    d.essentiel = [{ ...d.essentiel[0], echeance: d.jour }]
    servir(d)
    const ecrite = exempleContrat('taches', 'tache_ecrite')
    api.post.mockResolvedValue({ data: { ...ecrite, tache: { ...ecrite.tache, id: 20, lock_version: 5 }, geste_id: 76,
      avertissements: [{ code: 'echeance_aujourdhui', message: "L'échéance reste aujourd'hui." }], progression: d.progression } })
    // la réponse du PATCH sert la progression d'après : la ★ a quitté Essentiel
    api.patch.mockResolvedValue({ data: { ...ecrite, tache: { ...ecrite.tache, id: 20, echeance: d.prochain_jour_ouvre, lock_version: 6 }, geste_id: 77,
      progression: { ...d.progression, essentiel_faites: 0, essentiel_prevues: 0 } } })
    const { container } = monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Devis Settat »' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: /^Reporter à/ }))
    const ligne = container.querySelector('[data-ligne="tache:20"]')
    expect(ligne).not.toBeNull()
    expect(ligne.closest('.ligne-reste')).not.toBeNull() // jamais le fondu de départ
    expect(ligne).toHaveTextContent("→ jeu. 19 · échéance aujourd'hui")
    expect(container.querySelector('button.progression')).toHaveTextContent('essentiel 0/1') // la ★ est affichée, donc comptée
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    expect(toast).toHaveTextContent("Prévue jeu. 19 — l'échéance reste aujourd'hui")
    await userEvent.click(within(toast).getByRole('button', { name: "Repousser l'échéance" }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/taches/taches/20/', { echeance: d.prochain_jour_ouvre, lock_version: 5 }))
    await waitFor(() => expect(container.querySelector('[data-ligne="tache:20"]')?.closest('.ligne-reste') ?? null).toBeNull())
    expect(container.querySelector('button.progression')).not.toHaveTextContent('essentiel 0/1')
  })

  it('R3-021 — une échéance PASSÉE ne garde rien : la ligne part comme tout report (`===`, pas `<=`)', async () => {
    const d = donnees()
    d.essentiel = [{ ...d.essentiel[0], echeance: '2026-11-10' }]
    servir(d)
    api.post.mockResolvedValue({ data: { ...exempleContrat('taches', 'tache_ecrite'), geste_id: 78, progression: null } })
    const { container } = monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Devis Settat »' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: /^Reporter à/ }))
    expect(container.querySelector('[data-ligne="tache:20"]').closest('.ligne-reste')).toBeNull()
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).not.toHaveTextContent("l'échéance reste")
    expect(container.querySelector('button.progression')).not.toHaveTextContent('essentiel')
  })

  it('R3-029 — premier jour (objectif par défaut) : « 1 faite », jamais « 1 sur 5 » ; le détail dit la valeur par défaut', async () => {
    const d = donnees()
    d.objectif = { ...d.objectif, source: 'defaut' }
    servir(d)
    const { container } = monter()
    await screen.findByText('Devis Settat')
    expect(container.querySelector('.progression-compte')).toHaveTextContent(/^1 faite$/)
    expect(container.querySelector('button.progression')).not.toHaveTextContent('sur 5')
    await userEvent.click(screen.getByRole('button', { name: /^1 faite\. Détail de la journée$/ }))
    const detail = screen.getByRole('group', { name: 'Détail de la journée' })
    expect(detail).toHaveTextContent('Objectif : valeur par défaut, pas encore calculée sur toi')
    expect(detail).not.toHaveTextContent('sur 5')
  })
})

describe('R2-021 / R2-025 — la fiche s\u2019ouvre sur sa cible (pli L4 : `section`, `focus`)', () => {
  /** L'adresse de l'écran : la coquille ouvre la fiche selon `?tache=…&section=…&focus=…`. */
  function Adresse() {
    const { search } = useLocation()
    return <output data-testid="adresse">{search}</output>
  }
  const monterAvecAdresse = () => render(
    <MemoryRouter initialEntries={['/taches/aujourdhui']}><Aujourdhui /><Adresse /></MemoryRouter>,
  )
  const adresse = () => new URLSearchParams(screen.getByTestId('adresse').textContent)

  it('R2-021 — À revoir dit la raison sous chaque ligne ; « Découper » ouvre la fiche sur sa section Découper', async () => {
    servir(donnees())
    monterAvecAdresse()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('button', { name: /^À revoir/ }))
    const zone = document.querySelector('.replies')
    expect(within(zone).getByText('reportée 3 fois')).toBeInTheDocument()
    await userEvent.click(within(zone).getByRole('button', { name: 'Découper' }))
    await waitFor(() => expect(adresse().get('tache')).toBe('50'))
    expect(adresse().get('section')).toBe('decouper')
  })

  it('R2-021 — sans explication servie, la raison vient du motif (« en retard depuis … »)', async () => {
    const d = donnees()
    d.a_decider = [{ ...d.a_decider[0], explication: '', motif: 'retard_ancien', jour_prevu: '2026-11-09', reports: 0 }]
    servir(d)
    monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('button', { name: /^À revoir/ }))
    expect(within(document.querySelector('.replies')).getByText(/^en retard depuis /)).toBeInTheDocument()
  })

  it('R2-025 — `e` ouvre la fiche curseur dans le TITRE', async () => {
    servir(donnees())
    monterAvecAdresse()
    await screen.findByText('Timbres')
    const focaliser = () => act(() => { document.querySelector('[data-ligne="tache:42"] .ligne-corps-bouton').focus() })
    focaliser()
    await userEvent.keyboard('e')
    await waitFor(() => expect(adresse().get('focus')).toBe('titre'))
    expect(adresse().get('tache')).toBe('42')
  })

  it('R2-025 — `h` ouvre la fiche sur le champ HEURE', async () => {
    servir(donnees())
    monterAvecAdresse()
    await screen.findByText('Timbres')
    act(() => { document.querySelector('[data-ligne="tache:42"] .ligne-corps-bouton').focus() })
    await userEvent.keyboard('h')
    await waitFor(() => expect(adresse().get('focus')).toBe('heure'))
    expect(adresse().get('tache')).toBe('42')
  })

  it('R3-028 — `d` (ou `e`, `h`) sur une activité ERP le DIT : « Une activité ERP s\'ouvre dans l\'ERP · Ouvrir »', async () => {
    function Chemin() { const { pathname, search } = useLocation(); return <output data-testid="chemin">{pathname + search}</output> }
    servir(donnees())
    render(<MemoryRouter initialEntries={['/taches/aujourdhui']}><Aujourdhui /><Chemin /></MemoryRouter>)
    await screen.findByText('Rappeler Benali')
    act(() => { document.querySelector('[data-ligne="activite:101"] .ligne-corps-bouton').focus() })
    await userEvent.keyboard('d')
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    expect(toast).toHaveTextContent("Une activité ERP s'ouvre dans l'ERP")
    expect(screen.queryByRole('dialog', { name: 'Quand ?' })).toBeNull()
    await userEvent.click(within(toast).getByRole('button', { name: 'Ouvrir' }))
    await waitFor(() => expect(screen.getByTestId('chemin')).toHaveTextContent('/crm/leads?lead=1637'))
  })

  it('R3-023 — `?ouvrir=alleger` (carte « Ta journée déborde » du Copilote) ouvre « Alléger ma journée » ; la fermer ôte le paramètre', async () => {
    servir(donnees())
    render(<MemoryRouter initialEntries={['/taches/aujourdhui?ouvrir=alleger']}><Aujourdhui /><Adresse /></MemoryRouter>)
    const feuille = await screen.findByRole('dialog', { name: 'Alléger ma journée' })
    expect(feuille).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(adresse().get('ouvrir')).toBeNull())
    expect(screen.queryByRole('dialog', { name: 'Alléger ma journée' })).toBeNull()
  })

  it('R3-028 — Entrée sur une activité ERP SANS adresse le dit aussi (jamais rien sans un mot)', async () => {
    const d = donnees()
    d.journee = d.journee.map((it) => (it.type === 'activite' ? { ...it, lien: null } : it))
    servir(d)
    monter()
    await screen.findByText('Rappeler Benali')
    act(() => { document.querySelector('[data-ligne="activite:101"] .ligne-corps-bouton').focus() })
    await userEvent.keyboard('{Enter}')
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    expect(toast).toHaveTextContent("Une activité ERP s'ouvre dans l'ERP")
    expect(within(toast).queryByRole('button', { name: 'Ouvrir' })).toBeNull()
  })
})

describe('R2-014b —« Oui » de la carte « tâches reportées » (constat C7) mène à « À revoir »', () => {
  it('Oui : « À revoir » se déplie (aria-expanded) et vient à l\'écran', async () => {
    const d = donnees()
    // la carte elle-même (son type, sa question) est rendue par ui/CarteDuMoment (lane L3) : ici, le chemin de la RÉPONSE
    d.carte_du_moment = {
      type: 'rythme',
      proposition: {
        id: 55, type: 'constat', cle: 'C7', texte: '1 tâche reportée 3 fois ou plus. Les revoir maintenant ?', donnees: { n: 1 },
        boutons: [{ reponse: 'oui', libelle: 'Oui' }, { reponse: 'pas_maintenant', libelle: 'Pas maintenant' }], expire_le: null,
      },
      donnees: {},
    }
    servir(d)
    api.post.mockResolvedValue({ data: { ...exempleContrat('taches', 'proposition_repondue') } })
    const defiler = vi.fn()
    Element.prototype.scrollIntoView = defiler
    monter()
    await screen.findByText('Devis Settat')
    const aRevoir = screen.getByRole('button', { name: /^À revoir/ })
    expect(aRevoir).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(screen.getByRole('button', { name: 'Oui' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/rythme/propositions/55/repondre/', { reponse: 'oui' }))
    await waitFor(() => expect(screen.getByRole('button', { name: /^À revoir/ })).toHaveAttribute('aria-expanded', 'true'))
    expect(screen.getByText('Site web')).toBeInTheDocument()
    expect(defiler).toHaveBeenCalled()
    delete Element.prototype.scrollIntoView
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
    const feuille = await screen.findByRole('dialog', { name: 'Quand ?' })
    // R2-022 — le sélecteur « Quand » du module ; la tuile « Reporter à jeu. 19 » a le focus : Entrée reporte
    expect(within(feuille).getByRole('radio', { name: 'Reporter à jeu. 19' })).toHaveFocus()
    await userEvent.keyboard('{Enter}')
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/42/planifier/', expect.objectContaining({ jour_prevu: '2026-11-19', lock_version: expect.anything() })))
    expect(screen.queryByRole('dialog', { name: 'Quand ?' })).toBeNull()
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Reportée à jeu. 19')
  })

  it('R2-022 — « Choisir un jour » : les tuiles du sélecteur Quand ; « Demain » en UN toucher', async () => {
    servir(donnees())
    api.post.mockResolvedValue({ data: { ...exempleContrat('taches', 'tache_ecrite'), geste_id: 74, progression: null } })
    monter()
    await screen.findByText('Timbres')
    await userEvent.click(screen.getByRole('button', { name: 'Actions pour « Timbres »' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Choisir un jour' }))
    const feuille = await screen.findByRole('dialog', { name: 'Quand ?' })
    const tuiles = within(feuille).getAllByRole('radio').map((t) => t.querySelector('b').textContent)
    expect(tuiles).toEqual(["Aujourd'hui", 'Demain', 'Ce soir', 'Reporter à jeu. 19', 'Calendrier…', 'En réserve', 'Sans jour'])
    await userEvent.click(within(feuille).getByRole('radio', { name: /^Demain/ }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/42/planifier/', expect.objectContaining({ jour_prevu: '2026-11-18' })))
    expect(screen.queryByRole('dialog', { name: 'Quand ?' })).toBeNull()
    expect(document.querySelector('[data-ligne="tache:42"]')).toHaveTextContent('→ mer. 18')
  })

  it('couture r2 (R2-040) — « Fait » dans la fiche : la ligne se barre SUR PLACE, comme une case cochée (pas de relecture qui la range dans « Faites » replié)', async () => {
    servir(donnees())
    monter()
    await screen.findByText('Timbres')
    const lectures = api.get.mock.calls.filter(([url]) => url === '/taches/aujourdhui/').length
    act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:ecrite', { detail: { tache: { id: 42, statut: 'fait', lock_version: 9 } } })) })
    await waitFor(() => expect(document.querySelector('[data-ligne="tache:42"] .ligne.faite')).not.toBeNull())
    expect(api.get.mock.calls.filter(([url]) => url === '/taches/aujourdhui/')).toHaveLength(lectures)
    // toute autre écriture de la fiche relit la journée (R2-040 : Quand › Aujourd'hui fait ARRIVER une ligne)
    act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:ecrite', { detail: { tache: { id: 99, statut: 'a_faire' } } })) })
    await waitFor(() => expect(api.get.mock.calls.filter(([url]) => url === '/taches/aujourdhui/').length).toBeGreaterThan(lectures))
  })

  it('couture r2 — `*` rend la ligne essentielle ET le focus la suit dans « Essentiel » (jamais perdu sur la page)', async () => {
    servir(donnees())
    const ecrite = exempleContrat('taches', 'tache_ecrite')
    api.post.mockImplementation((url) => Promise.resolve(url === '/taches/journee/essentiel/'
      ? { data: { ...ecrite, tache: { ...ecrite.tache, id: 42, essentielle: true }, progression: donnees().progression } }
      : { data: {} }))
    monter()
    await screen.findByText('Timbres')
    focaliser(42)
    await userEvent.keyboard('*')
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/journee/essentiel/', { tache_id: 42, essentielle: true }))
    await waitFor(() => expect(document.activeElement.closest('[data-ligne="tache:42"]')).not.toBeNull())
  })

  it('`m` ouvre « Changer de projet » sur un AUTRE projet que le sien ; Entrée déplace', async () => {
    servir(donnees())
    const autres = { results: [{ id: 3, nom: 'Ventes', couleur: 'indigo', priorite: 1 }, { id: 7, nom: 'Salon', couleur: 'vert', priorite: 2 }], next: null, count: 2 }
    api.get.mockImplementation((url) => Promise.resolve({ data: url === '/taches/projets/' ? autres : donnees() }))
    api.post.mockResolvedValue({ data: { geste_id: 72, refusees: [] } })
    monter()
    await screen.findByText('Devis Settat')
    focaliser(20)
    await userEvent.keyboard('m')
    const feuille = await screen.findByRole('dialog', { name: 'Changer de projet' })
    expect(within(feuille).getByRole('combobox', { name: 'Chercher un projet' })).toHaveFocus()
    // Entrée frappée avant même l'arrivée de la liste des projets : elle n'est pas perdue
    await userEvent.keyboard('{Enter}')
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/lot/', expect.objectContaining({
      ids: [20], action: 'deplacer', valeurs: { projet_id: 7 },
    }), expect.anything()))
  })
})
