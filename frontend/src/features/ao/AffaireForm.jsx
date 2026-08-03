import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import aoApi from '../../api/aoApi'
import {
  Button, Card, CardHeader, CardTitle, CardContent, Input, Textarea, Label, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { getApiError } from '../../lib/apiError'

/* ============================================================================
   AOF — Écran de création d'une affaire AO (`/ao/affaires/nouveau`).
   ----------------------------------------------------------------------------
   194 tâches du groupe AOF avaient été livrées et cochées SANS que cet écran
   n'existe jamais — `AffairesList` n'avait AUCUN moyen d'ouvrir une affaire.
   Ce composant crée réellement l'enregistrement via
   `aoApi.affaires.create()` (POST `/ao/appels-offres/`, ViewSet legacy ODX11).

   Contrat serveur (`apps/ao/serializers.py::AppelOffreSerializer` +
   `apps/ao/models.py::AppelOffre`), vérifié avant d'écrire cet écran :
   - `objet` est le SEUL champ vraiment obligatoire.
   - `reference` (la nôtre, `AO-AAAAMM-0001`) est GÉNÉRÉE côté serveur quand
     elle est absente/vide (`views.py::perform_create` —
     `(serializer.validated_data.get('reference') or '').strip()`) : jamais
     rendue obligatoire ici, et l'écran le dit à l'utilisateur.
   - `company` est posé CÔTÉ SERVEUR (`perform_create`) — jamais envoyé
     depuis ce formulaire.
   - `type_marche`/`mode_passation` : libellés FR copiés de
     `AppelOffre.TypeMarche`/`AppelOffre.ModePassation` (jamais inventés).

   `aoApi.affaires.create()` (fabrique CRUD ARC44) renvoie la réponse axios
   BRUTE — l'objet créé vit dans `.data` (une fiche a déjà affiché « #undefined »
   dans ce dépôt pour avoir oublié ce déballage, cf. AffaireDetail.jsx).

   Erreurs 400 : `getApiError()` (`lib/apiError.js`, VX203) extrait
   `fieldErrors` du payload DRF — affichées VERBATIM sous chaque champ,
   AUCUNE règle métier réimplémentée côté client.
   ========================================================================== */

const TYPE_MARCHE = [
  { value: 'public', label: 'Public' },
  { value: 'prive', label: 'Privé' },
]

const MODE_PASSATION = [
  { value: 'appel_ouvert', label: "Appel d'offres ouvert" },
  { value: 'appel_restreint', label: "Appel d'offres restreint" },
  { value: 'concours', label: 'Concours' },
  { value: 'negocie', label: 'Marché négocié' },
  { value: 'consultation', label: 'Consultation / bon de commande' },
  { value: 'autre', label: 'Autre' },
]

function emptyForm() {
  return {
    objet: '',
    acheteur: '',
    reference_acheteur: '',
    reference: '',
    type_marche: 'public',
    mode_passation: 'appel_ouvert',
    lot: '',
    reference_cps: '',
    date_limite: '',
    date_ouverture_plis: '',
    validite_offre_jours: '',
    delai_execution_jours: '',
    montant_estime: '',
    caution_provisoire: '',
    site_adresse: '',
  }
}

// Ne JAMAIS envoyer `company` (posé côté serveur) ni un champ optionnel vide
// (le serveur applique alors son propre défaut/génération — reference,
// validite_offre_jours (75j), montant_estime/caution_provisoire (0)…).
function buildPayload(form) {
  const payload = { objet: form.objet.trim(), type_marche: form.type_marche, mode_passation: form.mode_passation }
  if (form.acheteur.trim()) payload.acheteur = form.acheteur.trim()
  if (form.reference_acheteur.trim()) payload.reference_acheteur = form.reference_acheteur.trim()
  if (form.reference.trim()) payload.reference = form.reference.trim()
  if (form.lot.trim()) payload.lot = form.lot.trim()
  if (form.reference_cps.trim()) payload.reference_cps = form.reference_cps.trim()
  if (form.date_limite) payload.date_limite = form.date_limite
  if (form.date_ouverture_plis) payload.date_ouverture_plis = form.date_ouverture_plis
  if (form.validite_offre_jours !== '') payload.validite_offre_jours = Number(form.validite_offre_jours)
  if (form.delai_execution_jours !== '') payload.delai_execution_jours = Number(form.delai_execution_jours)
  if (form.montant_estime !== '') payload.montant_estime = Number(form.montant_estime)
  if (form.caution_provisoire !== '') payload.caution_provisoire = Number(form.caution_provisoire)
  if (form.site_adresse.trim()) payload.site_adresse = form.site_adresse.trim()
  return payload
}

function FieldError({ message }) {
  if (!message) return null
  return <p role="alert" className="text-xs text-destructive">{message}</p>
}

export default function AffaireForm() {
  const navigate = useNavigate()
  const [form, setForm] = useState(emptyForm)
  const [fieldErrors, setFieldErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const setValue = (key, value) => setForm((f) => ({ ...f, [key]: value }))

  const submit = async (e) => {
    e.preventDefault()
    if (saving) return // jamais une double-soumission
    setSaving(true)
    setFieldErrors({})
    try {
      const res = await aoApi.affaires.create(buildPayload(form))
      const affaire = res.data // réponse axios BRUTE — le créé vit dans .data
      toast.success('Affaire créée.')
      navigate(`/ao/affaires/${affaire.id}`)
    } catch (err) {
      const { message, fieldErrors: fe } = getApiError(err, 'Création impossible.')
      setFieldErrors(fe || {})
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Nouvelle affaire"
        subtitle="Appel d'offres public/privé — l'objet suffit pour créer le dossier, tout le reste se complète plus tard."
      />

      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Identification</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label htmlFor="ao-objet" required>Objet</Label>
              <Input
                id="ao-objet"
                value={form.objet}
                onChange={set('objet')}
                placeholder="Centrale solaire — toiture école…"
                invalid={!!fieldErrors.objet}
              />
              <FieldError message={fieldErrors.objet} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-acheteur">Acheteur</Label>
              <Input id="ao-acheteur" value={form.acheteur} onChange={set('acheteur')} invalid={!!fieldErrors.acheteur} />
              <FieldError message={fieldErrors.acheteur} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-reference-acheteur">Référence du marché (acheteur)</Label>
              <Input
                id="ao-reference-acheteur" value={form.reference_acheteur} onChange={set('reference_acheteur')}
                invalid={!!fieldErrors.reference_acheteur}
              />
              <FieldError message={fieldErrors.reference_acheteur} />
            </div>
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label htmlFor="ao-reference">Référence interne (facultative)</Label>
              <Input
                id="ao-reference" value={form.reference} onChange={set('reference')}
                placeholder="AO-2026-08-0001" invalid={!!fieldErrors.reference}
              />
              <p className="text-xs text-muted-foreground">
                Laissez vide : générée automatiquement (AO-AAAAMM-0001).
              </p>
              <FieldError message={fieldErrors.reference} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Marché</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-type-marche">Type de marché</Label>
              <Select value={form.type_marche} onValueChange={(v) => setValue('type_marche', v)}>
                <SelectTrigger id="ao-type-marche"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TYPE_MARCHE.map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FieldError message={fieldErrors.type_marche} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-mode-passation">Mode de passation</Label>
              <Select value={form.mode_passation} onValueChange={(v) => setValue('mode_passation', v)}>
                <SelectTrigger id="ao-mode-passation"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {MODE_PASSATION.map((m) => (
                    <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FieldError message={fieldErrors.mode_passation} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-lot">Lot</Label>
              <Input id="ao-lot" value={form.lot} onChange={set('lot')} invalid={!!fieldErrors.lot} />
              <FieldError message={fieldErrors.lot} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-reference-cps">Référence du CPS</Label>
              <Input
                id="ao-reference-cps" value={form.reference_cps} onChange={set('reference_cps')}
                invalid={!!fieldErrors.reference_cps}
              />
              <FieldError message={fieldErrors.reference_cps} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Calendrier</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-date-limite">Date limite de remise des plis</Label>
              <Input
                id="ao-date-limite" type="date" value={form.date_limite} onChange={set('date_limite')}
                invalid={!!fieldErrors.date_limite}
              />
              <FieldError message={fieldErrors.date_limite} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-date-ouverture">Date d'ouverture des plis</Label>
              <Input
                id="ao-date-ouverture" type="date" value={form.date_ouverture_plis} onChange={set('date_ouverture_plis')}
                invalid={!!fieldErrors.date_ouverture_plis}
              />
              <FieldError message={fieldErrors.date_ouverture_plis} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-validite-offre">Validité de l'offre (jours)</Label>
              <Input
                id="ao-validite-offre" type="number" step="any"
                value={form.validite_offre_jours} onChange={set('validite_offre_jours')}
                invalid={!!fieldErrors.validite_offre_jours}
              />
              <p className="text-xs text-muted-foreground">75 jours par défaut si laissé vide.</p>
              <FieldError message={fieldErrors.validite_offre_jours} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-delai-execution">Délai d'exécution (jours)</Label>
              <Input
                id="ao-delai-execution" type="number" step="any"
                value={form.delai_execution_jours} onChange={set('delai_execution_jours')}
                invalid={!!fieldErrors.delai_execution_jours}
              />
              <FieldError message={fieldErrors.delai_execution_jours} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Montants</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-montant-estime">Montant estimé (MAD)</Label>
              <Input
                id="ao-montant-estime" type="number" step="any"
                value={form.montant_estime} onChange={set('montant_estime')}
                invalid={!!fieldErrors.montant_estime}
              />
              <FieldError message={fieldErrors.montant_estime} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-caution-provisoire">Caution provisoire (MAD)</Label>
              <Input
                id="ao-caution-provisoire" type="number" step="any"
                value={form.caution_provisoire} onChange={set('caution_provisoire')}
                invalid={!!fieldErrors.caution_provisoire}
              />
              <FieldError message={fieldErrors.caution_provisoire} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Site</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ao-site-adresse">Adresse du site</Label>
              <Textarea
                id="ao-site-adresse" rows={2} value={form.site_adresse} onChange={set('site_adresse')}
                invalid={!!fieldErrors.site_adresse}
              />
              <FieldError message={fieldErrors.site_adresse} />
            </div>
          </CardContent>
        </Card>

        <div className="flex items-center justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => navigate('/ao/affaires')}>
            Annuler
          </Button>
          <Button type="submit" disabled={saving || !form.objet.trim()}>
            {saving ? 'Création…' : "Créer l'affaire"}
          </Button>
        </div>
      </form>
    </div>
  )
}
