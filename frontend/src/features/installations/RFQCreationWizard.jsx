import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, Send } from 'lucide-react'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { Button, Spinner } from '../../ui'
import { formatMAD } from '../../lib/format'
import installationsApi from '../../api/installationsApi'
import stockApi from '../../api/stockApi'

/* ============================================================================
   NTP2P28 — Wizard de création RFQ depuis une DemandeAchat approuvée.

   Purement FRONTEND : appelle dans l'ordre les endpoints RFQ existants
   (FG311/XPUR20) — createRFQ → consulterFournisseurRFQ (une fois par
   fournisseur choisi) → envoyerRFQ + envoyerConsultationsRFQ (email ET
   WhatsApp manuel-first). Aucun nouveau modèle : `RFQ` ne porte pas de
   lignes structurées — l'étape 2 REPREND l'objet et affiche les lignes de
   la demande en lecture seule (contexte pour l'acheteur), l'étape 1
   SUGGÈRE les fournisseurs PRÉFÉRÉS des produits de la demande (dérivés de
   `Produit.fournisseur`) tout en laissant la liste complète disponible.
   ========================================================================== */

const STEPS = ['Fournisseurs', 'Lignes de la demande', 'Date limite & envoi']

export default function RFQCreationWizard({ demande, onClose, onDone }) {
  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(true)
  const [fournisseurs, setFournisseurs] = useState([])
  const [suggeresIds, setSuggeresIds] = useState(() => new Set())
  const [selectedIds, setSelectedIds] = useState(() => new Set())
  const [dateLimite, setDateLimite] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [resultat, setResultat] = useState(null) // { rfqId, reference, resultats }

  useEffect(() => {
    let active = true
    Promise.all([
      stockApi.getFournisseurs({ page_size: 200 }).catch(() => ({ data: [] })),
      ...(demande.lignes ?? [])
        .filter((l) => l.produit)
        .map((l) => stockApi.getProduit(l.produit).catch(() => null)),
    ]).then(([fRes, ...produits]) => {
      if (!active) return
      const list = Array.isArray(fRes.data) ? fRes.data : (fRes.data?.results ?? [])
      setFournisseurs(list)
      const suggeres = new Set(
        produits.filter(Boolean).map((p) => p.data?.fournisseur).filter(Boolean))
      setSuggeresIds(suggeres)
      setSelectedIds(new Set(suggeres))
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const toggleFournisseur = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const creerEtEnvoyer = async () => {
    setBusy(true); setError(null)
    try {
      const create = await installationsApi.createRFQ({
        objet: demande.objet, demande: demande.id,
        date_limite_reponse: dateLimite || null,
      })
      const rfqId = create.data.id
      await Promise.all(
        [...selectedIds].map((fid) =>
          installationsApi.consulterFournisseurRFQ(rfqId, fid)))
      await installationsApi.envoyerRFQ(rfqId)
      const envoi = await installationsApi.envoyerConsultationsRFQ(rfqId)
      setResultat({
        rfqId, reference: create.data.reference,
        resultats: envoi.data?.resultats ?? [],
      })
    } catch (err) {
      setError(err?.response?.data?.detail || 'La création de la RFQ a échoué.')
    } finally { setBusy(false) }
  }

  const suivant = () => {
    if (step === 0 && selectedIds.size === 0) {
      setError('Sélectionnez au moins un fournisseur à consulter.')
      return
    }
    setError(null)
    if (step < 2) setStep(step + 1); else creerEtEnvoyer()
  }
  const precedent = () => { setError(null); setStep((s) => Math.max(0, s - 1)) }

  if (resultat) {
    return (
      <ResponsiveDialog open onOpenChange={(o) => { if (!o) onDone?.(resultat) }} className="sm:max-w-lg" showClose={false}>
        <div className="modal-header">
          <h3 className="modal-title">RFQ {resultat.reference} envoyée</h3>
        </div>
        <div className="modal-body flex flex-col gap-3">
          <p className="flex items-center gap-2 text-sm text-success">
            <Check className="size-4" aria-hidden="true" />
            {selectedIds.size} fournisseur(s) consulté(s), lignes reprises de {demande.reference}.
          </p>
          {resultat.resultats.some((r) => r.whatsapp?.url) && (
            <div className="flex flex-col gap-1.5 rounded-lg border border-info/30 bg-info/10 p-2.5 text-sm">
              <span className="font-medium">Brouillons WhatsApp prêts (manuel-first) :</span>
              {resultat.resultats.filter((r) => r.whatsapp?.url).map((r) => {
                const f = fournisseurs.find((x) => x.id === r.fournisseur)
                return (
                  <a key={r.consultation} href={r.whatsapp.url} target="_blank" rel="noreferrer"
                     className="text-primary underline">
                    {f?.nom || `Fournisseur #${r.fournisseur}`}
                  </a>
                )
              })}
            </div>
          )}
        </div>
        <div className="modal-footer">
          <Button type="button" onClick={() => onDone?.(resultat)}>Fermer</Button>
        </div>
      </ResponsiveDialog>
    )
  }

  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose?.() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Créer une RFQ — {demande.reference}</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          {STEPS.map((label, i) => (
            <span key={label} className={i === step ? 'font-semibold text-foreground' : ''}>
              {i > 0 && ' → '}{label}
            </span>
          ))}
        </div>

        {loading ? (
          <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Spinner className="size-4" /> Chargement…
          </p>
        ) : (
          <>
            {step === 0 && (
              <div className="flex flex-col gap-1.5">
                <p className="text-sm text-muted-foreground">
                  Fournisseurs préférés des articles de la demande pré-cochés — ajoutez-en d&apos;autres si besoin.
                </p>
                {fournisseurs.map((f) => (
                  <label key={f.id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={selectedIds.has(f.id)}
                           onChange={() => toggleFournisseur(f.id)} />
                    {f.nom}
                    {suggeresIds.has(f.id) && (
                      <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary">Suggéré</span>
                    )}
                  </label>
                ))}
              </div>
            )}

            {step === 1 && (
              <div className="flex flex-col gap-1.5">
                <p className="text-sm text-muted-foreground">
                  Les lignes de {demande.reference} sont reprises dans l&apos;objet de la RFQ.
                </p>
                <table className="w-full text-sm">
                  <tbody>
                    {(demande.lignes ?? []).map((l) => (
                      <tr key={l.id}>
                        <td className="py-1">{l.designation || l.produit_nom}</td>
                        <td className="py-1 text-right tabular-nums">{l.quantite}</td>
                        <td className="py-1 text-right tabular-nums">{formatMAD(l.total_estime)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {step === 2 && (
              <div className="flex flex-col gap-2">
                <label className="form-label" htmlFor="rfq-wizard-limite">Date limite de réponse (optionnel)</label>
                <input id="rfq-wizard-limite" type="date" className="form-control"
                       value={dateLimite} onChange={(e) => setDateLimite(e.target.value)} />
                <p className="text-sm text-muted-foreground">
                  {selectedIds.size} fournisseur(s) seront consultés par email et brouillon WhatsApp (manuel-first).
                </p>
              </div>
            )}
          </>
        )}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        {step > 0 && (
          <Button type="button" variant="outline" onClick={precedent} disabled={busy}>
            <ArrowLeft className="size-4" aria-hidden="true" /> Précédent
          </Button>
        )}
        <Button type="button" loading={busy} disabled={loading || busy} onClick={suivant}>
          {step < 2 ? <>Suivant <ArrowRight className="size-4" aria-hidden="true" /></> : <><Send className="size-4" aria-hidden="true" /> Créer et envoyer</>}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}
