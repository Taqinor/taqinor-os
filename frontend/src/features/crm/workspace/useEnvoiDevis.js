import { useEffect, useRef, useState } from 'react'
import ventesApi from '../../../api/ventesApi'
import crmApi from '../../../api/crmApi'
import stockApi from '../../../api/stockApi'
import { fetchAllPages } from '../../../utils/fetchAllPages'
import { normalizePhoneE164 } from '../../../lib/format'
import { errorMessageFrom } from '../../../lib/toast'
// L5 (fondateur 21/08/2026) — lien PAGE CLIENT + message WhatsApp, MÊME
// FORMAT que l'outil 3D (ToitureDesign.jsx). Fonctions pures, testées à part.
import { clientProposalUrl, proposalWhatsappText, buildWaUrl } from '../../ventes/clientProposalLink'
import {
  sectionsDepuisServeur, taillesDepuisServeur, taillesFromOptionsCount, dateRelanceJ3,
} from './devisTabLogique'

// ALEA52 — l'ÉTAT et les GESTES de la boîte « Envoyer au client » (partagée par
// la carte devis de DevisTab et l'aperçu de LeadDevisPanel) ; le rendu vit dans
// EnvoiDevisDialog.jsx (react-refresh : un fichier de composants n'exporte que
// des composants).

// L5 — site public (page client), même résolution que ToitureDesign.jsx.
const PUBLIC_SITE_URL = import.meta.env.VITE_PUBLIC_SITE_URL || 'https://taqinor.ma'

// Les options 1/2/3 (Éco/Recommandé/Max) n'existent que pour le RÉSIDENTIEL
// (DevisOffresTailles refuse les autres marchés) : un devis dont le marché est
// connu et différent n'en propose pas. Marché inconnu ⇒ comportement d'avant.
export const optionsTaillesOffertes = (modeDevis) => !modeDevis || modeDevis === 'residentiel'

/** Les réglages de la page client (niveau, OTP, sections, tailles) + le
 *  dernier lien minté, par devis. Le choix local prime ; à défaut on repart de
 *  l'état RÉEL du lien connu du serveur (`share_link`), jamais des défauts. */
export function useReglagesLien() {
  const [niveauSel, setNiveauSel] = useState({}) // id -> 'standard'|'confiance'
  const [otpSel, setOtpSel] = useState({}) // id -> bool
  const [linkMeta, setLinkMeta] = useState({}) // id -> { niveau, otp_lecture, token, sections }
  const [sectionsSel, setSectionsSel] = useState({}) // id -> { clé: bool }
  const [taillesSel, setTaillesSel] = useState({}) // id -> { taille_eco, taille_max }
  const serverLinkMeta = (d) => (d?.share_link ? d.share_link : null)
  const currentLinkMeta = (d) => linkMeta[d.id] ?? serverLinkMeta(d)
  const getNiveau = (d) => niveauSel[d.id] ?? serverLinkMeta(d)?.niveau ?? 'standard'
  const getOtp = (d) => otpSel[d.id] ?? serverLinkMeta(d)?.otp_lecture ?? false
  const sectionsChoisies = (d) => (
    sectionsSel[d.id] ?? sectionsDepuisServeur(currentLinkMeta(d)?.sections)
  )
  const onSectionChange = (d, cle, valeur) => {
    setSectionsSel((cur) => ({ ...cur, [d.id]: { ...sectionsChoisies(d), [cle]: !!valeur } }))
  }
  const getTailles = (d) => (
    taillesSel[d.id] ?? taillesDepuisServeur(currentLinkMeta(d)?.sections)
  )
  const onTailleToggle = (d, cle, valeur) => {
    setTaillesSel((cur) => ({ ...cur, [d.id]: { ...getTailles(d), [cle]: !!valeur } }))
  }
  const onOptionsCountChange = (d, count) => {
    setTaillesSel((cur) => ({ ...cur, [d.id]: taillesFromOptionsCount(count, getTailles(d)) }))
  }
  // Le corps posté au serveur : les 7 clés de sections + les 2 clés de
  // tailles, dans le MÊME objet `sections` (whitelist serveur étendue).
  const getSections = (d) => ({ ...sectionsChoisies(d), ...getTailles(d) })
  const memoriserLien = (d, data) => setLinkMeta((cur) => ({
    ...cur,
    [d.id]: {
      niveau: data?.niveau, otp_lecture: data?.otp_lecture,
      token: data?.token, sections: data?.sections,
    },
  }))
  return {
    setNiveauSel, setOtpSel, currentLinkMeta, getNiveau, getOtp, getSections,
    getTailles, onSectionChange, onTailleToggle, onOptionsCountChange,
    sectionsChoisies, memoriserLien,
  }
}

/** Catalogue société chargé À L'OUVERTURE de « Modifier les options » (une
 *  seule fois par session d'écran) : sans lui l'éditeur ne propose aucune
 *  substitution (LANE E). Un échec réseau dégrade sans bloquer. */
function useCatalogueSubstitutions(editTaillesOuvert) {
  const demarre = useRef(false)
  const [produits, setProduits] = useState(null)
  useEffect(() => {
    if (editTaillesOuvert == null || demarre.current) return
    demarre.current = true
    fetchAllPages((page) => stockApi.getProduits({ page }).then((r) => r.data))
      .then(setProduits)
      .catch(() => { /* dégrade : éditeur sans substitutions, jamais un dialogue cassé */ })
  }, [editTaillesOuvert])
  return produits
}

/** ALEA55 — « Proposer une relance J+3 » : case décochée par défaut (jamais un
 *  effet caché) ; cochée, APRÈS un envoi réussi `relance_date` du lead = J+3 par
 *  l'API existante (`updateLead`). Une relance déjà planifiée n'est JAMAIS
 *  écrasée, et la relance n'est posée qu'une fois. */
function useRelanceJ3({ leadId, relanceActuelle }) {
  const [cochee, setCochee] = useState(false)
  const [posee, setPosee] = useState(null)
  const proposable = !!leadId && !relanceActuelle && !posee
  const appliquer = async () => {
    if (!cochee || !proposable) return
    const date = dateRelanceJ3()
    await crmApi.updateLead(leadId, { relance_date: date })
    setPosee(date)
  }
  return { cochee, setCochee, posee, actuelle: relanceActuelle, proposable, date: dateRelanceJ3(), appliquer }
}

/** Tous les gestes d'envoi d'un devis (copier / ouvrir / WhatsApp / e-mail /
 *  aperçu interne) et leur état. `onRefresh` recharge la fiche après un ENVOI
 *  (le devis passe « envoyé », le funnel avance — QJ-FUNNEL). */
export function useEnvoiDevis({
  leadPhone, leadEmail, leadNom, onRefresh, leadId = null, relanceActuelle = null,
}) {
  const reglages = useReglagesLien()
  const relance = useRelanceJ3({ leadId, relanceActuelle })
  const [linkBusy, setLinkBusy] = useState(null)
  const [copiedId, setCopiedId] = useState(null)
  // L-INTPREV — feedback « Copié » DISTINCT de `copiedId`.
  const [copiedInterneId, setCopiedInterneId] = useState(null)
  const [actionMsg, setActionMsg] = useState(null)
  const [editTaillesOuvert, setEditTaillesOuvert] = useState(null) // id du devis | null
  const produitsCatalogue = useCatalogueSubstitutions(editTaillesOuvert)
  const leadPhoneOk = !!normalizePhoneE164(leadPhone)
  const { getNiveau, getOtp, getSections, memoriserLien } = reglages

  // Après un ENVOI réussi : relance J+3 si demandée, puis rechargement de la fiche.
  const apresEnvoi = async () => {
    await relance.appliquer()
    onRefresh?.()
  }

  // Un geste réseau : busy PAR devis + PAR action, message d'échec commun.
  const lancer = async (busyKey, echec, geste) => {
    setLinkBusy(busyKey)
    setActionMsg(null)
    try {
      await geste()
    } catch (err) {
      setActionMsg(errorMessageFrom(err, echec))
    } finally {
      setLinkBusy(null)
    }
  }
  const poserCopie = (setter, id) => {
    setter(id)
    window.setTimeout(() => setter((cur) => (cur === id ? null : cur)), 2000)
  }
  const copier = async (url, setter, id) => {
    try {
      await navigator.clipboard?.writeText(url)
      poserCopie(setter, id)
    } catch (err) {
      // presse-papier indisponible (contexte non sécurisé, permission) : le lien
      // reste ouvrable dans la boîte — dit au commercial, jamais avalé (AFAC95).
      setActionMsg(errorMessageFrom(err, 'Copie impossible : sélectionnez le lien et copiez-le.'))
    }
  }

  // Mint (ou réutilise — idempotent côté serveur) le ShareLink du devis, AU
  // niveau/OTP choisis pour CE devis. QJ-FUNNEL : `envoi: true` dit au backend
  // que ce POST est un ENVOI au client (devis brouillon → « envoyé »).
  const mint = async (d, { envoi = false, cle = 'path' } = {}) => {
    const res = await ventesApi.shareLinkDevis(d.id, {
      niveau: getNiveau(d), otp_lecture: getOtp(d), sections: getSections(d),
      ...(envoi ? { envoi: true } : {}),
    })
    memoriserLien(d, res.data)
    return clientProposalUrl(res.data?.[cle], PUBLIC_SITE_URL)
  }

  const copierApercuInterne = (d) => lancer(`i-${d.id}`, 'Lien d’aperçu interne indisponible.', async () => {
    await copier(await mint(d, { cle: 'path_interne' }), setCopiedInterneId, d.id)
  })
  const ouvrirApercuInterne = (d) => lancer(`io-${d.id}`, 'Lien d’aperçu interne indisponible.', async () => {
    window.open(await mint(d, { cle: 'path_interne' }), '_blank', 'noopener')
  })
  const copierPageClient = (d) => lancer(`l-${d.id}`, 'Lien de la page client indisponible.', async () => {
    // QJ-FUNNEL — copier le lien = l'envoyer (devis « envoyé », funnel avance).
    await copier(await mint(d, { envoi: true }), setCopiedId, d.id)
    await apresEnvoi()
  })
  const ouvrirPageClient = (d) => lancer(`o-${d.id}`, 'Lien de la page client indisponible.', async () => {
    window.open(await mint(d), '_blank', 'noopener')
  })
  // WhatsApp PAR devis : on partage la PAGE CLIENT web, MÊME message que l'outil 3D.
  const envoyerWhatsAppUnique = (d) => {
    if (!leadPhoneOk) return undefined
    return lancer(`w-${d.id}`, 'Lien WhatsApp indisponible.', async () => {
      const url = await mint(d, { envoi: true })
      const waUrl = buildWaUrl(normalizePhoneE164(leadPhone), proposalWhatsappText(leadNom, url))
      if (waUrl) window.open(waUrl, '_blank', 'noopener')
      await apresEnvoi()
    })
  }
  // E-mail (QJ14) : PDF premium + lien tokenisé → le client, consigné et marqué
  // « envoyé » côté serveur (chemin unique `mark_devis_sent`).
  const envoyerEmail = (d) => lancer(`e-${d.id}`, 'Envoi e-mail impossible.', async () => {
    await ventesApi.envoyerEmailDevis(d.id, leadEmail ? { to_email: leadEmail } : {})
    setActionMsg(`E-mail envoyé à ${leadEmail || 'l’adresse du client'}.`)
    await apresEnvoi()
  })

  // L-NIV-UI — niveau/OTP : si un lien EXISTE DÉJÀ, on re-poste tout de suite
  // le nouveau choix (même token, seul le niveau affiché au client change).
  const appliquerNiveauSiMinte = (d, niveau, otpLecture) => {
    if (!reglages.currentLinkMeta(d)) return undefined
    return lancer(`n-${d.id}`, 'Changement de niveau impossible.', async () => {
      const res = await ventesApi.shareLinkDevis(d.id, {
        niveau, otp_lecture: otpLecture, sections: getSections(d),
      })
      memoriserLien(d, res.data)
    })
  }
  const onNiveauChange = (d, niveau) => {
    reglages.setNiveauSel((cur) => ({ ...cur, [d.id]: niveau }))
    appliquerNiveauSiMinte(d, niveau, getOtp(d))
  }
  const onOtpChange = (d, otpLecture) => {
    reglages.setOtpSel((cur) => ({ ...cur, [d.id]: otpLecture }))
    appliquerNiveauSiMinte(d, getNiveau(d), otpLecture)
  }

  return {
    ...reglages, leadPhoneOk, leadEmail, relance, linkBusy, copiedId, copiedInterneId,
    actionMsg, setActionMsg, editTaillesOuvert, setEditTaillesOuvert,
    produitsCatalogue, copierApercuInterne, ouvrirApercuInterne, copierPageClient,
    ouvrirPageClient, envoyerWhatsAppUnique, envoyerEmail, onNiveauChange,
    onOtpChange,
  }
}
