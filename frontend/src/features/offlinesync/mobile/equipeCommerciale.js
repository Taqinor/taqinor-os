// NTMOB26 — logique PURE (aucun React) de l'onglet « Équipe » de l'accueil
// mobile Commercial responsable. Aucun calcul métier nouveau : un simple
// regroupement d'affichage des relances EN RETARD déjà renvoyées par
// `crm/leads/relances/?scope=overdue` (le sélecteur applique déjà la portée de
// visibilité du responsable — on ne réagrège rien côté client).

/** Regroupe les relances en retard par commercial, du plus chargé au moins. */
export function classementParCommercial(leads = []) {
  const par = new Map()
  for (const lead of leads) {
    const cle = lead.owner ?? 'sans'
    const entree = par.get(cle) || {
      id: cle, nom: lead.owner_nom || 'Non attribué', leads: [],
    }
    entree.leads.push(lead)
    par.set(cle, entree)
  }
  return [...par.values()].sort((a, b) => b.leads.length - a.leads.length)
}
