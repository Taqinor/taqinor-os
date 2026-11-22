import { useCallback, useEffect, useRef, useState } from 'react'
import calepinageApi from '../../../../../api/calepinageApi'
import { messageRefus } from '../../../commun/refusServeur'
import { lireConflit } from '../../../conflitEcriture'
import { fmtKwc } from './panneaux/sources'
import { formatNumber } from '../../../../../lib/format'

/* ============================================================================
   ÉTAPE TOIT (maquette Main, 22/11) — LECTURE DU DOM DU CONSTRUCTEUR ET RENVOI
   DES GESTES VERS SES CONTRÔLES.
   ----------------------------------------------------------------------------
   Le constructeur (script `@roofbuilder`) écrit ses chiffres et ses états dans
   le DOM qu'il possède (`rp9-*`). L'écran guidé ne recalcule RIEN : il LIT ces
   nœuds (surface, pans, besoin, pente, obstacles, cotes, outils actifs) et, pour
   agir, CLIQUE le vrai contrôle du script (même geste, même effet). Une valeur
   absente du DOM rend `null` : le bloc correspondant n'est pas affiché — jamais
   un chiffre inventé.
   ========================================================================== */

const parId = (racine, id) => racine?.getElementById?.(id) ?? racine?.querySelector?.(`[id="${id}"]`) ?? null
const texte = (n) => (n?.textContent ?? '').replace(/\s+/g, ' ').trim()
const vide = (t) => t === '' || t === '—' || t === '-'
const visible = (n) => Boolean(n) && !n.hidden

const NOMS_FACE = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']

/** Nom de la face (8 points, minuscules : « face sud ») d'un azimut en degrés (0 = nord, 180 = sud). */
export function nomFace(azimutDeg) {
  const n = Number(azimutDeg)
  if (!Number.isFinite(n)) return null
  return NOMS_FACE[Math.round((((n % 360) + 360) % 360) / 45) % 8]
}

/** Degrés à la française : entier tel quel, sinon une décimale (« 22 », « 22,5 »). */
export function degres(valeur) {
  const n = Number(valeur)
  if (!Number.isFinite(n)) return null
  return formatNumber(n, { maxDecimals: 1 })
}

const nombre = (t) => {
  const m = /-?\d+(?:[.,]\d+)?/.exec(String(t ?? '').replace(/\s/g, ''))
  return m ? Number(m[0].replace(',', '.')) : null
}

/** « Surface du toit » : la somme des surfaces de la table des pans quand il y en a plusieurs (un pan encore
    à tracer, « — », n'y compte pas), sinon la surface du pan tracé (`#rp9-area-value`, sans son « ~ »).
    `null` tant qu'aucun contour n'existe. */
export function lireSurface(racine) {
  const lignes = [...(racine?.querySelectorAll?.('[data-pan-stat]') ?? [])]
  const valeurs = lignes.map((l) => {
    const cellules = l.querySelectorAll('td')
    return nombre(texte(cellules[cellules.length - 2]))
  }).filter((v) => v !== null && v > 0)
  const somme = valeurs.length > 0
    ? `${formatNumber(valeurs.reduce((a, b) => a + b, 0), { decimals: 0 })} m²`
    : null
  if (lignes.length > 1 && somme) return somme
  const t = texte(parId(racine, 'rp9-area-value')).replace(/^~\s*/, '')
  // Le pan actif encore à tracer (ajout d'un pan) : la table garde le toit déjà tracé.
  return vide(t) ? somme : t
}

/** Les zones de la liste du script (`#rp9-areas-list [data-area-row]`) : l'active est celle sans bouton
    « Voir » ; « à tracer » = sans contour (texte écrit par `zones.ts::renderAreasPanel`). */
export function lireZones(racine) {
  return [...(racine?.querySelectorAll?.('#rp9-areas-list [data-area-row]') ?? [])].map((li) => ({
    id: li.dataset.areaRow,
    active: !li.querySelector('[data-area-select]'),
    aTracer: /à tracer/.test(texte(li)),
  }))
}

/** Nombre de pans TRACÉS de la liste des zones (une zone « à tracer » n'est pas encore un pan), `null` sans pan. */
export function lirePans(racine) {
  const n = lireZones(racine).filter((z) => !z.aTracer).length
  return n > 0 ? n : null
}

/** « Besoin d'après la facture » : UNIQUEMENT la taille tirée des factures du lead que sert le design-context
    (`cible_factures.kwc`, accesseur `panneaux/sources.js::cibleFactures`, même chiffre et même format que l'étape
    Panneaux). Jamais un chiffre du constructeur : en mode calepinage, ses `rp9-reco-*` / `rp9-need-*` décrivent la
    pose ou la cible ENREGISTRÉE du pan, pas la facture. `null` (puce à deux parts) sans bloc servi. */
export function texteBesoin(cible) {
  return typeof cible?.kwc === 'number' && cible.kwc > 0 ? `≈ ${fmtKwc(cible.kwc)}` : null
}

/** Vue de la caméra lue sur la boussole de MapLibre (`rotateX(<inclinaison>deg)`) : 'plan' ou '3d', `null` inconnue. */
export function lireVue(racine) {
  const icone = racine?.querySelector?.('.maplibregl-ctrl-compass .maplibregl-ctrl-icon')
  const m = /rotateX\((-?[\d.]+)deg\)/.exec(icone?.style?.transform ?? '')
  if (!m) return null
  return Number(m[1]) > 1 ? '3d' : 'plan'
}

/** Longueur / largeur : avant tout contour, les champs de « Créer le toit » (`#rp9-toit-cotes`) ; contour
    fermé, les cotes du pan actif (`#rp9-pan-longueur` / `#rp9-pan-largeur`, vides et désactivées hors rectangle). */
export function lireCotes(racine) {
  const form = parId(racine, 'rp9-toit-cotes')
  if (visible(form)) {
    const champ = (nom) => form.querySelector(`input[name="${nom}"]`)?.value ?? ''
    return { mode: 'creer', longueur: champ('longueur'), largeur: champ('largeur'), desactive: false }
  }
  const panneau = parId(racine, 'rp9-pan-geometry')
  const L = parId(racine, 'rp9-pan-longueur')
  const W = parId(racine, 'rp9-pan-largeur')
  if (visible(panneau) && L && W) {
    return { mode: 'pan', longueur: L.value, largeur: W.value, desactive: L.disabled || W.disabled }
  }
  return { mode: 'aucun', longueur: '', largeur: '', desactive: true }
}

/** Les obstacles du tableau « Objets du site » du script (`#rp9-objets-site [data-objet]`, texte
    « type · cotes · hauteur H · provenance · pan ») : `{ id, pan, nom, cotes, hauteur }`. */
export function lireObstacles(racine) {
  return [...(racine?.querySelectorAll?.('#rp9-objets-site [data-objet]') ?? [])].map((b) => {
    const [nom = '', cotes = '', hauteur = ''] = texte(b).split(' · ')
    const h = hauteur.replace(/^hauteur\s*/, '')
    return { id: b.dataset.objet, pan: b.dataset.pan, nom, cotes, hauteur: vide(h) ? null : h }
  })
}

/** Pente et face du pan actif telles que le script les affiche (`#rp9-pitch-value`, `#rp9-facing-value`) ;
    « à confirmer » = la mention du script `#rp9-pitch-note` (`hypotheses.ts::etatHypotheses` : pas de `pitchSource`). */
export function lirePente(racine) {
  const plat = Boolean(racine?.querySelector?.('[data-rooftype="flat"][aria-pressed="true"]'))
  const face = texte(parId(racine, 'rp9-facing-value')).split(' · ')[0].toLowerCase()
  return {
    plat,
    deg: nombre(texte(parId(racine, 'rp9-pitch-value'))),
    face: face || null,
    aConfirmer: !vide(texte(parId(racine, 'rp9-pitch-note'))),
  }
}

/** État des outils de la carte, lu sur les vrais contrôles du script. */
export function lireOutils(racine) {
  const finish = parId(racine, 'rp9-finish')
  const point = parId(racine, 'rp9-undo-point')
  const zone = parId(racine, 'rp9-add-area')
  const actif = (id) => Boolean(parId(racine, id)) && !parId(racine, id).disabled
  const obstacle = parId(racine, 'rp9-obstacle')?.getAttribute('aria-pressed') === 'true'
  const mesure = Boolean(racine?.querySelector?.('[data-mesure-kind][aria-pressed="true"]'))
  return {
    ferme: Boolean(zone) && !zone.disabled,
    traceEnCours: (Boolean(finish) && !finish.disabled) || visible(point),
    obstacle,
    mesure,
    annuler: visible(point) || actif('rp9-layout-undo'),
    retablir: actif('rp9-layout-redo'),
    vue: lireVue(racine),
  }
}

/** Tout ce que l'étape Toit affiche, lu d'un coup (objet sérialisable : comparé pour éviter les rendus inutiles). */
export function lireEtatToit(racine) {
  return {
    surface: lireSurface(racine),
    pans: lirePans(racine),
    cotes: lireCotes(racine),
    obstacles: lireObstacles(racine),
    pente: lirePente(racine),
    outils: lireOutils(racine),
  }
}

/** Clique le vrai contrôle du script (`id`) s'il existe et n'est pas désactivé. Rend vrai si le geste est parti. */
export function cliquerControle(racine, id) {
  const b = parId(racine, id)
  if (!b || b.disabled) return false
  b.click()
  return true
}

/** Les gestes de la barre d'outils flottante, chacun RENVOYÉ au contrôle existant du constructeur. */
export const GESTES = {
  // Sélectionner = sortir du mode en cours (obstacle armé, mesure en cours).
  selection: (racine) => {
    const o = lireOutils(racine)
    if (o.obstacle) cliquerControle(racine, 'rp9-obstacle')
    if (o.mesure) cliquerControle(racine, 'rp9-mesure-cancel')
  },
  // Tracer, sans toit : le tracé au clic est déjà le mode actif (rien à cliquer). Avec un toit : `commencerAjoutPan`.
  trace: () => false,
  obstacle: (racine) => cliquerControle(racine, 'rp9-obstacle'),
  mesure: (racine) => cliquerControle(racine, lireOutils(racine).mesure ? 'rp9-mesure-cancel' : 'rp9-mesure-distance'),
  // Annuler : le dernier point pendant un tracé, sinon l'historique de pose.
  annuler: (racine) => cliquerControle(racine, visible(parId(racine, 'rp9-undo-point')) ? 'rp9-undo-point' : 'rp9-layout-undo'),
  retablir: (racine) => cliquerControle(racine, 'rp9-layout-redo'),
}

const ligneZone = (racine, attribut, id) => [...(racine?.querySelectorAll?.(`[${attribut}]`) ?? [])]
  .find((b) => b.getAttribute(attribut) === id) ?? null

/** « Ajouter un pan » (toit déjà tracé) : « + Ajouter une zone » du script (`addArea`), qui ouvre une zone vide et
    la rend active. Rend `{ precedent, nouveau }` (ids de zone) pour pouvoir l'annuler, `null` si rien n'est parti. */
export function commencerAjoutPan(racine) {
  const avant = lireZones(racine)
  if (!cliquerControle(racine, 'rp9-add-area')) return null
  const nouveau = lireZones(racine).find((z) => !avant.some((a) => a.id === z.id))
  if (!nouveau) return null
  return { precedent: avant.find((z) => z.active)?.id ?? null, nouveau: nouveau.id }
}

/** Annule l'ajout : la zone ouverte est supprimée par son « × » (`deleteArea`) et le pan d'avant redevient actif
    par son « Voir » (`selectArea`) — le toit d'avant revient tel quel. Rend vrai si la zone a été retirée. */
export function annulerAjoutPan(racine, ajout) {
  const suppr = ligneZone(racine, 'data-area-del', ajout?.nouveau)
  if (!suppr) return false
  suppr.click()
  ligneZone(racine, 'data-area-select', ajout.precedent)?.click()
  return true
}

/** L'ajout est fini quand sa zone n'existe plus, ou que son contour est fermé : la ligne n'est plus « à tracer »,
    ou « + Ajouter une zone » est réactivé (le script ne l'active que contour fermé — même un pan sans panneau). */
export function ajoutTermine(racine, ajout) {
  const z = lireZones(racine).find((x) => x.id === ajout.nouveau)
  return !z || !z.aTracer || lireOutils(racine).ferme
}

/** Pose longueur × largeur dans le vrai contrôle : « Créer le toit » (soumet `#rp9-toit-cotes`) ou les cotes du
    pan actif (« Appliquer les cotes », `#rp9-pan-coter`). Le script valide et dit son refus dans `#rp9-status`. */
export function appliquerCotes(racine, longueur, largeur) {
  const { mode } = lireCotes(racine)
  if (mode === 'creer') {
    const form = parId(racine, 'rp9-toit-cotes')
    form.querySelector('input[name="longueur"]').value = longueur
    form.querySelector('input[name="largeur"]').value = largeur
    if (typeof form.requestSubmit === 'function') form.requestSubmit()
    else form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    return true
  }
  if (mode === 'pan') {
    parId(racine, 'rp9-pan-longueur').value = longueur
    parId(racine, 'rp9-pan-largeur').value = largeur
    return cliquerControle(racine, 'rp9-pan-coter')
  }
  return false
}

/** Sélectionne un obstacle comme le fait le tableau « Objets du site » (clic sur sa ligne). */
export function selectionnerObstacle(racine, { id, pan }) {
  const ligne = [...(racine?.querySelectorAll?.('#rp9-objets-site [data-objet]') ?? [])]
    .find((b) => b.dataset.objet === id && b.dataset.pan === pan)
  if (!ligne) return false
  ligne.click()
  return true
}

/** L'état de l'étape, relu toutes les `intervalle` ms (le script n'émet aucun événement) et à la demande
    (`relire`, juste après un geste renvoyé). Un état inchangé ne provoque aucun rendu. `contourFerme` change
    (un numéro qui croît) quand un tracé EN COURS vient de se fermer — jamais à l'ouverture d'un toit enregistré. */
export function useEtatToit(intervalle = 500) {
  const [etat, setEtat] = useState(() => ({ ...lireEtatToit(document), contourFerme: 0 }))
  const dernier = useRef({ cle: JSON.stringify(etat), traceEnCours: etat.outils.traceEnCours, contourFerme: 0 })
  const relire = useCallback(() => {
    const lu = lireEtatToit(document)
    const avant = dernier.current
    const ferme = avant.traceEnCours && !lu.outils.traceEnCours && lu.outils.ferme
    const suivant = { ...lu, contourFerme: avant.contourFerme + (ferme ? 1 : 0) }
    const cle = JSON.stringify(suivant)
    dernier.current = { cle, traceEnCours: lu.outils.traceEnCours, contourFerme: suivant.contourFerme }
    if (cle !== avant.cle) setEtat(suivant)
  }, [])
  useEffect(() => {
    const minuterie = window.setInterval(() => { if (!document.hidden) relire() }, intervalle)
    return () => window.clearInterval(minuterie)
  }, [relire, intervalle])
  return [etat, relire]
}

/**
 * L'écriture de la pente d'UN pan par la primitive de section (`layout/section/`, clé `zones`) —
 * la MÊME requête pour « Enregistrer la pente » (onglet Pente, `SaisiePente.jsx`) et « Confirmer » (carte « Pente et
 * orientation » de l'étape Toit, maquette Main). Le document lu (`doc`) et l'atelier vivant
 * reprennent les pans rendus. Rend `{ ok, message }` (motif serveur d'abord, ACAL280).
 */
export async function enregistrerPentePan({ calepinageId, doc, documentVivant = null, zone, zones, champs }) {
  // ACAL316 — le jeton de l'atelier vivant s'il existe, sinon celui de la lecture : un
  // document changé ailleurs répond 409 plutôt que d'être écrasé.
  const base = documentVivant?.empreinte || doc.empreinte
  try {
    const res = await calepinageApi.calepinages.enregistrerSectionLayout(calepinageId, {
      cle: 'zones', zone_id: zone.id, champs, base_empreinte: base,
    })
    const apres = res?.data?.empreinte_document ?? null
    const rendues = res?.data?.roof_layout?.zones
    const mises = Array.isArray(rendues) ? rendues : zones.map((z) => (
      String(z.id) === String(zone.id) ? { ...z, ...champs } : z))
    doc.appliquerSection('zones', mises, apres)
    documentVivant?.appliquerSection?.('zones', mises, apres)
    return { ok: true, message: `Pente enregistrée sur le pan « ${zone.label || zone.id} ».` }
  } catch (e) {
    // Lot 2 critique #32 — jeton périmé (relu) ≠ verrou (motif serveur).
    const conflit = lireConflit(e)
    if (conflit?.documentModifie) {
      doc.recharger()
      return { ok: false, message: 'La conception a changé ailleurs : elle est relue, recommencez.' }
    }
    // ACAL280 — le motif serveur (400 : son champ) avant tout repli.
    return { ok: false, message: conflit ? conflit.motif : messageRefus(e, 'La pente n’a pas pu être enregistrée.') }
  }
}
