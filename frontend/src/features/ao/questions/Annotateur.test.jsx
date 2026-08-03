import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { readFileSync } from 'node:fs'
import { champsServeur, fichierAo } from '../../../test/contratServeur'

/* ============================================================================
   AOF106 — Done = 10 repères posés en moins de deux minutes, rendu net en
   haute résolution, numérotation cohérente APRÈS SUPPRESSION, les trois séries
   d'un cas réel se saisissent et se relisent.
   ----------------------------------------------------------------------------
   Ce fichier est le seul fichier de test déclaré par AOF106 : il couvre donc
   l'annotateur, le repère lettré et l'écran des séries.
   ========================================================================== */

const mocks = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn() }))

vi.mock('../../../api/aoApi', () => ({
  default: { seriesQR: { list: mocks.list, create: mocks.create } },
}))

import Annotateur, { TAILLE } from './Annotateur'
import { lettreDe, deplacer, redimensionner, RAYON_MIN, RAYON_MAX, PAS_DEPLACEMENT } from './RepereMarker'
import SeriesPage, { CANAUX } from './SeriesPage'

const IMAGE = 'data:image/png;base64,AAAA'

const canvas = () => screen.getByRole('group', { name: /Annotateur d’image/ })

// Un clic « souris » sur le canvas. Sous jsdom, `getBoundingClientRect()` rend
// des zéros : l'annotateur retombe alors sur l'échelle 1:1 du viewBox (garde
// anti-NaN documentée), donc clientX/clientY SONT les coordonnées d'annotation.
const cliquer = (x, y) => fireEvent.click(canvas(), { clientX: x, clientY: y })

describe('lettreDe — la lettre est DÉRIVÉE de l’index, jamais stockée', () => {
  it('rend A…Z puis AA, AB…', () => {
    expect(lettreDe(0)).toBe('A')
    expect(lettreDe(9)).toBe('J')
    expect(lettreDe(25)).toBe('Z')
    expect(lettreDe(26)).toBe('AA')
    expect(lettreDe(27)).toBe('AB')
  })
})

describe('deplacer / redimensionner — bornés au cadre', () => {
  it('ne sort jamais du cadre', () => {
    expect(deplacer({ x: 5, y: 5 }, { dx: -100, dy: -100 }, 1000)).toMatchObject({ x: 0, y: 0 })
    expect(deplacer({ x: 995, y: 995 }, { dx: 100, dy: 100 }, 1000)).toMatchObject({ x: 1000, y: 1000 })
  })

  it('respecte le rayon minimum et maximum', () => {
    expect(redimensionner({ r: RAYON_MIN }, -50).r).toBe(RAYON_MIN)
    expect(redimensionner({ r: RAYON_MAX }, 50).r).toBe(RAYON_MAX)
  })
})

describe('Annotateur — poser des repères', () => {
  it('sans image : propose de charger une image, jamais un canvas vide', () => {
    render(<Annotateur />)
    expect(screen.getByText('Aucune image à annoter')).toBeInTheDocument()
    expect(screen.getByLabelText('Charger une image à annoter')).toBeInTheDocument()
  })

  it('UN clic = UN repère, sans dialogue intermédiaire (condition des « 10 repères en 2 minutes »)', () => {
    render(<Annotateur imageSrc={IMAGE} />)
    cliquer(100, 100)
    expect(screen.getByRole('button', { name: 'Repère A' })).toBeInTheDocument()
    expect(screen.getByText('1 repère(s)')).toBeInTheDocument()
  })

  it('10 clics posent 10 repères lettrés A→J, sans aucune étape supplémentaire', () => {
    render(<Annotateur imageSrc={IMAGE} />)
    for (let i = 0; i < 10; i += 1) cliquer(50 + i * 20, 60 + i * 15)
    expect(screen.getByText('10 repère(s)')).toBeInTheDocument()
    for (const lettre of ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']) {
      expect(screen.getByRole('button', { name: `Repère ${lettre}` })).toBeInTheDocument()
    }
  })

  it('les coordonnées sont en unités de VIEWBOX (rendu net à toute résolution)', () => {
    const onChange = vi.fn()
    const { container } = render(<Annotateur imageSrc={IMAGE} onChange={onChange} />)
    cliquer(240, 360)
    const cercle = container.querySelector('g[data-ao-repere="A"] circle')
    expect(Number(cercle.getAttribute('cx'))).toBe(240)
    expect(Number(cercle.getAttribute('cy'))).toBe(360)
    expect(container.querySelector('svg').getAttribute('viewBox')).toBe(`0 0 ${TAILLE} ${TAILLE}`)
  })

  it('une voie CLAVIER pose un repère au centre (l’écran ne dépend pas de la souris)', async () => {
    const user = userEvent.setup()
    const { container } = render(<Annotateur imageSrc={IMAGE} />)
    await user.click(screen.getByRole('button', { name: 'Ajouter un repère' }))
    const cercle = container.querySelector('g[data-ao-repere="A"] circle')
    expect(Number(cercle.getAttribute('cx'))).toBe(TAILLE / 2)
  })
})

describe('Annotateur — NUMÉROTATION COHÉRENTE APRÈS SUPPRESSION', () => {
  it('supprimer B fait de l’ancien C le nouveau B (aucune lettre orpheline)', async () => {
    const user = userEvent.setup()
    render(<Annotateur imageSrc={IMAGE} />)
    cliquer(100, 100) // A
    cliquer(200, 200) // B
    cliquer(300, 300) // C
    expect(screen.getByRole('button', { name: 'Repère C' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Supprimer le repère B' }))

    expect(screen.getByText('2 repère(s)')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Repère C' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Repère A' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Repère B' })).toBeInTheDocument()
  })

  it('après suppression, le repère B porte bien la position de l’ancien C', async () => {
    const user = userEvent.setup()
    const { container } = render(<Annotateur imageSrc={IMAGE} />)
    cliquer(100, 100)
    cliquer(200, 200)
    cliquer(300, 300)
    await user.click(screen.getByRole('button', { name: 'Supprimer le repère B' }))
    const cercleB = container.querySelector('g[data-ao-repere="B"] circle')
    expect(Number(cercleB.getAttribute('cx'))).toBe(300)
  })

  it('supprimer TOUS les repères vide proprement la liste', async () => {
    const user = userEvent.setup()
    render(<Annotateur imageSrc={IMAGE} />)
    cliquer(10, 10)
    await user.click(screen.getByRole('button', { name: 'Supprimer le repère A' }))
    expect(screen.getByText('Aucun repère posé.')).toBeInTheDocument()
  })
})

describe('Annotateur — déplacement, redimensionnement, suppression au CLAVIER', () => {
  const marqueur = (lettre = 'A') => screen.getByRole('button', { name: `Repère ${lettre}` })

  it('les flèches déplacent le repère', () => {
    const { container } = render(<Annotateur imageSrc={IMAGE} />)
    cliquer(500, 500)
    fireEvent.keyDown(marqueur(), { key: 'ArrowRight' })
    expect(Number(container.querySelector('g[data-ao-repere="A"] circle').getAttribute('cx')))
      .toBe(500 + PAS_DEPLACEMENT)
  })

  it('Maj + flèche déplace plus vite', () => {
    const { container } = render(<Annotateur imageSrc={IMAGE} />)
    cliquer(500, 500)
    fireEvent.keyDown(marqueur(), { key: 'ArrowDown', shiftKey: true })
    expect(Number(container.querySelector('g[data-ao-repere="A"] circle').getAttribute('cy')))
      .toBe(500 + PAS_DEPLACEMENT * 5)
  })

  it('+ et - redimensionnent le cercle', () => {
    const { container } = render(<Annotateur imageSrc={IMAGE} />)
    cliquer(500, 500)
    const rAvant = Number(container.querySelector('g[data-ao-repere="A"] circle').getAttribute('r'))
    fireEvent.keyDown(marqueur(), { key: '+' })
    const rApres = Number(container.querySelector('g[data-ao-repere="A"] circle').getAttribute('r'))
    expect(rApres).toBeGreaterThan(rAvant)
    fireEvent.keyDown(marqueur(), { key: '-' })
    expect(Number(container.querySelector('g[data-ao-repere="A"] circle').getAttribute('r'))).toBe(rAvant)
  })

  it('Suppr supprime le repère focalisé', () => {
    render(<Annotateur imageSrc={IMAGE} />)
    cliquer(500, 500)
    fireEvent.keyDown(marqueur(), { key: 'Delete' })
    expect(screen.getByText('Aucun repère posé.')).toBeInTheDocument()
  })
})

describe('Annotateur — glisser à la souris', () => {
  it('un glisser déplace le repère et ne crée JAMAIS un second repère', () => {
    const { container } = render(<Annotateur imageSrc={IMAGE} />)
    cliquer(100, 100)
    const g = container.querySelector('g[data-ao-repere="A"]')
    fireEvent.pointerDown(g, { clientX: 100, clientY: 100 })
    fireEvent.pointerMove(canvas(), { clientX: 400, clientY: 250 })
    fireEvent.pointerUp(canvas(), { clientX: 400, clientY: 250 })
    expect(screen.getByText('1 repère(s)')).toBeInTheDocument()
    const cercle = container.querySelector('g[data-ao-repere="A"] circle')
    expect(Number(cercle.getAttribute('cx'))).toBe(400)
    expect(Number(cercle.getAttribute('cy'))).toBe(250)
  })
})

/* ── SeriesPage : la forme est celle de `SerieQuestionsSerializer` ────────────
   RÉPARATION 03/08/2026. Les fixtures d'origine inventaient `date`, `objet`,
   `questions_count`, `reponses_count`, `impact_constate_modules` et
   `echanges` : le serveur n'a JAMAIS produit un seul de ces champs, et
   l'écran appelait `/ao/series-qr/`, une route inexistante. Le test était
   vert parce qu'il se mockait lui-même.
   Ci-dessous : la réponse RÉELLE (`numero`, `date_envoi`, `canal_display`,
   `destinataire`, `questions` imbriquées, `impact_total_modules {min,max}`),
   plus une GARDE qui relit `serializers.py` et `models.py`. */

const SERIES = [
  {
    id: 1, appel_offre: 7, numero: 1, date_envoi: '2026-07-20', canal: 'email',
    canal_display: 'Courriel', destinataire: 'Maîtrise d’œuvre',
    impact_total_modules: { min: 10, max: 14 },
    questions: [
      {
        id: 11, serie: 1, repere: 'A', texte: 'Les 4 souches sont-elles réelles ?',
        impact_min_modules: 6, impact_max_modules: 8, a_un_impact_chiffre: true,
        reponse: 'Souches inexistantes — à écarter.', statut: 'tranchee',
        statut_display: 'Tranchée',
      },
      {
        id: 12, serie: 1, repere: 'B', texte: 'L’allée centrale est-elle imposée ?',
        impact_min_modules: 4, impact_max_modules: 6, a_un_impact_chiffre: true,
        reponse: '', statut: 'posee', statut_display: 'Posée',
      },
    ],
  },
  {
    id: 2, appel_offre: 7, numero: 2, date_envoi: null, canal: 'whatsapp',
    canal_display: 'WhatsApp', destinataire: 'Conducteur de travaux',
    impact_total_modules: { min: 0, max: 0 }, questions: [],
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: SERIES })
  mocks.create.mockResolvedValue({ data: {} })
})

describe('GARDE de contrat — les fixtures de séries ne peuvent pas inventer de champ', () => {
  it('chaque clé mockée est déclarée par le sérialiseur serveur', () => {
    const serie = champsServeur('SerieQuestionsSerializer')
    const question = champsServeur('QuestionAOSerializer')
    for (const cle of Object.keys(SERIES[0])) {
      expect(serie.has(cle), `SerieQuestionsSerializer ne produit pas « ${cle} »`).toBe(true)
    }
    for (const cle of Object.keys(SERIES[0].questions[0])) {
      expect(question.has(cle), `QuestionAOSerializer ne produit pas « ${cle} »`).toBe(true)
    }
    // Les six champs du bug : le serveur ne les a jamais eus.
    for (const invente of ['date', 'objet', 'questions_count', 'reponses_count',
      'impact_constate_modules', 'echanges']) {
      expect(serie.has(invente)).toBe(false)
    }
  })

  it('les canaux proposés à l’écran sont EXACTEMENT ceux du modèle', () => {
    const models = readFileSync(fichierAo('models.py'), 'utf8')
    const debut = models.indexOf('class SerieQuestions(')
    const bloc = models.slice(debut, models.indexOf('class Meta:', debut))
    const duModele = [...bloc.matchAll(/=\s*'([a-z_]+)',\s*'[^']*'/g)].map((m) => m[1])
    expect(CANAUX.map((c) => c.value)).toEqual(duModele)
  })
})

describe('SeriesPage — séries datées', () => {
  it('filtre sur `appel_offre` (le ViewSet ignore « affaire ») et relit la forme serveur', async () => {
    render(<SeriesPage affaireId={7} />)
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ appel_offre: 7 }))
    expect(await screen.findByText('Série 1')).toBeInTheDocument()
    expect(screen.getByText('Maîtrise d’œuvre')).toBeInTheDocument()
    expect(screen.getByText('WhatsApp')).toBeInTheDocument()
    // Fourchette PRÉVISIONNELLE du serveur — jamais un « constaté » inventé.
    expect(screen.getByText('+10 à +14 module(s)')).toBeInTheDocument()
    // Série sans question : on le dit, on n'affiche pas un « 0 » qui se
    // lirait comme « sans effet ».
    expect(screen.getByText('aucune question')).toBeInTheDocument()
    expect(screen.getByText('non envoyée')).toBeInTheDocument()
  })

  it('les compteurs sont la LECTURE de la liste imbriquée (2 questions, 1 répondue)', async () => {
    render(<SeriesPage affaireId={7} />)
    await screen.findByText('Série 1')
    const ligne = screen.getByText('Série 1').closest('tr')
    const cellules = [...ligne.querySelectorAll('td')].map((c) => c.textContent)
    expect(cellules).toContain('2') // questions
    expect(cellules).toContain('1') // réponses non vides
  })

  it('déplie les QUESTIONS de la série (aucune timeline d’échanges n’existe côté serveur)', async () => {
    const user = userEvent.setup()
    render(<SeriesPage affaireId={7} />)
    await screen.findByText('Série 1')
    await user.click(screen.getAllByRole('button', { name: 'Voir' })[0])
    expect(await screen.findByText('Les 4 souches sont-elles réelles ?')).toBeInTheDocument()
    expect(screen.getByText('Réponse : Souches inexistantes — à écarter.')).toBeInTheDocument()
    expect(screen.getByText('Sans réponse à ce jour.')).toBeInTheDocument()
  })

  it('crée une série avec les champs RÉELS — jamais un numéro proposé par l’écran', async () => {
    const user = userEvent.setup()
    render(<SeriesPage affaireId={7} />)
    await screen.findByText('Série 1')
    await user.click(screen.getByRole('button', { name: /Nouvelle série/ }))
    await user.type(await screen.findByLabelText('Destinataire de la série'), 'Architecte')
    await user.click(screen.getByRole('button', { name: 'Créer la série' }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({
      appel_offre: 7, canal: 'email', destinataire: 'Architecte',
    }))
    expect(mocks.create.mock.calls[0][0]).not.toHaveProperty('numero')
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
  })

  it('aucune série : état nommé, jamais un tableau fantôme', async () => {
    mocks.list.mockResolvedValue({ data: [] })
    render(<SeriesPage affaireId={7} />)
    expect(await screen.findByText('Aucune série de questions')).toBeInTheDocument()
  })
})
