import { useEffect, useState } from 'react'
import adminopsApi from './adminopsApi'
import PageHeader from '../../components/layout/PageHeader'
import { Card, Segmented, Spinner } from '../../ui'
import { toastError } from '../../lib/toast'

/* ============================================================================
   NTADM17 — Dashboard adoption par module : tableau (module → utilisateurs
   actifs / événements / dernière utilisation), filtrable 7/30/90 jours.
   ========================================================================== */

const PERIODES = [
  { value: '7', label: '7 j' },
  { value: '30', label: '30 j' },
  { value: '90', label: '90 j' },
]

export default function AdoptionPage() {
  const [periode, setPeriode] = useState('30')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
    setLoading(true)
    adminopsApi
      .adoption(Number(periode))
      .then((res) => setData(res.data))
      .catch(() => toastError("Impossible de charger l'adoption."))
      .finally(() => setLoading(false))
  }, [periode])

  const parModule = data?.par_module || {}

  return (
    <div>
      <PageHeader
        title="Analytics d'adoption"
        subtitle="Usage des modules par votre équipe"
        actions={<Segmented options={PERIODES} value={periode} onChange={setPeriode} />}
      />
      <Card className="mt-4 p-4">
        {loading ? (
          <Spinner />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2">Module</th>
                <th>Utilisateurs actifs</th>
                <th>Événements</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(parModule).map(([module, stats]) => (
                <tr key={module} className="border-b">
                  <td className="py-2">{module}</td>
                  <td>{stats.nb_utilisateurs_actifs}</td>
                  <td>{stats.nb_evenements}</td>
                </tr>
              ))}
              {Object.keys(parModule).length === 0 && (
                <tr>
                  <td colSpan={3} className="py-4 text-center text-muted-foreground">
                    Aucun événement sur la période.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
