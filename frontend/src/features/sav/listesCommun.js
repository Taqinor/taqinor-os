// ENF28 (ENF19) — briques PURES partagées des listes SAV (tickets,
// équipements) : tri générique et lecture de la configuration des statuts
// (N58). Elles existaient en copies littérales ; une seule ici. Sans import :
// importable tel quel par `node --test`.

/** Copie triée de `items` ; `valeur(item)` rend la clé comparée (< / >). */
export function trierPar(items, dir, valeur) {
  const sign = dir === 'asc' ? 1 : -1
  return [...(items ?? [])].sort((a, b) => {
    const va = valeur(a)
    const vb = valeur(b)
    if (va < vb) return -1 * sign
    if (va > vb) return 1 * sign
    return 0
  })
}

/** Liste effective de statuts (API N58) -> `[libellés|null, ordres|null]`,
 *  restreinte aux clés canoniques `clesValides`. `null`/`[]` = réinitialise. */
export function lireConfigStatuts(rows, clesValides) {
  if (!rows || !rows.length) return [null, null]
  const libelles = {}
  const ordres = {}
  for (const r of rows) {
    if (!r || !clesValides.includes(r.cle)) continue
    if (r.libelle) libelles[r.cle] = r.libelle
    if (typeof r.ordre === 'number') ordres[r.cle] = r.ordre
  }
  return [
    Object.keys(libelles).length ? libelles : null,
    Object.keys(ordres).length ? ordres : null,
  ]
}
