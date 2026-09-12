import { useEffect, useState } from 'react'
import { DatabaseBackup, ShieldCheck } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import { Badge, Card, CardContent, Spinner } from '../../ui'

/* ============================================================================
   NTOBS5 — Paramètres → Fiabilité → Sauvegardes. Écran self-service LECTURE
   SEULE : consomme `core.backup.resume_sauvegardes` (GET /core/mes-sauvegardes/),
   qui lit les `BackupRun` déjà produits par le moteur interne (YOPSB1/2) —
   aucun nouveau moteur, aucun bouton « déclencher une sauvegarde » ici.
   ========================================================================== */

const DRILL_STALE_DAYS = 30

function joursDepuis(iso) {
  if (!iso) return null
  const ms = Date.now() - new Date(iso).getTime()
  return Math.floor(ms / (1000 * 60 * 60 * 24))
}

function formatDate(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function StatutBadge({ statut }) {
  const tones = {
    termine: 'success',
    en_cours: 'info',
    en_attente: 'neutral',
    echec: 'danger',
    non_configure: 'warning',
  }
  return <Badge tone={tones[statut] || 'neutral'}>{statut}</Badge>
}

export default function SauvegardesPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    let active = true
    parametresApi.getMesSauvegardes()
      .then((r) => { if (active) setData(r.data ?? {}) })
      .catch(() => { if (active) setErreur('Impossible de charger le statut des sauvegardes.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spinner />
      </div>
    )
  }

  if (erreur) {
    return <div className="p-6 text-sm text-destructive">{erreur}</div>
  }

  const derniere = data?.derniere_sauvegarde
  const drill = data?.dernier_drill
  const joursDrill = joursDepuis(drill?.date)
  const drillPerime = joursDrill === null || joursDrill > DRILL_STALE_DAYS

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <h1 className="text-xl font-semibold">Sauvegardes</h1>

      <Card>
        <CardContent className="flex items-start gap-3 p-4">
          <DatabaseBackup className="mt-0.5 h-5 w-5 text-muted-foreground" aria-hidden="true" />
          <div className="flex-1">
            <p className="text-sm font-medium">Dernière sauvegarde</p>
            {derniere ? (
              <p className="mt-1 text-sm text-muted-foreground">
                Réussie le {formatDate(derniere.date)} <StatutBadge statut={derniere.statut} />
              </p>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">Aucune sauvegarde réussie pour le moment.</p>
            )}
            {data?.rpo_planifie && (
              <p className="mt-1 text-xs text-muted-foreground">
                Fréquence planifiée (RPO) : {data.rpo_planifie}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex items-start gap-3 p-4">
          <ShieldCheck className="mt-0.5 h-5 w-5 text-muted-foreground" aria-hidden="true" />
          <div className="flex-1">
            <p className="text-sm font-medium">Dernier test de restauration</p>
            {drill ? (
              <p className="mt-1 text-sm text-muted-foreground">
                {drill.statut === 'termine' ? 'Réussi' : 'Statut'} le {formatDate(drill.date)}{' '}
                <StatutBadge statut={drill.statut} />
              </p>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">Aucun test de restauration enregistré.</p>
            )}
            {drillPerime && (
              <Badge tone="danger" className="mt-2">
                {drill ? `Périmé — ${joursDrill} jours sans drill réussi` : 'Aucun drill réussi'}
              </Badge>
            )}
            {data?.rto_annonce_heures != null && (
              <p className="mt-1 text-xs text-muted-foreground">
                RTO annoncé : {data.rto_annonce_heures} h (informatif)
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
