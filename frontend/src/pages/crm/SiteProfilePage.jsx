import { useEffect, useState } from 'react'
import crmApi from '../../api/crmApi'
import PageHeader from '../../components/layout/PageHeader'
import {
  Button, Card, CardContent, Checkbox, Combobox, EmptyState,
  Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
  toast,
} from '../../ui'

/* ============================================================================
   WIR99/DC12 — Écran minimal de création/édition du profil site (SiteProfile).
   ----------------------------------------------------------------------------
   `crm.SiteProfile` est la SOURCE UNIQUE par client du profil énergie /
   toiture / pompage : il pré-remplit le générateur de devis pour les devis
   SANS lead (`ventesApi.getPrefillSite` → `crm.selectors.site_profile_for_client`).
   Le modèle et son endpoint `/crm/site-profiles/` existaient déjà mais aucun
   écran ne permettait de créer ni d'éditer un profil — il restait donc
   toujours vide, et le pré-remplissage promis n'arrivait jamais.

   Un seul profil par client (OneToOne côté serveur) : on choisit un client,
   on charge son profil s'il existe, on l'enregistre (POST ou PATCH).
   `company` est TOUJOURS posée côté serveur, jamais envoyée d'ici.
   ========================================================================== */

const RACCORDEMENT = [
  { value: 'monophase', label: 'Monophasé' },
  { value: 'triphase', label: 'Triphasé' },
]
const TYPE_INSTALLATION = [
  { value: 'residentiel', label: 'Résidentiel' },
  { value: 'industriel', label: 'Industriel / Commercial' },
  { value: 'agricole', label: 'Agricole (pompage)' },
]
const TYPE_TOITURE = [
  { value: 'tole', label: 'Tôle' },
  { value: 'beton', label: 'Béton' },
  { value: 'tuile', label: 'Tuile' },
  { value: 'sol', label: 'Au sol' },
]

const EMPTY = {
  facture_hiver: '', facture_ete: '', ete_differente: false,
  conso_mensuelle_kwh: '', raccordement: '', type_installation: '',
  pompe_cv: '', pompe_hmt_m: '', pompe_debit_m3h: '',
  type_toiture: '', surface_toiture_m2: '', inclinaison_deg: '',
}

// Le serveur renvoie des Decimals en chaîne ou en nombre : on normalise en
// chaîne pour des <input> contrôlés, et null → ''.
const toForm = (p) => {
  const out = { ...EMPTY }
  if (!p) return out
  for (const k of Object.keys(EMPTY)) {
    const v = p[k]
    if (k === 'ete_differente') out[k] = Boolean(v)
    else out[k] = v == null ? '' : String(v)
  }
  return out
}

// Les champs numériques vides doivent partir en `null` (et non ''), sinon le
// serveur refuse la valeur.
const toPayload = (form, clientId) => {
  const out = { client: Number(clientId) }
  for (const [k, v] of Object.entries(form)) {
    if (k === 'ete_differente') out[k] = Boolean(v)
    else out[k] = v === '' ? null : v
  }
  return out
}

export default function SiteProfilePage() {
  const [clients, setClients] = useState([])
  const [clientId, setClientId] = useState('')
  const [profileId, setProfileId] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    crmApi.getClients()
      .then((r) => {
        if (!active) return
        const data = r.data
        setClients(Array.isArray(data) ? data : (data?.results || []))
      })
      .catch(() => { if (active) setClients([]) })
    return () => { active = false }
  }, [])

  // Charge (ou réinitialise) le profil du client sélectionné.
  useEffect(() => {
    if (!clientId) { setProfileId(null); setForm(EMPTY); return }
    let active = true
    setLoading(true)
    crmApi.getSiteProfiles({ client: clientId })
      .then((r) => {
        if (!active) return
        const data = r.data
        const rows = Array.isArray(data) ? data : (data?.results || [])
        const p = rows[0] || null
        setProfileId(p?.id ?? null)
        setForm(toForm(p))
      })
      .catch(() => { if (active) { setProfileId(null); setForm(EMPTY) } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [clientId])

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }))
  const setInput = (k) => (e) => set(k)(e.target.value)

  const submit = async (e) => {
    e.preventDefault()
    if (!clientId) return
    setSaving(true)
    try {
      const payload = toPayload(form, clientId)
      const res = profileId
        ? await crmApi.updateSiteProfile(profileId, payload)
        : await crmApi.createSiteProfile(payload)
      setProfileId(res?.data?.id ?? profileId)
      toast.success('Profil site enregistré.')
    } catch {
      toast.error("Enregistrement impossible. Vérifiez les valeurs saisies.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page">
      <PageHeader
        title="Profils site"
        subtitle="Profil énergie / toiture / pompage réutilisable par client — saisi une fois, il pré-remplit ensuite le générateur de devis (y compris sans lead)."
      />

      <Card>
        <CardContent className="p-4">
          <div className="grid gap-1.5 max-w-md">
            <Label htmlFor="sp-client">Client</Label>
            <Combobox
              id="sp-client"
              options={clients.map((c) => ({
                value: String(c.id),
                label: `${c.nom}${c.prenom ? ` ${c.prenom}` : ''}`,
              }))}
              value={clientId ? String(clientId) : null}
              onChange={(v) => setClientId(v ? String(v) : '')}
              placeholder="— Sélectionner un client —"
              emptyText="Aucun client"
            />
          </div>
        </CardContent>
      </Card>

      {!clientId && (
        <EmptyState
          className="mt-4"
          title="Sélectionnez un client"
          description="Le profil site est unique par client : choisissez-en un pour le créer ou l'éditer."
        />
      )}

      {clientId && (
        <form onSubmit={submit} noValidate className="mt-4 space-y-4">
          <Card>
            <CardContent className="grid gap-4 p-4 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="sp-hiver">Facture hiver (MAD)</Label>
                <Input id="sp-hiver" type="number" step="any"
                  value={form.facture_hiver} onChange={setInput('facture_hiver')} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="sp-ete">Facture été (MAD)</Label>
                <Input id="sp-ete" type="number" step="any"
                  value={form.facture_ete} onChange={setInput('facture_ete')} />
              </div>
              <div className="flex items-center gap-2">
                <Checkbox id="sp-ete-diff" checked={form.ete_differente}
                  onCheckedChange={(v) => set('ete_differente')(Boolean(v))} />
                <Label htmlFor="sp-ete-diff">Facture d&apos;été différente</Label>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="sp-conso">Consommation mensuelle (kWh)</Label>
                <Input id="sp-conso" type="number" step="any"
                  value={form.conso_mensuelle_kwh}
                  onChange={setInput('conso_mensuelle_kwh')} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="sp-racc">Raccordement</Label>
                <Select value={form.raccordement || ''}
                  onValueChange={(v) => set('raccordement')(v)}>
                  <SelectTrigger id="sp-racc"><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>
                    {RACCORDEMENT.map((o) => (
                      <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="sp-type">Type d&apos;installation</Label>
                <Select value={form.type_installation || ''}
                  onValueChange={(v) => set('type_installation')(v)}>
                  <SelectTrigger id="sp-type"><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>
                    {TYPE_INSTALLATION.map((o) => (
                      <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="grid gap-4 p-4 sm:grid-cols-3">
              <div className="grid gap-1.5">
                <Label htmlFor="sp-cv">Pompe (CV)</Label>
                <Input id="sp-cv" type="number" step="any"
                  value={form.pompe_cv} onChange={setInput('pompe_cv')} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="sp-hmt">HMT (m)</Label>
                <Input id="sp-hmt" type="number" step="any"
                  value={form.pompe_hmt_m} onChange={setInput('pompe_hmt_m')} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="sp-debit">Débit (m³/h)</Label>
                <Input id="sp-debit" type="number" step="any"
                  value={form.pompe_debit_m3h} onChange={setInput('pompe_debit_m3h')} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="grid gap-4 p-4 sm:grid-cols-3">
              <div className="grid gap-1.5">
                <Label htmlFor="sp-toit">Type de toiture</Label>
                <Select value={form.type_toiture || ''}
                  onValueChange={(v) => set('type_toiture')(v)}>
                  <SelectTrigger id="sp-toit"><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>
                    {TYPE_TOITURE.map((o) => (
                      <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="sp-surface">Surface toiture (m²)</Label>
                <Input id="sp-surface" type="number" step="any"
                  value={form.surface_toiture_m2}
                  onChange={setInput('surface_toiture_m2')} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="sp-incl">Inclinaison (°)</Label>
                <Input id="sp-incl" type="number" step="any"
                  value={form.inclinaison_deg} onChange={setInput('inclinaison_deg')} />
              </div>
            </CardContent>
          </Card>

          <div className="flex items-center gap-3">
            <Button type="submit" disabled={saving || loading}>
              {profileId ? 'Enregistrer le profil' : 'Créer le profil'}
            </Button>
            {loading && (
              <span className="text-xs text-muted-foreground">Chargement…</span>
            )}
          </div>
        </form>
      )}
    </div>
  )
}
