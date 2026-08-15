// WR5 — Onglet « Données » de la page Paramètres (admin / INTERNE).
// Regroupe des opérations stock avancées jusque-là sans écran :
//   • sessions d'inventaire physique (brouillon → valider / annuler) ;
//   • explosion d'un kit (nomenclature) en lignes composant ;
//   • fiches techniques (datasheets) rattachées à un produit ;
//   • rappel vers la page « Export / Sauvegarde » (déjà existante).
// Section autonome : charge ses propres données et s'enregistre seule.
// Prix d'achat/marges jamais exposés ici (données de vente uniquement pour
// l'explosion de kit — client-facing OK).
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ClipboardCheck, FileText, Archive, Plus, Trash2, ExternalLink, Pencil, X,
} from 'lucide-react'
import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import {
  Card, CardContent, Button, IconButton, Badge, Spinner, EmptyState,
  Input, Label, Checkbox, FileUpload,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle } from './peComponents'

const INV_STATUT = {
  brouillon: { label: 'Brouillon', tone: 'warning' },
  valide: { label: 'Validé', tone: 'success' },
  annule: { label: 'Annulé', tone: 'muted' },
}

const fmtDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

// Message FR d'une erreur serveur (jamais de JSON brut).
function frErr(err, fallback = 'Une erreur est survenue. Réessayez.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  for (const v of Object.values(data)) {
    const m = Array.isArray(v) ? v[0] : v
    if (typeof m === 'string') return m
  }
  return fallback
}

// ── Sessions d'inventaire (FG63) ─────────────────────────────────────────────
function InventaireSessions() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    stockApi.getInventaireSessions({ ordering: '-date_creation' })
      .then((r) => setSessions(r.data?.results ?? r.data ?? []))
      .catch((e) => setError(e?.response?.status === 403
        ? 'Réservé à l\'administrateur.'
        : 'Chargement des sessions impossible.'))
      .finally(() => setLoading(false))
  }
  // `loading` démarre à true ; load() ne setState que dans ses callbacks async.
  useEffect(() => { load() }, [])

  const valider = async (s) => {
    setBusyId(s.id); setError(null); setInfo(null)
    try {
      const r = await stockApi.validerInventaireSession(s.id)
      const d = r.data ?? {}
      setInfo(`Session ${s.reference} validée : ${d.ajustes ?? 0} ajustement(s), ${d.inchanges ?? 0} inchangé(s).`)
      load()
    } catch (e) {
      setError(frErr(e, 'La validation de la session a échoué.'))
    } finally { setBusyId(null) }
  }

  const annuler = async (s) => {
    if (!window.confirm(`Annuler la session ${s.reference} ?`)) return
    setBusyId(s.id); setError(null); setInfo(null)
    try {
      await stockApi.annulerInventaireSession(s.id)
      setInfo(`Session ${s.reference} annulée.`)
      load()
    } catch (e) {
      setError(frErr(e, "L'annulation de la session a échoué."))
    } finally { setBusyId(null) }
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Sessions d'inventaire"
          icon={<><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></>} />
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Comptages physiques du stock. La validation d&apos;une session émet les
          ajustements de stock pour chaque écart ; l&apos;annulation n&apos;est
          possible que sur un brouillon. Donnée interne.
        </p>

        {error && (
          <div role="alert" className="mb-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">{error}</div>
        )}
        {info && (
          <div role="status" className="mb-2 rounded-lg border border-success/30 bg-success/10 p-2 text-sm text-success">{info}</div>
        )}

        {loading ? (
          <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
        ) : sessions.length === 0 ? (
          <EmptyState icon={ClipboardCheck} title="Aucune session d'inventaire"
                      description="Les sessions de comptage physique apparaîtront ici." />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[32rem] text-sm">
              <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">Référence</th>
                  <th className="px-3 py-2 text-left font-semibold">Statut</th>
                  <th className="px-3 py-2 text-left font-semibold">Lignes</th>
                  <th className="px-3 py-2 text-left font-semibold">Créée le</th>
                  <th className="px-3 py-2 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => {
                  const meta = INV_STATUT[s.statut] ?? INV_STATUT.brouillon
                  const isBrouillon = s.statut === 'brouillon'
                  return (
                    <tr key={s.id} className="border-t border-border">
                      <td className="px-3 py-2 font-mono text-xs">{s.reference}</td>
                      <td className="px-3 py-2"><Badge tone={meta.tone}>{meta.label}</Badge></td>
                      <td className="px-3 py-2 tabular-nums">{(s.lignes ?? []).length}</td>
                      <td className="px-3 py-2">{fmtDateFR(s.date_creation)}</td>
                      <td className="px-3 py-2">
                        <div className="flex items-center justify-end gap-1">
                          {isBrouillon && (
                            <>
                              <Button type="button" size="sm" variant="success"
                                      loading={busyId === s.id} onClick={() => valider(s)}>
                                Valider
                              </Button>
                              <Button type="button" size="sm" variant="outline"
                                      loading={busyId === s.id} onClick={() => annuler(s)}>
                                Annuler
                              </Button>
                            </>
                          )}
                          {!isBrouillon && <span className="text-xs text-muted-foreground">—</span>}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ── Explosion d'un kit (FG66 / DC36) ─────────────────────────────────────────
function KitExplosion() {
  const [kits, setKits] = useState([])
  const [kitId, setKitId] = useState('')
  const [quantite, setQuantite] = useState('1')
  const [result, setResult] = useState(null)
  // ZMFG9 — disponibilité multi-niveaux (kits assemblables + goulots).
  const [dispo, setDispo] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // XMFG18 / WIR268 — duplication avec facteur d'échelle + historique des
  // révisions de nomenclature + « composition au JJ/MM/AAAA ».
  const [facteur, setFacteur] = useState('')
  const [revisions, setRevisions] = useState(null)
  const [dateComposition, setDateComposition] = useState('')
  const [compositionAu, setCompositionAu] = useState(null)
  const [info, setInfo] = useState(null)

  const chargerKits = () => {
    stockApi.getKits({ page_size: 500 })
      .then((r) => setKits(r.data?.results ?? r.data ?? []))
      .catch(() => {})
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { chargerKits() }, [])

  const dupliquer = async () => {
    if (!kitId) { setError('Choisissez un kit.'); return }
    setBusy(true); setError(null); setInfo(null)
    try {
      const r = await stockApi.dupliquerKit(kitId, facteur || undefined)
      setInfo(`Kit dupliqué : ${r.data?.nom ?? ''}${facteur ? ` (quantités × ${facteur})` : ''}.`)
      chargerKits()
    } catch (e) {
      setError(frErr(e, 'La duplication du kit a échoué.'))
    } finally { setBusy(false) }
  }

  const voirRevisions = async () => {
    if (!kitId) { setError('Choisissez un kit.'); return }
    setBusy(true); setError(null)
    try {
      const r = await stockApi.getKitRevisions(kitId)
      setRevisions(r.data ?? [])
    } catch (e) {
      setError(frErr(e, 'Historique des révisions indisponible.'))
    } finally { setBusy(false) }
  }

  const voirCompositionAu = async () => {
    if (!kitId) { setError('Choisissez un kit.'); return }
    if (!dateComposition) { setError('Saisissez une date.'); return }
    setBusy(true); setError(null); setCompositionAu(null)
    try {
      const r = await stockApi.getKitCompositionAu(kitId, dateComposition)
      setCompositionAu(r.data ?? null)
    } catch (e) {
      setError(frErr(e, 'Aucune révision en vigueur à cette date.'))
    } finally { setBusy(false) }
  }

  const exploser = async () => {
    if (!kitId) { setError('Choisissez un kit.'); return }
    setBusy(true); setError(null); setDispo(null)
    try {
      const q = Number(quantite) > 0 ? Number(quantite) : 1
      const r = await stockApi.exploserKit(kitId, q)
      setResult(r.data)
      // ZMFG9 — best-effort : la disponibilité récursive accompagne
      // l'explosion (jamais bloquante pour l'affichage des lignes).
      try {
        const d = await stockApi.getKitDisponibilite(kitId)
        setDispo(d.data)
      } catch { /* fiche sans disponibilité si le calcul échoue */ }
    } catch (e) {
      setError(frErr(e, "L'explosion du kit a échoué."))
    } finally { setBusy(false) }
  }

  const lignes = result?.lignes ?? []

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Explosion de kit (nomenclature)"
          icon={<><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /></>} />
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Décompose un kit en ses lignes composant (prix de vente / TVA / marque
          lus sur chaque produit). Le prix d&apos;achat n&apos;est jamais exposé.
        </p>

        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-48 flex-1">
            <Select value={kitId || '__none'} onValueChange={(v) => setKitId(v === '__none' ? '' : v)}>
              <SelectTrigger><SelectValue placeholder="— Choisir un kit —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Choisir un kit —</SelectItem>
                {kits.map((k) => (
                  <SelectItem key={k.id} value={String(k.id)}>
                    {k.nom}{k.sku ? ` (${k.sku})` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-28">
            <Input type="number" min="1" step="any" inputMode="decimal"
                   placeholder="Quantité" value={quantite}
                   onChange={(e) => setQuantite(e.target.value)} />
          </div>
          <Button type="button" loading={busy} onClick={exploser}>Exploser</Button>
        </div>

        {/* XMFG18 / WIR268 — dupliquer (facteur d'échelle) + traçabilité de la
            nomenclature : ces trois routes existaient sans aucun bouton. */}
        <div className="mt-3 flex flex-wrap items-end gap-2 rounded-lg border border-border p-2">
          <div className="w-36">
            <label className="mb-1 block text-[11.5px] font-medium" htmlFor="kit-facteur">
              Facteur d&apos;échelle
            </label>
            <Input id="kit-facteur" type="number" step="any" inputMode="decimal"
                   placeholder="ex. 1.67" value={facteur}
                   onChange={(e) => setFacteur(e.target.value)} />
          </div>
          <Button type="button" variant="outline" loading={busy} onClick={dupliquer}>
            Dupliquer le kit
          </Button>
          <Button type="button" variant="outline" loading={busy} onClick={voirRevisions}>
            Historique des révisions
          </Button>
          <div className="w-40">
            <label className="mb-1 block text-[11.5px] font-medium" htmlFor="kit-date-compo">
              Composition au
            </label>
            <Input id="kit-date-compo" type="date" value={dateComposition}
                   onChange={(e) => setDateComposition(e.target.value)} />
          </div>
          <Button type="button" variant="outline" loading={busy} onClick={voirCompositionAu}>
            Voir la composition
          </Button>
        </div>

        {error && (
          <div role="alert" className="mt-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">{error}</div>
        )}
        {info && (
          <div className="mt-2 rounded-lg border border-success/30 bg-success/10 p-2 text-sm text-success">{info}</div>
        )}
        {revisions && (
          revisions.length === 0
            ? <p className="mt-2 text-sm text-muted-foreground">Aucune révision enregistrée.</p>
            : (
              <ul className="mt-2 flex flex-col gap-1 text-sm">
                {revisions.map((rev) => (
                  <li key={rev.id ?? rev.numero} className="flex justify-between gap-3 border-b border-border py-1">
                    <span>Révision n° {rev.numero}</span>
                    <span className="text-muted-foreground">
                      {rev.user_username ?? rev.user ?? '—'} · {rev.date_creation ?? rev.date ?? '—'}
                    </span>
                  </li>
                ))}
              </ul>
            )
        )}
        {compositionAu && (
          <div className="mt-2 rounded-lg border border-border bg-muted/40 p-2 text-sm">
            Composition en vigueur : révision n° {compositionAu.numero ?? '—'}
            {' '}({(compositionAu.snapshot?.composants ?? compositionAu.composants ?? []).length} composant(s)).
          </div>
        )}

        {dispo && (
          <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-border bg-muted/40 p-2 text-sm">
            <Badge tone={dispo.kits_assemblables > 0 ? 'success' : 'warning'}>
              {dispo.kits_assemblables} kit{dispo.kits_assemblables > 1 ? 's' : ''} assemblable{dispo.kits_assemblables > 1 ? 's' : ''}
            </Badge>
            {(dispo.goulots ?? []).length > 0 && (
              <span className="text-muted-foreground">
                Goulot{dispo.goulots.length > 1 ? 's' : ''} :{' '}
                {dispo.goulots.map((g) => g.designation).join(', ')}
              </span>
            )}
          </div>
        )}

        {result && (
          lignes.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">Ce kit n&apos;a aucun composant.</p>
          ) : (
            <div className="mt-3 overflow-x-auto rounded-lg border border-border">
              <table className="w-full min-w-[30rem] text-sm">
                <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold">Composant</th>
                    <th className="px-3 py-2 text-left font-semibold">SKU</th>
                    <th className="px-3 py-2 text-right font-semibold">Quantité</th>
                    <th className="px-3 py-2 text-right font-semibold">Prix vente U.</th>
                    <th className="px-3 py-2 text-right font-semibold">Dispo</th>
                  </tr>
                </thead>
                <tbody>
                  {lignes.map((l) => (
                    <tr key={l.produit_id} className="border-t border-border">
                      <td className="px-3 py-2">{l.designation}</td>
                      <td className="px-3 py-2 font-mono text-xs">{l.sku || '—'}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{l.quantite}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatMAD(l.prix_vente_unitaire, { withSymbol: false })} DH</td>
                      <td className="px-3 py-2 text-right tabular-nums">{l.disponible}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </CardContent>
    </Card>
  )
}

// ── Fiches techniques (DC35 / FG254 / PV7) ───────────────────────────────────
// PV5 (backend) porte 3 blocs de champs supplémentaires selon `type_fiche` —
// les 6 champs électriques historiques restent le socle « module »/« autre ».
const CHAMPS_FICHE = [
  ['pmax_wc', 'Pmax (Wc)'], ['voc_v', 'Voc (V)'], ['isc_a', 'Isc (A)'],
  ['vmp_v', 'Vmp (V)'], ['imp_a', 'Imp (A)'], ['rendement_pct', 'Rendement (%)'],
]
const CHAMPS_MODULE_NUM = [
  ['longueur_mm', 'Longueur (mm)'], ['largeur_mm', 'Largeur (mm)'],
  ['epaisseur_mm', 'Épaisseur (mm)'], ['poids_kg', 'Poids (kg)'],
  ['temp_coeff_voc_pct_c', 'Coeff. temp. Voc (%/°C)'],
  ['temp_coeff_pmax_pct_c', 'Coeff. temp. Pmax (%/°C)'],
]
const CHAMPS_ONDULEUR_NUM = [
  ['ond_n_mppt', 'Nombre de MPPT'],
  ['ond_mppt_v_min', 'Tension MPPT min (V)'],
  ['ond_mppt_v_max', 'Tension MPPT max (V)'],
  ['ond_v_max_abs', 'Tension DC max absolue (V)'],
  ['ond_i_max_mppt_a', 'Courant max par MPPT (A)'],
  ['ond_ac_kw', 'Puissance AC nominale (kW)'],
  ['ond_rendement_euro_pct', 'Rendement européen (%)'],
]
const CHAMPS_BATTERIE_NUM = [
  ['bat_kwh_nominal', 'Capacité nominale (kWh)'],
  ['bat_kwh_usable', 'Capacité utilisable (kWh)'],
  ['bat_dod_pct', 'Profondeur de décharge (%)'],
  ['bat_v_nominal', 'Tension nominale (V)'],
  ['bat_max_charge_kw', 'Puissance de charge max (kW)'],
]
const TYPE_FICHE_OPTIONS = [
  ['module', 'Module (panneau)'], ['onduleur', 'Onduleur'],
  ['batterie', 'Batterie'], ['autre', 'Autre'],
]
const TYPE_FICHE_LABELS = Object.fromEntries(TYPE_FICHE_OPTIONS)

// Champs numériques actifs pour un type donné (le bloc « module »/« autre »
// englobe le socle historique — onduleur/batterie sont des blocs dédiés).
function champsNumeriquesPour(type) {
  if (type === 'module') return [...CHAMPS_FICHE, ...CHAMPS_MODULE_NUM]
  if (type === 'onduleur') return CHAMPS_ONDULEUR_NUM
  if (type === 'batterie') return CHAMPS_BATTERIE_NUM
  return CHAMPS_FICHE
}

function FichesTechniques() {
  const [produits, setProduits] = useState([])
  const [fiches, setFiches] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [pdfActuelUrl, setPdfActuelUrl] = useState(null)
  const [produitId, setProduitId] = useState('')
  const [typeFiche, setTypeFiche] = useState('')
  const [vals, setVals] = useState({})
  const [pdfFile, setPdfFile] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = () => {
    stockApi.getFichesTechniques()
      .then((r) => setFiches(r.data?.results ?? r.data ?? []))
      .catch(() => setError('Chargement des fiches impossible.'))
      .finally(() => setLoading(false))
  }
  // `loading` démarre à true ; les setState n'arrivent que dans les callbacks
  // asynchrones (jamais synchrone dans l'effet).
  useEffect(() => {
    load()
    stockApi.getProduits({ page_size: 1000 })
      .then((r) => setProduits(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  // Produits sans fiche (une fiche par produit, OneToOne) — sauf la fiche en
  // cours d'édition, dont le produit doit rester sélectionnable.
  const dispo = useMemo(() => {
    const used = new Set(
      fiches.filter((f) => f.id !== editingId).map((f) => String(f.produit)),
    )
    return produits.filter((p) => !used.has(String(p.id)))
  }, [produits, fiches, editingId])

  const setVal = (k, v) => setVals((s) => ({ ...s, [k]: v }))

  const resetForm = () => {
    setEditingId(null); setPdfActuelUrl(null)
    setProduitId(''); setTypeFiche(''); setVals({}); setPdfFile(null)
    setError(null)
  }

  const commencerEdition = (f) => {
    setEditingId(f.id); setPdfActuelUrl(f.pdf || null)
    setProduitId(String(f.produit)); setTypeFiche(f.type_fiche || '')
    const v = {}
    for (const [k] of [
      ...CHAMPS_FICHE, ...CHAMPS_MODULE_NUM, ...CHAMPS_ONDULEUR_NUM, ...CHAMPS_BATTERIE_NUM,
    ]) {
      if (f[k] != null) v[k] = String(f[k])
    }
    v.techno_cellule = f.techno_cellule || ''
    v.bifacial = Boolean(f.bifacial)
    if (f.ond_phases != null) v.ond_phases = String(f.ond_phases)
    setVals(v); setPdfFile(null); setError(null)
  }

  const buildPayload = () => {
    const payload = { produit: Number(produitId), type_fiche: typeFiche }
    for (const [k] of champsNumeriquesPour(typeFiche)) {
      if (vals[k] !== undefined && vals[k] !== '') payload[k] = vals[k]
    }
    if (typeFiche === 'module') {
      if (vals.techno_cellule) payload.techno_cellule = vals.techno_cellule
      payload.bifacial = Boolean(vals.bifacial)
    }
    if (typeFiche === 'onduleur' && vals.ond_phases !== undefined && vals.ond_phases !== '') {
      payload.ond_phases = Number(vals.ond_phases)
    }
    return payload
  }

  const enregistrer = async () => {
    if (!produitId) { setError('Choisissez un produit.'); return }
    setBusy(true); setError(null)
    try {
      const payload = buildPayload()
      let id = editingId
      if (editingId) {
        await stockApi.updateFicheTechnique(editingId, payload)
      } else {
        const r = await stockApi.createFicheTechnique(payload)
        id = r.data?.id
      }
      if (pdfFile && id) {
        await stockApi.uploadFicheTechniquePdf(id, pdfFile)
      }
      resetForm()
      load()
    } catch (e) {
      setError(frErr(e, "L'enregistrement de la fiche a échoué."))
    } finally { setBusy(false) }
  }

  const supprimer = async (f) => {
    if (!window.confirm(`Supprimer la fiche de « ${f.produit_nom} » ?`)) return
    setError(null)
    try {
      await stockApi.deleteFicheTechnique(f.id)
      if (editingId === f.id) resetForm()
      load()
    } catch (e) { setError(frErr(e, 'Suppression impossible.')) }
  }

  const champsForm = champsNumeriquesPour(typeFiche)

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Fiches techniques"
          icon={<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></>} />
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Paramètres électriques/dimensionnels (module, onduleur ou batterie)
          et PDF constructeur, rattachés à un produit. Un produit a au plus
          une fiche.
        </p>

        {error && (
          <div role="alert" className="mb-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">{error}</div>
        )}

        {loading ? (
          <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
        ) : fiches.length === 0 ? (
          <EmptyState icon={FileText} title="Aucune fiche technique"
                      description="Ajoutez-en une pour un produit ci-dessous." />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[36rem] text-sm">
              <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">Produit</th>
                  <th className="px-3 py-2 text-left font-semibold">Type</th>
                  <th className="px-3 py-2 text-left font-semibold">PDF</th>
                  <th className="w-20 px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {fiches.map((f) => (
                  <tr key={f.id} className="border-t border-border">
                    <td className="px-3 py-2">{f.produit_nom}</td>
                    <td className="px-3 py-2">
                      <Badge tone="outline">{TYPE_FICHE_LABELS[f.type_fiche] || '—'}</Badge>
                    </td>
                    <td className="px-3 py-2">
                      {f.pdf ? (
                        <a href={f.pdf} target="_blank" rel="noopener noreferrer"
                           className="inline-flex items-center gap-1 text-primary hover:underline">
                          Voir <ExternalLink className="size-3.5" aria-hidden="true" />
                        </a>
                      ) : '—'}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center justify-end gap-1">
                        <IconButton size="md" variant="ghost" label="Modifier la fiche"
                                    onClick={() => commencerEdition(f)}>
                          <Pencil className="size-4" aria-hidden="true" />
                        </IconButton>
                        <IconButton size="md" variant="ghost" label="Supprimer la fiche"
                                    className="text-destructive hover:text-destructive"
                                    onClick={() => supprimer(f)}>
                          <Trash2 className="size-4" aria-hidden="true" />
                        </IconButton>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Ajout / édition d'une fiche */}
        <div className="mt-3 flex flex-col gap-2 rounded-lg border border-border p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold">
              {editingId ? 'Modifier la fiche' : 'Nouvelle fiche'}
            </span>
            {editingId && (
              <Button type="button" size="sm" variant="ghost" onClick={resetForm}>
                <X className="size-4" aria-hidden="true" /> Annuler
              </Button>
            )}
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="min-w-48">
              <Select value={produitId || '__none'} onValueChange={(v) => setProduitId(v === '__none' ? '' : v)}>
                <SelectTrigger aria-label="Produit"><SelectValue placeholder="— Produit —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Produit —</SelectItem>
                  {dispo.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>
                      {p.nom}{p.sku ? ` (${p.sku})` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="min-w-48">
              <Select value={typeFiche || '__none'} onValueChange={(v) => setTypeFiche(v === '__none' ? '' : v)}>
                <SelectTrigger aria-label="Type de fiche"><SelectValue placeholder="— Type de fiche —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Type de fiche —</SelectItem>
                  {TYPE_FICHE_OPTIONS.map(([v, label]) => (
                    <SelectItem key={v} value={v}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-3">
            {champsForm.map(([k, label]) => (
              <Input key={k} type="number" step="any" inputMode="decimal"
                     placeholder={label} value={vals[k] ?? ''}
                     onChange={(e) => setVal(k, e.target.value)} />
            ))}
          </div>

          {typeFiche === 'module' && (
            <div className="grid gap-2 sm:grid-cols-3 sm:items-center">
              <Input placeholder="Technologie de cellule" value={vals.techno_cellule ?? ''}
                     onChange={(e) => setVal('techno_cellule', e.target.value)} />
              <div className="flex items-center gap-2">
                <Checkbox id="fiche-bifacial" checked={Boolean(vals.bifacial)}
                          onCheckedChange={(v) => setVal('bifacial', Boolean(v))}
                          aria-label="Bifacial" />
                <Label htmlFor="fiche-bifacial" className="font-normal">Bifacial</Label>
              </div>
            </div>
          )}

          {typeFiche === 'onduleur' && (
            <div className="min-w-48">
              <Select value={vals.ond_phases || '__none'}
                      onValueChange={(v) => setVal('ond_phases', v === '__none' ? '' : v)}>
                <SelectTrigger aria-label="Phases"><SelectValue placeholder="— Phases —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Phases —</SelectItem>
                  <SelectItem value="1">Monophasé</SelectItem>
                  <SelectItem value="3">Triphasé</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <FileUpload accept="application/pdf" onFiles={(files) => setPdfFile(files[0] || null)}
                        hint="Fiche PDF constructeur (optionnel)" />
            {pdfFile && (
              <p className="text-xs text-muted-foreground">Fichier sélectionné : {pdfFile.name}</p>
            )}
            {!pdfFile && pdfActuelUrl && (
              <a href={pdfActuelUrl} target="_blank" rel="noopener noreferrer"
                 className="inline-flex w-fit items-center gap-1 text-xs text-primary hover:underline">
                Voir le PDF actuel <ExternalLink className="size-3.5" aria-hidden="true" />
              </a>
            )}
          </div>

          <div>
            <Button type="button" loading={busy} onClick={enregistrer}>
              <Plus /> {editingId ? 'Enregistrer les modifications' : 'Ajouter la fiche'}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Remplacement de masse d'un composant (XMFG19) ────────────────────────────
// Dialogue préview (dry_run) → confirmer : remplace un produit par un autre
// dans TOUTES les nomenclatures (kits stock + kits de pré-assemblage), avec
// ratio de quantité optionnel. L'application est atomique côté serveur et
// chaque kit modifié crée sa révision (XMFG18).
function RemplacementComposant() {
  const [produits, setProduits] = useState([])
  const [ancien, setAncien] = useState('')
  const [nouveau, setNouveau] = useState('')
  const [ratio, setRatio] = useState('')
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null)

  useEffect(() => {
    stockApi.getProduits({ page_size: 1000 })
      .then((r) => setProduits(r.data?.results ?? r.data ?? []))
      .catch(() => {})
  }, [])

  const payload = () => ({
    produit_ancien: ancien,
    produit_nouveau: nouveau,
    ...(ratio ? { ratio_quantite: ratio } : {}),
  })

  const previsualiser = async () => {
    if (!ancien || !nouveau) { setError('Choisissez les deux produits.'); return }
    setBusy(true); setError(null); setDone(null)
    try {
      const r = await stockApi.remplacerComposantKits({ ...payload(), dry_run: true })
      setPreview(r.data)
    } catch (e) { setError(frErr(e, 'La préview a échoué.')); setPreview(null) }
    finally { setBusy(false) }
  }

  const confirmer = async () => {
    setBusy(true); setError(null)
    try {
      const r = await stockApi.remplacerComposantKits({ ...payload(), dry_run: false })
      setDone(r.data); setPreview(null)
    } catch (e) { setError(frErr(e, 'Le remplacement a échoué.')) }
    finally { setBusy(false) }
  }

  const lignes = (res) => [
    ...(res?.kits_stock ?? []).map((k) => ({ ...k, module: 'Kit stock' })),
    ...(res?.kits_installations ?? []).map((k) => ({ ...k, module: 'Pré-assemblage' })),
  ]

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Remplacement de composant (nomenclatures)"
          icon={<><path d="M16 3h5v5" /><path d="M8 3H3v5" /><path d="M21 3l-7 7" /><path d="M3 3l7 7" /><path d="M16 21h5v-5" /><path d="M8 21H3v-5" /><path d="M21 21l-7-7" /><path d="M3 21l7-7" /></>} />
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Remplace un produit par un autre dans toutes les nomenclatures
          (kits stock et kits de pré-assemblage). Prévisualisez d&apos;abord les
          kits impactés, puis confirmez : l&apos;application est atomique et
          chaque kit modifié garde une révision de sa composition.
        </p>

        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-48 flex-1">
            <Select value={ancien || '__none'} onValueChange={(v) => { setAncien(v === '__none' ? '' : v); setPreview(null) }}>
              <SelectTrigger><SelectValue placeholder="— Produit remplacé —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Produit remplacé —</SelectItem>
                {produits.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="min-w-48 flex-1">
            <Select value={nouveau || '__none'} onValueChange={(v) => { setNouveau(v === '__none' ? '' : v); setPreview(null) }}>
              <SelectTrigger><SelectValue placeholder="— Produit de remplacement —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Produit de remplacement —</SelectItem>
                {produits.filter((p) => String(p.id) !== ancien).map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-32">
            <Input type="number" step="any" inputMode="decimal" min="0"
                   placeholder="Ratio qté (opt.)" value={ratio}
                   onChange={(e) => { setRatio(e.target.value); setPreview(null) }} />
          </div>
          <Button type="button" loading={busy} variant="outline" onClick={previsualiser}>
            Prévisualiser
          </Button>
        </div>

        {error && (
          <div role="alert" className="mt-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">{error}</div>
        )}

        {preview && (
          lignes(preview).length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">
              Aucune nomenclature n&apos;utilise ce produit.
            </p>
          ) : (
            <div className="mt-3">
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full min-w-[28rem] text-sm">
                  <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left font-semibold">Kit impacté</th>
                      <th className="px-3 py-2 text-left font-semibold">Module</th>
                      <th className="px-3 py-2 text-right font-semibold">Qté avant</th>
                      <th className="px-3 py-2 text-right font-semibold">Qté après</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lignes(preview).map((k) => (
                      <tr key={`${k.module}-${k.kit_id}`} className="border-t border-border">
                        <td className="px-3 py-2">{k.kit_nom}</td>
                        <td className="px-3 py-2 text-xs">{k.module}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{k.quantite_avant}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{k.quantite_apres}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <Button type="button" loading={busy} onClick={confirmer}>
                  Confirmer le remplacement ({preview.nb_total} kit{preview.nb_total > 1 ? 's' : ''})
                </Button>
                <Button type="button" variant="outline" onClick={() => setPreview(null)}>Annuler</Button>
              </div>
            </div>
          )
        )}

        {done && (
          <div className="mt-3 rounded-lg border border-border bg-muted/40 p-2 text-sm">
            Remplacement appliqué à {done.nb_total} nomenclature{done.nb_total > 1 ? 's' : ''}
            {' '}(« {done.produit_ancien} » → « {done.produit_nouveau} »).
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function DonneesSection() {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col gap-4">
      <InventaireSessions />
      <KitExplosion />
      <RemplacementComposant />
      <FichesTechniques />

      {/* Export / sauvegarde : surface existante (page dédiée). */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Export & sauvegarde"
            icon={<><path d="M21 8v13H3V8" /><path d="M1 3h22v5H1z" /><path d="M10 12h4" /></>} />
          <p className="mb-3 text-[11.5px] text-muted-foreground">
            Exportez vos données par objet ou générez une sauvegarde ZIP
            complète (prix d&apos;achat et marges jamais inclus).
          </p>
          <Button type="button" variant="outline" onClick={() => navigate('/parametres/export')}>
            <Archive className="size-4" aria-hidden="true" />
            Ouvrir l&apos;export / sauvegarde
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
