import { useCallback, useMemo, useState } from 'react'
import { AlertTriangle, Minus, Maximize2, Plus, RefreshCw } from 'lucide-react'
import { Badge, Button, EmptyState, Skeleton } from '../../../ui'
import { cn } from '../../../lib/cn'
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

   ── L'INSPECTEUR EST VIDE, ET C'EST DIT À L'ÉCRAN ────────────────────────
   Les cinq tiroirs (AOF95-99) sont pilotés par des DESCRIPTEURS serveur
   (`donnees` : champs, bornes, presets, impacts, recommandations). Le résultat
   de `/ao/calepinage/calculer/` n'en publie AUCUN — aucune route ne le fait.
   Chaque tiroir rend donc `null`, et plutôt que de laisser une colonne
   mystérieusement vide (le symptôme exact d'un écran « livré » qui ne marche
   pas), l'atelier NOMME ce qui manque. Les tiroirs restent montés : le jour où
   une route publie ces descripteurs, ils s'allument sans modification.

   Les paramètres restent donc, aujourd'hui, ceux du preset de la toiture
   (`ToitureAO.parametres_calepinage`), appliqués côté SERVEUR quand le corps
   n'envoie pas de `params`.

   ── PACT168 — MODE EXPERT ET SUGGESTIONS, MONTÉS ─────────────────────────
   `ModeExpert` (AOF101, qui révèle `RobustesseBadges`) et `SuggestionsPanel`
   (AOF100) étaient livrés et importés par PERSONNE : l'inspecteur s'arrêtait
   aux 5 tiroirs débutant. Ils sont désormais montés À CÔTÉ d'eux, avec
   exactement le même principe que les tiroirs — montés, alimentés par ce que
   le moteur publie, et silencieux quand il ne publie rien :

     · `ModeExpert` pilote de VRAIS paramètres (pas de recherche, seuils,
       phase, mode de pose, forçage de rangée) : son `onChange` est le MÊME
       `majParametres` que les tiroirs, donc le serveur recalcule (AOF94). Son
       interrupteur est mémorisé côté navigateur (`safeStorage`) ;
     · `RobustesseBadges` n'affiche des marges que si le moteur en publie
       (`resultat.marges`, `Optional[Marges]` dans `core/calepinage/types.py`) ;
       les seuils sont la CONVERSION en centimètres des paramètres courants,
       jamais une valeur inventée ;
     · `SuggestionsPanel` reste vide tant qu'aucune route ne publie de
       recommandations (`aoApi.calepinages.suggestions` est `nonConstruit` :
       `core/calepinage/recommandations.py` existe, l'endpoint non). « Appliquer »
       rejoue le `patch_entree` par la voie normale des paramètres — le gain
       est donc RE-VÉRIFIÉ par le moteur, jamais cru sur parole.
   ========================================================================== */

const ZOOM_MIN = 0.25
const ZOOM_MAX = 12
const PAS_ZOOM = 1.25

const borne = (valeur) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, valeur))

/**
 * @param {number|string} toitureId  Toiture à calepiner (`ToitureAO.id`).
 * @param {Function} [onConformite]  Remontée de conformité du tiroir électrique.
 */
export default function CalepinageStudio({ toitureId, onConformite }) {
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
  // paramètres, et c'est le serveur qui recalcule (AOF94).
  const majParametres = useCallback((patch) => {
    setParametres((courants) => ({ ...(courants || {}), ...patch }))
  }, [])

  /* ── PACT168 — suggestions du moteur ──────────────────────────────────────
     `historique` est tenu ICI : une suggestion appliquée quitte la liste
     actionnable et se retrouve marquée dans l'historique, exactement comme le
     contrat d'AOF100 le décrit — sans quoi on pourrait « appliquer » deux fois
     le même patch et croire avoir gagné deux fois les mêmes modules. */
  const [historiqueSuggestions, setHistoriqueSuggestions] = useState([])
  const [codeApplique, setCodeApplique] = useState(null)
  const [questionSuggeree, setQuestionSuggeree] = useState(null)

  const appliquerSuggestion = useCallback((suggestion) => {
    setCodeApplique(suggestion.code)
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
    // La voie NORMALE des paramètres : c'est le moteur qui recalcule et qui
    // dira si le gain annoncé était réel (AOF94).
    majParametres(suggestion.patch_entree ?? {})
  }, [majParametres])

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

      <VerdictBar resultat={resultat} perime={perime} />

      {erreur && (
        <p className="text-sm text-destructive" role="alert">{erreur}</p>
      )}

      {progression && (
        <p className="text-sm text-muted-foreground" role="status" data-progression={progression.statut}>
          Calcul en tâche de fond — {progression.pct} %
        </p>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
        <div className="relative flex min-h-0 flex-1 flex-col" onWheel={onWheel}>
          <div className={cn('flex min-h-0 flex-1 flex-col', perime && 'opacity-40')}>
            <PlanLayer plan={plan} zoom={zoom} />
          </div>
          {perime && (
            <Badge tone="neutral" className="absolute right-2 top-2">recalcul…</Badge>
          )}
        </div>

        {/* Inspecteur : tiroirs de paramètres. Chaque tiroir remonte un patch
            de paramètres ; le calcul appartient au serveur (AOF94). Les
            descripteurs (`donnees`) ne sont publiés par AUCUNE route : les
            tiroirs restent donc masqués, et l'atelier le DIT. */}
        <aside className="flex w-full flex-col gap-1 overflow-y-auto lg:w-96" aria-label="Tiroirs de paramètres">
          <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground" data-tiroirs="absents">
            Les CINQ tiroirs débutant attendent un endpoint qui n’existe pas encore :
            aucune route ne publie leurs descripteurs (champs, bornes, presets, impacts).
            Le calcul utilise donc le preset enregistré sur la toiture. Le mode expert,
            plus bas, pilote lui directement les paramètres du moteur.
          </p>
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

          {/* PACT168 — suggestions du moteur. Vide tant qu'aucune route ne les
              publie : monté quand même, comme les tiroirs, pour s'allumer sans
              modification le jour où l'endpoint existe. */}
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
