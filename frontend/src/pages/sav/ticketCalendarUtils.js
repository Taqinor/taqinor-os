// ZMFG3 — Vue calendrier des tickets SAV. Un ticket n'apparaît que s'il porte
// une `date_tournee` (préventif généré planifié, ou correctif planifié via
// FG88/le glisser-déposer dans TicketsPage) ; un ticket SANS date n'y figure
// JAMAIS (fonction pure, testée indépendamment du rendu).
//
// Extrait de TicketsPage.jsx (react-refresh/only-export-components exige
// qu'un fichier de composants n'exporte que des composants).
export function groupTicketsByDate(tickets) {
  const map = {}
  for (const t of tickets ?? []) {
    if (!t?.date_tournee) continue
    const key = t.date_tournee
    ;(map[key] = map[key] || []).push(t)
  }
  return map
}
