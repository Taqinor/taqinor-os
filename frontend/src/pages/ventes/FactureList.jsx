import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Link } from 'react-router-dom'
import {
  Search, Plus, Download, BookText, ListChecks, FileWarning,
  MessageCircle, Code2, Check, FileText, ReceiptText, MoreHorizontal,
} from 'lucide-react'
import {
  fetchFactures,
  emettreFacture,
  marquerPayeeFacture,
  annulerFacture,
  genererPdfFacture,
} from '../../features/ventes/store/ventesSlice'
import ventesApi from '../../api/ventesApi'
import api from '../../api/axios'
import importApi, { downloadXlsx } from '../../api/importApi'
import FactureForm from './FactureForm'
import {
  Button, Badge, StatusPill, Card, EmptyState, Spinner,
  Tabs, TabsList, TabsTrigger,
  Input,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  Form, FormField, FormActions,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../ui'
import { formatMAD, toNumber } from '../../lib/format'

const STATUT_DISPLAY = {
  brouillon: 'Brouillon',
  emise:     'Émise',
  payee:     'Payée',
  en_retard: 'En retard',
  annulee:   'Annulée',
}

// N39 — statut de télédéclaration DGI (purement informatif, lecture seule).
const TELEDECLARATION_DISPLAY = {
  non_soumise: 'DGI : Non soumise',
  soumise:     'DGI : Soumise',
  validee:     'DGI : Validée',
}
const TELEDECLARATION_TONE = {
  non_soumise: 'neutral',
  soumise:     'info',
  validee:     'success',
}

const TABS = [
  { key: 'toutes',    label: 'Toutes' },
  { key: 'brouillon', label: 'Brouillon' },
  { key: 'emise',     label: 'Émises' },
  { key: 'overdue',   label: 'En retard' },
  { key: 'partielle', label: 'Partiellement payées' },
  { key: 'payee',     label: 'Payées' },
  { key: 'annulee',   label: 'Annulées' },
]

// Filtre par type de facture d'échéancier (champ type_facture du modèle).
const TYPES_FACTURE = [
  { value: '',             label: 'Tous les types' },
  { value: 'complete',     label: 'Complète' },
  { value: 'acompte',      label: 'Acompte' },
  { value: 'intermediaire', label: 'Intermédiaire' },
  { value: 'solde',        label: 'Solde' },
]

// Facture à solde partiel : un acompte encaissé mais reste dû > 0.
const isPartiallyPaid = f =>
  toNumber(f.montant_paye) > 0 && toNumber(f.montant_du) > 0 &&
  f.statut !== 'annulee'

const MODES_PAIEMENT = [
  { value: 'especes',     label: 'Espèces' },
  { value: 'virement',    label: 'Virement' },
  { value: 'cheque',      label: 'Chèque' },
  { value: 'carte',       label: 'Carte' },
  { value: 'prelevement', label: 'Prélèvement' },
  { value: 'autre',       label: 'Autre' },
]

const today = new Date().toISOString().slice(0, 10)
const isOverdue = f =>
  f.is_overdue ||
  (f.statut === 'emise' && f.date_echeance && f.date_echeance < today)

// Prochaine action contextuelle (next-best-action) : clé de l'action mise en
// avant selon statut/montant dû/retard. Une brouillon → Émettre ; une émise en
// retard → Relancer ; une émise partiellement payée → Encaisser ; sinon null.
function nextBestAction(f) {
  if (f.statut === 'brouillon') return 'emettre'
  if (f.statut === 'annulee' || f.statut === 'payee') return null
  if (isOverdue(f)) return 'relancer'
  if (toNumber(f.montant_paye) > 0 && toNumber(f.montant_du) > 0) return 'encaisser'
  return null
}

function openPdfBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.target = '_blank'
  a.rel = 'noopener'
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

export default function FactureList() {
  const dispatch = useDispatch()
  const { factures, loading, error } = useSelector(s => s.ventes)
  const isAdmin = useSelector(s => s.auth.role) === 'admin'

  // ── Avoir (note de crédit) : modale total OU partiel ──
  const [avoirTarget, setAvoirTarget] = useState(null) // facture ciblée
  const [avoirMotif, setAvoirMotif]   = useState('')
  const [avoirSaving, setAvoirSaving] = useState(false)
  // Quantités à créditer par ligne (clé = id de ligne) ; vide = avoir total.
  const [avoirQtes, setAvoirQtes]     = useState({})

  const openAvoirModal = async (f) => {
    setAvoirMotif('')
    setAvoirQtes({})
    // Charge le détail des lignes pour permettre un avoir partiel.
    try {
      const res = await ventesApi.getFacture(f.id)
      setAvoirTarget(res.data)
    } catch {
      setAvoirTarget(f)
    }
  }

  const handleCreerAvoir = async (mode) => {
    if (!avoirTarget) return
    setAvoirSaving(true)
    try {
      const payload = { motif: avoirMotif }
      if (mode === 'partiel') {
        const lignes = (avoirTarget.lignes || [])
          .map(l => ({ ...l, _qte: parseFloat(avoirQtes[l.id] ?? 0) }))
          .filter(l => l._qte > 0)
          .map(l => ({
            produit: l.produit ?? null,
            designation: l.designation,
            quantite: l._qte,
            prix_unitaire: l.prix_unitaire,
            remise: l.remise ?? 0,
            taux_tva: l.taux_tva,
          }))
        if (lignes.length === 0) {
          alert('Saisissez au moins une quantité à créditer.')
          setAvoirSaving(false)
          return
        }
        payload.lignes = lignes
      }
      await ventesApi.creerAvoir(avoirTarget.id, payload)
      setAvoirTarget(null)
      dispatch(fetchFactures())
      alert('Avoir créé. Retrouvez-le dans Ventes → Avoirs.')
    } catch (err) {
      alert(err?.response?.data?.detail ?? "Création de l'avoir impossible.")
    } finally {
      setAvoirSaving(false)
    }
  }

  const [showForm, setShowForm]       = useState(false)
  const [editFacture, setEditFacture] = useState(null)
  const [activeTab, setActiveTab]     = useState('toutes')
  const [search, setSearch]           = useState('')
  const [typeFilter, setTypeFilter]   = useState('')
  const [actionId, setActionId]       = useState(null)
  const [pdfGenerating, setPdfGenerating] = useState({})
  const [pdfDownloading, setPdfDownloading] = useState({})
  const [auditBusy, setAuditBusy] = useState(false)

  // ── Enregistrement de paiement ──
  const [payTarget, setPayTarget] = useState(null) // facture ciblée
  const [paySaving, setPaySaving] = useState(false)
  const [payMontant, setPayMontant] = useState('')
  const [payDate, setPayDate] = useState(today)
  const [payMode, setPayMode] = useState('virement')
  const [payReference, setPayReference] = useState('')

  // Chatter facture (avoirs + paiements) chargé à l'ouverture de la modale.
  const [factureActivites, setFactureActivites] = useState([])
  const loadActivites = async (id) => {
    try {
      const res = await api.get(`/ventes/factures/${id}/historique/`)
      setFactureActivites(res.data)
    } catch {
      setFactureActivites([])
    }
  }

  const openPayModal = (f) => {
    setPayTarget(f)
    setPayMontant(f.montant_du ?? '')
    setPayDate(today)
    setPayMode('virement')
    setPayReference('')
    setFactureActivites([])
    loadActivites(f.id)
  }

  const handleEnregistrerPaiement = async (e) => {
    e.preventDefault()
    if (!payTarget) return
    setPaySaving(true)
    try {
      await ventesApi.enregistrerPaiement(payTarget.id, {
        montant: parseFloat(payMontant),
        date_paiement: payDate,
        mode: payMode,
        reference: payReference || undefined,
      })
      setPayTarget(null)
      dispatch(fetchFactures())
      alert('Paiement enregistré.')
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Enregistrement du paiement impossible.')
    } finally {
      setPaySaving(false)
    }
  }

  // ── Édition inline de la date d'échéance (facture émise) ──
  const [echeanceEditId, setEcheanceEditId] = useState(null)
  const [echeanceValue, setEcheanceValue]   = useState('')
  const [echeanceSaving, setEcheanceSaving] = useState(false)

  const startEditEcheance = (f) => {
    setEcheanceEditId(f.id)
    setEcheanceValue(f.date_echeance ?? '')
  }
  const saveEcheance = async (f) => {
    setEcheanceSaving(true)
    try {
      await ventesApi.patchFacture(f.id, { date_echeance: echeanceValue || null })
      setEcheanceEditId(null)
      dispatch(fetchFactures())
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Mise à jour de l’échéance impossible.')
    } finally {
      setEcheanceSaving(false)
    }
  }

  useEffect(() => { dispatch(fetchFactures()) }, [dispatch])

  const filtered = useMemo(() => {
    let list = factures
    if (activeTab === 'overdue') {
      list = list.filter(isOverdue)
    } else if (activeTab === 'partielle') {
      list = list.filter(isPartiallyPaid)
    } else if (activeTab !== 'toutes') {
      list = list.filter(f => f.statut === activeTab)
    }
    if (typeFilter) {
      list = list.filter(f => f.type_facture === typeFilter)
    }
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter(f =>
        f.reference?.toLowerCase().includes(q) ||
        (f.client_nom ?? '').toLowerCase().includes(q)
      )
    }
    return list
  }, [factures, activeTab, search, typeFilter])

  const counts = useMemo(() => ({
    toutes:    factures.length,
    brouillon: factures.filter(f => f.statut === 'brouillon').length,
    emise:     factures.filter(f => f.statut === 'emise' && !isOverdue(f)).length,
    overdue:   factures.filter(isOverdue).length,
    partielle: factures.filter(isPartiallyPaid).length,
    payee:     factures.filter(f => f.statut === 'payee').length,
    annulee:   factures.filter(f => f.statut === 'annulee').length,
  }), [factures])

  // Total encaissé du mois courant, dérivé on-the-fly des paiements des
  // factures chargées (date_paiement dans le mois en cours).
  const encaisseMois = useMemo(() => {
    const ym = today.slice(0, 7)  // AAAA-MM
    let total = 0
    for (const f of factures) {
      for (const p of (f.paiements || [])) {
        if ((p.date_paiement || '').slice(0, 7) === ym) {
          total += toNumber(p.montant) || 0
        }
      }
    }
    return total
  }, [factures])

  // Export comptable DGI (groundwork) : factures validées d'une plage, en
  // .xlsx ET .csv (ventilation TVA par ligne + ICE + totaux). Borné société.
  const handleExportComptable = async () => {
    const start = window.prompt('Export comptable — date de début (AAAA-MM-JJ) :',
      new Date().toISOString().slice(0, 8) + '01')
    if (!start) return
    const end = window.prompt('Date de fin (exclue, AAAA-MM-JJ) :',
      new Date().toISOString().slice(0, 10))
    if (!end) return
    const dl = async (fmt, ext) => {
      const res = await api.get('/ventes/export-comptable/', {
        params: { start, end, fmt }, responseType: 'blob',
      })
      openPdfBlob(res.data, `export-comptable-${start}_${end}.${ext}`)
    }
    try {
      await dl('xlsx', 'xlsx')
      await dl('csv', 'csv')
    } catch {
      alert('Export comptable impossible.')
    }
  }

  const openNew   = () => { setEditFacture(null); setShowForm(true) }
  const openEdit  = f  => { setEditFacture(f);    setShowForm(true) }
  const closeForm = () => { setShowForm(false);   setEditFacture(null) }
  const onSaved   = () => dispatch(fetchFactures())

  const doAction = async (thunk, id, confirmMsg) => {
    if (confirmMsg && !window.confirm(confirmMsg)) return
    setActionId(id)
    try {
      await dispatch(thunk(id)).unwrap()
    } catch (err) {
      alert(err?.detail ?? JSON.stringify(err))
    } finally {
      setActionId(null)
    }
  }

  const handleGenererPdf = async (f) => {
    setPdfGenerating(prev => ({ ...prev, [f.id]: true }))
    try {
      await dispatch(genererPdfFacture(f.id)).unwrap()
      let attempts = 0
      const poll = async () => {
        if (attempts++ > 15) {
          alert('La génération PDF prend plus de temps que prévu. Réessayez dans quelques instants.')
          return
        }
        try {
          const res = await ventesApi.getFacture(f.id)
          if (res.data.fichier_pdf) {
            dispatch(fetchFactures())
          } else {
            setTimeout(poll, 2000)
          }
        } catch {
          // ignore poll errors
        }
      }
      setTimeout(poll, 2000)
    } catch (err) {
      alert(err?.detail ?? 'Erreur lors de la génération PDF.')
    } finally {
      setPdfGenerating(prev => ({ ...prev, [f.id]: false }))
    }
  }

  const handleTelechargerPdf = async (f) => {
    setPdfDownloading(prev => ({ ...prev, [f.id]: true }))
    try {
      const res = await ventesApi.telechargerPdfFacture(f.id)
      openPdfBlob(res.data, `${f.reference}.pdf`)
    } catch {
      alert('Fichier introuvable. Régénérez le PDF.')
    } finally {
      setPdfDownloading(prev => ({ ...prev, [f.id]: false }))
    }
  }

  // Envoyer par WhatsApp : ouvre WhatsApp avec le message + lien public (PDF
  // client) pré-rempli ; le commercial appuie lui-même sur Envoyer.
  const handleWhatsApp = async (f, modele = 'facture') => {
    try {
      const res = await ventesApi.whatsappFacture(f.id, { modele })
      if (res.data?.wa_url) window.open(res.data.wa_url, '_blank', 'noopener')
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Envoi WhatsApp impossible.')
    }
  }

  // N38 — télécharge l'aperçu BROUILLON UBL 2.1 (XML) de la facture.
  const handleUbl = async (f) => {
    try {
      const res = await ventesApi.telechargerUbl(f.id)
      openPdfBlob(res.data, `${f.reference}-ubl.xml`)
    } catch {
      alert("Génération de l'aperçu UBL impossible.")
    }
  }

  // N31 — audit admin de la numérotation : résumé des trous/doublons.
  const handleAuditNumerotation = async () => {
    setAuditBusy(true)
    try {
      const { data } = await ventesApi.auditNumerotation()
      if (data.conforme) {
        alert('Numérotation conforme : aucun trou ni doublon détecté.')
      } else {
        const lignes = []
        const labels = { devis: 'Devis', facture: 'Factures',
          avoir: 'Avoirs', bon_commande: 'Bons de commande' }
        for (const cle of Object.keys(labels)) {
          for (const g of (data[cle] || [])) {
            const parts = []
            if (g.manquants.length) parts.push(`manquants : ${g.manquants.join(', ')}`)
            if (g.doublons.length) parts.push(`doublons : ${g.doublons.join(', ')}`)
            lignes.push(`${labels[cle]} ${g.radical} → ${parts.join(' ; ')}`)
          }
        }
        alert(`Anomalies de numérotation détectées :\n\n${lignes.join('\n')}\n\n`
          + `(${data.total_manquants} numéro(s) manquant(s), `
          + `${data.total_doublons} doublon(s)). Aucune renumérotation automatique.`)
      }
    } catch (err) {
      alert(err?.response?.data?.detail ?? "Audit de numérotation impossible.")
    } finally {
      setAuditBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
        <Spinner /> Chargement des factures…
      </div>
    )
  }
  if (error) {
    return (
      <div className="page">
        <EmptyState icon={FileWarning} title="Erreur de chargement"
                    description="Impossible de charger les factures. Réessayez." />
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Factures
          {factures.length > 0 && (
            <Badge tone="primary" className="ml-2 align-middle">{factures.length}</Badge>
          )}
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="search"
            className="w-full sm:w-56"
            leading={<Search />}
            placeholder="Référence, client…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <Select value={typeFilter || 'all'}
                  onValueChange={v => setTypeFilter(v === 'all' ? '' : v)}>
            <SelectTrigger className="w-full sm:w-44" title="Filtrer par type de facture">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TYPES_FACTURE.map(t => (
                <SelectItem key={t.value || 'all'} value={t.value || 'all'}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" variant="outline"
                  onClick={() => importApi.exportList('factures', factures.map(f => f.id))
                    .then(r => downloadXlsx(r.data, 'factures.xlsx')).catch(() => {})}>
            <Download /> Exporter Excel
          </Button>
          <Button size="sm" variant="outline" title="Journal des ventes + résumé TVA (comptable) — mois ou trimestre"
                  onClick={() => {
                    const choix = window.prompt(
                      'Période du journal des ventes :\n'
                      + '— Mois : AAAA-MM (ex. 2026-06)\n'
                      + '— Trimestre : AAAA-T (ex. 2026-2)',
                      new Date().toISOString().slice(0, 7))
                    if (!choix) return
                    const v = choix.trim()
                    // Trimestre (AAAA-Q avec Q de 1 à 4) vs mois (AAAA-MM).
                    const isQuarter = /^\d{4}-[1-4]$/.test(v)
                    const params = isQuarter ? { quarter: v } : { month: v }
                    ventesApi.journalVentes(params)
                      .then(r => downloadXlsx(r.data, `journal-ventes-${v}.xlsx`))
                      .catch(() => {})
                  }}>
            <BookText /> Journal comptable
          </Button>
          <Button size="sm" variant="outline"
                  title="Export comptable (factures validées d'une plage) — Excel + CSV"
                  onClick={handleExportComptable}>
            <Download /> Export comptable
          </Button>
          {isAdmin && (
            <Button size="sm" variant="outline" loading={auditBusy}
                    title="Vérifier les trous/doublons de numérotation (Art. 145 — séquence continue)"
                    onClick={handleAuditNumerotation}>
              <ListChecks /> Audit numérotation
            </Button>
          )}
          <Button onClick={openNew}><Plus /> Nouvelle facture</Button>
        </div>
      </div>

      {showForm && (
        <FactureForm facture={editFacture} onClose={closeForm} onSaved={onSaved} />
      )}

      {/* ── Modale d'enregistrement de paiement ── */}
      <Dialog open={!!payTarget} onOpenChange={(o) => { if (!o) setPayTarget(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enregistrer un paiement — {payTarget?.reference}</DialogTitle>
            <DialogDescription>
              Payé {formatMAD(payTarget?.montant_paye)} / Dû {formatMAD(payTarget?.montant_du)}
            </DialogDescription>
          </DialogHeader>
          <Form onSubmit={handleEnregistrerPaiement} className="gap-4">
            <FormField label="Montant (MAD)" required htmlFor="pay-montant" fullWidth>
              <Input id="pay-montant" type="number" min="0" step="any" required
                     value={payMontant} onChange={e => setPayMontant(e.target.value)} />
            </FormField>
            <FormField label="Date de paiement" required htmlFor="pay-date">
              <Input id="pay-date" type="date" required
                     value={payDate} onChange={e => setPayDate(e.target.value)} />
            </FormField>
            <FormField label="Mode" htmlFor="pay-mode">
              <Select value={payMode} onValueChange={setPayMode}>
                <SelectTrigger id="pay-mode"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {MODES_PAIEMENT.map(m => (
                    <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Référence (optionnel)" htmlFor="pay-ref" fullWidth>
              <Input id="pay-ref" type="text"
                     value={payReference} onChange={e => setPayReference(e.target.value)} />
            </FormField>
            <FormActions sticky={false}>
              <Button type="button" variant="ghost" onClick={() => setPayTarget(null)}>Annuler</Button>
              <Button type="submit" loading={paySaving}>Enregistrer</Button>
            </FormActions>
          </Form>
          {/* Historique des paiements déjà encaissés sur cette facture. */}
          <div className="mt-1 border-t pt-3">
            <p className="mb-2 text-sm font-medium">Paiements encaissés</p>
            {(payTarget?.paiements?.length ?? 0) === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun paiement enregistré.</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {payTarget.paiements.map(p => (
                  <li key={p.id} className="flex justify-between gap-3 tabular-nums">
                    <span className="text-muted-foreground">
                      {p.date_paiement ? new Date(p.date_paiement).toLocaleDateString('fr-FR') : '—'}
                      {p.mode_display ? ` · ${p.mode_display}` : ''}
                      {p.reference ? ` · ${p.reference}` : ''}
                    </span>
                    <strong>{formatMAD(p.montant)}</strong>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {/* Chatter facture : avoirs créés + paiements encaissés (qui/quand). */}
          <div className="mt-1 border-t pt-3">
            <p className="mb-2 text-sm font-medium">Historique (avoirs &amp; paiements)</p>
            {factureActivites.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune activité consignée.</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {factureActivites.map(a => (
                  <li key={a.id} className="flex justify-between gap-3">
                    <span className="text-muted-foreground">
                      {a.created_at ? new Date(a.created_at).toLocaleString('fr-FR') : '—'}
                      {a.user_nom ? ` · ${a.user_nom}` : ''}
                    </span>
                    <span className="text-right">{a.body || a.field_label}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Modale d'avoir (total ou partiel par ligne) ── */}
      <Dialog open={!!avoirTarget} onOpenChange={(o) => { if (!o) setAvoirTarget(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Créer un avoir — {avoirTarget?.reference}</DialogTitle>
            <DialogDescription>
              Avoir total (toute la facture) ou partiel (quantités à créditer par ligne).
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <FormField label="Motif (optionnel)" htmlFor="avoir-motif" fullWidth>
              <Input id="avoir-motif" type="text" value={avoirMotif}
                     onChange={e => setAvoirMotif(e.target.value)} />
            </FormField>
            {(avoirTarget?.lignes?.length ?? 0) > 0 && (
              <div className="overflow-x-auto">
                <table className="data-table text-sm">
                  <thead>
                    <tr>
                      <th>Désignation</th>
                      <th className="ta-right">Qté facturée</th>
                      <th className="ta-right">Qté à créditer</th>
                    </tr>
                  </thead>
                  <tbody>
                    {avoirTarget.lignes.map(l => (
                      <tr key={l.id}>
                        <td>{l.designation}</td>
                        <td className="ta-right tabular-nums">{l.quantite}</td>
                        <td className="ta-right">
                          <Input
                            type="number" min="0" step="any"
                            className="w-24"
                            value={avoirQtes[l.id] ?? ''}
                            max={l.quantite}
                            onChange={e => setAvoirQtes(q => ({ ...q, [l.id]: e.target.value }))}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={() => setAvoirTarget(null)}>Annuler</Button>
            {(avoirTarget?.lignes?.length ?? 0) > 0 && (
              <Button type="button" variant="outline" loading={avoirSaving}
                      onClick={() => handleCreerAvoir('partiel')}>
                Avoir partiel
              </Button>
            )}
            <Button type="button" loading={avoirSaving}
                    onClick={() => handleCreerAvoir('total')}>
              Avoir total
            </Button>
          </FormActions>
        </DialogContent>
      </Dialog>

      {factures.length > 0 && (
        <Card className="mt-3 w-fit px-4 py-2 text-sm">
          <span className="text-muted-foreground">Encaissé ce mois : </span>
          <strong className="tabular-nums">{formatMAD(encaisseMois)}</strong>
        </Card>
      )}

      {/* ── Tabs ── */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-1">
        <TabsList className="flex-wrap">
          {TABS.map(t => (
            <TabsTrigger key={t.key} value={t.key}
                         className={t.key === 'overdue' && counts.overdue > 0 ? 'text-destructive data-[state=active]:text-destructive' : undefined}>
              {t.label}
              {counts[t.key] > 0 && (
                <span className="ml-1.5 rounded bg-muted px-1.5 text-xs text-muted-foreground">{counts[t.key]}</span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {filtered.length === 0 ? (
        <EmptyState
          icon={ReceiptText}
          title={
            search ? `Aucun résultat pour « ${search} »`
              : activeTab !== 'toutes' ? 'Aucune facture dans cet onglet'
                : 'Aucune facture'
          }
          description={search || activeTab !== 'toutes' ? undefined : 'Créez votre première facture.'}
          action={!search && activeTab === 'toutes'
            ? <Button onClick={openNew}><Plus /> Nouvelle facture</Button> : undefined}
          className="mt-4"
        />
      ) : (
        <Card className="mt-4 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Référence</th>
                  <th>Client</th>
                  <th>Émission</th>
                  <th>Échéance</th>
                  <th className="ta-right">Total TTC</th>
                  <th>Statut</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(f => {
                  const overdue = isOverdue(f)
                  const statutKey = overdue && f.statut === 'emise' ? 'en_retard' : f.statut
                  const busy = actionId === f.id
                  const isGenerating = pdfGenerating[f.id]
                  const isDownloading = pdfDownloading[f.id]
                  const nba = nextBestAction(f)

                  return (
                    <tr key={f.id} className={overdue ? 'bg-destructive/5' : undefined}>
                      <td>
                        <strong>{f.reference}</strong>
                        {(f.type_facture_display || toNumber(f.pourcentage) > 0) && (
                          <div className="mt-0.5 text-xs text-muted-foreground">
                            {f.type_facture_display}
                            {toNumber(f.pourcentage) > 0
                              ? ` ${Math.round(toNumber(f.pourcentage))} %` : ''}
                          </div>
                        )}
                        {f.devis_reference && f.devis && (
                          <div className="mt-0.5 text-xs">
                            <Link to={`/ventes/devis?ref=${encodeURIComponent(f.devis_reference)}`}
                                  className="text-primary hover:underline">
                              Devis {f.devis_reference}
                            </Link>
                          </div>
                        )}
                        {Array.isArray(f.mentions_manquantes) && f.mentions_manquantes.length > 0 && (
                          <Badge
                            tone="warning"
                            className="mt-1 cursor-help"
                            title={`Mentions légales manquantes (Art. 145) :\n- ${f.mentions_manquantes.join('\n- ')}`}
                          >
                            <FileWarning className="size-3" />
                            {f.mentions_manquantes.length} mention(s) manquante(s)
                          </Badge>
                        )}
                      </td>
                      <td>{f.client_nom ?? '—'}</td>
                      <td>{new Date(f.date_emission).toLocaleDateString('fr-FR')}</td>
                      <td>
                        {echeanceEditId === f.id ? (
                          <span className="flex items-center gap-1">
                            <Input type="date" className="w-36" value={echeanceValue}
                                   onChange={e => setEcheanceValue(e.target.value)} />
                            <Button size="sm" loading={echeanceSaving} onClick={() => saveEcheance(f)}>OK</Button>
                            <Button size="sm" variant="ghost" onClick={() => setEcheanceEditId(null)}>×</Button>
                          </span>
                        ) : (
                          <span
                            className={`${overdue ? 'font-semibold text-destructive' : ''}`
                              + (['emise', 'en_retard'].includes(f.statut) || overdue
                                ? ' cursor-pointer hover:underline' : '')}
                            title={['emise', 'en_retard'].includes(f.statut) || overdue
                              ? 'Cliquer pour modifier l’échéance' : undefined}
                            onClick={() => {
                              if (['emise', 'en_retard'].includes(f.statut) || overdue) startEditEcheance(f)
                            }}
                          >
                            {f.date_echeance
                              ? new Date(f.date_echeance).toLocaleDateString('fr-FR')
                              : '—'}
                          </span>
                        )}
                      </td>
                      <td className="ta-right tabular-nums">
                        {f.total_ttc != null ? formatMAD(f.total_ttc) : '—'}
                        {(f.montant_paye != null || f.montant_du != null) && (
                          <div className="mt-0.5 text-xs text-muted-foreground">
                            Payé {formatMAD(f.montant_paye)} / Dû {formatMAD(f.montant_du)}
                          </div>
                        )}
                      </td>
                      <td>
                        <StatusPill status={statutKey} label={STATUT_DISPLAY[statutKey] ?? STATUT_DISPLAY.brouillon} />
                        {['emise', 'payee', 'en_retard'].includes(f.statut) && f.statut_teledeclaration && (
                          <Badge
                            tone={TELEDECLARATION_TONE[f.statut_teledeclaration] ?? 'neutral'}
                            className="mt-1 block w-fit"
                            title="Statut de télédéclaration DGI (informatif)"
                          >
                            {TELEDECLARATION_DISPLAY[f.statut_teledeclaration] ?? f.statut_teledeclaration}
                          </Badge>
                        )}
                      </td>
                      <td>
                        {nba === 'relancer' && (
                          <Badge tone="warning" className="mb-1 block w-fit"
                                 title="Facture échue — à relancer dans Relances / Impayés">
                            À relancer
                          </Badge>
                        )}
                        <div className="flex flex-wrap items-center gap-2">
                          {f.statut === 'brouillon' && (
                            <Button size="sm" variant="outline" onClick={() => openEdit(f)}>
                              Éditer
                            </Button>
                          )}
                          {f.statut === 'brouillon' && (
                            <Button size="sm" variant={nba === 'emettre' ? 'default' : 'outline'}
                                    loading={busy} onClick={() => doAction(emettreFacture, f.id)}>
                              Émettre
                            </Button>
                          )}
                          {(f.statut === 'emise' || f.statut === 'en_retard' || overdue) && (
                            <Button size="sm" variant="success" loading={busy}
                                    onClick={() => doAction(marquerPayeeFacture, f.id, `Marquer la facture ${f.reference} comme payée ?`)}>
                              <Check /> Payée
                            </Button>
                          )}
                          {parseFloat(f.montant_du ?? 0) > 0 && f.statut !== 'annulee' && (
                            <Button size="sm" variant={nba === 'encaisser' ? 'default' : 'outline'}
                                    onClick={() => openPayModal(f)} title="Enregistrer un paiement">
                              Enregistrer paiement
                            </Button>
                          )}
                          {f.fichier_pdf ? (
                            <Button size="sm" variant="success" loading={isDownloading}
                                    onClick={() => handleTelechargerPdf(f)} title="Télécharger le PDF">
                              <Download /> PDF
                            </Button>
                          ) : (
                            <Button size="sm" variant="outline" loading={isGenerating}
                                    onClick={() => handleGenererPdf(f)} title="Générer le PDF">
                              <FileText /> PDF
                            </Button>
                          )}
                          {/* Actions secondaires regroupées : tiennent sans déborder
                              sur écran étroit (menu compact « Actions »). */}
                          {(['emise', 'payee', 'en_retard'].includes(f.statut)
                            || (f.statut !== 'payee' && f.statut !== 'annulee')) && (
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button size="sm" variant="outline" title="Plus d'actions">
                                  <MoreHorizontal /> Actions
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                {isAdmin && ['emise', 'payee', 'en_retard'].includes(f.statut) && (
                                  <DropdownMenuItem onClick={() => openAvoirModal(f)}>
                                    Avoir (note de crédit)
                                  </DropdownMenuItem>
                                )}
                                {['emise', 'payee', 'en_retard'].includes(f.statut) && (
                                  <DropdownMenuItem onClick={() => handleWhatsApp(f, 'facture')}>
                                    <MessageCircle /> WhatsApp
                                  </DropdownMenuItem>
                                )}
                                {['emise', 'payee', 'en_retard'].includes(f.statut) && (
                                  <DropdownMenuItem onClick={() => handleUbl(f)}>
                                    <Code2 /> Aperçu UBL
                                  </DropdownMenuItem>
                                )}
                                {f.statut !== 'payee' && f.statut !== 'annulee' && (
                                  <DropdownMenuItem
                                    onClick={() => doAction(annulerFacture, f.id, `Annuler la facture ${f.reference} ?`)}>
                                    Annuler la facture
                                  </DropdownMenuItem>
                                )}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
