import { useMemo } from 'react'
import { StatusPill } from '../../../ui'
import { PIPELINE_STAGES, STAGE_LABELS, CONVERSION_STAGE } from '../stages'
import {
  LEAD_STAGE_SHORTCUTS, useFocusedRecordShortcuts,
} from '../../../providers/focusedRecordShortcuts'
import { rottingLevel, thresholdsForIndex } from './rotting.js'

// LW16 — StageControl : l'étape du lead en rangée de StatusPill (jamais un
// <select>), l'ancienneté d'étape teintée par la rampe « rotting », et SIGNED
// toujours gardé par le dialogue de signature.
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

  return (
    <div className="lw-stage" role="group" aria-label="Étape du lead">
      <div className="lw-stage-row">
        {PIPELINE_STAGES.map((key) => {
          const label = STAGE_LABELS[key]
          if (key === currentStage) {
            return (
              <span
                key={key}
                className="lw-stage-pill lw-stage-pill--current"
                aria-current="true"
              >
                <StatusPill status={key} label={label} />
              </span>
            )
          }
          const toSigne = key === CONVERSION_STAGE
          return (
            <button
              key={key}
              type="button"
              className="lw-stage-pill lw-stage-pill--ghost"
              onClick={() => activate(key)}
              title={toSigne
                ? 'Marquer comme signé (ouvre la signature du devis)'
                : `Passer à « ${label} »`}
            >
              <StatusPill status={key} label={label} tone="outline" dot={false} />
            </button>
          )
        })}
      </div>
      {currentStage && sinceDays != null && (
        <p className={`lw-stage-since lw-stage-since--${level}`} data-rotting={level}>
          depuis <span className="num">{sinceDays}</span> j
        </p>
      )}
    </div>
  )
}
