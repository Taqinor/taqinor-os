/**
 * readingTime.ts — calcule le temps de lecture estimé à partir d'un texte brut.
 *
 * Cadence de référence : 200 mots/min (lecture en français, contenu technique).
 * Résultat arrondi à la minute supérieure, minimum 1 min.
 * Aucun package externe : regex simple sur les espaces.
 */

export function estimateReadingTime(text: string): number {
  const wordsPerMinute = 200;
  // Compte les séquences de caractères non-blancs (mots)
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.ceil(words / wordsPerMinute));
}

/** Extrait les titres h2/h3 d'un contenu HTML brut (SSR/source) pour la table des matières. */
export interface TocEntry {
  level: 2 | 3;
  id: string;
  text: string;
}

/**
 * Dérive la table des matières depuis du texte source Markdown (pas de DOM).
 * Reconnaît ## et ### en début de ligne.
 */
export function extractTocFromMarkdown(markdown: string): TocEntry[] {
  const lines = markdown.split(/\r?\n/);
  const entries: TocEntry[] = [];
  const seen = new Map<string, number>();

  for (const line of lines) {
    const m = line.match(/^(#{2,3})\s+(.+)$/);
    if (!m) continue;
    const level = m[1].length as 2 | 3;
    const text = m[2].trim();
    // Génère un id slug stable (même logique qu'Astro/remark)
    let id = text
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '') // supprime les diacritiques
      .replace(/[^\w\s-]/g, '')
      .trim()
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-');

    // Déduplication : suffixe numérique si id déjà utilisé
    const baseId = id;
    const count = seen.get(baseId) ?? 0;
    if (count > 0) id = `${baseId}-${count}`;
    seen.set(baseId, count + 1);

    entries.push({ level, id, text });
  }

  return entries;
}
