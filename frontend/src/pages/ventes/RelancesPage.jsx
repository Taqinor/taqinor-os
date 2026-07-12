import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  PartyPopper, FileText, MessageCircle, Mail, History, ReceiptText, MoreHorizontal,
} from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import PaiementDialog from './PaiementDialog'
import { openPdfBlob } from '../../utils/pdfBlob'
import {
  Button, Badge, Card, EmptyState, Spinner, Checkbox, Input,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Label, Textarea,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel,
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from '../../ui'
import { formatMAD, formatDateTime, toNumber, normalizeMaPhone } from '../../lib/format'

// Ajoute n jours à aujourd'hui (date ISO AAAA-MM-JJ).
function todayPlus(days) {
  const d = new Date()
  d.setDate(d.getDate() + (Number(days) || 0))
  return d.toISOString().slice(0, 10)
}

// Balance âgée : libellé du bucket d'ancienneté dérivé des jours de retard,
// cohérent avec /reporting/balance-agee (0–30 / 31–60 / 61–90 / 90+).
function ageBucket(joursRetard) {
  const jr = Number(joursRetard) || 0
  if (jr <= 0) return null
  if (jr <= 30) return '0–30 j'
  if (jr <= 60) return '31–60 j'
  if (jr <= 90) return '61–90 j'
  return '90+ j'
}

export default function RelancesPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [target, setTarget] = useState(null)  // facture being relancée
  // VX230 — encaisser LÀ où on chasse l'impayé : la facture ciblée par la modale
  // de paiement PARTAGÉE (PaiementDialog), sans quitter la vue de recouvrement.
  const [payTarget, setPayTarget] = useState(null)
  const [note, setNote] = useState('')
  const [prochaine, setProchaine] = useState('')  // date de prochaine relance
  const [busy, setBusy] = useState(false)
  const [niveauFilter, setNiveauFilter] = useState('')  // '' = tous
  // VX112 — pré-filtre client depuis le drill-down de la balance âgée
  // (?client=<id> ; miroir du ?produit= de MouvementsPage), filtrage
  // d'affichage sur les lignes déjà chargées, aucun endpoint dédié.
  const [searchParams] = useSearchParams()
  const clientFilter = searchParams.get('client')
  const [sortByDu, setSortByDu] = useState(false)  // tri par montant dû décroissant
  const [selected, setSelected] = useState({})  // {id: true} pour la relance en lot
  const [bulkBusy, setBulkBusy] = useState(false)
  const [histTarget, setHistTarget] = useState(null)  // facture dont on voit l'historique
  const [histRows, setHistRows] = useState([])
  const [histLoading, setHistLoading] = useState(false)
  // ── Rappel WhatsApp : langue (L851), busy par facture (L857), aperçu (L852) ──
  const [waLangue, setWaLangue] = useState('fr')
  const [waBusy, setWaBusy] = useState({})
  const [waPreview, setWaPreview] = useState(null) // { reference, message, url, wa_url }

  const load = () => {
    setLoading(true)
    ventesApi.getRelances()
      .then(r => setRows(r.data)).catch(() => {}).finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  // Ouvre la modale de relance en pré-remplissant le niveau courant, la note
  // depuis le message configuré du niveau et la date de prochaine relance
  // (aujourd'hui + délai du niveau suivant, sinon +7 j par défaut).
  const openRelancer = (r) => {
    setTarget(r)
    setNote(r.niveau?.message || '')
    const delaiSuivant = r.niveau_suivant?.delai_jours
    setProchaine(delaiSuivant != null ? todayPlus(delaiSuivant) : todayPlus(7))
  }

  const relancer = async () => {
    setBusy(true)
    try {
      await ventesApi.relancerFacture(target.id, {
        niveau: target.niveau?.ordre, note,
        prochaine_relance: prochaine || undefined,
      })
      setTarget(null); setNote(''); setProchaine(''); load()
    } catch { /* */ } finally { setBusy(false) }
  }

  // Relance en lot : consigne une relance pour chaque facture cochée, au niveau
  // courant de chacune (sans note ni envoi forcé — comportement par défaut).
  const doConsigner = async (ids) => {
    for (const id of ids) {
      const r = rows.find(x => String(x.id) === String(id))
      await ventesApi.relancerFacture(id, { niveau: r?.niveau?.ordre })
    }
  }
  // « Consigner uniquement » — comportement historique, byte-identique.
  const relancerSelection = async () => {
    const ids = Object.keys(selected).filter(id => selected[id])
    if (ids.length === 0) return
    if (!window.confirm(`Consigner une relance pour ${ids.length} facture(s) ?`)) return
    setBulkBusy(true)
    try {
      await doConsigner(ids)
      setSelected({}); load()
    } catch { /* */ } finally { setBulkBusy(false) }
  }

  // VX116 — file d'aperçus WhatsApp SÉQUENTIELS après consignation en lot.
  // JAMAIS d'envoi wa.me sans clic explicite (règle manuel-wa.me du fondateur) :
  // on montre le MÊME aperçu-puis-confirmer par client, l'un après l'autre.
  const [waQueue, setWaQueue] = useState([]) // factures restant à prévisualiser
  const [waQueueIdx, setWaQueueIdx] = useState(0)
  const inWaQueue = waQueue.length > 0

  const loadWaPreviewFor = async (r) => {
    if (!r) return
    try {
      const res = await ventesApi.whatsappFacture(r.id, {
        modele: 'relance', langue: waLangue,
      })
      setWaPreview({
        reference: r.reference,
        message: res.data?.message ?? '',
        url: res.data?.url ?? '',
        wa_url: res.data?.wa_url ?? '',
      })
    } catch {
      // Un aperçu indisponible ne bloque pas la file : on l'affiche vide (sans
      // wa_url, donc « Ouvrir WhatsApp » reste désactivé) et l'utilisateur passe.
      setWaPreview({ reference: r.reference, message: 'Aperçu indisponible pour cette facture.', url: '', wa_url: '' })
    }
  }

  const endWaQueue = () => { setWaQueue([]); setWaQueueIdx(0); setWaPreview(null); load() }

  const advanceWaQueue = async () => {
    const nextIdx = waQueueIdx + 1
    if (nextIdx >= waQueue.length) { endWaQueue(); return }
    setWaQueueIdx(nextIdx)
    await loadWaPreviewFor(waQueue[nextIdx])
  }

  // « Consigner + aperçu WhatsApp pour chacun » : consigne d'abord (comme
  // ci-dessus), puis démarre la séquence d'aperçus par client.
  const relancerSelectionAvecWhatsapp = async () => {
    const ids = Object.keys(selected).filter(id => selected[id])
    if (ids.length === 0) return
    if (!window.confirm(
      `Consigner une relance pour ${ids.length} facture(s), puis prévisualiser un message WhatsApp pour chacune ?`)) return
    const facturesSel = ids
      .map(id => rows.find(x => String(x.id) === String(id)))
      .filter(Boolean)
    setBulkBusy(true)
    try {
      await doConsigner(ids)
      setSelected({})
      setWaQueue(facturesSel)
      setWaQueueIdx(0)
      await loadWaPreviewFor(facturesSel[0])
    } catch { /* */ } finally { setBulkBusy(false) }
  }

  // Historique des relances déjà consignées pour une facture.
  const openHistorique = async (r) => {
    setHistTarget(r); setHistRows([]); setHistLoading(true)
    try {
      const res = await ventesApi.getRelancesFacture(r.id)
      setHistRows(res.data)
    } catch { /* */ } finally { setHistLoading(false) }
  }

  // Relevé de compte client (PDF) — en plus de la balance âgée.
  const releve = async (r) => {
    if (!r.client_id) { alert('Client introuvable pour cette facture.'); return }
    try {
      const res = await ventesApi.getClientRelevePdf(r.client_id)
      openPdfBlob(res.data, `Releve_${r.client_nom || r.client_id}.pdf`)
    } catch { alert('Relevé indisponible.') }
  }

  const toggleSel = (id) => setSelected(s => ({ ...s, [id]: !s[id] }))
  const exclure = async (r) => {
    if (!window.confirm('Exclure cette facture des relances ?')) return
    try { await ventesApi.exclureRelance(r.id, true); load() } catch { /* */ }
  }
  const lettre = async (r) => {
    try {
      const res = await ventesApi.getLettreRelancePdf(r.id)
      openPdfBlob(res.data, `Relance_${r.reference}.pdf`)
    } catch { alert('PDF indisponible.') }
  }
  // Lettre de relance premium (langage visuel du devis) — niveau 1/2/3.
  const lettrePremium = async (r, niveau) => {
    try {
      const res = await ventesApi.getLettreRelancePremiumPdf(r.id, niveau)
      openPdfBlob(res.data, `Relance_${r.reference}_N${niveau}.pdf`)
    } catch { alert('PDF indisponible.') }
  }
  // Rappel de paiement par WhatsApp : construit le message « relance » côté
  // serveur (FR/Darija) puis montre un aperçu (message + lien public) avant
  // d'ouvrir wa.me ; le POST consigne aussi l'action au chatter (L856).
  const whatsapp = async (r) => {
    setWaBusy(prev => ({ ...prev, [r.id]: true }))
    try {
      const res = await ventesApi.whatsappFacture(r.id, {
        modele: 'relance', langue: waLangue,
      })
      setWaPreview({
        reference: r.reference,
        message: res.data?.message ?? '',
        url: res.data?.url ?? '',
        wa_url: res.data?.wa_url ?? '',
      })
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Envoi WhatsApp impossible.')
    } finally {
      setWaBusy(prev => ({ ...prev, [r.id]: false }))
    }
  }

  // Ouvre wa.me après confirmation de l'aperçu. En file (VX116), avance vers le
  // client suivant ; sinon ferme simplement l'aperçu.
  const ouvrirWhatsApp = () => {
    if (waPreview?.wa_url) window.open(waPreview.wa_url, '_blank', 'noopener')
    if (inWaQueue) { advanceWaQueue() } else { setWaPreview(null) }
  }

  // Niveaux distincts présents (pour le filtre).
  const niveaux = useMemo(() => {
    const map = new Map()
    rows.forEach(r => { if (r.niveau) map.set(r.niveau.ordre, r.niveau.nom) })
    return [...map.entries()].sort((a, b) => a[0] - b[0])
  }, [rows])

  // Lignes affichées : pré-filtre client (URL) + filtre par niveau courant +
  // tri optionnel par dû.
  const displayed = useMemo(() => {
    let list = rows
    if (clientFilter) {
      list = list.filter(r => String(r.client_id) === String(clientFilter))
    }
    if (niveauFilter === 'none') list = list.filter(r => !r.niveau)
    else if (niveauFilter !== '') {
      list = list.filter(r => r.niveau && String(r.niveau.ordre) === niveauFilter)
    }
    if (sortByDu) {
      list = [...list].sort(
        (a, b) => (toNumber(b.montant_du) || 0) - (toNumber(a.montant_du) || 0))
    }
    return list
  }, [rows, clientFilter, niveauFilter, sortByDu])

  // Encours total à recouvrer (somme des montants dus affichés).
  const totalDu = useMemo(
    () => displayed.reduce((s, r) => s + (toNumber(r.montant_du) || 0), 0),
    [displayed])

  const selCount = useMemo(
    () => Object.values(selected).filter(Boolean).length, [selected])
  const allSelected = displayed.length > 0 && displayed.every(r => selected[r.id])
  const toggleAll = () => {
    if (allSelected) { setSelected({}); return }
    const next = {}
    displayed.forEach(r => { next[r.id] = true })
    setSelected(next)
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Relances / Impayés
          <Badge tone="warning" className="ml-2 align-middle">{rows.length}</Badge>
        </h2>
      </div>
      <p className="mb-3 text-sm text-muted-foreground">
        Vue de recouvrement — consigner et imprimer uniquement. Aucun envoi
        automatique (email/SMS) n'est effectué.
      </p>

      {clientFilter && (
        <div className="mb-3">
          <Badge tone="info" className="align-middle">
            Filtré sur un client{' '}
            <Link to="/ventes/relances" className="ml-1 underline">(effacer)</Link>
          </Badge>
        </div>
      )}

      {!loading && rows.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <Card className="px-4 py-2 text-sm">
            <span className="text-muted-foreground">Total à recouvrer : </span>
            <strong className="tabular-nums">{formatMAD(totalDu)}</strong>
            <span className="text-muted-foreground"> sur {displayed.length} facture{displayed.length > 1 ? 's' : ''}</span>
          </Card>
          {/* VX142(c) — seul <select> HTML natif de pages/ventes/ : remplacé par
              le composant Select tokenisé (Radix). Valeur vide « Tous » mappée
              sur 'all' (Select n'accepte pas de valeur vide). */}
          <label className="flex items-center gap-1.5 text-sm">
            Niveau&nbsp;:
            <Select
              value={niveauFilter === '' ? 'all' : niveauFilter}
              onValueChange={v => setNiveauFilter(v === 'all' ? '' : v)}
            >
              <SelectTrigger className="w-40" aria-label="Filtrer par niveau de relance">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous</SelectItem>
                <SelectItem value="none">Sans niveau</SelectItem>
                {niveaux.map(([ordre, nom]) => (
                  <SelectItem key={ordre} value={String(ordre)}>{nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
          {/* VX116 — la relance en lot propose « Consigner uniquement »
              (inchangé) ou « Consigner + aperçu WhatsApp pour chacun » (aperçu
              séquentiel par client, jamais d'auto-envoi). */}
          {selCount > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" loading={bulkBusy}>
                  Relancer la sélection ({selCount})
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem onSelect={relancerSelection}>
                  Consigner uniquement
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={relancerSelectionAvecWhatsapp}>
                  Consigner + aperçu WhatsApp pour chacun
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          {/* L851 — langue des rappels WhatsApp (FR par défaut). */}
          <div role="group" aria-label="Langue des rappels WhatsApp"
               className="ml-auto inline-flex items-center gap-1"
               title="Langue du rappel « WhatsApp »">
            <MessageCircle className="size-4 text-muted-foreground" />
            {[['fr', 'FR'], ['darija', 'Darija']].map(([val, label]) => (
              <Button key={val} size="sm"
                      variant={waLangue === val ? 'default' : 'outline'}
                      aria-pressed={waLangue === val}
                      onClick={() => setWaLangue(val)}>
                {label}
              </Button>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Spinner /> Chargement…
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={PartyPopper}
          title="Aucune facture impayée"
          description="Toutes les factures sont à jour — rien à relancer."
          className="mt-1"
        />
      ) : (
        <Card className="mt-1 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="w-8">
                    <Checkbox checked={allSelected} onCheckedChange={toggleAll}
                              aria-label="Tout sélectionner" />
                  </th>
                  <th>Facture</th><th>Client</th><th>Échéance</th>
                  <th
                    className="ta-right cursor-pointer select-none"
                    onClick={() => setSortByDu(v => !v)}
                    title="Trier par montant dû décroissant"
                  >
                    Dû{sortByDu ? ' ↓' : ''}
                  </th>
                  <th>Retard</th><th>Âge</th><th>Niveau</th>
                  <th>Relances</th><th></th>
                </tr>
              </thead>
              <tbody>
                {displayed.map(r => (
                  <tr key={r.id}>
                    <td>
                      <Checkbox checked={!!selected[r.id]}
                                onCheckedChange={() => toggleSel(r.id)}
                                aria-label={`Sélectionner ${r.reference}`} />
                    </td>
                    <td><strong>{r.reference}</strong></td>
                    <td data-label="Client">{r.client_nom}</td>
                    <td data-label="Échéance"
                        className={r.jours_retard > 0 ? 'font-semibold text-destructive' : undefined}>
                      {r.date_echeance || '—'}
                    </td>
                    <td className="ta-right tabular-nums" data-label="Dû">{formatMAD(r.montant_du)}</td>
                    <td data-label="Retard"
                        className={r.jours_retard > 0 ? 'text-destructive' : undefined}>
                      {r.jours_retard > 0
                        ? `${r.jours_retard} j`
                        : <span className="text-muted-foreground">À échoir</span>}
                    </td>
                    <td className="m-hide">{ageBucket(r.jours_retard)
                      ? <Badge tone="warning">{ageBucket(r.jours_retard)}</Badge>
                      : '—'}</td>
                    <td data-label="Niveau">{r.niveau ? <Badge tone="warning">{r.niveau.nom}</Badge> : '—'}</td>
                    <td className="m-hide">{r.nb_relances}</td>
                    <td className="ta-right">
                      {/* VX20 — « soupe d'actions » réduite : Relancer (action
                          principale) + WhatsApp (canal de communication le
                          plus fréquent) restent des boutons directs ; le
                          reste (Historique, Lettre, Relevé, Relance premium,
                          Exclure) vit dans un seul menu « Plus ». */}
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <Button size="sm" onClick={() => openRelancer(r)}>Relancer</Button>
                        {/* VX230 — « Encaisser » : ouvre la MÊME modale de
                            paiement que FactureList, sur place. Le chèque
                            décroché après la relance s'enregistre sans quitter
                            la vue de recouvrement. */}
                        <Button size="sm" variant="outline"
                                onClick={() => setPayTarget(r)}
                                title="Enregistrer un paiement sur cette facture">
                          <ReceiptText /> Encaisser
                        </Button>
                        <Button size="sm" variant="outline"
                                loading={!!waBusy[r.id]}
                                disabled={!!waBusy[r.id] || !normalizeMaPhone(r.client_telephone)}
                                onClick={() => whatsapp(r)}
                                title={!normalizeMaPhone(r.client_telephone)
                                  ? 'Numéro invalide'
                                  : 'Rappel de paiement par WhatsApp'}>
                          <MessageCircle /> {waBusy[r.id] ? 'Préparation…' : 'WhatsApp'}
                        </Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button size="sm" variant="ghost" aria-label={`Plus d'actions — ${r.reference}`}>
                              <MoreHorizontal className="size-4" aria-hidden="true" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuLabel>Plus d'actions</DropdownMenuLabel>
                            <DropdownMenuItem onSelect={() => openHistorique(r)}>
                              <History className="size-3.5" aria-hidden="true" />
                              Historique
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => lettre(r)}>
                              <FileText className="size-3.5" aria-hidden="true" />
                              Lettre
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => releve(r)}>
                              <ReceiptText className="size-3.5" aria-hidden="true" />
                              Relevé de compte client (PDF)
                            </DropdownMenuItem>
                            <DropdownMenuLabel>Relance premium</DropdownMenuLabel>
                            <DropdownMenuItem onSelect={() => lettrePremium(r, 1)}>
                              <Mail className="size-3.5" aria-hidden="true" />
                              Niveau 1 — courtois
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => lettrePremium(r, 2)}>
                              <Mail className="size-3.5" aria-hidden="true" />
                              Niveau 2 — ferme
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => lettrePremium(r, 3)}>
                              <Mail className="size-3.5" aria-hidden="true" />
                              Niveau 3 — mise en demeure
                            </DropdownMenuItem>
                            <DropdownMenuItem destructive onSelect={() => exclure(r)}>
                              Exclure
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* ── L852 — Aperçu du rappel WhatsApp avant ouverture de wa.me ──
          VX116 — en file (relance en lot + WhatsApp), le titre montre la
          progression et « Annuler » clôt toute la séquence. */}
      <Dialog open={!!waPreview}
              onOpenChange={(o) => { if (!o) { if (inWaQueue) endWaQueue(); else setWaPreview(null) } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Aperçu du rappel WhatsApp — {waPreview?.reference}
              {inWaQueue ? ` (${waQueueIdx + 1}/${waQueue.length})` : ''}
            </DialogTitle>
            <DialogDescription>
              {waLangue === 'darija' ? 'Variante Darija' : 'Variante Français'}
              {' '}— vérifiez le texte et le lien, puis ouvrez WhatsApp.
            </DialogDescription>
          </DialogHeader>
          <pre className="m-0 whitespace-pre-wrap break-words rounded-lg bg-muted p-3 text-sm"
               style={{ fontFamily: 'inherit' }}>
            {waPreview?.message}
          </pre>
          {waPreview?.url && (
            <p className="mt-2 break-words text-xs text-muted-foreground">
              Lien public : {waPreview.url}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost"
                    onClick={() => { if (inWaQueue) endWaQueue(); else setWaPreview(null) }}>
              {inWaQueue ? 'Arrêter' : 'Annuler'}
            </Button>
            {inWaQueue && (
              <Button type="button" variant="outline" onClick={advanceWaQueue}>
                Passer
              </Button>
            )}
            <Button type="button" variant="success" disabled={!waPreview?.wa_url}
                    onClick={ouvrirWhatsApp}>
              <MessageCircle /> Ouvrir WhatsApp
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!target} onOpenChange={(o) => { if (!o) setTarget(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Consigner une relance — {target?.reference}</DialogTitle>
            <DialogDescription>
              {target?.niveau ? `Niveau courant : ${target.niveau.nom}. ` : ''}
              Cette action journalise la relance (aucun envoi).
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="relance-note">Note (appel, courrier remis…)</Label>
              <Textarea id="relance-note" rows={3} value={note}
                        onChange={e => setNote(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="relance-prochaine">Prochaine relance</Label>
              <Input id="relance-prochaine" type="date" value={prochaine}
                     onChange={e => setProchaine(e.target.value)} />
              {target?.niveau_suivant && (
                <p className="text-xs text-muted-foreground">
                  Proposée d'après le niveau suivant
                  ({target.niveau_suivant.nom}, J+{target.niveau_suivant.delai_jours}).
                </p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setTarget(null)}>Annuler</Button>
            <Button loading={busy} onClick={relancer}>Consigner</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Modale historique des relances consignées ── */}
      <Dialog open={!!histTarget} onOpenChange={(o) => { if (!o) setHistTarget(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Historique des relances — {histTarget?.reference}</DialogTitle>
            <DialogDescription>Relances déjà consignées (aucun envoi).</DialogDescription>
          </DialogHeader>
          {histLoading ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
              <Spinner /> Chargement…
            </div>
          ) : histRows.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">Aucune relance consignée.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {histRows.map(h => (
                <li key={h.id} className="border-b pb-2 last:border-b-0">
                  <div className="flex justify-between gap-3">
                    <span className="font-medium">
                      {h.date ? formatDateTime(h.date) : '—'}
                      {h.niveau_nom ? ` · ${h.niveau_nom}` : ''}
                    </span>
                    <span className="text-muted-foreground">{h.created_by_nom || '—'}</span>
                  </div>
                  {h.note && <p className="mt-0.5 text-muted-foreground">{h.note}</p>}
                </li>
              ))}
            </ul>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setHistTarget(null)}>Fermer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* VX230 — modale de paiement PARTAGÉE (extraite de FactureList). Sur
          « onSaved », on recharge la liste des impayés : une facture soldée en
          disparaît. */}
      <PaiementDialog
        facture={payTarget}
        onOpenChange={(o) => { if (!o) setPayTarget(null) }}
        onSaved={load}
      />
    </div>
  )
}
