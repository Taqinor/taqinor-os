import { useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { downloadBlob, filenameFromResponse } from '../../../utils/downloadBlob'
import { Button, Card, Spinner } from '../../../ui'

/* ============================================================================
   CALX360 — L'ONGLET « FIXATION » DE L'ATELIER.
   ----------------------------------------------------------------------------
   LE TROU QU'IL BOUCHE. `GET calepinages/<pk>/bom-fixation/` (CALX359,
   contrat CALX335 `contract_samples/calepinage_fixation_bom.json`) composait
   la nomenclature de fixation (rails, pinces, crochets, embouts, lests,
   visserie) mais n'avait AUCUN écran : aucun onglet ne parlait de rail, de
   pince ni de crochet. Ce panneau en est le PREMIER lecteur.

   CHOIX DU SYSTÈME. La porte accepte déjà `?systeme=<id>` (bornée à la
   société) — sans lui, elle applique l'UNIQUE système ACTIF, ou REFUSE en
   nommant pourquoi (catalogue vide, ou plusieurs systèmes actifs sans choix).
   Aucune route ne LISTE le catalogue : l'écran ne fabrique donc AUCUNE liste
   déroulante inventée — un champ SAISI (l'identifiant, tel que la société le
   connaît dans ses réglages) applique l'override, exactement ce que la porte
   sait déjà faire ; le message de refus, recopié tel quel, NOMME les systèmes
   actifs quand plusieurs le sont.

   ZÉRO CHIFFRE INVENTÉ (D-CALX 7) : une ligne dont la quantité vaut `null`
   affiche le `manquant` SERVEUR — jamais un tiret muet, jamais un zéro.

   LE TÉLÉCHARGEMENT DU CLASSEUR n'ouvre AUCUNE seconde porte : CALX359 a
   ajouté la feuille « fixation » au MÊME export général
   (`services/export_tableur.py::exporter_xlsx`, servi par `export.xlsx/`,
   CAL179) déjà inventorié par `GET sorties/` (CALX19, code `tableur_xlsx`).
   Ce panneau lit CET inventaire et télécharge son `endpoint` TEL QUEL —
   jamais un chemin reconstruit à la main.
   ========================================================================== */

const CODE_TABLEUR = 'tableur_xlsx'

/** Le corps 400/4xx d'un téléchargement (blob ou JSON), résumé en UNE phrase
    lisible — jamais un plantage muet. */
function resumerRefus(donnee) {
  if (donnee && typeof donnee === 'object' && !Array.isArray(donnee)) {
    return Object.values(donnee).map((message) => String(message)).join(' ')
  }
  return 'Le serveur a refusé le téléchargement.'
}

async function erreurDeTelechargement(erreur) {
  const donnees = erreur?.response?.data
  if (typeof Blob !== 'undefined' && donnees instanceof Blob) {
    try {
      return resumerRefus(JSON.parse(await donnees.text()))
    } catch {
      return 'Réponse du serveur illisible.'
    }
  }
  if (donnees) return resumerRefus(donnees)
  return 'Le serveur est resté injoignable.'
}

function LigneNomenclature({ ligne }) {
  const omise = ligne.quantite === null || ligne.quantite === undefined
  return (
    <tr data-testid={`calx360-ligne-${ligne.role}`}>
      <th scope="row" className="py-1 text-left font-normal">{ligne.composant}</th>
      <td className="py-1 text-xs text-muted-foreground" data-testid={`calx360-role-${ligne.role}`}>
        {ligne.role}
      </td>
      <td className="py-1 text-xs text-muted-foreground" data-testid={`calx360-regle-${ligne.role}`}>
        {ligne.regle || '—'}
      </td>
      <td className="py-1" data-testid={`calx360-quantite-${ligne.role}`}>
        {omise ? (
          <span className="text-destructive" data-testid={`calx360-manquant-${ligne.role}`}>
            {ligne.manquant}
          </span>
        ) : (
          `${ligne.quantite} ${ligne.unite || ''}`.trim()
        )}
      </td>
    </tr>
  )
}

export default function Fixation({ calepinageId: idPropose = null }) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl ?? null

  const [systemeSaisi, setSystemeSaisi] = useState('')
  const [systemeApplique, setSystemeApplique] = useState('')

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.bomFixation(
      calepinageId, systemeApplique ? { systeme: systemeApplique } : undefined,
    ),
    [calepinageId, systemeApplique],
    {
      select: (reponse) => reponse?.data ?? null,
      enabled: Boolean(calepinageId),
      errorMessage: 'La nomenclature de fixation n’a pas pu être chargée.',
    },
  )

  // L'inventaire des sorties (CALX19) — jamais une seconde source pour le
  // chemin du classeur : l'`endpoint` vient d'ICI, tel quel.
  const { data: inventaire } = useResource(
    () => calepinageApi.calepinages.sorties(calepinageId),
    calepinageId,
    { select: (reponse) => reponse?.data ?? null, enabled: Boolean(calepinageId) },
  )

  const [telechargementEnCours, setTelechargementEnCours] = useState(false)
  const [erreurTelechargement, setErreurTelechargement] = useState(null)

  const appliquerSysteme = () => setSystemeApplique(systemeSaisi.trim())

  const entreeClasseur = (inventaire?.sorties || []).find((s) => s.code === CODE_TABLEUR) || null

  const telecharger = async () => {
    if (!entreeClasseur || !calepinageId) return
    setErreurTelechargement(null)
    setTelechargementEnCours(true)
    try {
      const reponse = await calepinageApi.calepinages.telechargerSortie(entreeClasseur.endpoint)
      downloadBlob(reponse.data,
        filenameFromResponse(reponse, `fixation-calepinage-${calepinageId}.xlsx`))
    } catch (erreur) {
      setErreurTelechargement(await erreurDeTelechargement(erreur))
    } finally {
      setTelechargementEnCours(false)
    }
  }

  if (loading) return <Spinner />
  if (error) {
    return (
      <p className="text-sm text-destructive" role="alert" data-testid="calx360-erreur">{error}</p>
    )
  }
  if (!data) return null

  const lignes = Array.isArray(data.lignes) ? data.lignes : []
  const refus = Array.isArray(data.refus) ? data.refus : []

  return (
    <div className="space-y-4" data-testid="calx360-panneau">
      <Card className="p-4" data-testid="calx360-systeme">
        <h3 className="text-sm font-semibold">Choix du système</h3>
        {data.systeme ? (
          <p className="mt-1 text-sm" data-testid="calx360-systeme-applique">
            Système appliqué : <strong>{data.systeme.libelle || data.systeme.code}</strong>
            {` (${data.systeme.code})`}
          </p>
        ) : (
          <p className="mt-1 text-sm text-muted-foreground" data-testid="calx360-systeme-absent">
            Aucun système n’est appliqué.
          </p>
        )}
        <label className="mt-2 flex flex-wrap items-end gap-2" data-testid="calx360-champ-systeme">
          <span className="text-xs text-muted-foreground">
            Identifiant du système à appliquer (réglages du catalogue de fixation)
          </span>
          <input
            type="text"
            value={systemeSaisi}
            onChange={(e) => setSystemeSaisi(e.target.value)}
            className="rounded border border-input bg-card px-2 py-1 text-sm"
          />
          <Button
            type="button"
            variant="outline"
            onClick={appliquerSysteme}
            data-testid="calx360-appliquer-systeme"
          >
            Appliquer
          </Button>
        </label>
        {refus.length > 0 && (
          <ul className="mt-2 space-y-1" data-testid="calx360-refus">
            {refus.map((r, index) => (
              <li
                key={r.champ || index}
                className="text-xs text-destructive"
                data-testid={`calx360-refus-${index}`}
              >
                {r.message}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-4" data-testid="calx360-nomenclature">
        <h3 className="text-sm font-semibold">Nomenclature de fixation</h3>
        {lignes.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground" data-testid="calx360-vide">
            {refus[0]?.message || 'Aucun composant à afficher.'}
          </p>
        ) : (
          <table className="mt-2 w-full text-left text-sm" data-testid="calx360-tableau">
            <thead>
              <tr className="text-xs uppercase text-muted-foreground">
                <th scope="col" className="py-1">Composant</th>
                <th scope="col" className="py-1">Rôle</th>
                <th scope="col" className="py-1">Règle appliquée</th>
                <th scope="col" className="py-1">Quantité</th>
              </tr>
            </thead>
            <tbody>
              {lignes.map((ligne, index) => (
                <LigneNomenclature key={`${ligne.role}-${index}`} ligne={ligne} />
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card className="p-4" data-testid="calx360-telechargement">
        <h3 className="text-sm font-semibold">Classeur</h3>
        {entreeClasseur?.disponible ? (
          <Button
            type="button"
            variant="outline"
            disabled={telechargementEnCours}
            onClick={telecharger}
            data-testid="calx360-telecharger"
          >
            {telechargementEnCours ? 'Téléchargement…' : 'Télécharger le classeur (nomenclature incluse)'}
          </Button>
        ) : (
          <p className="text-xs text-muted-foreground" data-testid="calx360-telechargement-indisponible">
            {entreeClasseur?.motif_indisponible || 'Classeur non disponible.'}
          </p>
        )}
        {erreurTelechargement && (
          <p role="alert" className="mt-2 text-xs text-destructive" data-testid="calx360-erreur-telechargement">
            {erreurTelechargement}
          </p>
        )}
      </Card>
    </div>
  )
}
