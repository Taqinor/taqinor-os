/**
 * FG35 — Lead express quick capture.
 *
 * Formulaire minimal (nom + téléphone + canal + owner=me) pour saisir un lead
 * rapidement (walk-in, salon, terrain mobile) sans ouvrir le lourd LeadForm.
 *
 * Comportement :
 *   - Vérification inline de doublons après saisie du téléphone (>= 8 chiffres)
 *     via GET /crm/leads/check-duplicates/?phone=… — avertissement non bloquant.
 *   - POST vers l'endpoint existant /crm/leads/ (identique au LeadForm).
 *   - Après création : appelle onSaved(lead) et se ferme.
 *   - XSAL8 — « Scanner une carte » (photo) pré-remplit le formulaire via
 *     l'OCR existant (503 douce sans clé configurée : message clair, aucune
 *     répétition automatique — l'utilisateur retombe sur la saisie manuelle).
 */
import { useState, useEffect, useId, useRef } from 'react'
import { AlertTriangle } from 'lucide-react'
import crmApi from '../../../api/crmApi'
import useCanaux from '../../../features/crm/useCanaux'
import { usePasteClean, parsePastedPhone, parsePasteCard } from '../../../hooks/usePasteClean'
import PhoneHint from '../../../components/PhoneHint'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle,
  Form, FormField, FormActions, Input,
} from '../../../ui'

// Dédoublonnage grossier : on retire les non-chiffres pour comparer.
function normalizePhone(raw) {
  return (raw || '').replace(/\D/g, '')
}

// VX240(e) — dernier canal utilisé (localStorage, modifiable), même patron
// que VX93 (lireLastTva/lireDernierMode) : le canal ne reset plus en dur à
// 'walk_in' à chaque ouverture (un salon/terrain saisit rafale sur le même
// canal, retaper à chaque lead coûtait un clic évitable).
const LEAD_EXPRESS_CANAL_KEY = 'taqinor.leadExpress.lastCanal'
const lireLastCanal = () => {
  try { return window.localStorage.getItem(LEAD_EXPRESS_CANAL_KEY) || 'walk_in' }
  catch { return 'walk_in' }
}
const ecrireLastCanal = (v) => {
  try { if (v) window.localStorage.setItem(LEAD_EXPRESS_CANAL_KEY, v) }
  catch { /* localStorage indisponible (navigation privée, quota) : no-op */ }
}

export default function LeadExpressModal({ onClose, onSaved }) {
  const formId = useId()
  const nomRef = useRef(null)
  const scanInputRef = useRef(null)

  const [nom, setNom] = useState('')
  const [telephone, setTelephone] = useState('')
  const [societe, setSociete] = useState('')
  const [email, setEmail] = useState('')
  const [canal, setCanal] = useState(lireLastCanal)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // FG35 — état de la vérification de doublons.
  // dupState: null (pas encore) | 'checking' | { warning: string|null }
  const [dupState, setDupState] = useState(null)
  // XSAL8 — scan de carte de visite : null | 'scanning' | { error } | { ok }
  const [scanState, setScanState] = useState(null)
  // Une fois l'OCR détecté indisponible (clé absente), on masque le bouton
  // pour le reste de la session — évite de retenter un appel voué à échouer.
  const [scanUnavailable, setScanUnavailable] = useState(false)
  // VX237 — carte de visite collée dans « Nom » : jamais répartie
  // silencieusement, un bandeau propose « Répartir » sur confirmation.
  const [cardPaste, setCardPaste] = useState(null)
  const onNomPaste = (e) => {
    const card = parsePasteCard(e.clipboardData?.getData('text'))
    if (card) setCardPaste(card)
  }
  const applyCardPaste = () => {
    if (!cardPaste) return
    setNom(cardPaste.nom)
    setTelephone(cardPaste.telephone)
    setCardPaste(null)
  }
  const onTelephonePaste = usePasteClean(parsePastedPhone, setTelephone)

  const { options: canauxOptions, loaded: canauxLoaded } = useCanaux()

  // Mise au point auto sur le champ nom à l'ouverture.
  useEffect(() => { nomRef.current?.focus() }, [])

  const handleScanFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = '' // permet de rescanner la même photo si besoin
    if (!file) return
    setScanState('scanning')
    try {
      const res = await crmApi.scanCarteVisite(file)
      const data = res.data || {}
      if (data.nom) setNom(data.nom + (data.prenom ? ` ${data.prenom}` : ''))
      if (data.telephone) setTelephone(data.telephone)
      if (data.societe) setSociete(data.societe)
      if (data.email) setEmail(data.email)
      const dups = data.doublons ?? []
      setScanState({
        ok: true,
        warning: dups.length
          ? `Doublon possible : ${dups.slice(0, 2).map((d) => d.nom || '?').join(', ')}.`
          : null,
      })
    } catch (err) {
      if (err?.response?.status === 503) {
        setScanUnavailable(true)
        setScanState(null)
        return
      }
      const detail =
        err?.response?.data?.detail || 'Lecture de la carte impossible — saisie manuelle.'
      setScanState({ error: detail })
    }
  }

  // Vérification de doublons dès que le numéro est suffisamment long.
  useEffect(() => {
    const digits = normalizePhone(telephone)
    if (digits.length < 8) {
      // Pas assez de chiffres — on efface tout résultat précédent lors du prochain tick.
      const id = setTimeout(() => setDupState(null), 0)
      return () => clearTimeout(id)
    }
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDupState('checking')
    crmApi.checkDuplicates({ phone: telephone })
      .then((r) => {
        if (cancelled) return
        const dups = r.data ?? []
        if (dups.length > 0) {
          const names = dups.slice(0, 2).map((d) => d.nom || '?').join(', ')
          setDupState({
            warning: `Doublon possible : ${names}${dups.length > 2 ? ` + ${dups.length - 2} autre(s)` : ''}.`,
          })
        } else {
          setDupState({ warning: null })
        }
      })
      .catch(() => { if (!cancelled) setDupState({ warning: null }) })
    return () => { cancelled = true }
  }, [telephone])

  const dupChecking = dupState === 'checking'
  const dupWarning = dupState && typeof dupState === 'object' ? dupState.warning : null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!nom.trim()) { setError('Le nom est requis.'); return }
    setBusy(true)
    try {
      const payload = {
        nom: nom.trim(),
        telephone: telephone.trim() || null,
        societe: societe.trim() || null,
        email: email.trim() || null,
        canal: canal || null,
        // owner et company sont injectés côté serveur
      }
      const res = await crmApi.createLead(payload)
      ecrireLastCanal(canal)  // VX240(e) — mémorise le canal pour le prochain lead express
      onSaved?.(res.data)
      onClose?.()
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        (typeof err?.response?.data === 'string' ? err.response.data : null) ||
        'Erreur lors de la création du lead.'
      setError(detail)
    } finally {
      setBusy(false)
    }
  }

  return (
    // VX118(b) — les 23 références `lem-*` n'avaient AUCUN CSS depuis la
    // création de l'écran (HTML nu) ; migré sur Dialog+Form/FormField (le
    // langage des autres dialogues CRM), zéro CSS ajouté. Radix Dialog gère
    // nativement Echap/overlay-click (l'ancien handler manuel est retiré).
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle id={`${formId}-title`}>⚡ Nouveau lead express</DialogTitle>
        </DialogHeader>

        <Form onSubmit={handleSubmit} className="gap-4">
          {/* XSAL8 — Scan de carte de visite (photo) : masqué sans clé OCR
              configurée (503 rencontrée une fois → bouton retiré). */}
          {!scanUnavailable && (
            <div className="flex flex-col gap-1.5">
              <input
                ref={scanInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                capture="environment"
                onChange={handleScanFile}
                className="sr-only"
              />
              <Button
                type="button"
                variant="outline"
                className="w-fit"
                disabled={scanState === 'scanning'}
                onClick={() => scanInputRef.current?.click()}
              >
                {scanState === 'scanning' ? 'Lecture…' : '📇 Scanner une carte'}
              </Button>
              {scanState && scanState.error && (
                <p className="text-xs text-destructive" role="alert">{scanState.error}</p>
              )}
              {scanState && scanState.ok && scanState.warning && (
                <p className="flex items-center gap-1.5 text-xs text-warning" role="alert" aria-live="assertive">
                  <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" /> {scanState.warning}
                </p>
              )}
            </div>
          )}

          <FormField label="Nom" required htmlFor={`${formId}-nom`}>
            <Input
              id={`${formId}-nom`}
              ref={nomRef}
              type="text"
              placeholder="Nom du prospect"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              onPaste={onNomPaste}
              required
              autoComplete="off"
            />
          </FormField>
          {cardPaste && (
            <div
              role="status"
              className="-mt-2 flex flex-wrap items-center gap-2 rounded-md border border-info/30 bg-info/5 px-2.5 py-1.5 text-xs text-foreground"
            >
              <span>Carte de visite détectée — {cardPaste.nom} · {cardPaste.telephone}</span>
              <Button type="button" variant="outline" size="sm" onClick={applyCardPaste}>
                Répartir
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => setCardPaste(null)}>
                Ignorer
              </Button>
            </div>
          )}

          <FormField label="Société" htmlFor={`${formId}-societe`}>
            <Input
              id={`${formId}-societe`}
              type="text"
              placeholder="Société du prospect"
              value={societe}
              onChange={(e) => setSociete(e.target.value)}
              autoComplete="off"
            />
          </FormField>

          <FormField
            label="Téléphone"
            htmlFor={`${formId}-tel`}
            hint={dupChecking ? 'Vérification des doublons…' : undefined}
          >
            <Input
              id={`${formId}-tel`}
              type="tel"
              placeholder="06 00 00 00 00"
              value={telephone}
              onChange={(e) => setTelephone(e.target.value)}
              onPaste={onTelephonePaste}
              autoComplete="off"
            />
            {/* VX239 — <PhoneHint> extrait de ClientForm : aperçu de la forme
                normalisée uniquement (le check de doublons existant de cet
                écran, `dupState` ci-dessous, reste inchangé). */}
            <PhoneHint value={telephone} testId="lem-tel-hint" />
          </FormField>
          {dupWarning && !dupChecking && (
            <p className="-mt-2 flex items-center gap-1.5 text-xs text-warning" role="alert" aria-live="assertive">
              <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" /> {dupWarning}
            </p>
          )}

          <FormField label="E-mail" htmlFor={`${formId}-email`}>
            <Input
              id={`${formId}-email`}
              type="email"
              placeholder="contact@exemple.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="off"
            />
          </FormField>

          <FormField label="Canal" htmlFor={`${formId}-canal`}>
            <select
              id={`${formId}-canal`}
              className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
              value={canal}
              onChange={(e) => setCanal(e.target.value)}
              disabled={!canauxLoaded}
            >
              <option value="">— Choisir —</option>
              {canauxOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </FormField>

          {error && (
            <p className="text-sm text-destructive" role="alert">{error}</p>
          )}

          <FormActions sticky={false}>
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              Annuler
            </Button>
            <Button type="submit" disabled={busy || !nom.trim()}>
              {busy ? 'Création…' : 'Créer le lead'}
            </Button>
          </FormActions>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
