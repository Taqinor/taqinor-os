import { useCallback, useEffect, useState } from 'react'
import { ShieldCheck, CalendarClock } from 'lucide-react'
import fiscalApi from '../../api/fiscalApi'
import {
  Card, CardHeader, CardTitle, CardContent, Badge, EmptyState, Skeleton,
} from '../../ui'
import { StateBlock } from '../../components/StateBlock'

/* ============================================================================
   WIR106 — Écran « Calendrier fiscal / Conformité » (NTMAR16).
   Feu tricolore par obligation (lecture seule) + échéances datées. NE DUPLIQUE
   PAS la gestion des obligations : celle-ci vit dans le module Comptabilité
   (XACC9, `comptaApi.obligationsFiscales`). Ici, uniquement la vue conformité.
   ========================================================================== */

// Feu tricolore : statut serveur → libellé + tonalité de badge.
const STATUT_META = {
  a_jour: { label: 'À jour', tone: 'success' },
  echeance_proche: { label: 'Échéance proche', tone: 'warning' },
  en_retard: { label: 'En retard', tone: 'destructive' },
  aucune_echeance: { label: 'Aucune échéance', tone: 'neutral' },
}

const ECHEANCE_STATUT = {
  a_preparer: { label: 'À préparer', tone: 'warning' },
  deposee: { label: 'Déposée', tone: 'info' },
  payee: { label: 'Payée', tone: 'success' },
}

export default function ConformiteFiscale() {
  const [conformite, setConformite] = useState([])
  const [echeances, setEcheances] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  const fetchAll = useCallback(() => Promise.allSettled([
    fiscalApi.tableauConformite(),
    fiscalApi.echeances(),
  ]).then(([confRes, echRes]) => {
    setConformite(confRes.status === 'fulfilled'
      ? (confRes.value.data ?? []) : [])
    setEcheances(echRes.status === 'fulfilled'
      ? (echRes.value.data?.results ?? echRes.value.data ?? []) : [])
    setLoadError(confRes.status === 'rejected' && echRes.status === 'rejected')
  }).finally(() => setLoading(false)), [])

  const load = useCallback(() => { setLoading(true); return fetchAll() }, [fetchAll])

  useEffect(() => { fetchAll() }, [fetchAll])

  if (loading) {
    return (
      <div className="ui-root page">
        <div className="page-header" style={{ marginBottom: '1.25rem' }}>
          <h2>Conformité fiscale</h2>
        </div>
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="ui-root page">
        <Card>
          <CardContent className="py-6">
            <StateBlock error="Le tableau de conformité n'a pas pu être chargé." onRetry={load} />
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>Calendrier fiscal / Conformité</h2>
        <p className="text-sm text-muted-foreground">
          Feu tricolore de conformité et échéances déclaratives (NTMAR). La
          gestion des obligations se fait dans le module Comptabilité.
        </p>
      </div>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck size={18} strokeWidth={1.75} aria-hidden="true" />
            Statut de conformité
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 sm:p-0">
          {conformite.length === 0 ? (
            <EmptyState
              icon={ShieldCheck}
              title="Aucune obligation active"
              description="Créez vos obligations fiscales depuis le module Comptabilité pour suivre leur conformité ici."
              className="border-0 py-6"
            />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-3 py-2">Obligation</th>
                  <th className="px-3 py-2">Statut</th>
                  <th className="px-3 py-2">Prochaine échéance</th>
                </tr>
              </thead>
              <tbody>
                {conformite.map((row) => {
                  const meta = STATUT_META[row.statut] ?? STATUT_META.aucune_echeance
                  return (
                    <tr key={row.obligation_id} className="border-b border-border/60">
                      <td className="px-3 py-2">{row.libelle}</td>
                      <td className="px-3 py-2">
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                      </td>
                      <td className="px-3 py-2">{row.prochaine_echeance || '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarClock size={18} strokeWidth={1.75} aria-hidden="true" />
            Échéances déclaratives
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 sm:p-0">
          {echeances.length === 0 ? (
            <EmptyState
              icon={CalendarClock}
              title="Aucune échéance"
              description="Générez le calendrier fiscal de l'année depuis le module Comptabilité."
              className="border-0 py-6"
            />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-3 py-2">Échéance</th>
                  <th className="px-3 py-2">Date limite</th>
                  <th className="px-3 py-2">Statut</th>
                </tr>
              </thead>
              <tbody>
                {echeances.map((e) => {
                  const meta = ECHEANCE_STATUT[e.statut] ?? { label: e.statut, tone: 'neutral' }
                  return (
                    <tr key={e.id} className="border-b border-border/60">
                      <td className="px-3 py-2">{e.libelle || e.obligation_libelle || `#${e.id}`}</td>
                      <td className="px-3 py-2">{e.date_limite || '—'}</td>
                      <td className="px-3 py-2">
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
