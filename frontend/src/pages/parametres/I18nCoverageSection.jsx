// NTI18N28 — onglet « Couverture i18n » de la page Paramètres.
//
// Écran LECTURE SEULE alimenté par le rapport JSON déjà produit par
// `scripts/extract_i18n_strings.py` (NTI18N1) — importé directement (Vite
// gère nativement l'import JSON), donc AUCUN nouvel endpoint backend, AUCUN
// nouveau moteur PDF (règle #4 : ce n'est jamais lié au PDF devis client).
// Le rapport reflète le dernier passage du script committé dans le repo ;
// NTI18N39 (hors périmètre de cette lane) planifiera son recalcul en tâche de
// fond — cet écran se contente d'AFFICHER ce qui existe déjà.
//
// Export CSV : réutilise le helper générique `utils/downloadBlob`
// (téléchargement de blob déjà utilisé par les autres exports tableur du
// repo) — pas de mécanisme d'export dédié inventé pour cet écran.
import { useMemo } from 'react'
import { Download } from 'lucide-react'
import coverageReport from '../../i18n/coverage-report.json'
import { Card, CardContent, Badge, Button } from '../../ui'
import { downloadBlob, stampedFilename } from '../../utils/downloadBlob'

export default function I18nCoverageSection() {
  const domains = useMemo(
    () => Object.entries(coverageReport.domains || {}).sort((a, b) => a[0].localeCompare(b[0])),
    [],
  )

  const exportCsv = () => {
    const header = 'domaine;composants_migres;composants_total;pourcentage;chaines_en_dur_restantes'
    const lines = domains.map(([key, d]) =>
      `${key};${d.migrated};${d.total};${d.pct};${d.hardcoded_strings}`)
    // BOM UTF-8 en tête : Excel (cible principale d'un export « relecture
    // métier ») affiche sinon les accents FR/AR mal décodés.
    const csv = ['﻿' + header, ...lines].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    downloadBlob(blob, stampedFilename('couverture-i18n', 'csv'))
  }

  return (
    <>
      <div className="rounded-xl border border-border bg-muted/30 px-4 py-3 text-[12.5px] leading-relaxed text-muted-foreground">
        Rapport de couverture i18n de l’UI (composants de page réels, verticaux
        parqués exclus : {(coverageReport.gated_modules_excluded || []).join(', ') || '—'}).
        Dernier calcul du script <code>scripts/extract_i18n_strings.py</code> :{' '}
        <strong>{coverageReport.generated_at || 'inconnu'}</strong>.
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-4 sm:pt-5">
          <div>
            <div className="text-2xl font-semibold text-foreground">
              {coverageReport.coverage_pct ?? 0}%
            </div>
            <div className="text-sm text-muted-foreground">
              {coverageReport.migrated_components ?? 0} / {coverageReport.total_components ?? 0}{' '}
              composants de page migrés vers le cadre i18n (useI18n/useT).
            </div>
          </div>
          <Button type="button" variant="outline" onClick={exportCsv}>
            <Download className="size-4" aria-hidden="true" /> Exporter en CSV
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="overflow-x-auto pt-4 sm:pt-5">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Domaine</th>
                <th className="py-2 pr-3 text-right font-medium">Migrés</th>
                <th className="py-2 pr-3 text-right font-medium">Total</th>
                <th className="py-2 pr-3 text-right font-medium">Couverture</th>
                <th className="py-2 text-right font-medium">Chaînes en dur restantes</th>
              </tr>
            </thead>
            <tbody>
              {domains.map(([key, d]) => (
                <tr key={key} className="border-b border-border/60 last:border-0">
                  <td className="py-2 pr-3 font-mono text-[12.5px]">{key}</td>
                  <td className="py-2 pr-3 text-right">{d.migrated}</td>
                  <td className="py-2 pr-3 text-right">{d.total}</td>
                  <td className="py-2 pr-3 text-right">
                    <Badge tone={d.pct >= 60 ? 'success' : d.pct > 0 ? 'info' : 'neutral'}>
                      {d.pct}%
                    </Badge>
                  </td>
                  <td className="py-2 text-right">{d.hardcoded_strings}</td>
                </tr>
              ))}
              {domains.length === 0 && (
                <tr><td colSpan={5} className="py-4 text-center text-muted-foreground">
                  Aucune donnée — régénérez le rapport (`python scripts/extract_i18n_strings.py --write`).
                </td></tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </>
  )
}
