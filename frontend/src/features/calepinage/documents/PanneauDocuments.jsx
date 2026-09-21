import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
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
  'plan_pose_pdf', // CALX20
  'plan_toiture_pdf', // CALX20
  'plan_masse_pdf', // CALX20 — inactif sans parcelle, motif du serveur nommant le champ.
  // CALX21 — note de calcul. Aucune logique propre : le RÉGIME D'ERREUR
  // générique (`ErreursSortie`, posé par CALX19) affiche déjà la grandeur
  // manquante que `NoteRefusee` NOMME quand un résultat partiel refuse le
  // rendu — c'est exactement « la liste NOMMÉE des valeurs indispensables
  // absentes » que la tâche demande, sans code supplémentaire ici. Aucun
  // montant n'entre dans ce panneau (la note est une pièce technique).
  'note_calcul_pdf',
  'dxf', // CALX22 — 4 calques, voir DESCRIPTIONS.
  'tableur_xlsx', // CALX22 — 3 feuilles, voir DESCRIPTIONS.
  'tableur_csv', // CALX23 — sélecteur de feuille, voir FEUILLES_CSV.
  'pack_technique', // CALX24 — POST, pas un GET : voir composerPack().
]

// CALX23 — les TROIS feuilles servies par `?feuille=`, recopiées à l'IDENTIQUE
// de `services/export_tableur.py::FEUILLES` (« Modules », « Chaînes »,
// « Nomenclature ») — jamais un nom inventé ni une quatrième feuille : le
// sélecteur ne propose QUE celles-là.
const FEUILLES_CSV = ['Modules', 'Chaînes', 'Nomenclature']

// CALX22 — ce que contient chaque export, affiché SOUS le bouton pour que
// l'utilisateur sache ce qu'il télécharge AVANT de cliquer. Noms recopiés
// TELS QUELS des services qui les produisent (jamais reformulés) :
// `services/export_dxf.py::CALQUES` (TOITURE/OBSTACLES/MODULES/COTES) et
// `services/export_tableur.py::FEUILLES` (Modules/Chaînes/Nomenclature) — la
// MÊME liste que CALX23 sert au sélecteur de feuille du CSV.
const DESCRIPTIONS = {
  dxf: 'Calques : TOITURE, OBSTACLES, MODULES, COTES.',
  tableur_xlsx: 'Feuilles du classeur : Modules, Chaînes, Nomenclature.',
}

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
    l'inventaire le dit), motif d'indisponibilité SOUS le bouton inactif.
    `libelleBouton` : « Télécharger » par défaut, remplacé pour une action
    qui n'est pas un téléchargement (CALX24 — « Composer… », une écriture). */
function CarteSortie({
  entree, enCours, onTelecharger, erreurs, description, enfant,
  libelleBouton = 'Télécharger',
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
          {libelleBouton}
        </Button>
      </div>
      {description && (
        <p
          className="mt-2 text-xs text-muted-foreground"
          data-testid={`cal-doc-description-${entree.code}`}
        >
          {description}
        </p>
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

/** CALX23 — le sélecteur de feuille du CSV. Un `<select>` NATIF plutôt que le
    composant `Select` (Radix) de `ui/` : les menus Radix portalés sont
    invisibles dans jsdom hors d'un vrai navigateur (piège catalogué), et ce
    choix n'a aucun besoin de portail. */
function SelecteurFeuilleCsv({ valeur, onChange }) {
  return (
    <label className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
      Feuille
      <select
        className="rounded border border-input bg-card px-2 py-1 text-xs text-foreground"
        value={valeur}
        onChange={(evenement) => onChange(evenement.target.value)}
        data-testid="cal-doc-feuille-csv"
      >
        {FEUILLES_CSV.map((feuille) => (
          <option key={feuille} value={feuille}>{feuille}</option>
        ))}
      </select>
    </label>
  )
}

/** CALX24 — le résultat d'une composition RÉUSSIE : le lien du document
    déposé (nom rendu par le serveur) et CHAQUE signalement affiché « en
    toutes lettres », jamais résumé. Un dossier sans signalement n'affiche
    aucune liste vide. Le lien vise `/ged` (aucune route de détail par
    document n'existe encore côté GED) — jamais un import `apps.ged` ici : ce
    module ne parle qu'à `composerPackTechnique`, une action DÉJÀ posée par le
    serveur. */
function ResultatPack({ resultat }) {
  if (!resultat) return null
  return (
    <div className="mt-2 space-y-1" data-testid="cal-doc-pack-resultat">
      <p className="text-xs text-foreground">
        Document déposé :{' '}
        <Link to="/ged" className="font-medium text-primary-text underline">
          {resultat.nom || `Dossier technique #${resultat.document}`}
        </Link>
      </p>
      {resultat.signalements?.length > 0 && (
        <ul
          className="space-y-0.5 text-xs text-muted-foreground"
          data-testid="cal-doc-pack-signalements"
        >
          {resultat.signalements.map((signalement) => (
            <li key={signalement}>{signalement}</li>
          ))}
        </ul>
      )}
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
  // CALX23 — la feuille CSV choisie, réamorcée à la première des trois servies.
  const [feuilleCsv, setFeuilleCsv] = useState(FEUILLES_CSV[0])
  // CALX24 — le dernier résultat de composition du pack technique (ou `null`).
  const [resultatPack, setResultatPack] = useState(null)

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

  // CALX24 — POST, jamais un téléchargement : succès -> `resultatPack`
  // (document déposé + signalements) ; échec -> le MÊME régime d'erreur
  // générique que tous les autres boutons (sous CETTE carte).
  async function composerPack() {
    const entree = parCode.get('pack_technique')
    if (!entree) return
    setErreurs((precedent) => ({ ...precedent, pack_technique: null }))
    setResultatPack(null)
    setEnCours('pack_technique')
    try {
      const reponse = await calepinageApi.calepinages.composerPackTechnique(id)
      setResultatPack(reponse.data)
    } catch (erreur) {
      const details = await erreurDeTelechargement(erreur)
      setErreurs((precedent) => ({ ...precedent, pack_technique: details }))
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
      {entrees.map((entree) => {
        // CALX23/CALX24 — deux codes s'écartent du téléchargement générique
        // (un sélecteur de feuille, une composition POST) : le dispatch reste
        // ICI, jamais dans `CarteSortie` elle-même (qui ne connaît AUCUN code
        // par son nom).
        if (entree.code === 'tableur_csv') {
          return (
            <CarteSortie
              key={entree.code}
              entree={entree}
              enCours={enCours === entree.code}
              onTelecharger={() => telecharger(entree.code, { feuille: feuilleCsv })}
              erreurs={erreurs[entree.code]}
              description={DESCRIPTIONS[entree.code]}
              enfant={<SelecteurFeuilleCsv valeur={feuilleCsv} onChange={setFeuilleCsv} />}
            />
          )
        }
        if (entree.code === 'pack_technique') {
          return (
            <CarteSortie
              key={entree.code}
              entree={entree}
              enCours={enCours === entree.code}
              onTelecharger={composerPack}
              erreurs={erreurs[entree.code]}
              libelleBouton="Composer le pack technique"
              enfant={<ResultatPack resultat={resultatPack} />}
            />
          )
        }
        return (
          <CarteSortie
            key={entree.code}
            entree={entree}
            enCours={enCours === entree.code}
            onTelecharger={() => telecharger(entree.code)}
            erreurs={erreurs[entree.code]}
            description={DESCRIPTIONS[entree.code]}
          />
        )
      })}
    </Card>
  )
}
