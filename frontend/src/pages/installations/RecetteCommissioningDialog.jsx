import { useEffect, useState } from 'react'
import installationsApi from '../../api/installationsApi'
import { frenchError } from '../../lib/frenchError'
import {
  Button, Input, Label, Textarea, Badge,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

/* ============================================================================
   WIR202/CH3 — Saisie de la fiche de recette IEC 62446-1.

   Le bouton « Ouvrir la fiche de recette » CRÉAIT un enregistrement VIDE et
   c'était tout : aucun écran ne permettait de le remplir, donc `resultat`
   restait `en_cours` et le gate « Mise en service » ne se franchissait
   JAMAIS. Ce dialog est le formulaire manquant.

   Les 4 sections reprennent exactement le sérialiseur serveur
   (`CommissioningRecordSerializer`) : documentaire, visuel, électrique,
   sécurité — plus les relevés I-V par string via l'action `ajouter-iv`.
   Les booléens sont TERNAIRES côté serveur (null = non contrôlé) : on ne
   force jamais un « non » là où le technicien n'a rien dit.
   ========================================================================== */

// source-choix: installations.CommissioningRecord.Resultat
const RESULTATS = [
  { value: 'en_cours', label: 'En cours' },
  { value: 'conforme', label: 'Conforme' },
  { value: 'reserves', label: 'Conforme avec réserves' },
  { value: 'non_conforme', label: 'Non conforme' },
]

// Les cases à cocher du serveur sont ternaires (true / false / null).
const TERNAIRE = [
  { value: 'null', label: 'Non contrôlé' },
  { value: 'true', label: 'Conforme' },
  { value: 'false', label: 'Non conforme' },
]

const CONTROLES = {
  documentaire: [
    ['doc_dossier_ok', 'Dossier technique fourni'],
    ['doc_schema_ok', 'Schéma unifilaire à jour'],
    ['doc_datasheets_ok', 'Fiches techniques des équipements'],
  ],
  visuel: [
    ['visuel_structure_ok', 'Structure et fixations'],
    ['visuel_cablage_ok', 'Cheminement et câblage'],
    ['visuel_terre_ok', 'Mise à la terre visible'],
  ],
  securite: [
    ['securite_coupure_ok', 'Organes de coupure accessibles'],
    ['securite_signalisation_ok', 'Signalisation et étiquetage'],
  ],
}

const versApi = (v) => (v === 'null' ? null : v === 'true')
const versUi = (v) => (v === null || v === undefined ? 'null' : String(!!v))

function ControleTernaire({ champ, libelle, valeur, onChange }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 py-1">
      <Label htmlFor={`rec-${champ}`} className="text-sm font-normal">{libelle}</Label>
      <Select value={valeur} onValueChange={(v) => onChange(champ, v)}>
        <SelectTrigger id={`rec-${champ}`} className="w-[11rem]"><SelectValue /></SelectTrigger>
        <SelectContent>
          {TERNAIRE.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  )
}

export default function RecetteCommissioningDialog({ recordId, onClose, onSaved }) {
  const [record, setRecord] = useState(null)
  const [form, setForm] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // Relevé I-V en cours de saisie (ajouté un par un via `ajouter-iv`).
  const [iv, setIv] = useState({
    string_label: '', n_modules_serie: '', voc_mesure_v: '', isc_mesure_a: '',
    pmax_mesure_w: '', voc_attendu_v: '', isc_attendu_a: '', pmax_attendu_w: '',
    observations: '',
  })
  const [ivBusy, setIvBusy] = useState(false)

  useEffect(() => {
    let vivant = true
    installationsApi.getRecetteRecord(recordId)
      .then((res) => {
        if (!vivant) return
        const d = res.data ?? {}
        setRecord(d)
        setForm({
          date_essai: d.date_essai ?? '',
          technicien: d.technicien ?? '',
          doc_dossier_ok: versUi(d.doc_dossier_ok),
          doc_schema_ok: versUi(d.doc_schema_ok),
          doc_datasheets_ok: versUi(d.doc_datasheets_ok),
          visuel_structure_ok: versUi(d.visuel_structure_ok),
          visuel_cablage_ok: versUi(d.visuel_cablage_ok),
          visuel_terre_ok: versUi(d.visuel_terre_ok),
          continuite_terre_ok: versUi(d.continuite_terre_ok),
          continuite_terre_ohm: d.continuite_terre_ohm ?? '',
          polarite_ok: versUi(d.polarite_ok),
          isolement_mohm: d.isolement_mohm ?? '',
          isolement_ok: versUi(d.isolement_ok),
          production_test_kw: d.production_test_kw ?? '',
          production_attendue_kw: d.production_attendue_kw ?? '',
          performance_ok: versUi(d.performance_ok),
          securite_coupure_ok: versUi(d.securite_coupure_ok),
          securite_signalisation_ok: versUi(d.securite_signalisation_ok),
          resultat: d.resultat ?? 'en_cours',
          observations: d.observations ?? '',
        })
      })
      .catch((err) => {
        if (vivant) setError(frenchError(err, 'Chargement de la fiche impossible.'))
      })
    return () => { vivant = false }
  }, [recordId])

  const set = (champ, valeur) => setForm(f => ({ ...f, [champ]: valeur }))

  // Un champ numérique vide doit partir en `null` (le DecimalField DRF
  // refuse la chaîne vide), jamais en '' ni en 0 inventé.
  const nombre = (v) => (v === '' || v === null || v === undefined ? null : v)

  async function enregistrer(e) {
    e.preventDefault()
    if (busy) return
    setBusy(true); setError(null)
    try {
      const res = await installationsApi.updateRecette(recordId, {
        date_essai: form.date_essai || null,
        technicien: form.technicien || '',
        doc_dossier_ok: versApi(form.doc_dossier_ok),
        doc_schema_ok: versApi(form.doc_schema_ok),
        doc_datasheets_ok: versApi(form.doc_datasheets_ok),
        visuel_structure_ok: versApi(form.visuel_structure_ok),
        visuel_cablage_ok: versApi(form.visuel_cablage_ok),
        visuel_terre_ok: versApi(form.visuel_terre_ok),
        continuite_terre_ok: versApi(form.continuite_terre_ok),
        continuite_terre_ohm: nombre(form.continuite_terre_ohm),
        polarite_ok: versApi(form.polarite_ok),
        isolement_mohm: nombre(form.isolement_mohm),
        isolement_ok: versApi(form.isolement_ok),
        production_test_kw: nombre(form.production_test_kw),
        production_attendue_kw: nombre(form.production_attendue_kw),
        performance_ok: versApi(form.performance_ok),
        securite_coupure_ok: versApi(form.securite_coupure_ok),
        securite_signalisation_ok: versApi(form.securite_signalisation_ok),
        resultat: form.resultat,
        observations: form.observations || '',
      })
      setRecord(res.data)
      onSaved?.(res.data)
    } catch (err) {
      setError(frenchError(err, "L'enregistrement de la fiche a échoué."))
    } finally { setBusy(false) }
  }

  async function ajouterIv() {
    if (ivBusy) return
    if (!iv.string_label.trim()) { setError('Le repère du string est requis.'); return }
    setIvBusy(true); setError(null)
    try {
      await installationsApi.ajouterReleveIv(recordId, {
        string_label: iv.string_label.trim(),
        n_modules_serie: nombre(iv.n_modules_serie),
        voc_mesure_v: nombre(iv.voc_mesure_v),
        isc_mesure_a: nombre(iv.isc_mesure_a),
        pmax_mesure_w: nombre(iv.pmax_mesure_w),
        voc_attendu_v: nombre(iv.voc_attendu_v),
        isc_attendu_a: nombre(iv.isc_attendu_a),
        pmax_attendu_w: nombre(iv.pmax_attendu_w),
        observations: iv.observations || '',
      })
      // On repart du serveur : l'écart et le drapeau de défaut sont CALCULÉS
      // côté serveur (read_only) — jamais recalculés ici.
      const frais = await installationsApi.getRecetteRecord(recordId)
      setRecord(frais.data)
      setIv({
        string_label: '', n_modules_serie: '', voc_mesure_v: '', isc_mesure_a: '',
        pmax_mesure_w: '', voc_attendu_v: '', isc_attendu_a: '', pmax_attendu_w: '',
        observations: '',
      })
    } catch (err) {
      setError(frenchError(err, "L'ajout du relevé I-V a échoué."))
    } finally { setIvBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            Fiche de recette IEC 62446-1
            {record && (
              <Badge tone={record.passe ? 'success' : 'outline'}>
                {record.resultat_display ?? record.resultat}
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            Contrôles documentaires, visuels, électriques et de sécurité. Le
            résultat « Conforme » (ou « Conforme avec réserves ») est ce qui
            franchit le gate de mise en service.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {!record ? (
          <p className="text-sm text-muted-foreground">Chargement de la fiche…</p>
        ) : (
          <form onSubmit={enregistrer} noValidate className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="rec-date">Date de l'essai</Label>
                <Input id="rec-date" type="date" value={form.date_essai}
                       onChange={(e) => set('date_essai', e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="rec-technicien">Technicien</Label>
                <Input id="rec-technicien" value={form.technicien}
                       onChange={(e) => set('technicien', e.target.value)} />
              </div>
            </div>

            <section>
              <h4 className="mb-1 text-sm font-semibold">1. Contrôle documentaire</h4>
              {CONTROLES.documentaire.map(([champ, libelle]) => (
                <ControleTernaire key={champ} champ={champ} libelle={libelle}
                                  valeur={form[champ]} onChange={set} />
              ))}
            </section>

            <section>
              <h4 className="mb-1 text-sm font-semibold">2. Contrôle visuel</h4>
              {CONTROLES.visuel.map(([champ, libelle]) => (
                <ControleTernaire key={champ} champ={champ} libelle={libelle}
                                  valeur={form[champ]} onChange={set} />
              ))}
            </section>

            <section>
              <h4 className="mb-1 text-sm font-semibold">3. Essais électriques</h4>
              <ControleTernaire champ="continuite_terre_ok" libelle="Continuité de terre"
                                valeur={form.continuite_terre_ok} onChange={set} />
              <div className="grid gap-1.5 py-1">
                <Label htmlFor="rec-terre-ohm">Continuité de terre mesurée (Ω)</Label>
                {/* step="any" : aucune valeur saisie n'est snappée ni refusée. */}
                <Input id="rec-terre-ohm" type="number" step="any"
                       value={form.continuite_terre_ohm}
                       onChange={(e) => set('continuite_terre_ohm', e.target.value)} />
              </div>
              <ControleTernaire champ="polarite_ok" libelle="Polarité des strings"
                                valeur={form.polarite_ok} onChange={set} />
              <ControleTernaire champ="isolement_ok" libelle="Résistance d'isolement"
                                valeur={form.isolement_ok} onChange={set} />
              <div className="grid gap-1.5 py-1">
                <Label htmlFor="rec-isolement">Isolement mesuré (MΩ)</Label>
                <Input id="rec-isolement" type="number" step="any"
                       value={form.isolement_mohm}
                       onChange={(e) => set('isolement_mohm', e.target.value)} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label htmlFor="rec-prod-test">Production mesurée (kW)</Label>
                  <Input id="rec-prod-test" type="number" step="any"
                         value={form.production_test_kw}
                         onChange={(e) => set('production_test_kw', e.target.value)} />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="rec-prod-attendue">Production attendue (kW)</Label>
                  <Input id="rec-prod-attendue" type="number" step="any"
                         value={form.production_attendue_kw}
                         onChange={(e) => set('production_attendue_kw', e.target.value)} />
                </div>
              </div>
              <ControleTernaire champ="performance_ok" libelle="Performance conforme"
                                valeur={form.performance_ok} onChange={set} />
            </section>

            <section>
              <h4 className="mb-1 text-sm font-semibold">4. Sécurité</h4>
              {CONTROLES.securite.map(([champ, libelle]) => (
                <ControleTernaire key={champ} champ={champ} libelle={libelle}
                                  valeur={form[champ]} onChange={set} />
              ))}
            </section>

            <div className="grid gap-1.5">
              <Label htmlFor="rec-resultat">Résultat</Label>
              <Select value={form.resultat} onValueChange={(v) => set('resultat', v)}>
                <SelectTrigger id="rec-resultat"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {RESULTATS.map(r => (
                    <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="rec-observations">Observations</Label>
              <Textarea id="rec-observations" rows={3} value={form.observations}
                        onChange={(e) => set('observations', e.target.value)} />
            </div>

            <DialogFooter>
              <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>
                Fermer
              </Button>
              <Button type="submit" loading={busy}>
                {busy ? 'Enregistrement…' : 'Enregistrer la fiche'}
              </Button>
            </DialogFooter>
          </form>
        )}

        {/* ── Relevés I-V par string (action serveur `ajouter-iv`) ── */}
        {record && (
          <section className="mt-2 border-t border-border pt-3">
            <h4 className="mb-2 text-sm font-semibold">Relevés I-V par string</h4>
            {(record.iv_readings ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun relevé pour l'instant.</p>
            ) : (
              <ul className="mb-3 divide-y divide-border rounded-md border border-border text-sm">
                {record.iv_readings.map((r) => (
                  <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                    <span className="font-medium">{r.string_label}</span>
                    <span className="text-muted-foreground">
                      Voc {r.voc_mesure_v ?? '—'} V · Isc {r.isc_mesure_a ?? '—'} A
                      {' · '}Pmax {r.pmax_mesure_w ?? '—'} W
                    </span>
                    {/* Écart et défaut sont CALCULÉS côté serveur. */}
                    {r.ecart_pmax_pct != null && (
                      <Badge tone={r.defaut_detecte ? 'danger' : 'success'}>
                        écart {r.ecart_pmax_pct} %
                      </Badge>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="iv-label" required>Repère du string</Label>
                <Input id="iv-label" value={iv.string_label}
                       onChange={(e) => setIv(s => ({ ...s, string_label: e.target.value }))}
                       placeholder="ex : S1" />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="iv-modules">Modules en série</Label>
                <Input id="iv-modules" type="number" step="any" value={iv.n_modules_serie}
                       onChange={(e) => setIv(s => ({ ...s, n_modules_serie: e.target.value }))} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="iv-voc">Voc mesurée (V)</Label>
                <Input id="iv-voc" type="number" step="any" value={iv.voc_mesure_v}
                       onChange={(e) => setIv(s => ({ ...s, voc_mesure_v: e.target.value }))} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="iv-isc">Isc mesurée (A)</Label>
                <Input id="iv-isc" type="number" step="any" value={iv.isc_mesure_a}
                       onChange={(e) => setIv(s => ({ ...s, isc_mesure_a: e.target.value }))} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="iv-pmax">Pmax mesurée (W)</Label>
                <Input id="iv-pmax" type="number" step="any" value={iv.pmax_mesure_w}
                       onChange={(e) => setIv(s => ({ ...s, pmax_mesure_w: e.target.value }))} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="iv-pmax-attendu">Pmax attendue (W)</Label>
                <Input id="iv-pmax-attendu" type="number" step="any" value={iv.pmax_attendu_w}
                       onChange={(e) => setIv(s => ({ ...s, pmax_attendu_w: e.target.value }))} />
              </div>
            </div>
            <Button type="button" variant="outline" size="sm" className="mt-2"
                    onClick={ajouterIv} disabled={ivBusy}>
              {ivBusy ? 'Ajout…' : 'Ajouter le relevé'}
            </Button>
          </section>
        )}
      </DialogContent>
    </Dialog>
  )
}
