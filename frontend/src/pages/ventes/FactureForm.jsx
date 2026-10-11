import { useState, useEffect, useRef } from 'react'
import { useDispatch } from 'react-redux'
import { Plus, Trash2, AlertTriangle } from 'lucide-react'
import {
  createFacture,
  updateFacture,
  addLigneFacture,
  updateLigneFacture,
  removeLigneFacture,
} from '../../features/ventes/store/ventesSlice'
import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import { resilientMutation } from '../../lib/resilientMutation'
import { useStaleGuard } from '../../hooks/useStaleGuard'
import fetchAllPages from '../../utils/fetchAllPages'
import {
  Button, IconButton,
  Dialog, DialogContent, DialogHeader, DialogTitle,
  Form, FormField, FormActions, useDirtyGuard, confirmLeaveIfDirty,
  Input, Textarea, Label,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import ProduitPicker from '../../components/ProduitPicker'
import ClientQuickCreateModal from './ClientQuickCreateModal'
import AttachmentsPanel from '../../components/AttachmentsPanel'
import { formatMAD, toNumber } from '../../lib/format'
import { frenchError } from '../../lib/frenchError'
import { useServerFieldErrors } from '../../hooks/useServerFieldErrors'
import { parsePastedAmount } from '../../hooks/usePasteClean'
import { todayLocalIso } from '../../lib/dateLocale.js'

let _keyCounter = 0
const newKey = () => ++_keyCounter

const emptyLine = () => ({
  _key: newKey(),
  id: null,
  produit: '',
  designation: '',
  quantite: '1',
  prix_unitaire: '0',
  remise: '0',
  taux_tva: '',  // vide = taux global de la facture (N37)
})

const today = todayLocalIso()

export default function FactureForm({ facture = null, onClose, onSaved }) {
  const dispatch = useDispatch()
  const isEdit = !!facture
  // AFAC71 — une facture hors BROUILLON (émise, payée, en retard, annulée) s'ouvre en
  // lecture seule pour l'argent et les lignes ; seuls note, échéance, conditions et
  // référence de commande client sont modifiables et envoyés. Le statut et la
  // télédéclaration DGI ne se posent plus depuis ce formulaire (actions dédiées).
  const horsBrouillon = isEdit && facture.statut !== 'brouillon'

  // VX243(c) — garde d'édition périmée : re-GET léger de `updated_at` au
  // submit, bannière non bloquante si un autre utilisateur a sauvegardé
  // cette facture entre-temps (2 onglets).
  const staleGuard = useStaleGuard({
    openedAt: facture?.updated_at,
    fetchLatest: facture?.id
      ? () => ventesApi.getFacture(facture.id).then(r => r.data)
      : undefined,
  })

  const [clients, setClients]           = useState([])
  const [produits, setProduits]         = useState([])
  const [bonsCommande, setBonsCommande] = useState([])
  const [bcBusy, setBcBusy] = useState(false)
  const [bcErreur, setBcErreur] = useState('')
  const [factureCreee, setFactureCreee] = useState(null)
  const [saving, setSaving]             = useState(false)
  // VX171 — vérité serveur → champ ; le rouge s'efface à la frappe.
  const { errors, setErrors, setFromResponse, clearField } = useServerFieldErrors()
  const [dirty, setDirty]               = useState(false)
  const [clientQuickCreateOpen, setClientQuickCreateOpen] = useState(false)
  useDirtyGuard(dirty)
  // VX117 — la facture créée par un submit partiellement échoué reste
  // EXPOSÉE : un retry ne repart JAMAIS en second `createFacture` (doublon
  // fiscal).
  const [createdFactureId, setCreatedFactureId] = useState(null)
  // AFAC70 — raison SERVEUR de l'échec d'enregistrement de chaque ligne
  // ({[_key]: message FR}), affichée sous la ligne fautive.
  const [lineErrors, setLineErrors] = useState({})

  const [fields, setFields] = useState({
    client:          facture?.client          ?? '',
    bon_commande:    facture?.bon_commande     ?? '',
    date_echeance:   facture?.date_echeance    ?? '',
    date_livraison:  facture?.date_livraison    ?? '',
    conditions_paiement: facture?.conditions_paiement ?? '',
    taux_tva:        String(facture?.taux_tva        ?? '20.00'),
    remise_globale:  String(facture?.remise_globale  ?? '0'),
    note:            facture?.note             ?? '',
    // CIQ226 — référence de commande du client (héritée du devis, éditable).
    reference_commande_client: facture?.reference_commande_client ?? '',
  })
  // CIQ226 — retenue de garantie : l'état SERVI (montant retenu, exigible,
  // date de libération), rafraîchi par « Libérer la retenue ».
  const [retenue, setRetenue] = useState({
    retenue_garantie_mad: facture?.retenue_garantie_mad ?? null,
    retenue_liberee_le: facture?.retenue_liberee_le ?? null,
    montant_exigible: facture?.montant_exigible ?? null,
  })
  const [dateLiberation, setDateLiberation] = useState('')
  const [liberation, setLiberation] = useState({ enCours: false, erreur: null })
  const libererRetenue = async () => {
    setLiberation({ enCours: true, erreur: null })
    try {
      const { data } = await ventesApi.libererRetenueFacture(facture.id, dateLiberation)
      setRetenue({
        retenue_garantie_mad: data.retenue_garantie_mad ?? null,
        retenue_liberee_le: data.retenue_liberee_le ?? null,
        montant_exigible: data.montant_exigible ?? null,
      })
      setLiberation({ enCours: false, erreur: null })
    } catch (err) {
      const detail = err?.response?.data?.detail
      setLiberation({ enCours: false,
                      erreur: typeof detail === 'string' ? detail : 'La retenue n’a pas pu être libérée.' })
    }
  }

  const [lines, setLines] = useState(
    facture?.lignes?.length
      ? facture.lignes.map(l => ({
          _key: newKey(),
          id: l.id,
          produit: String(l.produit),
          designation: l.designation,
          quantite: String(l.quantite),
          prix_unitaire: String(l.prix_unitaire),
          remise: String(l.remise),
          taux_tva: l.taux_tva != null ? String(l.taux_tva) : '',
        }))
      : [emptyLine()]
  )

  const [removedLineIds, setRemovedLineIds] = useState([])
  // VX90 — focus la nouvelle ligne (sélecteur produit) après « Ajouter ligne ».
  const linesTableRef = useRef(null)
  const [pendingFocusKey, setPendingFocusKey] = useState(null)

  useEffect(() => {
    // ALEA33 — TOUTES les pages (jamais les 50 premiers clients seulement).
    fetchAllPages((page) => crmApi.getClients({ page, page_size: 200 }).then((r) => r.data))
      .then((res) => setClients(Array.isArray(res) ? res : (res?.results ?? []))).catch(() => {})
    fetchAllPages((page) => stockApi.getProduits({ page }).then((r) => r.data))
      .then(setProduits).catch(() => {})
    fetchAllPages((page) => ventesApi.getBonsCommande({ page, page_size: 200 }).then((r) => r.data))
      .then((res) => setBonsCommande(Array.isArray(res) ? res : (res?.results ?? []))).catch(() => {})
  }, [])

  // VX90 — après ajout d'une ligne, focaliser son sélecteur produit + défiler.
  useEffect(() => {
    if (pendingFocusKey == null) return
    const row = linesTableRef.current
      ?.querySelector(`[data-line-key="${pendingFocusKey}"]`)
    if (row) {
      row.querySelector('button[type="button"]')?.focus()
      row.scrollIntoView({ block: 'nearest' })
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset one-shot du focus (VX90)
    setPendingFocusKey(null)
  }, [pendingFocusKey, lines])

  // Live totals
  const remGlobal   = parseFloat(fields.remise_globale) || 0
  const tva         = parseFloat(fields.taux_tva) || 0

  const subtotalHT = lines.reduce((sum, l) => {
    const qte = parseFloat(l.quantite)      || 0
    const pu  = parseFloat(l.prix_unitaire) || 0
    const rem = parseFloat(l.remise)        || 0
    return sum + qte * pu * (1 - rem / 100)
  }, 0)

  const totalHT  = subtotalHT * (1 - remGlobal / 100)
  // Ventilation TVA par taux : chaque ligne utilise son taux propre (N37),
  // sinon le taux global de la facture. La remise globale s'applique au prorata.
  const remFactor = subtotalHT > 0 ? totalHT / subtotalHT : (1 - remGlobal / 100)
  const tvaParTaux = lines.reduce((acc, l) => {
    const qte = parseFloat(l.quantite)      || 0
    const pu  = parseFloat(l.prix_unitaire) || 0
    const rem = parseFloat(l.remise)        || 0
    const ligneHT = qte * pu * (1 - rem / 100) * remFactor
    const taux = l.taux_tva !== '' && l.taux_tva != null
      ? (parseFloat(l.taux_tva) || 0)
      : tva
    acc[taux] = (acc[taux] || 0) + ligneHT
    return acc
  }, {})
  const totalTVA = Object.entries(tvaParTaux)
    .reduce((sum, [taux, ht]) => sum + ht * (parseFloat(taux) / 100), 0)

  // AFAC68 — le chiffre DÉFINITIF est celui du serveur (FactureSerializer) tant que
  // la facture n'a pas été modifiée ; dès qu'on touche une ligne, le bloc devient une
  // ESTIMATION dont le TTC est toujours = HT affiché + TVA affichée (jamais un TTC JS
  // arrondi autrement sous le libellé « Total TTC »).
  const r2 = (n) => Math.round((Number(n) + Number.EPSILON) * 100) / 100
  const totauxServeur = isEdit && !dirty && facture?.montant_ttc != null
  const aff = totauxServeur
    ? {
        ht: toNumber(facture.montant_ht), tva: toNumber(facture.montant_tva),
        ttc: toNumber(facture.montant_ttc),
      }
    : { ht: r2(totalHT), tva: r2(totalTVA), ttc: r2(r2(totalHT) + r2(totalTVA)) }
  const arrondiDevis = totauxServeur ? r2(aff.ttc - aff.ht - aff.tva) : 0
  const tauxDistincts = Object.keys(tvaParTaux).filter(t => Number(t) > 0)

  // VX171 — le rouge ne doit jamais mentir pendant que l'utilisateur corrige.
  const setField = (k, v) => { setDirty(true); clearField(k); setFields(f => ({ ...f, [k]: v })) }

  // AFAC67 — plus AUCUNE recopie JS devis → facture : un BC issu d'un devis se
  // facture par la porte unique `creer-facture` (copier_devis_sur_facture), si bien
  // que l'écran ne peut plus produire une facture différente du devis signé.
  const onBcChange = (bcId) => {
    setField('bon_commande', bcId)
    setBcErreur('')
    if (!bcId) return
    const bc = bonsCommande.find(b => String(b.id) === String(bcId))
    if (bc) setField('client', String(bc.client))
  }
  const bcSelectionne = bonsCommande.find(b => String(b.id) === String(fields.bon_commande))
  const modeBcDevis = !isEdit && !!bcSelectionne?.devis
  const creerDepuisBc = async () => {
    if (!bcSelectionne) return
    setBcBusy(true); setBcErreur('')
    try {
      const res = await ventesApi.creerFactureBC(bcSelectionne.id)
      setFactureCreee(res.data)
      setDirty(false)
      onSaved?.()
    } catch (err) {
      setBcErreur(frenchError(err, 'Création de la facture depuis le bon de commande impossible.'))
    } finally { setBcBusy(false) }
  }

  const setLine = (key, k, v) => {
    setDirty(true)
    clearField('lines')
    setLines(ls => ls.map(l => l._key === key ? { ...l, [k]: v } : l))
    setLineErrors(errs => {
      if (!(key in errs)) return errs
      const rest = { ...errs }
      delete rest[key]
      return rest
    })
  }

  const onProduitChange = (key, produitId) => {
    setDirty(true)
    clearField('lines')
    const p = produits.find(p => String(p.id) === String(produitId))
    setLines(ls => ls.map(l =>
      l._key === key
        ? {
            ...l, produit: produitId, designation: p?.nom ?? '',
            prix_unitaire: p ? String(p.prix_vente) : '0',
            // Pré-remplit le taux TVA depuis le produit (10 % panneaux PV,
            // 20 % le reste). Vide si le produit n'a pas de taux → taux global.
            taux_tva: p?.tva != null ? String(p.tva) : l.taux_tva,
          }
        : l
    ))
  }

  const addLine    = () => {
    setDirty(true)
    clearField('lines')
    setLines(ls => {
      const line = emptyLine()
      setPendingFocusKey(line._key) // VX90
      return [...ls, line]
    })
  }
  const removeLine = key => {
    setDirty(true)
    clearField('lines')
    const line = lines.find(l => l._key === key)
    if (line?.id) setRemovedLineIds(ids => [...ids, line.id])
    setLines(ls => ls.filter(l => l._key !== key))
  }

  const validate = () => {
    const e = {}
    if (!fields.client)          e.client = 'Client requis'
    if (lines.length === 0)      e.lines  = 'Au moins une ligne est requise'
    else if (lines.some(l => !l.produit)) e.lines = 'Chaque ligne doit avoir un produit'
    else if (lines.some(l => !(parseFloat(l.quantite) > 0))) e.lines = 'Quantité invalide (doit être > 0)'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    // VX243(c) — garde de fraîcheur AVANT le PATCH en édition (conflit → on
    // interrompt et on affiche la bannière, aucune mutation).
    if (isEdit) {
      const canProceed = await staleGuard.checkBeforeSave()
      if (!canProceed) return
    }
    setSaving(true)
    try {
      const nonFinanciers = {
        date_echeance:  fields.date_echeance  || null,
        conditions_paiement: fields.conditions_paiement || '',
        note:           fields.note || null,
        reference_commande_client: (fields.reference_commande_client || '').trim(),
      }
      const payload = horsBrouillon ? nonFinanciers : {
        ...nonFinanciers,
        client:         parseInt(fields.client),
        bon_commande:   fields.bon_commande ? parseInt(fields.bon_commande) : null,
        date_livraison: fields.date_livraison || null,
        taux_tva:       fields.taux_tva,
        remise_globale: fields.remise_globale,
      }

      // VX117 — une facture déjà créée (id serveur ou id exposé par un
      // submit précédent partiellement échoué) ne repart JAMAIS en second
      // POST : la relance passe systématiquement en ÉDITION.
      let factureId = facture?.id ?? createdFactureId
      if (factureId && horsBrouillon) {
        // AFAC71 — hors brouillon, seuls les champs non financiers partent :
        // mise à jour PARTIELLE (PATCH). Un PUT exige le client et les montants
        // (400 « client : Ce champ est obligatoire », vu en acceptation live).
        const { data } = await ventesApi.patchFacture(factureId, payload)
        factureId = data.id
      } else if (factureId) {
        const res = await dispatch(updateFacture({ id: factureId, data: payload })).unwrap()
        factureId = res.id
      } else {
        const res = await dispatch(createFacture(payload)).unwrap()
        factureId = res.id
        setCreatedFactureId(factureId)
      }

      // Lignes supprimées — allSettled : une suppression en échec ne bloque
      // pas les autres déjà supprimées, et ne les redemande pas au retry.
      const delResult = await resilientMutation(horsBrouillon ? [] : removedLineIds, (id) =>
        dispatch(removeLigneFacture(id)).unwrap())
      setRemovedLineIds(delResult.failed.map(f => f.item))

      // Lignes existantes → update
      const updResult = await resilientMutation(horsBrouillon ? [] : lines.filter(l => l.id), (l) =>
        dispatch(updateLigneFacture({
          id: l.id,
          data: {
            facture:       factureId,
            produit:       parseInt(l.produit),
            designation:   l.designation,
            quantite:      l.quantite,
            prix_unitaire: l.prix_unitaire,
            remise:        l.remise,
            taux_tva:      l.taux_tva !== '' ? l.taux_tva : null,
          },
        })).unwrap())

      // Nouvelles lignes → create — chaque ligne créée avec succès reçoit
      // son id serveur immédiatement : un retry ne la recrée jamais (fin du
      // doublon fiscal ligne-par-ligne).
      const newLines = horsBrouillon ? [] : lines.filter(l => !l.id)
      const createResult = await resilientMutation(newLines, (l) =>
        dispatch(addLigneFacture({
          facture:       factureId,
          produit:       parseInt(l.produit),
          designation:   l.designation,
          quantite:      l.quantite,
          prix_unitaire: l.prix_unitaire,
          remise:        l.remise,
          taux_tva:      l.taux_tva !== '' ? l.taux_tva : null,
        })).unwrap())
      if (createResult.succeeded.length > 0) {
        setLines(ls => ls.map(l => {
          const ok = createResult.succeeded.find(s => s.item._key === l._key)
          return ok ? { ...l, id: ok.value.id } : l
        }))
      }

      // AFAC70 — chaque ligne refusée dit POURQUOI (motif serveur, clé de
      // champ DRF via frenchError) et LAQUELLE (numéro d'affichage) ; la
      // saisie reste dans le champ, jamais corrigée en silence.
      const lignesEnEchec = [...updResult.failed, ...createResult.failed]
        .map(f => ({
          key: f.item._key,
          numero: lines.findIndex(l => l._key === f.item._key) + 1,
          motif: frenchError(f.error, 'Ligne refusée par le serveur.'),
        }))
        .sort((a, b) => a.numero - b.numero)
      setLineErrors(Object.fromEntries(lignesEnEchec.map(e => [e.key, e.motif])))
      const lineFails = delResult.failed.length + lignesEnEchec.length
      if (lineFails > 0) {
        const parts = []
        if (lignesEnEchec.length === 1) {
          const [e] = lignesEnEchec
          parts.push(`la ligne ${e.numero} n'a pas pu être enregistrée : ${e.motif}`)
        } else if (lignesEnEchec.length > 1) {
          parts.push(`les lignes ${lignesEnEchec.map(e => e.numero).join(', ')} n'ont pas pu être enregistrées : `
            + lignesEnEchec.map(e => `ligne ${e.numero} — ${e.motif}`).join(' ; '))
        }
        if (delResult.failed.length > 0) {
          parts.push(`${delResult.failed.length} ligne(s) supprimée(s) n'ont pas pu être retirée(s) : `
            + frenchError(delResult.failed[0].error, 'suppression refusée.'))
        }
        setErrors(prev => ({ ...prev, submit:
          `Facture enregistrée, mais ${parts.join(' ; ').replace(/\.$/, '')}. `
          + 'Corrigez et réessayez — seules les lignes en échec seront retentées, aucun doublon.' }))
        return
      }

      setDirty(false)
      onSaved?.()
      onClose()
    } catch (err) {
      // VX171 — mapping DRF générique (detail / {champ:[…]} / array) : chaque
      // champ en erreur vire rouge, plus un toast anonyme.
      setFromResponse(err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o && confirmLeaveIfDirty(dirty)) onClose() }}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Éditer — ${facture.reference}` : 'Nouvelle facture'}</DialogTitle>
        </DialogHeader>

        {/* VX243(c) — bannière non bloquante : un autre utilisateur a
            sauvegardé cette facture pendant l'édition en cours. */}
        {staleGuard.staleInfo && (
          <div role="alert" className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
            <span>
              Modifié par {staleGuard.staleInfo.by || 'un autre utilisateur'}
              {' '}pendant votre édition — vérifiez avant d'enregistrer.
            </span>
            <span className="flex gap-2">
              <Button type="button" size="sm" variant="outline" onClick={staleGuard.dismiss}>
                Revoir
              </Button>
              <Button
                type="button" size="sm" variant="outline"
                onClick={() => { staleGuard.force(); handleSubmit({ preventDefault: () => {} }) }}
              >
                Enregistrer quand même
              </Button>
            </span>
          </div>
        )}

        <Form onSubmit={handleSubmit} className="gap-5">
          {/* ── Conformité Article 145 CGI (N29) — AVERTISSEMENT, jamais bloquant ── */}
          {isEdit && Array.isArray(facture.mentions_manquantes)
            && facture.mentions_manquantes.length > 0 && (
            <div role="alert" className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
              <p className="flex items-center gap-1.5 font-semibold">
                <AlertTriangle className="size-4 shrink-0" />
                Conformité Article 145 — mentions légales manquantes :
              </p>
              <ul className="ml-6 mt-1.5 list-disc space-y-0.5">
                {facture.mentions_manquantes.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
              <p className="mt-1.5 text-xs">
                Vous pouvez tout de même émettre la facture — complétez ces
                mentions (Paramètres → Identité, fiche client, lignes) pour
                une facture pleinement conforme.
              </p>
            </div>
          )}

          {/* ── Infos générales ── */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <FormField label="Client" required htmlFor="fc-client" error={errors.client}>
              <div className="flex gap-2">
                <div className="flex-1">
                  <Select value={fields.client ? String(fields.client) : undefined}
                          disabled={horsBrouillon}
                          onValueChange={v => setField('client', v)}>
                    {/* VX240(a) — la modale s'ouvrait SANS aucun autofocus (le
                        vendeur devait cliquer avant de pouvoir taper/choisir) ;
                        premier champ utile focalisé à l'ouverture. */}
                    <SelectTrigger id="fc-client" invalid={!!errors.client} autoFocus>
                      <SelectValue placeholder="— Sélectionner un client —" />
                    </SelectTrigger>
                    <SelectContent>
                      {clients.map(c => (
                        <SelectItem key={c.id} value={String(c.id)}>
                          {c.nom}{c.prenom ? ` ${c.prenom}` : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {/* VX91 — création rapide client (QG3), sans quitter la facture */}
                <Button type="button" variant="outline" disabled={horsBrouillon}
                        onClick={() => setClientQuickCreateOpen(true)}>
                  <Plus /> Nouveau client
                </Button>
              </div>
            </FormField>

            <FormField label="Bon de commande (optionnel)" htmlFor="fc-bc">
              <Select value={fields.bon_commande ? String(fields.bon_commande) : undefined}
                      disabled={horsBrouillon}
                      onValueChange={v => onBcChange(v)}>
                <SelectTrigger id="fc-bc">
                  <SelectValue placeholder="— Aucun BC —" />
                </SelectTrigger>
                <SelectContent>
                  {/* AFAC67 — un BC déjà facturé (facture vivante) n'est plus proposé. */}
                  {bonsCommande
                    .filter(bc => !bc.facture_active || String(bc.id) === String(fields.bon_commande))
                    .map(bc => (
                    <SelectItem key={bc.id} value={String(bc.id)}>
                      {bc.reference} — {bc.client_nom}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {modeBcDevis && (
                <div className="mt-2 rounded-lg border border-border bg-muted/40 p-3 text-sm">
                  {factureCreee ? (
                    <p role="status" className="m-0">
                      Facture <strong>{factureCreee.reference}</strong> créée — Total TTC{' '}
                      <strong>{formatMAD(factureCreee.montant_ttc)}</strong>, identique au devis signé.
                    </p>
                  ) : (
                    <>
                      <p className="m-0 mb-2">
                        Ce bon de commande est issu du devis {bcSelectionne.devis_reference || ''} :
                        la facture est créée à l&apos;identique du devis signé, sans ressaisie.
                      </p>
                      <Button type="button" loading={bcBusy} onClick={creerDepuisBc}>
                        Créer la facture depuis ce BC
                      </Button>
                    </>
                  )}
                  {bcErreur && (
                    <p role="alert" className="mt-2 text-destructive">{bcErreur}</p>
                  )}
                </div>
              )}
            </FormField>

            <FormField label="Date d'échéance" htmlFor="fc-echeance">
              <Input id="fc-echeance" type="date" value={fields.date_echeance}
                     onChange={e => setField('date_echeance', e.target.value)} />
              {fields.date_echeance && fields.date_echeance < today && (
                <p className="mt-1 text-xs text-warning">
                  Échéance déjà dépassée.
                </p>
              )}
            </FormField>

            <FormField label="Date de livraison/prestation" htmlFor="fc-livraison"
                       hint="Mention Art. 145 — date de la livraison ou prestation">
              <Input id="fc-livraison" type="date" value={fields.date_livraison}
                     disabled={horsBrouillon}
                     onChange={e => setField('date_livraison', e.target.value)} />
            </FormField>

            <FormField label="TVA (%)" htmlFor="fc-tva"
                       hint="Taux global (par défaut 20 %). Le taux par ligne prime quand renseigné.">
              <Input id="fc-tva" type="number" min="0" max="100" step="0.01" disabled={horsBrouillon}
                     value={fields.taux_tva} onChange={e => setField('taux_tva', e.target.value)} />
              <div className="mt-1 flex gap-1">
                {['20', '10'].map(t => (
                  <Button key={t} type="button" size="sm" disabled={horsBrouillon}
                          variant={fields.taux_tva === `${t}.00` || fields.taux_tva === t ? 'default' : 'outline'}
                          onClick={() => setField('taux_tva', t)}>
                    {t} %
                  </Button>
                ))}
              </div>
            </FormField>

            <FormField label="Remise globale (%)" htmlFor="fc-remise">
              <Input id="fc-remise" type="number" min="0" max="100" step="0.01" disabled={horsBrouillon}
                     value={fields.remise_globale} onChange={e => setField('remise_globale', e.target.value)} />
            </FormField>
          </div>

          {/* ── Lignes ── */}
          <section className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h3 className="font-display text-base font-semibold text-foreground">Lignes de la facture</h3>
              {!horsBrouillon && (
                <Button type="button" size="sm" variant="outline" onClick={addLine}>
                  <Plus /> Ajouter une ligne
                </Button>
              )}
            </div>

            {errors.lines && (
              <p role="alert" className="text-xs text-destructive">{errors.lines}</p>
            )}

            {/* VX184 — même comportement mobile que le générateur : `.lines-table`
                bascule en cartes empilées sous 768px via `data-label`
                (index.css ~2264-2296), au lieu du scroll horizontal permanent. */}
            <div className="lines-table-wrap">
              <table className="lines-table" ref={linesTableRef}>
                <thead>
                  <tr>
                    <th style={{ minWidth: 160 }}>Produit</th>
                    <th>Désignation</th>
                    <th className="col-num">Qté</th>
                    <th className="col-num">Prix HT (DH)</th>
                    <th className="col-num">Rem. %</th>
                    <th className="col-num">TVA %</th>
                    <th className="col-num">Total HT</th>
                    <th className="col-del" />
                  </tr>
                </thead>
                <tbody>
                  {lines.map(l => {
                    const lineTotal =
                      (parseFloat(l.quantite)      || 0) *
                      (parseFloat(l.prix_unitaire) || 0) *
                      (1 - (parseFloat(l.remise)   || 0) / 100)
                    return (
                      <tr key={l._key} data-line-key={l._key}>
                        <td data-label="Produit">
                          {/* VX91 — picker partagé (recherche + prix), même
                              composant que DevisForm/DevisGenerator : fin du
                              <Select> natif non filtrable sur 50+ SKU. */}
                          {horsBrouillon ? (
                            <span className="text-xs">
                              {produits.find(p => String(p.id) === String(l.produit))?.nom ?? l.designation}
                            </span>
                          ) : (
                          <ProduitPicker
                            produits={produits}
                            value={l.produit ? String(l.produit) : ''}
                            onChange={v => onProduitChange(l._key, v)}
                            // VX238(c) — choisir un produit avance directement
                            // le focus sur la Qté de CETTE ligne (réutilise
                            // data-line-key, VX90) au lieu de rendre le focus
                            // au bouton déclencheur.
                            onPicked={() => {
                              document
                                .querySelector(`tr[data-line-key="${l._key}"] [data-role="line-qty"]`)
                                ?.focus()
                            }}
                          />
                          )}
                        </td>
                        <td data-label="Désignation">
                          <Input className="h-[var(--control-h-sm)] text-xs" value={l.designation}
                                 disabled={horsBrouillon}
                                 onChange={e => setLine(l._key, 'designation', e.target.value)}
                                 placeholder="Désignation" />
                          {/* AFAC70 — motif serveur de l'échec de CETTE ligne. */}
                          {lineErrors[l._key] && (
                            <p role="alert" data-line-error={l._key}
                               className="m-0 mt-1 text-xs text-destructive">
                              {lineErrors[l._key]}
                            </p>
                          )}
                        </td>
                        <td data-label="Qté">
                          <Input type="number" min="0.01" step="0.01" data-role="line-qty" disabled={horsBrouillon}
                                 className="h-[var(--control-h-sm)] text-right text-xs"
                                 value={l.quantite}
                                 onChange={e => setLine(l._key, 'quantite', e.target.value)} />
                        </td>
                        <td data-label="Prix HT (DH)">
                          <Input type="number" min="0" step="0.01" disabled={horsBrouillon}
                                 className="h-[var(--control-h-sm)] text-right text-xs"
                                 value={l.prix_unitaire}
                                 onChange={e => setLine(l._key, 'prix_unitaire', e.target.value)}
                                 // VX237 — montant collé d'Excel ("12 500,00",
                                 // "3 200 DH"...) nettoyé au lieu de tomber
                                 // brut dans le champ number.
                                 onPaste={e => {
                                   const clean = parsePastedAmount(e.clipboardData?.getData('text'))
                                   if (clean == null) return
                                   e.preventDefault()
                                   setLine(l._key, 'prix_unitaire', clean)
                                 }} />
                        </td>
                        <td data-label="Rem. %">
                          <Input type="number" min="0" max="100" step="0.01" disabled={horsBrouillon}
                                 className="h-[var(--control-h-sm)] text-right text-xs"
                                 value={l.remise}
                                 onChange={e => setLine(l._key, 'remise', e.target.value)} />
                        </td>
                        <td data-label="TVA %">
                          <Input type="number" min="0" max="100" step="0.01" disabled={horsBrouillon}
                                 className="h-[var(--control-h-sm)] text-right text-xs"
                                 value={l.taux_tva}
                                 placeholder={String(tva)}
                                 title="Vide = taux global de la facture"
                                 onChange={e => setLine(l._key, 'taux_tva', e.target.value)} />
                        </td>
                        <td className="line-total" data-label="Total HT">{formatMAD(lineTotal, { withSymbol: false })} DH</td>
                        <td>
                          {!horsBrouillon && lines.length > 1 && (
                            <IconButton type="button" label="Supprimer la ligne" size="sm"
                                        className="text-destructive hover:bg-destructive/10"
                                        onClick={() => removeLine(l._key)}>
                              <Trash2 />
                            </IconButton>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>

          {/* ── Totaux ── */}
          <div className="ml-auto w-full max-w-xs rounded-lg border border-border bg-muted/30 p-3 text-sm">
            {!totauxServeur && (
              <p data-testid="totaux-estimation" className="m-0 mb-1 text-xs font-medium text-warning">
                Estimation — le total définitif est calculé à l&apos;enregistrement
              </p>
            )}
            <div className="flex justify-between py-0.5">
              <span className="text-muted-foreground">Sous-total HT</span>
              <span className="tabular-nums">{formatMAD(subtotalHT, { withSymbol: false })} DH</span>
            </div>
            {remGlobal > 0 && (
              <div className="flex justify-between py-0.5 text-warning">
                <span>Remise globale ({remGlobal}%)</span>
                <span className="tabular-nums">−{formatMAD(subtotalHT * remGlobal / 100, { withSymbol: false })} DH</span>
              </div>
            )}
            <div className="flex justify-between py-0.5">
              <span className="text-muted-foreground">Total HT</span>
              <strong className="tabular-nums">{formatMAD(aff.ht, { withSymbol: false })} DH</strong>
            </div>
            {tauxDistincts.length > 1 && !totauxServeur ? (
              <>
                {tauxDistincts
                  .sort((a, b) => Number(a) - Number(b))
                  .map(taux => (
                    <div key={taux} className="flex justify-between py-0.5">
                      <span className="text-muted-foreground">
                        TVA {Number(taux)} %
                      </span>
                      <span className="tabular-nums">
                        {formatMAD(tvaParTaux[taux] * Number(taux) / 100, { withSymbol: false })} DH
                      </span>
                    </div>
                  ))}
                <div className="flex justify-between py-0.5">
                  <span className="text-muted-foreground">TVA totale</span>
                  <span className="tabular-nums">{formatMAD(aff.tva, { withSymbol: false })} DH</span>
                </div>
              </>
            ) : (
              <div className="flex justify-between py-0.5">
                <span className="text-muted-foreground">{totauxServeur ? 'TVA' : `TVA (${tva}%)`}</span>
                <span className="tabular-nums">{formatMAD(aff.tva, { withSymbol: false })} DH</span>
              </div>
            )}
            {arrondiDevis !== 0 && (
              <div className="flex justify-between py-0.5">
                <span className="text-muted-foreground">Arrondi du devis</span>
                <span className="tabular-nums">{formatMAD(arrondiDevis, { withSymbol: false })} DH</span>
              </div>
            )}
            <div className="mt-1 flex justify-between border-t border-border pt-1.5 text-base">
              <span className="font-semibold">{totauxServeur ? 'Total TTC' : 'Total TTC (estimation)'}</span>
              <strong className="tabular-nums text-primary">{formatMAD(aff.ttc, { withSymbol: false })} DH</strong>
            </div>
          </div>

          {/* ── Conditions et mode de paiement (mention Art. 145) ── */}
          <div className="grid gap-1.5">
            <Label htmlFor="fc-conditions">Conditions et mode de paiement</Label>
            <Textarea id="fc-conditions" rows={2} value={fields.conditions_paiement}
                      onChange={e => setField('conditions_paiement', e.target.value)}
                      placeholder="Ex. Virement à 30 jours, RIB…" />
          </div>

          {/* ── CIQ226 — référence de commande du client ── */}
          <div className="grid gap-1.5">
            <Label htmlFor="fc-ref-commande">Référence de commande du client</Label>
            <Input id="fc-ref-commande" maxLength={60} value={fields.reference_commande_client}
                   onChange={e => setField('reference_commande_client', e.target.value)} />
          </div>

          {/* ── CIQ226 — retenue de garantie : montant retenu, exigible, libération ── */}
          {isEdit && retenue.retenue_garantie_mad != null && (
            <div className="grid gap-1.5 rounded-lg border border-border p-3 text-sm" data-testid="fc-retenue">
              <p>Retenue de garantie : <strong>{formatMAD(retenue.retenue_garantie_mad)}</strong>
                {retenue.retenue_liberee_le ? ` — libérée le ${retenue.retenue_liberee_le}` : ' — non libérée'}</p>
              <p data-testid="fc-montant-exigible">Montant exigible : <strong>{formatMAD(retenue.montant_exigible)}</strong></p>
              {!retenue.retenue_liberee_le && (
                <div className="flex flex-wrap items-end gap-2">
                  <div className="grid gap-1">
                    <Label htmlFor="fc-date-liberation">Date de réception définitive</Label>
                    <Input id="fc-date-liberation" type="date" value={dateLiberation}
                           onChange={e => setDateLiberation(e.target.value)} />
                  </div>
                  <Button type="button" variant="outline" loading={liberation.enCours}
                          disabled={!dateLiberation} onClick={libererRetenue}
                          data-testid="fc-liberer-retenue">
                    Libérer la retenue
                  </Button>
                </div>
              )}
              {liberation.erreur && <p className="text-xs text-destructive">{liberation.erreur}</p>}
            </div>
          )}

          {/* ── Note ── */}
          <div className="grid gap-1.5">
            <Label htmlFor="fc-note">Note interne</Label>
            <Textarea id="fc-note" rows={3} value={fields.note}
                      onChange={e => setField('note', e.target.value)}
                      placeholder="Conditions de paiement, remarques..." />
          </div>

          {errors.submit && (
            <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {errors.submit}
            </p>
          )}

          {isEdit && facture?.id && (
            <div className="border-t border-border pt-4">
              <p className="mb-2 text-sm font-semibold text-foreground">Pièces jointes</p>
              <AttachmentsPanel model="ventes.facture" id={facture.id} />
            </div>
          )}

          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving} disabled={modeBcDevis}
                    title={modeBcDevis ? 'Utilisez « Créer la facture depuis ce BC »' : undefined}>
              {isEdit ? 'Mettre à jour' : 'Créer la facture'}
            </Button>
          </FormActions>
        </Form>

        {/* VX91 — création rapide client (QG3) ; sélectionne le nouveau client */}
        <ClientQuickCreateModal
          open={clientQuickCreateOpen}
          onClose={() => setClientQuickCreateOpen(false)}
          onCreated={(c) => {
            setClients(cs => [...cs, c])
            setField('client', String(c.id))
            setClientQuickCreateOpen(false)
          }}
        />
      </DialogContent>
    </Dialog>
  )
}
