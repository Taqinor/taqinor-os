/* NTSUB23 — Assistant « migrer un contrat existant vers un plan catalogue ».
   ----------------------------------------------------------------------------
   Les contrats créés AVANT le catalogue d'offres (NTSUB1) n'ont pas de
   `plan_abonnement`. Cet écran de confirmation les rattache :

     • sans cocher « appliquer le prix » → CLASSIFICATION SEULE : le montant du
       contrat, ses échéances et son statut ne bougent pas d'un centime ;
     • en cochant → le prix du plan est appliqué, en créant un AVENANT
       (XCTR6, prorata) côté serveur.

   Le DELTA de prix est affiché AVANT validation, calculé sur les deux valeurs
   que le serveur a déjà fournies (montant du contrat, prix de base du plan) —
   aucun montant n'est inventé ici. */
import { useEffect, useMemo, useState } from 'react'
import api from '../../api/axios'
import contratsApi from '../../api/contratsApi'
import {
  Button, Checkbox, Label, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../ui'
import { formatMAD } from '../../lib/format'

const listData = (res) => (
  Array.isArray(res.data) ? res.data : (res.data?.results ?? []))

function messageErreur(err, repli) {
  const d = err?.response?.data
  if (typeof d === 'string') return d
  if (d?.detail) return d.detail
  if (d && typeof d === 'object') {
    const [champ, valeur] = Object.entries(d)[0] || []
    if (champ) return `${champ} : ${Array.isArray(valeur) ? valeur[0] : valeur}`
  }
  return repli
}

export default function RattacherPlanDialog({ contrat, onClose, onDone }) {
  const [plans, setPlans] = useState([])
  const [planId, setPlanId] = useState('')
  const [appliquerPrix, setAppliquerPrix] = useState(false)
  const [busy, setBusy] = useState(false)
  const [erreurChamp, setErreurChamp] = useState('')

  useEffect(() => {
    let vivant = true
    api.get('/contrats/plans-abonnement/')
      .then((r) => { if (vivant) setPlans(listData(r)) })
      .catch(() => { if (vivant) setPlans([]) })
    return () => { vivant = false }
  }, [])

  const plan = useMemo(
    () => plans.find((p) => String(p.id) === String(planId)) || null,
    [plans, planId])

  const montantActuel = Number(contrat?.montant ?? 0)
  const prixPlan = plan ? Number(plan.prix_base ?? 0) : null
  const delta = prixPlan === null ? null : prixPlan - montantActuel

  const valider = async () => {
    if (!planId) {
      setErreurChamp('plan')
      toast.error('Plan d’abonnement : choisissez un plan.')
      return
    }
    setErreurChamp('')
    setBusy(true)
    try {
      const res = await contratsApi.rattacherPlan(contrat.id, {
        plan: planId, appliquer_prix: appliquerPrix,
      })
      toast.success(res.data?.prix_applique
        ? 'Plan rattaché et prix appliqué (avenant créé).'
        : 'Plan rattaché — aucun montant modifié.')
      onDone?.()
    } catch (err) {
      toast.error(messageErreur(err, 'Rattachement impossible.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Rattacher ce contrat à un plan catalogue</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="rp-plan">Plan d’abonnement</Label>
            <select
              id="rp-plan" value={planId}
              onChange={(e) => setPlanId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">Choisir un plan…</option>
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} — {p.nom}
                </option>
              ))}
            </select>
            {erreurChamp === 'plan' && (
              <span className="text-xs text-destructive">
                Plan d’abonnement : champ obligatoire.
              </span>
            )}
          </div>

          <div className="rounded-lg border px-3 py-2 text-sm">
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">Montant actuel du contrat</span>
              <strong>{formatMAD(montantActuel)}</strong>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">Prix de base du plan</span>
              <strong>{prixPlan === null ? '—' : formatMAD(prixPlan)}</strong>
            </div>
            <div className="mt-1 flex justify-between gap-3 border-t pt-1">
              <span className="text-muted-foreground">Delta</span>
              <strong className={
                delta === null || delta === 0 ? '' : (delta > 0 ? 'text-warning' : 'text-success')
              }>
                {delta === null ? '—' : formatMAD(delta)}
              </strong>
            </div>
          </div>

          <div className="flex items-start gap-2">
            <Checkbox
              id="rp-appliquer"
              checked={appliquerPrix}
              onCheckedChange={(v) => setAppliquerPrix(Boolean(v))}
            />
            <Label htmlFor="rp-appliquer" className="text-sm font-normal">
              Appliquer le prix du plan au contrat (crée un avenant, avec
              prorata sur la prochaine échéance). Décoché, le rattachement
              n’est qu’un classement : aucun montant existant n’est modifié.
            </Label>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={valider} disabled={busy}>Rattacher</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
