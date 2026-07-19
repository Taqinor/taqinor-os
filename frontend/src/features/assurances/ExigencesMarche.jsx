import { useEffect, useState } from 'react'
import { ClipboardCheck, AlertTriangle, Plus, RefreshCw, Trash2 } from 'lucide-react'
import assurancesApi from './assurancesApi'
import {
  Badge, Button, Card, CardContent, EmptyState, IconButton, Input, Label, Spinner,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem, toast,
} from '../../ui'
import { PageHeader } from '../../ui/PageHeader'
import { formatMAD } from '../../lib/format'
import { POLICE_TYPES } from './status'

/* ============================================================================
   WIR145 (NTASS) — Exigences d'assurance par marché : un marché peut exiger un
   type de police (ex. décennale) avec un montant de couverture minimum. La
   vérification croise les polices ACTIVES de l'entreprise et pose le statut
   conforme / non_conforme (verifier_conformite_assurance_marche, backend).
   ========================================================================== */

const STATUT_TONE = { conforme: 'success', non_conforme: 'danger' }
const STATUT_LABEL = { conforme: 'Conforme', non_conforme: 'Non conforme', non_verifie: 'Non vérifié' }

export default function ExigencesMarche() {
  const [exigences, setExigences] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    marche_ref: '', type_police_requis: POLICE_TYPES[0]?.value || '',
    montant_couverture_minimum: '',
  })

  const load = () => {
    setLoading(true)
    assurancesApi.getExigencesMarche()
      .then((r) => { setExigences(Array.isArray(r.data) ? r.data : (r.data?.results ?? [])); setError(false) })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const creer = async () => {
    if (!form.marche_ref.trim()) { toast.error('Référence marché requise.'); return }
    setBusy(true)
    try {
      await assurancesApi.createExigenceMarche({
        marche_ref: form.marche_ref.trim(),
        type_police_requis: form.type_police_requis,
        montant_couverture_minimum: form.montant_couverture_minimum || 0,
      })
      toast.success('Exigence ajoutée.')
      setForm({ marche_ref: '', type_police_requis: POLICE_TYPES[0]?.value || '', montant_couverture_minimum: '' })
      load()
    } catch { toast.error('Création impossible.') }
    finally { setBusy(false) }
  }

  const verifier = async (id) => {
    setBusy(true)
    try {
      await assurancesApi.verifierExigenceMarche(id)
      toast.success('Conformité vérifiée.')
      load()
    } catch { toast.error('Vérification impossible.') }
    finally { setBusy(false) }
  }

  const supprimer = async (id) => {
    setBusy(true)
    try {
      await assurancesApi.deleteExigenceMarche(id)
      toast.success('Exigence supprimée.')
      load()
    } catch { toast.error('Suppression impossible.') }
    finally { setBusy(false) }
  }

  return (
    <div className="ui-root page">
      <PageHeader title="Exigences d'assurance par marché" icon={ClipboardCheck} />

      <Card className="mb-4">
        <CardContent className="pt-4">
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <Label>Référence marché</Label>
              <Input value={form.marche_ref} placeholder="MARCHE-2026-001"
                     onChange={(e) => setForm((f) => ({ ...f, marche_ref: e.target.value }))} />
            </div>
            <div>
              <Label>Type de police requis</Label>
              <Select value={form.type_police_requis}
                      onValueChange={(v) => setForm((f) => ({ ...f, type_police_requis: v }))}>
                <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {POLICE_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Couverture minimum (MAD)</Label>
              <Input type="number" step="any" value={form.montant_couverture_minimum}
                     onChange={(e) => setForm((f) => ({ ...f, montant_couverture_minimum: e.target.value }))} />
            </div>
            <Button type="button" onClick={creer} disabled={busy}>
              <Plus className="size-4" /> Ajouter
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <Spinner />
      ) : error ? (
        <EmptyState icon={AlertTriangle} title="Données indisponibles"
                    description="Impossible de charger les exigences." />
      ) : exigences.length === 0 ? (
        <EmptyState icon={ClipboardCheck} title="Aucune exigence"
                    description="Ajoutez une exigence d'assurance pour un marché ci-dessus." />
      ) : (
        <ul className="flex flex-col gap-2">
          {exigences.map((ex) => (
            <li key={ex.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
              <span className="flex flex-col">
                <span className="font-medium">Marché {ex.marche_ref}</span>
                <span className="text-muted-foreground">
                  {ex.type_police_requis_display || ex.type_police_requis}
                  {ex.montant_couverture_minimum > 0 && ` · min ${formatMAD(ex.montant_couverture_minimum, { decimals: 0 })}`}
                </span>
              </span>
              <span className="flex items-center gap-2">
                <Badge tone={STATUT_TONE[ex.statut_verification] || 'neutral'}>
                  {STATUT_LABEL[ex.statut_verification] || ex.statut_verification || 'Non vérifié'}
                </Badge>
                <Button type="button" variant="outline" size="sm" disabled={busy}
                        onClick={() => verifier(ex.id)}>
                  <RefreshCw className="size-3.5" /> Vérifier
                </Button>
                <IconButton size="md" variant="ghost" label="Supprimer"
                            className="text-destructive hover:text-destructive"
                            onClick={() => supprimer(ex.id)}>
                  <Trash2 className="size-4" />
                </IconButton>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
