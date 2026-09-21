import { useCallback, useMemo, useState } from 'react'
import { AlertTriangle, Minus, Maximize2, Plus, RefreshCw, Sparkles } from 'lucide-react'
import { Badge, Button, EmptyState, Skeleton, toast } from '../../../ui'
import { cn } from '../../../lib/cn'
import aoApi from '../../../api/aoApi'
import { unwrapList } from '../../../api/resource'
import PlanLayer from './PlanLayer'
import VerdictBar from './VerdictBar'
import TiroirKits from './TiroirKits'
import TiroirAllees from './TiroirAllees'
import TiroirRives from './TiroirRives'
import TiroirOrientation from './TiroirOrientation'
import TiroirElectrique from './TiroirElectrique'
import ModeExpert from './ModeExpert'
import SuggestionsPanel from './SuggestionsPanel'
import useCalepinage from './useCalepinage'
import useCalepinageImpose from './useCalepinageImpose'
import planDepuisResultat from './planDepuisResultat'

/* ============================================================================
   AOF92 — `CalepinageStudio` : la coquille de l'atelier de calepinage.
   ----------------------------------------------------------------------------
   RECÂBLAGE DU 03/08/2026. L'atelier était piloté par un `calepinageId` et
   chargeait `/ao/calepinages/<id>/` — une ressource que le serveur n'a jamais
   servie (aucun modèle `Calepinage` n'existe). Il n'affichait donc QUE des
   erreurs. Il est désormais piloté par un **`toitureId`** et fait ce que le
   serveur sait faire : `POST /ao/calepinage/calculer/` (et, au-delà du budget
   synchrone, `lancer` + `resultat/<job>/` — c'est le SERVEUR qui bascule).

   La coquille ne possède que la FENÊTRE d'affichage (zoom, recadrage) — jamais
   une grandeur métier. Tout ce qui est dérivé (barre de verdict + plan) est
   estompé pendant un calcul en vol : on n'affiche jamais un ancien chiffre
   comme s'il était courant (AOF93/AOF94).

   Zoom : la molette (avec Ctrl/⌘) et les trois boutons agissent sur le viewBox
   SVG — aucune position n'est recalculée.

   ── PV51 — L'INSPECTEUR EST ALIMENTÉ, POUR DE VRAI ────────────────────────
   Les cinq tiroirs (AOF95-99) sont pilotés par des DESCRIPTEURS serveur
   (`donnees` : champs, bornes, presets, impacts, recommandations). PV49/PV50/
   PV44 les publient désormais DANS le résultat même de `/ao/calepinage/
   calculer|lancer/+résultat/` : `resultat.tiroirs.{kits,allees,rives,
   orientation,electrique}`, `resultat.marges` et `resultat.suggestions`
   (`calepinage_service.calepiner(..., tiroirs=True, suggestions=True)` par
   défaut — voir `apps/ao/calepinage_service.py` et le contrat
   `apps/ao/contract_samples/calepinage_tiroirs.json`). Chaque tiroir garde sa
   garde `if (!donnees) return null` : une toiture multi-surfaces ou hors
   budget de charge utile reste dégradée (`donnees: null`) SANS que l'écran
   n'invente rien — mais il n'y a plus de bandeau statique prétendant
   qu'aucune route ne les sert.

   Les paramètres restent, tant qu'aucun tiroir n'a encore été touché, ceux du
   preset de la toiture (`ToitureAO.parametres_calepinage`), appliqués côté
   SERVEUR quand le corps n'envoie pas de `params`.

   ── PACT168/PV51 — MODE EXPERT ET SUGGESTIONS, MONTÉS ET ALIMENTÉS ────────
   `ModeExpert` (AOF101, qui révèle `RobustesseBadges`) et `SuggestionsPanel`
   (AOF100) sont montés À CÔTÉ des tiroirs, avec le même principe :

     · `ModeExpert` pilote de VRAIS paramètres (pas de recherche, seuils,
       phase, mode de pose) : son `onChange` est le MÊME `majParametres` que
       les tiroirs, donc le serveur recalcule (AOF94). Son interrupteur est
       mémorisé côté navigateur (`safeStorage`) ;
     · `RobustesseBadges` n'affiche des marges que si le moteur en publie
       (`resultat.marges`, `Optional[Marges]` dans `core/calepinage/types.py`) ;
       les seuils sont la CONVERSION en centimètres des paramètres courants,
       jamais une valeur inventée ;
     · `SuggestionsPanel` affiche les suggestions RÉELLES du moteur
       (`resultat.suggestions`, PV50). Chaque suggestion porte une `action`
       DISCRIMINÉE par `action.type` (`apps/ao/calepinage_io.action_de_patch`) :
       `'parametres'` rejoue `action.patch` par la voie normale des paramètres
       (`majParametres`) — le gain est donc RE-VÉRIFIÉ par le moteur, jamais
       cru sur parole ; `'obstacle'` retrouve l'`ObstacleAO` de la toiture par
       son `repere` (`action.obstacle`) et lui PATCH sa `provenance`
       (`action.provenance` — `ECARTE`/`MESURE`), puis force un recalcul :
       l'obstacle est une ressource PERSISTÉE, jamais un paramètre du corps
       de `/calculer/`.

   ── PV31/PV32 — MODE « RANGÉES IMPOSÉES PAR L'UTILISATEUR » ────────────────
   `useCalepinageImpose` (PV31) tient le BROUILLON local des rangées éditées
   à la main ; chaque geste (glisser/ajouter/supprimer) repasse par
   `majParametres` — donc par le MÊME anti-rebond/garde de séquence que les
   tiroirs — et c'est le SERVEUR qui recalcule et publie le plan RÉEL (jamais
   une table dessinée localement). `PlanLayer` reçoit les bandes d'accroche
   (`impose.lignesAffichees`) et l'aperçu de glissé (`impose.yPropose`) en
   PLUS du plan, jamais à la place de lui.

   `majParametres` retire désormais du patch fusionné toute clé qui vaut
   `undefined` : c'est ce qui permet à « Revenir au calcul optimal » (PV32)
   d'effacer VRAIMENT `mode_pose`/`rangees_imposees` du corps envoyé au
   serveur (qui retombe alors sur le preset enregistré de la toiture) plutôt
   que d'y laisser une clé fantôme à `undefined`.

   PV32 — l'écart à l'optimum et le bouton « Enregistrer comme variante »
   vivent dans `VerdictBar` (affichage) + ici (l'appel réseau, comme
   `definirRetenue` dans `VariantesCompare.jsx`). Le garde-fou de confirmation
   avant de perdre un brouillon divergent (`isDraftDirty`) ne couvre QUE
   « Revenir au calcul optimal » — la seule action de cet écran qui EFFACE
   réellement le brouillon ; un changement de tiroir ne le fait pas (il
   fusionne son patch SANS toucher `mode_pose`/`rangees_imposees`).

   ── PV51/PV67 — « GÉNÉRER DES VARIANTES » ─────────────────────────────────
   L'action porte sur la VARIANTE RETENUE de la toiture (`CalepinageVarianteViewSet.
   generer_variantes`, `POST /ao/calepinage/variantes/<id>/generer-variantes/`) :
   elle rejoue 2 à 4 alternatives d'ORIENTATION à partir d'elle. Le studio
   n'a qu'un `toitureId`, jamais un id de variante — le clic RETROUVE donc la
   variante retenue de cette toiture (`aoApi.variantes.list({toiture,
   est_retenue: true})`) avant d'appeler l'action ; sans variante retenue, le
   bouton le DIT (même motif que le 400 `retenue` que le serveur renverrait de
   toute façon) plutôt que d'appeler un endpoint sans cible valide.
   ========================================================================== */

const ZOOM_MIN = 0.25
const ZOOM_MAX = 12
const PAS_ZOOM = 1.25

const borne = (valeur) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, valeur))

// PV32 — nom auto « Plan imposé du JJ/MM » : formatage de PRÉSENTATION d'une
// `Date` locale, pas un chiffre métier (aucune donnée du moteur n'y entre).
function jourMois(date) {
  const jj = String(date.getDate()).padStart(2, '0')
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  return `${jj}/${mm}`
}

// L'ERREUR SERVEUR TELLE QUELLE — `charge.detail` couvre `lancer()` (persister
// une variante), mais PV67 (`generer-variantes`) répond en 400 NOMMÉ
// (`{retenue: […]}` / `{entree: […]}` / `{calepinage: […]}`), sans `detail` :
// le premier motif d'un champ est repris tel quel plutôt que de retomber sur
// le message générique alors que le serveur en a publié un précis.
function messageErreurVariante(err, repli) {
  const charge = err?.response?.data
  if (typeof charge?.detail === 'string' && charge.detail) return charge.detail
  if (charge && typeof charge === 'object') {
    for (const valeur of Object.values(charge)) {
      const brut = Array.isArray(valeur) ? valeur[0] : valeur
      if (typeof brut === 'string' && brut) return brut
    }
  }
  return repli
}

/**
 * @param {number|string} toitureId  Toiture à calepiner (`ToitureAO.id`).
 * @param {Function} [onConformite]  Remontée de conformité du tiroir électrique.
 * @param {Function} [onVarianteEnregistree]  PV32 — INJECTÉ par l'appelant (même
 *   patron que `exporterImage` d'AOF75) : appelé après un enregistrement réussi
 *   du brouillon comme variante ALTERNATIVE, pour une navigation éventuelle vers
 *   le comparateur. Sans lui, l'écran reste honnête : un simple texte indique où
 *   retrouver la variante, jamais un lien qui ne mène nulle part.
 */
export default function CalepinageStudio({ toitureId, onConformite, onVarianteEnregistree }) {
  const [zoom, setZoom] = useState(1)
  // Paramètres pilotés par les tiroirs. `null` = « laisse le serveur appliquer
  // le preset de la toiture » — jamais un jeu de valeurs par défaut inventé ici.
  const [parametres, setParametres] = useState(null)

  const {
    resultat, perime, enVol, chargementInitial, erreur, progression, recalculer,
  } = useCalepinage(toitureId, parametres)

  // Traduction de RENDU uniquement (coins de rectangle → rectangles SVG +
  // fenêtre) : aucune grandeur métier n'y est dérivée. Voir `planDepuisResultat`.
  const plan = useMemo(() => planDepuisResultat(resultat), [resultat])

  // Un tiroir ne modifie JAMAIS un résultat : il remonte un patch de
  // paramètres, et c'est le serveur qui recalcule (AOF94). Une clé du patch
  // qui vaut `undefined` est RETIRÉE après fusion (pas laissée en fantôme) :
  // c'est ce qui permet à PV32 (« Revenir au calcul optimal ») d'effacer
  // vraiment `mode_pose`/`rangees_imposees` du corps envoyé au serveur.
  const majParametres = useCallback((patch) => {
    setParametres((courants) => {
      const suivant = { ...(courants || {}), ...patch }
      for (const cle of Object.keys(suivant)) {
        if (suivant[cle] === undefined) delete suivant[cle]
      }
      return suivant
    })
  }, [])

  // PV31 — brouillon local des rangées imposées par l'utilisateur.
  const impose = useCalepinageImpose({ resultat, majParametres, toitureId })

  const [enregistrementEnCours, setEnregistrementEnCours] = useState(false)

  const quitterModeImpose = useCallback(() => {
    // Même patron que `ObjetsPersonnalisesPage.jsx` : `window.confirm` direct,
    // une confirmation légère pour une action réversible.
    if (impose.isDraftDirty && !window.confirm(
      'Des rangées imposées non enregistrées comme variante seront perdues. '
      + 'Revenir au calcul optimal ?',
    )) return
    impose.quitter()
  }, [impose])

  const enregistrerCommeVariante = useCallback(async () => {
    if (!impose.actif || !toitureId) return
    setEnregistrementEnCours(true)
    try {
      const reponse = await aoApi.calepinage.lancer({
        toiture: toitureId,
        params: { ...(parametres || {}), mode_pose: 'rangees_imposees_utilisateur', rangees_imposees: impose.draft },
        persister: true,
        role: 'ALTERNATIVE',
        nom: `Plan imposé du ${jourMois(new Date())}`,
      })
      toast.success(
        'Variante enregistrée — non publiable (sous l’optimum). Retrouvez-la '
        + 'dans l’onglet « Variantes » de cette affaire pour la comparer.',
      )
      onVarianteEnregistree?.(reponse?.data)
    } catch (err) {
      toast.error(messageErreurVariante(err, 'Impossible d’enregistrer ce plan comme variante.'))
    } finally {
      setEnregistrementEnCours(false)
    }
  }, [impose.actif, impose.draft, toitureId, parametres, onVarianteEnregistree])

  const [generationVariantesEnCours, setGenerationVariantesEnCours] = useState(false)

  // PV51/PV67 — retrouve la variante RETENUE de la toiture (le studio ne
  // connaît que le `toitureId`, pas d'id de variante) avant d'appeler
  // l'action serveur qui pose les alternatives d'orientation.
  const genererVariantes = useCallback(async () => {
    if (!toitureId) return
    setGenerationVariantesEnCours(true)
    try {
      const variantes = unwrapList(await aoApi.variantes.list({ toiture: toitureId, est_retenue: true }))
      const retenue = variantes[0]
      if (!retenue) {
        toast.error(
          'Cette toiture n’a aucune variante retenue : calculez un calepinage '
          + 'et retenez-le avant de générer des alternatives d’orientation.',
        )
        return
      }
      await aoApi.calepinage.variantes.genererVariantes(retenue.id)
      toast.success(
        'Variantes d’orientation générées — retrouvez-les dans l’onglet '
        + '« Variantes » de cette affaire pour les comparer.',
      )
    } catch (err) {
      toast.error(messageErreurVariante(err, 'Impossible de générer les variantes d’orientation.'))
    } finally {
      setGenerationVariantesEnCours(false)
    }
  }, [toitureId])

  /* ── PACT168 — suggestions du moteur ──────────────────────────────────────
     `historique` est tenu ICI : une suggestion appliquée quitte la liste
     actionnable et se retrouve marquée dans l'historique, exactement comme le
     contrat d'AOF100 le décrit — sans quoi on pourrait « appliquer » deux fois
     le même patch et croire avoir gagné deux fois les mêmes modules. */
  const [historiqueSuggestions, setHistoriqueSuggestions] = useState([])
  const [codeApplique, setCodeApplique] = useState(null)
  const [questionSuggeree, setQuestionSuggeree] = useState(null)

  const marquerSuggestionAppliquee = useCallback((suggestion) => {
    setHistoriqueSuggestions((liste) => (
      liste.some((s) => s.code === suggestion.code)
        ? liste
        : [...liste, {
          code: suggestion.code,
          titre: suggestion.titre,
          gain_modules: suggestion.gain_modules,
          gain_kwc: suggestion.gain_kwc,
        }]
    ))
  }, [])

  // PV51 — `action.type` DISCRIMINE ce qu'« Appliquer » doit faire
  // (`apps/ao/calepinage_io.action_de_patch`, contrat `calepinage_suggestions.
  // json`) : un patch de PARAMÈTRES rejoue la voie normale (`majParametres`,
  // AOF94) ; une décision d'OBSTACLE écrit sur la ressource PERSISTÉE
  // (`ObstacleAO`, retrouvée par son `repere` parmi les obstacles de la
  // toiture) puis force le recalcul — un obstacle n'est PAS un paramètre du
  // corps de `/calculer/`.
  const appliquerSuggestion = useCallback(async (suggestion) => {
    const action = suggestion.action ?? {}
    if (action.type === 'obstacle') {
      setCodeApplique(suggestion.code)
      try {
        const obstacles = unwrapList(await aoApi.obstacles.list({ toiture: toitureId }))
        const cible = obstacles.find((o) => o.repere === action.obstacle)
        if (!cible) {
          toast.error(
            `Obstacle « ${action.obstacle} » introuvable sur cette toiture — décision non appliquée.`,
          )
          setCodeApplique(null)
          return
        }
        await aoApi.obstacles.update(cible.id, { provenance: action.provenance })
        marquerSuggestionAppliquee(suggestion)
        await recalculer()
      } catch (err) {
        setCodeApplique(null)
        toast.error(messageErreurVariante(err, 'Impossible d’appliquer cette décision d’obstacle.'))
      }
      return
    }

    setCodeApplique(suggestion.code)
    marquerSuggestionAppliquee(suggestion)
    // La voie NORMALE des paramètres : c'est le moteur qui recalcule et qui
    // dira si le gain annoncé était réel (AOF94).
    majParametres(action.patch ?? {})
  }, [majParametres, marquerSuggestionAppliquee, recalculer, toitureId])

  // Seuils de robustesse : simple CONVERSION m → cm des paramètres courants
  // (`RobustesseBadges` les compare aux marges du moteur). Aucun seuil par
  // défaut n'est inventé : sans paramètre, le badge s'affiche sans seuil.
  const seuilsRobustesse = useMemo(() => ({
    troncon_min_cm: Number.isFinite(parametres?.marge_troncon_min_m)
      ? parametres.marge_troncon_min_m * 100 : undefined,
    bande_min_cm: Number.isFinite(parametres?.marge_bande_min_m)
      ? parametres.marge_bande_min_m * 100 : undefined,
  }), [parametres])

  const onWheel = useCallback((event) => {
    if (!event.ctrlKey && !event.metaKey) return
    event.preventDefault()
    setZoom((z) => borne(event.deltaY < 0 ? z * PAS_ZOOM : z / PAS_ZOOM))
  }, [])

  if (chargementInitial) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-48" />
        {progression && (
          <p className="text-sm text-muted-foreground" role="status" data-progression={progression.statut}>
            Calcul en tâche de fond — {progression.pct} %
          </p>
        )}
        <Skeleton className="h-[60vh] w-full" />
      </div>
    )
  }

  // L'ERREUR SERVEUR S'AFFICHE TELLE QUELLE — jamais un écran blanc, jamais
  // « une erreur est survenue ».
  if (erreur && !resultat) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Calepinage indisponible"
        description={erreur}
        action={<Button size="sm" variant="outline" onClick={recalculer}>Réessayer</Button>}
      />
    )
  }

  if (!plan) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Aucune table posée"
        description={"Le moteur n'a posé aucune table sur cette toiture : vérifiez son enveloppe, "
          + 'ses obstacles et le preset de calepinage.'}
        action={<Button size="sm" variant="outline" onClick={recalculer}>Recalculer</Button>}
      />
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Atelier de calepinage</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Plan calculé par le moteur — affiché tel quel, aucune position recalculée.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* PV51/PV67 — pose 2 à 4 alternatives d'orientation à partir de la
              variante RETENUE de cette toiture (le studio retrouve son id au
              clic, voir `genererVariantes`). */}
          <Button
            size="sm"
            variant="outline"
            loading={generationVariantesEnCours}
            disabled={generationVariantesEnCours}
            onClick={genererVariantes}
          >
            <Sparkles className="size-4" aria-hidden="true" />
            Générer des variantes
          </Button>
          <div className="flex items-center gap-1" role="group" aria-label="Zoom du plan">
            <Button size="sm" variant="outline" aria-label="Dézoomer" onClick={() => setZoom((z) => borne(z / PAS_ZOOM))}>
              <Minus className="size-4" aria-hidden="true" />
            </Button>
            <Button size="sm" variant="outline" aria-label="Ajuster à la vue" onClick={() => setZoom(1)}>
              <Maximize2 className="size-4" aria-hidden="true" />
            </Button>
            <Button size="sm" variant="outline" aria-label="Zoomer" onClick={() => setZoom((z) => borne(z * PAS_ZOOM))}>
              <Plus className="size-4" aria-hidden="true" />
            </Button>
            <Button size="sm" variant="outline" aria-label="Recalculer" disabled={enVol} onClick={recalculer}>
              <RefreshCw className={cn('size-4', enVol && 'animate-spin')} aria-hidden="true" />
            </Button>
          </div>
        </div>
      </div>

      <VerdictBar
        resultat={resultat}
        perime={perime}
        onEnregistrerVariante={impose.actif ? enregistrerCommeVariante : undefined}
        enregistrementEnCours={enregistrementEnCours}
      />

      {erreur && (
        <p className="text-sm text-destructive" role="alert">{erreur}</p>
      )}

      {progression && (
        <p className="text-sm text-muted-foreground" role="status" data-progression={progression.statut}>
          Calcul en tâche de fond — {progression.pct} %
        </p>
      )}

      {/* PV31 — brouillon de rangées imposées : n'apparaît qu'APRÈS le premier
          geste (glisser une bande / cliquer le fond pour en ajouter une) ;
          avant cela, les bandes restent des poignées silencieuses. */}
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-dashed border-border bg-muted/40 p-2 text-xs" data-ao-impose={impose.actif ? 'actif' : undefined}>
        <p className="text-muted-foreground">
          Glissez une rangée pour la déplacer, cliquez le plan pour en ajouter une — le
          serveur recalcule et prouve l’écart à l’optimum.
        </p>
        {impose.actif && (
          <div className="ml-auto flex flex-wrap items-center gap-1.5">
            <Button size="sm" variant="outline" disabled={!impose.peutAnnuler} onClick={impose.annuler}>
              Annuler
            </Button>
            <Button size="sm" variant="outline" disabled={!impose.peutRefaire} onClick={impose.refaire}>
              Rétablir
            </Button>
            <Button size="sm" variant="outline" disabled={impose.selection === null} onClick={impose.supprimerSelection}>
              Supprimer la rangée sélectionnée
            </Button>
            <Button size="sm" variant="ghost" onClick={quitterModeImpose}>
              Revenir au calcul optimal
            </Button>
          </div>
        )}
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
        <div className="relative flex min-h-0 flex-1 flex-col" onWheel={onWheel}>
          <div className={cn('flex min-h-0 flex-1 flex-col', perime && 'opacity-40')}>
            <PlanLayer
              plan={plan}
              zoom={zoom}
              rangeesImposees={impose.lignesAffichees}
              rangeeSelectionnee={impose.selection}
              yPropose={impose.yPropose}
              onRangeePointerDown={impose.commencerGlisser}
              // PlanLayer relaie `(y, event)` — le 2ᵉ paramètre d'`ajouterRangee`
              // est `kitCode` : sans ce filtre, l'ÉVÉNEMENT pointeur serait pris
              // pour un code de kit (aucun kit n'y correspondrait jamais).
              onFondPointerDown={(y) => impose.ajouterRangee(y)}
              onPointerMoveSvg={impose.deplacerVers}
              onPointerUpSvg={impose.validerGlisser}
            />
          </div>
          {perime && (
            <Badge tone="neutral" className="absolute right-2 top-2">recalcul…</Badge>
          )}
        </div>

        {/* Inspecteur : tiroirs de paramètres. Chaque tiroir remonte un patch
            de paramètres ; le calcul appartient au serveur (AOF94). PV51 —
            `resultat.tiroirs` est publié par `/ao/calepinage/calculer|…/` : un
            tiroir sans `donnees` (toiture multi-surfaces, hors budget) rend
            simplement `null` — jamais un bandeau qui prétendrait qu'aucune
            route ne les sert. */}
        <aside className="flex w-full flex-col gap-1 overflow-y-auto lg:w-96" aria-label="Tiroirs de paramètres">
          <TiroirKits
            donnees={resultat?.tiroirs?.kits}
            valeurs={parametres || {}}
            onChange={majParametres}
            perime={perime}
          />
          <TiroirAllees
            donnees={resultat?.tiroirs?.allees}
            valeurs={parametres || {}}
            onChange={majParametres}
            perime={perime}
          />
          <TiroirRives
            donnees={resultat?.tiroirs?.rives}
            valeurs={parametres || {}}
            onChange={majParametres}
          />
          <TiroirOrientation
            donnees={resultat?.tiroirs?.orientation}
            valeurs={parametres || {}}
            onChange={majParametres}
          />
          <TiroirElectrique
            donnees={resultat?.tiroirs?.electrique}
            valeurs={parametres || {}}
            onChange={majParametres}
            onConformite={onConformite}
          />

          {/* PACT168 — l'expert a tout : réglages fins + marges de robustesse
              (affichées seulement si le moteur en publie). */}
          <ModeExpert
            valeurs={parametres || {}}
            onChange={majParametres}
            marges={resultat?.marges}
            seuils={seuilsRobustesse}
          />

          {/* PACT168/PV51 — suggestions RÉELLES du moteur (`resultat.suggestions`).
              Vide si le moteur n'en a trouvé aucune pour l'entrée courante — le
              panneau le DIT (`SuggestionsPanel`), jamais une colonne muette. */}
          <SuggestionsPanel
            suggestions={resultat?.suggestions ?? []}
            historique={historiqueSuggestions}
            enCours={enVol ? codeApplique : null}
            onAppliquer={appliquerSuggestion}
            onPoserQuestion={(s) => setQuestionSuggeree(s.question_a_poser ?? null)}
          />

          {questionSuggeree && (
            <div
              className="rounded-md border border-border bg-muted p-3 text-xs text-muted-foreground"
              data-suggestion-question=""
            >
              <p className="whitespace-pre-line">{questionSuggeree}</p>
              <p className="mt-1">
                Question PRÉ-REMPLIE, pas encore envoyée : elle se crée dans la série
                Q/R de l’affaire (onglet « Questions terrain »).
              </p>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
