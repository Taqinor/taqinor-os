import { useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Download } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import { Button, Card } from '../../../ui'
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
  for (const [champ, valeur] of Object.entries(corps)) {
    if (champ === 'exports_disponibles') continue
    const motif = Array.isArray(valeur) ? valeur[0] : valeur
    if (typeof motif === 'string' && motif.trim()) return { champ, motif }
  }
  return null
}

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
    </div>
  )
}
