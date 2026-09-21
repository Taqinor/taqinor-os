import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   CALX64 — LE TAPIS JOUR × HEURE ET LA JOURNÉE TYPE, VUS DU CONTRAT.
   ----------------------------------------------------------------------------
   Ce fichier tient les quatre invariants du « Done » :
     1. 8 760 points rendent 365 colonnes (une par jour du calendrier) ;
     2. série absente ⇒ état vide qui NOMME le geste (« Lancer la
        simulation ») et porte le motif ÉCRIT PAR LE SERVEUR ;
     3. la journée type de juin est plus haute que celle de décembre sur la
        fixture ;
     4. série agrégée au jour (CALX193, `tronquee: true`) ⇒ UNE seule ligne,
        et le motif de troncature est affiché.

   LA FIXTURE DE 8 760 POINTS EST SYNTHÉTIQUE, ET ASSUMÉE : elle ne décrit
   AUCUNE installation réelle (D-CALX 7). Ce sont les COLONNES qui viennent du
   contrat committé `calepinage_serie_horaire.json` (relu à sa source, comme
   le test backend `test_calx6_serie_horaire.py`) ; les valeurs, elles, sont
   une courbe en cloche d'essai dont le seul rôle est de rendre juin
   distinguable de décembre.
   ========================================================================== */

const CONTRAT = documentContrat('calepinage', 'calepinage_serie_horaire')

const exportCsv = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { exportCsv: (...a) => exportCsv(...a) } },
}))

const { default: TapisHoraire } = await import('./TapisHoraire')

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

// 2021 n'est PAS bissextile : douze mois, 365 jours — exactement 8 760 points
// au pas horaire, la borne que le contrat CALX142 décrit.
const JOURS_DU_MOIS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
//: Amplitude d'essai par mois — juin haut, décembre bas. AUCUNE mesure.
const AMPLITUDE_ESSAI = [3, 4, 5.5, 7, 8.5, 9.5, 9, 8.5, 7, 5.5, 4, 3]

function serieSynthetique() {
  const points = []
  for (let mois = 1; mois <= 12; mois += 1) {
    for (let jour = 1; jour <= JOURS_DU_MOIS[mois - 1]; jour += 1) {
      for (let heure = 0; heure < 24; heure += 1) {
        const arche = Math.max(0, Math.sin((Math.PI * (heure - 6)) / 12))
        const production = arche * AMPLITUDE_ESSAI[mois - 1]
        points.push({
          annee: 2021,
          mois,
          jour,
          heure,
          p_ac_kw: production,
          gi_w_m2: arche * 900,
          charge_kwh: null,
        })
      }
    }
  }
  return {
    pas_minutes: 60,
    tronquee: false,
    colonnes: CONTRAT.exemple.serie_horaire.colonnes,
    points,
  }
}

/** Le refus RÉEL de `views/export_csv.py` : corps JSON servi en BLOB. */
const refusServeur = (champ, motif) => ({
  response: {
    status: 400,
    data: { text: () => Promise.resolve(JSON.stringify({ [champ]: [motif] })) },
  },
})

const MOTIF_SANS_SERIE = (
  "La série horaire n'est pas disponible pour ce calepinage : lancez la "
  + "simulation avant d'exporter."
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

const rendre = (props = {}) => render(
  <MemoryRouter><TapisHoraire calepinageId={9} {...props} /></MemoryRouter>,
)

const pic = (mois) => Number(
  screen.getByTestId(`cal-tapis-pic-${mois}`).getAttribute('data-pic'))

describe('CALX64 — le tapis d’une année complète', () => {
  it('8 760 points rendent 365 colonnes, une par jour', async () => {
    rendre({ serie: serieSynthetique() })

    await screen.findByTestId('cal-tapis')
    expect(screen.getAllByTestId('cal-tapis-jour')).toHaveLength(365)
    // Aucun appel réseau : la série fournie suffit.
    expect(exportCsv).not.toHaveBeenCalled()
  }, 30_000)

  it('la journée type de JUIN est plus haute que celle de DÉCEMBRE', async () => {
    rendre({ serie: serieSynthetique() })

    await screen.findByTestId('cal-tapis-journee-type')
    expect(pic(6)).toBeGreaterThan(pic(12))
    expect(pic(6)).toBeGreaterThan(0)
  }, 30_000)

  it('la légende publie les bornes réellement observées, avec leur unité', async () => {
    rendre({ serie: serieSynthetique() })

    const legende = await screen.findByTestId('cal-tapis-legende')
    expect(legende).toHaveTextContent('kW')
    expect(legende).toHaveTextContent('365 jour(s)')
    expect(legende).toHaveTextContent('24 heures')
  }, 30_000)

  it('l’irradiance est une seconde lecture de la MÊME série', async () => {
    rendre({ serie: serieSynthetique() })

    fireEvent.click(await screen.findByTestId('cal-tapis-grandeur-gi_w_m2'))
    expect(screen.getByTestId('cal-tapis-legende')).toHaveTextContent('W/m²')
    expect(screen.getAllByTestId('cal-tapis-jour')).toHaveLength(365)
  }, 30_000)
})

describe('CALX64 — série absente', () => {
  it('état vide nommant « Lancer la simulation » et le motif DU SERVEUR', async () => {
    exportCsv.mockRejectedValue(refusServeur('points', MOTIF_SANS_SERIE))
    rendre()

    const vide = await screen.findByTestId('cal-tapis-vide')
    expect(vide).toHaveTextContent('Lancer la simulation')
    expect(vide).toHaveTextContent('lancez la simulation')
    expect(screen.queryByTestId('cal-tapis-grille')).toBeNull()
  })

  it('une réponse sans tableau ne peint AUCUN zéro', async () => {
    exportCsv.mockResolvedValue({ data: '' })
    rendre()

    expect(await screen.findByTestId('cal-tapis-vide')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-tapis-grille')).toBeNull()
  })
})

describe('CALX64 — la série lue par la MÊME porte que le panneau Séries', () => {
  it('le CSV du serveur est relu tel quel, décimale française comprise', async () => {
    const csv = [
      'Provenance;Module Calepinage',
      '',
      'annee;mois;jour;heure;production_kw;irradiance_plan_w_m2;temperature_air_c',
      '2021;1;15;12;6,800;880,00;19,80',
      '2021;1;16;12;7,200;910,00;20,10',
    ].join('\r\n')
    exportCsv.mockResolvedValue({ data: csv })
    rendre()

    await screen.findByTestId('cal-tapis')
    expect(exportCsv).toHaveBeenCalledWith(9, 'horaire')
    expect(screen.getAllByTestId('cal-tapis-jour')).toHaveLength(2)
    // 6,800 et 7,200 kW sont les bornes RÉELLEMENT publiées par le fichier :
    // rien n'est arrondi vers un chiffre plus flatteur.
    const legende = screen.getByTestId('cal-tapis-legende')
    expect(legende).toHaveTextContent('6,80 kW')
    expect(legende).toHaveTextContent('7,20 kW')
  })
})

describe('CALX64 — série agrégée au jour (CALX193)', () => {
  it('affiche UNE ligne par journée et publie le motif de troncature', async () => {
    const motif = 'Série agrégée au jour : 35 136 points au pas de 15 min.'
    rendre({
      serie: {
        pas_minutes: 1440,
        tronquee: true,
        motif_troncature: motif,
        colonnes: ['annee', 'mois', 'jour', 'p_ac_kw'],
        points: [
          { annee: 2021, mois: 1, jour: 15, heure: null, p_ac_kw: 41.2 },
          { annee: 2021, mois: 1, jour: 16, heure: null, p_ac_kw: 38.9 },
        ],
      },
    })

    await screen.findByTestId('cal-tapis')
    expect(screen.getByTestId('cal-tapis-tronquee')).toHaveTextContent(motif)
    expect(screen.getAllByTestId('cal-tapis-jour')).toHaveLength(2)
    expect(screen.getByTestId('cal-tapis-legende'))
      .toHaveTextContent('journée entière')
    // Aucune heure n'est reconstituée : pas de journée type.
    expect(screen.queryByTestId('cal-tapis-journee-type')).toBeNull()
  })
})

describe('CALX64 — le contrat committé', () => {
  it('nomme bien les deux colonnes que le tapis sait peindre', () => {
    const colonnes = CONTRAT.exemple.serie_horaire.colonnes
    expect(colonnes).toContain('p_ac_kw')
    expect(colonnes).toContain('gi_w_m2')
  })

  it('l’état « jamais simulé » du contrat porte une série VIDE', () => {
    expect(CONTRAT.exemple_vide.serie_horaire.points).toEqual([])
  })
})
