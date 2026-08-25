import { useEffect, useState } from 'react'
import {
  Link2, Check, ExternalLink, MessageCircle, Eye, Send,
} from 'lucide-react'
import {
  Button, Checkbox,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../../ui'
import crmApi from '../../../api/crmApi'
import { formatDateTime, normalizePhoneE164 } from '../../../lib/format'
import { errorMessageFrom } from '../../../lib/toast'
// Même helper WhatsApp que DevisTab.jsx (buildWaUrl) — un seul lien wa.me,
// un seul endroit qui sait le construire.
import { buildWaUrl } from '../../ventes/clientProposalLink'
import {
  SECTIONS_QUESTIONNAIRE, questionsDepuisReponse, questionsPourEnvoi,
  nbSectionsChoisies, questionnaireWhatsappText,
} from './questionnaireLink'

// LANE Q-C (fondateur 25/08/2026) — « Envoyer un questionnaire » sur la fiche
// lead : même patron que le dialogue « Envoyer au client » de DevisTab.jsx
// (L-SECT) — whitelist de sections cochables, mint idempotent via POST, et la
// vérité affichée vient TOUJOURS de la réponse serveur, jamais devinée.
// Ouvert depuis IdentityRail (onAction('questionnaire')), monté en satellite
// par LeadWorkspace.jsx — même famille que SigneDialog/PlanActiviteDialog/
// ConvertirClientDialog (open inconditionnel tant que le parent le monte).
//
// DÉFAUT des cases = ce qui MANQUE au lead (`questionsDepuisReponse`) ; si un
// lien existait déjà avec des questions choisies, on repart de CES questions
// (vérité serveur), jamais des manquantes ACTUELLES. Toutes les cases restent
// cochables/décochables librement avant chaque (ré)envoi — ordre fondateur :
// « every thing can be ticked or unticked before sending ».
//
// ADDENDUM fondateur (25/08/2026) — le mint renvoie EN PLUS `url_interne` :
// un aperçu du commercial (même page, jeton DIFFÉRENT) qui n'envoie ni
// notification ni trace côté client. Affiché à part, clairement distingué du
// lien à ENVOYER (`url`) — c'est `url`, jamais `url_interne`, qui part dans
// le message WhatsApp (questionnaireWhatsappText, questionnaireLink.js —
// testé : le message ne contient jamais url_interne).
export default function QuestionnaireDialog({ lead, onClose }) {
  const leadId = lead?.id ?? null
  const prenom = (lead?.prenom || '').trim()
  const leadPhone = (lead?.whatsapp || lead?.telephone || '').trim()
  const waPhone = normalizePhoneE164(leadPhone)

  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null) // dernière réponse serveur brute
  const [sel, setSel] = useState({}) // état LOCAL des cases (modifiable)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(null) // 'client' | 'interne' | null

  // Ouverture : mint SANS body → le serveur renvoie manquantes + questions
  // déjà stockées (idempotent — ne crée jamais un second lien pour rien).
  useEffect(() => {
    if (!leadId) return undefined
    let cancelled = false
    // Même patron que LeadWorkspace.jsx (leadLoading) : le vrai début d'une
    // opération réseau déclenchée PAR cet effet, pas un dérivé de props/state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true)
    setError(null)
    crmApi.mintQuestionnaireLien(leadId)
      .then((res) => {
        if (cancelled) return
        setData(res.data)
        setSel(questionsDepuisReponse(res.data))
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessageFrom(err, 'Lien de questionnaire indisponible.'))
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [leadId])

  const toggle = (key, valeur) => {
    setSel((cur) => ({ ...cur, [key]: !!valeur }))
  }

  const genererLien = () => {
    if (!leadId) return
    setBusy(true)
    setError(null)
    crmApi.mintQuestionnaireLien(leadId, { questions: questionsPourEnvoi(sel) })
      .then((res) => {
        setData(res.data)
        // La vérité affichée vient TOUJOURS de la réponse serveur (même
        // règle que L-NIV-UI/L-SECT dans DevisTab.jsx).
        setSel(questionsDepuisReponse(res.data))
        setCopied(null)
      })
      .catch((err) => setError(errorMessageFrom(err, 'Mise à jour du lien impossible.')))
      .finally(() => setBusy(false))
  }

  const copier = async (which, url) => {
    if (!url) return
    try {
      await navigator.clipboard?.writeText(url)
      setCopied(which)
      window.setTimeout(() => setCopied((cur) => (cur === which ? null : cur)), 2000)
    } catch { /* presse-papier indisponible — le lien reste ouvrable */ }
  }

  const ouvrir = (url) => {
    if (url) window.open(url, '_blank', 'noopener')
  }

  // Le lien ENVOYÉ au client est TOUJOURS `data.url` — jamais `url_interne`.
  const envoyerWhatsApp = () => {
    if (!waPhone || !data?.url) return
    const waUrl = buildWaUrl(waPhone, questionnaireWhatsappText(prenom, data.url))
    if (waUrl) window.open(waUrl, '_blank', 'noopener')
  }

  const nb = nbSectionsChoisies(sel)

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Envoyer un questionnaire</DialogTitle>
          <DialogDescription>
            Le lead reçoit un lien vers quelques questions ciblées — cochez ce
            qu&apos;il doit renseigner, décochez le reste.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <p className="gen-hint" role="status">Chargement…</p>
        ) : (
          <>
            <div className="lw-context-devis-sections">
              <p className="gen-hint">Ce que le lead devra renseigner :</p>
              {SECTIONS_QUESTIONNAIRE.map(({ key, label }) => (
                <label key={key} className="lw-context-devis-section">
                  <Checkbox
                    checked={!!sel[key]}
                    onCheckedChange={(v) => toggle(key, v)}
                    aria-label={label}
                  />
                  {label}
                </label>
              ))}
              <p className="gen-hint">
                {nb} section{nb > 1 ? 's' : ''} seront demandées.
              </p>
            </div>

            <div className="lw-context-devis-links">
              <Button type="button" size="sm" disabled={busy} onClick={genererLien}>
                <Send size={14} aria-hidden="true" />
                {busy ? '…' : 'Générer / mettre à jour le lien'}
              </Button>
            </div>

            {data?.url && (
              <>
                <div className="lw-context-devis-links">
                  <Button
                    type="button" size="sm" variant="outline"
                    title="Copier le lien à envoyer au client"
                    onClick={() => copier('client', data.url)}
                  >
                    {copied === 'client'
                      ? <Check size={14} aria-hidden="true" />
                      : <Link2 size={14} aria-hidden="true" />}
                    {copied === 'client' ? 'Copié' : 'Copier le lien'}
                  </Button>
                  <Button
                    type="button" size="sm" variant="ghost"
                    aria-label="Ouvrir le lien du questionnaire dans un nouvel onglet"
                    title="Ouvrir le lien à envoyer au client"
                    onClick={() => ouvrir(data.url)}
                  >
                    <ExternalLink size={14} aria-hidden="true" />
                  </Button>
                  <Button
                    type="button" size="sm" variant="outline"
                    disabled={!waPhone}
                    title={waPhone
                      ? 'Envoyer le lien du questionnaire par WhatsApp'
                      : 'Aucun numéro de téléphone exploitable'}
                    onClick={envoyerWhatsApp}
                  >
                    <MessageCircle size={14} aria-hidden="true" /> WhatsApp
                  </Button>
                </div>

                {data.expires_at && (
                  <p className="gen-hint">
                    Valable jusqu&apos;au {formatDateTime(data.expires_at)}.
                  </p>
                )}

                {/* ADDENDUM fondateur — aperçu interne, jeton DIFFÉRENT du
                    lien client : n'envoie jamais de notification ni de trace
                    côté client, et ne part JAMAIS dans le message WhatsApp
                    ci-dessus (questionnaireWhatsappText ne reçoit que `url`). */}
                {data.url_interne && (
                  <div className="lw-context-devis-links">
                    <span className="gen-hint">Aperçu interne (sans notification) :</span>
                    <Button
                      type="button" size="sm" variant="ghost"
                      title="Copier le lien d'aperçu interne (ne notifie pas le lead)"
                      onClick={() => copier('interne', data.url_interne)}
                    >
                      {copied === 'interne'
                        ? <Check size={14} aria-hidden="true" />
                        : <Eye size={14} aria-hidden="true" />}
                      {copied === 'interne' ? 'Copié' : 'Copier'}
                    </Button>
                    <Button
                      type="button" size="sm" variant="ghost"
                      aria-label="Ouvrir l'aperçu interne du questionnaire dans un nouvel onglet"
                      title="Ouvrir sans notifier le lead"
                      onClick={() => ouvrir(data.url_interne)}
                    >
                      <ExternalLink size={14} aria-hidden="true" />
                    </Button>
                  </div>
                )}
              </>
            )}

            {!leadPhone && (
              <p className="gen-hint">Aucun numéro de téléphone pour ce lead.</p>
            )}
            {leadPhone && !waPhone && (
              <p className="gen-hint">Numéro de téléphone invalide.</p>
            )}
          </>
        )}

        {error && <p className="gen-hint" role="status">{error}</p>}
      </DialogContent>
    </Dialog>
  )
}
