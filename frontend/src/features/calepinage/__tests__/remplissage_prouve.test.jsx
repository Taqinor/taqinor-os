import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import process from 'node:process'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   CAL79 — « PROUVÉ » N'EST JAMAIS ÉCRIT SUR UNE HEURISTIQUE.
   ----------------------------------------------------------------------------
   La charge utile vient du contrat COMMITTÉ `moteur_calculer.json` (PACT10) —
   le même fichier que la porte moteur CAL22 affirme, avec son bloc `preuve` et
   son `exemple_vide` qui est le 202 `{job_id}` du dépassement de budget.

   CE QUE CE TEST TIENT :
     * les DEUX phrases apparaissent selon le régime, jamais l'une pour l'autre ;
     * l'attente affiche l'AVANCEMENT PUBLIÉ par la tâche de fond ;
     * l'édition manuelle reste prioritaire : rien n'est appliqué sans geste.
   ========================================================================== */

const RESULTAT = exempleContrat('calepinage', 'moteur_calculer')
const JOB = exempleContrat('calepinage', 'moteur_calculer', 'exemple_vide')

const calculer = vi.fn()
const resultatJob = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    moteur: {
      calculer: (...a) => calculer(...a),
      resultat: (...a) => resultatJob(...a),
    },
  },
}))

const { default: RemplissageProuve, regimeDePreuve } = await import('../RemplissageProuve')

const ENTREE = { surfaces: [{ id: 'PAN-A' }] }

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

const rendre = (props = {}) => render(
  <RemplissageProuve entree={ENTREE} intervalleMs={1} {...props} />,
)

/* ── 1. LE RÉGIME, PUR ─────────────────────────────────────────────────── */

describe('CAL79 — le régime de preuve, lu sur le bloc du moteur', () => {
  it('le contrat committé porte bien un optimum DÉMONTRÉ', () => {
    expect(RESULTAT.preuve.optimal).toBe(true)
    expect(RESULTAT.preuve.methode_exacte).toBe(true)
    const regime = regimeDePreuve(RESULTAT)
    expect(regime.prouve).toBe(true)
    expect(regime.phrase).toBe(`Optimum prouvé (${RESULTAT.preuve.total_retenu})`)
  })

  it('méthode NON exacte : « meilleur plan trouvé » + la borne PUBLIÉE', () => {
    const heuristique = {
      ...RESULTAT,
      preuve: {
        ...RESULTAT.preuve,
        optimal: false, methode_exacte: false, methode: 'glouton',
        total_retenu: 11, borne_superieure: 13,
      },
    }
    const regime = regimeDePreuve(heuristique)
    expect(regime.prouve).toBe(false)
    expect(regime.phrase).toBe('Meilleur plan trouvé (11) — borne supérieure 13')
    expect(regime.phrase).not.toMatch(/prouvé/)
  })

  it('« optimal » sans méthode exacte ne suffit PAS à écrire « prouvé »', () => {
    const regime = regimeDePreuve({
      preuve: { optimal: true, methode_exacte: false, total_retenu: 12, borne_superieure: 12 },
    })
    expect(regime.prouve).toBe(false)
    expect(regime.phrase).not.toMatch(/prouvé/)
  })

  it('sans borne publiée, aucune borne n’est inventée', () => {
    const regime = regimeDePreuve({
      preuve: { optimal: false, methode_exacte: false, total_retenu: 9 },
    })
    expect(regime.phrase).toBe('Meilleur plan trouvé (9) — aucune borne supérieure publiée')
  })

  it('sans bloc `preuve`, aucun régime n’est affirmé', () => {
    expect(regimeDePreuve({ total_modules: 12 })).toBeNull()
    expect(regimeDePreuve(null)).toBeNull()
  })
})

/* ── 2. L'ÉCRAN ────────────────────────────────────────────────────────── */

describe('CAL79 — l’écran, branché sur la porte moteur CAL22', () => {
  it('appelle `moteur/calculer` et affiche « Optimum prouvé »', async () => {
    calculer.mockResolvedValue({ data: RESULTAT })
    rendre()
    fireEvent.click(screen.getByTestId('cal-remplissage-lancer'))

    expect(calculer).toHaveBeenCalledWith(ENTREE)
    const regime = await screen.findByTestId('cal-remplissage-regime')
    expect(regime).toHaveTextContent('Optimum prouvé')
    expect(regime).toHaveAttribute('data-regime', 'prouve')
    expect(screen.getByTestId('cal-remplissage-methode'))
      .toHaveTextContent(RESULTAT.preuve.methode)
  })

  it('un plan heuristique n’est JAMAIS annoncé comme prouvé', async () => {
    calculer.mockResolvedValue({
      data: {
        ...RESULTAT,
        preuve: {
          ...RESULTAT.preuve, optimal: false, methode_exacte: false,
          total_retenu: 11, borne_superieure: 13,
        },
      },
    })
    rendre()
    fireEvent.click(screen.getByTestId('cal-remplissage-lancer'))

    const regime = await screen.findByTestId('cal-remplissage-regime')
    expect(regime).toHaveTextContent('Meilleur plan trouvé (11) — borne supérieure 13')
    expect(regime).not.toHaveTextContent('prouvé')
    expect(regime).toHaveAttribute('data-regime', 'heuristique')
  })

  it('202 : l’attente affiche l’avancement PUBLIÉ par la tâche de fond', async () => {
    calculer.mockResolvedValue({ data: JOB })
    // Le travail RESTE en cours : c'est l'état d'attente qu'on observe, sans
    // aucune temporisation arbitraire (on attend une CONDITION de l'écran).
    resultatJob.mockResolvedValue({ data: { ...JOB, statut: 'STARTED', progress_pct: 40 } })
    rendre({ intervalleMs: 10_000 })
    fireEvent.click(screen.getByTestId('cal-remplissage-lancer'))

    const avancement = await screen.findByTestId('cal-remplissage-avancement')
    expect(avancement).toHaveTextContent(String(JOB.job_id))
    await waitFor(() => expect(screen.getByTestId('cal-remplissage-avancement'))
      .toHaveTextContent('40 %'))
    // L'avancement AFFICHÉ est celui que le serveur publie, pas une barre qui
    // avance toute seule : aucun régime n'est encore annoncé.
    expect(screen.queryByTestId('cal-remplissage-regime')).toBeNull()
    expect(resultatJob).toHaveBeenCalledWith(JOB.job_id)
  })

  it('202 : le plan arrive à la fin du travail de fond, avec son régime', async () => {
    calculer.mockResolvedValue({ data: JOB })
    resultatJob.mockResolvedValue({
      data: { ...JOB, statut: 'SUCCESS', progress_pct: 100, resultat: RESULTAT },
    })
    rendre()
    fireEvent.click(screen.getByTestId('cal-remplissage-lancer'))

    expect(await screen.findByTestId('cal-remplissage-regime'))
      .toHaveTextContent('Optimum prouvé')
    expect(screen.queryByTestId('cal-remplissage-avancement')).toBeNull()
  })

  it('l’édition manuelle reste PRIORITAIRE : rien n’est appliqué sans geste', async () => {
    calculer.mockResolvedValue({ data: RESULTAT })
    const onAppliquer = vi.fn()
    rendre({ onAppliquer })
    fireEvent.click(screen.getByTestId('cal-remplissage-lancer'))

    await screen.findByTestId('cal-remplissage-regime')
    expect(onAppliquer).not.toHaveBeenCalled()
    fireEvent.click(screen.getByTestId('cal-remplissage-appliquer'))
    expect(onAppliquer).toHaveBeenCalledWith(RESULTAT)
  })

  it('en lecture seule, ni lancement ni application', () => {
    rendre({ lectureSeule: true })
    expect(screen.queryByTestId('cal-remplissage-lancer')).toBeNull()
    expect(screen.queryByTestId('cal-remplissage-appliquer')).toBeNull()
  })

  it('sans surface à remplir, un refus qui NOMME ce qui manque', () => {
    render(<RemplissageProuve entree={null} />)
    fireEvent.click(screen.getByTestId('cal-remplissage-lancer'))
    expect(screen.getByTestId('cal-remplissage-refus'))
      .toHaveTextContent('dessinez d’abord un pan de toit')
    expect(calculer).not.toHaveBeenCalled()
  })

  it('refus du moteur : son message, jamais un régime inventé', async () => {
    calculer.mockRejectedValue({ response: { data: { detail: 'Surface illisible.' } } })
    rendre()
    fireEvent.click(screen.getByTestId('cal-remplissage-lancer'))
    expect(await screen.findByTestId('cal-remplissage-refus'))
      .toHaveTextContent('Surface illisible.')
    expect(screen.queryByTestId('cal-remplissage-regime')).toBeNull()
  })

  it('un plan SANS bloc de preuve n’affirme rien', async () => {
    calculer.mockResolvedValue({ data: { total_modules: 12 } })
    rendre()
    fireEvent.click(screen.getByTestId('cal-remplissage-lancer'))
    expect(await screen.findByTestId('cal-remplissage-sans-preuve'))
      .toHaveTextContent('ni « prouvé », ni borne supérieure')
  })
})

describe('CAL79 — le panneau est monté dans l’atelier', () => {
  /* Un composant écrit pour PERSONNE est l'oubli du 03/08/2026. On le vérifie
     ici sur la SOURCE de l'atelier plutôt qu'en le remontant : le rendu réel
     d'`AtelierPanneaux` est déjà exercé par `raccourcis_atelier.test.jsx`, et
     un second `vi.resetModules()` + réimport dans le même dossier de tests
     faisait dépasser le délai d'import du registre de modules (constaté : la
     garde d'`order` de `module.config.test.jsx` tombait en timeout de 20 s dès
     que ce dossier gagnait un quatorzième fichier). */
  it('AtelierPanneaux l’importe ET le rend', () => {
    /* `import.meta.url` est virtuel sous vitest : on résout depuis la racine
       du projet, que la configuration vitest fixe à `frontend/`. */
    const source = readFileSync(
      join(process.cwd(), 'src/features/calepinage/AtelierPanneaux.jsx'), 'utf8')
    expect(source).toMatch(/import RemplissageProuve from '\.\/RemplissageProuve'/)
    expect(source).toMatch(/<RemplissageProuve/)
    // Et il reçoit bien de quoi travailler, sinon il serait monté pour rien.
    expect(source).toMatch(/entree=\{builderApi\?\.entreeMoteur/)
  })
})
