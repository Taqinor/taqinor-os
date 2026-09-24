import { useMemo, useState } from 'react'
import { Plus, Tag as IconeEtiquette, X } from 'lucide-react'
import calepinageApi from '../../api/calepinageApi'
import recordsApi from '../../api/recordsApi'
import useResource from '../../hooks/useResource'
import { unwrapList } from '../../api/resource'

/* ============================================================================
   CALX344 — LES ÉTIQUETTES LIBRES d'un calepinage : fiche ET filtre de liste.
   ----------------------------------------------------------------------------
   La moitié SERVEUR existe (`views/etiquettes.py`, CALX343) et sa forme est
   figée par `contract_samples/calepinage_etiquettes.json` (CALX332) : les trois
   méthodes (lire, poser, retirer) rendent la liste À JOUR
   `{etiquettes: [{id, nom, couleur}]}`. L'écran AFFICHE cette réponse telle
   quelle — il ne recompose jamais la liste lui-même, et un retrait fait
   disparaître le jeton SANS second appel ni rechargement.

   LE VOCABULAIRE SE CHOISIT, IL NE SE CRÉE PAS ICI. Les étiquettes proposées
   viennent du vocabulaire de la société (`records`, `recordsApi.getTags`,
   FG9) ; le serveur refuse toute création à la volée en NOMMANT le champ, et
   son motif est affiché tel quel sous le sélecteur.

   LE DRAPEAU « MODÈLE » N'EST PAS UNE ÉTIQUETTE. `calepinage:modele` (CAL199)
   est le tag SYSTÈME de la bibliothèque : le contrat le déclare EXCLU
   (`exclu_de_la_liste`) — il n'est donc jamais proposé, ni ici ni dans le
   filtre de la liste.

   LA COULEUR est `Tag.couleur` telle quelle (`#rrggbb`) ; vide ⇒ couleur par
   défaut du jeton — jamais une couleur inventée par étiquette.
   ========================================================================== */

/** Le tag système exclu par le contrat (`exclu_de_la_liste`, CALX332). */
const TAG_SYSTEME = 'calepinage:modele'

const HEX = /^#[0-9a-f]{6}$/i

/** Le motif du serveur, tel quel — jamais un « non enregistré » générique. */
function motifServeur(erreur, repli) {
  const corps = erreur?.response?.data
  if (corps && typeof corps === 'object') {
    const premier = corps.tag_id ?? corps.nom ?? corps.etiquette ?? corps.detail
      ?? Object.values(corps)[0]
    if (premier) return Array.isArray(premier) ? premier.join(' ') : String(premier)
  }
  return repli
}

/** Le vocabulaire de la société, SANS le tag système. */
function vocabulaireLibre(reponse) {
  return unwrapList(reponse)
    .filter((tag) => tag && tag.nom !== TAG_SYSTEME)
    .map((tag) => ({ id: tag.id, nom: tag.nom, couleur: tag.couleur || '' }))
}

/** UN jeton d'étiquette, coloré par `Tag.couleur` quand il est valide. */
export function JetonEtiquette({ etiquette, onRetirer = null, testId }) {
  const couleur = HEX.test(etiquette?.couleur || '') ? etiquette.couleur : null
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border border-white/20 px-2 py-0.5 text-xs"
      style={couleur ? { borderColor: couleur, color: couleur } : undefined}
      data-testid={testId}
    >
      <IconeEtiquette size={12} aria-hidden="true" />
      {etiquette.nom}
      {onRetirer ? (
        <button
          type="button"
          className="ml-0.5 opacity-70 hover:opacity-100"
          aria-label={`Retirer l’étiquette ${etiquette.nom}`}
          onClick={() => onRetirer(etiquette)}
        >
          <X size={12} aria-hidden="true" />
        </button>
      ) : null}
    </span>
  )
}

/* ── La fiche : lire, poser, retirer ─────────────────────────────────────── */
export default function Etiquettes({ calepinageId, peutGerer = false }) {
  // Même prudence que la bascule « modèle » de la fiche : sans porte, on se
  // tait (jamais une erreur affichée pour une capacité absente).
  const disponible = typeof calepinageApi?.calepinages?.etiquettes === 'function'
    && Boolean(calepinageId)

  const { data, error } = useResource(
    (p) => calepinageApi.calepinages.etiquettes(p.id),
    { id: calepinageId },
    {
      enabled: disponible,
      select: (res) => (Array.isArray(res?.data?.etiquettes) ? res.data.etiquettes : []),
      errorMessage: (e) => motifServeur(e, 'Étiquettes indisponibles.'),
    },
  )
  // La réponse d'un geste REMPLACE la liste affichée : le serveur la rend à
  // jour, l'écran n'a rien à recomposer ni à recharger.
  const [apresGeste, setApresGeste] = useState(null)
  const [choix, setChoix] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const [refus, setRefus] = useState(null)

  const vocabulaire = useResource(
    () => recordsApi.getTags(),
    null,
    { enabled: choix, select: vocabulaireLibre, errorMessage: 'Vocabulaire indisponible.' },
  )

  const liste = useMemo(() => apresGeste ?? data ?? [], [apresGeste, data])
  const proposables = useMemo(() => {
    const poses = new Set(liste.map((e) => e.id))
    return (vocabulaire.data ?? []).filter((tag) => !poses.has(tag.id))
  }, [liste, vocabulaire.data])

  if (!disponible) return null

  const geste = async (appel, repli) => {
    setRefus(null)
    setEnCours(true)
    try {
      const reponse = await appel()
      setApresGeste(Array.isArray(reponse?.data?.etiquettes) ? reponse.data.etiquettes : [])
      return true
    } catch (err) {
      setRefus(motifServeur(err, repli))
      return false
    } finally {
      setEnCours(false)
    }
  }

  const poser = async (tag) => {
    const ok = await geste(() => calepinageApi.calepinages.poserEtiquette(calepinageId, tag.id),
      'L’étiquette n’a pas pu être posée.')
    if (ok) setChoix(false)
  }
  const retirer = (etiquette) => geste(
    () => calepinageApi.calepinages.retirerEtiquette(calepinageId, etiquette.id),
    'L’étiquette n’a pas pu être retirée.')

  return (
    <div className="mt-4" data-testid="cal-etiquettes">
      <p className="tech-label text-lune-faint">Étiquettes</p>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        {liste.length === 0 && !error ? (
          <span className="text-sm text-lune-faint">Aucune étiquette</span>
        ) : null}
        {liste.map((etiquette) => (
          <JetonEtiquette
            key={etiquette.id}
            etiquette={etiquette}
            testId={`cal-etiquette-${etiquette.id}`}
            onRetirer={peutGerer && !enCours ? retirer : null}
          />
        ))}
        {peutGerer ? (
          <button
            type="button"
            className="inline-flex items-center gap-1 text-xs text-brass-300 underline"
            onClick={() => { setChoix((ouvert) => !ouvert); setRefus(null) }}
            data-testid="cal-etiquettes-ajouter"
          >
            <Plus size={12} aria-hidden="true" />
            Ajouter une étiquette
          </button>
        ) : null}
      </div>
      {error ? <p className="mt-1 text-xs text-lune-faint">{error}</p> : null}

      {choix ? (
        <div className="mt-2 flex flex-wrap gap-2" data-testid="cal-etiquettes-choix">
          {vocabulaire.loading ? <span className="text-xs text-lune-faint">Chargement…</span> : null}
          {vocabulaire.error ? <span className="text-xs text-lune-faint">{vocabulaire.error}</span> : null}
          {!vocabulaire.loading && !vocabulaire.error && proposables.length === 0 ? (
            <span className="text-xs text-lune-faint">
              Aucune autre étiquette dans le vocabulaire de la société.
            </span>
          ) : null}
          {proposables.map((tag) => (
            <button
              key={tag.id}
              type="button"
              disabled={enCours}
              onClick={() => poser(tag)}
              data-testid={`cal-etiquettes-proposer-${tag.id}`}
            >
              <JetonEtiquette etiquette={tag} />
            </button>
          ))}
        </div>
      ) : null}

      {/* L'ERREUR SOUS LE GESTE — le motif du serveur, tel quel. */}
      {refus ? (
        <p className="mt-1 text-xs text-alert-300" role="alert" data-testid="cal-etiquettes-erreur">
          {refus}
        </p>
      ) : null}
    </div>
  )
}

/* ── Le filtre de la LISTE (`?etiquette=`, ET logique) ────────────────────
   `valeur` : les étiquettes RETENUES (`[{id, nom, couleur}]`) ; `onChange`
   reçoit la nouvelle sélection. Le vocabulaire n'est chargé qu'à l'ouverture
   du sélecteur : une liste sans filtre n'interroge rien de plus. */
export function FiltreEtiquettes({ valeur = [], onChange }) {
  const [ouvert, setOuvert] = useState(false)
  const vocabulaire = useResource(
    () => recordsApi.getTags(),
    null,
    { enabled: ouvert, select: vocabulaireLibre, errorMessage: 'Vocabulaire indisponible.' },
  )
  const retenus = new Set(valeur.map((e) => e.id))
  const basculer = (tag) => onChange(retenus.has(tag.id)
    ? valeur.filter((e) => e.id !== tag.id)
    : [...valeur, tag])

  return (
    <div className="space-y-1" data-testid="cal-filtre-etiquettes">
      <div className="flex flex-wrap items-center gap-2">
        {valeur.map((etiquette) => (
          <JetonEtiquette
            key={etiquette.id}
            etiquette={etiquette}
            testId={`cal-filtre-etiquette-${etiquette.id}`}
            onRetirer={(e) => onChange(valeur.filter((autre) => autre.id !== e.id))}
          />
        ))}
        <button
          type="button"
          className="inline-flex items-center gap-1 text-xs underline"
          aria-expanded={ouvert}
          onClick={() => setOuvert((o) => !o)}
          data-testid="cal-filtre-etiquettes-ouvrir"
        >
          <IconeEtiquette size={12} aria-hidden="true" />
          Filtrer par étiquette
        </button>
      </div>
      {ouvert ? (
        <div className="flex flex-wrap gap-2" data-testid="cal-filtre-etiquettes-choix">
          {vocabulaire.loading ? <span className="text-xs text-muted-foreground">Chargement…</span> : null}
          {vocabulaire.error ? <span className="text-xs text-muted-foreground">{vocabulaire.error}</span> : null}
          {(vocabulaire.data ?? []).map((tag) => (
            <button
              key={tag.id}
              type="button"
              aria-pressed={retenus.has(tag.id)}
              onClick={() => basculer(tag)}
              data-testid={`cal-filtre-etiquettes-option-${tag.id}`}
              className={retenus.has(tag.id) ? 'font-semibold' : undefined}
            >
              <JetonEtiquette etiquette={tag} />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
