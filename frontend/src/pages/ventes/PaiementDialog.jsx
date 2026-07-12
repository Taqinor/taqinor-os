// VX230 — Modale d'enregistrement de paiement PARTAGÉE.
//
// Extraite VERBATIM de FactureList.jsx (mêmes champs, mêmes libellés, même flux
// ZFAC11 arrondi-caisse, mêmes défauts intelligents VX92/VX93) pour être montée
// AUSSI depuis RelancesPage : le chèque décroché après une relance s'encaisse
// LÀ où on chasse l'impayé, sans quitter/rouvrir/re-chercher la même facture.
//
// Contrat : `facture` (null = fermée) pilote l'ouverture ; `onOpenChange(false)`
// demande la fermeture au parent (qui possède l'état de ciblage) ; `onSaved()`
// est appelé après CHAQUE paiement enregistré pour que le parent rafraîchisse
// sa liste. Toute la logique de paiement (état, arrondi, chatter) vit ici.
import { useEffect, useRef, useState } from 'react'
import ventesApi from '../../api/ventesApi'
import api from '../../api/axios'
import {
  Button, Switch,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  Form, FormField, FormActions,
  Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  toast,
} from '../../ui'
import { formatMAD, formatDateTime } from '../../lib/format'

const MODES_PAIEMENT = [
  { value: 'especes',     label: 'Espèces' },
  { value: 'virement',    label: 'Virement' },
  { value: 'cheque',      label: 'Chèque' },
  { value: 'carte',       label: 'Carte' },
  { value: 'prelevement', label: 'Prélèvement' },
  { value: 'autre',       label: 'Autre' },
]

const todayIso = () => new Date().toISOString().slice(0, 10)

// VX92 — « Créer un autre » : persisté par poste (localStorage), défaut OFF
// (comportement historique inchangé). Un relevé bancaire = 5 paiements à saisir
// d'affilée ; sans ce toggle chaque paiement coûte un cycle fermer/rouvrir.
const PAY_CREER_UN_AUTRE_KEY = 'taqinor.factureList.paiement.creerUnAutre'
function lireCreerUnAutrePaiement() {
  try {
    return window.localStorage.getItem(PAY_CREER_UN_AUTRE_KEY) === '1'
  } catch {
    return false
  }
}
function ecrireCreerUnAutrePaiement(v) {
  try {
    window.localStorage.setItem(PAY_CREER_UN_AUTRE_KEY, v ? '1' : '0')
  } catch {
    // localStorage indisponible (navigation privée, quota) : no-op silencieux.
  }
}

// VX93 — défaut intelligent : dernier mode de paiement utilisé (localStorage).
// Repli sur 'virement' (cas le plus courant) si absent. Toujours modifiable.
const PAY_MODE_KEY = 'taqinor.factureList.paiement.dernierMode'
function lireDernierMode() {
  try {
    return window.localStorage.getItem(PAY_MODE_KEY) || 'virement'
  } catch {
    return 'virement'
  }
}
function ecrireDernierMode(v) {
  try {
    if (v) window.localStorage.setItem(PAY_MODE_KEY, v)
  } catch {
    // no-op silencieux.
  }
}

export default function PaiementDialog({ facture, onOpenChange, onSaved }) {
  const [paySaving, setPaySaving] = useState(false)
  const [payMontant, setPayMontant] = useState('')
  const [payDate, setPayDate] = useState(todayIso)
  const [payMode, setPayMode] = useState(lireDernierMode)  // VX93 — dernier mode utilisé
  // VX249(b) — payMode : 1 des 4 champs VX93 « suggérés ». « Suggéré » tant que
  // l'utilisateur n'a pas choisi LUI-MÊME un mode pour CE paiement.
  const [payModeTouched, setPayModeTouched] = useState(false)
  const [payModeFocused, setPayModeFocused] = useState(false)
  const [payReference, setPayReference] = useState('')
  // ZFAC11 — proposition d'arrondi de caisse (règlement espèces).
  const [arrondiCaisse, setArrondiCaisse] = useState(null)
  // VX92 — « Créer un autre » : persisté, défaut OFF.
  const [payCreerUnAutre, setPayCreerUnAutre] = useState(lireCreerUnAutrePaiement)
  const payMontantRef = useRef(null)

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

  // (Ré)initialise le formulaire à chaque nouvelle facture ciblée.
  useEffect(() => {
    if (!facture) return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- (ré)init form on facture change
    setPayMontant(facture.montant_du ?? '')
    setPayDate(todayIso())
    setPayMode(lireDernierMode())  // VX93 — pré-remplit avec le dernier mode utilisé
    setPayModeTouched(false)  // VX249(b) — nouveau paiement → « suggéré » redevient vrai
    setPayReference('')
    setArrondiCaisse(null)
    setFactureActivites([])
    loadActivites(facture.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facture?.id])

  // ZFAC11 — quand le mode passe à « espèces », interroge le reste à payer
  // arrondi au pas de caisse société. Aucun arrondi configuré → applicable
  // false, aucune proposition affichée (comportement inchangé).
  useEffect(() => {
    if (!facture || payMode !== 'especes') return undefined
    let annule = false
    ventesApi.arrondiCaisseFacture(facture.id, 'especes')
      .then(({ data }) => { if (!annule) setArrondiCaisse(data) })
      .catch(() => { if (!annule) setArrondiCaisse(null) })
    return () => { annule = true; setArrondiCaisse(null) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facture?.id, payMode])

  const appliquerArrondiCaisse = () => {
    if (arrondiCaisse?.montant_arrondi != null) {
      setPayMontant(arrondiCaisse.montant_arrondi)
    }
  }

  const handleEnregistrerPaiement = async (e) => {
    e.preventDefault()
    if (!facture) return
    setPaySaving(true)
    try {
      await ventesApi.enregistrerPaiement(facture.id, {
        montant: parseFloat(payMontant),
        date_paiement: payDate,
        mode: payMode,
        reference: payReference || undefined,
      })
      ecrireDernierMode(payMode)  // VX93 — mémorise le mode pour le prochain paiement
      toast.success('Paiement enregistré.')
      onSaved?.()
      // VX92 — « Créer un autre » : on vide les champs (sauf la facture ciblée,
      // inchangée) et on refocalise le montant au lieu de fermer.
      if (payCreerUnAutre) {
        setPayMontant('')
        setPayDate(todayIso())
        setPayMode(lireDernierMode())  // VX93 — ré-applique le dernier mode saisi
        setPayModeTouched(false)  // VX249(b) — paiement suivant → « suggéré » redevient vrai
        setPayReference('')
        loadActivites(facture.id)
        payMontantRef.current?.focus()
      } else {
        onOpenChange?.(false)
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Enregistrement du paiement impossible.')
    } finally {
      setPaySaving(false)
    }
  }

  return (
    <Dialog open={!!facture} onOpenChange={(o) => { if (!o) onOpenChange?.(false) }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Enregistrer un paiement — {facture?.reference}</DialogTitle>
          <DialogDescription>
            Payé {formatMAD(facture?.montant_paye)} / Dû {formatMAD(facture?.montant_du)}
          </DialogDescription>
        </DialogHeader>
        <Form onSubmit={handleEnregistrerPaiement} className="gap-4">
          <FormField label="Montant (MAD)" required htmlFor="pay-montant" fullWidth>
            <Input id="pay-montant" ref={payMontantRef} type="number" min="0" step="any" required
                   autoFocus
                   value={payMontant} onChange={e => setPayMontant(e.target.value)} />
          </FormField>
          <FormField label="Date de paiement" required htmlFor="pay-date">
            <Input id="pay-date" type="date" required
                   value={payDate} onChange={e => setPayDate(e.target.value)} />
          </FormField>
          {/* VX249(b) — payMode « suggéré » : contour pointillé + micro-libellé
              au focus tant que le dernier mode mémorisé n'a pas été touché,
              retiré dès la première modification. */}
          <FormField
            label="Mode"
            htmlFor="pay-mode"
            hint={!payModeTouched && payModeFocused ? 'Suggéré — modifiable' : undefined}
          >
            <Select value={payMode} onValueChange={(v) => { setPayMode(v); setPayModeTouched(true) }}>
              <SelectTrigger
                id="pay-mode"
                className={!payModeTouched ? 'vx-suggested-field' : undefined}
                onFocus={() => setPayModeFocused(true)}
                onBlur={() => setPayModeFocused(false)}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MODES_PAIEMENT.map(m => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          {/* ZFAC11 — proposition d'arrondi de caisse (espèces). */}
          {payMode === 'especes' && arrondiCaisse?.applicable && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
              <p className="text-amber-800">
                Arrondi espèces : {formatMAD(arrondiCaisse.montant_arrondi)}
                {' '}(écart de {formatMAD(arrondiCaisse.ecart)} tracé « Arrondi espèces »).
              </p>
              <Button type="button" variant="ghost" size="sm" className="mt-1"
                      onClick={appliquerArrondiCaisse}>
                Appliquer le montant arrondi
              </Button>
            </div>
          )}
          <FormField label="Référence (optionnel)" htmlFor="pay-ref" fullWidth>
            <Input id="pay-ref" type="text"
                   value={payReference} onChange={e => setPayReference(e.target.value)} />
          </FormField>
          <FormActions sticky={false}>
            {/* VX92 — « Créer un autre » : saisir plusieurs paiements d'affilée
                (ex. relevé bancaire) sans rouvrir la modale à chaque fois. */}
            <label className="mr-auto flex items-center gap-2 text-sm text-muted-foreground">
              <Switch
                checked={payCreerUnAutre}
                onCheckedChange={(v) => { setPayCreerUnAutre(v); ecrireCreerUnAutrePaiement(v) }}
                aria-label="Créer un autre"
              />
              Créer un autre
            </label>
            <Button type="button" variant="ghost" onClick={() => onOpenChange?.(false)}>Annuler</Button>
            <Button type="submit" loading={paySaving}>Enregistrer</Button>
          </FormActions>
        </Form>
        {/* Historique des paiements déjà encaissés sur cette facture. */}
        <div className="mt-1 border-t pt-3">
          <p className="mb-2 text-sm font-medium">Paiements encaissés</p>
          {(facture?.paiements?.length ?? 0) === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun paiement enregistré.</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {facture.paiements.map(p => (
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
                    {a.created_at ? formatDateTime(a.created_at) : '—'}
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
  )
}
