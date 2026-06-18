import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  Download, Plus, FileText, FileDown, Check, ArrowRight, HardHat, FileStack,
} from 'lucide-react'
import {
  fetchDevis,
  genererPdfDevis,
  convertirDevisEnBC,
} from '../../features/ventes/store/ventesSlice'
import ventesApi from '../../api/ventesApi'
import installationsApi from '../../api/installationsApi'
import importApi, { downloadXlsx } from '../../api/importApi'
import DevisForm from './DevisForm'
import {
  Button, Badge, StatusPill, Card, EmptyState, Spinner,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
  RadioGroup, RadioGroupItem, Checkbox, Label, Input,
} from '../../ui'
import { formatMAD } from '../../lib/format'

const STATUT_DISPLAY = {
  brouillon: 'Brouillon',
  envoye:    'Envoyé',
  accepte:   'Accepté',
  refuse:    'Refusé',
  expire:    'Expiré',
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

export default function DevisList() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { devis, loading, error } = useSelector(s => s.ventes)
  const role = useSelector(s => s.auth.role)
  const canDelete = role === 'admin'  // règle existante : destroy = admin

  const [showForm, setShowForm]       = useState(false)
  const [editDevis, setEditDevis]     = useState(null)
  const [convertingId, setConvertingId] = useState(null)
  const [factureGenId, setFactureGenId] = useState(null) // devis id en cours de facturation
  const [pdfGenerating, setPdfGenerating] = useState({}) // id → true
  const [pdfDownloading, setPdfDownloading] = useState({}) // id → true

  // ── Choix du format PDF (parité simulateur) ──
  const [pdfTarget, setPdfTarget] = useState(null) // devis ciblé par la modale
  const [pdfMode, setPdfMode] = useState('full')
  const [showMonthly, setShowMonthly] = useState(true)
  const [devisFinal, setDevisFinal] = useState(false)
  const [paymentMode, setPaymentMode] = useState('standard')
  const [customAcompte, setCustomAcompte] = useState('')
  const [includeEtude, setIncludeEtude] = useState(false)

  const openPdfModal = (d) => {
    setPdfTarget(d)
    setPdfMode('full')
    setShowMonthly(true)
    setDevisFinal(false)
    setPaymentMode('standard')
    setCustomAcompte('')
    setIncludeEtude(false)
  }

  useEffect(() => { dispatch(fetchDevis()) }, [dispatch])

  // Création ET édition passent par la page générateur solaire (l'ancien
  // modal DevisForm est conservé mais n'est plus le chemin d'édition).
  const openNew  = () => navigate('/ventes/devis/nouveau')
  const openEdit = (d) => {
    if (d.statut !== 'brouillon') return
    navigate(`/ventes/devis/nouveau?edit=${d.id}`)
  }
  const closeForm = () => { setShowForm(false); setEditDevis(null) }
  const onSaved  = () => dispatch(fetchDevis())

  const [deletingId, setDeletingId] = useState(null)
  const handleDelete = async (d) => {
    setDeletingId(d.id)
    try {
      await ventesApi.deleteDevis(d.id)
      dispatch(fetchDevis())
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Suppression impossible.')
    } finally {
      setDeletingId(null)
    }
  }

  const [chantierBusy, setChantierBusy] = useState(null)
  // « Créer le chantier » sur un devis accepté : crée (ou ouvre s'il existe
  // déjà) le chantier pré-rempli, puis navigue vers la page Chantiers.
  const handleChantier = async (d) => {
    if (d.chantier) { navigate('/chantiers'); return }
    setChantierBusy(d.id)
    try {
      await installationsApi.createFromDevis(d.id)
      dispatch(fetchDevis())
      navigate('/chantiers')
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Création du chantier impossible.')
    } finally {
      setChantierBusy(null)
    }
  }

  const handleConvertBC = async (d) => {
    if (!window.confirm(`Convertir « ${d.reference} » en bon de commande ?`)) return
    setConvertingId(d.id)
    try {
      await dispatch(convertirDevisEnBC(d.id)).unwrap()
      dispatch(fetchDevis())
    } catch (err) {
      alert(err?.detail ?? JSON.stringify(err))
    } finally {
      setConvertingId(null)
    }
  }

  const handleGenererFacture = async (d) => {
    setFactureGenId(d.id)
    try {
      const res = await ventesApi.genererFacture(d.id)
      const f = res.data
      alert(`${f.type_facture_display ?? 'Facture'} ${f.reference} créée.`)
      dispatch(fetchDevis())
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Génération de facture impossible.')
    } finally {
      setFactureGenId(null)
    }
  }

  const handleGenererPdf = async (d) => {
    const options = {
      pdf_mode: pdfMode,
      show_monthly: showMonthly,
      devis_final: devisFinal,
      payment_mode: paymentMode,
      custom_acompte: (devisFinal && paymentMode === 'custom' && customAcompte !== '')
        ? parseFloat(customAcompte) : null,
      include_etude: pdfMode === 'full' && includeEtude,
    }
    setPdfTarget(null)
    setPdfGenerating(prev => ({ ...prev, [d.id]: true }))
    try {
      await dispatch(genererPdfDevis({ id: d.id, options })).unwrap()
      // Poll until fichier_pdf is ready (max 30s, every 2s)
      let attempts = 0
      const poll = async () => {
        if (attempts++ > 15) {
          alert('La génération PDF prend plus de temps que prévu. Réessayez dans quelques instants.')
          return
        }
        try {
          const res = await ventesApi.getDevisById(d.id)
          if (res.data.fichier_pdf) {
            dispatch(fetchDevis())
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
      setPdfGenerating(prev => ({ ...prev, [d.id]: false }))
    }
  }

  const handleTelechargerPdf = async (d) => {
    setPdfDownloading(prev => ({ ...prev, [d.id]: true }))
    try {
      const res = await ventesApi.telechargerPdfDevis(d.id)
      openPdfBlob(res.data, `${d.reference}.pdf`)
    } catch {
      alert('Fichier introuvable. Régénérez le PDF.')
    } finally {
      setPdfDownloading(prev => ({ ...prev, [d.id]: false }))
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
        <Spinner /> Chargement des devis…
      </div>
    )
  }
  if (error) {
    return (
      <div className="page">
        <EmptyState icon={FileStack} title="Erreur de chargement"
                    description={typeof error === 'string' ? error : JSON.stringify(error)} />
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Devis</h2>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline"
                  onClick={() => importApi.exportList('devis', devis.map(d => d.id))
                    .then(r => downloadXlsx(r.data, 'devis.xlsx')).catch(() => {})}>
            <Download /> Exporter Excel
          </Button>
          <Button onClick={openNew}><Plus /> Nouveau devis</Button>
        </div>
      </div>

      {showForm && (
        <DevisForm devis={editDevis} onClose={closeForm} onSaved={onSaved} />
      )}

      {/* ── Modale de génération PDF : formats du simulateur ── */}
      <Dialog open={!!pdfTarget} onOpenChange={(o) => { if (!o) setPdfTarget(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Générer le PDF — {pdfTarget?.reference}</DialogTitle>
          </DialogHeader>

          <div className="flex flex-col gap-4">
            <div className="grid gap-2">
              <Label>Format</Label>
              <RadioGroup value={pdfMode} onValueChange={setPdfMode} className="flex flex-col gap-2">
                <label className="flex items-start gap-2 text-sm">
                  <RadioGroupItem value="full" className="mt-0.5" />
                  <span>Devis premium (3 pages — options, analyse, garanties)</span>
                </label>
                <label className="flex items-start gap-2 text-sm">
                  <RadioGroupItem value="onepage" className="mt-0.5" />
                  <span>Devis une page (liste produits uniquement, sans graphiques)</span>
                </label>
              </RadioGroup>
            </div>

            {pdfMode === 'full' && (
              <label className="flex items-start gap-2 text-sm">
                <Checkbox checked={showMonthly} onCheckedChange={v => setShowMonthly(!!v)} className="mt-0.5" />
                <span>Économies mensuelles <span className="text-muted-foreground">(graphique mensuel page 2)</span></span>
              </label>
            )}

            {pdfMode === 'full' && (
              <label className="flex items-start gap-2 text-sm">
                <Checkbox checked={includeEtude} onCheckedChange={v => setIncludeEtude(!!v)} className="mt-0.5" />
                <span>Inclure l'étude <span className="text-muted-foreground">(page autoconsommation — devis industriel)</span></span>
              </label>
            )}

            <label className="flex items-start gap-2 text-sm">
              <Checkbox checked={devisFinal} onCheckedChange={v => setDevisFinal(!!v)} className="mt-0.5" />
              <span>Devis Final <span className="text-muted-foreground">(ajoute modalités de paiement + RIB)</span></span>
            </label>

            {devisFinal && (
              <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/40 p-3">
                <RadioGroup value={paymentMode} onValueChange={setPaymentMode} className="flex flex-col gap-2">
                  <label className="flex items-center gap-2 text-sm">
                    <RadioGroupItem value="standard" />
                    <span>Standard (30/60/10)</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <RadioGroupItem value="custom" />
                    <span>Acompte personnalisé</span>
                  </label>
                </RadioGroup>
                {paymentMode === 'custom' && (
                  <div className="grid gap-1.5">
                    <Label htmlFor="pdf-acompte">Montant acompte (MAD)</Label>
                    <Input id="pdf-acompte" type="number" min="0" step="any"
                           value={customAcompte} onChange={e => setCustomAcompte(e.target.value)} />
                  </div>
                )}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setPdfTarget(null)}>Annuler</Button>
            <Button onClick={() => handleGenererPdf(pdfTarget)}>
              <FileText /> Générer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {devis.length === 0 ? (
        <EmptyState
          icon={FileStack}
          title="Aucun devis"
          description="Créez votre premier devis depuis le générateur solaire."
          action={<Button onClick={openNew}><Plus /> Nouveau devis</Button>}
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
                  <th>Créé le</th>
                  <th>Validité</th>
                  <th className="ta-right">Total TTC</th>
                  <th>Statut</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {devis.map(d => {
                  // Expiration calculée à la volée (T7) : un devis en attente dont la
                  // date de validité est dépassée s'affiche « Expiré » sans changer
                  // son statut stocké ni l'étape du lead.
                  const effStatut = d.is_expired ? 'expire' : d.statut
                  const isGenerating = pdfGenerating[d.id]
                  const isDownloading = pdfDownloading[d.id]
                  return (
                    <tr key={d.id}>
                      <td>
                        <strong>{d.reference}</strong>
                        {d.version > 1 && (
                          <Badge tone="primary" className="ml-1.5">v{d.version}</Badge>
                        )}
                        {d.superseded_by_ref && (
                          <div className="mt-0.5 text-xs text-warning">
                            remplacé par {d.superseded_by_ref}
                          </div>
                        )}
                      </td>
                      <td data-label="Client">
                        {d.client_nom ?? '—'}
                        {d.lead && (
                          <div className="mt-1">
                            <button
                              type="button"
                              title="Ouvrir le lead lié"
                              onClick={() => navigate(`/crm/leads?lead=${d.lead}`)}
                              className="inline-flex items-center gap-1 rounded-full border border-warning/40 bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning hover:bg-warning/20"
                            >
                              ↗ {d.lead_nom ?? 'Lead'}
                            </button>
                          </div>
                        )}
                      </td>
                      <td data-label="Créé le">{new Date(d.date_creation).toLocaleDateString('fr-FR')}</td>
                      <td className="m-hide">
                        {d.date_validite
                          ? new Date(d.date_validite).toLocaleDateString('fr-FR')
                          : '—'}
                      </td>
                      <td className="ta-right tabular-nums" data-label="Total TTC">
                        {(d.total_affiche ?? d.total_ttc) != null
                          ? formatMAD(d.total_affiche ?? d.total_ttc)
                          : '—'}
                        {d.nb_options === 2 && (
                          <Badge tone="warning" className="ml-1.5"
                                 title="Devis à deux options — total affiché : option 1 (sans batterie), remise incluse">
                            2 options
                          </Badge>
                        )}
                        {d.solde && (
                          <div className="mt-1 text-xs text-muted-foreground">
                            Facturé {d.solde.facture} / Payé {d.solde.paye} / Restant {d.solde.restant} MAD
                          </div>
                        )}
                      </td>
                      <td data-label="Statut">
                        <StatusPill status={effStatut} label={STATUT_DISPLAY[effStatut] ?? STATUT_DISPLAY.brouillon} />
                        {d.statut === 'accepte' && d.option_acceptee && (
                          <div className="mt-1 text-xs text-success">
                            Option : {d.option_acceptee === 'avec_batterie' ? 'Avec batterie' : 'Sans batterie'}
                          </div>
                        )}
                      </td>
                      <td>
                        <div className="flex flex-wrap items-center gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openEdit(d)}
                            disabled={d.statut !== 'brouillon'}
                            title={d.statut === 'brouillon'
                              ? 'Ouvrir dans le générateur'
                              : 'Devis envoyé/clôturé — non modifiable (dupliquez-le depuis le générateur si besoin)'}
                          >
                            Éditer
                          </Button>
                          {d.is_active && d.statut !== 'brouillon' && (
                            <Button
                              size="sm"
                              variant="outline"
                              title="Créer une nouvelle version (v2, v3…) de ce devis"
                              onClick={() => {
                                ventesApi.reviserDevis(d.id)
                                  .then(() => dispatch(fetchDevis()))
                                  .catch(() => {})
                              }}
                            >
                              Réviser
                            </Button>
                          )}
                          {role === 'admin' && d.statut === 'brouillon'
                            && parseFloat(d.remise_globale) > 0 && !d.remise_approuvee && (
                            <Button
                              size="sm"
                              variant="outline"
                              title="Approuver la remise (autorise l'envoi si au-dessus du seuil)"
                              onClick={() => {
                                ventesApi.approuverRemise(d.id)
                                  .then(() => dispatch(fetchDevis())).catch(() => {})
                              }}
                            >
                              Approuver remise
                            </Button>
                          )}
                          {canDelete && (
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  loading={deletingId === d.id}
                                  className="border-destructive/40 text-destructive hover:bg-destructive/10"
                                  title="Supprimer ce devis"
                                >
                                  Supprimer
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Supprimer le devis {d.reference} ?</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    Cette action est définitive et irréversible.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Annuler</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => handleDelete(d)}>Supprimer</AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          )}

                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openPdfModal(d)}
                            loading={isGenerating}
                            title="Générer le PDF (choix du format)"
                          >
                            <FileText /> PDF
                          </Button>
                          {d.fichier_pdf && (
                            <Button
                              size="sm"
                              variant="success"
                              onClick={() => handleTelechargerPdf(d)}
                              loading={isDownloading}
                              title="Télécharger le dernier PDF généré"
                            >
                              <FileDown />
                            </Button>
                          )}

                          {d.statut === 'envoye' && (
                            <Button
                              size="sm"
                              title="Marquer accepté (date + nom + option) — déclenche la création du chantier"
                              onClick={() => {
                                // A1 — pour un devis à deux options, demander
                                // l'option retenue (Sans / Avec batterie) AVANT le
                                // reste. « OK » = Avec batterie, « Annuler » = Sans.
                                let option = ''
                                if (d.nb_options === 2) {
                                  const avec = window.confirm(
                                    `Devis ${d.reference} — option choisie par le client ?\n\n`
                                    + '« OK » = Avec batterie\n« Annuler » = Sans batterie')
                                  option = avec ? 'avec_batterie' : 'sans_batterie'
                                }
                                const nom = window.prompt(
                                  `Devis ${d.reference} — nom de la personne qui accepte :`, '')
                                if (nom === null) return
                                const date = window.prompt(
                                  "Date d'acceptation (AAAA-MM-JJ) :",
                                  new Date().toISOString().slice(0, 10))
                                if (date === null) return
                                ventesApi.accepterDevis(d.id, { nom, date, option })
                                  .then(() => dispatch(fetchDevis()))
                                  .catch(err => alert(
                                    err?.response?.data?.detail ?? 'Acceptation impossible.'))
                              }}
                            >
                              <Check /> Accepter
                            </Button>
                          )}

                          {d.statut === 'accepte' && (
                            <Button
                              size="sm"
                              variant="success"
                              onClick={() => handleConvertBC(d)}
                              loading={convertingId === d.id}
                              title="Convertir en bon de commande"
                            >
                              <ArrowRight /> BC
                            </Button>
                          )}

                          {d.statut === 'accepte' && (
                            <Button
                              size="sm"
                              variant={d.chantier ? 'outline' : 'default'}
                              onClick={() => handleChantier(d)}
                              loading={chantierBusy === d.id}
                              title={d.chantier
                                ? `Ouvrir le chantier ${d.chantier.reference}`
                                : 'Créer le chantier à partir de ce devis'}
                            >
                              <HardHat /> {d.chantier ? 'Voir le chantier' : 'Créer le chantier'}
                            </Button>
                          )}

                          {/* « Générer facture » TOUJOURS visible, pour montrer que
                              c'est ici qu'un devis devient des factures. Désactivé
                              tant que le devis n'est pas « Accepté », avec un indice
                              VISIBLE (pas seulement au survol → lisible sur mobile). */}
                          {d.statut !== 'accepte' ? (
                            <div className="flex flex-col gap-0.5">
                              <Button size="sm" variant="outline" disabled>
                                Générer facture
                              </Button>
                              <span className="max-w-[190px] text-xs leading-tight text-muted-foreground">
                                Passez le devis en « Accepté » pour générer les factures.
                              </span>
                            </div>
                          ) : d.solde && d.solde.tranches_facturees >= d.solde.tranches_total ? (
                            <Button size="sm" variant="outline" disabled
                                    title="Toutes les tranches ont été facturées">
                              Échéancier complet
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              onClick={() => handleGenererFacture(d)}
                              loading={factureGenId === d.id}
                              title="Générer la prochaine tranche de facture"
                            >
                              Générer facture
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
