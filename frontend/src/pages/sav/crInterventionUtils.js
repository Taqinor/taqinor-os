/* PACT142 — helpers du compte rendu d'intervention dicté (NTAI12).
   Extraits de `TicketsPage.jsx` : un fichier qui exporte des composants ne
   peut pas aussi exporter des constantes/fonctions (react-refresh), et le
   dépôt range déjà ce genre d'aide dans un module frère (cf.
   `ticketCalendarUtils.js`). */

/** Sections du CR, dans l'ORDRE du serveur (`services.CR_SECTIONS`). */
export const CR_SECTIONS_FR = [
  ['diagnostic', 'Diagnostic'],
  ['travaux', 'Travaux'],
  ['pieces', 'Pièces'],
  ['recommandations', 'Recommandations'],
]

/** Aplatit le CR structuré en un texte FR éditable (sections vides omises). */
export function crEnTexte(cr) {
  return CR_SECTIONS_FR
    .map(([cle, libelle]) => [libelle, String(cr?.[cle] ?? '').trim()])
    .filter(([, valeur]) => valeur !== '')
    .map(([libelle, valeur]) => `${libelle} : ${valeur}`)
    .join('\n')
}
