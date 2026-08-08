import { useEffect, useState } from 'react'
import { Card, Label, Input, Button, Checkbox, toast } from '../../ui'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT94 — Réglages RH.
   ----------------------------------------------------------------------------
   `ReglageRH` (XRH12/XRH24, une ligne par société) porte le rayon de
   géo-clôture (`geofence_metres`) du pointage chantier — l'action
   `mon-reglage` (GET/PATCH) n'était appelée par personne. Désactiver le rayon
   GPS (case décochée → `geofence_metres: null`) redevient effectif
   IMMÉDIATEMENT sur le prochain pointage, puisque le pointage relit
   `ReglageRH` à chaque appel — aucun redéploiement n'est nécessaire.
   ========================================================================== */

export default function ReglagesRh() {
  const [reglage, setReglage] = useState(null)
  const [geofenceActif, setGeofenceActif] = useState(false)
  const [geofenceMetres, setGeofenceMetres] = useState('')
  const [retention, setRetention] = useState('24')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let vivant = true
    setLoading(true)
    setError(null)
    rhApi.getMonReglageRh()
      .then((res) => {
        if (!vivant) return
        const data = res.data
        setReglage(data)
        setGeofenceActif(data.geofence_metres != null)
        setGeofenceMetres(data.geofence_metres != null ? String(data.geofence_metres) : '')
        setRetention(String(data.retention_candidatures_mois ?? 24))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les réglages RH.')
        toast.error('Impossible de charger les réglages RH.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [])

  const enregistrer = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const res = await rhApi.updateMonReglageRh({
        geofence_metres: geofenceActif ? (Number(geofenceMetres) || 0) : null,
        retention_candidatures_mois: Number(retention) || 24,
      })
      setReglage(res.data)
      toast.success('Réglages RH enregistrés.')
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Réglages RH</h2>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Chargement…</p>
      ) : error ? (
        <Card className="p-4 text-sm text-destructive" role="alert">{error}</Card>
      ) : (
        <Card className="max-w-lg p-5">
          <form onSubmit={enregistrer} className="flex flex-col gap-5" noValidate>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <Checkbox id="rr-geofence-actif" checked={geofenceActif} onCheckedChange={(v) => setGeofenceActif(Boolean(v))} />
                <Label htmlFor="rr-geofence-actif">Contrôler le rayon GPS au pointage chantier</Label>
              </div>
              {geofenceActif && (
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="rr-geofence-metres">Rayon (mètres)</Label>
                  <Input id="rr-geofence-metres" type="number" step="any" min="0"
                    value={geofenceMetres} onChange={(e) => setGeofenceMetres(e.target.value)} />
                </div>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rr-retention">Rétention des candidatures rejetées (mois)</Label>
              <Input id="rr-retention" type="number" step="any" min="1"
                value={retention} onChange={(e) => setRetention(e.target.value)} />
            </div>
            <div>
              <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
            </div>
            {reglage?.date_modification && (
              <p className="text-xs text-muted-foreground">
                Dernière modification serveur : {new Date(reglage.date_modification).toLocaleString('fr-FR')}
              </p>
            )}
          </form>
        </Card>
      )}
    </div>
  )
}
