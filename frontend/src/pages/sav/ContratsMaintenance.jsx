// T16 — contrats de maintenance (visites préventives). Liste + vue « à venir »
// (visites dues) + génération à la demande des tickets SAV préventifs (sans
// planificateur, cohérent T7). Création (client + périodicité + début + prix +
// installation + durée), édition/désactivation inline, revenu récurrent par
// ligne, badges « À renouveler » / « Visite proche », comptes de visites
// générées et choix de la date du rapport PDF.
import { useEffect, useMemo, useState } from 'react'
import {
  Download, Cog, Plus, CalendarClock, ClipboardList, AlertTriangle, Pencil,
  Check, X,
} from 'lucide-react'
import savApi from '../../api/savApi'
import { formatMAD } from '../../lib/format'
import crmApi from '../../api/crmApi'
import fetchAllPages from '../../utils/fetchAllPages'
import installationsApi from '../../api/installationsApi'
import api from '../../api/axios'
import { openPdfBlob } from '../../utils/pdfBlob'
import { useHasPermission } from '../../hooks/useHasPermission'
import {
  TooltipProvider,
  Button,
  Badge,
  StatusPill,
  Card,
  EmptyState,
  Skeleton,
  Input,
  Checkbox,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Segmented,
  Form, FormField,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
  DataTable,
  toast,
} from '../../ui'

const PERIODES = [
  { value: 'mensuel', label: 'Mensuel' },
  { value: 'trimestriel', label: 'Trimestriel' },
  { value: 'semestriel', label: 'Semestriel' },
  { value: 'annuel', label: 'Annuel' },
]
const PERIODE_LABELS = Object.fromEntries(PERIODES.map((p) => [p.value, p.label]))
// L323 — nombre de visites par an, par périodicité (pour le revenu récurrent).
const PERIODE_PAR_AN = { mensuel: 12, trimestriel: 4, semestriel: 2, annuel: 1 }

// ASAV50 — lit TOUTES les pages d'une liste DRF (jamais la page 1 seule) ;
// tolère une réponse non paginée (tableau brut).
const lireTout = (appel, params = {}) =>
  fetchAllPages((page) => appel({ ...params, page, page_size: 200 }).then((r) => r.data))
    .then((res) => (Array.isArray(res) ? res : (res?.results ?? [])))

const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}
const fmtDH = (n) => `${formatMAD(n, { decimals: 0, withSymbol: false })} DH`

// L323 — revenu récurrent équivalent mensuel d'un contrat (même maths que
// l'insight recurring_revenue : prix × visites/an ÷ 12).
function revenuMensuel(contrat) {
  const prix = Number(contrat?.prix)
  if (!Number.isFinite(prix) || prix <= 0) return null
  const parAn = PERIODE_PAR_AN[contrat.periodicite] ?? 1
  return (prix * parAn) / 12
}

// L324 — « Visite proche » : prochaine visite dans ~90 j mais pas encore due
// (calculé à la lecture, comme T7).
function visiteProche(contrat, jours = 90) {
  if (!contrat?.actif || contrat.due || !contrat.prochaine_visite) return false
  const d = new Date(`${String(contrat.prochaine_visite).slice(0, 10)}T00:00:00`)
  if (Number.isNaN(d.getTime())) return false
  const diff = Math.round((d - new Date()) / 86400000)
  return diff >= 0 && diff <= jours
}

// J144 — statut d'un contrat → { tone, label } pour StatusPill (la couleur n'est
// jamais le seul signal : le libellé reste explicite). Inactif > visite due > à jour.
function contratStatut(row) {
  if (!row?.actif) return { tone: 'neutral', label: 'Inactif' }
  if (row.due) return { tone: 'danger', label: 'Visite due' }
  return { tone: 'success', label: 'À jour' }
}

// Composant exporté (testable) : le statut d'un contrat rendu en StatusPill.
export function ContratStatutPill({ contrat }) {
  const { tone, label } = contratStatut(contrat)
  return <StatusPill tone={tone} label={label} />
}

/* CIQ648 (Groupe CIQ, D-CIQ-12) — contrat O&M C&I : prestations nommées
   (type, incluse, fréquence par an, prix HT) et délai d'intervention en
   heures, forme du contrat partagé `apps/sav/contract_samples/contrat_om.json`.
   AUCUN nombre pré-rempli : vide = « à renseigner » / « non engagé » ; une
   valeur tapée part telle quelle (step="any") ; refus 400 sous le champ. */
const TYPES_PRESTATION = {
  nettoyage: 'Nettoyage',
  inspection: 'Inspection',
  thermographie: 'Thermographie',
  test_protections: 'Test des protections',
  supervision: 'Supervision',
  autre: 'Autre',
}
const versTexte = (v) => (v === null || v === undefined ? '' : String(v))
const nombreOuNul = (v) => {
  const t = versTexte(v).trim().replace(',', '.')
  return t === '' ? null : t
}
const etatOm = (contrat) => ({
  delai_intervention_heures: versTexte(contrat?.delai_intervention_heures),
  prestations: (contrat?.prestations ?? []).map((p) => ({
    id: p.id, type: p.type, libelle: p.libelle, incluse: !!p.incluse,
    frequence_an: versTexte(p.frequence_an), prix_ht: versTexte(p.prix_ht),
  })),
})
const payloadOm = (etat) => ({
  delai_intervention_heures: nombreOuNul(etat.delai_intervention_heures),
  prestations: etat.prestations.map((p) => ({
    id: p.id, incluse: !!p.incluse,
    frequence_an: nombreOuNul(p.frequence_an), prix_ht: nombreOuNul(p.prix_ht),
  })),
})
const messageErreur = (v) => {
  if (v == null) return ''
  return (Array.isArray(v) ? v : [v])
    .map((m) => (typeof m === 'string' ? m : JSON.stringify(m))).join(' ')
}

export function PrestationsOmEditor({ contrat, onSaved }) {
  const [etat, setEtat] = useState(() => etatOm(contrat))
  const [erreur, setErreur] = useState(null)
  const [busy, setBusy] = useState(false)
  const setPrestation = (id, champ, valeur) => setEtat((e) => ({
    ...e,
    prestations: e.prestations.map((p) => (p.id === id ? { ...p, [champ]: valeur } : p)),
  }))
  const enregistrer = async (ev) => {
    ev.preventDefault()
    setBusy(true)
    setErreur(null)
    try {
      const res = await savApi.saveContratOm(contrat.id, payloadOm(etat))
      toast.success('Contrat O&M enregistré.')
      onSaved?.(res?.data)
    } catch (e) {
      setErreur(e?.response?.data ?? { detail: 'Enregistrement impossible.' })
    } finally {
      setBusy(false)
    }
  }
  const erreurDelai = messageErreur(erreur?.delai_intervention_heures)
  const erreurPrestations = messageErreur(erreur?.prestations) || messageErreur(erreur?.detail)
  const delaiVide = etat.delai_intervention_heures.trim() === ''
  return (
    <form noValidate onSubmit={enregistrer} className="flex flex-col gap-3">
      <FormField label="Délai d'intervention (heures)">
        <Input type="number" step="any" aria-label="Délai d'intervention (heures)"
               name="delai_intervention_heures"
               value={etat.delai_intervention_heures}
               invalid={Boolean(erreurDelai)}
               aria-describedby={erreurDelai ? 'om-delai-erreur' : undefined}
               onChange={(e) => setEtat((s) => ({ ...s, delai_intervention_heures: e.target.value }))} />
        {delaiVide && !erreurDelai && (
          <p className="text-xs text-muted-foreground">Vide : non engagé.</p>
        )}
        {erreurDelai && (
          <p id="om-delai-erreur" role="alert" className="text-xs font-medium text-destructive">
            {erreurDelai}
          </p>
        )}
      </FormField>
      {etat.prestations.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune prestation O&amp;M sur ce contrat.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th>Prestation</th><th>Incluse</th><th>Fréquence / an</th><th>Prix HT</th>
            </tr>
          </thead>
          <tbody>
            {etat.prestations.map((p) => (
              <tr key={p.id} className="border-t border-border" data-testid={`prestation-${p.id}`}>
                <td>
                  {p.libelle}
                  <span className="block text-xs text-muted-foreground">
                    {TYPES_PRESTATION[p.type] ?? p.type}
                  </span>
                </td>
                <td>
                  <input type="checkbox" aria-label={`${p.libelle} — incluse`}
                         checked={p.incluse}
                         onChange={(e) => setPrestation(p.id, 'incluse', e.target.checked)} />
                </td>
                <td>
                  <Input type="number" step="any" className="h-8"
                         aria-label={`${p.libelle} — fréquence par an`}
                         placeholder="à renseigner" value={p.frequence_an}
                         onChange={(e) => setPrestation(p.id, 'frequence_an', e.target.value)} />
                  {p.frequence_an.trim() === '' && (
                    <span className="text-xs text-muted-foreground">à renseigner</span>
                  )}
                </td>
                <td>
                  <Input type="number" step="any" className="h-8"
                         aria-label={`${p.libelle} — prix HT`}
                         placeholder="à renseigner" value={p.prix_ht}
                         onChange={(e) => setPrestation(p.id, 'prix_ht', e.target.value)} />
                  {p.prix_ht.trim() === '' && (
                    <span className="text-xs text-muted-foreground">à renseigner</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {erreurPrestations && (
        <p role="alert" className="text-xs font-medium text-destructive">{erreurPrestations}</p>
      )}
      <div className="flex justify-end">
        <Button type="submit" loading={busy}><Check /> Enregistrer</Button>
      </div>
    </form>
  )
}

export function Component() {
  const [rows, setRows] = useState([])
  const [clients, setClients] = useState([])
  const [installations, setInstallations] = useState([])
  const [equipements, setEquipements] = useState([]) // WIR120 — registre couvert
  const [preventifs, setPreventifs] = useState([]) // L327 — tickets préventifs
  const [vue, setVue] = useState('tous') // 'tous' | 'dus' | 'renouveler'
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false) // L329 — vide vs erreur
  // WIR120 — valeurs par défaut des champs « Avancé » (tous optionnels ;
  // vides = comportement historique inchangé côté serveur).
  const ADVANCED_DEFAULTS = {
    sla_response_days: '', sla_resolution_days: '',
    visites_incluses_an: '', deplacements_inclus_an: '', pieces_couvertes_pct: '',
    equipements: [],
  }
  const [form, setForm] = useState({
    client: '', periodicite: 'annuel', date_debut: '', date_renouvellement: '',
    prix: '', installation: '', duree_mois: '', ...ADVANCED_DEFAULTS,
  })
  const [formError, setFormError] = useState(null) // L326
  const [edit, setEdit] = useState(null) // L320 — { id, periodicite, prix, actif }
  // L675 — choix de la date du rapport PDF : { row, date }.
  const [pdfDialog, setPdfDialog] = useState(null)
  // CIQ648 — édition des prestations O&M et du délai d'intervention.
  const [omDialog, setOmDialog] = useState(null)

  // WIR231 — Rentabilité gardée EXCLUSIVEMENT par prix_achat_voir : l'option
  // n'apparaît même pas dans le Segmented sans la permission (unmount total,
  // jamais un simple masquage CSS — cf. EquipementFiabilitePanel).
  const canSeeCouts = useHasPermission('prix_achat_voir')

  // WIR230 — Tournée préventive (FG88) : file des visites dues avec GPS,
  // triée par proximité SERVEUR (jamais recalculée côté écran).
  const [tournee, setTournee] = useState([])
  const [tourneeLoading, setTourneeLoading] = useState(false)
  const [tourneeError, setTourneeError] = useState(null)
  const [tourneeSelected, setTourneeSelected] = useState(() => new Set())
  const [tourneeDate, setTourneeDate] = useState('')
  const [tourneeTechnicien, setTourneeTechnicien] = useState('')
  const [tourneeBusy, setTourneeBusy] = useState(false)
  const [users, setUsers] = useState([]) // technicien assignable (best-effort, réservé admin)

  // WIR231 — Rentabilité par contrat (XSAV18) : revenu/coût/marge, triés par
  // marge croissante par le SERVEUR (les contrats à perte en premier).
  const [rentabilite, setRentabilite] = useState([])
  const [rentabiliteLoading, setRentabiliteLoading] = useState(false)
  const [rentabiliteError, setRentabiliteError] = useState(null)

  const dueOnly = vue === 'dus'

  const loadTournee = () => {
    setTourneeLoading(true)
    setTourneeError(null)
    savApi.getTourneePreventive()
      .then((r) => setTournee(r.data?.results ?? r.data ?? []))
      .catch((e) => setTourneeError(e?.response?.data?.detail ?? 'Tournée indisponible.'))
      .finally(() => setTourneeLoading(false))
  }

  const loadRentabilite = () => {
    setRentabiliteLoading(true)
    setRentabiliteError(null)
    savApi.getRentabiliteContrats()
      .then((r) => setRentabilite(r.data?.results ?? r.data ?? []))
      .catch((e) => setRentabiliteError(
        e?.response?.data?.detail ?? 'Rentabilité indisponible.'))
      .finally(() => setRentabiliteLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { if (vue === 'tournee') loadTournee() }, [vue])
  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { if (vue === 'rentabilite' && canSeeCouts) loadRentabilite() }, [vue, canSeeCouts])
  useEffect(() => {
    // Best-effort (réservé admin) — sinon dropdown technicien vide, comme
    // TicketsPage.jsx pour la même liste.
    api.get('/users/').then((r) => setUsers(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  const toggleTourneeSelected = (id) => setTourneeSelected((s) => {
    const next = new Set(s)
    if (next.has(id)) next.delete(id); else next.add(id)
    return next
  })

  const planifierLaTournee = async () => {
    if (!tourneeSelected.size || !tourneeDate) return
    setTourneeBusy(true)
    setTourneeError(null)
    try {
      await savApi.planifierTournee({
        ticket_ids: [...tourneeSelected],
        date_tournee: tourneeDate,
        technicien_id: tourneeTechnicien || null,
      })
      toast.success('Tournée planifiée.')
      setTourneeSelected(new Set())
      loadTournee()
    } catch (e) {
      setTourneeError(e?.response?.data?.detail ?? 'Planification impossible.')
    } finally {
      setTourneeBusy(false)
    }
  }

  const load = () => {
    setLoading(true)
    setLoadError(false)
    return lireTout(savApi.getContrats, dueOnly ? { due: 1 } : {})
      .then((liste) => setRows(liste))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { load() }, [dueOnly])
  useEffect(() => {
    // ALEA33 — TOUTES les pages (jamais les 50 premiers clients seulement).
    fetchAllPages((page) => crmApi.getClients({ page, page_size: 200 }).then((r) => r.data))
      .then((res) => setClients(Array.isArray(res) ? res : (res?.results ?? []))).catch(() => {})
    lireTout(installationsApi.getInstallations)
      .then((liste) => setInstallations(liste)).catch(() => {})
    // L327 — tickets préventifs pour compter les visites générées par contrat.
    lireTout(savApi.getTickets, { type: 'preventif', ouvert: 'tous' })
      .then((liste) => setPreventifs(liste)).catch(() => {})
    // WIR120 — parc d'équipements pour le registre de couverture du contrat.
    lireTout(savApi.getEquipements)
      .then((liste) => setEquipements(liste)).catch(() => {})
  }, [])

  // L327 — compte de tickets préventifs par client (et installation si fixée).
  const preventifCount = (contrat) => (preventifs ?? []).filter((t) => {
    if (String(t.client) !== String(contrat.client)) return false
    if (contrat.installation
        && String(t.installation ?? '') !== String(contrat.installation)) return false
    return true
  }).length

  // L322 — vue « À renouveler » via renouvellement_du déjà sérialisé.
  // AUD502 — `a_renouveler` élargit le filtre à l'échéance duree_mois échue
  // (période de grâce de 30 j comprise : la couverture tombe à sa fin). Repli
  // sur `renouvellement_du` si le serveur ne sérialise pas encore le champ.
  const visibleRows = useMemo(() => {
    if (vue === 'renouveler') {
      return rows.filter((r) => r.a_renouveler ?? r.renouvellement_du)
    }
    return rows
  }, [rows, vue])

  const create = async () => {
    // L326 — validation FR claire au lieu d'un no-op silencieux.
    if (!form.client || !form.date_debut) {
      setFormError('Client et date de début requis.')
      return
    }
    setFormError(null)
    try {
      const payload = {
        client: form.client,
        periodicite: form.periodicite,
        date_debut: form.date_debut,
      }
      if (form.date_renouvellement) payload.date_renouvellement = form.date_renouvellement
      if (form.prix !== '') payload.prix = form.prix
      if (form.installation) payload.installation = form.installation
      if (form.duree_mois !== '') payload.duree_mois = form.duree_mois
      // WIR120 — champs « Avancé » : overrides SLA (D-ASAV-3 : plus de facturation récurrente),
      // registre d'équipements couverts, quotas visites/déplacements/pièces.
      if (form.sla_response_days !== '') payload.sla_response_days = form.sla_response_days
      if (form.sla_resolution_days !== '') payload.sla_resolution_days = form.sla_resolution_days
      if (form.visites_incluses_an !== '') payload.visites_incluses_an = form.visites_incluses_an
      if (form.deplacements_inclus_an !== '') payload.deplacements_inclus_an = form.deplacements_inclus_an
      if (form.pieces_couvertes_pct !== '') payload.pieces_couvertes_pct = form.pieces_couvertes_pct
      if (form.equipements.length) payload.equipements = form.equipements
      await savApi.saveContrat(null, payload)
      setForm({
        client: '', periodicite: 'annuel', date_debut: '', date_renouvellement: '',
        prix: '', installation: '', duree_mois: '', ...ADVANCED_DEFAULTS,
      })
      toast.success('Contrat ajouté')
      load()
    } catch (e) {
      setFormError(e?.response?.data?.detail ?? 'Création impossible.')
    }
  }

  // L320 — édition/désactivation inline (saveContrat(id, …) + actif).
  const startEdit = (row) => setEdit({
    id: row.id, periodicite: row.periodicite, prix: row.prix ?? '', actif: row.actif,
  })
  const saveEdit = async () => {
    try {
      await savApi.saveContrat(edit.id, {
        periodicite: edit.periodicite,
        prix: edit.prix === '' ? null : edit.prix,
        actif: edit.actif,
      })
      setEdit(null)
      toast.success('Contrat mis à jour')
      load()
    } catch { toast.error('Mise à jour impossible.') }
  }
  const toggleActif = async (row) => {
    try {
      await savApi.saveContrat(row.id, { actif: !row.actif })
      load()
    } catch { toast.error('Bascule impossible.') }
  }

  // L675 — ouvre le choix de date avant téléchargement (défaut derniere_visite).
  const openRapport = (row) => setPdfDialog({
    row,
    date: (row.derniere_visite || row.prochaine_visite || '').slice(0, 10),
  })
  const rapport = async () => {
    if (!pdfDialog) return
    const { row, date } = pdfDialog
    try {
      const res = await savApi.maintenanceRapportPdf(row.id, date || undefined)
      openPdfBlob(res.data, `maintenance-contrat-${row.id}.pdf`)
      setPdfDialog(null)
    } catch { toast.error('Rapport indisponible.') }
  }
  const generer = async () => {
    try {
      const { data } = await savApi.genererVisitesDues()
      // L328 — confirmer le compte généré et recharger sans race.
      toast.success(`${data.tickets_generes} ticket(s) de maintenance généré(s).`)
      await load()
      lireTout(savApi.getTickets, { type: 'preventif', ouvert: 'tous' })
        .then((liste) => setPreventifs(liste)).catch(() => {})
    } catch { toast.error('Génération impossible.') }
  }

  const columns = [
    { id: 'client_nom', header: 'Client', width: 180, accessor: (r) => r.client_nom },
    {
      id: 'periodicite', header: 'Périodicité', width: 130,
      // L325 — libellé FR (Annuel/Mensuel/…) via la map PERIODES.
      cell: (_v, row) => (edit?.id === row.id ? (
        <Select value={edit.periodicite}
                onValueChange={(v) => setEdit((e) => ({ ...e, periodicite: v }))}>
          <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
          <SelectContent>
            {PERIODES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
          </SelectContent>
        </Select>
      ) : (PERIODE_LABELS[row.periodicite] ?? row.periodicite)),
      exportValue: (row) => PERIODE_LABELS[row.periodicite] ?? row.periodicite,
    },
    {
      id: 'prix', header: 'Prix', width: 110,
      cell: (_v, row) => (edit?.id === row.id ? (
        <Input type="number" step="any" className="h-8" value={edit.prix}
               onChange={(e) => setEdit((s) => ({ ...s, prix: e.target.value }))} />
      ) : (row.prix != null ? fmtDH(row.prix) : '—')),
      exportValue: (row) => (row.prix != null ? row.prix : ''),
    },
    {
      // L323 — revenu récurrent équivalent mensuel.
      id: 'recurrent', header: 'Récurrent', width: 130, searchable: false,
      cell: (_v, row) => {
        const rev = revenuMensuel(row)
        return rev ? `≈ ${fmtDH(rev)}/mois` : '—'
      },
      exportValue: (row) => { const r = revenuMensuel(row); return r ? Math.round(r) : '' },
    },
    { id: 'date_debut', header: 'Début', width: 120, accessor: (r) => formatDateFR(r.date_debut) },
    {
      id: 'prochaine_visite', header: 'Prochaine visite', width: 160,
      cell: (_v, row) => (
        <span className="flex items-center gap-1.5">
          {formatDateFR(row.prochaine_visite)}
          {/* L324 — badge « Visite proche » distinct de déjà dû. */}
          {visiteProche(row) && <Badge tone="warning">Visite proche</Badge>}
        </span>
      ),
      exportValue: (row) => formatDateFR(row.prochaine_visite),
    },
    {
      // FE-XCTR2 — équipements couverts par le registre du contrat
      // (`equipements_detail`, sérialisé par ContratMaintenanceSerializer).
      id: 'couverture', header: 'Équipements couverts', width: 170, searchable: false,
      cell: (_v, row) => {
        const eqs = row.equipements_detail ?? []
        if (eqs.length === 0) return <span className="text-muted-foreground">—</span>
        const label = eqs.map((e) => e.numero_serie || e.produit_nom || `#${e.id}`).join(', ')
        return <Badge tone="neutral" title={label}>{eqs.length} équipement{eqs.length > 1 ? 's' : ''}</Badge>
      },
      exportValue: (row) => (row.equipements_detail ?? []).length,
    },
    {
      // FE-XCTR3 — visites incluses/consommées (`droits_restants`, XCTR3).
      // Quota NULL = illimité : on retombe sur le décompte historique des
      // tickets préventifs générés (comportement inchangé).
      id: 'visites', header: 'Visites', width: 130, searchable: false,
      cell: (_v, row) => {
        const droits = row.droits_restants
        if (droits && droits.visites_incluses_an != null) {
          const epuise = droits.visites_restantes === 0
          return (
            <Badge tone={epuise ? 'danger' : 'neutral'}>
              {droits.visites_consommees}/{droits.visites_incluses_an} visites
            </Badge>
          )
        }
        const n = preventifCount(row)
        return n ? `${n} visite(s)` : '—'
      },
      exportValue: (row) => {
        const droits = row.droits_restants
        if (droits && droits.visites_incluses_an != null) {
          return `${droits.visites_consommees}/${droits.visites_incluses_an}`
        }
        return preventifCount(row)
      },
    },
    {
      id: 'date_renouvellement', header: 'Renouvellement', width: 200,
      cell: (_v, row) => (
        <span className="flex flex-wrap items-center gap-1.5">
          {formatDateFR(row.date_renouvellement)}
          {/* AUD502 — échéance réelle (date_debut + duree_mois) : « En
              grâce » = expiré mais encore couvrant 30 j, « Expiré » = la
              couverture est tombée (tickets redevenus facturables). */}
          {row.date_expiration && (
            <span className="text-xs text-muted-foreground">
              échéance {formatDateFR(row.date_expiration)}
            </span>
          )}
          {row.en_periode_grace
            ? <Badge tone="danger">En grâce (30 j)</Badge>
            : row.expire
              ? <Badge tone="danger">Expiré</Badge>
              : row.renouvellement_du && <Badge tone="warning">à renouveler</Badge>}
        </span>
      ),
      exportValue: (row) => formatDateFR(row.date_renouvellement),
    },
    {
      // L330 — date de création + notes (sérialisés, désormais affichés).
      id: 'infos', header: 'Créé le / Notes', width: 180, searchable: false,
      cell: (_v, row) => (
        <span className="flex flex-col text-xs text-muted-foreground">
          <span>Créé le {formatDateFR(row.date_creation)}</span>
          {row.notes && <span className="truncate" title={row.notes}>{row.notes}</span>}
        </span>
      ),
      exportValue: (row) => `${formatDateFR(row.date_creation)} ${row.notes ?? ''}`.trim(),
    },
    {
      id: 'statut', header: 'Statut', width: 130, searchable: false,
      cell: (_v, row) => <ContratStatutPill contrat={row} />,
      exportValue: (row) => contratStatut(row).label,
    },
    {
      id: 'actions', header: '', width: 270, sortable: false, searchable: false, hideable: false,
      cell: (_v, row) => (edit?.id === row.id ? (
        <span className="flex items-center gap-2 text-sm">
          <label className="flex items-center gap-1.5">
            <Checkbox checked={edit.actif}
                      onCheckedChange={(v) => setEdit((e) => ({ ...e, actif: !!v }))} />
            Actif
          </label>
          <Button variant="outline" size="sm" onClick={saveEdit}><Check /> Enregistrer</Button>
          <Button variant="ghost" size="sm" onClick={() => setEdit(null)}><X /></Button>
        </span>
      ) : (
        <span className="flex items-center gap-1.5">
          <Button variant="outline" size="sm" onClick={() => openRapport(row)}>
            <Download /> Rapport PDF
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setOmDialog(row)}
                  title="Prestations O&M et délai d'intervention">
            O&amp;M
          </Button>
          <Button variant="ghost" size="sm" onClick={() => startEdit(row)} title="Éditer">
            <Pencil />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => toggleActif(row)}
                  title={row.actif ? 'Désactiver' : 'Activer'}>
            {row.actif ? 'Désactiver' : 'Activer'}
          </Button>
        </span>
      )),
    },
  ]

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root mx-auto flex max-w-6xl flex-col gap-5 p-1">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight">Contrats de maintenance</h1>
            <p className="text-sm text-muted-foreground">
              Visites préventives — {visibleRows.length} contrat{visibleRows.length > 1 ? 's' : ''}
            </p>
          </div>
          {/* MB5 — segmenté (3 options) + bouton : sur mobile ils passent sur
              deux lignes plutôt que déborder horizontalement. */}
          <div className="flex flex-wrap items-center gap-2">
            <Segmented
              size="sm"
              className="flex-wrap"
              value={vue}
              onChange={setVue}
              options={[
                { value: 'tous', label: 'Tous' },
                { value: 'dus', label: 'À venir (dus)' },
                { value: 'renouveler', label: 'À renouveler' },
                { value: 'tournee', label: 'Tournée' },
                // WIR231 — l'option n'existe même pas dans le DOM sans la
                // permission (unmount total, jamais un simple masquage).
                ...(canSeeCouts ? [{ value: 'rentabilite', label: 'Rentabilité' }] : []),
              ]}
            />
            <Button variant="outline" size="sm" onClick={generer}>
              <Cog /> Générer les visites dues
            </Button>
          </div>
        </header>

        {/* ── Création ── */}
        <Card className="p-4">
          <Form onSubmit={(e) => { e.preventDefault(); create() }}
                className="grid items-end gap-3 sm:grid-cols-[2fr_1fr_1fr_1fr] lg:grid-cols-[2fr_1fr_1fr_1fr_1fr_1fr_auto]">
            <FormField label="Client">
              <Select value={form.client ? String(form.client) : '__none'}
                      onValueChange={(v) => setForm((f) => ({ ...f, client: v === '__none' ? '' : v }))}>
                <SelectTrigger><SelectValue placeholder="— Client —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Client —</SelectItem>
                  {clients.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>{c.nom} {c.prenom || ''}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Périodicité">
              <Select value={form.periodicite}
                      onValueChange={(v) => setForm((f) => ({ ...f, periodicite: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PERIODES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Début">
              <Input type="date" value={form.date_debut}
                     onChange={(e) => setForm((f) => ({ ...f, date_debut: e.target.value }))} />
            </FormField>
            <FormField label="Renouvellement" hint="optionnel">
              <Input type="date" value={form.date_renouvellement}
                     onChange={(e) => setForm((f) => ({ ...f, date_renouvellement: e.target.value }))} />
            </FormField>
            {/* L321 — prix, installation et durée exposés à la création. */}
            <FormField label="Prix (DH)" hint="optionnel">
              <Input type="number" step="any" value={form.prix}
                     onChange={(e) => setForm((f) => ({ ...f, prix: e.target.value }))} />
            </FormField>
            <FormField label="Durée (mois)" hint="optionnel">
              <Input type="number" step="any" value={form.duree_mois}
                     onChange={(e) => setForm((f) => ({ ...f, duree_mois: e.target.value }))} />
            </FormField>
            <Button type="submit"><Plus /> Ajouter</Button>
            <FormField label="Chantier (optionnel)" className="sm:col-span-2 lg:col-span-2">
              <Select value={form.installation ? String(form.installation) : '__none'}
                      onValueChange={(v) => setForm((f) => ({ ...f, installation: v === '__none' ? '' : v }))}>
                <SelectTrigger><SelectValue placeholder="— Aucun chantier —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Aucun chantier —</SelectItem>
                  {installations.map((i) => (
                    <SelectItem key={i.id} value={String(i.id)}>
                      {i.reference ?? `Chantier ${i.id}`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
          </Form>

          {/* WIR120 — section « Avancé » : facturation récurrente, overrides SLA,
              registre d'équipements couverts, quotas visites/déplacements/pièces.
              Tous optionnels ; vides = comportement historique inchangé. */}
          <details className="mt-3 rounded-lg border border-border">
            <summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium">
              Avancé — SLA, couverture &amp; quotas
            </summary>
            <div className="flex flex-col gap-4 border-t border-border p-3">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <FormField label="SLA réponse (jours, override)" hint="vide = SLA société">
                  <Input type="number" min="0" step="1" value={form.sla_response_days}
                         onChange={(e) => setForm((f) => ({ ...f, sla_response_days: e.target.value }))} />
                </FormField>
                <FormField label="SLA résolution (jours, override)" hint="vide = SLA société">
                  <Input type="number" min="0" step="1" value={form.sla_resolution_days}
                         onChange={(e) => setForm((f) => ({ ...f, sla_resolution_days: e.target.value }))} />
                </FormField>
                <FormField label="Pièces couvertes (%)" hint="0–100, vide = indéfini">
                  <Input type="number" min="0" max="100" step="1" value={form.pieces_couvertes_pct}
                         onChange={(e) => setForm((f) => ({ ...f, pieces_couvertes_pct: e.target.value }))} />
                </FormField>
                <FormField label="Visites incluses / an" hint="vide = illimité">
                  <Input type="number" min="0" step="1" value={form.visites_incluses_an}
                         onChange={(e) => setForm((f) => ({ ...f, visites_incluses_an: e.target.value }))} />
                </FormField>
                <FormField label="Déplacements inclus / an" hint="vide = illimité">
                  <Input type="number" min="0" step="1" value={form.deplacements_inclus_an}
                         onChange={(e) => setForm((f) => ({ ...f, deplacements_inclus_an: e.target.value }))} />
                </FormField>
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-sm font-medium">Équipements couverts (registre)</span>
                {equipements.length === 0 ? (
                  <p className="text-xs text-muted-foreground">Aucun équipement au parc.</p>
                ) : (
                  <div className="flex max-h-44 flex-col gap-1 overflow-y-auto rounded-md border border-border p-2">
                    {equipements.map((eq) => {
                      const checked = form.equipements.includes(eq.id)
                      const label = `${eq.numero_serie || `#${eq.id}`}${eq.produit_nom ? ` — ${eq.produit_nom}` : ''}`
                      return (
                        <label key={eq.id} className="flex items-center gap-2 text-sm">
                          <Checkbox checked={checked}
                                    aria-label={label}
                                    onCheckedChange={(v) => setForm((f) => ({
                                      ...f,
                                      equipements: v
                                        ? [...f.equipements, eq.id]
                                        : f.equipements.filter((id) => id !== eq.id),
                                    }))} />
                          {label}
                        </label>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          </details>

          {formError && (
            <div role="alert"
                 className="mt-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">
              <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
              {formError}
            </div>
          )}
        </Card>

        {vue === 'tournee' ? (
          // WIR230 — Tournée préventive (FG88) : ordre SERVEUR (proximité
          // haversine), jamais retrié côté écran.
          <Card className="flex flex-col gap-3 p-4">
            {tourneeError && (
              <div role="alert"
                   className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">
                <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
                {tourneeError}
              </div>
            )}
            {tourneeLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
              </div>
            ) : tournee.length === 0 ? (
              <EmptyState icon={CalendarClock} title="Aucune visite due"
                          description="Aucune visite préventive due n'a de chantier à tourner." />
            ) : (
              <ul className="flex flex-col divide-y divide-border rounded-lg border border-border">
                {tournee.map((t) => (
                  <li key={t.id} className="flex items-center gap-3 p-2.5 text-sm">
                    <Checkbox
                      checked={tourneeSelected.has(t.id)}
                      aria-label={`Sélectionner ${t.reference}`}
                      onCheckedChange={() => toggleTourneeSelected(t.id)}
                    />
                    <span className="flex-1">
                      {t.reference} — {t.client_nom ?? '—'}
                      {t.distance_km != null && (
                        <span className="text-muted-foreground"> · {Number(t.distance_km).toFixed(1)} km</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <div className="flex flex-wrap items-end gap-3">
              {/* Fable review — FormField ne relie PAS label→enfant
                  (ui/Form.jsx) : aria-label explicite comme VehiculeDetail.jsx,
                  sinon `getByLabelText` échoue en CI (« no form control
                  associated »). */}
              <FormField label="Date de tournée">
                <Input type="date" value={tourneeDate} aria-label="Date de tournée"
                       onChange={(e) => setTourneeDate(e.target.value)} />
              </FormField>
              <FormField label="Technicien (optionnel)">
                <Select value={tourneeTechnicien || '__none'}
                        onValueChange={(v) => setTourneeTechnicien(v === '__none' ? '' : v)}>
                  <SelectTrigger className="w-48" aria-label="Technicien (optionnel)">
                    <SelectValue placeholder="— Technicien —" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none">— Technicien —</SelectItem>
                    {users.map((u) => (
                      <SelectItem key={u.id} value={String(u.id)}>{u.username}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>
              <Button
                disabled={!tourneeSelected.size || !tourneeDate}
                loading={tourneeBusy}
                onClick={planifierLaTournee}
              >
                Planifier la tournée
              </Button>
            </div>
          </Card>
        ) : vue === 'rentabilite' && canSeeCouts ? (
          // WIR231 — revenu/coût/marge par contrat, triés par le SERVEUR
          // (marge croissante — les contrats à perte en premier).
          <Card className="p-4">
            {rentabiliteError && (
              <div role="alert"
                   className="mb-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">
                <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
                {rentabiliteError}
              </div>
            )}
            {rentabiliteLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
              </div>
            ) : rentabilite.length === 0 ? (
              <EmptyState icon={ClipboardList} title="Aucune donnée de rentabilité" />
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th>Client</th><th>Revenu</th><th>Coût</th><th>Marge</th><th>Marge / visite</th>
                  </tr>
                </thead>
                <tbody>
                  {rentabilite.map((r) => (
                    <tr key={r.contrat_id} className="border-t border-border">
                      <td>{r.client_nom ?? `Contrat #${r.contrat_id}`}</td>
                      <td>{fmtDH(r.revenu)}</td>
                      <td>{fmtDH(r.cout)}</td>
                      <td className={r.marge < 0 ? 'text-destructive' : undefined}>{fmtDH(r.marge)}</td>
                      <td>{r.marge_par_visite != null ? fmtDH(r.marge_par_visite) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        ) : loading ? (
          // L329 — état de chargement explicite.
          <Card className="space-y-2 p-4">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </Card>
        ) : loadError ? (
          // L329 — distinction vide vs erreur de chargement.
          <EmptyState
            icon={AlertTriangle}
            title="Chargement impossible"
            description="Les contrats n'ont pas pu être chargés. Réessayez."
            action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>}
          />
        ) : visibleRows.length === 0 ? (
          <EmptyState
            icon={vue === 'tous' ? ClipboardList : CalendarClock}
            title={vue === 'dus' ? 'Aucune visite due'
              : vue === 'renouveler' ? 'Aucun contrat à renouveler' : 'Aucun contrat'}
            description={vue === 'dus'
              ? 'Aucun contrat n’a de visite due pour le moment.'
              : vue === 'renouveler'
                ? 'Aucun contrat n’atteint sa date de renouvellement.'
                : 'Ajoutez un contrat de maintenance ci-dessus pour planifier les visites préventives.'}
          />
        ) : (
          <DataTable
            data={visibleRows}
            columns={columns}
            getRowId={(row) => row.id}
            searchable={false}
            exportName="contrats-maintenance"
            emptyTitle="Aucun contrat"
          />
        )}

        {/* CIQ648 — prestations O&M (fréquence, prix « à renseigner ») et
            délai d'intervention en heures, sans aucun nombre pré-rempli. */}
        <Dialog open={!!omDialog} onOpenChange={(o) => { if (!o) setOmDialog(null) }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Contrat O&amp;M — {omDialog?.client_nom ?? ''}</DialogTitle>
              <DialogDescription>
                Prestations, fréquences et prix saisis par la société : vide =
                « à renseigner ».
              </DialogDescription>
            </DialogHeader>
            {omDialog && (
              <PrestationsOmEditor key={omDialog.id} contrat={omDialog}
                                   onSaved={() => { setOmDialog(null); load() }} />
            )}
          </DialogContent>
        </Dialog>

        {/* L675 — choix de la date de visite avant téléchargement du rapport. */}
        <Dialog open={!!pdfDialog} onOpenChange={(o) => { if (!o) setPdfDialog(null) }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Rapport de maintenance</DialogTitle>
              <DialogDescription>
                Choisissez la date de visite figurant sur le rapport
                (par défaut, la dernière visite générée).
              </DialogDescription>
            </DialogHeader>
            <FormField label="Date de visite">
              <Input type="date" value={pdfDialog?.date ?? ''}
                     onChange={(e) => setPdfDialog((d) => ({ ...d, date: e.target.value }))} />
            </FormField>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setPdfDialog(null)}>Annuler</Button>
              <Button onClick={rapport}><Download /> Télécharger</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  )
}
