/* ============================================================================
   UX29–UX33 — Pastilles de statut QHSE (JSX) construites via `statusPill(map)`.
   Chaque Pill expose aussi `.options` / `.labelOf` / `.toneOf` pour les colonnes
   de tableau et les filtres. Cartes de statuts : `qhseStatus.js` (pur).
   ========================================================================== */
import { statusPill } from '../../ui/module'
import {
  NCR_STATUTS, CAPA_STATUTS, AUDIT_STATUTS, PLAN_CHANTIER_STATUTS,
  PROCEDURE_STATUTS, INSPECTION_STATUTS, EVAL_RISQUE_STATUTS, PERMIS_STATUTS,
  LOTO_STATUTS, INCIDENT_STATUTS, INCIDENT_TYPES, GRAVITE, CNSS_STATUTS,
  BSD_STATUTS, RECYCLAGE_STATUTS, CONFORMITE_STATUTS, BILAN_STATUTS, ESG_PILIERS,
} from './qhseStatus'

export const NcrStatutPill = statusPill(NCR_STATUTS)
export const CapaStatutPill = statusPill(CAPA_STATUTS)
export const AuditStatutPill = statusPill(AUDIT_STATUTS)
export const PlanChantierStatutPill = statusPill(PLAN_CHANTIER_STATUTS)
export const ProcedureStatutPill = statusPill(PROCEDURE_STATUTS)
export const InspectionStatutPill = statusPill(INSPECTION_STATUTS)
export const EvalRisqueStatutPill = statusPill(EVAL_RISQUE_STATUTS)
export const PermisStatutPill = statusPill(PERMIS_STATUTS)
export const LotoStatutPill = statusPill(LOTO_STATUTS)
export const IncidentStatutPill = statusPill(INCIDENT_STATUTS)
export const IncidentTypePill = statusPill(INCIDENT_TYPES)
export const GravitePill = statusPill(GRAVITE)
export const CnssStatutPill = statusPill(CNSS_STATUTS)
export const BsdStatutPill = statusPill(BSD_STATUTS)
export const RecyclageStatutPill = statusPill(RECYCLAGE_STATUTS)
export const ConformiteStatutPill = statusPill(CONFORMITE_STATUTS)
export const BilanStatutPill = statusPill(BILAN_STATUTS)
export const EsgPilierPill = statusPill(ESG_PILIERS)
