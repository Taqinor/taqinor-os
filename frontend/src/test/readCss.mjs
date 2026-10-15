// SPL280 — LE lecteur d'index.css des tests et de `check_hex` : `resolveCss`
// remplace chaque ligne `@import './styles/<sous-dossier>/<fichier>.css';`
// (sous-dossier OBLIGATOIRE) par le contenu VERBATIM de ce fichier, pour que le
// découpage d'index.css en @import (SPL282) ne change aucun octet lu par les
// gardes. `@import "tailwindcss"`, `./design/tokens.css` et `./styles/print.css`
// (sans sous-dossier) restent tels quels. Aucune normalisation de fin de ligne :
// la ligne d'@import garde sa fin (`\r` compris) et le fichier inliné perd UNE
// fin de ligne finale (celle que la ligne remplacée fournit déjà) — un bloc
// déplacé tel quel se relit donc à l'octet près.
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'

const IMPORT_STYLES = /^@import\s+(['"])\.\/styles\/([^/'"]+)\/([^/'"]+\.css)\1;[ \t]*(\r?)$/

const lireDisque = (chemin) => readFileSync(chemin, 'utf8')

/** Le texte d'une feuille avec ses `@import './styles/<dossier>/<f>.css'` inlinés.
 *  `lire(chemin)` (défaut : le disque) permet de résoudre un autre arbre — le
 *  golden relit ainsi l'index.css d'un ref git, découpé ou non. */
export function resolveCss(chemin, lire = lireDisque) {
  const base = dirname(chemin)
  return lire(chemin).split('\n').map((ligne) => {
    const m = ligne.match(IMPORT_STYLES)
    if (!m) return ligne
    const contenu = resolveCss(join(base, 'styles', m[2], m[3]), lire)
    return contenu.replace(/\r?\n$/, '') + m[4]
  }).join('\n')
}
