// LB11 — Prédicats PURS du drag-to-pan sur l'espace vide du board (Trello —
// docs/design/leads-board-blueprint.md D2, exactement la plainte fondatrice
// « quand je veux scroller à droite je dois défiler tout en bas »). Aucun
// import : zéro React/DOM réel requis, testable `node --test`. Le hook
// `usePanScroll.js` (React) importe ces fonctions — jamais de logique
// dupliquée entre le hook et ses tests.

// Cibles qui ne doivent JAMAIS armer un pan : le PointerSensor de dnd-kit gère
// déjà le drag de carte via ses propres listeners posés sur `.kb-card`/
// `.kb-drag-wrap` (KanbanView.jsx, DraggableCard) — les ignorer ici élimine
// tout conflit par construction, sans avoir besoin de `stopPropagation`
// nulle part. Les contrôles interactifs de la colonne (chevron de repli LB10,
// sélecteur d'étape StageMover, cases à cocher…) sont ignorés de la même
// façon.
export const PAN_IGNORE_SELECTOR =
  '.kb-card, .kb-drag-wrap, .kb-col-body, button, a, select, input, [role="button"]'

// Distance (px) avant d'armer réellement le pan — un simple clic (ouverture
// de fiche, clic dans le vide pour désélectionner) ne doit jamais déclencher
// un pan fantôme ni empêcher le clic d'aboutir.
export const PAN_ACTIVATION_DISTANCE_PX = 4

// `target` = l'élément DOM du pointerdown (ou tout objet exposant `.closest`,
// pour rester testable sans DOM réel).
export function shouldIgnorePanStart(target) {
  return Boolean(
    target
    && typeof target.closest === 'function'
    && target.closest(PAN_IGNORE_SELECTOR),
  )
}

// Le tactile/stylet scrolle déjà nativement sur `.kb-board` (`overflow-x:
// auto` posé par LB2) et le TouchSensor dnd-kit gère son propre drag de
// carte à l'appui long — le pan à la souris ne doit s'armer QUE pour
// pointerType === 'mouse' (blueprint : « désactivé sur pointer coarse »).
export function isPannablePointerType(pointerType) {
  return pointerType === 'mouse'
}

export function exceedsPanThreshold(dx, dy, threshold = PAN_ACTIVATION_DISTANCE_PX) {
  return Math.hypot(dx, dy) >= threshold
}
