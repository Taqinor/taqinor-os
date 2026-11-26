// ENF22 — helpers extraits de SchemaUnifilairePanel.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.
import { telechargerBlob } from './exportImage'
import { motifDuRefusBlob } from './motifRefusBlob'
import { svgTexteEnPng } from './documents/deposerImage'
import { formatNumber } from '../../lib/format'
import { chainesServies, texteOnduleur } from './electrique/resumeRaccordement'

/* ============================================================================
   CAL195 — LE SCHÉMA UNIFILAIRE, DANS LE MODULE.
   ----------------------------------------------------------------------------
   Le schéma existait déjà — mais seulement à l'intérieur du PDF de devis. Un
   calepinage sans devis n'en avait aucun, et personne ne pouvait le regarder
   avant d'avoir chiffré.

   CE PANNEAU NE DESSINE RIEN. Le SVG est composé PAR LE SERVEUR (le MÊME
   moteur `core.electrique` que le devis, à travers la porte
   `apps.ventes.selectors.schema_unifilaire_svg`) : deux surfaces ne peuvent
   donc pas montrer deux schémas qui se contredisent. L'écran l'insère tel
   quel et n'ajoute pas un trait.

   FICHE INCOMPLÈTE ⇒ PAS DE SCHÉMA, et on le DIT. `svg: null` n'est jamais
   affiché comme un cadre vide : les libellés français du serveur
   (`manquantes`, `bloquants`) sont rendus TELS QUELS — l'écran ne reformule
   aucun motif et n'en invente aucun. Même discipline que PVFCH-ANNEXE côté
   devis : un schéma d'aspect officiel bâti sur des caractéristiques devinées
   est un défaut invisible.

   CALX236 — EXPORTER LE SCHÉMA, DEPUIS LE NAVIGATEUR, JAMAIS DEPUIS LE
   SERVEUR (D1 : aucun rastériseur SVG côté serveur). Le SVG est DÉJÀ dans le
   DOM (inséré ci-dessus) : l'export PNG le sérialise dans un canvas hors
   écran (même patron que `features/ged/capture.js`) et télécharge l'image —
   AUCUN second appel à `schemaUnifilaire()`, aucune route neuve. Le lien SVG
   télécharge le TEXTE déjà reçu, tel quel. Les deux boutons n'existent QUE
   quand `balisage` est vrai (`svg` non nul) : un schéma absent n'a rien à
   exporter.

   CALX235/236 — LE TROISIÈME BOUTON : LE DXF. La route existe désormais
   (`views/schema.py`, `url_path='schema-unifilaire.dxf'`, service
   `services/sld_export.py::exporter_sld_dxf`) et
   `calepinageApi.calepinages.sldDxf(id)` a été ajoutée EN FIN de
   `calepinageApi.js` (`// CALX235`). Contrairement au PNG et au SVG, le DXF
   n'est PAS dans le DOM : il est produit par le serveur depuis le MÊME
   dessin (blocs, positions éditées, liaisons), donc un appel réseau est ici
   la seule façon de l'obtenir — et c'est le SEUL de ce panneau. Une
   conception incomplète ou bloquée ne produit aucun fichier : le serveur
   refuse en 400 en nommant le champ, et ce motif-là est affiché tel quel.
   ========================================================================== */

/** Le nom du fichier exporté : porte la RÉFÉRENCE du calepinage servie par
    CETTE réponse (`data.calepinage`, le seul identifiant que ce contrat
    publie — aucun titre n'y est servi, donc aucun titre n'est inventé ici). */
export function nomFichierSchema(referenceCalepinage, extension) {
  const base = referenceCalepinage === null || referenceCalepinage === undefined
    ? 'calepinage'
    : `calepinage-${referenceCalepinage}`
  return `${base}-schema-unifilaire.${extension}`
}

/**
 * Sérialise le SVG (déjà reçu, déjà affiché) dans un canvas hors écran et
 * télécharge le PNG obtenu. Aucun appel réseau : Blob/URL.createObjectURL
 * sont locaux au navigateur. Un échec de rastérisation (navigateur trop
 * ancien, contexte 2D indisponible) revient en REJET avec un motif
 * affichable — jamais une exception qui casserait l'écran.
 */
export function exporterSchemaPng(svgTexte, nomFichier, { telecharger = telechargerBlob } = {}) {
  // Le rastériseur est UN seul exemplaire (documents/deposerImage.js) : ici on
  // télécharge le Blob obtenu au lieu de l'envoyer au serveur.
  return svgTexteEnPng(svgTexte).then((blobPng) => {
    telecharger(blobPng, nomFichier)
    return { ok: true, nom: nomFichier }
  })
}

/** Télécharge le SVG texte tel quel — aucune conversion, aucun appel réseau. */
export function exporterSchemaSvg(svgTexte, nomFichier, { telecharger = telechargerBlob } = {}) {
  telecharger(new Blob([svgTexte], { type: 'image/svg+xml;charset=utf-8' }), nomFichier)
}

/**
 * CALX235 — le MOTIF d'un refus de DXF, lu sur la réponse du serveur.
 *
 * La réponse est demandée en `blob` : un refus 400 arrive donc lui aussi en
 * Blob, et son JSON (`{champ: motif}`) doit être relu pour qu'on affiche la
 * phrase du serveur — jamais une phrase reformulée ici. Un corps illisible
 * (panne réseau, HTML d'un proxy) rend un motif générique qui DIT qu'il est
 * générique, plutôt qu'un motif métier inventé.
 */
export async function motifDuRefusDxf(erreur) {
  return motifDuRefusBlob(erreur, 'Le DXF n’a pas pu être produit par le serveur.')
}

/**
 * ACAL161 — l'ÉDITEUR du schéma : renommer le libellé ou le repère d'un bloc DESSINÉ. L'écran
 * ne crée ni ne supprime aucun organe et ne change aucune grandeur : il poste
 * `{libelles: {clef: texte}, reperes: {clef: texte}}` (les rubriques MODIFIÉES seulement ; un
 * champ vidé vaut `null`, qui efface l'édition de cette rubrique). Le refus du serveur
 * (`edition.libelles.<clef>`, `edition.reperes.<clef>`) se pose SOUS le champ nommé, mot pour mot.
 */
export function corpsEdition(blocs, saisie) {
  const corps = {}
  for (const [rubrique, cle] of [['libelles', 'titre'], ['reperes', 'repere']]) {
    for (const bloc of blocs) {
      const v = saisie[rubrique]?.[bloc.clef]
      if (v === undefined || v === (bloc[cle] ?? '')) continue
      corps[rubrique] = { ...(corps[rubrique] ?? {}), [bloc.clef]: v.trim() === '' ? null : v }
    }
  }
  return corps
}

/* ============================================================================
   ACAL1301 — LA LÉGENDE ET LE CARTOUCHE DU SOUS-ÉCRAN « SCHÉMA » (maquette `Schema.dc.html`).
   La légende ne nomme QUE les signes que le SVG SERVI dessine (`core/electrique/schema.py` : liaisons
   pleines fléchées, liaison de terre en pointillé, sections « mm² » du tableau) ; le cartouche ne
   montre QUE les champs servis par le détail du calepinage (un champ absent : sa ligne est omise).
   ========================================================================== */

/** `[{cle, trait, libelle}]` — `trait` ∈ 'plein' | 'pointille' | 'mm2'. Aucun SVG ⇒ aucune ligne. */
export function lignesLegende(svg) {
  if (typeof svg !== 'string' || !svg) return []
  const lignes = []
  if (/<line\b(?![^>]*stroke-dasharray)[^>]*>/.test(svg)) {
    lignes.push({ cle: 'liaison', trait: 'plein', libelle: 'Liaison entre deux organes' })
  }
  if (/stroke-dasharray/.test(svg)) lignes.push({ cle: 'terre', trait: 'pointille', libelle: 'Liaison à la terre' })
  if (/mm²/.test(svg)) lignes.push({ cle: 'section', trait: 'mm2', libelle: 'Section du câble, puis sa longueur' })
  return lignes
}

/* ============================================================================
   F3 (maquette `Schema.dc.html`, tour 2) — LE SCHÉMA EN BLOCS, À TAILLE LISIBLE.
   Le dessin de la maquette (bandes « courant continu / courant alternatif », chaînes colorées,
   coffrets, onduleur, compteur, réseau, terre) est composé ICI à partir de données SERVIES :
   `schema-unifilaire/` (`blocs[]` : les organes que le serveur RETIENT, avec titre / sous-titre /
   repère ; `edition.libelles` ; le SVG pour savoir s'il trace une terre) et `resultat/`
   (`electrique.affectation` : chaînes, couleur, entrée MPPT ; `electrique.onduleurs[0]` ;
   `electrique.chainage.puissance_module_wc` ; `troncons` : sections et longueurs). Un organe non
   servi n'est PAS dessiné ; une section n'est écrite que si TOUS les tronçons du côté la partagent ;
   une longueur seulement si le côté n'a qu'UN tronçon (aucune attribution devinée). Coordonnées en
   pixels CSS (échelle 1 : un texte de 12 px reste à 12 px) — géométrie de la maquette, resserrée
   pour tenir dans la planche de 1440 × 900 (~880 px utiles).
   ========================================================================== */

const chiffre = (v, d = 0) => formatNumber(v, { decimals: d, locale: 'fr' })
const fini = (v) => typeof v === 'number' && Number.isFinite(v)
// ACAL1551 — `organe_dc` (`organe_dc#2`…) : un organe côté continu retenu hors chaîne canonique (la coupure
// d'urgence DC exigée par le dossier) ; son nom est le titre SERVI (sa désignation).
const DC_ORGANES = ['fusibles', 'parafoudre_dc', 'sectionneur_dc', 'organe_dc']
const AC_ORGANES = ['disjoncteur_ac', 'parafoudre_ac', 'ddr']
/* Nom court de l'organe dans son coffret + ce qu'il fait (aucun chiffre). La 2e ligne est le
   calibre SERVI (`sous_titre`) quand il existe ; sinon cette phrase. */
const ORGANES = {
  fusibles: { nom: 'Fusibles', role: 'protègent chaque chaîne', picto: 'fusible' },
  parafoudre_dc: { nom: 'Parafoudre', role: 'protège de la foudre', picto: 'parafoudre' },
  sectionneur_dc: { nom: 'Sectionneur', role: 'coupe les panneaux', picto: 'sectionneur' },
  organe_dc: { nom: null, role: 'décision société', picto: 'sectionneur' },
  disjoncteur_ac: { nom: 'Disjoncteur', role: 'calibre : note de calcul', picto: 'disjoncteur' },
  parafoudre_ac: { nom: 'Parafoudre', role: 'protège de la foudre', picto: 'parafoudre' },
  ddr: { nom: 'Différentiel', role: 'protège les personnes', picto: 'disjoncteur' },
}
/* Ce qu'ouvre un clic sur un élément : la section de l'étape Électrique où SA valeur se règle. */
export const CIBLE_DU_BLOC = {
  chaine: 'controle-chaine',
  coffret: 'equipements-electriques',
  onduleur: 'materiel-electrique',
  reseau: 'raccordement',
  cable: 'cheminement-cables',
  batterie: 'materiel-electrique',
}

/** S2 (tablette) — l'échelle de DÉPART du schéma en blocs : tout le dessin tient dans la largeur du cadre (jamais
    coupé), sans jamais agrandir au-delà de 1 ; sans mesure exploitable (cadre pas encore mesuré), 1. */
export function echelleAjustee(largeurCadre, largeurDessin) {
  const cadre = Number(largeurCadre)
  const dessin = Number(largeurDessin)
  if (!Number.isFinite(cadre) || !Number.isFinite(dessin) || cadre <= 0 || dessin <= 0) return 1
  return Math.min(1, Math.floor((cadre / dessin) * 1000) / 1000)
}

/** Coupe un texte en lignes d'au plus `max` caractères (mots entiers), `n` lignes au plus (… au bout). */
export function couperTexte(texte, max, n = 2) {
  const mots = String(texte ?? '').trim().split(/\s+/).filter(Boolean)
  const lignes = []
  for (const mot of mots) {
    const derniere = lignes[lignes.length - 1]
    if (derniere !== undefined && `${derniere} ${mot}`.length <= max) lignes[lignes.length - 1] = `${derniere} ${mot}`
    else lignes.push(mot)
  }
  if (lignes.length <= n) return lignes
  const gardees = lignes.slice(0, n)
  gardees[n - 1] = `${gardees[n - 1].slice(0, Math.max(1, max - 1))}…`
  return gardees
}

/** Site déclaré hors réseau : `resultat.hors_reseau` est un bloc chiffré (sans `motif_absence`, que le serveur
    pose quand le site n'est pas déclaré hors réseau — alors `null` tant qu'aucune simulation n'a eu lieu). */
export function estHorsReseau(resultat) {
  const h = resultat?.hors_reseau
  return Boolean(h) && typeof h === 'object' && !h.motif_absence
}

/** La phrase du côté réseau en creux : ce qui le dimensionne (la simulation, sinon la norme choisie). */
export function phraseCoteReseau(resultat) {
  return resultat?.simule === true
    ? 'Choisissez la norme électrique dans les réglages pour dimensionner le côté réseau'
    : 'Lancez la simulation pour dimensionner le côté réseau'
}

/** La section commune à TOUS les tronçons d'un côté (`dc` | `ac`), sinon `null`. */
function sectionDuCote(troncons, cote) {
  const duCote = troncons.filter((t) => t?.cote === cote)
  if (!duCote.length || !duCote.every((t) => fini(t.section_mm2))) return null
  const sections = new Set(duCote.map((t) => t.section_mm2))
  return sections.size === 1 ? duCote[0].section_mm2 : null
}

const familleDe = (clef) => String(clef ?? '').split('#')[0]

function organesDe(blocs, clefs, libelles) {
  return clefs.flatMap((clef) => blocs.filter((b) => familleDe(b.clef) === clef)).map((b) => {
    const organe = ORGANES[familleDe(b.clef)]
    return {
      clef: b.clef,
      nom: libelles[b.clef] || !organe.nom ? b.titre : organe.nom,
      detail: String(b.sous_titre ?? '').trim() || organe.role,
      picto: organe.picto,
    }
  })
}

/**
 * Le modèle du schéma en blocs, ou `null` quand rien de servi ne permet de le dessiner (aucune
 * chaîne ni onduleur) — l'écran montre alors le schéma détaillé du serveur.
 */
export function planSchemaEnBlocs(schema, resultat) {
  const blocs = Array.isArray(schema?.blocs) ? schema.blocs : []
  const libelles = schema?.edition?.libelles ?? {}
  const blocOnduleur = blocs.find((b) => b.clef === 'onduleur') ?? null
  const chaines = chainesServies(resultat)
  if (!blocOnduleur || !chaines.length) return null
  const troncons = Array.isArray(resultat?.troncons?.troncons) ? resultat.troncons.troncons : []
  const secDc = sectionDuCote(troncons, 'dc')
  const secAc = sectionDuCote(troncons, 'ac')
  const ac = troncons.filter((t) => t?.cote === 'ac')
  const longueurAc = ac.length === 1 && fini(ac[0].longueur_m) ? ac[0].longueur_m : null
  const wc = resultat?.electrique?.chainage?.puissance_module_wc
  const ond = resultat?.electrique?.onduleurs?.[0] ?? null

  // ── Côté courant alternatif, de l'onduleur vers le réseau (de droite à gauche).
  const organesAc = organesDe(blocs, AC_ORGANES, libelles)
  const trouve = (clef) => blocs.find((b) => b.clef === clef) ?? null
  const chaineAc = []
  if (organesAc.length) chaineAc.push({ cle: 'coffret_ac', l: 196, h: Math.max(212, 42 + organesAc.length * 66), dy: 32, ecart: 72 })
  const compteur = trouve('compteur_production')
  if (compteur) chaineAc.push({ cle: 'compteur', l: 104, h: 98, ecart: 40, titre: couperTexte(compteur.titre, 12) })
  const tgbt = trouve('tgbt')
  if (tgbt) chaineAc.push({ cle: 'tgbt', l: 64, h: 64, ecart: 32, titre: couperTexte(tgbt.titre, 8) })
  const reseau = trouve('reseau')
  if (reseau) chaineAc.push({ cle: 'reseau', l: 140, h: 130, ecart: 32, titre: ['Réseau du', 'distributeur'], detail: couperTexte(reseau.titre, 18, 1) })
  /* Côté réseau PAS ENCORE SERVI (pas de simulation, pas de norme choisie) : l'installation raccordée au réseau
     a pourtant un coffret, un compteur et le réseau. Ils sont dessinés EN CREUX (`aCalculer`) — ni calibre ni
     section ni appareil inventés — et sont remplacés par les blocs servis dès que le serveur les sert.
     Un site déclaré hors réseau n'en a pas : rien n'est dessiné. */
  const aCalculer = chaineAc.length === 0 && !estHorsReseau(resultat)
  if (aCalculer) {
    chaineAc.push({ cle: 'coffret_ac', aCalculer: true, l: 196, h: 212, dy: 32, ecart: 72, titre: ['Coffret côté réseau'] })
    chaineAc.push({ cle: 'compteur', aCalculer: true, l: 104, h: 98, ecart: 40, titre: ['Compteur'] })
    chaineAc.push({ cle: 'reseau', aCalculer: true, l: 140, h: 130, ecart: 32, titre: ['Réseau du', 'distributeur'] })
  }
  const largeurAc = 16 + chaineAc.reduce((s, b) => s + b.l + b.ecart, 0)
  const ox = Math.max(696, largeurAc)
  const largeur = ox + 160 + 16

  // ── Côté courant continu : chaînes, coffret, entrées de l'onduleur.
  const organesDc = organesDe(blocs, DC_ORGANES, libelles)
  const avecCoffretDc = organesDc.length > 0 || Boolean(trouve('coffret_dc'))
  // Au-delà de deux chaînes, rangées compactes (maquette : 2 chaînes) pour tenir dans la planche.
  const compact = chaines.length > 2
  const RANG = compact ? 76 : 126
  const rangees = chaines.map((c, i) => {
    const y = 36 + i * RANG
    const gap = c.nombre > 8 ? 3 : 6
    const lg = Math.min(28, (198 - gap * (c.nombre - 1)) / c.nombre)
    return {
      ...c,
      x: 16,
      y,
      h: compact ? 72 : 112,
      ligne: y + (compact ? 42 : 55),
      hGlyphe: compact ? 24 : 40,
      yDetail: compact ? 68 : 96,
      libelle: `Chaîne ${c.chaine} · ${c.nombre} panneau${c.nombre > 1 ? 'x' : ''}`,
      legende: c.mppt == null ? `Chaîne ${c.chaine}` : `Chaîne ${c.chaine} · entrée ${c.mppt}`,
      detail: fini(wc) ? `${c.nombre} × ${chiffre(wc)} Wc` : null,
      glyphes: { n: c.nombre, l: lg, gap },
    }
  })
  const entrees = rangees.map((r, k) => 179 + k * (compact ? 36 : 50))
  const basRangees = rangees[rangees.length - 1].ligne
  const coffretDc = avecCoffretDc
    ? {
      x: 302, y: 44, l: 196, h: Math.max(212, 42 + organesDc.length * 66, basRangees + 16 - 44, entrees[entrees.length - 1] + 16 - 44),
      organes: organesDc,
      // Sans organe de protection servi, la boîte dit ce que le serveur en publie (« 2 chaîne(s) raccordée(s) »).
      detail: organesDc.length ? null : couperTexte(trouve('coffret_dc')?.sous_titre, 22, 2),
    }
    : null
  const hDc = Math.max(300, 36 + rangees.length * RANG, coffretDc ? coffretDc.y + coffretDc.h + 28 : 0)
  const yAc = hDc + (compact ? 24 : 40)
  const lienAc = yAc + 123
  const onduleur = {
    x: ox, y: 148, l: 160, h: yAc + 152 - 148,
    puissance: texteOnduleur(resultat),
    // Sans désignation servie, le serveur titre le bloc « Onduleur » : pas deux fois le même mot.
    designation: /^onduleur$/i.test(String(blocOnduleur.titre ?? '').trim()) ? [] : couperTexte(blocOnduleur.titre, 22, 3),
    entrees: ond && fini(ond.n_mppt) && ond.n_mppt > 0
      ? `${ond.n_mppt} entrée${ond.n_mppt > 1 ? 's' : ''} : ${ond.n_mppt === 1 ? '1' : ond.n_mppt === 2 ? '1 et 2' : `1 à ${ond.n_mppt}`}`
      : null,
  }

  // Liaisons : une par chaîne (sa couleur servie), puis le côté alternatif (trait plein).
  const liaisons = []
  rangees.forEach((r, k) => {
    const entree = entrees[k]
    const etiquetteEntree = [r.mppt == null ? null : `entrée ${r.mppt}`, secDc == null ? null : `${chiffre(secDc, Number.isInteger(secDc) ? 0 : 1)} mm²`].filter(Boolean).join(' · ')
    if (coffretDc) {
      liaisons.push({ cle: `c${r.chaine}-a`, couleur: r.couleur, points: [[230, r.ligne], [coffretDc.x, r.ligne]],
        etiquette: secDc == null ? null : { x: 236, y: r.ligne - 10, lignes: [`${chiffre(secDc, Number.isInteger(secDc) ? 0 : 1)} mm²`] } })
      liaisons.push({ cle: `c${r.chaine}-b`, couleur: r.couleur, points: [[coffretDc.x + coffretDc.l, entree], [ox, entree]],
        etiquette: etiquetteEntree ? { x: coffretDc.x + coffretDc.l + 24, y: entree - 10, lignes: [etiquetteEntree] } : null })
    } else {
      const xm = 260 + k * 12
      liaisons.push({ cle: `c${r.chaine}`, couleur: r.couleur, points: [[230, r.ligne], [xm, r.ligne], [xm, entree], [ox, entree]],
        etiquette: etiquetteEntree ? { x: xm + 24, y: entree - 10, lignes: [etiquetteEntree] } : null })
    }
  })
  let curseur = ox
  const blocsAc = chaineAc.map((b, i) => {
    const x = curseur - b.ecart - b.l
    const bloc = { ...b, x, y: b.dy != null ? yAc + b.dy : lienAc - b.h / 2 }
    const ac1 = i === 0 && !b.aCalculer
    const lignes = ac1 ? [secAc == null ? null : `${chiffre(secAc, Number.isInteger(secAc) ? 0 : 1)} mm²`, longueurAc == null ? null : `${chiffre(longueurAc)} m`].filter(Boolean) : []
    liaisons.push({ cle: `ac${i}`, couleur: null, aCalculer: Boolean(b.aCalculer), points: [[x + b.l, lienAc], [curseur, lienAc]],
      etiquette: lignes.length ? { x: x + b.l + 6, y: lienAc - 10 - (lignes.length - 1) * 16, lignes } : null })
    curseur = x
    return bloc
  })
  if (organesAc.length) blocsAc[0].organes = organesAc

  // Terre : seulement quand le schéma SERVI en trace une (liaison en pointillé du SVG du serveur).
  const coffrets = [coffretDc, blocsAc.find((b) => b.cle === 'coffret_ac' && !b.aCalculer)].filter(Boolean)
  const terre = /stroke-dasharray/.test(String(schema?.svg ?? ''))
    ? {
      y: yAc + 267,
      x1: 82,
      descentes: [...coffrets.map((c) => [c.x + c.l / 2, c.y + c.h]), [ox + 80, onduleur.y + onduleur.h]],
      libelle: `Terre : ${[coffrets.length ? (coffrets.length > 1 ? 'coffrets' : 'coffret') : null, 'onduleur'].filter(Boolean).join(', ')} et structure`,
    }
    : null

  const etiquettes = liaisons.some((l) => l.etiquette?.lignes.some((t) => t.includes('mm²')))
  const legende = [
    ...rangees.map((r) => ({ cle: `chaine-${r.chaine}`, trait: 'chaine', couleur: r.couleur, libelle: r.legende })),
    ...(blocsAc.some((b) => !b.aCalculer) ? [{ cle: 'ac', trait: 'plein', libelle: 'Côté réseau (courant alternatif)' }] : []),
    ...(terre ? [{ cle: 'terre', trait: 'pointille', libelle: 'Liaison à la terre' }] : []),
    ...(etiquettes ? [{ cle: 'section', trait: 'mm2', libelle: 'Section du câble, puis sa longueur' }] : []),
  ]
  return {
    largeur,
    hauteur: yAc + 300,
    bandes: [
      { cle: 'dc', y: 0, h: hDc, libelle: 'Côté panneaux · courant continu' },
      { cle: 'ac', y: yAc, h: 300, libelle: 'Côté réseau · courant alternatif' },
    ],
    chaines: rangees,
    coffretDc,
    onduleur,
    blocsAc,
    liaisons,
    terre,
    legende,
    coteReseauACalculer: aCalculer,
  }
}

/* ============================================================================
   LOT 6 (fondateur, 26/11/2026) — LE MÊME DESSIN, LU SUR LE DOCUMENT `schema_electrique`.
   Le serveur sert désormais UN document structuré (contrat `ventes/schema_electrique.json`, clé
   `schema_electrique`) : chaînes (couleur, entrée), organes, onduleurs, BATTERIE, côté réseau.
   `planDepuisDocument` le traduit vers les entrées que `planSchemaEnBlocs` sait déjà dessiner
   (UNE seule géométrie, aucune copie) puis ajoute la carte batterie. Une grandeur `null` est omise.
   ========================================================================== */

const nombreFr = (v) => String(Math.round(v * 100) / 100).replace('.', ',')
const bloc = (clef, titre, sous_titre = '') => ({ clef, titre, sous_titre: sous_titre ?? '', repere: '' })

/** Les blocs « servis » que `planSchemaEnBlocs` lit, tirés du document. */
function blocsDuDocument(doc) {
  const organes = (c) => (c?.organes ?? []).map((o) => bloc(o.clef, o.titre, o.calibre))
  const simple = (clef, b) => (b ? [bloc(clef, b.titre, b.detail)] : [])
  // Un onduleur n'est dessiné que si le document en sert au moins un (rien d'inventé).
  return [
    ...(doc.onduleurs?.length ? [bloc('onduleur', doc.onduleurs[0].designation ?? 'Onduleur')] : []),
    ...organes(doc.coffret_dc),
    ...organes(doc.coffret_ac),
    ...simple('compteur_production', doc.compteur_production),
    ...simple('tgbt', doc.tgbt),
    ...simple('reseau', doc.reseau),
  ]
}

const avecChaines = (doc) => Boolean(doc.chaines_reparties) && doc.chaines.length > 0

/** Les chaînes du document (ou, SANS découpage servi, UN champ de panneaux au nombre réel). */
function affectationDuDocument(doc) {
  if (avecChaines(doc)) {
    return doc.chaines.flatMap((c) => Array.from({ length: c.nb_panneaux ?? 0 }, () => (
      { chaine: c.numero, mppt: c.entree, couleur_chaine: c.couleur })))
  }
  return Array.from({ length: doc.panneaux?.nombre ?? 0 }, () => ({ chaine: 1, mppt: null, couleur_chaine: null }))
}

/** Le document traduit vers les deux réponses (`schema-unifilaire/`, `resultat/`) que lit `planSchemaEnBlocs`. */
function entreesDuDocument(doc, libelles) {
  const o = doc.onduleurs?.[0] ?? null
  // Libellé ÉDITÉ (`edition.libelles`, servi avec le dessin) : il l'emporte sur le titre du document.
  const blocs = blocsDuDocument(doc).map((b) => (libelles[b.clef] ? { ...b, titre: libelles[b.clef] } : b))
  return {
    // `svg` ne sert à `planSchemaEnBlocs` qu'à savoir si une terre est tracée.
    schema: { blocs, edition: { libelles }, svg: doc.terre ? '<line stroke-dasharray="1"/>' : '' },
    resultat: {
      electrique: {
        affectation: affectationDuDocument(doc),
        onduleurs: o ? [{ taille_kw: o.puissance_kw, nombre: o.nombre, n_mppt: o.nb_entrees }] : [],
        chainage: { puissance_module_wc: doc.panneaux?.module?.puissance_wc },
      },
      troncons: {
        troncons: ['dc', 'ac'].map((cote) => ({
          cote, section_mm2: doc.liaisons?.[cote]?.section_mm2, longueur_m: doc.liaisons?.[cote]?.longueur_m,
        })),
      },
      hors_reseau: doc.cote_reseau?.etat === 'hors_reseau' ? { banque: null } : null,
      simule: false,
    },
  }
}

/** La carte batterie (bande courant continu, à gauche de l'onduleur) et sa liaison neutre à double flèche. */
function carteBatterie(batterie, onduleur) {
  const lignes = [
    ...couperTexte(batterie.designation, 20, 2),
    ...(fini(batterie.unites) ? [`${batterie.unites} unité${batterie.unites > 1 ? 's' : ''}`] : []),
    ...(fini(batterie.capacite_kwh) ? [`${nombreFr(batterie.capacite_kwh)} kWh au total`] : []),
    ...(fini(batterie.tension_v) ? [`${nombreFr(batterie.tension_v)} V`] : []),
  ]
  const l = 150
  const x = onduleur.x - 24 - l
  const y = 34
  const cx = onduleur.x + onduleur.l / 2
  return { x, y, l, h: 44 + lignes.length * 16, lignes, lien: [[x + l, y + 40], [cx, y + 40], [cx, onduleur.y]] }
}

/** L'étage moyenne tension (`etage_mt`), inséré dans la chaîne alternative : onduleur → coffret → [blocs MT] →
    compteur → TGBT → réseau. Chaque bloc porte « à confirmer » (le contrat les dit tous à confirmer). Le
    côté onduleur (onduleur, batterie, entrées des chaînes, terre) glisse vers la droite de la largeur ajoutée ;
    les blocs côté réseau ne bougent pas. Les liaisons alternatives sont retracées. */
function insererEtageMt(plan, etage) {
  if (!etage.length) return
  const { onduleur, blocsAc } = plan
  const k = blocsAc[0]?.cle === 'coffret_ac' ? 1 : 0
  const lienY = plan.bandes[1].y + 123
  const neufs = etage.map((b) => ({
    cle: `mt-${b.clef}`, aConfirmer: true, l: 128, h: 128, ecart: 32, y: lienY - 64,
    titre: couperTexte(b.titre, 14, 2), detail: couperTexte(b.detail, 16, 2),
  }))
  const w = neufs.reduce((s, b) => s + b.l + b.ecart, 0)
  const ancienOx = onduleur.x
  const centreCoffret = k ? blocsAc[0].x + blocsAc[0].l / 2 : null
  const etiquette = plan.liaisons.find((l) => l.cle === 'ac0')?.etiquette ?? null
  onduleur.x += w
  if (plan.batterie) { plan.batterie.x += w; plan.batterie.lien.forEach((p) => { p[0] += w }) }
  plan.liaisons.forEach((l) => { if (l.couleur) l.points.forEach((p) => { if (p[0] === ancienOx) p[0] += w }) })
  blocsAc.slice(0, k).forEach((b) => { b.x += w })
  let curseur = k ? blocsAc[0].x : onduleur.x
  neufs.forEach((b) => { b.x = curseur - b.ecart - b.l; curseur = b.x })
  blocsAc.splice(k, 0, ...neufs)
  plan.liaisons = plan.liaisons.filter((l) => !/^ac\d+$/.test(l.cle))
  let depart = onduleur.x
  blocsAc.forEach((b, i) => {
    plan.liaisons.push({ cle: `ac${i}`, couleur: null, aCalculer: Boolean(b.aCalculer),
      points: [[b.x + b.l, lienY], [depart, lienY]],
      etiquette: i === 0 && etiquette && !b.aCalculer ? { ...etiquette, x: b.x + b.l + 6 } : null })
    depart = b.x
  })
  if (plan.terre) plan.terre.descentes = plan.terre.descentes.map(([x, y]) => ((x >= ancienOx || x === centreCoffret) ? [x + w, y] : [x, y]))
  plan.largeur += w
  plan.etageMt = true
}

/** Plusieurs groupes d'onduleurs : la carte les liste TOUS (« N × désignation · X kW »), sans total inventé ni
    puissance / entrées d'un seul groupe attribuées à l'ensemble. */
function listerOnduleurs(plan, groupes) {
  if (groupes.length < 2) return
  const ligne = (g) => [
    [fini(g.nombre) ? `${g.nombre} ×` : null, g.designation].filter(Boolean).join(' '),
    fini(g.puissance_kw) ? `${nombreFr(g.puissance_kw)} kW` : null,
  ].filter(Boolean).join(' · ')
  plan.onduleur.puissance = null
  plan.onduleur.entrees = null
  plan.onduleur.designation = groupes.map(ligne).filter(Boolean).flatMap((t) => couperTexte(t, 22, 3))
}

const TUILES_MAX = 24

/** Au-delà de ~50 panneaux dans une rangée, la largeur d'une tuile devient nulle ou négative : on dessine au plus
    `TUILES_MAX` tuiles ; le NOMBRE écrit (libellé, détail) reste le nombre réel. */
function tuilesBornees(g) {
  if (g.l >= 4) return g
  const n = Math.min(g.n, TUILES_MAX)
  return { n, gap: 3, l: Math.min(28, (198 - 3 * (n - 1)) / n) }
}

/**
 * Le modèle du schéma en blocs lu sur le document `schema_electrique`, ou `null` quand il n'y a ni
 * panneau ni onduleur à dessiner. `plan.batterie` n'existe que si le document porte une batterie.
 */
export function planDepuisDocument(doc, libelles = {}) {
  if (!doc || typeof doc !== 'object' || !Array.isArray(doc.chaines)) return null
  const { schema, resultat } = entreesDuDocument(doc, libelles ?? {})
  const plan = planSchemaEnBlocs(schema, resultat)
  if (!plan) return null
  plan.chaines.forEach((c) => { c.glyphes = tuilesBornees(c.glyphes) })
  listerOnduleurs(plan, doc.onduleurs ?? [])
  if (!avecChaines(doc)) {
    const n = plan.chaines[0].nombre
    plan.chaines[0].libelle = `Champ · ${n} panneau${n > 1 ? 'x' : ''}`
    plan.chaines[0].legende = 'Champ de panneaux'
    plan.legende[0].libelle = 'Champ de panneaux'
  }
  if (doc.batterie) {
    plan.batterie = carteBatterie(doc.batterie, plan.onduleur)
    const i = plan.legende.findIndex((l) => l.cle === 'ac')
    plan.legende.splice(i < 0 ? plan.chaines.length : i, 0, { cle: 'batterie', trait: 'batterie', libelle: 'Liaison batterie' })
  }
  insererEtageMt(plan, doc.etage_mt ?? [])
  return plan
}

const date = (iso) => new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
const heure = (iso) => new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
const lisible = (iso) => typeof iso === 'string' && !Number.isNaN(Date.parse(iso))

/** `[{libelle, valeur}]` : Projet (nom servi + ville servie), Date et Version (dernière version
    enregistrée, empreinte courte du document), Auteur (responsable, sinon créateur) — servis seulement. */
export function lignesCartouche(detail) {
  if (!detail) return []
  // Même nom que le bandeau du projet (`atelier/coque/projet.js::titreProjet` : « Calepinage 5 ») —
  // le détail sert « Calepinage #5 » pour un calepinage sans titre.
  const nom = (String(detail.nom ?? '').trim() || String(detail.reference ?? '').trim()).replace(/^Calepinage #(\d+)\b/, 'Calepinage $1')
  const ville = String(detail.contexte_geographique?.ville ?? detail.lead?.ville ?? detail.client?.ville ?? '').trim()
  const projet = nom && ville && !nom.includes(ville) ? `${nom} — ${ville}` : nom
  const le = lisible(detail.versions?.derniere_le) ? detail.versions.derniere_le
    : (lisible(detail.modifie_le) ? detail.modifie_le : null)
  const empreinte = typeof detail.layout_hash === 'string' && detail.layout_hash ? detail.layout_hash.slice(0, 8) : ''
  // L'empreinte du document est une référence technique : elle ne sert que faute d'heure d'enregistrement.
  const version = lisible(detail.versions?.derniere_le) ? `Enregistrée à ${heure(detail.versions.derniere_le)}` : empreinte
  const auteur = String(detail.responsable?.nom_complet ?? detail.cree_par?.nom_complet ?? '').trim()
  return [
    { libelle: 'Projet', valeur: projet },
    { libelle: 'Date', valeur: le ? date(le) : '' },
    { libelle: 'Version', valeur: version },
    { libelle: 'Auteur', valeur: auteur },
  ].filter((l) => l.valeur)
}
