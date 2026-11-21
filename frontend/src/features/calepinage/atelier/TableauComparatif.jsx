// ACAL546 — « Comparer les poses » (toit plat) : le tableau que `roofPro11/matrix.ts` peint dans
// `#rp9-compare`, monté ici avec les mêmes ids que l'aperçu public. SANS colonne en MAD :
// `data-sans-montant` dit au script de ne pas écrire la sixième cellule (l'argent vit dans `ventes`).
export default function TableauComparatif() {
  return (
    <details className="mt-6 rounded-xl border border-border bg-card" data-sans-montant-bloc="1">
      <summary className="min-h-11 cursor-pointer px-5 py-3 text-sm font-semibold text-primary-text">Comparer les poses</summary>
      <div id="rp9-compare-wrap" data-sans-montant="1" hidden className="p-0">
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-2">
          <p className="text-xs text-muted-foreground">Chaque ligne est une pose possible sur ce toit ; cliquez-en une pour la voir.</p>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Filtrer
            <select id="rp9-matrix-filter" className="h-11 border border-border bg-background px-2 text-xs text-foreground">
              <option value="all">Toutes les orientations</option>
            </select>
          </label>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm text-foreground">
            <thead className="text-muted-foreground">
              <tr className="border-b border-border">
                <th className="px-5 py-3 font-semibold">Configuration</th>
                <th className="px-5 py-3 text-right font-semibold" aria-sort="none">
                  <button type="button" data-rp9-sort="placedCount" className="rp9-sort min-h-11">Panneaux<span className="rp9-sort-arrow"></span></button>
                </th>
                <th className="px-5 py-3 text-right font-semibold">kWc</th>
                <th className="px-5 py-3 text-right font-semibold" aria-sort="descending">
                  <button type="button" data-rp9-sort="annualKwh" className="rp9-sort min-h-11">kWh/an<span className="rp9-sort-arrow"></span></button>
                </th>
                <th className="px-5 py-3 text-right font-semibold" aria-sort="none">
                  <button type="button" data-rp9-sort="pctOfTarget" className="rp9-sort min-h-11">% du besoin<span className="rp9-sort-arrow"></span></button>
                </th>
              </tr>
            </thead>
            <tbody id="rp9-compare"></tbody>
          </table>
        </div>
      </div>
    </details>
  )
}
