import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  Plus, FileText, Undo2, Package, Trash2, Copy, RotateCcw, Receipt, LayoutTemplate,
} from 'lucide-react'
import stockApi from '../../api/stockApi'
import messagesApi from '../../api/messagesApi'
import { formatMAD } from '../../lib/format'
import BcfProduitPicker from './BcfProduitPicker'
import ProduitQuickCreateModal from '../../components/ProduitQuickCreateModal'
import { useCanCreateProduit } from '../../hooks/useHasPermission'
import { filenameFromResponse } from '../../utils/downloadBlob'
import { ouvrirPdfBlob, estBlobPdf, messageErreurBlob } from '../../utils/pdfBlob'
import {
  Button, IconButton, StatusPill, DataTable,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Input, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { buildCopyTSVAction } from '../../ui/datatable/BulkActionBar'
import {
  BCF_STATUTS,
  bcfStatutLabel,
  totalAchat,
  quantiteRestante,
  buildReceptionPayload,
  avancementReception,
  bcfDateAffichee,
  aLignePrixZero,
  nbEnvoyesNonRecus,
} from '../../features/stock/procurement'

// Page de gestion des bons de commande FOURNISSEUR (achats — N11).
// Le prix d'ACHAT est INTERNE : cette page n'est jamais un document client.

// Traduit une erreur serveur DRF en phrase FR lisible (jamais de JSON brut).
function frBcfError(err, fallback = 'Une erreur est survenue. Réessayez.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  if (Array.isArray(data.non_field_errors) && data.non_field_errors[0]) return data.non_field_errors[0]
  for (const v of Object.values(data)) {
    const m = Array.isArray(v) ? v[0] : v
    if (typeof m === 'string') return m
  }
  return fallback
}


const fmtMad = (v) => formatMAD(v)
const fmtDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

// ── N19 — Modal de retour fournisseur (créé + validé depuis un BCF) ──────────
// La validation décrémente le stock. Lien automatique vers le BCF d'origine.
function RetourModal({ bcf, onClose, onDone }) {
  const [saisies, setSaisies] = useState({})   // { ligneId: { qte, motif } }
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const lignes = bcf?.lignes ?? []

  const setLigne = (id, patch) =>
    setSaisies((s) => ({ ...s, [id]: { ...(s[id] ?? {}), ...patch } }))

  const submit = async () => {
    setError(null)
    const payloadLignes = lignes
      .map((l) => {
        const s = saisies[l.id] ?? {}
        // Plafonne au reçu : on ne retourne jamais plus que ce qui a été reçu.
        const qte = Math.min(Math.floor(Number(s.qte)), Number(l.quantite_recue) || 0)
        return Number.isFinite(qte) && qte > 0
          ? { produit: l.produit, quantite: qte, motif: s.motif || '' }
          : null
      })
      .filter(Boolean)
    if (payloadLignes.length === 0) {
      setError('Saisissez au moins une quantité à retourner.'); return
    }
    setBusy(true)
    try {
      const r = await stockApi.createRetourFournisseur({
        fournisseur: bcf.fournisseur, bon_commande: bcf.id,
        lignes: payloadLignes,
      })
      await stockApi.validerRetourFournisseur(r.data.id)
      onDone?.('Retour fournisseur enregistré — le stock a été décrémenté.')
      onClose()
    } catch (err) {
      setError(frBcfError(err, 'Échec du retour fournisseur.'))
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Retour fournisseur — {bcf.reference}</DialogTitle>
          <DialogDescription>
            Articles défectueux ou erronés. À la validation, le stock est décrémenté.
            Donnée interne (prix d&apos;achat jamais client-facing).
          </DialogDescription>
        </DialogHeader>

        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[34rem] text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Produit</th>
                <th className="px-3 py-2 text-left font-semibold">Reçu</th>
                <th className="px-3 py-2 text-left font-semibold">À retourner</th>
                <th className="px-3 py-2 text-left font-semibold">Motif</th>
              </tr>
            </thead>
            <tbody>
              {lignes.map((l) => (
                <tr key={l.id} className="border-t border-border">
                  <td className="px-3 py-2">{l.produit_nom}</td>
                  <td className="px-3 py-2 tabular-nums">{l.quantite_recue}</td>
                  <td className="px-3 py-2">
                    <Input type="number" min="0" max={l.quantite_recue ?? 0} inputMode="numeric" className="h-9 w-24"
                           value={saisies[l.id]?.qte ?? ''}
                           onChange={(e) => setLigne(l.id, { qte: e.target.value })} />
                    {Number(saisies[l.id]?.qte) > (Number(l.quantite_recue) || 0) && (
                      <p className="mt-1 text-xs text-warning">
                        Max {l.quantite_recue ?? 0} (quantité reçue)
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <Input className="h-9"
                           value={saisies[l.id]?.motif ?? ''}
                           placeholder="ex. cassé à la livraison"
                           onChange={(e) => setLigne(l.id, { motif: e.target.value })} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
          <Button type="button" loading={busy} onClick={submit}>
            {busy ? 'Enregistrement…' : 'Valider le retour'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── ZPUR11 — Modal d'annulation : motif OBLIGATOIRE (le backend refuse un
// motif vide en 400). Export nommé : testé directement.
export function MotifAnnulationModal({ onClose, onConfirm, busy }) {
  const [motif, setMotif] = useState('')
  const [error, setError] = useState(null)

  const confirmer = () => {
    if (!motif.trim()) { setError('Le motif est obligatoire.'); return }
    setError(null)
    onConfirm(motif.trim())
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Annuler le bon de commande</DialogTitle>
          <DialogDescription>
            Un motif d&apos;annulation est requis (tracé, horodaté).
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="bcf-motif-annulation">Motif</label>
          <Textarea id="bcf-motif-annulation" rows={3} value={motif}
                    onChange={(e) => setMotif(e.target.value)}
                    placeholder="ex. commande passée par erreur, fournisseur indisponible…" />
        </div>
        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
          <Button type="button" variant="destructive" loading={busy} onClick={confirmer}>
            {busy ? '…' : 'Confirmer l\'annulation'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Modal de création / consultation / réception d'un BCF ──
// Export nommé : testé directement (QS1 — bouton « PDF (interne) »).
export function BcfDetail({ bcf, fournisseurs, produits, onClose, onSaved }) {
  const isNew = !bcf?.id
  const statut = bcf?.statut ?? 'brouillon'
  const editableLignes = isNew || statut === 'brouillon'
  // QS2 — « + Nouveau produit » : réservé à Directeur + Commercial responsable
  // (hook QG5 ; backend QG4 est la garde qui compte). Réutilise la modale QG6.
  const canCreateProduit = useCanCreateProduit()

  const [fournisseur, setFournisseur] = useState(bcf?.fournisseur ?? '')
  const [dateCommande, setDateCommande] = useState(bcf?.date_commande ?? '')
  const [note, setNote] = useState(bcf?.note ?? '')
  const [lignes, setLignes] = useState(
    (bcf?.lignes ?? []).map((l) => ({ ...l })))
  // ZPUR8 — « Other Information » : acheteur (défaut = créateur côté serveur),
  // référence fournisseur, note de bas de page, incoterm reporté.
  const [acheteur, setAcheteur] = useState(bcf?.acheteur ?? '')
  const [refFournisseur, setRefFournisseur] = useState(bcf?.ref_fournisseur ?? '')
  const [noteBasPage, setNoteBasPage] = useState(bcf?.note_bas_page ?? '')
  const [incoterm, setIncoterm] = useState(bcf?.incoterm ?? '')
  const [membres, setMembres] = useState([])
  // Saisies de réception : { [ligneId]: quantité }
  const [receptions, setReceptions] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [showRetour, setShowRetour] = useState(false)
  const [showAnnuler, setShowAnnuler] = useState(false)
  const [info, setInfo] = useState(null)

  // ZPUR8 — liste des membres de la société pour le sélecteur « acheteur ».
  useEffect(() => {
    messagesApi.listCompanyMembers()
      .then((r) => setMembres(r.data?.results ?? r.data ?? []))
      .catch(() => {})
  }, [])
  // QS2 — produits créés à la volée (fusionnés au catalogue prop, en lecture
  // seule) + la ligne sur laquelle déposer le produit fraîchement créé.
  const [extraProduits, setExtraProduits] = useState([])
  const [quickCreateIdx, setQuickCreateIdx] = useState(null)
  const allProduits = useMemo(
    () => [...(produits ?? []), ...extraProduits], [produits, extraProduits])

  const total = useMemo(() => totalAchat(lignes), [lignes])
  const reception = useMemo(() => avancementReception(bcf?.lignes ?? lignes), [bcf, lignes])
  // Chantier source (BCF issu d'un besoin matériel) : la note contient
  // « chantier <ref> » — on l'extrait pour la mettre en avant (728).
  const chantierRef = useMemo(() => {
    const m = (bcf?.note ?? note ?? '').match(/chantier\s+([A-Za-z0-9\-/]+)/i)
    return m ? m[1] : null
  }, [bcf, note])

  const setLigne = (idx, patch) =>
    setLignes((ls) => ls.map((l, i) => (i === idx ? { ...l, ...patch } : l)))
  const addLigne = () =>
    setLignes((ls) => [...ls, { produit: '', quantite: 1, prix_achat_unitaire: '' }])
  // XPUR16 — ligne libre/service (transport, prestation, frais) : pas de
  // produit catalogue, désignation libre. Compte dans le total/l'approbation/
  // la facturation mais ne génère jamais de mouvement de stock à la réception.
  const addLigneLibre = () =>
    setLignes((ls) => [
      ...ls,
      { produit: '', designation: '', quantite: 1, prix_achat_unitaire: '', sans_stock: true },
    ])
  const removeLigne = (idx) =>
    setLignes((ls) => ls.filter((_, i) => i !== idx))

  // Sélection d'un produit : pré-remplit le prix d'achat U. (interne) depuis le
  // prix_achat catalogue quand la ligne n'en a pas encore — modifiable ensuite.
  const pickProduit = (idx, produitId) => {
    setLignes((ls) => ls.map((l, i) => {
      if (i !== idx) return l
      const next = { ...l, produit: produitId }
      const sansPrix = l.prix_achat_unitaire === '' || l.prix_achat_unitaire == null
      if (sansPrix) {
        const prod = allProduits.find((p) => String(p.id) === String(produitId))
        const cat = prod ? Number(prod.prix_achat) : 0
        if (cat > 0) next.prix_achat_unitaire = String(cat)
      }
      return next
    }))
  }

  // QS2 — produit créé à la volée : l'ajoute au catalogue local, le dépose sur
  // la ligne d'origine et pré-remplit son prix d'achat (interne) depuis
  // `prix_achat` — jamais transmis par le client, renvoyé par le serveur
  // seulement aux rôles autorisés à le voir. On dérive le prix d'achat DIRECTEMENT
  // de l'objet produit renvoyé (pas via allProduits, dont le state n'est pas
  // encore à jour dans ce même tick).
  const onProduitCreatedForLine = (produit) => {
    setExtraProduits((ps) => [...ps, produit])
    const idx = quickCreateIdx
    if (idx != null) {
      setLignes((ls) => ls.map((l, i) => {
        if (i !== idx) return l
        const next = { ...l, produit: String(produit.id) }
        const sansPrix = l.prix_achat_unitaire === '' || l.prix_achat_unitaire == null
        const cat = Number(produit.prix_achat) || 0
        if (sansPrix && cat > 0) next.prix_achat_unitaire = String(cat)
        return next
      }))
    }
    setQuickCreateIdx(null)
  }

  const buildPayload = () => ({
    fournisseur: fournisseur || null,
    date_commande: dateCommande || null,
    note: note || null,
    // ZPUR8 — « Other Information » : acheteur, réf. fournisseur, note de
    // bas de page + report incoterm (édité au document, jamais recalculé).
    acheteur: acheteur || null,
    ref_fournisseur: refFournisseur || null,
    note_bas_page: noteBasPage || null,
    incoterm: incoterm || null,
    // XPUR16 — une ligne libre/service (pas de produit catalogue) est gardée
    // tant qu'elle porte une désignation libre (« Transport Casablanca »…).
    lignes: lignes
      .filter((l) => l.produit || (l.designation ?? '').trim())
      .map((l) => ({
        produit: l.produit || null,
        designation: l.produit ? '' : (l.designation ?? '').trim(),
        quantite: Number(l.quantite) || 0,
        prix_achat_unitaire: l.prix_achat_unitaire === '' || l.prix_achat_unitaire == null
          ? 0 : Number(l.prix_achat_unitaire),
      })),
  })

  const save = async () => {
    setError(null)
    const payload = buildPayload()
    if (!payload.fournisseur) { setError('Choisissez un fournisseur.'); return }
    if (payload.lignes.length === 0) { setError('Ajoutez au moins une ligne.'); return }
    setBusy(true)
    try {
      if (isNew) await stockApi.createBonCommandeFournisseur(payload)
      else await stockApi.updateBonCommandeFournisseur(bcf.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frBcfError(err, "L'enregistrement du bon de commande a échoué."))
    } finally { setBusy(false) }
  }

  const envoyer = async () => {
    // Confirme l'envoi si une ligne a un prix d'achat à 0 (pompes/placeholder).
    if (aLignePrixZero(buildPayload().lignes)
        && !window.confirm('Une ou plusieurs lignes ont un prix d\'achat à 0. Envoyer quand même ?')) {
      return
    }
    setBusy(true); setError(null)
    try {
      // En brouillon, on enregistre d'abord d'éventuelles modifications.
      if (!isNew) await stockApi.updateBonCommandeFournisseur(bcf.id, buildPayload())
      let id = bcf?.id
      if (isNew) {
        const r = await stockApi.createBonCommandeFournisseur(buildPayload())
        id = r.data.id
      }
      await stockApi.envoyerBcf(id)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frBcfError(err, "L'envoi au fournisseur a échoué."))
    } finally { setBusy(false) }
  }

  // QS4 — coordonnées du fournisseur sélectionné (pour griser honnêtement les
  // boutons WhatsApp/email quand le contact manque). On lit la fiche
  // fournisseur du prop `fournisseurs` (FournisseurSerializer expose tel/email).
  const fournisseurObj = useMemo(
    () => (fournisseurs ?? []).find((f) => String(f.id) === String(fournisseur)) ?? null,
    [fournisseurs, fournisseur])
  const fournisseurTel = (fournisseurObj?.telephone ?? '').trim()
  const fournisseurEmail = (fournisseurObj?.email ?? '').trim()

  // QS4 — Envoyer par WhatsApp (QS3) : prépare un lien wa.me prêt à envoyer et
  // marque le BCF « envoyé ». On ouvre WhatsApp dans un nouvel onglet ; le
  // commercial appuie lui-même sur Envoyer (aucun envoi automatique).
  const envoyerWhatsapp = async () => {
    if (isNew || !bcf?.id) { setError('Enregistrez d\'abord le bon de commande.'); return }
    setBusy(true); setError(null)
    try {
      const r = await stockApi.whatsappBcf(bcf.id)
      const waUrl = r.data?.wa_url
      if (waUrl) window.open(waUrl, '_blank', 'noopener')
      setInfo('WhatsApp ouvert — appuyez sur Envoyer dans WhatsApp. Le BCF est marqué « envoyé ».')
      onSaved?.()
    } catch (err) {
      setError(frBcfError(err, "La préparation du message WhatsApp a échoué."))
    } finally { setBusy(false) }
  }

  // QS4 — Envoyer par email (QS3) : envoie le PDF au fournisseur + marque
  // « envoyé ». Confirmation affichée au retour.
  const envoyerEmail = async () => {
    if (isNew || !bcf?.id) { setError('Enregistrez d\'abord le bon de commande.'); return }
    setBusy(true); setError(null)
    try {
      const r = await stockApi.envoyerEmailBcf(bcf.id)
      setInfo(r.data?.detail || 'Email envoyé au fournisseur. Le BCF est marqué « envoyé ».')
      onSaved?.()
    } catch (err) {
      setError(frBcfError(err, "L'envoi de l'email au fournisseur a échoué."))
    } finally { setBusy(false) }
  }

  // Tout recevoir : pré-remplit chaque saisie de réception au reste dû.
  const toutRecevoir = () => {
    const next = {}
    for (const l of bcf?.lignes ?? []) {
      const reste = quantiteRestante(l)
      if (reste > 0) next[l.id] = String(reste)
    }
    setReceptions(next)
  }

  const recevoir = async () => {
    const payload = buildReceptionPayload(bcf.lignes, receptions)
    if (payload.length === 0) { setError('Saisissez au moins une quantité à recevoir.'); return }
    setBusy(true); setError(null)
    try {
      await stockApi.recevoirBcf(bcf.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frBcfError(err, 'La réception a échoué.'))
    } finally { setBusy(false) }
  }

  // ZPUR11 — motif OBLIGATOIRE, saisi via MotifAnnulationModal (le backend
  // refuse un motif vide en 400).
  const annuler = async (motif) => {
    setBusy(true); setError(null)
    try {
      await stockApi.annulerBcf(bcf.id, motif)
      setShowAnnuler(false)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frBcfError(err, "L'annulation a échoué."))
    } finally { setBusy(false) }
  }

  // ZPUR11 — réouvre un BCF ANNULE en BROUILLON (refusé si des réceptions
  // confirmées existent — le backend renvoie alors un 400 explicite).
  const rouvrir = async () => {
    setBusy(true); setError(null)
    try {
      await stockApi.rouvrirBcf(bcf.id)
      setInfo('Bon de commande réouvert (repassé en brouillon).')
      onSaved?.()
    } catch (err) {
      setError(frBcfError(err, 'La réouverture a échoué.'))
    } finally { setBusy(false) }
  }

  // ZPUR4 — clone ce BCF en un nouveau BROUILLON (quantités reçues à zéro).
  const dupliquer = async () => {
    setBusy(true); setError(null)
    try {
      await stockApi.dupliquerBcf(bcf.id)
      setInfo('Bon de commande dupliqué en nouveau brouillon.')
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frBcfError(err, 'La duplication a échoué.'))
    } finally { setBusy(false) }
  }

  // ZPUR1 — facture directement ce BCF (lignes « sur commande » uniquement,
  // sans exiger de réception préalable). Le backend refuse sinon (400).
  const facturer = async () => {
    setBusy(true); setError(null)
    try {
      const r = await stockApi.facturerBcf(bcf.id)
      setInfo(`Facture fournisseur ${r.data?.reference ?? ''} créée.`)
      onSaved?.()
    } catch (err) {
      setError(frBcfError(err, 'La facturation directe a échoué.'))
    } finally { setBusy(false) }
  }

  // ZPUR1 — gating : au moins une ligne produit porte la politique « sur
  // commande » (comme le backend l'exige — jamais deviné côté client).
  const peutFacturerDirect = !isNew && statut !== 'annule' && lignes.some((l) => {
    const prod = allProduits.find((p) => String(p.id) === String(l.produit))
    return prod?.politique_facturation_achat === 'sur_commande'
  })

  // QS1 — PDF fournisseur : ouvre le PDF dans un nouvel onglet (repli :
  // téléchargement si popup bloquée) et fait remonter la VRAIE erreur
  // serveur au lieu d'un « PDF indisponible » générique.
  const telechargerPdf = async () => {
    setError(null)
    try {
      const r = await stockApi.bcfPdf(bcf.id)
      const blob = r.data
      // Garde-fou : si la réponse n'est pas un PDF (page HTML d'erreur…),
      // on le dit honnêtement au lieu d'ouvrir un fichier corrompu.
      if (!estBlobPdf(blob)) {
        setError('Le serveur n\'a pas renvoyé de PDF (réponse inattendue). Réessayez ou contactez un administrateur.')
        return
      }
      // QD2 — nom cohérent posé par le serveur (repli sur la référence) pour
      // le téléchargement de secours si le popup est bloqué.
      ouvrirPdfBlob(blob, filenameFromResponse(r, `${bcf.reference ?? 'BCF'}.pdf`))
    } catch (err) {
      setError(await messageErreurBlob(err, {
        fallback: 'La génération du PDF a échoué. Réessayez.',
      }))
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {isNew ? 'Nouveau bon de commande fournisseur'
              : `Bon de commande — ${bcf.reference ?? ''}`}
            {!isNew && <StatusPill status={statut} label={bcfStatutLabel(statut)} />}
            {chantierRef && (
              <span className="inline-flex items-center gap-1 rounded-md border border-info/30 bg-info/10 px-2 py-0.5 text-xs font-normal text-info">
                <Package className="size-3" /> Chantier {chantierRef}
              </span>
            )}
          </DialogTitle>
          <DialogDescription>
            Document <strong>interne</strong> : les prix d&apos;achat n&apos;apparaissent
            jamais sur un document client.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="bcf-fou">Fournisseur</label>
            <Select value={fournisseur ? String(fournisseur) : '__none'} disabled={!editableLignes}
                    onValueChange={(v) => setFournisseur(v === '__none' ? '' : v)}>
              <SelectTrigger id="bcf-fou"><SelectValue placeholder="— Choisir un fournisseur —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Choisir un fournisseur —</SelectItem>
                {fournisseurs.map((f) => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="bcf-date">Date de commande</label>
            <Input id="bcf-date" type="date" value={dateCommande ?? ''}
                   disabled={!editableLignes}
                   onChange={(e) => setDateCommande(e.target.value)} />
          </div>
        </div>

        {/* ── ZPUR8 — « Other Information » : acheteur, réf. fournisseur,
            note de bas de page, incoterm (imprimés sur le PDF BCF). ── */}
        <div className="grid gap-4 rounded-lg border border-border p-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="bcf-acheteur">Acheteur</label>
            <Select value={acheteur ? String(acheteur) : '__none'}
                    onValueChange={(v) => setAcheteur(v === '__none' ? '' : v)}>
              <SelectTrigger id="bcf-acheteur"><SelectValue placeholder="— Créateur par défaut —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Créateur par défaut —</SelectItem>
                {membres.map((m) => (
                  <SelectItem key={m.id} value={String(m.id)}>
                    {m.username ?? m.email ?? `#${m.id}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="bcf-ref-fou">Référence fournisseur</label>
            <Input id="bcf-ref-fou" value={refFournisseur ?? ''}
                   placeholder="Numéro de commande côté fournisseur"
                   onChange={(e) => setRefFournisseur(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="bcf-incoterm">Incoterm</label>
            <Input id="bcf-incoterm" value={incoterm ?? ''}
                   placeholder="ex. FOB, EXW, DAP…"
                   onChange={(e) => setIncoterm(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="bcf-note-bas-page">Note de bas de page (PDF)</label>
            <Input id="bcf-note-bas-page" value={noteBasPage ?? ''}
                   placeholder="Mention imprimée en bas du PDF"
                   onChange={(e) => setNoteBasPage(e.target.value)} />
          </div>
        </div>

        {/* ── Lignes ── */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 text-sm font-semibold">
              <Package className="size-4 text-muted-foreground" /> Lignes
            </span>
            <div className="flex items-center gap-2">
              {!isNew && (statut === 'envoye' || statut === 'recu') && reception.commande > 0 && (
                <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                  {reception.recu}/{reception.commande} reçus
                  <span className="inline-block h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                    <span className="block h-full bg-success"
                          style={{ width: `${Math.round(reception.taux * 100)}%` }} />
                  </span>
                </span>
              )}
              {!isNew && statut === 'envoye' && (
                <Button type="button" variant="outline" size="sm" onClick={toutRecevoir}>
                  Tout recevoir
                </Button>
              )}
              {editableLignes && (
                <Button type="button" variant="outline" size="sm" onClick={addLigne}>
                  <Plus /> Ajouter une ligne
                </Button>
              )}
              {editableLignes && (
                <Button type="button" variant="outline" size="sm" onClick={addLigneLibre}>
                  <Plus /> Ligne libre (transport, frais…)
                </Button>
              )}
            </div>
          </div>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold" style={{ minWidth: 220 }}>Article</th>
                  <th className="px-3 py-2 text-left font-semibold">Quantité</th>
                  <th className="px-3 py-2 text-left font-semibold">Prix achat U. (interne)</th>
                  <th className="px-3 py-2 text-left font-semibold">Total HT</th>
                  {!isNew && <th className="px-3 py-2 text-left font-semibold">Reçu</th>}
                  {!isNew && statut === 'envoye' && <th className="px-3 py-2 text-left font-semibold">À recevoir</th>}
                  {editableLignes && <th className="w-10 px-3 py-2" />}
                </tr>
              </thead>
              <tbody>
                {lignes.length === 0 && (
                  <tr><td colSpan={7} className="px-3 py-3 text-sm text-muted-foreground">Aucune ligne.</td></tr>
                )}
                {lignes.map((l, idx) => {
                  const lineTotal = (Number(l.quantite) || 0) * (Number(l.prix_achat_unitaire) || 0)
                  const restante = quantiteRestante(l)
                  return (
                    <tr key={l.id ?? `new-${idx}`} className="border-t border-border">
                      <td className="px-3 py-2">
                        {editableLignes ? (
                          (l.sans_stock || (!l.produit && l.designation != null)) ? (
                            <div className="flex-1">
                              <Input className="h-9" placeholder="Désignation libre (ex. Transport Casablanca)"
                                     value={l.designation ?? ''}
                                     onChange={(e) => setLigne(idx, { designation: e.target.value })} />
                              <p className="mt-1 text-xs text-muted-foreground">
                                Ligne libre — aucun mouvement de stock à la réception.
                              </p>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1">
                              <div className="flex-1">
                                <BcfProduitPicker produits={allProduits} value={l.produit}
                                                  onChange={(v) => pickProduit(idx, v)} />
                              </div>
                              {canCreateProduit && (
                                <IconButton type="button" label="Nouveau produit" size="sm"
                                            className="size-8 text-primary hover:bg-accent"
                                            onClick={() => setQuickCreateIdx(idx)}>
                                  <Plus />
                                </IconButton>
                              )}
                            </div>
                          )
                        ) : (
                          <span>
                            {l.produit_nom ?? l.designation ?? '—'}
                            {l.produit_sku ? ` (${l.produit_sku})` : ''}
                            {l.sans_stock && !l.produit_nom && (
                              <span className="ml-1 text-xs text-muted-foreground">(ligne libre)</span>
                            )}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {editableLignes ? (
                          <Input type="number" step="any" inputMode="decimal" className="h-9 w-24"
                                 value={l.quantite ?? ''}
                                 onChange={(e) => setLigne(idx, { quantite: e.target.value })} />
                        ) : l.quantite}
                      </td>
                      <td className="px-3 py-2">
                        {editableLignes ? (
                          <>
                            <Input type="number" step="any" inputMode="decimal" className="h-9 w-32"
                                   value={l.prix_achat_unitaire ?? ''}
                                   onChange={(e) => setLigne(idx, { prix_achat_unitaire: e.target.value })} />
                            {l.produit && !(Number(l.prix_achat_unitaire) > 0) && (
                              <p className="mt-1 text-xs text-warning">
                                Sans prix d&apos;achat — commande possible (BCF interne).
                              </p>
                            )}
                          </>
                        ) : fmtMad(l.prix_achat_unitaire)}
                      </td>
                      <td className="px-3 py-2 tabular-nums">{fmtMad(lineTotal)}</td>
                      {!isNew && <td className="px-3 py-2 tabular-nums">{l.quantite_recue ?? 0}</td>}
                      {!isNew && statut === 'envoye' && (
                        <td className="px-3 py-2">
                          {restante > 0 ? (
                            <Input type="number" min="0" max={restante} inputMode="numeric" className="h-9 w-24"
                                   placeholder={`/${restante}`}
                                   value={receptions[l.id] ?? ''}
                                   onChange={(e) => setReceptions((r) => ({ ...r, [l.id]: e.target.value }))} />
                          ) : <span className="text-xs text-muted-foreground">soldée</span>}
                        </td>
                      )}
                      {editableLignes && (
                        <td className="px-3 py-2">
                          <IconButton label="Retirer la ligne" variant="ghost" size="icon" className="size-8"
                                      onClick={() => removeLigne(idx)}>
                            <Trash2 className="text-destructive" />
                          </IconButton>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="text-right text-sm font-bold">
            Total achat HT (interne) : {fmtMad(total)}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="bcf-note">Note</label>
          <Textarea id="bcf-note" rows={2} value={note ?? ''}
                    disabled={!editableLignes && statut !== 'envoye'}
                    onChange={(e) => setNote(e.target.value)} />
        </div>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
        {info && (
          <div className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
            {info}
          </div>
        )}

        <DialogFooter className="flex-wrap">
          {!isNew && statut !== 'annule' && (
            <Button type="button" variant="outline" onClick={telechargerPdf}>
              <FileText /> PDF (interne)
            </Button>
          )}
          {!isNew && (statut === 'brouillon' || statut === 'envoye') && (
            <Button type="button" variant="destructive" loading={busy} onClick={() => setShowAnnuler(true)}>
              Annuler le BC
            </Button>
          )}
          {/* ZPUR11 — un BCF ANNULE peut être réouvert en brouillon (refusé
              côté serveur si des réceptions confirmées existent). */}
          {!isNew && statut === 'annule' && (
            <Button type="button" variant="outline" loading={busy} onClick={rouvrir}>
              <RotateCcw /> Réouvrir
            </Button>
          )}
          {/* ZPUR4 — clone en nouveau brouillon (jamais sur un BCF neuf). */}
          {!isNew && (
            <Button type="button" variant="outline" loading={busy} onClick={dupliquer}>
              <Copy /> Dupliquer
            </Button>
          )}
          {/* ZPUR1 — facture directement les lignes « sur commande », sans
              exiger de réception préalable. */}
          {peutFacturerDirect && (
            <Button type="button" variant="outline" loading={busy} onClick={facturer}
                    title="Facture directement les lignes en politique « sur commande »">
              <Receipt /> Facturer (sur commande)
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
          {/* QS4 — envois directs au fournisseur (BCF déjà enregistré, non
              annulé). Grisés + tooltip explicite quand le contact manque. */}
          {!isNew && statut !== 'annule' && (
            <>
              <Button type="button" variant="outline" loading={busy}
                      disabled={busy || !fournisseurTel}
                      title={fournisseurTel
                        ? 'Préparer un message WhatsApp au fournisseur'
                        : 'Ce fournisseur n\'a pas de numéro de téléphone'}
                      onClick={envoyerWhatsapp}>
                Envoyer par WhatsApp
              </Button>
              <Button type="button" variant="outline" loading={busy}
                      disabled={busy || !fournisseurEmail}
                      title={fournisseurEmail
                        ? 'Envoyer le PDF par email au fournisseur'
                        : 'Ce fournisseur n\'a pas d\'adresse email'}
                      onClick={envoyerEmail}>
                Envoyer par email
              </Button>
            </>
          )}
          {editableLignes && (
            <>
              <Button type="button" variant="outline" loading={busy} onClick={save}>
                {busy ? '…' : 'Enregistrer'}
              </Button>
              <Button type="button" loading={busy} onClick={envoyer}
                      title="Marque le BCF « envoyé » (sans email/WhatsApp)">
                {busy ? '…' : 'Envoyer au fournisseur'}
              </Button>
            </>
          )}
          {!isNew && statut === 'envoye' && (
            <Button type="button" variant="success" loading={busy} onClick={recevoir}>
              {busy ? '…' : 'Recevoir les quantités'}
            </Button>
          )}
          {!isNew && (statut === 'recu' || statut === 'envoye') && (
            <Button type="button" variant="outline" onClick={() => setShowRetour(true)}
                    title="Retourner des articles défectueux/erronés (décrémente le stock)">
              <Undo2 /> Retour fournisseur
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
      {showRetour && (
        <RetourModal bcf={bcf} onClose={() => setShowRetour(false)}
                     onDone={(msg) => { onSaved?.(); if (msg) setInfo(msg) }} />
      )}
      {showAnnuler && (
        <MotifAnnulationModal busy={busy}
                               onClose={() => setShowAnnuler(false)}
                               onConfirm={annuler} />
      )}
      {/* QS2 — création rapide de produit (réutilise la modale QG6) puis dépôt
          sur la ligne du BCF avec pré-remplissage du prix d'achat interne. */}
      {canCreateProduit && (
        <ProduitQuickCreateModal
          open={quickCreateIdx != null}
          onClose={() => setQuickCreateIdx(null)}
          onCreated={onProduitCreatedForLine}
        />
      )}
    </Dialog>
  )
}

export default function BonsCommandeFournisseur() {
  const location = useLocation()
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [fournisseurs, setFournisseurs] = useState([])
  const [produits, setProduits] = useState([])
  const [statutFiltre, setStatutFiltre] = useState('')
  const [fusionInfo, setFusionInfo] = useState(null)
  const [fusionError, setFusionError] = useState(null)
  // Réapprovisionnement (706) : un BCF brouillon pré-rempli demandé via l'état
  // de navigation depuis le catalogue ouvre directement le détail.
  const prefill = location.state?.prefillBcf ?? null
  const [selected, setSelected] = useState(
    () => (prefill
      ? {
          fournisseur: prefill.fournisseur ? String(prefill.fournisseur) : '',
          lignes: [{ produit: String(prefill.produit), quantite: prefill.quantite || 1, prix_achat_unitaire: '' }],
        }
      : null), // bcf object or {} for new
  )

  // ZPUR3 — un BCF brouillon généré depuis un modèle (« Modèles » →
  // « Générer un BCF ») s'ouvre directement ici en édition avant envoi.
  const ouvrirBcfId = location.state?.ouvrirBcfId ?? null

  // Nettoie l'état de navigation pour ne pas rouvrir le brouillon au retour.
  useEffect(() => {
    if (prefill || ouvrirBcfId) navigate(location.pathname, { replace: true, state: null })
  }, [prefill, ouvrirBcfId, navigate, location.pathname])

  useEffect(() => {
    if (!ouvrirBcfId) return
    stockApi.getBonCommandeFournisseur(ouvrirBcfId)
      .then((r) => setSelected(r.data))
      .catch(() => {})
  }, [ouvrirBcfId])

  // setState arrive dans les callbacks asynchrones (jamais synchrone dans
  // l'effet) : l'état initial loading=true couvre le premier chargement.
  const reload = () => {
    stockApi.getBonsCommandeFournisseur()
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    reload()
    stockApi.getFournisseurs().then((r) => setFournisseurs(r.data?.results ?? r.data ?? [])).catch(() => {})
    stockApi.getProduits({ page_size: 1000 }).then((r) => setProduits(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  // Le filtre statut reste local (Select dédié) ; la recherche texte
  // (référence / fournisseur) est gérée par le DataTable via globalColumns.
  const rows = useMemo(() => (
    statutFiltre ? items.filter((b) => b.statut === statutFiltre) : items
  ), [items, statutFiltre])
  // BCF envoyés en attente de réception (raccourci de filtrage en un clic).
  const attenteReception = useMemo(() => nbEnvoyesNonRecus(items), [items])

  // Ouvre le détail en rechargeant la version complète (lignes à jour).
  const openBcf = async (b) => {
    try {
      const r = await stockApi.getBonCommandeFournisseur(b.id)
      setSelected(r.data)
    } catch { setSelected(b) }
  }

  // ZPUR6 — fusionne une sélection de BCF BROUILLON du même fournisseur en
  // un BCF cible unique (quantités cumulées par produit) ; les sources
  // passent en `annule`. Le backend refuse (400) toute sélection invalide
  // (statuts mélangés, fournisseurs différents, moins de 2 BCF).
  const fusionner = async (selRows, selKeys, clear) => {
    setFusionError(null); setFusionInfo(null)
    try {
      const r = await stockApi.fusionnerBcf([...selKeys])
      setFusionInfo(`BCF fusionnés en ${r.data?.reference ?? 'un nouveau bon de commande'}.`)
      clear()
      reload()
    } catch (err) {
      setFusionError(frBcfError(err, 'La fusion a échoué.'))
    }
  }

  const columns = useMemo(() => [
    { id: 'reference', header: 'Référence', minWidth: 140,
      accessor: (b) => b.reference ?? '' },
    { id: 'fournisseur_nom', header: 'Fournisseur', minWidth: 160,
      accessor: (b) => b.fournisseur_nom ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'statut', header: 'Statut', width: 130, searchable: false,
      accessor: (b) => b.statut,
      cell: (v) => <StatusPill status={v} label={bcfStatutLabel(v)} /> },
    { id: 'date_commande', header: 'Date', width: 120, searchable: false,
      accessor: (b) => bcfDateAffichee(b),
      cell: (v) => fmtDateFR(v) },
    { id: 'lignes', header: 'Lignes', align: 'right', width: 90, searchable: false,
      accessor: (b) => (b.lignes ?? []).length },
    { id: 'total_achat', header: 'Total achat HT (interne)', align: 'right', minWidth: 170, searchable: false,
      accessor: (b) => b.total_achat,
      cell: (v) => fmtMad(v) },
  ], [])

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Bons de commande fournisseur</h1>
          <p className="text-sm text-muted-foreground">{rows.length} bon(s) de commande</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* ZPUR3 — modèles de BCF réutilisables (purchase templates). */}
          <Button variant="outline" onClick={() => navigate('/stock/modeles-bcf')}>
            <LayoutTemplate /> Modèles
          </Button>
          <Button onClick={() => setSelected({})}>
            <Plus /> Nouveau bon de commande
          </Button>
        </div>
      </header>

      {fusionError && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {fusionError}
        </div>
      )}
      {fusionInfo && (
        <div className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
          {fusionInfo}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="w-48 sm:w-56">
          <Select value={statutFiltre || '__all'} onValueChange={(v) => setStatutFiltre(v === '__all' ? '' : v)}>
            <SelectTrigger><SelectValue placeholder="Tous les statuts" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous les statuts</SelectItem>
              {Object.entries(BCF_STATUTS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        {attenteReception > 0 && (
          <Button variant={statutFiltre === 'envoye' ? 'secondary' : 'outline'} size="sm"
                  onClick={() => setStatutFiltre(statutFiltre === 'envoye' ? '' : 'envoye')}
                  title="Bons de commande envoyés en attente de réception">
            En attente de réception ({attenteReception})
          </Button>
        )}
        {statutFiltre && (
          <Button variant="ghost" size="sm" onClick={() => setStatutFiltre('')}>
            Réinitialiser
          </Button>
        )}
      </div>

      <DataTable
        data={rows}
        columns={columns}
        loading={loading}
        getRowId={(b) => b.id}
        searchPlaceholder="Rechercher (référence, fournisseur)…"
        globalColumns={['reference', 'fournisseur_nom']}
        onRowClick={openBcf}
        selectable
        bulkActions={(selRows, selKeys, clear) => [
          // VX246(c) — « Copier » la sélection en TSV (colle en colonnes dans Excel).
          buildCopyTSVAction({ rows: selRows, filteredRows: selRows, columns }),
          // ZPUR6 — n'affiche l'action de fusion que si la sélection est éligible
          // (≥2 BCF BROUILLON du même fournisseur) — le backend re-vérifie
          // de toute façon, mais autant ne pas proposer une action vouée à
          // échouer.
          ...(selRows.length >= 2
          && selRows.every((b) => b.statut === 'brouillon')
          && new Set(selRows.map((b) => b.fournisseur)).size === 1
            ? [{
                id: 'fusionner', label: 'Fusionner en un seul BCF',
                onClick: () => fusionner(selRows, selKeys, clear),
              }]
            : []),
        ]}
        emptyTitle="Aucun bon de commande fournisseur"
        emptyDescription="Créez-en un avec « Nouveau bon de commande » ou depuis le besoin matériel d'un chantier."
        aria-label="Bons de commande fournisseur"
      />

      {selected && (
        <BcfDetail bcf={selected} fournisseurs={fournisseurs} produits={produits}
                   onClose={() => setSelected(null)} onSaved={reload} />
      )}
    </div>
  )
}
