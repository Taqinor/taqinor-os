/**
 * ToitureDesign — page ERP AUTHENTIFIÉE qui héberge le builder 3D de toiture
 * (apps/web/src/scripts/roof-tool-pro11.ts) DANS l'ERP, via la session de
 * Meriem (cookie httpOnly `access_token` porté par l'axios ERP). PAS de
 * formulaire de connexion, PAS de jeton Bearer, PAS de sessionStorage : la page
 * est MÊME ORIGINE que le backend (api.taqinor.ma), donc tous les appels axios
 * portent la session automatiquement (`withCredentials`).
 *
 * Flux :
 *   1. au montage : charge le lead (GET /crm/leads/<id>/) + la config carte
 *      (GET /ventes/roof-config/ pour la clé MapTiler) ;
 *   2. rend l'échafaudage `rp9-*` (copié de l'ancienne page astro publique) puis
 *      boote le builder COMPLET hydraté avec le repère/contour du client ;
 *   3. UN SEUL bouton « Générer le devis & envoyer au client » enchaîne :
 *        a. POST /ventes/devis/from-layout/  {layout, lead}  → {id, reference,
 *           proposal_token, proposal_path}
 *        b. POST /ventes/devis/<id>/layout/  (persistance idempotente du layout)
 *        c. capture le PNG de la 3D → POST /ventes/devis/<id>/roof-image/ (multipart)
 *        d. bascule sur l'état « Prêt à envoyer » : lien de proposition tokenisé
 *           + WhatsApp / e-mail / copier.
 *   En cas d'échec, le tracé de Meriem n'est JAMAIS perdu et le bouton se
 *   réactive pour relancer (messages FR lisibles).
 *
 * L'ancienne page publique `apps/web/src/pages/internal/devis-design.astro`
 * (login form + token + cross-domain) est remplacée par celle-ci. La source du
 * builder n'est PAS modifiée : on l'importe seulement via l'alias `@roofbuilder`.
 */
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import api from '../../api/axios'
import ventesApi from '../../api/ventesApi'
import { toastInfo } from '../../lib/toast'
import '../../styles/roofbuilder.css'

// ── Helpers de livraison (portés de apps/web/src/lib/devisDesign.ts +
//    whatsapp.ts — purs, sans dépendance ; on ne réimporte pas la source web). ──
function designProposalUrl(origin, proposalPath) {
  const base = (origin || '').replace(/\/+$/, '')
  const path = proposalPath?.startsWith('/') ? proposalPath : `/${proposalPath ?? ''}`
  return `${base}${path}`
}
function designWhatsappText(name, proposalUrl) {
  const hello = name?.trim() ? `Bonjour ${name.trim()}, ` : 'Bonjour, '
  return (
    `${hello}voici votre proposition d'installation solaire Taqinor : ${proposalUrl} ` +
    `N'hésitez pas à me poser vos questions.`
  )
}
function whatsappLink(number, text) {
  const digits = (number || '').replace(/\D/g, '')
  return `https://wa.me/${digits}?text=${encodeURIComponent(text)}`
}
function designMailto(email, name, proposalUrl) {
  const hello = name?.trim() ? `Bonjour ${name.trim()},` : 'Bonjour,'
  const subject = encodeURIComponent('Votre proposition solaire Taqinor')
  const body = encodeURIComponent(
    `${hello}\n\n` +
    `Voici votre proposition d'installation solaire Taqinor :\n${proposalUrl}\n\n` +
    `Je reste à votre disposition pour toute question.\n\n` +
    `Cordialement,\nL'équipe Taqinor`
  )
  return `mailto:${email}?subject=${subject}&body=${body}`
}

// Convertit un data URL PNG en Blob (upload multipart de la 3D).
function dataUrlToBlob(dataUrl) {
  const m = /^data:([^;]+);base64,(.*)$/.exec(dataUrl)
  if (!m) return null
  const mime = m[1]
  const bin = atob(m[2])
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Blob([bytes], { type: mime })
}

// Le proposal_path renvoyé par le backend est /proposition/<token> ; le lien
// client vit sur le site public taqinor.ma (configurable via VITE_PUBLIC_SITE_URL).
const PUBLIC_SITE_URL = import.meta.env.VITE_PUBLIC_SITE_URL || 'https://taqinor.ma'

// Le builder s'hydrate depuis un payload `LeadPayload` (roof_point/roof_outline/
// bill_kwh + fullName/phone/city). Le lead ERP utilise des champs français : on
// le projette dans la forme attendue (les coords roof_* sont déjà au bon format).
function leadToBuilderPayload(lead) {
  if (!lead) return null
  const fullName = `${lead.nom ?? ''} ${lead.prenom ?? ''}`.trim()
  const phone = (lead.whatsapp || lead.telephone || '').trim()
  const city = (lead.ville || '').trim()
  const billKwh = lead.bill_kwh != null ? Number(lead.bill_kwh) : null
  return {
    roof_point: lead.roof_point ?? null,
    roof_outline: lead.roof_outline ?? null,
    bill_kwh: Number.isFinite(billKwh) ? billKwh : null,
    fullName: fullName || undefined,
    phone: phone || undefined,
    city: city || undefined,
  }
}

// PV20 — MODE DEVIS. Le builder s'hydrate depuis un `DevisPayload` (PV19 :
// `geometrie.roof_layout | roof_point | roof_outline` + `cible.panneaux |
// panel_watt | scenario`). Le contexte serveur (contrat
// `contract_samples/devis_design_context.json`) nomme le repère `pin` et le
// contour `outline` : cette projection est le SEUL endroit qui les renomme —
// l'écran ne devine ni ne complète aucune clé absente.
function contexteToDevisPayload(contexte) {
  if (!contexte) return null
  const geo = contexte.geometrie ?? {}
  const cible = contexte.cible ?? {}
  const nom = (contexte.devis?.client_nom ?? '').trim()
  return {
    id: contexte.devis?.id ?? null,
    geometrie: {
      roof_layout: geo.roof_layout ?? null,
      roof_point: geo.pin ?? null,
      roof_outline: geo.outline ?? null,
    },
    cible: {
      panneaux: cible.panneaux ?? null,
      panel_watt: cible.panel_watt ?? null,
      scenario: cible.scenario || null,
    },
    fullName: nom || undefined,
  }
}

function httpMessage(status, responseData) {
  // QJ17 — the backend returns a structured French error for 422 (composition
  // pre-flight failures). Surface it directly instead of a generic message.
  if (status === 422) {
    const detail = responseData?.detail
    if (detail) return detail
    const errors = responseData?.errors
    if (Array.isArray(errors) && errors.length > 0) return errors[0]
    return 'Composition invalide — vérifiez le catalogue produits puis réessayez.'
  }
  if (status === 400)
    return "Le devis n'a pas pu être créé : données du tracé invalides. Vérifiez le toit puis réessayez."
  if (status === 403) return "Accès refusé pour ce lead. Contactez un administrateur."
  if (status === 404) return "Lead introuvable côté ERP. Vérifiez le lien puis réessayez."
  if (status >= 500) return `Le serveur a renvoyé une erreur (${status}). Réessayez dans un instant.`
  return `Création du devis impossible (erreur ${status}).`
}

export default function ToitureDesign({ mode = 'lead' }) {
  const { id: idParam } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  // PV20 — deux modes sur le MÊME écran. `lead` (défaut) est le flux d'origine,
  // strictement inchangé ; `devis` démarre SUR un devis existant.
  const estDevis = mode === 'devis'
  // Accepte /devis-design/:id ET ?lead=<id> (parité avec l'ancien lien public).
  const leadId = estDevis ? '' : (idParam || searchParams.get('lead') || '')
  const devisId = estDevis ? (idParam || '') : ''
  const cibleId = estDevis ? devisId : leadId

  const reducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  // État initial dérivé de la présence du leadId (évite un setState synchrone
  // dans l'effet) : sans identifiant, on affiche directement le message d'erreur.
  const [status, setStatus] = useState(() => {
    if (cibleId) return estDevis ? 'Chargement du devis…' : 'Chargement du lead…'
    return estDevis
      ? 'Aucun devis indiqué (identifiant manquant).'
      : 'Aucun lead indiqué (identifiant manquant).'
  })
  const [lead, setLead] = useState(null)
  // PV20 — contexte agrégé du devis (mode devis uniquement) : identité, cible,
  // `modifiable` + `raison_lecture_seule`. Toujours null en mode lead.
  const [contexte, setContexte] = useState(null)
  const [loadError, setLoadError] = useState(() => {
    if (cibleId) return null
    return estDevis ? 'Aucun devis indiqué.' : 'Aucun lead indiqué.'
  })

  // API exposée par le builder (serializeLayout / snapshot), posée à onApiReady.
  const builderApi = useRef(null)

  // — État de la génération du devis —
  const [sending, setSending] = useState(false)
  const [genError, setGenError] = useState(null)
  const [genStatus, setGenStatus] = useState(null)
  const [deliver, setDeliver] = useState(null) // {reference, proposalUrl, waUrl, mailUrl}
  const [copied, setCopied] = useState(false)
  // PV21 — conflit 409 renvoyé par sync-layout : {detail, revision_possible}.
  // Le texte est TOUJOURS celui du serveur ; l'écran choisit seulement entre
  // l'encart « Réviser (v2) » et le bandeau de document clos.
  const [conflit, setConflit] = useState(null)

  // ── Boot : charge lead + config carte, puis initialise le builder ──────────
  useEffect(() => {
    let cancelled = false
    // Sans identifiant, l'état initial affiche déjà l'erreur — rien à booter.
    if (!cibleId) return undefined

    // Le builder a une garde module-niveau `booted` (one-shot par chargement de
    // page). En SPA, revenir sur la route ne le ré-initialiserait pas : si on a
    // déjà booté un builder dans CETTE session de page, on recharge dur une fois
    // pour repartir d'un module frais (sinon : carte vide).
    if (window.__taqinorRoofBooted) {
      window.location.reload()
      return undefined
    }

    async function boot() {
      let leadData = null
      try {
        const res = await api.get(`/crm/leads/${encodeURIComponent(leadId)}/`)
        leadData = res.data
      } catch (err) {
        if (cancelled) return
        const code = err?.response?.status
        setLoadError(
          code === 404
            ? 'Lead introuvable.'
            : 'Impossible de charger le lead — réessayez.'
        )
        setStatus(`Lead introuvable (erreur ${code ?? '?'}).`)
        return
      }
      if (cancelled) return
      setLead(leadData)

      // Clé carte (même origine, session cookie) — sans elle, pas de carte.
      let maptilerKey = ''
      let mapboxToken
      try {
        const cfg = await api.get('/ventes/roof-config/')
        if (cfg.data?.available && cfg.data?.maptilerKey) {
          maptilerKey = cfg.data.maptilerKey
          mapboxToken = cfg.data.mapboxToken || undefined
        }
      } catch {
        /* repli : message ci-dessous */
      }
      if (cancelled) return
      if (!maptilerKey) {
        setStatus('Carte indisponible (clé MapTiler manquante côté serveur).')
        setLoadError('Carte indisponible : la clé MapTiler n’est pas configurée sur le serveur ERP.')
        return
      }

      // Le DOM `rp9-*` est déjà rendu (JSX ci-dessous) : on boote le builder.
      const mod = await import('@roofbuilder')
      if (cancelled) return
      window.__taqinorRoofBooted = true
      mod.initRoofToolPro8({
        maptilerKey,
        mapboxToken,
        reducedMotion: !!reducedMotion,
        hydrate: { lead: leadToBuilderPayload(leadData) },
        onApiReady: (a) => { builderApi.current = a },
      })
      // Pré-remplit l'adresse depuis la ville du lead (champ de recherche).
      const addrEl = document.getElementById('rp9-address')
      if (addrEl && leadData.ville) addrEl.value = String(leadData.ville)
      setStatus('Repère du client chargé. Dessinez / ajustez, puis « Générer le devis & envoyer au client ».')
    }

    // ── PV20 — boot MODE DEVIS : UN SEUL appel (design-context) ─────────────
    // Identité + géométrie + cible + carte + `modifiable` arrivent ensemble :
    // l'écran ne fait aucune requête de complément et ne devine aucun motif de
    // lecture seule (il vient toujours du serveur).
    async function bootDevis() {
      let ctx = null
      try {
        const res = await ventesApi.getDevisDesignContext(devisId)
        ctx = res.data
      } catch (err) {
        if (cancelled) return
        const code = err?.response?.status
        setLoadError(
          code === 404
            ? 'Devis introuvable.'
            : 'Impossible de charger le devis — réessayez.'
        )
        setStatus(`Devis introuvable (erreur ${code ?? '?'}).`)
        return
      }
      if (cancelled) return
      setContexte(ctx)

      const carte = ctx?.carte ?? {}
      if (!carte.available || !carte.maptilerKey) {
        setStatus('Carte indisponible (clé MapTiler manquante côté serveur).')
        setLoadError('Carte indisponible : la clé MapTiler n’est pas configurée sur le serveur ERP.')
        return
      }

      const mod = await import('@roofbuilder')
      if (cancelled) return
      window.__taqinorRoofBooted = true
      // Un devis en lecture seule BOOTE quand même : on peut regarder le
      // calepinage vendu — seule l'action d'enregistrement disparaît.
      mod.initRoofToolPro8({
        maptilerKey: carte.maptilerKey,
        mapboxToken: carte.mapboxToken || undefined,
        reducedMotion: !!reducedMotion,
        hydrate: { devis: contexteToDevisPayload(ctx) },
        onApiReady: (a) => { builderApi.current = a },
      })
      const reference = ctx?.devis?.reference ?? ''
      setStatus(
        ctx?.modifiable
          ? `Devis ${reference} chargé. Ajustez le calepinage, puis « Enregistrer la conception ».`
          : `Devis ${reference} en lecture seule — consultation du calepinage vendu.`
      )
    }

    if (estDevis) bootDevis()
    else boot()
    return () => { cancelled = true }
  }, [cibleId, devisId, leadId, estDevis, reducedMotion])

  // ── UN SEUL BOUTON : devis + snapshot + livraison ──────────────────────────
  const generer = async () => {
    if (sending) return
    setGenError(null)
    const apiTool = builderApi.current
    if (!apiTool) {
      setGenError('Outil non prêt — tracez le toit puis réessayez.')
      return
    }
    setSending(true)
    setGenStatus('Génération du devis…')
    try {
      const layout = apiTool.serializeLayout()
      // 1) Crée le devis depuis le layout (cookie = auth, pas de Bearer).
      //    QJ17 — le backend renvoie 200 si un brouillon identique existe déjà
      //    (idempotency par lead + hash du layout), 201 pour un nouveau devis, et
      //    422 avec un message FR clair si la composition est invalide (catalogue
      //    manquant ou sans prix). Dans tous les cas le corps a la même forme.
      let devis
      try {
        const createRes = await api.post('/ventes/devis/from-layout/', {
          layout,
          lead: leadId,
        })
        devis = createRes.data
        // QJ17 — if the backend deduplicated, show a soft notice to the agent.
        if (createRes.status === 200 && devis.deduplicated) {
          setGenStatus('Devis existant retrouvé — aucun doublon créé.')
        }
      } catch (err) {
        const code = err?.response?.status
        const responseData = err?.response?.data
        setGenStatus(null)
        setGenError(httpMessage(code ?? 0, responseData))
        setSending(false)
        return
      }

      // 2) Persistance idempotente du layout finalisé (best-effort).
      try {
        await api.post(`/ventes/devis/${devis.id}/layout/`, layout)
      } catch { /* on continue : la persistance est best-effort */ }

      // 3) Capture le PNG de la 3D et l'envoie (multipart, best-effort).
      setGenStatus('Capture de la vue 3D…')
      const png = apiTool.snapshot()
      if (png) {
        const blob = dataUrlToBlob(png)
        if (blob) {
          const form = new FormData()
          form.append('image', blob, `devis-${devis.id}.png`)
          try {
            await api.post(`/ventes/devis/${devis.id}/roof-image/`, form)
          } catch { /* image best-effort */ }
        }
      }

      // 4) Bascule sur « Prêt à envoyer » : lien tokenisé + WhatsApp / e-mail.
      const proposalUrl = designProposalUrl(PUBLIC_SITE_URL, devis.proposal_path)
      const name = `${lead?.nom ?? ''} ${lead?.prenom ?? ''}`.trim()
      const phone = (lead?.whatsapp || lead?.telephone || '').trim()
      const email = (lead?.email || '').trim()
      setDeliver({
        reference: devis.reference,
        proposalUrl,
        waUrl: phone ? whatsappLink(phone, designWhatsappText(name, proposalUrl)) : null,
        mailUrl: email ? designMailto(email, name, proposalUrl) : null,
      })
      setGenStatus(null)
      setSending(false)
      setStatus(`Devis ${devis.reference} créé — prêt à envoyer au client.`)
    } catch {
      setGenStatus(null)
      setGenError('Erreur réseau pendant la génération. Vérifiez votre connexion puis réessayez.')
      setSending(false)
    }
  }

  // ── PV21 — BOUCLE DE FINALISATION MODE DEVIS ───────────────────────────────
  // Le devis EXISTE : on ne le recrée pas, on resynchronise ses lignes sur le
  // calepinage. Le statut n'est jamais écrit ici (règle #4) — le serveur refuse
  // (409) dès que le document est parti chez le client ou clos.
  const enregistrerConception = async () => {
    if (sending) return
    setGenError(null)
    setConflit(null)
    const apiTool = builderApi.current
    if (!apiTool) {
      setGenError('Outil non prêt — ajustez le calepinage puis réessayez.')
      return
    }
    setSending(true)
    setGenStatus('Enregistrement de la conception…')
    try {
      const layout = apiTool.serializeLayout()

      // 1) Resynchronisation chirurgicale des lignes sur le calepinage.
      let resultat
      try {
        const res = await ventesApi.syncDevisLayout(devisId, { layout })
        resultat = res.data
      } catch (err) {
        const code = err?.response?.status
        const data = err?.response?.data
        setGenStatus(null)
        setSending(false)
        if (code === 409) {
          setConflit({
            detail: data?.detail || 'Ce devis ne peut plus être resynchronisé.',
            revision_possible: !!data?.revision_possible,
          })
          return
        }
        setGenError(httpMessage(code ?? 0, data))
        return
      }

      // 2) Même géométrie → ZÉRO écriture serveur : on le DIT, sans rien
      //    prétendre avoir enregistré.
      if (resultat?.inchange) {
        toastInfo('Aucun changement')
        setGenStatus(null)
        setSending(false)
        setStatus('Calepinage inchangé — le devis n’a pas bougé.')
        return
      }

      // 3) Capture le PNG de la 3D et l'envoie (multipart, best-effort) —
      //    même patron que le flux lead.
      setGenStatus('Capture de la vue 3D…')
      const png = apiTool.snapshot()
      if (png) {
        const blob = dataUrlToBlob(png)
        if (blob) {
          const form = new FormData()
          form.append('image', blob, `devis-${devisId}.png`)
          try {
            await api.post(`/ventes/devis/${devisId}/roof-image/`, form)
          } catch { /* image best-effort */ }
        }
      }

      // 4) Lien client : le lien tokenisé est (re)frappé sans aucune transition
      //    de statut, et l'aperçu WhatsApp est LECTURE SEULE (QX22 : ouvrir
      //    l'aperçu ne marque jamais un devis « envoyé »).
      setGenStatus('Préparation du lien client…')
      let proposalUrl = ''
      try {
        const lien = await ventesApi.shareLinkDevis(devisId)
        proposalUrl = designProposalUrl(PUBLIC_SITE_URL, lien.data?.path)
      } catch { /* le lien reste optionnel */ }
      let waUrl = null
      try {
        const apercu = await ventesApi.whatsappPreviewDevis(devisId)
        waUrl = apercu.data?.wa_url || null
      } catch { /* pas de numéro chez ce client → pas de bouton WhatsApp */ }

      setDeliver({
        reference: contexte?.devis?.reference ?? '',
        proposalUrl,
        waUrl,
        mailUrl: null,
      })
      setGenStatus(null)
      setSending(false)
      setStatus(
        `Conception enregistrée — ${resultat.panneaux} panneaux (${resultat.kwc} kWc), `
        + `${resultat.lignes_modifiees} ligne(s) de devis mise(s) à jour.`
      )
    } catch {
      setGenStatus(null)
      setGenError('Erreur réseau pendant l’enregistrement. Vérifiez votre connexion puis réessayez.')
      setSending(false)
    }
  }

  // PV21 — « Réviser (v2) » : le devis est déjà chez le client, on en crée une
  // NOUVELLE version (brouillon) et on rouvre la conception dessus.
  const reviser = async () => {
    if (sending) return
    setSending(true)
    setGenError(null)
    setGenStatus('Création de la révision…')
    try {
      const res = await ventesApi.reviserDevis(devisId)
      const nouveau = res?.data?.id
      setGenStatus(null)
      setSending(false)
      if (!nouveau) {
        setGenError('Révision créée sans identifiant — rouvrez le devis depuis la liste.')
        return
      }
      setConflit(null)
      navigate(`/ventes/devis/${nouveau}/design`)
    } catch (err) {
      setGenStatus(null)
      setSending(false)
      setGenError(httpMessage(err?.response?.status ?? 0, err?.response?.data))
    }
  }

  const copyLink = () => {
    if (!deliver?.proposalUrl) return
    try {
      navigator.clipboard?.writeText(deliver.proposalUrl)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch { /* presse-papier indispo */ }
  }

  const leadLabel = lead ? `${lead.nom ?? ''} ${lead.prenom ?? ''}`.trim() : ''
  // PV20 — en mode devis, le titre porte la référence + le client servis par le
  // contexte ; en lecture seule, le motif AFFICHÉ est celui du serveur.
  const devisLabel = (contexte?.devis?.client_nom ?? '').trim()
  const devisReference = contexte?.devis?.reference ?? ''
  const lectureSeule = estDevis && contexte != null && !contexte.modifiable
  const raisonLectureSeule = (contexte?.raison_lecture_seule ?? '').trim()
  const avertissements = Array.isArray(contexte?.avertissements)
    ? contexte.avertissements : []

  const inputClass =
    'w-full border border-white/15 bg-white/5 px-3 py-3 text-base text-white outline-none focus:border-brass-400'
  const chipClass = 'rp9-chip'

  // PV21 — le bloc « Prêt à envoyer » est PARTAGÉ par les deux modes : un devis
  // conçu depuis sa propre fiche se livre exactement comme un devis né d'un
  // lead (mêmes liens, même bouton copier). Une seule différence : la phrase
  // qui dit ce qui vient de se passer.
  const blocLivraison = () => (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="tech-label rule-brass text-brass-300">Prêt à envoyer</p>
        <p className="text-sm text-lune-soft">Devis <span className="font-semibold text-white">{deliver.reference}</span></p>
      </div>
      <p className="text-sm text-lune-soft">
        {estDevis
          ? 'La conception est enregistrée et la vue 3D mise à jour. Envoyez le lien au client par WhatsApp, e-mail, ou copiez-le.'
          : 'Le devis est créé et la vue 3D enregistrée. Envoyez le lien au client par WhatsApp, e-mail, ou copiez-le.'}
      </p>
      {deliver.proposalUrl && (
        <label className="block text-sm text-lune-soft">
          Lien de la proposition
          <input type="text" readOnly value={deliver.proposalUrl} className={`${inputClass} mt-1`} />
        </label>
      )}
      <div className="flex flex-wrap items-center gap-3">
        {deliver.waUrl && (
          <a href={deliver.waUrl} target="_blank" rel="noopener"
            className="inline-flex items-center gap-2 px-5 py-3 text-base font-bold text-white"
            style={{ background: 'var(--rp-ok-600)' }}>WhatsApp</a>
        )}
        {deliver.mailUrl && (
          <a href={deliver.mailUrl}
            className="inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300">E-mail</a>
        )}
        <button type="button" onClick={copyLink}
          className="inline-flex items-center gap-2 border border-white/25 px-5 py-3 text-base font-semibold text-lune-soft">Copier le lien</button>
        {copied && <span className="text-sm font-semibold text-ok-400" aria-live="polite">Lien copié</span>}
      </div>
      {deliver.proposalUrl && (
        <a href={deliver.proposalUrl} target="_blank" rel="noopener"
          className="inline-block text-sm text-lune-faint underline">
          Ouvrir la proposition dans un nouvel onglet
        </a>
      )}
    </div>
  )

  return (
    <div className="rp9-host">
      <p className="tech-label rule-brass text-brass-300">Interne · conception toiture</p>

      <div className="mt-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
          {estDevis ? (
            <h1 className="display text-xl text-white sm:text-2xl">
              Devis <span className="text-brass-300">{devisReference || devisId || '—'}</span> ·{' '}
              <span className="text-lune-soft">{devisLabel || '—'}</span>
            </h1>
          ) : (
            <h1 className="display text-xl text-white sm:text-2xl">
              Lead <span className="text-brass-300">{leadId || '—'}</span> ·{' '}
              <span className="text-lune-soft">{leadLabel || '—'}</span>
            </h1>
          )}
        </div>
        <p className="mt-2 text-sm text-lune-faint" aria-live="polite">{status}</p>

        {loadError && (
          <p className="mt-3 text-sm text-alert-300" role="alert">{loadError}</p>
        )}

        {/* PV20 — LECTURE SEULE : le motif vient du serveur, jamais rédigé ici. */}
        {lectureSeule && (
          <div className="cine-card mt-6 border border-brass-400/40 p-5" data-testid="pv20-lecture-seule">
            <p className="tech-label rule-brass text-brass-300">Lecture seule</p>
            <p className="mt-3 text-sm text-lune-soft" role="status">
              {raisonLectureSeule || 'Ce devis ne peut plus être modifié.'}
            </p>
            <Link
              to={`/ventes/devis/${devisId}/3d`}
              className="mt-4 inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300"
            >
              Voir en 3D
            </Link>
          </div>
        )}

        {/* PV20 — avertissements serveur (multi-villa, aucune ligne panneau…). */}
        {estDevis && avertissements.length > 0 && (
          <ul className="mt-4 space-y-1 text-xs text-lune-faint" data-testid="pv20-avertissements">
            {avertissements.map((a) => <li key={a}>{a}</li>)}
          </ul>
        )}

        {/* ÉTAPE FACTURE (alimente l'optimiseur). */}
        <div className="cine-card mt-6 p-5">
          <label htmlFor="rp9-bill" className="block text-sm text-lune-soft">
            Facture d'électricité moyenne par mois (MAD)
          </label>
          <div className="mt-2 flex items-center gap-3">
            <input id="rp9-bill" name="bill" type="text" inputMode="decimal" step="any"
              placeholder="ex. 1 500" className={`${inputClass} max-w-[12rem]`} />
            <span className="text-xs text-lune-faint">≈ <span id="rp9-bill-kwh" className="fig">—</span> par an</span>
          </div>
        </div>

        {/* BUILDER — DOM complet (mêmes ids que la preview pro-11). */}
        <div className="cine-card mt-6 overflow-hidden">
          <form id="rp9-search" className="flex flex-col gap-3 border-b border-white/10 p-4 sm:flex-row">
            <label htmlFor="rp9-address" className="sr-only">Adresse</label>
            <div className="relative flex-1">
              <input id="rp9-address" name="address" type="text" autoComplete="off"
                role="combobox" aria-autocomplete="list" aria-expanded="false"
                aria-controls="rp9-suggestions" aria-haspopup="listbox"
                placeholder="Adresse du client" className={inputClass} />
              <ul id="rp9-suggestions" role="listbox" aria-label="Suggestions d'adresses" hidden
                className="absolute left-0 right-0 top-full z-20 mt-1 max-h-72 overflow-auto border border-white/15 bg-nuit-900"></ul>
            </div>
            <button type="submit" className="flex-none bg-brass-400 px-6 py-3 text-base font-bold text-azur-950">Localiser</button>
          </form>

          <div id="rp9-map" className="h-[56vh] min-h-[360px] w-full bg-nuit-700"
            role="application" aria-label="Carte 3D pour dessiner le toit">
            <div id="rp9-compass" className="rp9-compass" aria-hidden="true">
              <div id="rp9-compass-arrow" className="rp9-compass-arrow"><span>N</span><span>S</span></div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-white/10 p-4">
            <button type="button" id="rp9-finish" disabled className={chipClass}>Terminer le tracé</button>
            <button type="button" id="rp9-undo-point" hidden className={chipClass}>Annuler le dernier point</button>
            <button type="button" id="rp9-clear" className={chipClass}>Effacer</button>
            <button type="button" id="rp9-add-area" disabled className={chipClass}>+ Ajouter une zone</button>
            <p className="ml-auto text-sm text-lune-faint"><span>Surface&nbsp;: </span><span id="rp9-area-value" className="text-white">—</span></p>
          </div>

          {/* Contrôles de config (mode normal) */}
          <div id="rp9-config" hidden className="space-y-4 border-t border-white/10 bg-nuit-800 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="tech-label mr-1 text-lune-faint">Type de toit</span>
              <button type="button" data-rooftype="flat" className={chipClass} aria-pressed="true">Toit plat</button>
              <button type="button" data-rooftype="pitched" className={chipClass} aria-pressed="false">Toit en pente / tuiles</button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" id="rp9-optimum" className={`${chipClass} text-brass-300`}>↺ Réinitialiser</button>
              <span id="rp9-optimum-note" className="min-w-0 flex-1 text-xs text-lune-faint"></span>
            </div>
            <div id="rp9-flat-controls" className="space-y-4">
              <div id="rp9-flat-only" className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="tech-label mr-1 text-lune-faint">Orientation</span>
                  <button type="button" data-family="south" className={chipClass} aria-pressed="true">Plein sud<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-family="eastwest" className={chipClass} aria-pressed="false">Est-Ouest<span className="rp9-reco-badge" hidden> ✓</span></button>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="tech-label mr-1 text-lune-faint">Inclinaison</span>
                  <button type="button" data-tilt="reco" className={chipClass} aria-pressed="true">Recommandé<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-tilt="29" className={chipClass} aria-pressed="false">29°<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-tilt="15" className={chipClass} aria-pressed="false">15°<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-tilt="10" className={chipClass} aria-pressed="false">10°<span className="rp9-reco-badge" hidden> ✓</span></button>
                </div>
                <div className="flex items-center gap-3">
                  <label htmlFor="rp9-tilt-range" className="tech-label shrink-0 text-lune-faint">Inclinaison fine</label>
                  <input id="rp9-tilt-range" type="range" min="5" max="35" step="1" defaultValue="29" className="rp9-range min-w-0 flex-1" />
                  <span id="rp9-tilt-value" className="w-16 shrink-0 text-right text-sm font-semibold text-brass-300">29°</span>
                </div>
                <div id="rp9-azimuth-group" hidden className="flex flex-wrap items-center gap-2">
                  <span className="tech-label mr-1 text-lune-faint">Azimut</span>
                  <button type="button" data-azimuth="south" className={chipClass} aria-pressed="true">Plein sud<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-azimuth="aligned" className={chipClass} aria-pressed="false">Aligné toit<span className="rp9-reco-badge" hidden> ✓</span></button>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="tech-label mr-1 text-lune-faint">Panneaux</span>
                <button type="button" data-orient="auto" className={chipClass} aria-pressed="true">Auto</button>
                <button type="button" data-orient="portrait" className={chipClass} aria-pressed="false">Portrait<span className="rp9-reco-badge" hidden> ✓</span></button>
                <button type="button" data-orient="landscape" className={chipClass} aria-pressed="false">Paysage<span className="rp9-reco-badge" hidden> ✓</span></button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="tech-label mr-1 text-lune-faint">Marge de rive</span>
                <button type="button" data-margin="keep" className={chipClass} aria-pressed="true">Garder<span className="rp9-reco-badge" hidden> ✓</span></button>
                <button type="button" data-margin="remove" className={chipClass} aria-pressed="false">Pleine rive<span className="rp9-reco-badge" hidden> ✓</span></button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <label htmlFor="rp9-overhang-input" className="tech-label mr-1 text-lune-faint">Débord (m)</label>
                <input id="rp9-overhang-input" type="number" inputMode="decimal" step="any" min="0" defaultValue="0"
                  className="fig h-9 w-20 border border-white/20 bg-nuit-900 px-2 text-center text-base text-white outline-none focus:border-brass-400" />
              </div>
            </div>
            <div id="rp9-pitched-controls" hidden className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="tech-label mr-1 text-lune-faint">Pente</span>
                <button type="button" data-pitch="15" className={chipClass} aria-pressed="false">~15°</button>
                <button type="button" data-pitch="22" className={chipClass} aria-pressed="true">~22°</button>
                <button type="button" data-pitch="30" className={chipClass} aria-pressed="false">~30°</button>
                <button type="button" data-pitch="45" className={chipClass} aria-pressed="false">~45°</button>
              </div>
              <div className="flex items-center gap-3">
                <label htmlFor="rp9-pitch-range" className="tech-label shrink-0 text-lune-faint">Pente fine</label>
                <input id="rp9-pitch-range" type="range" min="5" max="45" step="1" defaultValue="22" className="rp9-range min-w-0 flex-1" />
                <span id="rp9-pitch-value" className="w-12 shrink-0 text-right text-sm font-semibold text-brass-300">22°</span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="tech-label mr-1 text-lune-faint">Face du pan</span>
                <button type="button" data-facing="180" className={chipClass} aria-pressed="true">Sud</button>
                <button type="button" data-facing="135" className={chipClass} aria-pressed="false">Sud-Est</button>
                <button type="button" data-facing="225" className={chipClass} aria-pressed="false">Sud-Ouest</button>
                <button type="button" data-facing="90" className={chipClass} aria-pressed="false">Est</button>
                <button type="button" data-facing="270" className={chipClass} aria-pressed="false">Ouest</button>
              </div>
              <p id="rp9-facing-note" className="min-h-[1rem] text-xs text-lune-faint" aria-live="polite"></p>
              <div className="flex items-center gap-3">
                <label htmlFor="rp9-facing-range" className="tech-label shrink-0 text-lune-faint">Sens de la pente</label>
                <input id="rp9-facing-range" type="range" min="0" max="359" step="any" defaultValue="180" className="rp9-range min-w-0 flex-1" />
                <span id="rp9-facing-value" className="w-28 shrink-0 text-right text-sm font-semibold text-brass-300">Sud · 180°</span>
              </div>
              <p id="rp9-pitched-note" className="min-h-[1.25rem] text-xs text-lune-soft" aria-live="polite"></p>
            </div>
          </div>
          <p id="rp9-status" className="border-t border-white/10 px-4 py-3 text-sm text-lune-faint" aria-live="polite">Chargement…</p>
        </div>

        {/* RECOMMANDATION (panneaux/optimiseur visibles ici) */}
        <div id="rp9-results" className="rp9-results cine-card mt-6 p-6">
          <p className="tech-label rule-brass text-brass-300">Recommandation</p>
          <p id="rp9-reco-title" className="fig mt-4 text-2xl text-brass-300">—</p>
          <div className="mt-5 border border-white/10 bg-nuit-800/60 p-4">
            <label htmlFor="rp9-need-input" className="tech-label text-lune-faint">Panneaux nécessaires</label>
            <div className="mt-2 flex items-center gap-3">
              <button type="button" id="rp9-need-minus" aria-label="Un de moins" className="h-11 w-11 border border-white/25 text-2xl text-white">−</button>
              <input id="rp9-need-input" type="text" inputMode="numeric" defaultValue="—" disabled
                className="fig h-11 w-20 border border-white/20 bg-nuit-900 text-center text-2xl text-white" />
              <button type="button" id="rp9-need-plus" aria-label="Un de plus" className="h-11 w-11 border border-white/25 text-2xl text-white">+</button>
            </div>
            <p id="rp9-need-note" className="mt-2 min-h-[1.5rem] text-xs text-lune-faint" aria-live="polite"></p>
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-6" aria-live="polite">
            <div><dd id="rp9-reco-kwc" className="fig text-2xl text-white">—</dd><dt className="tech-label mt-1 text-lune-faint">Puissance</dt></div>
            <div><dd id="rp9-reco-panels" className="fig text-2xl text-white">—</dd><dt className="tech-label mt-1 text-lune-faint">Panneaux</dt></div>
            <div><dd id="rp9-reco-prod" className="fig text-xl text-white">—</dd><dt className="tech-label mt-1 text-lune-faint">Production</dt></div>
            <div><dd id="rp9-reco-cover" className="fig text-xl text-white">—</dd><dt className="tech-label mt-1 text-lune-faint">Couverture</dt></div>
          </dl>
          <div className="mt-5 border-t border-white/10 pt-5">
            <dd id="rp9-reco-savings" className="fig text-xl text-brass-300">—</dd>
            <dt className="tech-label mt-1 text-lune-faint">Économies estimées</dt>
          </div>
          <p id="rp9-reco-why" className="mt-5 min-h-[3.5rem] text-xs text-lune-soft"></p>
          <p id="rp9-reco-bifacial" className="mt-2 text-xs text-lune-faint"></p>
          <p id="rp9-reco-band" className="mt-2 min-h-[2.5rem] text-xs text-lune-faint" aria-live="polite"></p>
          <p id="rp9-maxline" className="mt-3 text-xs text-lune-faint"></p>
        </div>

        {/* UN SEUL BOUTON — génère le devis, capture la 3D, mint le lien.
            PV20 — mode lead UNIQUEMENT : un devis existant n'est jamais recréé
            depuis cet écran (sa boucle d'enregistrement arrive en PV21). */}
        {!estDevis && (
        <div className="cine-card mt-6 p-6">
          {!deliver ? (
            <div>
              <button type="button" onClick={generer} disabled={sending}
                className="inline-flex w-full items-center justify-center gap-3 bg-ok-600 px-6 py-4 text-base font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
                style={{ background: 'var(--rp-ok-600)' }}>
                {sending && (
                  <span aria-hidden="true"
                    className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
                )}
                <span>{sending ? 'Génération en cours…' : 'Générer le devis & envoyer au client'}</span>
              </button>
              <p className="mt-3 text-xs text-lune-faint">
                Un seul clic : le devis est créé, la vue 3D enregistrée et le lien client préparé.
              </p>
              {genStatus && <p className="mt-3 text-sm text-lune-soft" aria-live="polite">{genStatus}</p>}
              {genError && <p className="mt-3 text-sm text-alert-300" aria-live="assertive">{genError}</p>}
            </div>
          ) : blocLivraison()}
        </div>
        )}

        {/* PV21 — MODE DEVIS : « Enregistrer la conception ». Le devis existe
            déjà — on resynchronise ses lignes, on ne le recrée jamais. Absent
            en lecture seule (l'action de sauvegarde disparaît, PV20). */}
        {estDevis && !lectureSeule && (
        <div className="cine-card mt-6 p-6">
          {!deliver ? (
            <div>
              <button type="button" onClick={enregistrerConception} disabled={sending}
                className="inline-flex w-full items-center justify-center gap-3 bg-ok-600 px-6 py-4 text-base font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
                style={{ background: 'var(--rp-ok-600)' }}>
                {sending && (
                  <span aria-hidden="true"
                    className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
                )}
                <span>{sending ? 'Enregistrement en cours…' : 'Enregistrer la conception'}</span>
              </button>
              <p className="mt-3 text-xs text-lune-faint">
                Seuls le nombre de panneaux et la batterie suivent le calepinage :
                prix négociés, remises et notes du devis restent intacts.
              </p>
              {genStatus && <p className="mt-3 text-sm text-lune-soft" aria-live="polite">{genStatus}</p>}
              {genError && <p className="mt-3 text-sm text-alert-300" aria-live="assertive">{genError}</p>}

              {/* 409 « déjà envoyé » : le bon geste est une NOUVELLE version. */}
              {conflit?.revision_possible && (
                <div className="mt-4 border border-brass-400/40 p-4" data-testid="pv21-reviser">
                  <p className="text-sm text-lune-soft" role="status">{conflit.detail}</p>
                  <button type="button" onClick={reviser} disabled={sending}
                    className="mt-3 inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300 disabled:cursor-not-allowed disabled:opacity-60">
                    Réviser (v2)
                  </button>
                </div>
              )}

              {/* 409 document clos : plus aucune révision possible. */}
              {conflit && !conflit.revision_possible && (
                <div className="mt-4 border border-alert-300/40 p-4" data-testid="pv21-conflit-lecture-seule">
                  <p className="tech-label text-alert-300">Lecture seule</p>
                  <p className="mt-2 text-sm text-alert-300" role="alert">{conflit.detail}</p>
                  <Link
                    to={`/ventes/devis/${devisId}/3d`}
                    className="mt-3 inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300"
                  >
                    Voir en 3D
                  </Link>
                </div>
              )}
            </div>
          ) : blocLivraison()}
        </div>
        )}
      </div>
    </div>
  )
}
