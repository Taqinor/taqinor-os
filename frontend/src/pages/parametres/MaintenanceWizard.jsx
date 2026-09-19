import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { AlertTriangle, Clock, Send } from 'lucide-react'
import {
  Button, Card, CardContent, Input, Label, Textarea, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import coreApi from '../../api/coreApi'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   NTOBS19 — Assistant guidé « Créer une fenêtre de maintenance » (wizard 3
   étapes), au-dessus de `core.MaintenanceWindow` (NTOBS9) TEL QUEL — aucun
   nouveau modèle, aucun nouvel endpoint : `coreApi.maintenanceWindows.create`
   existait déjà (l'écran admin DIRECT n'existait, lui, nulle part encore).
   ----------------------------------------------------------------------------
   1. Portée — cette société (par défaut) ou système entier (superutilisateur
      seulement, reflète `IsDirecteurOrAdmin`/`is_superuser` côté serveur :
      `MaintenanceWindowListCreateView.perform_create` FORCE `company` à la
      société de l'appelant pour tout non-superutilisateur, quoi que l'écran
      envoie — l'option « système entier » n'est donc proposée qu'à qui peut
      réellement en faire usage) + région (libellé libre, optionnel).
   2. Fenêtre — début/fin, impact attendu, description.
   3. Aperçu — simulateur affichant le texte EXACT de la bannière in-app
      (même formule que `MaintenanceBanner.jsx`/NTOBS32) et de l'e-mail
      envoyé aux admins (même gabarit que
      `core.maintenance_windows._notifier_fenetre`) AVANT confirmation —
      c'est le SEUL bouton qui écrit.
   ========================================================================== */

const IMPACTS = [
  { value: 'aucun', label: 'Aucun' },
  { value: 'degrade', label: 'Dégradé' },
  { value: 'interruption', label: 'Interruption' },
]

// Même formule que `MaintenanceBanner.jsx` (NTOBS9/NTOBS32) — dupliquée à
// dessein (fichier UI générique, jamais couplé à un écran Paramètres).
function formatCountdown(debuteLeIso) {
  const ms = new Date(debuteLeIso).getTime() - Date.now()
  if (!Number.isFinite(ms) || ms <= 0) return null
  const heures = Math.floor(ms / (1000 * 60 * 60))
  const minutes = Math.floor((ms % (1000 * 60 * 60)) / (1000 * 60))
  if (heures >= 1) return `dans ${heures} h`
  return `dans ${Math.max(1, minutes)} min`
}

const emptyForm = {
  systemeEntier: false,
  region: '',
  debute_le: '',
  termine_le: '',
  impact: 'degrade',
  description: '',
}

export default function MaintenanceWizard() {
  const navigate = useNavigate()
  const isSuperuser = useSelector((s) => !!s.auth.user?.is_superuser)
  const [etape, setEtape] = useState(1)
  const [form, setForm] = useState(emptyForm)
  const [busy, setBusy] = useState(false)

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const etape1Valide = true // portée/région optionnelles, jamais bloquant.
  const etape2Valide = !!form.debute_le && !!form.termine_le
    && new Date(form.termine_le) > new Date(form.debute_le)

  const suivant = () => {
    if (etape === 1 && !etape1Valide) return
    if (etape === 2 && !etape2Valide) {
      toast.error('La fin doit être postérieure au début.')
      return
    }
    setEtape((e) => Math.min(3, e + 1))
  }
  const precedent = () => setEtape((e) => Math.max(1, e - 1))

  const confirmer = async () => {
    setBusy(true)
    try {
      const payload = {
        region: form.region.trim(),
        debute_le: new Date(form.debute_le).toISOString(),
        termine_le: new Date(form.termine_le).toISOString(),
        impact: form.impact,
        description: form.description.trim(),
      }
      // Superutilisateur ET « système entier » choisi -> `company: null`
      // explicite (seul cas où le serveur en tiendra compte — tout autre
      // appelant se voit de toute façon reposer sur SA société, quoi qu'on
      // envoie ici).
      if (isSuperuser && form.systemeEntier) payload.company = null
      await coreApi.maintenanceWindows.create(payload)
      toast.success('Fenêtre de maintenance créée.')
      navigate('/parametres')
    } catch (e) {
      const detail = e?.response?.data?.detail
        || Object.values(e?.response?.data || {})[0]
      toast.error((Array.isArray(detail) ? detail[0] : detail) || 'Création impossible.')
    } finally { setBusy(false) }
  }

  const countdown = formatCountdown(form.debute_le)

  return (
    <div className="page flex flex-col gap-6">
      <div className="page-header">
        <h1 className="page-title flex items-center gap-2">
          <AlertTriangle className="size-5 text-muted-foreground" aria-hidden="true" />
          Créer une fenêtre de maintenance
        </h1>
        <div className="page-subtitle">
          Étape {etape} sur 3 — {etape === 1 ? 'Portée' : etape === 2 ? 'Fenêtre' : 'Aperçu'}
        </div>
      </div>

      {etape === 1 && (
        <Card>
          <CardContent className="flex flex-col gap-4 pt-4 sm:pt-5">
            <fieldset className="flex flex-col gap-2">
              <legend className="mb-1 text-sm font-medium">Portée</legend>
              <label className="flex items-center gap-2 text-sm">
                <input type="radio" name="maintenance-portee" checked={!form.systemeEntier}
                  onChange={() => setField('systemeEntier', false)} />
                Cette société
              </label>
              {isSuperuser && (
                <label className="flex items-center gap-2 text-sm">
                  <input type="radio" name="maintenance-portee" checked={form.systemeEntier}
                    onChange={() => setField('systemeEntier', true)} />
                  Système entier (toutes les sociétés)
                </label>
              )}
            </fieldset>
            <div>
              <Label htmlFor="maintenance-region">Région (optionnel)</Label>
              <Input id="maintenance-region" value={form.region}
                placeholder="ex. Casablanca-Settat"
                onChange={(e) => setField('region', e.target.value)} />
            </div>
          </CardContent>
        </Card>
      )}

      {etape === 2 && (
        <Card>
          <CardContent className="grid gap-4 pt-4 sm:grid-cols-2 sm:pt-5">
            <div>
              <Label htmlFor="maintenance-debut">Débute le</Label>
              <Input id="maintenance-debut" type="datetime-local" value={form.debute_le}
                onChange={(e) => setField('debute_le', e.target.value)} />
            </div>
            <div>
              <Label htmlFor="maintenance-fin">Termine le</Label>
              <Input id="maintenance-fin" type="datetime-local" value={form.termine_le}
                onChange={(e) => setField('termine_le', e.target.value)} />
            </div>
            <div>
              <Label htmlFor="maintenance-impact">Impact attendu</Label>
              <Select value={form.impact} onValueChange={(v) => setField('impact', v)}>
                <SelectTrigger id="maintenance-impact"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {IMPACTS.map((i) => (
                    <SelectItem key={i.value} value={i.value}>{i.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="maintenance-description">Description</Label>
              <Textarea id="maintenance-description" value={form.description} rows={3}
                placeholder="Ce que les utilisateurs verront (bannière + e-mail)"
                onChange={(e) => setField('description', e.target.value)} />
            </div>
          </CardContent>
        </Card>
      )}

      {etape === 3 && (
        <div className="flex flex-col gap-4">
          <Card>
            <CardContent className="flex flex-col gap-2 pt-4 text-sm sm:pt-5">
              <h2 className="text-sm font-semibold">Aperçu — bannière in-app</h2>
              <p className="text-xs text-muted-foreground">
                Texte exact affiché à tous les utilisateurs concernés dès que
                la fenêtre entre dans l'horizon de 72h (identique à
                l'écran réel — NTOBS9/NTOBS32).
              </p>
              <div
                data-testid="maintenance-wizard-banner-preview"
                className="flex items-center gap-2 rounded-md border border-amber-300/60 bg-amber-50 px-4 py-1.5 text-[12.5px] font-medium text-amber-800 dark:border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-200"
              >
                <Clock className="size-3.5" aria-hidden="true" />
                <span>
                  Fenêtre de maintenance planifiée{countdown ? ` ${countdown}` : ''}
                  {form.impact && form.impact !== 'aucun' ? ` (${IMPACTS.find((i) => i.value === form.impact)?.label})` : ''}.
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="flex flex-col gap-2 pt-4 text-sm sm:pt-5">
              <h2 className="flex items-center gap-1.5 text-sm font-semibold">
                <Send className="size-4 text-muted-foreground" aria-hidden="true" />
                Aperçu — e-mail envoyé aux administrateurs
              </h2>
              <p className="text-xs text-muted-foreground">
                Envoyé 24h avant le début, puis 1h avant (jamais deux fois
                pour le même seuil) — exemple ci-dessous pour le seuil 24h.
              </p>
              <div data-testid="maintenance-wizard-email-preview"
                className="rounded-lg border border-border p-3">
                <p><span className="text-muted-foreground">Objet : </span>
                  <span className="font-medium">Fenêtre de maintenance dans 24h</span></p>
                <p className="mt-1 text-muted-foreground">
                  {form.description || '(aucune description saisie)'}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="flex flex-col gap-1 pt-4 text-sm sm:pt-5">
              <h2 className="text-sm font-semibold">Récapitulatif</h2>
              <p>
                <span className="text-muted-foreground">Portée : </span>
                {form.systemeEntier ? 'Système entier' : 'Cette société'}
                {form.region ? ` — ${form.region}` : ''}
              </p>
              <p>
                <span className="text-muted-foreground">Fenêtre : </span>
                {form.debute_le ? formatDateTime(form.debute_le) : '—'}
                {' → '}
                {form.termine_le ? formatDateTime(form.termine_le) : '—'}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" disabled={busy}
          onClick={etape === 1 ? () => navigate('/parametres') : precedent}>
          {etape === 1 ? 'Annuler' : 'Précédent'}
        </Button>
        {etape === 3 ? (
          <Button type="button" loading={busy} disabled={busy} onClick={confirmer}>
            {busy ? 'Création…' : 'Créer la fenêtre'}
          </Button>
        ) : (
          <Button type="button" disabled={etape === 2 && !etape2Valide} onClick={suivant}>
            Suivant
          </Button>
        )}
      </div>
    </div>
  )
}
