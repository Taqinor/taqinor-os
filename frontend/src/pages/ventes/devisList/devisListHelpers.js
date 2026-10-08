import { useMemo } from 'react'
import { STATUT_DISPLAY } from './devisListConstants.js'

// SPL204 — aides partagées de la liste des devis (DevisList.jsx et ses hooks
// sous devisList/). Jamais un import circulaire depuis DevisList.jsx.

// Extrait un message d'erreur lisible (français) d'une réponse DRF. Couvre
// {detail}, les erreurs de champ ({statut: [...]} — ex. garde de remise T17),
// et retombe sur un message générique sinon. Ne JAMAIS afficher de JSON brut.
export function frenchError(err, fallback) {
  const data = err?.response?.data ?? err
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') {
    if (data.detail) return String(data.detail)
    const first = Object.values(data).find(Boolean)
    if (Array.isArray(first) && first.length) return String(first[0])
    if (typeof first === 'string') return first
  }
  return fallback
}

// VX222 — « Relancer ce devis » : à partir de l'aperçu WhatsApp EXISTANT (même
// modale, mêmes données), on remplace UNIQUEMENT le texte du message wa.me par
// un RAPPEL (« petit rappel concernant votre devis ») au lieu de l'envoi
// initial. On réutilise le numéro déjà normalisé côté serveur (base de
// `waData.wa_url`, avant le `?text=`) + le lien public déjà émis (`waData.url`),
// donc aucun backend ni duplication de logique de téléphone. Aperçu-puis-clic :
// rien n'est envoyé automatiquement (règle manuel-wa.me fondateur).
export function buildRelanceMessage(waData, reference) {
  const lien = waData?.url || ''
  return `Bonjour, petit rappel concernant votre devis ${reference || ''}${lien ? ' : ' + lien : ''}`.trim()
}
export function buildRelanceWaUrl(waData, reference) {
  if (!waData?.wa_url) return null
  const base = waData.wa_url.split('?')[0]   // https://wa.me/<numéro normalisé>
  return `${base}?text=${encodeURIComponent(buildRelanceMessage(waData, reference))}`
}

// ADEV44 (C-ADEV-001) — le corps du POST « Refuser » selon le contrat
// `apps/ventes/contract_samples/devis_refuser.json` : `motif` = le NOM du
// MotifPerte choisi (la vue le valide contre les motifs actifs de la société),
// `note` = le détail libre. Avant, l'écran envoyait `motif_perte: <id>` (clé
// jamais lue par la vue) + la note sous `motif` : tout refus tombait « sans
// motif ».
export function corpsRefus({ motifsPerte, motifId, note }) {
  const choisi = (motifsPerte || []).find(m => String(m.id) === String(motifId))
  const nom = (choisi?.nom ?? choisi?.libelle ?? '').trim()
  const corps = {}
  if (nom) corps.motif = nom
  const detail = (note || '').trim()
  if (detail) corps.note = detail.slice(0, 255)
  return corps
}

// SPL206 — dérivés de la synthèse de l'en-tête de page (move only).
// Nombre de jours calendaires entre aujourd'hui et une date ISO (peut être
// négatif). null si la date est absente/invalide.
function daysUntil(isoDate) {
  if (!isoDate) return null
  const target = new Date(isoDate)
  if (Number.isNaN(target.getTime())) return null
  const today = new Date()
  const a = Date.UTC(target.getFullYear(), target.getMonth(), target.getDate())
  const b = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((a - b) / 86400000)
}

// ADEV9 (C-ADEV-003) — une version REMPLACÉE par une révision
// (`is_active === false`) n'est plus « en jeu » : la carte de synthèse compte
// l'installation UNE fois (sa version courante), comme le tableau de bord
// serveur (`selectors.devis_en_jeu`). Un devis sans champ `is_active` (ancien
// payload) reste compté.
export function devisEnJeu(d) {
  return d?.is_active !== false
}

// T6 — Résumé : nombre + total TTC par statut effectif (sur les devis chargés
// et en jeu).
export function syntheseParStatut(devis, effStatutOf) {
  const acc = {}
  for (const key of Object.keys(STATUT_DISPLAY)) acc[key] = { count: 0, total: 0 }
  for (const d of devis) {
    if (!devisEnJeu(d)) continue
    const key = effStatutOf(d)
    if (!acc[key]) acc[key] = { count: 0, total: 0 }
    acc[key].count += 1
    acc[key].total += Number(d.total_affiche ?? d.total_ttc ?? 0) || 0
  }
  return acc
}

// Dérivés de la synthèse (T6 / T15 / T16), calculés par le composant principal
// (l'en-tête de page lit `expiringSoon` aussi pendant le chargement/l'erreur).
export function useDevisListSynthese(devis, effStatutOf) {
  // T6 — Résumé : nombre + total TTC par statut effectif (sur les devis chargés).
  // eslint-disable-next-line react-hooks/exhaustive-deps -- dépendances identiques au code d'origine (effStatutOf est pure)
  const summary = useMemo(() => syntheseParStatut(devis, effStatutOf), [devis])

  // T15 — Devis envoyés expirant dans ≤ 7 jours (et pas encore expirés).
  // ADEV9 — une version remplacée n'expire plus « bientôt » : elle n'est plus en jeu.
  const expiringSoon = useMemo(() => devis.filter(d => {
    if (!devisEnJeu(d)) return false
    if (d.statut !== 'envoye' || d.is_expired) return false
    const days = daysUntil(d.date_expiration)
    return days !== null && days >= 0 && days <= 7
  }), [devis])

  // T16 — Répartition batterie sur les devis acceptés (option_acceptee).
  const batteryInsight = useMemo(() => {
    let avec = 0; let sans = 0
    for (const d of devis) {
      if (d.statut !== 'accepte') continue
      if (d.option_acceptee === 'avec_batterie') avec += 1
      else if (d.option_acceptee === 'sans_batterie') sans += 1
    }
    return { avec, sans }
  }, [devis])
  return { summary, expiringSoon, batteryInsight }
}

/** CIQ325 — le libellé du format complet annonce le VRAI nombre de pages. */
export function libelleFormatComplet({ targetIsAgricole, targetMode }) {
  if (targetIsAgricole) {
    return 'Document agricole complet (3 pages — eau et argent, fonctionnement, équipement et signature)'
  }
  if (targetMode === 'commercial') {
    return 'Document commercial (3 pages — votre installation, l\'investissement et son retour, conditions et signature)'
  }
  if (targetMode === 'industriel') {
    return 'Document industriel (4 pages — synthèse, équipements, rentabilité, conditions et signature)'
  }
  return 'Devis premium (3 pages — options, analyse, garanties)'
}
