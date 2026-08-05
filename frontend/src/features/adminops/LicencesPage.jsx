import { useEffect, useState } from 'react'
import adminopsApi from './adminopsApi'
import PageHeader from '../../components/layout/PageHeader'
import { Badge, Card, EmptyState, Spinner, StatusPill } from '../../ui'
import { formatDate } from '../../lib/format'
import { toastError } from '../../lib/toast'

/* ============================================================================
   NTADM9 — Écran admin « Licences & sièges » : palier de licence, modules
   inclus, sièges utilisés/max, historique des changements de plan. Lecture
   seule — un changement de plan reste une action manuelle du founder.
   ========================================================================== */

export default function LicencesPage() {
  const [statut, setStatut] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminopsApi
      .licenceStatut()
      .then((res) => setStatut(res.data))
      .catch(() => toastError('Impossible de charger le statut de licence.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />
  if (!statut) {
    return (
      <EmptyState
        title="Statut de licence indisponible"
        description="Réessayez dans un instant."
      />
    )
  }

  const { plan, sieges_utilises: siegesUtilises, sieges_max: siegesMax,
    quota_atteint: quotaAtteint, historique_plan: historique } = statut

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Licences & sièges"
        subtitle="Palier de licence, modules inclus et utilisation des sièges"
      />

      <Card className="p-6">
        <h3 className="text-sm font-semibold text-foreground">Palier de licence</h3>
        {plan ? (
          <div className="mt-3 flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <StatusPill label={plan.nom} tone="primary" />
              <span className="text-xs text-muted-foreground">{plan.code}</span>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground">Modules inclus</p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {plan.modules_inclus.length === 0 ? (
                  <span className="text-sm text-muted-foreground">Aucun module listé.</span>
                ) : (
                  plan.modules_inclus.map((m) => <Badge key={m}>{m}</Badge>)
                )}
              </div>
            </div>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">
            Aucun plan assigné — accès complet à tous les modules installés
            (comportement par défaut).
          </p>
        )}
      </Card>

      <Card className="p-6">
        <h3 className="text-sm font-semibold text-foreground">Sièges</h3>
        <div className="mt-3 flex items-center gap-3">
          <span className="font-display text-2xl font-semibold text-foreground">
            {siegesUtilises}
          </span>
          <span className="text-sm text-muted-foreground">
            / {siegesMax != null ? siegesMax : 'illimité'} sièges utilisés
          </span>
          {quotaAtteint && <StatusPill label="Quota atteint" tone="warning" />}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Le dépassement du quota alerte les administrateurs mais n&apos;empêche
          jamais la création d&apos;un compte.
        </p>
      </Card>

      <Card className="p-6">
        <h3 className="text-sm font-semibold text-foreground">Historique des changements de plan</h3>
        {!historique || historique.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            Aucun changement de plan enregistré.
          </p>
        ) : (
          <div className="mt-3 flex flex-col gap-2">
            {historique.map((ligne, idx) => (
              <div key={idx} className="flex items-center justify-between border-b py-2 text-sm">
                <span>
                  {ligne.ancien_plan || '—'} → {ligne.nouveau_plan || '—'}
                </span>
                <span className="text-xs text-muted-foreground">
                  {ligne.par || 'système'} · {formatDate(ligne.le)}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
