// ACAL576 — reflet du sélecteur « Priorité de pose » (CAL83), sorti à l'identique de
// `roof-tool-pro11.ts::syncPrioriteRemplissage` (un fichier de 2 000 lignes ou plus ne grossit pas).

/** Reflète l'état du sélecteur : choix courant, et « ensoleillement » grisé + motivé. */
export function refleterPrioriteRemplissage(select: HTMLSelectElement | null, valeur: string, motif: string | null): void {
  if (!select) return;
  select.value = valeur;
  for (const option of Array.from(select.options)) {
    if (option.value !== 'ensoleillement') continue;
    option.disabled = Boolean(motif);
    option.title = motif ?? '';
  }
}
