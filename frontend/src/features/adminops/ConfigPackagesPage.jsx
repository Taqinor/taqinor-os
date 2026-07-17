import { useEffect, useState } from 'react'
import adminopsApi from './adminopsApi'
import PageHeader from '../../components/layout/PageHeader'
import { Button, Card, EmptyState, Spinner } from '../../ui'
import { formatDateTime } from '../../lib/format'
import { toastError, toastSuccess } from '../../lib/toast'

/* ============================================================================
   NTADM15 — Écran « Packages de configuration » : liste des exports, bouton
   « Exporter la config actuelle », import avec aperçu du diff avant application
   (double confirmation). NTADM31 (assistant de sélection de catégories) : le
   contenu exporté est déjà scopé (rôles/champs/templates) — l'aperçu du diff
   tient lieu de garde-fou avant tout write.
   ========================================================================== */

function diffCount(diff) {
  if (!diff) return 0
  return Object.values(diff).reduce(
    (n, d) => n + (d.ajouts?.length || 0) + (d.modifications?.length || 0) + (d.suppressions?.length || 0),
    0)
}

export default function ConfigPackagesPage() {
  const [packages, setPackages] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [diff, setDiff] = useState(null)
  const [pendingContenu, setPendingContenu] = useState(null)

  const load = () => {
    setLoading(true)
    adminopsApi
      .listPackages()
      .then((res) => setPackages(res.data?.results ?? res.data ?? []))
      .catch(() => toastError('Impossible de charger les packages.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const exporter = async () => {
    const nom = window.prompt('Nom du package :', 'Configuration')
    if (!nom) return
    setBusy(true)
    try {
      await adminopsApi.exporterPackage(nom)
      toastSuccess('Configuration exportée.')
      load()
    } catch {
      toastError('Export impossible.')
    } finally {
      setBusy(false)
    }
  }

  const onFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const contenu = JSON.parse(await file.text())
      const res = await adminopsApi.previsualiserPackage(contenu)
      setDiff(res.data)
      setPendingContenu(contenu)
    } catch {
      toastError('Fichier invalide ou aperçu impossible.')
    }
    e.target.value = ''
  }

  const appliquer = async () => {
    if (!window.confirm('Confirmer l\'application de ce package ? Cette action modifie la configuration.')) return
    try {
      await adminopsApi.appliquerPackage(pendingContenu)
      toastSuccess('Package appliqué.')
      setDiff(null)
      setPendingContenu(null)
      load()
    } catch {
      toastError('Application impossible.')
    }
  }

  return (
    <div>
      <PageHeader
        title="Packages de configuration"
        subtitle="Exportez / importez la configuration (rôles, champs, modèles) — jamais de donnée client"
        actions={
          <div className="flex gap-2">
            <Button onClick={exporter} disabled={busy}>Exporter la config actuelle</Button>
            <label className="cursor-pointer">
              <span className="inline-flex items-center rounded-md border px-3 py-2 text-sm">Importer…</span>
              <input type="file" accept="application/json" className="hidden" onChange={onFileChange} />
            </label>
          </div>
        }
      />

      {diff && (
        <Card className="mt-4 border-amber-300 p-4">
          <h3 className="mb-2 font-semibold">Aperçu du diff ({diffCount(diff)} changement(s))</h3>
          {Object.entries(diff).map(([cat, d]) => (
            <div key={cat} className="mb-2 text-sm">
              <strong className="capitalize">{cat}</strong> :
              <span className="ml-2 text-green-600">+{d.ajouts?.length || 0}</span>
              <span className="ml-2 text-amber-600">~{d.modifications?.length || 0}</span>
              <span className="ml-2 text-red-600">−{d.suppressions?.length || 0}</span>
            </div>
          ))}
          <div className="mt-3 flex gap-2">
            <Button onClick={appliquer}>Appliquer</Button>
            <Button variant="ghost" onClick={() => { setDiff(null); setPendingContenu(null) }}>
              Annuler
            </Button>
          </div>
        </Card>
      )}

      <Card className="mt-4 p-4">
        {loading ? (
          <Spinner />
        ) : packages.length === 0 ? (
          <EmptyState title="Aucun export" description="Exportez votre configuration pour la réutiliser ou la sauvegarder." />
        ) : (
          packages.map((p) => (
            <div key={p.id} className="flex items-center justify-between border-b py-2 text-sm">
              <span>{p.nom} <span className="text-muted-foreground">v{p.version}</span></span>
              <span className="text-muted-foreground">{formatDateTime(p.date_creation)}{p.contenu_purge ? ' (contenu purgé)' : ''}</span>
            </div>
          ))
        )}
      </Card>
    </div>
  )
}
