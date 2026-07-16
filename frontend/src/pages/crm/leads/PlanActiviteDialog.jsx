// ZSAL2 — « Appliquer un plan d'activité » : sélectionne un plan (checklist
// de tâches commerciales, ex. « Nouveau lead solaire ») et l'applique en un
// clic au lead ouvert. Le serveur crée toutes les étapes (échéances relatives
// résolues côté serveur) et est idempotent (ré-appliquer ne duplique rien) —
// voir apps.crm.services.appliquer_plan_activite.
import { useEffect, useState } from 'react'
import crmApi from '../../../api/crmApi'
import { Button, Spinner } from '../../../ui'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'

export default function PlanActiviteDialog({ lead, onClose, onApplied }) {
  const [loading, setLoading] = useState(true)
  const [plans, setPlans] = useState([])
  const [planId, setPlanId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null) // nombre d'activités créées

  useEffect(() => {
    let alive = true
    crmApi.getPlansActivite()
      .then((r) => {
        if (!alive) return
        const all = r.data.results ?? r.data
        const actifs = (all ?? []).filter((p) => p.actif !== false)
        setPlans(actifs)
        if (actifs.length) setPlanId(String(actifs[0].id))
      })
      .catch(() => { if (alive) setError('Impossible de charger les plans d\'activité.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const selected = plans.find((p) => String(p.id) === String(planId)) ?? null

  const appliquer = async () => {
    if (!selected) return
    setBusy(true)
    setError(null)
    try {
      const res = await crmApi.appliquerPlanActivite(lead.id, selected.id)
      const activites = res.data ?? []
      setDone(activites.length)
      onApplied?.(activites)
    } catch (err) {
      setError(err?.response?.data?.detail
        ?? "L'application du plan a échoué — réessayez.")
    } finally {
      setBusy(false)
    }
  }

  const leadNom = `${lead.nom ?? ''} ${lead.prenom ?? ''}`.trim() || 'ce lead'

  return (
    // VX182 — shell fait-main remplacé par ResponsiveDialog (Escape + focus-
    // trap + bottom-sheet mobile) ; en-tête/pied conservés à l'identique.
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Appliquer un plan d'activité</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>

        <div className="modal-body">
          {loading && (
            <p className="sd-loading"><Spinner /> Chargement des plans…</p>
          )}

          {!loading && plans.length === 0 && !error && (
            <p className="gen-hint">
              Aucun plan d'activité actif. Créez-en un dans Paramètres.
            </p>
          )}

          {!loading && plans.length > 0 && done == null && (
            <>
              <p className="sd-intro">
                Appliquer quel plan à <strong>{leadNom}</strong> ?
              </p>
              <label className="form-label" htmlFor="pad-plan">Plan d'activité</label>
              <select
                id="pad-plan"
                className="form-control"
                value={planId}
                onChange={(e) => setPlanId(e.target.value)}
                autoFocus
              >
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nom} ({p.etapes?.length ?? 0} étape(s))
                  </option>
                ))}
              </select>
              {selected?.etapes?.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
                  {selected.etapes.map((e) => (
                    <li key={e.id}>
                      J+{e.delai_jours} — {e.resume_defaut || 'Activité'}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}

          {done != null && (
            <p className="form-success" role="status">
              {done} activité(s) planifiée(s) sur {leadNom}.
            </p>
          )}

          {error && <p className="form-error" role="alert">{error}</p>}
        </div>

        <div className="modal-footer">
          {done == null ? (
            <>
              <Button type="button" variant="outline" onClick={onClose}>
                Annuler
              </Button>
              {!loading && plans.length > 0 && (
                <Button type="button" onClick={appliquer}
                        loading={busy} disabled={busy || !selected}>
                  {busy ? 'Application…' : 'Appliquer le plan'}
                </Button>
              )}
            </>
          ) : (
            <Button type="button" onClick={onClose}>Fermer</Button>
          )}
        </div>
    </ResponsiveDialog>
  )
}
