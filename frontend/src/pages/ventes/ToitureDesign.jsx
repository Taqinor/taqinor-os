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
 *        d. bascule sur un bloc de CONFIRMATION. L-SECT (24/08/2026) : l'envoi
 *           au client (lien, WhatsApp, e-mail, copie) a quitté cet écran pour
 *           la fiche lead, onglet Devis, où le commercial choisit le niveau,
 *           l'OTP et les sections que le client reçoit.
 *   En cas d'échec, le tracé de Meriem n'est JAMAIS perdu et le bouton se
 *   réactive pour relancer (messages FR lisibles).
 *
 * L'ancienne page publique `apps/web/src/pages/internal/devis-design.astro`
 * (login form + token + cross-domain) est remplacée par celle-ci. La source du
 * builder n'est PAS modifiée : on l'importe seulement via l'alias `@roofbuilder`.
 */
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { X } from 'lucide-react'
import api from '../../api/axios'
import ventesApi from '../../api/ventesApi'
import aoApi from '../../api/aoApi'
import { toastInfo } from '../../lib/toast'
// L2 — confirmation maison (APX17 : jamais une popup système) avant une écriture qui
// diverge de la cible vendue du devis (voir enregistrerConception ci-dessous).
import { useConfirmDialog } from '../../ui/confirm'
import '../../styles/roofbuilder.css'

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

// Correction fondateur 24/08 — quand le client n'a JAMAIS posé d'épingle
// publique (`roof_point`, alimenté par l'outil site web), la fiche lead porte
// souvent déjà `gps_lat`/`gps_lng` (saisis côté « Toiture & site » du CRM,
// bornés ±90/±180 en base) : sans ce repli, la carte 3D démarrait TOUJOURS au
// niveau Maroc alors qu'une position réelle existait. Repli RÉEL, jamais une
// valeur inventée — `roof_point` posé prime toujours quand il existe.
function pinDepuisLead(lead) {
  if (lead?.roof_point) return lead.roof_point
  const lat = lead?.gps_lat
  const lng = lead?.gps_lng
  if (lat != null && lng != null && Number.isFinite(Number(lat)) && Number.isFinite(Number(lng))) {
    return { lat: Number(lat), lng: Number(lng) }
  }
  return null
}

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
    roof_point: pinDepuisLead(lead),
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
  // PV23bis (fondateur 20/08) — téléphone + ville du client, au même titre
  // que `fullName` ci-dessus et que `leadToBuilderPayload` en mode lead : le
  // builder les connaît DÉJÀ (roofPro11/prefill.ts `hydrateFromDevis` remplit
  // lf-phone/lf-city dès qu'ils sont présents) — seule cette projection ne
  // les lui transmettait pas encore, alors que le contexte serveur les porte
  // (`devis.client_telephone`/`client_ville`, client d'abord puis lead en repli).
  const phone = (contexte.devis?.client_telephone ?? '').trim()
  const city = (contexte.devis?.client_ville ?? '').trim()
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
    phone: phone || undefined,
    city: city || undefined,
  }
}

// MODE AO — MÊME écran, MÊME builder, pour une AFFAIRE d'appel d'offres. Le
// contexte serveur (contrat `apps/ao/contract_samples/ao_design_context.json`)
// est le MIROIR du contrat devis : `affaire` y remplace `devis`, la géométrie
// AO relevée est déjà reprojetée en degrés par le serveur (`pin` = ancre de la
// toiture, `outline` = contour en [lat, lng], convention CRM/builder).
//
// L'hydratation passe par le MÊME emplacement `hydrate.devis` : côté builder,
// c'est le créneau « géométrie déjà dessinée + cible imposée » (roofPro11/
// prefill.ts `hydrateFromDevis`), pas un créneau propre au document devis. La
// source du builder n'est JAMAIS éditée — on lui parle son langage. `id` reste
// null : une affaire n'est pas un devis, et rien ici ne prétend le contraire.
function contexteAoVersPayload(contexte) {
  if (!contexte) return null
  const geo = contexte.geometrie ?? {}
  const cible = contexte.cible ?? {}
  const objet = (contexte.affaire?.objet ?? '').trim()
  return {
    id: null,
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
    fullName: objet || undefined,
  }
}

// PV75 — projette `Devis.etude_params.simulation.pr` (étude bancable PV69/PV74 :
// P50/P90, ratio de performance, cascade des pertes) vers le payload `bankable`
// consommé par la fenêtre de production du builder. Le contexte agrégé
// (`devis_design_context.json`, PACT10) NE PORTE PAS `simulation` — on ne l'y
// ajoute pas depuis cette lane, on le lit sur le devis complet (endpoint déjà
// existant, `DevisSerializer` expose `etude_params` en entier). Aucune étude
// lancée/rangée → `pr` absent → null (fenêtre de production inchangée).
function bankableFromDevis(devis) {
  const pr = devis?.etude_params?.simulation?.pr
  if (!pr) return null
  return {
    p50_kwh: pr.p50_kwh,
    p90_kwh: pr.p90_kwh,
    performance_ratio: pr.performance_ratio,
    loss_breakdown: pr.loss_breakdown ?? {},
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
  // L2 — sync-layout renvoie désormais un 400 explicite quand la composition posée est
  // incompatible avec l'onduleur (même patron que le 422 ci-dessus) : le message SERVEUR
  // s'affiche TEL QUEL, jamais reformulé — sans `detail`, on garde le message générique
  // historique (création de devis, tracé invalide) pour ne rien changer aux autres 400.
  if (status === 400) {
    const detail = responseData?.detail
    if (detail) return detail
    const errors = responseData?.errors
    if (Array.isArray(errors) && errors.length > 0) return errors[0]
    return "Le devis n'a pas pu être créé : données du tracé invalides. Vérifiez le toit puis réessayez."
  }
  if (status === 403) return "Accès refusé pour ce lead. Contactez un administrateur."
  if (status === 404) return "Lead introuvable côté ERP. Vérifiez le lien puis réessayez."
  if (status >= 500) return `Le serveur a renvoyé une erreur (${status}). Réessayez dans un instant.`
  return `Création du devis impossible (erreur ${status}).`
}

export default function ToitureDesign({ mode = 'lead' }) {
  const { id: idParam } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  // L2 — confirmation maison (APX17) avant d'écrire un calepinage qui diverge de la
  // cible vendue du devis — voir enregistrerConception.
  const { confirm } = useConfirmDialog()
  // PV20 — deux modes sur le MÊME écran. `lead` (défaut) est le flux d'origine,
  // strictement inchangé ; `devis` démarre SUR un devis existant.
  // Mode `ao` — TROISIÈME mode, MÊME écran et MÊME builder, pour une AFFAIRE
  // d'appel d'offres : les mêmes outils pour les ventes et pour les appels
  // d'offres, jamais une seconde implémentation de la toiture 3D.
  const estDevis = mode === 'devis'
  const estAo = mode === 'ao'
  // Accepte /devis-design/:id ET ?lead=<id> (parité avec l'ancien lien public).
  const leadId = (estDevis || estAo)
    ? '' : (idParam || searchParams.get('lead') || '')
  const devisId = estDevis ? (idParam || '') : ''
  const affaireId = estAo ? (idParam || '') : ''
  const cibleId = estDevis ? devisId : (estAo ? affaireId : leadId)

  const reducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  // État initial dérivé de la présence du leadId (évite un setState synchrone
  // dans l'effet) : sans identifiant, on affiche directement le message d'erreur.
  const [status, setStatus] = useState(() => {
    if (cibleId) {
      if (estDevis) return 'Chargement du devis…'
      if (estAo) return 'Chargement de l’affaire…'
      return 'Chargement du lead…'
    }
    if (estDevis) return 'Aucun devis indiqué (identifiant manquant).'
    if (estAo) return 'Aucune affaire indiquée (identifiant manquant).'
    return 'Aucun lead indiqué (identifiant manquant).'
  })
  const [lead, setLead] = useState(null)
  // PV20 — contexte agrégé du devis (mode devis uniquement) : identité, cible,
  // `modifiable` + `raison_lecture_seule`. Toujours null en mode lead.
  const [contexte, setContexte] = useState(null)
  const [loadError, setLoadError] = useState(() => {
    if (cibleId) return null
    if (estDevis) return 'Aucun devis indiqué.'
    if (estAo) return 'Aucune affaire indiquée.'
    return 'Aucun lead indiqué.'
  })

  // API exposée par le builder (serializeLayout / snapshot), posée à onApiReady.
  const builderApi = useRef(null)

  // — État de la génération du devis —
  const [sending, setSending] = useState(false)
  const [genError, setGenError] = useState(null)
  const [genStatus, setGenStatus] = useState(null)
  // L-SECT — ne porte plus que { reference } : le lien, le menu WhatsApp, le
  // mailto et le bouton copier ont quitté cet écran pour la fiche lead.
  const [deliver, setDeliver] = useState(null) // { reference }
  // PV21 — conflit 409 renvoyé par sync-layout : {detail, revision_possible}.
  // Le texte est TOUJOURS celui du serveur ; l'écran choisit seulement entre
  // l'encart « Réviser (v2) » et le bandeau de document clos.
  const [conflit, setConflit] = useState(null)
  // PVHEAL — avertissements renvoyés par l'enregistrement (kit non complété,
  // composant absent du catalogue, deux onduleurs…). Le TEXTE est celui du
  // serveur, jamais rédigé ici : sans cet affichage, le devis repartait amputé
  // en silence.
  const [avertissementsSync, setAvertissementsSync] = useState([])

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

    // ── PV20 — boot MODE DEVIS : UN SEUL appel CRITIQUE (design-context) ────
    // Identité + géométrie + cible + carte + `modifiable` arrivent ensemble :
    // l'écran ne fait aucune requête de complément et ne devine aucun motif de
    // lecture seule (il vient toujours du serveur).
    async function bootDevis() {
      // PV75 — étude bancable (P50/P90/PR/pertes), lancée EN PARALLÈLE du
      // design-context : best-effort, ne bloque jamais le boot, n'invente rien
      // si l'étude n'a jamais été lancée (endpoint backend `POST .../simuler/`,
      // PV74 — pas encore câblé côté écran) ou n'est pas encore rangée. Le
      // contexte agrégé ne porte pas `simulation` (contrat
      // `devis_design_context.json`, PACT10) donc on la lit à part, sur le devis
      // complet déjà exposé par `getDevisById`.
      const bankablePromise = Promise.resolve()
        .then(() => ventesApi.getDevisById(devisId))
        .then((res) => bankableFromDevis(res.data))
        .catch(() => null)

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

      // L-SECT (fondateur 24/08/2026) — PV86 frappait ICI, AU BOOT, un
      // ShareLink sans aucune option (`shareLinkDevis(devisId)`) pour afficher
      // en permanence un panneau d'envoi en bas de page. Deux problèmes : le
      // lien partait toujours aux DÉFAUTS (jamais le niveau ni les sections
      // choisis), et ouvrir l'outil 3D mintait un lien public sans que
      // personne ne l'ait demandé. L'envoi vit désormais dans la fiche lead
      // (onglet Devis → « Envoyer au client ») : cet écran ne mint plus rien
      // au chargement.

      const carte = ctx?.carte ?? {}
      if (!carte.available || !carte.maptilerKey) {
        setStatus('Carte indisponible (clé MapTiler manquante côté serveur).')
        setLoadError('Carte indisponible : la clé MapTiler n’est pas configurée sur le serveur ERP.')
        return
      }

      const mod = await import('@roofbuilder')
      const bankable = await bankablePromise
      if (cancelled) return
      window.__taqinorRoofBooted = true
      // Un devis en lecture seule BOOTE quand même : on peut regarder le
      // calepinage vendu — seule l'action d'enregistrement disparaît.
      mod.initRoofToolPro8({
        maptilerKey: carte.maptilerKey,
        mapboxToken: carte.mapboxToken || undefined,
        reducedMotion: !!reducedMotion,
        hydrate: { devis: contexteToDevisPayload(ctx) },
        bankable,
        onApiReady: (a) => { builderApi.current = a },
      })
      // PV23bis — pré-remplit la barre de recherche d'adresse depuis
      // adresse+ville du devis, comme le mode lead le fait déjà ci-dessus
      // (`boot()`, `addrEl.value = leadData.ville`) : elle donne à la carte
      // un point de départ tant que le devis n'a pas ENCORE de repère posé ;
      // dès qu'un repère existe, l'hydratation ci-dessus centre déjà la carte
      // et cette barre ne sert plus qu'à chercher ailleurs.
      const addrEl = document.getElementById('rp9-address')
      const adresse = [ctx?.devis?.client_adresse, ctx?.devis?.client_ville]
        .map((v) => (v ?? '').trim())
        .filter(Boolean)
        .join(', ')
      if (addrEl && adresse) addrEl.value = adresse
      const reference = ctx?.devis?.reference ?? ''
      setStatus(
        ctx?.modifiable
          ? `Devis ${reference} chargé. Ajustez le calepinage, puis « Enregistrer la conception ».`
          : `Devis ${reference} en lecture seule — consultation du calepinage vendu.`
      )
    }

    // ── MODE AO — boot en UN SEUL appel (design-context de l'affaire) ──────
    // Même patron que `bootDevis` : identité + géométrie + cible + carte +
    // `modifiable` arrivent ensemble ; l'écran ne fait AUCUNE requête de
    // complément et ne devine AUCUN motif de lecture seule. Différences
    // assumées, parce qu'une affaire n'est pas un devis : ni lien client, ni
    // aperçu WhatsApp, ni étude bancable — rien de tout cela n'existe côté AO,
    // et l'inventer produirait des boutons morts.
    async function bootAo() {
      let ctx = null
      try {
        const res = await aoApi.affaires.designContext(affaireId)
        ctx = res.data
      } catch (err) {
        if (cancelled) return
        const code = err?.response?.status
        setLoadError(
          code === 404
            ? 'Affaire introuvable.'
            : 'Impossible de charger l’affaire — réessayez.'
        )
        setStatus(`Affaire introuvable (erreur ${code ?? '?'}).`)
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
      // Une affaire close BOOTE quand même (consultation du calepinage
      // remis) : seule l'action d'enregistrement disparaît.
      mod.initRoofToolPro8({
        maptilerKey: carte.maptilerKey,
        mapboxToken: carte.mapboxToken || undefined,
        reducedMotion: !!reducedMotion,
        hydrate: { devis: contexteAoVersPayload(ctx) },
        onApiReady: (a) => { builderApi.current = a },
      })
      const reference = ctx?.affaire?.reference ?? ''
      setStatus(
        ctx?.modifiable
          ? `Affaire ${reference} chargée. Ajustez le calepinage, puis « Enregistrer le calepinage ».`
          : `Affaire ${reference} en lecture seule — consultation du calepinage remis.`
      )
    }

    if (estDevis) bootDevis()
    else if (estAo) bootAo()
    else boot()
    return () => { cancelled = true }
  }, [cibleId, devisId, leadId, affaireId, estDevis, estAo, reducedMotion])

  // ── UN SEUL BOUTON : devis + snapshot + livraison ──────────────────────────
  const generer = async () => {
    if (sending) return
    setGenError(null)
    setAvertissementsSync([])
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
        // PVHEAL — si la création annonce des avertissements (composant absent
        // du catalogue…), ils s'affichent comme ceux de la resynchronisation.
        if (Array.isArray(devis?.avertissements)) {
          setAvertissementsSync(devis.avertissements)
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

      // 4) L-SECT — bascule sur le bloc de confirmation. L'envoi lui-même a
      //    quitté cet écran : il se fait depuis la fiche lead, onglet Devis,
      //    où le commercial choisit niveau / OTP / sections (voir blocLivraison).
      setDeliver({ reference: devis.reference })
      setGenStatus(null)
      setSending(false)
      setStatus(`Devis ${devis.reference} créé — à envoyer depuis la fiche lead.`)
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
    setAvertissementsSync([])
    const apiTool = builderApi.current
    if (!apiTool) {
      setGenError('Outil non prêt — ajustez le calepinage puis réessayez.')
      return
    }
    const layout = apiTool.serializeLayout()

    // L2 — incident PROUVÉ (DEV-202608-0016, onduleur+batterie sans ligne panneau
    // rempli au boot par erreur) : avant TOUTE écriture, on compare le calepinage
    // RÉELLEMENT posé à la cible vendue du devis — y COMPRIS une cible de zéro. Un
    // écart (dans un sens ou l'autre) prévient explicitement AVANT de réécrire les
    // lignes/câbles/structures du devis ; annuler = AUCUN appel réseau. Cible/posé
    // égaux (le cas courant) → aucun dialogue, comportement inchangé.
    const panneauxPoses = Number(layout?.result?.panels) || 0
    const panneauxDevis = Number(contexte?.cible?.panneaux) || 0
    if (panneauxPoses !== panneauxDevis) {
      const ok = await confirm({
        title: 'Le calepinage diverge du devis',
        description:
          `La conception pose ${panneauxPoses} panneaux ; le devis en porte ${panneauxDevis}. `
          + `Enregistrer mettra le devis à jour (lignes, câbles, structures). Continuer ?`,
        confirmLabel: 'Enregistrer quand même',
      })
      if (!ok) return
    }

    setSending(true)
    setGenStatus('Enregistrement de la conception…')
    try {
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

      // 1 bis) PVHEAL — ce que le serveur n'a PAS pu faire se dit tout de
      //    suite (composant absent du catalogue, kit non complété, deux
      //    onduleurs…), y compris quand rien n'a bougé.
      setAvertissementsSync(
        Array.isArray(resultat?.avertissements) ? resultat.avertissements : []
      )

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

      // 4) L-SECT — plus AUCUN mint ici : enregistrer une conception ne doit
      //    pas frapper un lien public aux réglages par défaut. L'écran confirme,
      //    et renvoie vers la fiche lead où l'envoi se choisit (voir
      //    blocLivraison). Aucun statut de devis n'est touché, comme avant.
      setDeliver({ reference: contexte?.devis?.reference ?? '' })
      setGenStatus(null)
      setSending(false)
      const ajoutees = Number(resultat.lignes_ajoutees) || 0
      setStatus(
        `Conception enregistrée — ${resultat.panneaux} panneaux (${resultat.kwc} kWc), `
        + `${resultat.lignes_modifiees} ligne(s) de devis mise(s) à jour`
        + (ajoutees > 0 ? `, ${ajoutees} ligne(s) de kit ajoutée(s).` : '.')
      )
    } catch {
      setGenStatus(null)
      setGenError('Erreur réseau pendant l’enregistrement. Vérifiez votre connexion puis réessayez.')
      setSending(false)
    }
  }

  // ── MODE AO — enregistrement du calepinage de l'AFFAIRE ────────────────
  // Le layout est un DOCUMENT DE TRAVAIL : il se range sur l'affaire
  // (`AppelOffre.roof_layout`) et ne réécrit JAMAIS la géométrie opposable du
  // dossier (toitures, zones, chaînes de cotes) ni le statut de l'affaire —
  // le serveur refuse (409) dès que le dossier est parti chez l'acheteur, avec
  // son propre motif en français.
  const enregistrerCalepinageAo = async () => {
    if (sending) return
    setGenError(null)
    setConflit(null)
    const apiTool = builderApi.current
    if (!apiTool) {
      setGenError('Outil non prêt — ajustez le calepinage puis réessayez.')
      return
    }
    setSending(true)
    setGenStatus('Enregistrement du calepinage…')
    try {
      const layout = apiTool.serializeLayout()
      await aoApi.affaires.enregistrerLayout(affaireId, layout)
      setGenStatus(null)
      setSending(false)
      setStatus('Calepinage enregistré sur l’affaire.')
    } catch (err) {
      const code = err?.response?.status
      const data = err?.response?.data
      setGenStatus(null)
      setSending(false)
      if (code === 409) {
        // Une affaire déposée ou close ne se révise pas depuis cet écran : le
        // geste est un nouvel indice de dossier, pas une « v2 » de devis.
        setConflit({
          detail: data?.detail || 'Ce calepinage ne peut plus être modifié.',
          revision_possible: false,
        })
        return
      }
      setGenError(httpMessage(code ?? 0, data))
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

  // Fondateur 18/08 — bouton Fermer (X, haut-droite) : cette fenêtre de
  // calepinage 3D n'avait aucune sortie visible une fois ouverte (lead,
  // liste des devis, générateur, ou la nouvelle entrée « Conception 3D » du
  // nav Ventes en amènent tous ici par un `navigate()` SPA). `navigate(-1)`
  // referme exactement comme le geste qui a ouvert l'écran l'a amené — jamais
  // une cible en dur qui pourrait diverger d'un appelant à l'autre. Le tracé
  // en cours n'est jamais perdu silencieusement : rien n'est envoyé ici, on
  // quitte seulement la vue (comme un retour navigateur).
  const fermer = () => navigate(-1)

  // PVHEAL — le bandeau d'avertissements du serveur, partagé par les deux
  // modes. Il reste affiché APRÈS le passage au bloc « Prêt à envoyer » : un
  // kit incomplet doit se voir au moment où l'on s'apprête à envoyer.
  const blocAvertissements = () => (
    avertissementsSync.length > 0 && (
      <div className="mt-4 border border-brass-400/40 p-4" data-testid="pvheal-avertissements">
        <p className="tech-label text-brass-300">À vérifier</p>
        <ul className="mt-2 space-y-1 text-sm text-lune-soft" role="status">
          {avertissementsSync.map((a) => <li key={a}>{a}</li>)}
        </ul>
      </div>
    )
  )

  const leadLabel = lead ? `${lead.nom ?? ''} ${lead.prenom ?? ''}`.trim() : ''
  // PV20 — en mode devis, le titre porte la référence + le client servis par le
  // contexte ; en lecture seule, le motif AFFICHÉ est celui du serveur.
  const devisLabel = (contexte?.devis?.client_nom ?? '').trim()
  const devisReference = contexte?.devis?.reference ?? ''
  // Mode AO — le titre porte NOTRE référence d'affaire + son objet, servis par
  // le même contexte agrégé (contrat `ao_design_context`).
  const affaireLabel = (contexte?.affaire?.objet ?? '').trim()
  const affaireReference = contexte?.affaire?.reference ?? ''
  const lectureSeule = (estDevis || estAo)
    && contexte != null && !contexte.modifiable
  const raisonLectureSeule = (contexte?.raison_lecture_seule ?? '').trim()
  const avertissements = Array.isArray(contexte?.avertissements)
    ? contexte.avertissements : []

  // Correction fondateur 24/08 — sans AUCUNE position (ni pin posé, ni GPS de
  // fiche), la carte reste au niveau Maroc : comportement inchangé, mais on le
  // DIT discrètement plutôt que de laisser deviner pourquoi la carte est loin
  // de chez le client. Mode AO non concerné (affaire, pas de repli GPS ici).
  const sansPositionGps = !loadError && (
    (!estDevis && !estAo && !!lead && !pinDepuisLead(lead))
    || (estDevis && !!contexte && !contexte?.geometrie?.pin)
  )

  const inputClass =
    'w-full border border-white/15 bg-white/5 px-3 py-3 text-base text-white outline-none focus:border-brass-400'
  const chipClass = 'rp9-chip'

  // PV21 — le bloc « Prêt à envoyer » est PARTAGÉ par les deux modes : un devis
  // conçu depuis sa propre fiche se livre exactement comme un devis né d'un
  // lead (mêmes liens, même bouton copier). Une seule différence : la phrase
  // qui dit ce qui vient de se passer.
  // L-SECT (fondateur 24/08/2026) — L'ENVOI A QUITTÉ CET ÉCRAN. Le lien, le
  // menu WhatsApp, le mailto et le bouton copier vivaient ici, dans l'outil de
  // calepinage : le commercial y envoyait donc la page client SANS pouvoir
  // choisir le niveau ni les sections (`shareLinkDevis` était appelé sans
  // aucune option — le lien partait toujours aux défauts). Il n'y a plus qu'UN
  // seul point d'envoi, la fiche lead → onglet Devis → « Envoyer au client »,
  // où ces choix existent. Cet écran confirme seulement ce qu'il vient de faire
  // et renvoie là-bas.
  const leadFiche = estDevis
    ? (contexte?.devis?.lead ?? null)
    : (lead?.id ?? (leadId || null))
  const blocLivraison = () => (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="tech-label rule-brass text-brass-300">Conception enregistrée</p>
        <p className="text-sm text-lune-soft">Devis <span className="font-semibold text-white">{deliver.reference}</span></p>
      </div>
      <p className="text-sm text-lune-soft">
        {estDevis
          ? 'La conception est enregistrée et la vue 3D mise à jour.'
          : 'Le devis est créé et la vue 3D enregistrée.'}
        {' '}
        L’envoi au client se fait depuis la fiche lead, onglet Devis : c’est là
        que vous choisissez le niveau, le code de lecture et les sections que le
        client reçoit.
      </p>
      {leadFiche && (
        <Link
          to={`/crm/leads/${leadFiche}`}
          data-testid="rp9-vers-fiche-lead"
          className="inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300"
        >
          Ouvrir la fiche lead
        </Link>
      )}
    </div>
  )

  return (
    <div className="rp9-host">
      {/* Fondateur 18/08 — barre haute : le libellé d'origine à gauche, le
          bouton Fermer (X) à droite. Toujours présent, quel que soit le mode
          (lead/devis/AO) — c'est LE MÊME écran, jamais une fenêtre qu'on ne
          peut refermer que par le bouton retour du navigateur. */}
      <div className="rp9-topbar">
        <p className="tech-label rule-brass text-brass-300">Interne · conception toiture</p>
        <button
          type="button"
          onClick={fermer}
          className="rp9-close"
          aria-label="Fermer la conception 3D"
          data-testid="rp9-fermer"
        >
          <X className="size-5" aria-hidden="true" />
        </button>
      </div>

      <div className="mt-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
          {estDevis && (
            <h1 className="display text-xl text-white sm:text-2xl">
              Devis <span className="text-brass-300">{devisReference || devisId || '—'}</span> ·{' '}
              <span className="text-lune-soft">{devisLabel || '—'}</span>
            </h1>
          )}
          {estAo && (
            <h1 className="display text-xl text-white sm:text-2xl">
              Affaire <span className="text-brass-300">{affaireReference || affaireId || '—'}</span> ·{' '}
              <span className="text-lune-soft">{affaireLabel || '—'}</span>
            </h1>
          )}
          {!estDevis && !estAo && (
            <h1 className="display text-xl text-white sm:text-2xl">
              Lead <span className="text-brass-300">{leadId || '—'}</span> ·{' '}
              <span className="text-lune-soft">{leadLabel || '—'}</span>
            </h1>
          )}
        </div>
        <p className="mt-2 text-sm text-lune-faint" aria-live="polite">{status}</p>

        {/* Correction fondateur 24/08 — discret, jamais bloquant : dit
            pourquoi la carte reste au niveau Maroc quand ni épingle ni GPS
            de fiche n'existent, plutôt que de laisser deviner. */}
        {sansPositionGps && (
          <p className="mt-1 text-xs text-lune-faint/70" data-testid="pv-sans-gps">
            Pas de position GPS sur la fiche — carte au niveau Maroc.
          </p>
        )}

        {loadError && (
          <p className="mt-3 text-sm text-alert-300" role="alert">{loadError}</p>
        )}

        {/* PV20 — LECTURE SEULE : le motif vient du serveur, jamais rédigé ici. */}
        {lectureSeule && (
          <div className="cine-card mt-6 border border-brass-400/40 p-5" data-testid="pv20-lecture-seule">
            <p className="tech-label rule-brass text-brass-300">Lecture seule</p>
            <p className="mt-3 text-sm text-lune-soft" role="status">
              {raisonLectureSeule || (estAo
                ? 'Ce calepinage ne peut plus être modifié.'
                : 'Ce devis ne peut plus être modifié.')}
            </p>
            {/* La visionneuse 3D plein écran est une route DEVIS
                (`/ventes/devis/:id/3d`) : en mode AO elle n'existe pas, et un
                lien mort serait pire que pas de lien. */}
            {estDevis && (
              <Link
                to={`/ventes/devis/${devisId}/3d`}
                className="mt-4 inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300"
              >
                Voir en 3D
              </Link>
            )}
          </div>
        )}

        {/* PV20 — avertissements serveur (multi-villa, aucune ligne panneau…).
            Mode AO : toiture non relevée, contour sans ancre géographique… */}
        {(estDevis || estAo) && avertissements.length > 0 && (
          <ul className="mt-4 space-y-1 text-xs text-lune-faint" data-testid="pv20-avertissements">
            {avertissements.map((a) => <li key={a}>{a}</li>)}
          </ul>
        )}

        {/* ÉTAPE FACTURE (alimente l'optimiseur) — MODE LEAD SEULEMENT. PV86 :
            en mode devis le dimensionnement vient du devis (cible.panneaux,
            imposée à l'optimiseur — voir roofPro11/prefill.ts hydrateFromDevis),
            la facture y est redondante et le fondateur a demandé son retrait.
            Retrait total (pas un simple masquage) : le builder lit ces deux
            éléments via `$('rp9-bill')`/`$('rp9-bill-kwh')`, qui renvoie `null`
            si absent (roofPro11/dom.ts) et TOUS les usages sont déjà gardés
            (`billEl?.value`, `if (billKwhEl)`, `billEl?.addEventListener`) —
            aucune casse à l'init sans ce bloc. Mode AO : le dimensionnement
            vient de l'engagement du dossier (cible.panneaux), pas d'une
            facture d'électricité — le bloc n'y a aucun sens non plus. */}
        {!estDevis && !estAo && (
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
        )}

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

          {/* W69 — « Personnaliser la disposition » : porté de apps/web/toiture-3d-pro-11.astro
              (bloc rp9-layout-window/rp9-layout-panel, lignes 478-632) — DEUX modes d'édition
              manuelle des panneaux (▦ Emplacements validés / ✥ Placement libre), pilotés par le
              module partagé roofPro11/layoutEditor.ts. Ids/data-* STRICTEMENT identiques à
              l'astro : le moteur les cherche par id, un id renommé = bouton mort silencieux. */}
          <div id="rp9-layout-window" hidden className="border-t border-white/10 bg-nuit-800 p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
              <p className="tech-label text-brass-300">Personnaliser la disposition</p>
              <button type="button" id="rp9-layout-toggle" aria-pressed="false"
                className="border border-brass-400 bg-brass-400/10 px-4 py-2 text-sm font-bold text-brass-300 transition-colors hover:bg-brass-400/20">
                Déplacer les panneaux
              </button>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-lune-faint">
              Activez, puis dans le <strong className="text-lune-soft">plan tactile</strong> ci-dessous
              touchez un panneau (bleu) puis un emplacement libre (vert) pour l'y déplacer — ou
              utilisez <strong className="text-lune-soft">+ / −</strong>. Vous pouvez aussi glisser un
              panneau directement sur la 3D. Les panneaux se calent toujours sur des emplacements
              valides (jamais hors toit, hors retrait ou sur un obstacle) ; le nombre, la puissance,
              la production et les économies se recalculent.
            </p>

            <div id="rp9-layout-panel" hidden className="mt-5 space-y-5">
              {/* PV30 — DEUX MODES d'édition, côte à côte et explicites. « Emplacements
                  validés » (le défaut) ne déplace un panneau que d'une cellule calculée à
                  une autre : sûr, mais impossible d'y gagner de la place. « Placement
                  libre » déplace au centimètre et laisse RÉGLER le retrait de rive et
                  l'écart entre panneaux — les seules limites qui restent sont physiques
                  (contour du toit, chevauchement, obstacle), et les distances réelles
                  s'affichent pendant le geste. */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="tech-label text-lune-faint">Mode d’édition</span>
                <button type="button" id="rp9-layout-mode-lattice" aria-pressed="true"
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300 aria-pressed:border-brass-400">
                  ▦ Emplacements validés
                </button>
                <button type="button" id="rp9-layout-mode-free" aria-pressed="false"
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300">
                  ✥ Placement libre
                </button>
              </div>

              <div id="rp9-free-controls" hidden className="space-y-3 border border-brass-400/30 bg-brass-400/5 p-3">
                <p className="text-xs leading-relaxed text-lune-soft">
                  En placement libre, ces deux marges sont les vôtres : les baisser fait tenir
                  plus de panneaux. Les <strong className="text-lune-soft">distances réellement
                  mesurées</strong> s’affichent pendant le déplacement — rien n’est réduit dans
                  votre dos. Le contour du toit, les chevauchements et les obstacles restent,
                  eux, infranchissables.
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <label htmlFor="rp9-free-setback" className="text-sm text-lune-soft">Retrait de rive (cm)</label>
                  <input id="rp9-free-setback" name="freeSetback" type="text" inputMode="decimal" step="any"
                    className="w-24 border border-white/25 bg-nuit-900 px-3 py-2 text-sm text-white" />
                  <label htmlFor="rp9-free-gap" className="text-sm text-lune-soft">Écart entre panneaux (cm)</label>
                  <input id="rp9-free-gap" name="freeGap" type="text" inputMode="decimal" step="any"
                    className="w-24 border border-white/25 bg-nuit-900 px-3 py-2 text-sm text-white" />
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <button type="button" id="rp9-free-add" aria-pressed="false"
                    className="border border-brass-400 bg-brass-400/10 px-4 py-2.5 text-sm font-bold text-brass-300 transition-colors hover:bg-brass-400/20">
                    ＋ Ajouter un panneau
                  </button>
                  <span id="rp9-free-measure" className="fig text-sm text-brass-300" aria-live="polite"></span>
                </div>
              </div>

              <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
                <div>
                  <dd id="rp9-layout-count" className="fig text-lg text-white sm:text-xl">—</dd>
                  <dt className="tech-label mt-0.5 text-lune-faint">Panneaux posés</dt>
                </div>
                <div>
                  <dd id="rp9-layout-kwc" className="fig text-lg text-white sm:text-xl">—</dd>
                  <dt className="tech-label mt-0.5 text-lune-faint">Puissance</dt>
                </div>
                <div>
                  <dd id="rp9-layout-free" className="fig text-lg text-white sm:text-xl">—</dd>
                  <dt className="tech-label mt-0.5 text-lune-faint">Emplacements libres</dt>
                </div>
                <div>
                  <dd id="rp9-layout-cover" className="fig text-lg text-brass-300 sm:text-xl">—</dd>
                  <dt className="tech-label mt-0.5 text-lune-faint">Couverture besoin</dt>
                </div>
              </dl>

              {/* Boutons +/− (touch + mouvement réduit, sans glissé fin) */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="tech-label text-lune-faint">Ajouter / retirer</span>
                <button type="button" id="rp9-layout-minus" aria-label="Retirer un panneau"
                  className="h-11 w-11 border border-white/25 text-2xl font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300 disabled:cursor-not-allowed disabled:opacity-40">−</button>
                <button type="button" id="rp9-layout-plus" aria-label="Ajouter un panneau"
                  className="h-11 w-11 border border-white/25 text-2xl font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300 disabled:cursor-not-allowed disabled:opacity-40">+</button>
                <button type="button" id="rp9-layout-fill"
                  className="border border-brass-400 bg-brass-400/10 px-4 py-2.5 text-sm font-bold text-brass-300 transition-colors hover:bg-brass-400/20 disabled:cursor-not-allowed disabled:opacity-40">
                  ⤢ Remplir automatiquement
                </button>
                <button type="button" id="rp9-layout-reset"
                  className="ml-auto border border-brass-400 bg-brass-400/10 px-4 py-2.5 text-sm font-bold text-brass-300 transition-colors hover:bg-brass-400/20">
                  ↺ Réinitialiser la disposition optimale
                </button>
              </div>

              {/* PV25 — sélection MULTIPLE (marquee au glissé + Maj, ou mode sélection au
                  doigt), déplacement du groupe / de la rangée entière, et nudge d'azimut.
                  Chaque déplacement reste « tout ou rien » : si un seul panneau du groupe
                  n'a pas d'emplacement valide, rien ne bouge.
                  PV34 — les gestes SANS modificateur sont désormais les principaux : glisser
                  sur le toit encadre, double-cliquer prend la rangée. Ces boutons restent le
                  repli tactile (et le mode rangée), et le compteur dit en permanence combien
                  de panneaux sont tenus. */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="tech-label text-lune-faint">Sélection &amp; rangée</span>
                <button type="button" id="rp9-layout-select" aria-pressed="false"
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300">
                  ▭ Sélection multiple
                </button>
                <button type="button" id="rp9-layout-row" aria-pressed="false"
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300">
                  ⇔ Déplacer la rangée
                </button>
                <button type="button" id="rp9-layout-clear-sel"
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300 disabled:cursor-not-allowed disabled:opacity-40">
                  ✕ Effacer la sélection
                </button>
                <span id="rp9-layout-selcount" data-rp9-selcount="0" aria-live="polite"
                  className="text-sm font-semibold text-brass-300">
                  Aucun panneau sélectionné
                </span>
              </div>
              <p className="text-xs leading-relaxed text-lune-soft">
                Sur la 3D : <strong className="text-lune-soft">glissez sur le toit, à côté des
                panneaux</strong>, pour encadrer un groupe ou une rangée ·{' '}
                <strong className="text-lune-soft">double-clic</strong> sur un panneau = toute sa
                rangée · <strong className="text-lune-soft">Ctrl (⌘) + clic</strong> ajoute ou
                retire un panneau · <strong className="text-lune-soft">Maj + glissé</strong> ajoute
                un cadre au groupe · <strong className="text-lune-soft">Échap</strong> lâche la
                sélection. Glissez ensuite n’importe quel panneau sélectionné : tout le groupe
                suit le curseur.
              </p>

              {/* PV26 — annuler / rétablir (Ctrl+Z / Ctrl+Y, ou ⌘). Les flèches du
                  clavier déplacent le panneau (ou le groupe) d'un emplacement. */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="tech-label text-lune-faint">Historique</span>
                <button type="button" id="rp9-layout-undo" disabled
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300 disabled:cursor-not-allowed disabled:opacity-40">
                  ↶ Annuler <span className="text-lune-faint">(Ctrl+Z)</span>
                </button>
                <button type="button" id="rp9-layout-redo" disabled
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300 disabled:cursor-not-allowed disabled:opacity-40">
                  ↷ Rétablir <span className="text-lune-faint">(Ctrl+Y)</span>
                </button>
                <span className="text-xs text-lune-soft">Flèches ← ↑ ↓ → : déplacer d’un emplacement</span>
              </div>

              {/* Nudge d'AZIMUT : n'a de sens que sur un toit en PENTE (la face du pan est
                  imposée par la toiture ; sur toit plat l'azimut est un axe de l'optimiseur).
                  Masqué en toit plat. */}
              <div id="rp9-layout-azimuth" hidden className="flex flex-wrap items-center gap-3">
                <span className="tech-label text-lune-faint">Azimut du pan</span>
                <button type="button" id="rp9-layout-az-minus" aria-label="Diminuer l’azimut d’un degré"
                  className="h-11 w-11 border border-white/25 text-2xl font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300">−</button>
                <span id="rp9-layout-az-value" className="fig text-lg text-white">—</span>
                <button type="button" id="rp9-layout-az-plus" aria-label="Augmenter l’azimut d’un degré"
                  className="h-11 w-11 border border-white/25 text-2xl font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300">+</button>
              </div>

              {/* Repli tactile : tap-sélection d'un panneau → tap-cible d'un emplacement vide.
                  Une mini-carte des cellules (occupées / libres) rend l'interaction code-vérifiable
                  et fonctionne sans glissé fin ni mouvement. */}
              <div>
                <p className="tech-label text-lune-faint">Plan des emplacements (tactile) — touchez un panneau, puis un emplacement libre</p>
                <div id="rp9-layout-grid" className="rp9-layout-grid mt-3" role="group" aria-label="Plan des emplacements de panneaux"></div>
                <p id="rp9-layout-note" className="mt-2 min-h-[1.25rem] text-xs leading-relaxed text-lune-soft" aria-live="polite"></p>
              </div>
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
            depuis cet écran (sa boucle d'enregistrement arrive en PV21).
            Mode AO : une affaire ne « génère » aucun devis depuis la toiture —
            le devis d'un appel d'offres naît du BORDEREAU DES PRIX (action
            « Créer le devis » de l'écran Bordereau), pas d'un calepinage. */}
        {!estDevis && !estAo && (
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
          {blocAvertissements()}
        </div>
        )}

        {/* PV21 — MODE DEVIS : « Enregistrer la conception ». Le devis existe
            déjà — on resynchronise ses lignes, on ne le recrée jamais. Absent
            en lecture seule (l'action de sauvegarde disparaît, PV20). */}
        {estDevis && !lectureSeule && (
        <div className="cine-card mt-6 p-6">
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
              Le nombre de panneaux, la batterie et l'onduleur suivent le calepinage,
              et le kit manquant (structures, socles, tableau de protection…) est
              ajouté : prix négociés, remises et notes du devis restent intacts.
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
          {blocAvertissements()}
        </div>
        )}

        {/* MODE AO : « Enregistrer le calepinage ». L'affaire existe déjà — on
            range son layout de travail, on ne touche NI son statut, NI sa
            géométrie opposable (toitures / zones / chaînes de cotes), NI aucun
            devis. Absent en lecture seule (dossier déposé ou clos). */}
        {estAo && !lectureSeule && (
        <div className="cine-card mt-6 p-6" data-testid="ao-enregistrer-calepinage">
          <button type="button" onClick={enregistrerCalepinageAo} disabled={sending}
            className="inline-flex w-full items-center justify-center gap-3 bg-ok-600 px-6 py-4 text-base font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
            style={{ background: 'var(--rp-ok-600)' }}>
            {sending && (
              <span aria-hidden="true"
                className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
            )}
            <span>{sending ? 'Enregistrement en cours…' : 'Enregistrer le calepinage'}</span>
          </button>
          <p className="mt-3 text-xs text-lune-faint">
            Le calepinage est rangé sur l'affaire. Le relevé opposable
            (toitures, zones, chaînes de cotes) et le statut du dossier ne
            bougent pas ; le devis, lui, se crée depuis le bordereau des prix.
          </p>
          {genStatus && <p className="mt-3 text-sm text-lune-soft" aria-live="polite">{genStatus}</p>}
          {genError && <p className="mt-3 text-sm text-alert-300" aria-live="assertive">{genError}</p>}

          {/* 409 : le dossier est parti chez l'acheteur — motif du SERVEUR. */}
          {conflit && (
            <div className="mt-4 border border-alert-300/40 p-4" data-testid="ao-conflit-lecture-seule">
              <p className="tech-label text-alert-300">Lecture seule</p>
              <p className="mt-2 text-sm text-alert-300" role="alert">{conflit.detail}</p>
            </div>
          )}
        </div>
        )}

        {/* PV86 — panneau de livraison TOUJOURS en bas de page en mode devis :
            frappé dès le chargement (voir bootDevis, best-effort), mis à jour
            après un enregistrement. Bloc séparé (jamais remplacé par le
            précédent) : sans lui, un devis en lecture seule n'aurait plus
            aucun moyen de renvoyer son lien au client. */}
        {estDevis && deliver && (
        <div className="cine-card mt-6 p-6">
          {blocLivraison()}
        </div>
        )}
      </div>
    </div>
  )
}
