import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

/* ============================================================================
   CALX6 — LE PANNEAU « SÉRIES », ET LE CONTRAT QU'IL PARTAGE AVEC LE SERVEUR.
   ----------------------------------------------------------------------------
   Ce fichier tient les trois invariants du « Done » :
     1. les trois exports servis (`services/export_csv.py::EXPORTS`) sont
        proposés, et le clic appelle la porte CAL144 avec le bon `quoi` ;
     2. un refus du serveur DÉSACTIVE le bouton et affiche SOUS lui le motif
        que le serveur a écrit, en nommant le champ (`points`) — jamais une
        phrase fabriquée ici ;
     3. l'échantillon de contrat COMMITTÉ est lu à sa source (le test backend
        `test_calx6_serie_horaire.py` affirme le même fichier) : les deux
        moitiés ne peuvent pas diverger en silence.

   L'échantillon est relu par `node:fs` et non par un `import` de module : il
   vit hors de la racine Vite du frontend, et un test de contrat n'a aucune
   raison de le faire traverser le bundler.
   ========================================================================== */

const ICI = dirname(fileURLToPath(import.meta.url))

function racineDepot() {
  let dossier = resolve(ICI)
  for (let i = 0; i < 10; i += 1) {
    try {
      readFileSync(join(dossier, 'backend', 'django_core', 'manage.py'))
      return dossier
    } catch { dossier = dirname(dossier) }
  }
  throw new Error(`Racine du depot introuvable depuis ${ICI}`)
}

const CONTRAT = JSON.parse(readFileSync(join(
  racineDepot(), 'backend', 'django_core', 'apps', 'calepinage',
  'contract_samples', 'calepinage_serie_horaire.json'), 'utf8'))

const exportCsv = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { exportCsv: (...a) => exportCsv(...a) } },
}))

const downloadBlob = vi.fn()
vi.mock('../../../utils/downloadBlob', () => ({
  downloadBlob: (...a) => downloadBlob(...a),
}))

const { default: PanneauSeries } = await import('./PanneauSeries')

/** Le refus RÉEL de `views/export_csv.py` : corps JSON servi en BLOB. */
const refusServeur = (champ, motif) => ({
  response: {
    status: 400,
    data: {
      text: () => Promise.resolve(JSON.stringify({
        [champ]: [motif], exports_disponibles: ['horaire', 'mensuel', 'ombrage'],
      })),
    },
  },
})

const MOTIF_SANS_SERIE = (
  "La série horaire n'est pas disponible pour ce calepinage : lancez la "
  + "simulation avant d'exporter. Aucun fichier de zéros n'est produit à la "
  + 'place.'
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

const rendre = (props = {}) => render(
  <MemoryRouter><PanneauSeries calepinageId={5} {...props} /></MemoryRouter>,
)

describe('CALX6 — les trois exports sont offerts', () => {
  it('propose horaire, mensuel et ombrage, tous cliquables au départ', () => {
    rendre()
    for (const quoi of ['horaire', 'mensuel', 'ombrage']) {
      const bouton = screen.getByTestId(`cal-series-telecharger-${quoi}`)
      expect(bouton, `bouton absent : ${quoi}`).toBeInTheDocument()
      expect(bouton).not.toBeDisabled()
    }
  })

  it('le clic demande LE fichier au serveur et le remet au navigateur', async () => {
    exportCsv.mockResolvedValue({ data: 'annee;mois;jour\r\n2020;1;15\r\n' })
    rendre()

    fireEvent.click(screen.getByTestId('cal-series-telecharger-horaire'))

    await waitFor(() => expect(exportCsv).toHaveBeenCalledWith(5, 'horaire'))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalled())
    expect(downloadBlob.mock.calls[0][1]).toBe('calepinage-5-horaire.csv')
    expect(await screen.findByTestId('cal-series-fichier-horaire'))
      .toHaveTextContent('calepinage-5-horaire.csv')
  })
})

describe('CALX6 — série absente : le bouton est désactivé, avec SON motif', () => {
  it('affiche le motif du serveur sous le bouton et NOMME le champ', async () => {
    exportCsv.mockRejectedValue(refusServeur('points', MOTIF_SANS_SERIE))
    rendre()

    fireEvent.click(screen.getByTestId('cal-series-telecharger-horaire'))

    const motif = await screen.findByTestId('cal-series-motif-horaire')
    expect(motif).toHaveTextContent('points')
    expect(motif).toHaveTextContent('lancez la simulation')
    expect(screen.getByTestId('cal-series-telecharger-horaire')).toBeDisabled()
    // Aucun fichier n'a été remis au navigateur : pas de CSV de zéros.
    expect(downloadBlob).not.toHaveBeenCalled()
  })

  it('un export refusé ne désactive QUE le sien', async () => {
    exportCsv.mockRejectedValue(
      refusServeur('shading12x24', "Aucune matrice d'ombrage 12 × 24 n'est "
        + 'disponible pour ce calepinage.'))
    rendre()

    fireEvent.click(screen.getByTestId('cal-series-telecharger-ombrage'))

    await screen.findByTestId('cal-series-motif-ombrage')
    expect(screen.getByTestId('cal-series-telecharger-ombrage')).toBeDisabled()
    expect(screen.getByTestId('cal-series-telecharger-horaire')).not.toBeDisabled()
    expect(screen.queryByTestId('cal-series-motif-horaire')).toBeNull()
  })

  it('un refus sans corps lisible le DIT, il n’invente aucun motif', async () => {
    exportCsv.mockRejectedValue({ response: { status: 400, data: undefined } })
    rendre()

    fireEvent.click(screen.getByTestId('cal-series-telecharger-mensuel'))

    const motif = await screen.findByTestId('cal-series-motif-mensuel')
    expect(motif).toHaveTextContent('sans en donner le motif')
  })
})

describe('CALX6 — le contrat committé, lu à sa source', () => {
  it('l’échantillon décrit bien la porte que le panneau appelle', () => {
    expect(CONTRAT.endpoint).toMatch(/export-csv\/$/)
    expect(CONTRAT.endpoint.startsWith('GET ')).toBe(true)
  })

  it('la série porte ses points et ses colonnes, jamais des zéros à vide', () => {
    const serie = CONTRAT.exemple.serie_horaire
    expect(Array.isArray(serie.points)).toBe(true)
    expect(serie.points.length).toBeGreaterThan(0)
    for (const colonne of ['annee', 'mois', 'jour', 'heure', 'p_w',
      'gi_w_m2', 't2m_c']) {
      expect(serie.colonnes, `colonne absente du contrat : ${colonne}`)
        .toContain(colonne)
    }
    // L'état « jamais simulé » : la liste est VIDE et le pas est `null` —
    // c'est exactement le cas où le serveur refuse en nommant `points`.
    const vide = CONTRAT.exemple_vide.serie_horaire
    expect(vide.points).toEqual([])
    expect(vide.pas_minutes).toBeNull()
  })
})
