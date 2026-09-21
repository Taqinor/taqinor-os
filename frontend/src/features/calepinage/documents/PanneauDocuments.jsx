import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { downloadBlob, filenameFromResponse } from '../../../utils/downloadBlob'
import { Button, Card, Spinner } from '../../../ui'

/* ============================================================================
   CALX19 — LE PANNEAU « DOCUMENTS » : l'INVENTAIRE des sorties, enfin lu.
   ----------------------------------------------------------------------------
   Constat (docs/PLAN2.md, CALX19) : `views/sorties.py:171-175` (l'inventaire,
   contrat `contract_samples/calepinage_sorties.json`) et les portes qu'il
   décrit (`:177-217` planche PDF/SVG, et dix autres) sont servies et TESTÉES
   depuis longtemps — aucun consommateur `frontend/src` n'existait. Ce panneau
   est ce consommateur, monté comme un onglet de plus dans `atelier/onglets.js`
   (D-CALX 3 : un panneau = une ligne de registre, jamais une route neuve —
   voir le commentaire au-dessus de `/calepinage/:id` dans `module.config.jsx`).

   CE PANNEAU N'INVENTE RIEN. Chaque entrée affichée est EXACTEMENT une sortie
   de l'inventaire servi (`sorties()`) : le libellé, le format, si le bouton
   est actif (`disponible`) et — SINON — le motif du serveur SOUS le bouton,
   jamais recalculé ni reformulé ici (règle fondateur « erreurs = le champ
   fautif, message exact »).

   BRANCHEMENT PROGRESSIF (`CODES_GERES`, append-only) : chaque tâche du lot 6
   (CALX20 → CALX24, CALX28) AJOUTE un code à cette liste, EN FIN, avec son
   commentaire `// CALX<id>` — jamais une réécriture. Un code de l'inventaire
   absent de cette liste N'A PAS D'ENTRÉE ICI (encore) : ce panneau ne rend
   JAMAIS un bouton actif qui ne ferait rien au clic — c'est exactement le
   défaut que `check_ecrans_atteignables.py` traque ailleurs, appliqué ici au
   niveau du bouton plutôt que de l'écran.

   TÉLÉCHARGEMENT : `calepinageApi.calepinages.telechargerSortie(endpoint)`
   (CALX19) réutilise l'`endpoint` PUBLIÉ PAR LE SERVEUR — jamais un chemin
   reconstruit ici — puis `utils/downloadBlob.js` (`downloadBlob` +
   `filenameFromResponse`, l'UNIQUE helper de téléchargement du dépôt : on ne
   réinvente pas un second `URL.createObjectURL`).

   RÉGIME D'ERREUR PARTAGÉ : une sortie refusée (400, `{champ: message}` — ou
   une LISTE de signalements, CALX24) s'affiche SOUS SA PROPRE carte, jamais
   en tête de panneau — un refus sur la note de calcul ne doit pas faire
   croire que la planche a, elle aussi, échoué.
   ========================================================================== */

// Les codes de l'inventaire déjà branchés ICI. CALX19 pose les deux premiers
// (planche cotée) ; `planche_png` (conversion NAVIGATEUR du SVG frère) et
// `image_3d` (pas un fichier — son URL voyage dans l'agrégat de détail) ne
// sont jamais des téléchargements génériques de ce panneau.
const CODES_GERES = [
  'planche_pdf', // CALX19
  'planche_svg', // CALX19
]

/** Une erreur serveur -> `[{champ, message}]`, triée pour un affichage
    STABLE. Couvre les DEUX formes vues sur ce module : un objet
    `{champ: message}` (`PlancheRefusee`/`NoteRefusee`/…, un seul couple à la
    fois) et une LISTE de chaînes (les `signalements` de `pack-technique/`,
    CALX24). Jamais un message générique tant qu'un détail existe. */
function detailsErreur(donnee) {
  if (Array.isArray(donnee)) {
    return donnee.map((message, index) => ({ champ: String(index + 1), message: String(message) }))
  }
  if (donnee && typeof donnee === 'object') {
    return Object.entries(donnee)
      .map(([champ, message]) => ({ champ, message: String(message) }))
      .sort((a, b) => a.champ.localeCompare(b.champ))
  }
  return [{ champ: '', message: 'Le serveur a refusé la demande, sans détail lisible.' }]
}

/** Le corps JSON d'une erreur axios dont la réponse est un BLOB
    (`responseType: 'blob'` — c'est le cas de tout téléchargement de ce
    panneau) : le corps d'erreur voyage lui aussi en blob, il faut le relire
    en texte avant de le parser. Sans réponse du tout (réseau coupé), un motif
    générique — jamais un plantage muet. */
async function erreurDeTelechargement(erreur) {
  const donnees = erreur?.response?.data
  if (typeof Blob !== 'undefined' && donnees instanceof Blob) {
    try {
      return detailsErreur(JSON.parse(await donnees.text()))
    } catch {
      return [{ champ: '', message: 'Réponse du serveur illisible.' }]
    }
  }
  if (donnees) return detailsErreur(donnees)
  return [{ champ: '', message: 'Le serveur est resté injoignable.' }]
}

/** La liste des motifs/signalements d'une carte — jamais en tête de panneau. */
function ErreursSortie({ erreurs }) {
  if (!erreurs?.length) return null
  return (
    <ul
      role="alert"
      className="mt-2 space-y-0.5 text-xs text-destructive"
      data-testid="cal-doc-erreurs"
    >
      {erreurs.map((e) => (
        <li key={`${e.champ}-${e.message}`}>
          {e.champ ? <strong>{e.champ}</strong> : null}
          {e.champ ? ' — ' : ''}
          {e.message}
        </li>
      ))}
    </ul>
  )
}

/** Une carte de sortie : libellé, format, bouton (actif seulement si
    l'inventaire le dit), motif d'indisponibilité SOUS le bouton inactif. */
function CarteSortie({
  entree, enCours, onTelecharger, erreurs, description, enfant,
}) {
  return (
    <div
      className="rounded-md border border-border/60 p-3"
      data-testid={`cal-doc-sortie-${entree.code}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-foreground">{entree.libelle}</p>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">{entree.format}</p>
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={!entree.disponible}
          loading={enCours}
          onClick={onTelecharger}
          data-testid={`cal-doc-bouton-${entree.code}`}
        >
          Télécharger
        </Button>
      </div>
      {description && (
        <p className="mt-2 text-xs text-muted-foreground">{description}</p>
      )}
      {!entree.disponible && (
        <p
          className="mt-2 text-xs text-muted-foreground"
          data-testid={`cal-doc-motif-${entree.code}`}
        >
          {entree.motif_indisponible}
        </p>
      )}
      {enfant}
      <ErreursSortie erreurs={erreurs} />
    </div>
  )
}

export default function PanneauDocuments({ calepinageId }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.sorties(id), id,
    { select: (r) => r.data, errorMessage: 'Inventaire des documents indisponible.' },
  )

  // `code` en téléchargement -> vrai. `code` -> `[{champ,message}]` en refus.
  const [enCours, setEnCours] = useState(null)
  const [erreurs, setErreurs] = useState({})

  const parCode = useMemo(() => {
    const carte = new Map()
    for (const entree of data?.sorties || []) carte.set(entree.code, entree)
    return carte
  }, [data])

  async function telecharger(code, params) {
    const entree = parCode.get(code)
    if (!entree) return
    setErreurs((precedent) => ({ ...precedent, [code]: null }))
    setEnCours(code)
    try {
      const reponse = await calepinageApi.calepinages.telechargerSortie(entree.endpoint, params)
      downloadBlob(reponse.data, filenameFromResponse(reponse, entree.code))
    } catch (erreur) {
      const details = await erreurDeTelechargement(erreur)
      setErreurs((precedent) => ({ ...precedent, [code]: details }))
    } finally {
      setEnCours(null)
    }
  }

  if (loading) return <Spinner />
  if (error) {
    return <p className="text-sm text-destructive" data-testid="cal-doc-erreur">{error}</p>
  }

  const entrees = CODES_GERES.map((code) => parCode.get(code)).filter(Boolean)

  return (
    <Card className="flex flex-col gap-3 p-4" data-testid="cal-doc-panneau">
      <h2 className="text-base font-semibold">Documents</h2>
      {entrees.length === 0 && (
        <p className="text-sm text-muted-foreground" data-testid="cal-doc-vide">
          Aucun document disponible pour l’instant.
        </p>
      )}
      {entrees.map((entree) => (
        <CarteSortie
          key={entree.code}
          entree={entree}
          enCours={enCours === entree.code}
          onTelecharger={() => telecharger(entree.code)}
          erreurs={erreurs[entree.code]}
        />
      ))}
    </Card>
  )
}
