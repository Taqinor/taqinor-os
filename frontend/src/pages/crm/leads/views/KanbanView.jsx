// Vue kanban des leads CRM, façon Odoo : 6 colonnes canoniques (stages.js,
// miroir de STAGES.py — jamais de liste d'étapes en dur ici), glisser-déposer
// via @dnd-kit/core. Le parent gère l'optimistic update : on ne mute rien.
import { memo, useCallback, useEffect, useMemo, useState } from 'react'
// VX45 — icônes lucide (rendu stable multi-OS, contrairement à un emoji brut).
import { ChevronDown, LayoutGrid, X } from 'lucide-react'
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  formatMAD, groupLeadsByStage, isStageMoveAllowed, isStageMoveBackward,
  PIPELINE_STAGES, STAGE_LABELS,
} from '../../../../features/crm/stages'
import {
  buildKanbanAnnouncements,
  kanbanScreenReaderInstructions,
} from '../../../../features/kanban/kanbanA11y'
import { readCollapsedStages, writeCollapsedStages } from '../../../../features/kanban/collapsedColumns'
import { usePanScroll } from '../../../../features/kanban/usePanScroll'
import { usePrefersReducedMotion } from '../../../../hooks/usePrefersReducedMotion'
// ORDRE FONDATEUR 2026-08-01 — un recul d'étape se DEMANDE. La formulation
// (elle nomme le lead et les deux étapes) est mutualisée avec la fenêtre lead :
// une seule phrase pour tous les gestes qui font reculer un lead.
import { useConfirmerRecul } from '../../../../features/crm/confirmRecul'
// EZ14 — undo universel : appliquer tout de suite, inverser à l'annulation.
// Un board se démonte au moindre changement de vue : aucun commit différé ici.
import { mutateWithUndo } from '../../../../lib/mutateWithUndo'
import { EmptyState, Button } from '../../../../ui'
// Hook média CANONIQUE (le même que LeadsPage) : ici interrogé sur
// `(pointer: coarse)` — c'est le POINTEUR qui décide, jamais une largeur.
import { useIsMobile } from '../../../../ui/ResponsiveDialog'
import LeadCard from './LeadCard'

// VX135 — dropAnimation dnd-kit par défaut désalignée des tokens de
// mouvement de l'app ; alignée --motion-*/--ease-out (tokens.css). Sous
// reduced-motion, quasi instantanée (dnd-kit exige une durée > 0).
const DROP_ANIMATION = { duration: 180, easing: 'cubic-bezier(0.23, 1, 0.32, 1)' }
const DROP_ANIMATION_REDUCED = { duration: 1, easing: 'linear' }

/* ORDRE FONDATEUR 2026-08-02 — le sélecteur d'étape par carte (StageMover,
   J140/L151/LB3/LB4) est SUPPRIMÉ, pas caché : « ne la cache pas, supprime-la
   complètement ». Les deux chemins restants pour changer d'étape : le
   glisser-déposer (souris/clavier via KeyboardSensor, garde LB4 + recul
   confirmé round 4) et la pilule d'étape de la fenêtre du lead. Le contrat
   d'absence vit dans KanbanView.test.jsx. */

// Probabilité de conversion par étape (entonnoir) — UI seulement, sert au
// prévisionnel pondéré (proba × total devis). Les leads perdus comptent 0.
// XSAL15 — exportée pour être réutilisée telle quelle par la vue « Prévision »
// (regroupement par mois plutôt que par étape, MÊME calcul de pondération —
// jamais une seconde table de probabilités déclarée ailleurs).
// eslint-disable-next-line react-refresh/only-export-components -- STAGE_PROBABILITY co-localisé
export const STAGE_PROBABILITY = {
  NEW: 0.1,
  CONTACTED: 0.25,
  QUOTE_SENT: 0.5,
  FOLLOW_UP: 0.7,
  SIGNED: 1,
  COLD: 0.05,
}

// Enveloppe draggable d'une carte ; l'original reste en place (style fantôme)
// pendant que le DragOverlay suit le pointeur.
// LB6 — memo() (blueprint I4, bug #4) : sans lui, KanbanView re-rendait
// TOUTES les instances de DraggableCard (donc ré-exécutait useDraggable +
// recréait la sous-arborescence) à chaque rendu du parent, même quand seule
// UNE carte avait réellement changé — LeadCard(memo) protège son PROPRE
// re-rendu mais pas le travail de DraggableCard lui-même en amont.
const DraggableCard = memo(function DraggableCard({
  lead, busy, onOpen, onAutoQuote, users, onReassign,
  selected, onToggleSelect, onPlanifierRelance, onMarkPerdu,
  // LB38 — booléen « une sélection est en cours quelque part sur le board »
  // (jamais le `Set` entier) : révèle la case de TOUTES les cartes pendant
  // qu'on constitue une sélection (blueprint D3). Primitive → memo intact.
  selectionActive,
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: lead.id,
    data: { lead },
    disabled: busy,
  })
  return (
    <div
      ref={setNodeRef}
      className={isDragging ? 'kb-drag-wrap kb-drag-source' : 'kb-drag-wrap'}
    >
      {/* LB12 — `data-lead-id` sur ce MÊME nœud (celui qui porte réellement
          `tabIndex`/`role` via `attributes` dnd-kit) : c'est lui que
          `handleDragEnd` refocalise après un déplacement réussi. */}
      <div data-lead-id={lead.id} {...listeners} {...attributes}>
        <LeadCard lead={lead} busy={busy} onOpen={onOpen} onAutoQuote={onAutoQuote}
                  users={users} onReassign={onReassign}
                  selected={selected} onToggleSelect={onToggleSelect}
                  selectionActive={selectionActive}
                  onPlanifierRelance={onPlanifierRelance} onMarkPerdu={onMarkPerdu} />
      </div>
    </div>
  )
})

/* APX6 — RETIRÉ sur ordre fondateur (2026-08-01, « enlève ça ») : la barre
   segmentée d'activité des en-têtes de colonne (la « case grise, parfois
   grise/rouge ») encombrait chaque étape sur téléphone. La somme `.num` de
   l'en-tête (LB9) reste ; le contrat d'absence vit dans
   KanbanActivityBar.apx6.test.mjs. */

/* APX9 — PLAFOND DE RENDU PAR COLONNE.
   ---------------------------------------------------------------------------
   `fetchLeads` charge TOUTES les pages en mémoire (`fetchAllPages`) et cette
   vue montait ensuite CHAQUE carte (`col.leads.map`, aucun découpage). Sur
   500+ leads cela fait des milliers de nœuds DOM ; densifier les cartes (APX2)
   ne fait qu'atteindre ce mur plus tôt, puisqu'il en tient davantage à l'écran.

   Le plafond ne touche QUE le RENDU : les données sont déjà là, « Charger
   plus » ne fait que découper plus loin dans le tableau en mémoire — ZÉRO
   appel réseau, ZÉRO dépendance (la virtualisation react-window reste
   refusée : c'est une dépendance). Les compteurs et sommes d'en-tête restent
   les totaux RÉELS de l'étape : on ne cache pas des leads, on en diffère
   l'affichage. */
export const RENDER_CAP = 40
/* ORDRE FONDATEUR 2026-08-01 : « pourquoi Charger plus ? mets-les TOUS —
   l'utilisateur balaie vers le bas de toute façon ».
   ---------------------------------------------------------------------------
   Le plafond tactile de 10 cartes par étape est RETIRÉ — constante ET bouton.
   Il avait été posé pour alléger le geste, mais il payait le mauvais prix : au
   téléphone la colonne est un rouleau qu'on parcourt AU POUCE — un bouton qui coupe ce
   rouleau tous les 10 leads est exactement l'interruption qu'on cherche à
   supprimer, et il rendait le pipeline illisible (on ne voit plus la fin de
   son étape). Le vrai poids du balayage était ailleurs et il est corrigé
   (round 4 : la colonne ne vole plus le geste ; round 3 : StageMover non
   monté au doigt). AU POINTEUR GROSSIER ON MONTE DONC TOUT, sans plafond ni
   bouton. Le desktop garde APX9 intact (RENDER_CAP = 40 + « Charger plus »),
   parce que là 6 colonnes sont visibles EN MÊME TEMPS — le mur de nœuds y est
   réel, alors que le pager mobile n'en montre qu'une. */

// Colonne d'étape : zone droppable, accent couleur, compteur, total devis.
// LB9 — région nommée (axe/lecteur d'écran atteignent chaque colonne par son
// libellé + compteur) ; en-têtes déjà épinglés hors du corps scrollant depuis
// LB2 (P0 fondateur), aucune retouche nécessaire pour ça ici.
// LB10 — `collapsed`/`onToggleCollapse` (état + persistance possédés par
// KanbanView, `features/kanban/collapsedColumns.js`) : une colonne repliée
// REND SEULEMENT le rail 44px (chevron + compteur + libellé pivoté), les
// cartes (`children`) ne sont même pas montées — mais le `<section>` garde
// EXACTEMENT le même `ref={setNodeRef}`/`id: col.key` qu'en dépliée : elle
// reste une zone droppable à part entière (surbrillance `kb-over` incluse).
function StageColumn({ col, collapsed, onToggleCollapse, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key })
  // Prévisionnel pondéré : total devis × probabilité de l'étape.
  const forecast = col.totalDevis * (STAGE_PROBABILITY[col.key] ?? 0)
  const chevronLabel = collapsed
    ? `Déplier la colonne ${col.label}`
    : `Replier la colonne ${col.label}`
  const sectionClassName = [
    'kb-col',
    isOver && 'kb-over',
    collapsed && 'kb-col-collapsed',
  ].filter(Boolean).join(' ')
  return (
    <section
      ref={setNodeRef}
      aria-label={`Étape ${col.label} — ${col.count} lead${col.count === 1 ? '' : 's'}`}
      className={sectionClassName}
      style={{ '--kb-accent': col.color }}
    >
      <header className="kb-col-header">
        <div className="kb-col-title-row">
          <button
            type="button"
            className="kb-col-collapse-btn"
            aria-expanded={!collapsed}
            aria-label={chevronLabel}
            title={chevronLabel}
            onClick={onToggleCollapse}
          >
            <ChevronDown
              className={collapsed ? 'kb-col-chevron kb-col-chevron-collapsed' : 'kb-col-chevron'}
              aria-hidden="true"
            />
          </button>
          {!collapsed && <span className="kb-col-title">{col.label}</span>}
          <span className="kb-col-count">{col.count}</span>
        </div>
        {/* LB9 — une SEULE rangée « total MAD · Prév. pondéré » (au lieu de
            deux lignes empilées) ; le tooltip explique la pondération
            STAGE_PROBABILITY importée de plus haut (jamais une seconde table).
            APX6 — la somme porte explicitement `.num` (typographie de données)
            et s'aligne à DROITE de l'en-tête. */}
        {!collapsed && col.totalDevis > 0 && (
          <span
            className="kb-col-money num"
            title={`Prévisionnel pondéré à ${Math.round((STAGE_PROBABILITY[col.key] ?? 0) * 100)} % (probabilité de conversion à cette étape)`}
          >
            {formatMAD(col.totalDevis)} · Prév. {formatMAD(forecast)}
          </span>
        )}
      </header>
      {collapsed ? (
        <div className="kb-col-rail-label">{col.label}</div>
      ) : (
        /* LB41 — le corps ne scrolle plus au desktop (board = scrolleur
           unique) : le tabindex clavier a déménagé sur .kb-board. */
        <div className="kb-col-body">
          {col.count === 0 ? (
            <div className="kb-col-empty">Déposer un lead ici</div>
          ) : (
            children
          )}
        </div>
      )}
    </section>
  )
}

export default function KanbanView({
  leads,
  onOpenLead,
  onChangeStage,
  onAutoQuote,
  busyLeadId,
  users,
  onReassign,
  selected = new Set(),
  onToggleSelect,
  onPlanifierRelance,
  onMarkPerdu,
  // LB9 — coach d'état vide à DEUX paliers, même idiome que ChartsView
  // (totalLeads/onClearFilters déjà câblés là-bas sur `leads.length`/
  // `setFilters(EMPTY_FILTERS)`) : `totalLeads` (non filtré) distingue
  // « aucun lead du tout » de « aucun résultat pour CES filtres ». Tous
  // optionnels — tant que `<KanbanView {...viewProps} />` (LeadsPage.jsx) ne
  // les câble pas encore, on dégrade proprement sur le message filtré
  // générique, jamais un crash ni un CTA mort.
  totalLeads = null,
  onClearFilters,
  onNewLead,
  onImportLeads,
  // (B1) — « mode déplacement » possédé par LeadsPage (entrée du menu ⋯
  // mobile). NON persisté : il retombe OFF à la navigation. Absent = OFF,
  // donc un consommateur qui ne le câble pas garde exactement l'ancien
  // comportement au desktop et perd seulement le drag tactile.
  dragMode = false,
  onExitDragMode,
}) {
  // VX135 — préférence reduced-motion lue en JS : le tilt (transform statique
  // posé par dnd-kit/CSS) et le dropAnimation (JS pur) échappent tous deux au
  // garde global CSS.
  const prefersReducedMotion = usePrefersReducedMotion()
  // LB11 — drag-to-pan sur l'espace vide du board (features/kanban/
  // usePanScroll.js) : ref à poser sur `.kb-board`, aucun autre câblage —
  // le hook attache lui-même ses écouteurs natifs pointerdown/move/up/cancel.
  const boardRef = usePanScroll()
  // ORDRE FONDATEUR 2026-08-01 — le bandeau éphémère « On ne recule pas une
  // étape » DISPARAÎT : il annonçait un refus qui n'existe plus. Un recul se
  // demande maintenant (useConfirmerRecul), il ne se signale plus après coup.
  const confirmerRecul = useConfirmerRecul()
  /* PHYSIQUE TACTILE (B1/B2) — deux défauts du TouchSensor, corrigés ensemble.
     B2 : `{ delay: 150, tolerance: 8 }` armait un drag pendant un scroll LENT
     (150 ms de contact, 8 px de tolérance : un pouce qui démarre doucement
     reste dedans). → `{ delay: 300, tolerance: 5 }`, l'appui long devient une
     intention, plus un accident.
     B1 : `TouchSensor.setup()` (dnd-kit) installe un `touchmove` NON PASSIF
     permanent sur `window` dès que le sensor est MONTÉ — donc même sans le
     moindre drag, tout le scroll au doigt de la page passe par un écouteur
     qui peut appeler preventDefault, et le navigateur perd son scroll natif.
     Sur pointeur GROSSIER on ne monte donc le sensor QUE si le « mode
     déplacement » est actif (entrée « Réorganiser par glisser » du menu ⋯
     mobile, LeadsPage). Le desktop (souris, MouseSensor) est STRICTEMENT
     inchangé, et le StageMover sous chaque carte reste le chemin sans-drag —
     réordonner reste possible au doigt sans jamais activer le mode. */
  const pointerCoarse = useIsMobile('(pointer: coarse)')
  const touchDragMonte = !pointerCoarse || dragMode
  /* GESTES PURS — MouseSensor, PAS PointerSensor : les pointer events unifient
     souris ET doigt, donc PointerSensor (distance 6px) saisissait la carte au
     tout début d'un balayage tactile — la carte se soulevait une frame puis
     retombait au pointercancel : le « leads collants » résiduel du retour
     fondateur. MouseSensor n'écoute que la souris ; au doigt, seul le
     TouchSensor (monté uniquement en mode déplacement) peut saisir. */
  const pointerSensor = useSensor(MouseSensor, { activationConstraint: { distance: 6 } })
  const touchSensor = useSensor(TouchSensor, {
    activationConstraint: { delay: 300, tolerance: 5 },
  })
  // VX192 — sensor clavier natif (@dnd-kit/core), 0 dépendance.
  const keyboardSensor = useSensor(KeyboardSensor)
  // `useSensors` filtre les entrées nulles : l'arité de l'appel (donc ses
  // dépendances) reste constante, seul le tableau produit rétrécit.
  const sensors = useSensors(
    pointerSensor,
    touchDragMonte ? touchSensor : null,
    keyboardSensor,
  )
  /* Le NOMBRE de sensors change quand le mode bascule ; dnd-kit dérive de ce
     tableau les dépendances de `useSensorSetup`, qui doivent rester de taille
     constante. On remonte donc proprement le contexte — ce qui garantit aussi
     le teardown de l'écouteur non passif. La clé est CONSTANTE au desktop :
     jamais de remontage là où rien ne change. */
  const dndKey = touchDragMonte ? 'dnd-tactile' : 'dnd-sans-tactile'
  /* Le plaisir du balayage (VX42 haptique) : un souffle de 5 ms quand le pager
     se POSE sur une colonne — le « clic » physique des pagers natifs. Écouteur
     passif, au doigt seulement ; `scrollend` absent (vieux iOS) = silence
     propre, `vibrate` absent (iOS) = no-op défensif, jamais une erreur. */
  useEffect(() => {
    // `boardRef` est la FONCTION callback-ref d'usePanScroll — le nœud vit
    // sur `boardRef.node` (lire `.current` sur la fonction = undefined muet :
    // le haptique était mort-né au round 2, attrapé par l'audit).
    const el = boardRef.node?.current
    if (!el || !pointerCoarse || !('onscrollend' in el)) return undefined
    const onSettle = () => navigator.vibrate?.(5)
    el.addEventListener('scrollend', onSettle, { passive: true })
    return () => el.removeEventListener('scrollend', onSettle)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- boardRef est un ref stable
  }, [pointerCoarse])
  const columns = useMemo(() => groupLeadsByStage(leads), [leads])
  const [activeLead, setActiveLead] = useState(null)

  // LB10 — repli de colonne PERSISTÉ (localStorage, features/kanban/
  // collapsedColumns.js) : lu UNE FOIS au montage (lazy useState — jamais de
  // repli par défaut, `readCollapsedStages()` renvoie `[]` tant que
  // l'utilisatrice n'a jamais replié une colonne), écrit à chaque bascule.
  // APX9 — combien de cartes sont MONTÉES par étape (jamais combien sont
  // chargées : tout est déjà en mémoire). Défaut RENDER_CAP.
  // Cet état ne sert QU'AU DESKTOP : au doigt on monte tout (ordre fondateur
  // 2026-08-01), il n'y a donc ni plafond à repousser ni bouton pour le faire.
  const [limiteParEtape, setLimiteParEtape] = useState({})
  const chargerPlus = useCallback((stageKey) => {
    setLimiteParEtape((prev) => ({
      ...prev,
      [stageKey]: (prev[stageKey] ?? RENDER_CAP) + RENDER_CAP,
    }))
  }, [])

  /* EZ14 — adoption n°7 : sur le board, la RÉASSIGNATION gagne l'undo.
     (L'adoption n°8 — l'étape au clavier via StageMover — est morte avec le
     StageMover, ordre fondateur 2026-08-02 ; l'étape se change par drag ou
     dans la fenêtre du lead.) Un board se démonte au moindre changement de
     vue : `mutateWithUndo` applique tout de suite, jamais rien en attente. */
  const reassignAvecUndo = useCallback(async (lead, nouvelId) => {
    if (!onReassign) return
    const precedent = lead?.owner ?? ''
    if (String(precedent) === String(nouvelId)) return
    await mutateWithUndo({
      kind: 'lead_owner',
      message: 'Responsable modifié.',
      apply: () => onReassign(lead, nouvelId),
      revert: () => onReassign(lead, precedent),
    })
  }, [onReassign])


  const [collapsedStages, setCollapsedStages] = useState(() => new Set(readCollapsedStages()))
  const toggleCollapsed = useCallback((stageKey) => {
    setCollapsedStages((prev) => {
      const next = new Set(prev)
      if (next.has(stageKey)) next.delete(stageKey)
      else next.add(stageKey)
      writeCollapsedStages([...next])
      return next
    })
  }, [])

  // VX192 — annonces FR : id de lead → nom, id de colonne → libellé d'étape.
  const announcements = useMemo(() => {
    const byId = new Map((leads ?? []).map((l) => [l.id, l]))
    const labelFor = (id) => {
      if (STAGE_LABELS[id]) return STAGE_LABELS[id]
      const l = byId.get(id)
      return l?.nom || `#${id}`
    }
    return buildKanbanAnnouncements(labelFor)
  }, [leads])

  const handleDragStart = ({ active }) => {
    setActiveLead(active.data.current?.lead ?? null)
  }

  const handleDragEnd = async ({ active, over }) => {
    setActiveLead(null)
    const lead = active.data.current?.lead
    if (!lead || !over || over.id === lead.stage) return
    // LB4 — garde-fou UI : MÊME règle que le serveur (isStageMoveAllowed,
    // miroir _bulk_stage_allowed, stages.js). Bug #7 (recon2-03) : l'ancien
    // `stageRank` local classait COLD au rang le plus HAUT → tout drag
    // COLD→actif était refusé comme un recul, alors que le serveur autorise
    // DÉJÀ cette réactivation (COLD est un parking, pas un rang avancé).
    // ORDRE FONDATEUR 2026-08-01 — un drop EN ARRIÈRE n'est plus refusé : il
    // pose une question. Confirmée, elle emprunte le MÊME chemin
    // d'enregistrement avec le marqueur `confirmeRecul` (que LeadsPage traduit
    // en `confirme_recul` dans le PATCH) ; annulée, on ne touche à rien — la
    // carte n'a jamais quitté sa colonne (aucun optimiste n'a été dispatché).
    // Les deux prédicats sont exclusifs et couvrent tout couple distinct : ce
    // `return` défensif ne se déclenche donc jamais en pratique.
    const enAvant = isStageMoveAllowed(lead.stage, over.id)
    const enArriere = isStageMoveBackward(lead.stage, over.id)
    if (!enAvant && !enArriere) return
    if (enArriere && !(await confirmerRecul(lead, over.id))) return
    onChangeStage(lead, over.id, { confirmeRecul: enArriere })
    // LB12 — la carte déposée se RE-PARENTE dans sa nouvelle colonne (React
    // démonte/remonte l'instance — un `key={lead.id}` qui change de tableau
    // parent n'est jamais un simple déplacement DOM) : sans ça, le focus
    // retombe sur `<body>` (recon-05 a11y #4). `requestAnimationFrame`
    // laisse le re-rendu déclenché par `onChangeStage` (dispatch Redux
    // optimiste) se poser avant de chercher le nœud dans sa NOUVELLE colonne
    // — même chemin, souris OU clavier (KeyboardSensor passe par ce même
    // `handleDragEnd`). Un drop refusé/annulé/sur-place ne re-parente rien :
    // le focus reste naturellement sur la carte d'origine, aucun code requis.
    requestAnimationFrame(() => {
      document.querySelector(`[data-lead-id="${lead.id}"]`)?.focus()
    })
  }

  const handleDragCancel = () => setActiveLead(null)

  // VX147 — « 0 lead » unifié sur `EmptyState` (calqué sur ChartsView, la
  // seule vue déjà correcte) au lieu de 6 colonnes vides en texte brut.
  // LB9 — désormais à DEUX paliers : `totalLeads === 0` (vraiment aucun lead)
  // reçoit le coach illustré (VX40 — leads est un des 4-5 écrans les plus vus)
  // + CTA création/import ; « filtré à 0 » garde le message générique + un
  // CTA « Effacer les filtres » réel quand le parent le fournit.
  if (!leads || leads.length === 0) {
    const aucunDuTout = totalLeads != null && totalLeads === 0
    if (aucunDuTout) {
      return (
        <EmptyState
          illustrated
          title="Aucun lead"
          description="Créez votre premier lead ou importez votre liste pour démarrer le pipeline."
          action={(onNewLead || onImportLeads) ? (
            <div className="flex flex-wrap items-center justify-center gap-2">
              {onNewLead && (
                <Button type="button" size="sm" onClick={onNewLead}>+ Nouveau lead</Button>
              )}
              {onImportLeads && (
                <Button type="button" variant="outline" size="sm" onClick={onImportLeads}>
                  Importer
                </Button>
              )}
            </div>
          ) : null}
        />
      )
    }
    return (
      <EmptyState
        icon={LayoutGrid}
        title="Aucun lead"
        description="Aucun lead ne correspond à ces filtres."
        action={onClearFilters ? (
          <Button type="button" variant="outline" size="sm" onClick={onClearFilters}>
            Effacer les filtres
          </Button>
        ) : null}
      />
    )
  }

  return (
    <DndContext
      key={dndKey} // (B1) — remontage propre quand le jeu de sensors change
      sensors={sensors}
      accessibility={{
        announcements,
        screenReaderInstructions: kanbanScreenReaderInstructions,
      }}
      // LB11 — autoScroll intégré à DndContext (blueprint D2) : était inerte
      // tant qu'aucun conteneur ne scrollait réellement (LB2 l'a réveillé).
      // Seuils réglés sur les deux axes imbriqués (board horizontal, colonne
      // verticale) — config, jamais de scroll maison pendant un drag.
      autoScroll={{ thresholds: { x: 0.18, y: 0.22 } }}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      {/* (B1) — sortie du mode déplacement, à portée de pouce. Rendue
          UNIQUEMENT en pointeur grossier : au desktop le drag souris n'a
          jamais été conditionné, il n'y a donc rien à désactiver. */}
      {pointerCoarse && dragMode && (
        <div
          className="kb-dragmode-chip mb-2 flex w-fit items-center gap-1 rounded-lg border border-border bg-muted pl-3 text-[13px] font-semibold"
          role="status"
        >
          <span>Déplacement activé</span>
          <button
            type="button"
            className="kb-dragmode-exit inline-flex min-h-[44px] min-w-[44px] items-center justify-center"
            aria-label="Désactiver le mode déplacement"
            title="Désactiver le mode déplacement"
            onClick={onExitDragMode}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>
      )}
      {/* LB41 — le board est LE scrolleur (2 axes) : focalisable pour le
          défilement clavier (l'ancien tabindex des corps de colonne l'a
          rejoint — ils ne scrollent plus). */}
      <div className="kb-board" ref={boardRef} tabIndex={0} aria-label="Board du pipeline">
        {columns.map((col) => (
          <StageColumn
            key={col.key}
            col={col}
            collapsed={collapsedStages.has(col.key)}
            onToggleCollapse={() => toggleCollapsed(col.key)}
          >
            {/* APX9 — plafond de RENDU au DESKTOP : on ne monte que les N
                premières cartes, le reste attend « Charger plus ». Les données
                sont déjà en mémoire — aucun appel réseau ici.
                AU DOIGT : aucun plafond (ordre fondateur 2026-08-01) — la
                colonne est un rouleau qu'on parcourt au pouce, `restants`
                vaut donc 0 et le bouton n'est jamais rendu. */}
            {(() => {
              const visibles = col.leads
              const limite = pointerCoarse ? visibles.length : (limiteParEtape[col.key] ?? RENDER_CAP)
              const restants = Math.max(0, visibles.length - limite)
              return (
                <>
                  {visibles.slice(0, limite).map((lead) => (
                    <DraggableCard
                      key={lead.id}
                      lead={lead}
                      busy={lead.id === busyLeadId}
                      onOpen={onOpenLead}
                      onAutoQuote={onAutoQuote}
                      users={users}
                      // EZ14 — réassignation et étape passent par l'undo.
                      onReassign={reassignAvecUndo}
                      selected={selected.has(lead.id)}
                      selectionActive={selected.size > 0}
                      onToggleSelect={onToggleSelect}
                      onPlanifierRelance={onPlanifierRelance}
                      onMarkPerdu={onMarkPerdu}
                    />
                  ))}
                  {restants > 0 && (
                    <button
                      type="button"
                      className="kb-charger-plus"
                      onClick={() => chargerPlus(col.key)}
                    >
                      Charger plus ({restants} restant{restants > 1 ? 's' : ''})
                    </button>
                  )}
                </>
              )
            })()}
          </StageColumn>
        ))}
      </div>
      {/* LB40 — `zIndex` explicite : dnd-kit pose 999 par défaut sur son
          calque de glisser, DESSOUS la barre bulk flottante (`--z-sticky`,
          1100) — la carte glissée passait sous la barre pendant une
          sélection. Prop native dnd-kit (jamais un z-index en dur sur notre
          `.kb-drag-overlay` : le calque parent est celui qui empile). */}
      <DragOverlay
        zIndex={1200}
        dropAnimation={prefersReducedMotion ? DROP_ANIMATION_REDUCED : DROP_ANIMATION}
      >
        {activeLead ? (
          <div className={prefersReducedMotion ? 'kb-drag-overlay kb-drag-overlay--flat' : 'kb-drag-overlay'}>
            <LeadCard lead={activeLead} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
