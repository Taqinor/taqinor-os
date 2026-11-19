import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../lib/gestes'
import VueChronologie, { Burnup } from './VueChronologie'
import Tableau from '../ui/Tableau'
import { poserRectangles } from './rectanglesDeTest'

vi.mock('../../../api/tachesApi', async (original) => ({
  ...(await original()),
  lireVueProjet: vi.fn(),
  modifierProjet: vi.fn(),
  modifierTache: vi.fn(),
  annulerGeste: vi.fn(),
  listerToutesLesTaches: vi.fn(),
  listerTousLesProjets: vi.fn(),
}))

const api = await import('../../../api/tachesApi')
const { default: Projet } = await import('../../../pages/taches/Projet')

/* TCH90 — vues Tableau et Chronologie d'un projet (mémorisées dans `affichage.vue`), burn-up. Tout est lu de
   `projet_vue.json` (`exempleContrat`) : une étape, un jalon, l'échéance du projet, `burnup`. La vue mémorisée se
   prouve par « enregistrer → rouvrir → enregistrer sans toucher » : l'objet du SERVEUR (un faux serveur en mémoire
   qui applique le PATCH comme le vrai) ne bouge plus au second passage. */

const AUJOURDHUI = '2026-11-17'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(`${AUJOURDHUI}T09:00:00`))
  reinitialiserGestes()
})
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks(); reinitialiserGestes() })

/** La vue servie, avec une étape datée, un jalon, une tâche sans date et l'échéance du projet. */
function vueDatee() {
  const vue = structuredClone(exempleContrat('taches', 'projet_vue'))
  vue.sections[0].date_debut = '2026-11-09'
  vue.sections[0].taches[0].jalon = true
  vue.sections[0].taches[0].echeance = '2026-11-19'
  vue.projet.echeance = '2026-12-15'
  vue.sans_section[0].jour_prevu = null
  vue.sans_section[0].echeance = null
  return vue
}

describe('TCH90 — Chronologie', () => {
  it('range étapes, jalon, aujourd\'hui et échéance par date, avec « Sans date » et les comptes SERVIS', () => {
    render(<VueChronologie vue={vueDatee()} aujourdhui={AUJOURDHUI} />)
    const frise = screen.getByRole('list', { name: 'Chronologie du projet jusqu\'à l\'échéance' })
    const lignes = within(frise).getAllByRole('listitem').map((l) => l.textContent)
    expect(lignes).toEqual([
      expect.stringContaining('Études'),
      expect.stringContaining("Aujourd'hui"),
      expect.stringContaining('Devis Settat'),
      expect.stringContaining('Échéance du projet'),
    ])
    expect(lignes[0]).toContain('lun. 9 nov. → lun. 30 nov.') // R3-130 : UNE forme de date (« lun. 9 nov. », plus « lun. 09/11 »)
    expect(lignes[0]).toContain('4 sur 5') // 4 faites, 1 ouverte : `compteurs` du serveur, jamais recompté
    expect(lignes[2]).toContain('Jalon')
    expect(lignes[3]).toContain('mar. 15 déc.')
    expect(screen.getByText('Sans date :').parentElement).toHaveTextContent('Sans date : Timbres')
  })

  it('R3-130 — une étape sans date va tout à la FIN, « Sans date » en dernier (jamais au milieu, à la place d\'aujourd\'hui)', () => {
    const vue = vueDatee()
    vue.sections[0].date_debut = null
    vue.sections[0].date_fin = null
    render(<VueChronologie vue={vue} aujourdhui={AUJOURDHUI} />)
    const frise = screen.getByRole('list', { name: 'Chronologie du projet jusqu\'à l\'échéance' })
    const lignes = within(frise).getAllByRole('listitem').map((l) => l.textContent)
    expect(lignes).toEqual([
      expect.stringContaining("Aujourd'hui"), expect.stringContaining('Devis Settat'), expect.stringContaining('Échéance du projet'),
      expect.stringContaining('Sans date'),
    ])
  })

  it('R3-130 — un seul format de date partout : « mer. 18 nov. » (axe, jalon, étape, échéance, aujourd\'hui) — jamais « 18/11 »', () => {
    const { container } = render(<VueChronologie vue={vueDatee()} aujourdhui={AUJOURDHUI} />)
    const texte = container.textContent
    expect(texte).not.toMatch(/\d{2}\/\d{2}/)
    const axe = container.querySelector('.ep-fh-axe')
    expect(axe).toHaveTextContent('lun. 9 nov.')
    expect(axe).toHaveTextContent('mar. 15 déc.')
    expect(container.querySelector('.ep-f-item.auj .ep-f-date')).toHaveTextContent("Aujourd'hui · mar. 17 nov.")
  })

  it('R3-130 — le retard est marqué : une étape dont la fin est passée, une tâche datée avant aujourd\'hui, un jalon dépassé', () => {
    const vue = vueDatee()
    vue.sections[0].date_fin = '2026-11-12' // fin AVANT aujourd'hui (17/11), non faite (4 sur 5)
    vue.sections[0].taches[0].echeance = '2026-11-15' // le jalon est dépassé
    const base = vue.sections[0].taches[0]
    vue.sections[0].taches.push({ ...base, id: 31, titre: 'Mesurer le toit', jalon: false, echeance: null, jour_prevu: '2026-11-13' })
    const { container } = render(<VueChronologie vue={vue} aujourdhui={AUJOURDHUI} />)
    expect(container.querySelector('.ep-f-item.etape')).toHaveClass('retard')
    expect(container.querySelector('.ep-f-item.jalon')).toHaveClass('retard')
    expect(container.querySelector('.ep-f-taches li')).toHaveClass('retard')
    expect(container.querySelector('.ep-fh-nom-point')).toHaveClass('retard') // 9 → 12 nov. : trop court pour une barre, son nom est en alerte
    expect(container.querySelector('.ep-fh-point')).toHaveClass('retard')
    // à venir : jamais marqué
    const aVenir = vueDatee()
    const { container: c2 } = render(<VueChronologie vue={aVenir} aujourdhui={AUJOURDHUI} />)
    expect(c2.querySelector('.ep-f-item.retard')).toBeNull()
  })

  it('R3-130 — bureau : une étape SANS dates à elle a sa barre du premier au dernier jour de ses tâches datées ; un seul jour = un point et son nom', () => {
    const vue = vueDatee()
    const base = vue.sections[0].taches[0]
    vue.sections[0].date_debut = null
    vue.sections[0].date_fin = null
    vue.sections[0].taches = [
      { ...base, id: 51, titre: 'Mesurer', jalon: false, echeance: null, jour_prevu: '2026-11-18' },
      { ...base, id: 52, titre: 'Commander', jalon: false, echeance: null, jour_prevu: '2026-12-10' },
    ]
    vue.sections.push({ ...vue.sections[0], id: 9, nom: 'Pose', compteurs: { ouvertes: 1, faites: 0 },
      taches: [{ ...base, id: 53, titre: 'Poser la structure', jalon: false, echeance: null, jour_prevu: '2026-11-20' }] })
    const { container } = render(<VueChronologie vue={vue} aujourdhui={AUJOURDHUI} />)
    const piste = container.querySelector('.ep-frise-h')
    const barres = [...piste.querySelectorAll('.ep-fh-barre')]
    expect(barres.map((b) => b.textContent)).toEqual(['Études']) // 18/11 → 10/12 : large, une barre
    expect(piste.querySelectorAll('.ep-fh-rang .ep-fh-point').length).toBe(3) // 2 points sur la barre, 1 point d'« une journée »
    // « Pose » : un jour, pas de barre — un point et son nom, sur la même ligne (`ep-fh-nom-point`)
    expect(piste.querySelector('.ep-fh-nom-point')).toHaveTextContent('Pose')
  })

  it('dessine la piste du bureau : barre de l\'étape, jalon, traits « aujourd\'hui » et « échéance »', () => {
    render(<VueChronologie vue={vueDatee()} aujourdhui={AUJOURDHUI} />)
    const piste = screen.getByRole('group', { name: /Chronologie : étapes et jalons/ })
    expect(within(piste).getByText('Études')).toBeInTheDocument()
    // passe visuelle n° 40 : la date d'un jalon a son mois, comme l'échéance (« jeu. 19 nov. », plus « jeu. 19 »)
    expect(within(piste).getByText('Devis Settat · jeu. 19 nov.')).toBeInTheDocument()
    expect(within(piste).getByText(/Échéance · mar\. 15 déc\./)).toBeInTheDocument()
    expect(within(piste).getByText(/Aujourd'hui · mar\. 17/)).toBeInTheDocument()
  })
})

describe('R2-066 — Chronologie : les tâches datées et les étapes sans date', () => {
  /** « Études » (datée) porte deux tâches datées ; « Pose » n'a aucune date mais une tâche datée ; « Livraison » rien. */
  function vueRiche() {
    const vue = vueDatee()
    const base = vue.sections[0].taches[0]
    vue.sections[0].taches = [
      base,
      { ...base, id: 31, titre: 'Mesurer le toit', jalon: false, echeance: null, jour_prevu: '2026-11-20' },
      { ...base, id: 32, titre: 'Commander le câble', jalon: false, echeance: null, jour_prevu: '2026-11-21' },
    ]
    vue.sections.push({ ...vue.sections[0], id: 9, nom: 'Pose', date_debut: null, date_fin: null, compteurs: { ouvertes: 1, faites: 0 },
      taches: [{ ...base, id: 33, titre: 'Poser la structure', jalon: false, echeance: null, jour_prevu: '2026-11-28' }] })
    vue.sections.push({ ...vue.sections[0], id: 10, nom: 'Livraison', date_debut: null, date_fin: null, compteurs: { ouvertes: 0, faites: 0 },
      taches: [] })
    return vue
  }

  it('iPhone : les tâches datées d\'une étape se lisent sous elle, avec leur jour', () => {
    render(<VueChronologie vue={vueRiche()} aujourdhui={AUJOURDHUI} />)
    const frise = screen.getByRole('list', { name: 'Chronologie du projet jusqu\'à l\'échéance' })
    const etudes = within(frise).getAllByRole('listitem').find((l) => l.textContent.includes('Études'))
    expect(etudes).toHaveTextContent('Mesurer le toit')
    expect(etudes).toHaveTextContent('ven. 20 nov.')
    expect(etudes).toHaveTextContent('Commander le câble')
    const pose = within(frise).getAllByRole('listitem').find((l) => l.textContent.includes('Pose'))
    expect(pose).toHaveTextContent('Poser la structure')
  })

  it("iPhone : des étapes sans date à la suite portent « Sans date » UNE seule fois, en tête du groupe", () => {
    render(<VueChronologie vue={vueRiche()} aujourdhui={AUJOURDHUI} />)
    const frise = screen.getByRole('list', { name: "Chronologie du projet jusqu'à l'échéance" })
    const items = within(frise).getAllByRole('listitem')
    const pose = items.find((l) => l.textContent.includes('Pose'))
    const livraison = items.find((l) => l.textContent.includes('Livraison'))
    expect(pose).toHaveTextContent('Sans date')
    expect(livraison).not.toHaveTextContent('Sans date')
    expect(items.filter((l) => l.textContent.includes('Sans date'))).toHaveLength(1)
  })

  it('bureau : un point par jour de tâche sur la piste, groupé par étape ; une étape sans date ni tâche datée va dans « Sans date »', () => {
    render(<VueChronologie vue={vueRiche()} aujourdhui={AUJOURDHUI} />)
    const piste = screen.getByRole('group', { name: /Chronologie : étapes et jalons/ })
    expect(within(piste).getByRole('img', { name: 'Mesurer le toit · ven. 20 nov.' })).toBeInTheDocument()
    expect(within(piste).getByRole('img', { name: 'Commander le câble · sam. 21 nov.' })).toBeInTheDocument()
    expect(within(piste).getByRole('img', { name: 'Poser la structure · sam. 28 nov.' })).toBeInTheDocument()
    // l'étape « Pose » (sans date) a sa rangée, nommée ; « Livraison » (rien de daté) est dite « Sans date »
    expect(within(piste).getAllByText('Pose').length).toBeGreaterThan(0)
    expect(within(piste).getByText('Sans date :').parentElement).toHaveTextContent('Livraison')
  })

  it('les pastilles « aujourd\'hui » et « échéance » restent dans le cadre : celle du bord prend le côté intérieur', () => {
    // aujourd'hui = le 09/11, début de l'axe ; l'échéance (15/12) en est la fin : les deux pastilles sont aux bords
    render(<VueChronologie vue={vueDatee()} aujourdhui="2026-11-09" />)
    const piste = screen.getByRole('group', { name: /Chronologie : étapes et jalons/ })
    const auj = piste.querySelector('.ep-fh-trait.auj')
    expect(auj.className).toMatch(/bord-g/) // 09/11 = le début de l'axe
    const fin = piste.querySelector('.ep-fh-trait.fin')
    expect(fin.className).toMatch(/bord-d/) // fin de l'axe
  })

  it("un point au premier jour de l'axe, comme au dernier, est posé par une position BORNÉE au cadre (le CSS la borne : preuve sur capture)", () => {
    // axe : 09/11 (début de l'étape) → 15/12 (échéance) ; une tâche datée le 09/11 et une le 15/12 tombent sur les bords
    const vue = vueDatee()
    const base = vue.sections[0].taches[0]
    vue.sections[0].taches = [
      base,
      { ...base, id: 41, titre: 'Premier jour', jalon: false, echeance: null, jour_prevu: '2026-11-09' },
      { ...base, id: 42, titre: 'Dernier jour', jalon: false, echeance: null, jour_prevu: '2026-12-15' },
    ]
    render(<VueChronologie vue={vue} aujourdhui={AUJOURDHUI} />)
    const piste = screen.getByRole('group', { name: /Chronologie : étapes et jalons/ })
    expect(within(piste).getByRole('img', { name: /Premier jour/ }).style.getPropertyValue('--x')).toBe('0.00%')
    expect(within(piste).getByRole('img', { name: /Dernier jour/ }).style.getPropertyValue('--x')).toBe('100.00%')
  })
})

describe('TCH90 — Burn-up « Avancement par semaine »', () => {
  it('rend les points SERVIS et la légende du serveur', () => {
    render(<Burnup vue={exempleContrat('taches', 'projet_vue')} aujourdhui={AUJOURDHUI} />)
    const liste = screen.getByRole('list', { name: 'Avancement par semaine' })
    expect(within(liste).getAllByRole('listitem')).toHaveLength(1)
    expect(liste).toHaveTextContent('10 sur 18')
    expect(screen.getByText('reconstruit depuis les dates actuelles')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Avancement par semaine/ })).toBeInTheDocument()
  })

  it('autant de points que de semaines servies, sans légende si le serveur n\'en sert pas', () => {
    const vue = exempleContrat('taches', 'projet_vue')
    vue.burnup = [{ semaine: '2026-11-02', total: 10, faites: 4 }, { semaine: '2026-11-09', total: 18, faites: 10 }]
    vue.burnup_legende = null
    render(<Burnup vue={vue} aujourdhui={AUJOURDHUI} />)
    expect(within(screen.getByRole('list', { name: 'Avancement par semaine' })).getAllByRole('listitem')).toHaveLength(2)
    expect(screen.queryByText(/reconstruit/)).toBeNull()
  })
})

/** Un faux serveur : `lireVueProjet` rend l'objet mémorisé, `modifierProjet` l'écrit (verrou compris) comme le vrai. */
function fauxServeur() {
  const serveur = { vue: structuredClone(exempleContrat('taches', 'projet_vue')) }
  api.lireVueProjet.mockImplementation(async () => ({ data: structuredClone(serveur.vue) }))
  api.modifierProjet.mockImplementation(async (id, corps) => {
    const projet = serveur.vue.projet
    if (corps.lock_version !== projet.lock_version) throw Object.assign(new Error('conflit'), { response: { status: 409, data: { code: 'conflit_version' } } })
    serveur.vue.projet = { ...projet, affichage: { ...projet.affichage, ...corps.affichage }, lock_version: projet.lock_version + 1 }
    return { data: structuredClone(serveur.vue.projet) }
  })
  return serveur
}

const monter = (chemin = '/taches/projets/3') => render(
  <MemoryRouter initialEntries={[chemin]}>
    <Routes><Route path="/taches/projets/:id" element={<Projet />} /></Routes>
  </MemoryRouter>,
)

describe('TCH90 — la vue choisie est mémorisée côté serveur (affichage.vue)', () => {
  it('enregistrer → rouvrir → enregistrer sans toucher : l\'objet du serveur ne bouge plus', async () => {
    const serveur = fauxServeur()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const premier = monter()
    const choix = await screen.findByRole('radiogroup', { name: 'Vue' })
    expect(within(choix).getByRole('radio', { name: 'Liste' })).toBeChecked()

    await user.click(within(choix).getByRole('radio', { name: 'Chronologie' })) // 1. enregistrer
    await waitFor(() => expect(serveur.vue.projet.affichage.vue).toBe('chronologie'))
    expect(api.modifierProjet).toHaveBeenCalledWith(3, expect.objectContaining({
      affichage: expect.objectContaining({ vue: 'chronologie', tri: 'manuel', groupe: 'section' }), lock_version: 4,
    }))
    expect(serveur.vue.projet.lock_version).toBe(5)
    expect(screen.getByRole('list', { name: 'Chronologie du projet jusqu\'à l\'échéance' })).toBeInTheDocument()
    premier.unmount()

    monter() // 2. rouvrir : sans `?vue=`, la vue mémorisée revient d'elle-même
    expect(await screen.findByRole('list', { name: 'Chronologie du projet jusqu\'à l\'échéance' })).toBeInTheDocument()
    expect(within(screen.getByRole('radiogroup', { name: 'Vue' })).getByRole('radio', { name: 'Chronologie' })).toBeChecked()

    const apres = structuredClone(serveur.vue.projet)
    api.modifierProjet.mockClear()
    await user.click(within(screen.getByRole('radiogroup', { name: 'Vue' })).getByRole('radio', { name: 'Chronologie' })) // 3. sans toucher
    expect(api.modifierProjet).not.toHaveBeenCalled()
    expect(serveur.vue.projet).toEqual(apres)
  })

  it('une vue de l\'adresse (?vue=tableau) s\'affiche sans rien écrire ; la choisir la mémorise', async () => {
    const serveur = fauxServeur()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    monter('/taches/projets/3?vue=tableau')
    expect(await screen.findByRole('region', { name: 'Études' })).toBeInTheDocument()
    expect(screen.getByRole('tablist', { name: 'Étapes' })).toBeInTheDocument()
    expect(api.modifierProjet).not.toHaveBeenCalled()
    await user.click(within(screen.getByRole('radiogroup', { name: 'Vue' })).getByRole('radio', { name: 'Tableau' }))
    await waitFor(() => expect(serveur.vue.projet.affichage.vue).toBe('tableau'))
    expect(api.modifierProjet).toHaveBeenCalledTimes(1)
  })

  it('un refus du serveur remet la vue d\'avant et le dit', async () => {
    const serveur = fauxServeur()
    api.modifierProjet.mockRejectedValue({ response: { status: 400, data: { detail: 'Valeur inconnue.' } } })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    monter()
    await user.click(within(await screen.findByRole('radiogroup', { name: 'Vue' })).getByRole('radio', { name: 'Tableau' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(serveur.vue.projet.affichage.vue).toBe('liste')
  })

  it('« Avancement par semaine » s\'ouvre depuis le ⋯ du projet avec le burn-up servi', async () => {
    fauxServeur()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    monter()
    await screen.findByRole('radiogroup', { name: 'Vue' })
    await user.click(screen.getByRole('button', { name: /Plus d'actions|Plus/ }))
    await user.click(await screen.findByRole('menuitem', { name: 'Avancement par semaine' }))
    expect(await screen.findByText('10 sur 18')).toBeInTheDocument()
  })
})

describe('TCH90 — Tableau : déplacer une carte au clavier (kanbanA11y.js)', () => {
  let rendre
  beforeEach(() => { rendre = poserRectangles() })
  afterEach(() => rendre())

  // dnd-kit n'écoute le clavier qu'un tour d'horloge APRÈS la saisie : chaque touche attend ce tour.
  const touche = async (cible, code) => {
    await act(async () => {
      fireEvent.keyDown(cible, { code, key: code === 'Space' ? ' ' : code })
      await new Promise((fin) => { setTimeout(fin, 15) })
    })
  }
  const deplacerAuClavier = async (poignee) => {
    poignee.focus()
    await touche(poignee, 'Space')
    await touche(document, 'ArrowRight')
    await touche(document, 'Space')
  }

  it('une colonne par étape puis « Sans étape » ; la poignée porte les instructions et les annonces en français', () => {
    render(<Tableau vue={exempleContrat('taches', 'projet_vue')} aujourdhui={AUJOURDHUI} onDeplacer={vi.fn()} onTerminer={vi.fn()}
      onOuvrir={vi.fn()} onAction={vi.fn()} onAjouter={vi.fn()} onAnnonce={vi.fn()} />)
    expect(within(screen.getByRole('region', { name: 'Études' })).getByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Sans étape' })).getByRole('button', { name: 'Timbres' })).toBeInTheDocument()
    expect(screen.getAllByText('4 sur 5').length).toBeGreaterThan(0) // l'onglet et l'en-tête de colonne : le compte SERVI
    const poignee = screen.getByRole('button', { name: 'Déplacer « Devis Settat »' })
    const aide = document.getElementById(poignee.getAttribute('aria-describedby'))
    expect(aide).toHaveTextContent('Pour déplacer une carte au clavier')
  })

  it('Espace, → puis Espace : la carte change de colonne (onDeplacer reçoit la tâche et l\'étape cible)', async () => {
    const onDeplacer = vi.fn()
    render(<Tableau vue={exempleContrat('taches', 'projet_vue')} aujourdhui={AUJOURDHUI} onDeplacer={onDeplacer} onTerminer={vi.fn()}
      onOuvrir={vi.fn()} onAction={vi.fn()} onAjouter={vi.fn()} onAnnonce={vi.fn()} />)
    await deplacerAuClavier(screen.getByRole('button', { name: 'Déplacer « Devis Settat »' }))
    await waitFor(() => expect(onDeplacer).toHaveBeenCalledTimes(1))
    expect(onDeplacer.mock.calls[0][0].id).toBe(20)
    expect(onDeplacer.mock.calls[0][1]).toBeNull() // « Sans étape »
  })

  it('déposer dans la même colonne n\'écrit rien', async () => {
    const onDeplacer = vi.fn()
    render(<Tableau vue={exempleContrat('taches', 'projet_vue')} aujourdhui={AUJOURDHUI} onDeplacer={onDeplacer} onTerminer={vi.fn()}
      onOuvrir={vi.fn()} onAction={vi.fn()} onAjouter={vi.fn()} onAnnonce={vi.fn()} />)
    const poignee = screen.getByRole('button', { name: 'Déplacer « Devis Settat »' })
    poignee.focus()
    await touche(poignee, 'Space')
    await touche(document, 'Space')
    expect(onDeplacer).not.toHaveBeenCalled()
  })

  it('dans l\'écran : la carte part dans « Sans étape » à l\'instant, le serveur confirme, Annuler la remet', async () => {
    fauxServeur()
    api.modifierTache.mockResolvedValue({ data: exempleContrat('taches', 'tache_ecrite') })
    api.annulerGeste.mockResolvedValue({ data: {} })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    monter('/taches/projets/3?vue=tableau')
    await screen.findByRole('region', { name: 'Études' })
    await deplacerAuClavier(screen.getByRole('button', { name: 'Déplacer « Devis Settat »' }))
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledWith(20, { section_id: null, lock_version: 4 }))
    expect(within(screen.getByRole('region', { name: 'Sans étape' })).getByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Études' })).queryByRole('button', { name: 'Devis Settat' })).toBeNull()
    expect(api.lireVueProjet).toHaveBeenCalledTimes(1) // la vue n'est pas relue

    await user.click(await screen.findByRole('button', { name: 'Annuler' }))
    expect(api.annulerGeste).toHaveBeenCalledWith(77)
    await waitFor(() => expect(within(screen.getByRole('region', { name: 'Études' })).getByRole('button', { name: 'Devis Settat' })).toBeInTheDocument())
  })

  it('un refus du serveur ramène la carte dans sa colonne et le dit', async () => {
    fauxServeur()
    api.modifierTache.mockRejectedValue(new Error('Network Error'))
    monter('/taches/projets/3?vue=tableau')
    await screen.findByRole('region', { name: 'Études' })
    await deplacerAuClavier(screen.getByRole('button', { name: 'Déplacer « Devis Settat »' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Études' })).getByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
  })
})
