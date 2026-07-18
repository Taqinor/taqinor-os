import { useEffect, useState } from 'react'
import adminopsApi from './adminopsApi'
import PageHeader from '../../components/layout/PageHeader'
import { Button, Badge, Card, EmptyState, Spinner } from '../../ui'
import { formatDate } from '../../lib/format'
import { toastError, toastSuccess } from '../../lib/toast'

/* ============================================================================
   NTADM12 — Écran Sandbox : créer un environnement de test, statut + expiration
   + prolongation (+14j, max 2 fois).
   ========================================================================== */

const STATUT_LABEL = {
  en_creation: 'En création',
  pret: 'Prêt',
  expire: 'Expiré',
  echec: 'Échec',
}

export default function SandboxPage() {
  const [envs, setEnvs] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const load = () => {
    setLoading(true)
    adminopsApi
      .listSandbox()
      .then((res) => setEnvs(res.data?.results ?? res.data ?? []))
      .catch(() => toastError('Impossible de charger les sandbox.'))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(load, [])

  const creer = async () => {
    setBusy(true)
    try {
      await adminopsApi.creerSandbox()
      toastSuccess('Création lancée — disponible sous quelques minutes.')
      load()
    } catch (err) {
      toastError(err?.response?.data?.detail || 'Création impossible.')
    } finally {
      setBusy(false)
    }
  }

  const prolonger = async (id) => {
    try {
      await adminopsApi.prolongerSandbox(id)
      toastSuccess('Environnement prolongé de 14 jours.')
      load()
    } catch (err) {
      toastError(err?.response?.data?.detail || 'Prolongation impossible.')
    }
  }

  return (
    <div>
      <PageHeader
        title="Environnements sandbox"
        subtitle="Copies de test isolées de votre espace"
        actions={<Button onClick={creer} disabled={busy}>Créer un environnement de test</Button>}
      />
      <Card className="mt-4 p-4">
        {loading ? (
          <Spinner />
        ) : envs.length === 0 ? (
          <EmptyState title="Aucun sandbox" description="Créez un environnement de test pour explorer sans risque." />
        ) : (
          envs.map((env) => (
            <div key={env.id} className="flex items-center justify-between border-b py-3">
              <div>
                <Badge>{STATUT_LABEL[env.statut] || env.statut}</Badge>
                <span className="ml-3 text-sm text-muted-foreground">
                  Expire le {formatDate(env.date_expiration)}
                </span>
                {env.erreur && <span className="ml-3 text-sm text-destructive">{env.erreur}</span>}
              </div>
              {env.statut === 'pret' && env.prolongations_count < 2 && (
                <Button size="sm" variant="ghost" onClick={() => prolonger(env.id)}>
                  Prolonger (+14j)
                </Button>
              )}
            </div>
          ))
        )}
      </Card>
    </div>
  )
}
