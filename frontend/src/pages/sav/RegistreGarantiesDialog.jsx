import { useEffect, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import savApi from '../../api/savApi'
import {
  Badge, Button, Spinner,
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '../../ui'

// WR11 / FG290 — registre des garanties matériel & échéancier PAR PARC.
// Lecture seule : parcs triés par échéance la plus proche, chaque unité avec
// ses dates de fin de garantie CALCULÉES et un statut d'alerte. Les données
// viennent de l'endpoint scopé société — aucun calcul local.

const STATUT_LABELS = {
  expiree: 'Expirée',
  expire_bientot: 'Expire bientôt',
  sous_garantie: 'Sous garantie',
  non_renseignee: 'Non renseignée',
}
const STATUT_TONES = {
  expiree: 'danger',
  expire_bientot: 'warning',
  sous_garantie: 'success',
  non_renseignee: 'neutral',
}

const fmtDate = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

export default function RegistreGarantiesDialog({ onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    savApi.getRegistreGaranties()
      .then((r) => { if (alive) setData(r.data) })
      .catch(() => { if (alive) setError(true) })
    return () => { alive = false }
  }, [])

  const totaux = data?.totaux

  return (
    <Sheet open onOpenChange={(o) => { if (!o) onClose() }}>
      <SheetContent side="right" className="w-[min(46rem,calc(100%-1.5rem))] sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-muted-foreground" aria-hidden="true" />
            Registre des garanties
          </SheetTitle>
          <SheetDescription>
            Échéancier des fins de garantie par parc — les parcs à échéance la
            plus proche apparaissent en premier.
          </SheetDescription>
        </SheetHeader>

        {error && (
          <p className="page-error">
            Registre indisponible — réessayez.
          </p>
        )}
        {!error && data == null && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="size-4" /> Chargement du registre…
          </p>
        )}

        {data && (
          <div className="flex flex-col gap-4" data-testid="registre-garanties">
            {totaux && (
              <div className="flex flex-wrap gap-2 text-xs">
                <Badge tone="neutral">{totaux.equipements} équipement(s)</Badge>
                <Badge tone="danger">{totaux.expirees} expirée(s)</Badge>
                <Badge tone="warning">
                  {totaux.expire_bientot} expire(nt) sous {data.expiring_soon_days} j
                </Badge>
                <Badge tone="success">{totaux.sous_garantie} sous garantie</Badge>
              </div>
            )}

            {(data.parcs ?? []).length === 0 && (
              <p className="text-sm text-muted-foreground">
                Aucun équipement dans le parc.
              </p>
            )}

            {(data.parcs ?? []).map((parc) => (
              <section key={parc.installation ?? 'sans-chantier'}
                       className="rounded-lg border border-border">
                <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/40 px-3 py-2">
                  <span className="text-sm font-medium">
                    {parc.installation_nom || 'Sans chantier'}
                    {parc.client_nom ? ` — ${parc.client_nom}` : ''}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Prochaine échéance : {fmtDate(parc.prochaine_echeance)}
                  </span>
                </header>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground">
                      <th className="px-3 py-1.5 font-medium">Produit</th>
                      <th className="px-3 py-1.5 font-medium">Série</th>
                      <th className="px-3 py-1.5 font-medium">Fin garantie</th>
                      <th className="px-3 py-1.5 font-medium">Statut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(parc.items ?? []).map((it) => (
                      <tr key={it.equipement} className="border-t border-border">
                        <td className="px-3 py-1.5">
                          {it.produit || '—'}
                          {it.marque ? (
                            <span className="text-xs text-muted-foreground"> · {it.marque}</span>
                          ) : null}
                        </td>
                        <td className="px-3 py-1.5">{it.numero_serie || '—'}</td>
                        <td className="px-3 py-1.5">{fmtDate(it.date_fin_garantie)}</td>
                        <td className="px-3 py-1.5">
                          <Badge tone={STATUT_TONES[it.statut_garantie] ?? 'neutral'}>
                            {STATUT_LABELS[it.statut_garantie] ?? it.statut_garantie}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            ))}
          </div>
        )}

        <div className="flex justify-end">
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
