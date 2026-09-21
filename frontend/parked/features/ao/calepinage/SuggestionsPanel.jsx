import { CheckCircle2, MessageCircleQuestion, Sparkles } from 'lucide-react'
import { Badge, Button, Card, EmptyState } from '../../../ui'

/* ============================================================================
   AOF100 — Panneau « Suggestions du moteur » ACTIONNABLES.
   ----------------------------------------------------------------------------
   La boucle 512 → 618 (constat mesuré du relevé FRDISI, `SerieQuestions`
   d'AOF25) rendue MÉCANIQUE : une recommandation applicable en un clic, ou une
   question au client pré-remplie de son impact — jamais un conseil qu'il
   faudrait relire, chiffrer et retaper à la main.

   **Rien n'est écrit en dur ici.** Chaque carte vient d'un `Recommandation`
   SERVEUR (`core/calepinage/recommandations.py:proposer`, AOF54) — titre, gain
   RECALCULÉ (jamais estimé), coût qualitatif/condition, niveau de confiance,
   `patch_entree` et `question_a_poser`. Ce composant ne fait qu'AFFICHER et
   RELAYER deux actions :
     · « Appliquer »                → `onAppliquer(suggestion)` — le
       propriétaire de l'atelier rejoue `useCalepinage.appliquer(patch_entree)`
       (AOF94), donc le gain affiché est RE-VÉRIFIÉ par le moteur, jamais cru
       sur parole ;
     · « Poser la question au client » → `onPoserQuestion(suggestion)` — crée
       une question dans la série Q/R (AOF25/AOF106/AOF107) avec
       `question_a_poser` et le gain PRÉVISIONNEL déjà pré-remplis.

   **Historique.** `historique` porte les suggestions DÉJÀ appliquées (photo
   au moment de l'application — code, titre, gain) : elles quittent la liste
   actionnable et se retrouvent, marquées, dans une section distincte. Une
   suggestion dont le `code` réapparaît dans `suggestions` ET `historique` (le
   moteur peut la reproposer après un recalcul) reste rangée côté historique —
   on n'actionne jamais deux fois « la même » carte.

   ── Contrat de charge utile ───────────────────────────────────────────────
   suggestions = [{ code, titre, gain_modules, gain_kwc?, cout_qualitatif?,
                    confiance, patch_entree, question_a_poser? }]
   historique  = [{ code, titre, gain_modules, gain_kwc? }]
   ========================================================================== */

const CONFIANCE_TONE = { HAUTE: 'success', MOYENNE: 'warning', BASSE: 'neutral' }
const CONFIANCE_LABEL = { HAUTE: 'Confiance haute', MOYENNE: 'Confiance moyenne', BASSE: 'Confiance basse' }

function signeModules(v) {
  if (!Number.isFinite(v)) return null
  return v > 0 ? `+${v}` : String(v)
}

function ImpactChiffre({ gainModules, gainKwc }) {
  const modules = signeModules(gainModules)
  if (modules == null) return null
  return (
    <p className="text-sm font-medium tabular-nums" data-ao-compte={gainModules}>
      {`${modules} module${Math.abs(gainModules) > 1 ? 's' : ''}`}
      {Number.isFinite(gainKwc) && gainKwc !== 0 && (
        <span className="ml-1 font-normal text-muted-foreground">
          {`(soit ${gainKwc > 0 ? '+' : ''}${gainKwc.toFixed(2)} kWc)`}
        </span>
      )}
    </p>
  )
}

function CarteSuggestion({
  suggestion, appliquee, enCours, onAppliquer, onPoserQuestion,
}) {
  const tonConfiance = CONFIANCE_TONE[suggestion.confiance] ?? 'neutral'
  const libelleConfiance = CONFIANCE_LABEL[suggestion.confiance] ?? suggestion.confiance
  return (
    <Card
      className="flex flex-col gap-2 p-3"
      data-suggestion={suggestion.code}
      data-suggestion-appliquee={appliquee ? 'true' : undefined}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-medium text-foreground">{suggestion.titre}</p>
        {appliquee ? (
          <Badge tone="success">
            <CheckCircle2 className="size-3.5" aria-hidden="true" />
            Appliquée
          </Badge>
        ) : (
          suggestion.confiance && <Badge tone={tonConfiance}>{libelleConfiance}</Badge>
        )}
      </div>

      <ImpactChiffre gainModules={suggestion.gain_modules} gainKwc={suggestion.gain_kwc} />

      {suggestion.cout_qualitatif && (
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Condition&nbsp;: </span>
          {suggestion.cout_qualitatif}
        </p>
      )}

      {!appliquee && (
        <div className="mt-1 flex flex-wrap gap-2">
          <Button
            size="sm"
            loading={enCours}
            disabled={enCours}
            onClick={() => onAppliquer?.(suggestion)}
          >
            Appliquer
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={enCours}
            onClick={() => onPoserQuestion?.(suggestion)}
          >
            <MessageCircleQuestion className="size-3.5" aria-hidden="true" />
            Poser la question au client
          </Button>
        </div>
      )}
    </Card>
  )
}

export function SuggestionsPanel({
  suggestions = [],
  historique = [],
  enCours = null,
  onAppliquer,
  onPoserQuestion,
}) {
  const codesAppliques = new Set(historique.map((h) => h.code))
  const enAttente = suggestions.filter((s) => !codesAppliques.has(s.code))

  return (
    <section className="flex flex-col gap-3" data-suggestions-panel={enAttente.length}>
      <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Suggestions du moteur
      </h4>

      {enAttente.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="Aucune suggestion en attente"
          description="Le moteur n’a pas identifié de gain applicable pour le calepinage courant."
        />
      ) : (
        <div className="flex flex-col gap-2">
          {enAttente.map((s) => (
            <CarteSuggestion
              key={s.code}
              suggestion={s}
              appliquee={false}
              enCours={enCours === s.code}
              onAppliquer={onAppliquer}
              onPoserQuestion={onPoserQuestion}
            />
          ))}
        </div>
      )}

      {historique.length > 0 && (
        <div className="flex flex-col gap-2">
          <h5 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Historique</h5>
          {historique.map((s) => (
            <CarteSuggestion key={s.code} suggestion={s} appliquee />
          ))}
        </div>
      )}
    </section>
  )
}

export default SuggestionsPanel
