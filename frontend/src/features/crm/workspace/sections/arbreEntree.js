// ENF22 — rendu pur d'une entrée de l'arbre d'historique (table kind → icône/libellé +
// `entreeArbre`), séparé du composant ArbreHistorique.jsx (règle
// react-refresh/only-export-components). Déplacement pur.
import {
  Phone, Mail, MessageCircle, StickyNote, Sparkles, TrendingUp,
  Send, Eye, CheckCircle2, XCircle, Activity as ActivityIcon,
} from 'lucide-react'
import { OUTCOME_LABELS } from '../../../../components/ChatterTimeline'

// Icône + libellé + accent par type d'événement. Les kinds sont CEUX du
// serveur (crm.LeadActivity.Kind + les jalons devis virtuels de l'endpoint
// /historique/, QX32) — jamais un vocabulaire inventé ici.
const KIND_RENDER = {
  appel: { Icon: Phone, label: 'Appel' },
  whatsapp: { Icon: MessageCircle, label: 'WhatsApp' },
  email: { Icon: Mail, label: 'E-mail' },
  note: { Icon: StickyNote, label: 'Note' },
  creation: { Icon: Sparkles, label: 'Création' },
  stage: { Icon: TrendingUp, label: 'Étape', accent: 'jalon' },
  devis_sent: { Icon: Send, label: 'Devis envoyé', accent: 'jalon' },
  devis_opened: { Icon: Eye, label: 'Devis ouvert', accent: 'jalon' },
  devis_signed: { Icon: CheckCircle2, label: 'Devis signé', accent: 'gagne' },
  devis_refused: { Icon: XCircle, label: 'Devis refusé', accent: 'perdu' },
  devis_engagement: { Icon: ActivityIcon, label: 'Lecture détaillée', accent: 'jalon' },
}

// Un événement mérite-t-il l'arbre ? Les logs automatiques de champ sont du
// bruit — SAUF l'étape funnel (le seul champ qui raconte le parcours).
export function entreeArbre(a) {
  if (!a || !a.kind) return null
  if (a.kind === 'modification') {
    if (a.field !== 'stage') return null
    return {
      ...KIND_RENDER.stage,
      texte: `${a.old_value || '—'} → ${a.new_value || '—'}`,
    }
  }
  const rendu = KIND_RENDER[a.kind]
  if (!rendu) return null
  const badge = OUTCOME_LABELS[a.outcome] || null
  return { ...rendu, badge, texte: a.body || '' }
}
