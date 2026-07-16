/* ============================================================================
   UX1 — Kit « coquille de module ERP ».
   ----------------------------------------------------------------------------
   Composants partagés par tous les modules ERP (contrats, SAV, flotte, QHSE,
   GED, RH, paie…) : tableau de bord de KPI, coquilles de liste et de détail,
   centre d'échéances, fabrique de pastilles de statut, et logique d'urgence
   pure. Un seul point d'import : `import { ... } from '@/ui/module'`.
   ========================================================================== */
export * from './statusPill'
export * from './ModuleHero'
export * from './ModuleDashboard'
export * from './ListShell'
export * from './DetailShell'
export * from './RecordShell'
export * from './EcheanceCenter'
export * from './urgency'
