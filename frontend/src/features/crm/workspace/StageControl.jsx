import { useMemo } from 'react'
import {
  StatusPill,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../../ui'
import { PIPELINE_STAGES, STAGE_LABELS, CONVERSION_STAGE } from '../stages'
import {
  LEAD_STAGE_SHORTCUTS, useFocusedRecordShortcuts,
} from '../../../providers/focusedRecordShortcuts'
import { rottingLevel, thresholdsForIndex } from './rotting.js'

// LW16 — StageControl : l'étape du lead en StatusPill (jamais un <select>),
// l'ancienneté d'étape teintée par la rampe « rotting », et SIGNED toujours
// gardé par le dialogue de signature.
//
// LWC1 (compactage) — la rangée des 6 pastilles occupait 90-120 px du haut du
// rail pour afficher 5 étapes qu'on ne regarde pas. Elle devient UNE pilule
// (l'étape COURANTE) + « depuis X j » inline + un chevron ▾ qui ouvre le menu
// des AUTRES étapes : ≤44 px, un seul geste, zéro information perdue. Le
// contrat (onChangeStage/onSigne), les clés stages.js et les raccourcis 1-4
// sont INCHANGÉS — seule la forme du contrôle change.
//
// Contrat de props (lane 1) : { state, onChangeStage(key), onSigne() }. Rendu
// dans IdentityRail avec onChangeStage={(k)=>onAction('change-stage',k)} et
// onSigne={()=>onAction('signe')}. Le PATCH d'étape (flush-puis-PATCH, garde de
// recul 400→toast) vit dans le moteur (hook) via `change-stage` — ce contrôle
// ne fait que DÉCLENCHER, jamais patcher directement (couches funnel/document
// séparées, règles #2/#4).
//
// Clés/labels d'étape : features/crm/stages.js UNIQUEMENT (miroir STAGES.py,
// règle #2) — aucun littéral de clé ici.
export default function StageControl({ state, onChangeStage, onSigne }) {
  const server = state.server || {}
  const currentStage = server.stage
  const sinceDays = server.stage_since_days
  const isEdit = state.mode === 'edit'

  // Raccourcis 1-4 (LEAD_STAGE_SHORTCUTS = 4 premières étapes ; la signature et
  // l'abandon sont exclus par conception) → changement d'étape. Handlers
  // mémorisés (dep scalaire stable).
  const shortcutHandlers = useMemo(
    () => Object.fromEntries(
      LEAD_STAGE_SHORTCUTS.map((s) => [s.key, () => onChangeStage(s.stage)]),
    ),
    [onChangeStage],
  )
  useFocusedRecordShortcuts('leadForm', shortcutHandlers, isEdit)

  const currentIndex = PIPELINE_STAGES.indexOf(currentStage)
  const level = rottingLevel(sinceDays, thresholdsForIndex(currentIndex))

  const activate = (key) => {
    // SIGNED n'est JAMAIS un PATCH direct : l'acceptation devis+option avance
    // l'étape côté serveur → on ouvre la signature (SigneDialog via le shell).
    if (key === CONVERSION_STAGE) onSigne()
    else onChangeStage(key)
  }

  // Les AUTRES étapes (l'étape courante n'est jamais une cible : le moteur
  // refuse le no-op, et la proposer n'apporte rien).
  const autres = PIPELINE_STAGES.filter((key) => key !== currentStage)

  return (
    <div className="lw-stage" role="group" aria-label="Étape du lead">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          {/* Toute la pilule est la cible (≥44 px de haut) : pilule + ancienneté
              + chevron. Le nom accessible vient du CONTENU (« Contacté depuis
              8 j »), donc l'ancienneté reste annoncée aux lecteurs d'écran. */}
          <button
            type="button"
            className="lw-stagepill"
            title="Changer l'étape du lead"
          >
            <StatusPill status={currentStage} label={STAGE_LABELS[currentStage] ?? currentStage} />
            {currentStage && sinceDays != null && (
              <span
                className={`lw-stage-since lw-stage-since--${level}`}
                data-rotting={level}
              >
                depuis <span className="num">{sinceDays}</span> j
              </span>
            )}
            <span className="lw-stagepill-chev" aria-hidden="true">▾</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="lw-stage-menu">
          {autres.map((key) => {
            const label = STAGE_LABELS[key]
            const toSigne = key === CONVERSION_STAGE
            return (
              <DropdownMenuItem
                key={key}
                onSelect={() => activate(key)}
                title={toSigne
                  ? 'Marquer comme signé (ouvre la signature du devis)'
                  : `Passer à « ${label} »`}
              >
                <StatusPill status={key} label={label} />
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
