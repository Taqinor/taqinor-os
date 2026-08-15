// NTMOB19 — logique PURE (aucun React) du widget « À faire aujourd'hui ».
// Agrège en UNE liste triée par urgence ce que quatre sources EXISTANTES
// exposent déjà, sans aucun nouveau modèle ni endpoint :
//   • relances CRM dues        → `crm/leads/relances/?scope=today`
//   • approbations en attente  → `reporting/approbations-en-attente/`
//   • interventions du jour    → `installations/ma-tournee/`
//   • factures échues          → `reporting/notifications/` (bloc `factures`)
// Extrait ici pour être testable sans DOM ; le composant se contente de rendre.

export const MAX_ITEMS = 10

// Rang d'urgence quand deux items n'ont pas de date comparable : ce qui bloque
// quelqu'un d'autre (approbation) puis ce qui est daté du jour (intervention,
// relance) puis l'argent en retard.
const KIND_RANK = {
  approbation: 0,
  intervention: 1,
  relance: 2,
  facture: 3,
}

/**
 * Trie par urgence : d'abord ce qui est EN RETARD (date passée), du plus
 * ancien au plus récent ; ensuite le reste par rang de nature puis par date.
 */
export function trierParUrgence(items, today = new Date().toISOString().slice(0, 10)) {
  const score = (it) => {
    const enRetard = !!it.date && it.date < today
    return [enRetard ? 0 : 1, enRetard ? it.date : (KIND_RANK[it.kind] ?? 9), it.date || '9999-12-31']
  }
  return [...items].sort((a, b) => {
    const sa = score(a)
    const sb = score(b)
    for (let i = 0; i < sa.length; i += 1) {
      if (sa[i] < sb[i]) return -1
      if (sa[i] > sb[i]) return 1
    }
    return 0
  })
}

/** Normalise les quatre réponses brutes en items {id,kind,label,sublabel,date,to}. */
export function construireItems({
  relances = [], approbations = [], interventions = [], factures = [],
} = {}) {
  const items = []
  for (const lead of relances) {
    items.push({
      id: `relance-${lead.id}`,
      kind: 'relance',
      label: [lead.prenom, lead.nom].filter(Boolean).join(' ') || `Lead #${lead.id}`,
      sublabel: 'Relance due',
      date: lead.date_relance || null,
      to: `/crm/leads/${lead.id}`,
    })
  }
  for (const ap of approbations) {
    items.push({
      id: `approbation-${ap.source}-${ap.id}`,
      kind: 'approbation',
      label: ap.libelle || 'Demande à approuver',
      sublabel: 'Approbation en attente',
      date: ap.date || null,
      to: '/approbations',
    })
  }
  for (const iv of interventions) {
    items.push({
      id: `intervention-${iv.id}`,
      kind: 'intervention',
      label: iv.titre || iv.reference || `Intervention #${iv.id}`,
      sublabel: 'Intervention du jour',
      date: iv.date_prevue || null,
      to: '/ma-journee',
    })
  }
  for (const f of factures) {
    // Seules les factures ÉCHUES sont « à relancer » — une facture émise dont
    // l'échéance est à venir n'est pas une tâche du jour.
    if (!f.overdue) continue
    items.push({
      id: `facture-${f.id}`,
      kind: 'facture',
      label: f.label || `Facture #${f.id}`,
      sublabel: `Facture échue${f.sublabel ? ` — ${f.sublabel}` : ''}`,
      date: f.date || null,
      to: `/ventes/factures/${f.id}`,
    })
  }
  return items
}

/** Items prêts à l'affichage : normalisés, triés, bornés à MAX_ITEMS. */
export function aFaireAujourdhui(sources, today) {
  return trierParUrgence(construireItems(sources), today).slice(0, MAX_ITEMS)
}
