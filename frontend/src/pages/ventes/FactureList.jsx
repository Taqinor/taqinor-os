import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  Search, Plus, Download, BookText, ListChecks, FileWarning,
  MessageCircle, Code2, Check, FileText, ReceiptText,
} from 'lucide-react'
import {
  fetchFactures,
  emettreFacture,
  marquerPayeeFacture,
  annulerFacture,
  genererPdfFacture,
} from '../../features/ventes/store/ventesSlice'
import ventesApi from '../../api/ventesApi'
import importApi, { downloadXlsx } from '../../api/importApi'
import FactureForm from './FactureForm'
import {
  Button, Badge, StatusPill, Card, EmptyState, Spinner,
  Tabs, TabsList, TabsTrigger,
  Input,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  Form, FormField, FormActions,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { formatMAD } from '../../lib/format'

const STATUT_DISPLAY = {
  brouillon: 'Brouillon',
  emise:     'Émise',
  payee:     'Payée',
  en_retard: 'En retard',
  annulee:   'Annulée',
}

const TABS = [
  { key: 'toutes',    label: 'Toutes' },
  { key: 'brouillon', label: 'Brouillon' },
  { key: 'emise',     label: 'Émises' },
  { key: 'overdue',   label: 'En retard' },
  { key: 'payee',     label: 'Payées' },
  { key: 'annulee',   label: 'Annulées' },
]

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

  const creerAvoir = async (f) => {
    const motif = window.prompt(
      `Créer un avoir TOTAL pour la facture ${f.reference} ?\n`
      + 'Motif (optionnel) :', '')
    if (motif === null) return
    try {
      await ventesApi.creerAvoir(f.id, { motif })
      dispatch(fetchFactures())
      alert('Avoir créé. Retrouvez-le dans Ventes → Avoirs.')
    } catch (err) {
      alert(err?.response?.data?.detail ?? "Création de l'avoir impossible.")
    }
  }

  const [showForm, setShowForm]       = useState(false)
  const [editFacture, setEditFacture] = useState(null)
  const [activeTab, setActiveTab]     = useState('toutes')
  const [search, setSearch]           = useState('')
  const [actionId, setActionId]       = useState(null)
  const [pdfGenerating, setPdfGenerating] = useState({})
  const [pdfDownloading, setPdfDownloading] = useState({})
  const [waBusyId, setWaBusyId] = useState(null)
  const [ublBusyId, setUblBusyId] = useState(null)
  const [auditBusy, setAuditBusy] = useState(false)

  // ── Enregistrement de paiement ──
  const [payTarget, setPayTarget] = useState(null) // facture ciblée
  const [paySaving, setPaySaving] = useState(false)
  const [payMontant, setPayMontant] = useState('')
  const [payDate, setPayDate] = useState(today)
  const [payMode, setPayMode] = useState('virement')
  const [payReference, setPayReference] = useState('')

  const openPayModal = (f) => {
    setPayTarget(f)
    setPayMontant(f.montant_du ?? '')
    setPayDate(today)
    setPayMode('virement')
    setPayReference('')
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

  useEffect(() => { dispatch(fetchFactures()) }, [dispatch])

  const filtered = useMemo(() => {
    let list = factures
    if (activeTab === 'overdue') {
      list = list.filter(isOverdue)
    } else if (activeTab !== 'toutes') {
      list = list.filter(f => f.statut === activeTab)
    }
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter(f =>
        f.reference?.toLowerCase().includes(q) ||
        (f.client_nom ?? '').toLowerCase().includes(q)
      )
    }
    return list
  }, [factures, activeTab, search])

  const counts = useMemo(() => ({
    toutes:    factures.length,
    brouillon: factures.filter(f => f.statut === 'brouillon').length,
    emise:     factures.filter(f => f.statut === 'emise' && !isOverdue(f)).length,
    overdue:   factures.filter(isOverdue).length,
    payee:     factures.filter(f => f.statut === 'payee').length,
    annulee:   factures.filter(f => f.statut === 'annulee').length,
  }), [factures])

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
    setWaBusyId(f.id)
    try {
      const res = await ventesApi.whatsappFacture(f.id, { modele })
      if (res.data?.wa_url) window.open(res.data.wa_url, '_blank', 'noopener')
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Envoi WhatsApp impossible.')
    } finally {
      setWaBusyId(null)
    }
  }

  // N38 — télécharge l'aperçu BROUILLON UBL 2.1 (XML) de la facture.
  const handleUbl = async (f) => {
    setUblBusyId(f.id)
    try {
      const res = await ventesApi.telechargerUbl(f.id)
      openPdfBlob(res.data, `${f.reference}-ubl.xml`)
    } catch {
      alert("Génération de l'aperçu UBL impossible.")
    } finally {
      setUblBusyId(null)
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
                    description={typeof error === 'string' ? error : JSON.stringify(error)} />
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
          <Button size="sm" variant="outline"
                  onClick={() => importApi.exportList('factures', factures.map(f => f.id))
                    .then(r => downloadXlsx(r.data, 'factures.xlsx')).catch(() => {})}>
            <Download /> Exporter Excel
          </Button>
          <Button size="sm" variant="outline" title="Journal des ventes + résumé TVA (comptable)"
                  onClick={() => {
                    const m = window.prompt('Mois du journal des ventes (AAAA-MM) :',
                      new Date().toISOString().slice(0, 7))
                    if (!m) return
                    ventesApi.journalVentes({ month: m })
                      .then(r => downloadXlsx(r.data, `journal-ventes-${m}.xlsx`))
                      .catch(() => {})
                  }}>
            <BookText /> Journal comptable
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
              Payé {payTarget?.montant_paye} / Dû {payTarget?.montant_du} MAD
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
        </DialogContent>
      </Dialog>

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

                  return (
                    <tr key={f.id} className={overdue ? 'bg-destructive/5' : undefined}>
                      <td>
                        <strong>{f.reference}</strong>
                        {f.type_facture_display && (
                          <div className="mt-0.5 text-xs text-muted-foreground">
                            {f.type_facture_display}
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
                        <span className={overdue ? 'font-semibold text-destructive' : undefined}>
                          {f.date_echeance
                            ? new Date(f.date_echeance).toLocaleDateString('fr-FR')
                            : '—'}
                        </span>
                      </td>
                      <td className="ta-right tabular-nums">
                        {f.total_ttc != null ? formatMAD(f.total_ttc) : '—'}
                        {(f.montant_paye != null || f.montant_du != null) && (
                          <div className="mt-0.5 text-xs text-muted-foreground">
                            Payé {f.montant_paye} / Dû {f.montant_du} MAD
                          </div>
                        )}
                      </td>
                      <td>
                        <StatusPill status={statutKey} label={STATUT_DISPLAY[statutKey] ?? STATUT_DISPLAY.brouillon} />
                      </td>
                      <td>
                        <div className="flex flex-wrap items-center gap-2">
                          {f.statut === 'brouillon' && (
                            <Button size="sm" variant="outline" onClick={() => openEdit(f)}>
                              Éditer
                            </Button>
                          )}
                          {f.statut === 'brouillon' && (
                            <Button size="sm" loading={busy} onClick={() => doAction(emettreFacture, f.id)}>
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
                            <Button size="sm" variant="outline" onClick={() => openPayModal(f)} title="Enregistrer un paiement">
                              Enregistrer paiement
                            </Button>
                          )}
                          {f.statut !== 'payee' && f.statut !== 'annulee' && (
                            <Button size="sm" variant="outline" loading={busy}
                                    onClick={() => doAction(annulerFacture, f.id, `Annuler la facture ${f.reference} ?`)}>
                              Annuler
                            </Button>
                          )}
                          {isAdmin && ['emise', 'payee', 'en_retard'].includes(f.statut) && (
                            <Button size="sm" variant="outline" onClick={() => creerAvoir(f)}
                                    title="Créer un avoir (note de crédit)">
                              Avoir
                            </Button>
                          )}
                          {['emise', 'payee', 'en_retard'].includes(f.statut) && (
                            <Button size="sm" variant="outline" loading={waBusyId === f.id}
                                    onClick={() => handleWhatsApp(f, 'facture')}
                                    title="Envoyer par WhatsApp (lien vers le PDF client)">
                              <MessageCircle /> WhatsApp
                            </Button>
                          )}
                          {['emise', 'payee', 'en_retard'].includes(f.statut) && (
                            <Button size="sm" variant="outline" loading={ublBusyId === f.id}
                                    onClick={() => handleUbl(f)}
                                    title="Aperçu BROUILLON UBL 2.1 (XML) — préparation e-facturation, non transmis">
                              <Code2 /> UBL
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
