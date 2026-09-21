import { useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Download, Upload } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import { Button, Card, Input, Label } from '../../../ui'
import { downloadBlob } from '../../../utils/downloadBlob'

/* ============================================================================
   CALX6 — LE PANNEAU « SÉRIES » : les trois exports de la simulation.
   ----------------------------------------------------------------------------
   CONSTAT. La porte `calepinages/<pk>/export-csv/?quoi=…` est servie depuis
   CAL144 (`views/export_csv.py`) et `services/export_csv.py::EXPORTS` offre
   les trois sorties `horaire | mensuel | ombrage` : AUCUN écran ne les
   appelait. Un export construit et injoignable n'existe pas.

   CE PANNEAU NE CALCULE RIEN. Il ne relit ni la série, ni les agrégats : il
   demande le FICHIER au serveur et le remet au navigateur. La série horaire
   elle-même est écrite par la chaîne de pertes (CALX193) et n'est PAS
   recopiée par `GET resultat/` (D-CALX 14, volume) — il n'existe donc aucune
   lecture bon marché qui dirait d'avance « la série est là ».

   POURQUOI LE MOTIF ARRIVE APRÈS LE CLIC, ET PAS AVANT. Sonder les trois
   exports au montage voudrait dire télécharger trois fichiers (dont un de
   8 760 lignes) à chaque ouverture de l'onglet, pour n'en garder que le code
   de statut. Le bouton part donc actif ; au premier refus, il se DÉSACTIVE et
   porte SOUS lui le motif que le serveur a écrit — jamais une phrase
   fabriquée ici, jamais un « export impossible » générique (règle fondateur :
   l'erreur nomme le champ fautif, `points` / `mensuel` / `shading12x24`).

   ZÉRO CHIFFRE (D-CALX 7). Aucune valeur de production n'est affichée ni
   déduite dans ce panneau : il ne montre que des boutons, des motifs de refus
   et le nom du fichier obtenu.
   ========================================================================== */

/** Les trois exports servis, dans l'ordre où le panneau les propose. */
const EXPORTS = [
  {
    quoi: 'horaire',
    libelle: 'Série horaire (CSV)',
    aide: "Une ligne par heure : production, irradiance sur le plan et "
      + "température de l'air, précédées de leur provenance.",
  },
  {
    quoi: 'mensuel',
    libelle: 'Agrégat mensuel (CSV)',
    aide: 'Les douze mois et le total annuel, avec la même provenance.',
  },
  {
    quoi: 'ombrage',
    libelle: 'Matrice d’ombrage 12 × 24 (CSV)',
    aide: "Le facteur d'ombrage de chaque mois pour chacune des vingt-quatre "
      + 'heures, tel qu’il est tracé sur le toit.',
  },
]

const REFUS_SANS_MOTIF = (
  "Le serveur a refusé cet export sans en donner le motif : réessayez, puis "
  + 'signalez-le si le refus persiste.'
)

/**
 * Le refus du serveur, tel qu'il l'a écrit : `{champ, motif}` ou `null`.
 *
 * La réponse d'erreur arrive en BLOB (la requête demande `responseType:
 * 'blob'` pour le fichier) : il faut donc la relire en texte avant de la lire
 * en JSON. Une forme inattendue ne fabrique aucun motif — elle rend `null`,
 * et l'appelant affiche la phrase générique ci-dessus en le DISANT.
 */
async function lireRefus(erreur) {
  let corps = erreur?.response?.data
  if (corps && typeof corps.text === 'function') {
    try { corps = JSON.parse(await corps.text()) } catch { return null }
  } else if (typeof corps === 'string') {
    try { corps = JSON.parse(corps) } catch { return null }
  }
  if (!corps || typeof corps !== 'object') return null
  // CALX62 — `ligne` accompagne un refus de fichier : elle dit OÙ ouvrir le
  // CSV. Ce n'est pas un champ fautif, elle ne peut donc pas en tenir lieu.
  const ligne = Number.isFinite(corps.ligne) ? corps.ligne : null
  for (const [champ, valeur] of Object.entries(corps)) {
    if (champ === 'exports_disponibles' || champ === 'ligne') continue
    const motif = Array.isArray(valeur) ? valeur[0] : valeur
    if (typeof motif === 'string' && motif.trim()) {
      return { champ, motif, ligne }
    }
  }
  return null
}

/* ============================================================================
   CALX62 — LE DÉPÔT D'UNE SÉRIE MÉTÉO HORAIRE DE LA SOCIÉTÉ.
   ----------------------------------------------------------------------------
   Deux champs, et les deux sont obligatoires : le FICHIER (CSV à colonnes
   nommées, `horodatage` avec fuseau explicite et `gi_w_m2`) et le
   FOURNISSEUR, SAISI — une série météo dont la provenance n'est pas écrite
   devient un chiffre sans origine dès le lendemain, et l'écran n'en invente
   aucune.

   Le serveur est le seul juge du fichier : l'écran ne lit pas le CSV, ne
   compte pas ses lignes et ne devine aucune colonne. Un refus s'affiche SOUS
   le champ qu'il nomme (`fichier` ou `fournisseur` pour le formulaire, sinon
   la COLONNE du CSV), avec la ligne du fichier quand le serveur la donne.
   ========================================================================== */
const CHAMPS_DU_FORMULAIRE = new Set(['fichier', 'fournisseur'])

export default function PanneauSeries({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  // Par export : `{ etat: 'encours' | 'refus' | 'ok', champ, motif, fichier }`.
  const [sorties, setSorties] = useState({})

  const telecharger = useCallback((quoi) => {
    setSorties((precedent) => ({ ...precedent, [quoi]: { etat: 'encours' } }))
    return Promise.resolve(calepinageApi.calepinages.exportCsv(calepinageId, quoi))
      .then((res) => {
        const fichier = `calepinage-${calepinageId}-${quoi}.csv`
        downloadBlob(res?.data, fichier)
        setSorties((precedent) => ({
          ...precedent, [quoi]: { etat: 'ok', fichier },
        }))
      })
      .catch(async (erreur) => {
        const refus = await lireRefus(erreur)
        setSorties((precedent) => ({
          ...precedent,
          [quoi]: {
            etat: 'refus',
            champ: refus?.champ || '',
            motif: refus?.motif || REFUS_SANS_MOTIF,
          },
        }))
      })
  }, [calepinageId])

  return (
    <div className="mt-6" data-testid="cal-series">
      <p className="tech-label rule-brass text-brass-300">Séries</p>
      <p className="mt-2 text-xs text-lune-faint" data-testid="cal-series-rappel">
        Les trois fichiers sont produits par le serveur à partir de la
        simulation enregistrée. Tant qu’elle n’a pas tourné, l’export est
        refusé avec son motif — aucun fichier de zéros n’est livré à la place.
      </p>

      <div className="mt-3 space-y-2">
        {EXPORTS.map(({ quoi, libelle, aide }) => {
          const sortie = sorties[quoi] || {}
          const refuse = sortie.etat === 'refus'
          return (
            <Card key={quoi} className="p-3" data-testid={`cal-series-ligne-${quoi}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="space-y-0.5">
                  <div className="text-sm text-white">{libelle}</div>
                  <div className="text-xs text-muted-foreground">{aide}</div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => telecharger(quoi)}
                  disabled={refuse || sortie.etat === 'encours'}
                  data-testid={`cal-series-telecharger-${quoi}`}
                >
                  <Download className="mr-1 h-4 w-4" aria-hidden="true" />
                  {sortie.etat === 'encours' ? 'Préparation…' : 'Télécharger'}
                </Button>
              </div>

              {refuse && (
                <p
                  role="alert"
                  className="mt-2 text-sm text-destructive"
                  data-testid={`cal-series-motif-${quoi}`}
                >
                  {sortie.champ ? `${sortie.champ} : ` : ''}{sortie.motif}
                </p>
              )}
              {sortie.etat === 'ok' && (
                <p
                  className="mt-2 text-xs text-lune-soft"
                  data-testid={`cal-series-fichier-${quoi}`}
                >
                  Fichier téléchargé : {sortie.fichier}
                </p>
              )}
            </Card>
          )
        })}
      </div>

      <DepotMeteo calepinageId={calepinageId} />
    </div>
  )
}

function DepotMeteo({ calepinageId }) {
  const [fichier, setFichier] = useState(null)
  const [fournisseur, setFournisseur] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [refus, setRefus] = useState(null)
  const [depose, setDepose] = useState(null)

  const deposer = (evenement) => {
    evenement.preventDefault()
    setRefus(null)
    setDepose(null)
    setEnvoi(true)
    const corps = new FormData()
    if (fichier) corps.append('fichier', fichier)
    corps.append('fournisseur', fournisseur)
    return Promise.resolve(
      calepinageApi.calepinages.deposerMeteoFichier(calepinageId, corps))
      .then((res) => setDepose(res?.data || {}))
      .catch(async (erreur) => {
        setRefus(await lireRefus(erreur) || {
          champ: 'fichier', motif: REFUS_SANS_MOTIF, ligne: null,
        })
      })
      .finally(() => setEnvoi(false))
  }

  const refusDe = (champ) => (refus && refus.champ === champ ? refus : null)
  // Un refus qui nomme une COLONNE du CSV (et non un champ du formulaire)
  // appartient au fichier : c'est sous lui qu'il doit s'afficher.
  const refusFichier = refusDe('fichier')
    || (refus && !CHAMPS_DU_FORMULAIRE.has(refus.champ) ? refus : null)
  const refusFournisseur = refusDe('fournisseur')

  return (
    <Card className="mt-2 p-3" data-testid="cal-series-depot">
      <p className="text-sm text-white">Série météo de la société</p>
      <p className="mt-1 text-xs text-muted-foreground">
        Un CSV à colonnes nommées : « horodatage » (ISO, avec son fuseau) et
        « gi_w_m2 » (irradiance sur le PLAN) sont obligatoires ;
        « gb_i_w_m2 », « gd_i_w_m2 », « gr_i_w_m2 », « t2m_c » et « ws10m »
        entrent si elles sont là. Le serveur vérifie le fichier et refuse en
        nommant la colonne — rien n’est deviné ici.
      </p>

      {refus && (
        <p
          role="alert"
          className="mt-2 text-sm text-destructive"
          data-testid="cal-series-depot-bandeau"
        >
          Dépôt refusé : corrigez « {refus.champ} »
          {refus.ligne ? ` (ligne ${refus.ligne} du fichier)` : ''}.
        </p>
      )}

      <form className="mt-3 flex flex-col gap-2" onSubmit={deposer}>
        <div>
          <Label htmlFor="cal-series-depot-fichier">Fichier CSV</Label>
          <input
            id="cal-series-depot-fichier"
            type="file"
            accept=".csv,text/csv"
            className="mt-1 block w-full text-xs"
            onChange={(e) => setFichier(e.target.files?.[0] || null)}
            data-testid="cal-series-depot-fichier"
          />
          {refusFichier && (
            <p
              className="mt-1 text-xs text-destructive"
              data-testid="cal-series-depot-motif-fichier"
            >
              {refusFichier.champ} : {refusFichier.motif}
            </p>
          )}
        </div>

        <div>
          <Label htmlFor="cal-series-depot-fournisseur">Fournisseur</Label>
          <Input
            id="cal-series-depot-fournisseur"
            value={fournisseur}
            onChange={(e) => setFournisseur(e.target.value)}
            placeholder="Station, bureau d’études, éditeur du fichier…"
            data-testid="cal-series-depot-fournisseur"
          />
          {refusFournisseur && (
            <p
              className="mt-1 text-xs text-destructive"
              data-testid="cal-series-depot-motif-fournisseur"
            >
              {refusFournisseur.motif}
            </p>
          )}
        </div>

        <div>
          <Button
            type="submit"
            size="sm"
            variant="outline"
            disabled={envoi}
            data-testid="cal-series-depot-envoyer"
          >
            <Upload className="mr-1 h-4 w-4" aria-hidden="true" />
            {envoi ? 'Dépôt…' : 'Déposer la série météo'}
          </Button>
        </div>
      </form>

      {depose && (
        <p
          className="mt-2 text-xs text-lune-soft"
          data-testid="cal-series-depot-provenance"
        >
          {depose.message}
          {depose.meteo?.fichier?.nom
            ? ` Fichier : ${depose.meteo.fichier.nom}`
            : ''}
          {depose.meteo?.fournisseur
            ? ` · Fournisseur : ${depose.meteo.fournisseur}`
            : ''}
          {depose.serie?.points != null
            ? ` · ${depose.serie.points} heure(s)`
            : ''}
          {depose.meteo?.fenetre_annees
            ? ` · ${depose.meteo.fenetre_annees}`
            : ''}
        </p>
      )}
    </Card>
  )
}
