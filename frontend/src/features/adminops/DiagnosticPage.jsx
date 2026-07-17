import { useEffect, useState } from 'react'
import adminopsApi from './adminopsApi'
import api from '../../api/axios'
import PageHeader from '../../components/layout/PageHeader'
import { Button, Card, KeyValueTable, Spinner } from '../../ui'
import { toastError } from '../../lib/toast'

/* ============================================================================
   NTADM23/24 — Diagnostic tenant (instantané non-sensible) + export du
   « support bundle » .zip à joindre à une demande de support.
   ========================================================================== */

export default function DiagnosticPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminopsApi
      .diagnostic()
      .then((res) => setData(res.data))
      .catch(() => toastError('Impossible de charger le diagnostic.'))
      .finally(() => setLoading(false))
  }, [])

  const telechargerBundle = async () => {
    try {
      const res = await api.get('/adminops/diagnostic/support-bundle/', {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'support-bundle.zip'
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      toastError('Téléchargement impossible.')
    }
  }

  if (loading) return <Spinner />

  const items = data
    ? [
        { key: 'users', label: "Nombre d'utilisateurs", value: data.nb_utilisateurs },
        { key: 'sandbox', label: 'Sandbox actifs', value: data.sandbox_actifs },
        { key: 'packages', label: 'Packages exportés', value: data.config_packages_exportes },
        {
          key: 'last_login',
          label: 'Dernière connexion',
          value: data.derniere_connexion
            ? `${data.derniere_connexion[0]} — ${data.derniere_connexion[1]}`
            : '—',
        },
      ]
    : []

  return (
    <div>
      <PageHeader
        title="Diagnostic tenant"
        subtitle="État non-sensible de votre espace (aucune donnée d'un autre compte)"
        actions={<Button onClick={telechargerBundle}>Exporter le support bundle (.zip)</Button>}
      />
      <Card className="mt-4 p-4">
        <KeyValueTable items={items} />
      </Card>
    </div>
  )
}
