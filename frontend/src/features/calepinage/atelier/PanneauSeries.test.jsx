import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { formatNumber } from '../../../lib/format'
import { MemoryRouter } from 'react-router-dom'
import { OPTIONS_TELECHARGEMENT } from '../documents/telechargement'
import { COLONNES_CSV, COLONNES_DATE } from './colonnesCsv'
import { documentContrat, exempleContrat } from '../../../test/fixtures/contractSamples'

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

const CONTRAT = documentContrat('calepinage', 'calepinage_serie_horaire')

const CONTRAT_METEO = documentContrat('calepinage', 'calepinage_meteo_fichier')

const exportCsv = vi.fn()
const deposerMeteoFichier = vi.fn()
const meteoFichier = vi.fn()
const retirerFichierMeteo = vi.fn()
const permission = vi.hoisted(() => ({ gerer: true }))
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      exportCsv: (...a) => exportCsv(...a),
      deposerMeteoFichier: (...a) => deposerMeteoFichier(...a),
      meteoFichier: (...a) => meteoFichier(...a),
      retirerFichierMeteo: (...a) => retirerFichierMeteo(...a),
    },
  },
}))

/* ACAL148 — « Retirer le fichier météo » est sous `calepinage_gerer` (doublure :
   pas de Provider Redux dans ce test). */
vi.mock('../../../hooks/useHasPermission', () => ({
  useHasPermission: () => permission.gerer,
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

beforeEach(() => {
  vi.clearAllMocks()
  permission.gerer = true
  // Par défaut : aucun fichier retenu, la simulation lit PVGIS.
  meteoFichier.mockResolvedValue({ data: null })
})
afterEach(() => { cleanup() })

const rendre = (props = {}) => render(
  <MemoryRouter><PanneauSeries calepinageId={5} {...props} /></MemoryRouter>,
)

describe('ACAL755 — le menu « Pas : heure / jour »', () => {
  it('« Pas : jour » envoie pas=jour en 4e argument ; le défaut ne change pas', async () => {
    exportCsv.mockResolvedValue({ data: 'x' })
    rendre()
    fireEvent.change(screen.getByTestId('acal755-pas'), { target: { value: 'jour' } })
    fireEvent.click(screen.getByTestId('cal-series-telecharger-horaire'))
    await waitFor(() => expect(exportCsv).toHaveBeenCalledWith(5, 'horaire', null, { pas: 'jour', ...OPTIONS_TELECHARGEMENT }))
  })

  it("l'échantillon du contrat nomme le pas « jour »", () => {
    expect(exempleContrat('calepinage', 'calepinage_export_csv').pas).toContain('jour')
  })
})

describe('ACAL1614 — la carte « Série horaire » ne promet plus une ligne par heure partout', () => {
  it('son aide nomme le pas du jour en météo pluriannuelle', () => {
    rendre()
    expect(screen.getByTestId('cal-series-ligne-horaire')).toHaveTextContent(/au pas du jour en météo pluriannuelle/)
  })
})

describe('ACAL754 — la carte « Ombrage module par module »', () => {
  it("la 4e carte demande quoi=ombrage_modules ; l'échantillon la nomme", async () => {
    const { exports } = exempleContrat('calepinage', 'calepinage_export_csv')
    expect(exports).toContain('ombrage_modules')
    exportCsv.mockResolvedValue({ data: 'x' })
    rendre()
    fireEvent.click(screen.getByTestId('cal-series-telecharger-ombrage_modules'))
    await waitFor(() => expect(exportCsv).toHaveBeenCalledWith(5, 'ombrage_modules', null, OPTIONS_TELECHARGEMENT))
    expect(screen.getByTestId('cal-series-ligne-ombrage_modules'))
      .toHaveTextContent('Ombrage module par module (CSV)')
  })
})

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

    await waitFor(() => expect(exportCsv).toHaveBeenCalledWith(5, 'horaire', null, OPTIONS_TELECHARGEMENT))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalled())
    expect(downloadBlob.mock.calls[0][1]).toBe('calepinage-5-horaire.csv')
    expect(await screen.findByTestId('cal-series-fichier-horaire'))
      .toHaveTextContent('calepinage-5-horaire.csv')
  })
})

const ECARTEES = ['t', 'p_w', 'gi_w_m2', 't2m_c']

describe('ACAL753 — choisir les colonnes de la série horaire', () => {
  it("la liste de l'écran et l'échantillon du serveur disent les mêmes noms", () => {
    const { colonnes_horaire: serveur } = exempleContrat('calepinage', 'calepinage_export_csv')
    const ecran = [...COLONNES_DATE, ...COLONNES_CSV.map((c) => c.nom)]
    for (const nom of ecran) expect(serveur, nom).toContain(nom)
    for (const nom of serveur) {
      expect(ecran.includes(nom) || ECARTEES.includes(nom), nom).toBe(true)
    }
  })

  it("cocher « Puissance écrêtée » envoie la chaîne des colonnes dans l'ordre de la liste", async () => {
    exportCsv.mockResolvedValue({ data: 'x' })
    rendre()
    // Cochée AVANT une colonne de la liste placée plus haut : l'ordre reste celui de la liste.
    fireEvent.click(screen.getByTestId('cal-series-colonne-ecretage_kw'))
    fireEvent.click(screen.getByTestId('cal-series-colonne-ws10m'))
    fireEvent.click(screen.getByTestId('cal-series-telecharger-horaire'))
    await waitFor(() => expect(exportCsv).toHaveBeenCalledWith(
      5, 'horaire',
      'annee,mois,jour,heure,production_kw,irradiance_plan_w_m2,temperature_air_c,ws10m,ecretage_kw',
      OPTIONS_TELECHARGEMENT,
    ))
    expect(typeof exportCsv.mock.calls[0][2]).toBe('string')
  })

  it("la sélection d'office n'envoie aucune colonne (null) mais le délai de téléchargement", async () => {
    exportCsv.mockResolvedValue({ data: 'x' })
    rendre()
    fireEvent.click(screen.getByTestId('cal-series-colonne-ecretage_kw'))
    fireEvent.click(screen.getByTestId('cal-series-colonne-ecretage_kw'))
    fireEvent.click(screen.getByTestId('cal-series-telecharger-horaire'))
    await waitFor(() => expect(exportCsv).toHaveBeenCalled())
    expect(exportCsv.mock.calls[0]).toEqual([5, 'horaire', null, OPTIONS_TELECHARGEMENT])
  })

  it('un export trop long dit le délai en français (R3)', async () => {
    exportCsv.mockRejectedValue({ code: 'ECONNABORTED' })
    rendre()
    fireEvent.click(screen.getByTestId('cal-series-telecharger-horaire'))
    expect(await screen.findByTestId('cal-series-motif-horaire')).toHaveTextContent("Le serveur n'a pas fini de préparer ce document en 2 minutes.")
  })

  it('un refus 400 nomme la colonne sous la carte', async () => {
    exportCsv.mockRejectedValue(refusServeur('colonnes', 'Colonne inconnue : ws10m.'))
    rendre()
    fireEvent.click(screen.getByTestId('cal-series-colonne-ws10m'))
    fireEvent.click(screen.getByTestId('cal-series-telecharger-horaire'))
    expect(await screen.findByTestId('cal-series-motif-horaire')).toHaveTextContent('Colonne inconnue : ws10m.')
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

describe('CALX62 — déposer une série météo de la société', () => {
  const fichierCsv = () => new File(
    ['horodatage;gi_w_m2\r\n2021-01-15T13:00:00+01:00;780.0\r\n'],
    'meteo-2021.csv', { type: 'text/csv' })

  it('ACAL971 — le sélecteur de fichier est un bouton français, sans « Choose File »', () => {
    rendre()
    expect(screen.getByText('Choisir un fichier')).toHaveAttribute('for', 'cal-series-depot-fichier')
    expect(screen.getByText('Aucun fichier choisi')).toBeInTheDocument()
    expect(screen.queryByText('Choose File')).toBeNull()
  })

  it('offre les DEUX champs obligatoires : le fichier et le fournisseur', () => {
    rendre()
    expect(screen.getByTestId('cal-series-depot-fichier')).toBeInTheDocument()
    expect(screen.getByTestId('cal-series-depot-fournisseur')).toBeInTheDocument()
    expect(screen.getByTestId('cal-series-depot-envoyer')).toBeInTheDocument()
  })

  it('envoie le fichier ET le fournisseur, puis affiche la provenance rendue', async () => {
    const utilisateur = userEvent.setup()
    deposerMeteoFichier.mockResolvedValue({ data: CONTRAT_METEO.exemple })
    rendre()

    await utilisateur.upload(screen.getByTestId('cal-series-depot-fichier'),
      fichierCsv())
    await utilisateur.type(screen.getByTestId('cal-series-depot-fournisseur'),
      'Station d essai')
    await utilisateur.click(screen.getByTestId('cal-series-depot-envoyer'))

    await waitFor(() => expect(deposerMeteoFichier).toHaveBeenCalled())
    const [id, corps] = deposerMeteoFichier.mock.calls[0]
    expect(id).toBe(5)
    expect(corps.get('fournisseur')).toBe('Station d essai')
    expect(corps.get('fichier')).toBeTruthy()

    const provenance = await screen.findByTestId('cal-series-depot-provenance')
    // Ce qui s'affiche vient du SERVEUR (l'exemple committé), pas de l'écran.
    expect(provenance).toHaveTextContent(
      CONTRAT_METEO.exemple.meteo.fichier.nom)
    expect(provenance).toHaveTextContent(
      CONTRAT_METEO.exemple.meteo.fournisseur)
  })

  async function deposerAvec(reponse) {
    const utilisateur = userEvent.setup()
    deposerMeteoFichier.mockResolvedValue({ data: reponse })
    rendre()
    await utilisateur.upload(screen.getByTestId('cal-series-depot-fichier'), fichierCsv())
    await utilisateur.type(screen.getByTestId('cal-series-depot-fournisseur'), 'Station d essai')
    await utilisateur.click(screen.getByTestId('cal-series-depot-envoyer'))
    return screen.findByTestId('acal764-qualite')
  }

  it('ACAL764 — les quatre lignes de qualité de l’exemple du contrat, sans verdict', async () => {
    const q = CONTRAT_METEO.exemple.qualite
    const bloc = await deposerAvec(CONTRAT_METEO.exemple)
    const nb = (v) => formatNumber(v)
    expect(screen.getByTestId('acal764-couverture').textContent).toBe(
      `Couverture : ${nb(q.couverture.heures_lues)} heures sur 2021 ; mois sans mesure : aucun`)
    expect(screen.getByTestId('acal764-decalage')).toHaveTextContent(
      `tombe ${q.decalage.ecart_median_min} minutes après le midi solaire calculé (sur ${q.decalage.jours_mesures} jours)`)
    expect(screen.getByTestId('acal764-negatifs')).toHaveTextContent('Valeurs négatives : aucune')
    expect(screen.getByTestId('acal764-extraterrestre')).toHaveTextContent('Au-dessus du soleil du jour : aucune')
    expect(bloc).toHaveTextContent('Contrôle fait au dépôt')
    expect(bloc.querySelector('button')).toBeNull() // aucun bouton bloquant
  })

  it('ACAL764 — « avant » si l’écart est négatif ; une ligne null dit « non calculé » et son motif', async () => {
    const q = CONTRAT_METEO.exemple.qualite
    await deposerAvec({
      ...CONTRAT_METEO.exemple,
      qualite: {
        ...q,
        decalage: { ...q.decalage, ecart_median_min: -62.0 },
        extraterrestre: null,
        negatifs: { gi_w_m2: { nombre: 3, plus_petite: -4.5 } },
        motifs: { extraterrestre: 'épingle du site absente' },
      },
    })
    expect(screen.getByTestId('acal764-decalage')).toHaveTextContent('62 minutes avant le midi solaire')
    expect(screen.getByTestId('acal764-extraterrestre')).toHaveTextContent(
      'non calculé — épingle du site absente')
    expect(screen.getByTestId('acal764-negatifs')).toHaveTextContent('3 valeurs négatives')
    expect(screen.getByTestId('acal764-negatifs')).toHaveTextContent('la plus petite : −4,5 W/m²')
  })

  it('un refus qui nomme une COLONNE du CSV s’affiche sous le fichier, avec sa ligne', async () => {
    const utilisateur = userEvent.setup()
    deposerMeteoFichier.mockRejectedValue({
      response: {
        status: 400,
        data: {
          dni_w_m2: CONTRAT_METEO.exemple_refus_composante_seule.dni_w_m2,
          ligne: 2,
        },
      },
    })
    rendre()
    await utilisateur.click(screen.getByTestId('cal-series-depot-envoyer'))

    const motif = await screen.findByTestId('cal-series-depot-motif-fichier')
    expect(motif).toHaveTextContent('dni_w_m2')
    expect(motif).toHaveTextContent('global seul')
    expect(screen.getByTestId('cal-series-depot-bandeau'))
      .toHaveTextContent('ligne 2 du fichier')
    expect(screen.queryByTestId('cal-series-depot-motif-fournisseur')).toBeNull()
  })

  it('un refus qui nomme le fournisseur s’affiche SOUS ce champ-là', async () => {
    const utilisateur = userEvent.setup()
    deposerMeteoFichier.mockRejectedValue({
      response: {
        status: 400,
        data: CONTRAT_METEO.exemple_refus_sans_fournisseur,
      },
    })
    rendre()
    await utilisateur.click(screen.getByTestId('cal-series-depot-envoyer'))

    expect(await screen.findByTestId('cal-series-depot-motif-fournisseur'))
      .toHaveTextContent('provenance')
    expect(screen.queryByTestId('cal-series-depot-motif-fichier')).toBeNull()
  })
})

describe('CALX62 — le contrat committé du dépôt météo', () => {
  it('décrit la porte multipart que le panneau appelle', () => {
    expect(CONTRAT_METEO.endpoint.startsWith('POST ')).toBe(true)
    expect(CONTRAT_METEO.endpoint).toMatch(/meteo-fichier\/$/)
  })

  it('publie la provenance, et le NOMBRE de points — jamais les points', () => {
    const { meteo, serie } = CONTRAT_METEO.exemple
    expect(meteo.service).toBe('fichier')
    expect(typeof meteo.fournisseur).toBe('string')
    expect(meteo.fichier.empreinte_sha256).toHaveLength(64)
    expect(typeof serie.points).toBe('number')
    // Aucune clé de points dans le résumé : la série ne voyage pas en HTTP.
    expect(Array.isArray(serie.points)).toBe(false)
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

/* ACAL147 — la source météo RETENUE est affichée, jamais un dépôt muet. La
   réponse de `GET meteo-fichier/` reprend les valeurs du contrat
   `calepinage_meteo_fichier.json` (nom, fournisseur, empreinte du dépôt). */
describe('ACAL147 — la source météo retenue', () => {
  const depot = CONTRAT_METEO.exemple
  // ACAL363 — la réponse GET vient du contrat committé, jamais d'une valeur inventée.
  const retenu = CONTRAT_METEO.exemple_get

  it('fichier retenu affiché avec son fournisseur', async () => {
    meteoFichier.mockResolvedValue({ data: retenu })
    rendre()

    const source = await screen.findByTestId('acal147-source-meteo')
    await waitFor(() => expect(source).toHaveTextContent('Source météo : fichier meteo-2021-plan.csv'))
    expect(source).toHaveTextContent(`fournisseur ${depot.meteo.fournisseur}`)
    expect(source).toHaveTextContent('déposé le 21/09/2026 par Sami Alaoui')
    expect(source).toHaveTextContent('remplace PVGIS')
    expect(meteoFichier).toHaveBeenCalledWith(5)
  })

  it('sans fichier : « Source météo : PVGIS »', async () => {
    rendre()

    await waitFor(() => expect(screen.getByTestId('acal147-source-meteo'))
      .toHaveTextContent('Source météo : PVGIS'))
  })

  it('lecture impossible : aucune source fabriquée', async () => {
    meteoFichier.mockRejectedValue(new Error('boom'))
    rendre()

    await waitFor(() => expect(screen.getByTestId('acal147-source-meteo'))
      .toHaveTextContent('indisponible'))
    expect(screen.getByTestId('acal147-source-meteo')).not.toHaveTextContent('PVGIS')
  })
})

/* ACAL148 — « Retirer le fichier météo » et l'annonce du remplacement. Les
   réponses reprennent le contrat `calepinage_meteo_fichier.json`
   (`exemple_remplace`, `exemple_delete_404`). */
describe('ACAL148 — retirer ou remplacer le fichier météo', () => {
  // ACAL363 — la réponse GET vient du contrat committé, jamais d'une valeur inventée.
  const retenu = CONTRAT_METEO.exemple_get

  it('Retirer le fichier météo appelle DELETE puis affiche Retour à PVGIS', async () => {
    meteoFichier
      .mockResolvedValueOnce({ data: retenu })
      .mockResolvedValue({ data: null })
    retirerFichierMeteo.mockResolvedValue({ status: 204, data: null })
    rendre()

    fireEvent.click(await screen.findByTestId('acal148-retirer'))
    // Confirmation d'abord : rien n'est supprimé au premier clic.
    expect(retirerFichierMeteo).not.toHaveBeenCalled()
    fireEvent.click(screen.getByTestId('acal148-confirmer'))

    await waitFor(() => expect(retirerFichierMeteo).toHaveBeenCalledWith(5))
    expect(await screen.findByTestId('acal148-retrait')).toHaveTextContent(
      'Fichier météo retiré : meteo-2021-plan.csv — retour à PVGIS',
    )
    await waitFor(() => expect(screen.getByTestId('acal147-source-meteo'))
      .toHaveTextContent('Source météo : PVGIS'))
    expect(screen.queryByTestId('acal148-retirer')).toBeNull()
  })

  it('annuler la confirmation ne retire rien', async () => {
    meteoFichier.mockResolvedValue({ data: retenu })
    rendre()

    fireEvent.click(await screen.findByTestId('acal148-retirer'))
    fireEvent.click(screen.getByTestId('acal148-annuler'))

    expect(retirerFichierMeteo).not.toHaveBeenCalled()
    expect(screen.getByTestId('acal148-retirer')).toBeInTheDocument()
  })

  it('404 nommé : le motif du serveur est affiché, le fichier reste affiché', async () => {
    meteoFichier.mockResolvedValue({ data: retenu })
    retirerFichierMeteo.mockRejectedValue({
      response: { status: 404, data: CONTRAT_METEO.exemple_delete_404 },
    })
    rendre()

    fireEvent.click(await screen.findByTestId('acal148-retirer'))
    fireEvent.click(screen.getByTestId('acal148-confirmer'))

    expect(await screen.findByTestId('acal148-erreur'))
      .toHaveTextContent(CONTRAT_METEO.exemple_delete_404.detail)
    expect(screen.getByTestId('acal147-source-meteo')).toHaveTextContent('fichier meteo-2021-plan.csv')
  })

  it('sans le droit de gérer : aucun bouton de retrait', async () => {
    permission.gerer = false
    meteoFichier.mockResolvedValue({ data: retenu })
    rendre()

    await waitFor(() => expect(screen.getByTestId('acal147-source-meteo'))
      .toHaveTextContent('fichier meteo-2021-plan.csv'))
    expect(screen.queryByTestId('acal148-retirer')).toBeNull()
  })

  it('un dépôt sur un fichier existant annonce le remplacement', async () => {
    meteoFichier.mockResolvedValue({ data: retenu })
    deposerMeteoFichier.mockResolvedValue({ data: CONTRAT_METEO.exemple_remplace })
    rendre()

    const fichier = new File(['x'], 'meteo-2021-plan.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByTestId('cal-series-depot-fichier'), { target: { files: [fichier] } })
    fireEvent.change(screen.getByTestId('cal-series-depot-fournisseur'), { target: { value: 'Station' } })
    fireEvent.click(screen.getByTestId('cal-series-depot-envoyer'))

    const annonce = await screen.findByTestId('acal148-remplace')
    expect(annonce).toHaveTextContent(`Remplace ${CONTRAT_METEO.exemple_remplace.remplace.nom}`)
    expect(annonce).toHaveTextContent('déposé le 10/09/2026')
  })

  it('un premier dépôt n’annonce aucun remplacement', async () => {
    deposerMeteoFichier.mockResolvedValue({ data: CONTRAT_METEO.exemple })
    rendre()

    const fichier = new File(['x'], 'meteo.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByTestId('cal-series-depot-fichier'), { target: { files: [fichier] } })
    fireEvent.change(screen.getByTestId('cal-series-depot-fournisseur'), { target: { value: 'Station' } })
    fireEvent.click(screen.getByTestId('cal-series-depot-envoyer'))

    await screen.findByTestId('cal-series-depot-provenance')
    expect(screen.queryByTestId('acal148-remplace')).toBeNull()
  })
})
