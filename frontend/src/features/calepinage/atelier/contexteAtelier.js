// SPL213 — mappeurs purs de l'atelier 3D, déplacés VERBATIM depuis
// pages/ventes/ToitureDesign.jsx (move only : seul `export` a été ajouté).

// Convertit un data URL PNG en Blob (upload multipart de la 3D).
export function dataUrlToBlob(dataUrl) {
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
export function pinDepuisLead(lead) {
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
export function leadToBuilderPayload(lead) {
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

// QJR40 (décision fondateur D8, 29/08/2026 ; jumelle backend = QJR25,
// `electrical_service._option_choisie`) — sur un devis « Les deux »,
// `contexte.cible_avec` (CTX3D, `selectors.contexte_conception_devis`) n'est
// présente QUE quand l'option AVEC (onduleur hybride + batterie) est
// réellement servable — MÊME critère que le schéma unifilaire. La cible 3D
// DOIT alors cibler la MÊME option que le SLD : AVEC. Un devis mono-option
// ne porte JAMAIS `cible_avec` : `cible` reste l'UNIQUE option vendue,
// comportement strictement inchangé. Avant ce correctif, l'écran ne lisait
// QUE `cible` (option SANS par construction de CTX3D) — exactement le bug
// que la docstring de CTX3D dit corriger.
export function cibleActiveDuContexte(contexte) {
  return contexte?.cible_avec ?? contexte?.cible ?? {}
}

// PV20 — MODE DEVIS. Le builder s'hydrate depuis un `DevisPayload` (PV19 :
// `geometrie.roof_layout | roof_point | roof_outline` + `cible.panneaux |
// panel_watt | scenario`). Le contexte serveur (contrat
// `contract_samples/devis_design_context.json`) nomme le repère `pin` et le
// contour `outline` : cette projection est le SEUL endroit qui les renomme —
// l'écran ne devine ni ne complète aucune clé absente. QJR40 : `cible` vient
// de `cibleActiveDuContexte` — AVEC quand ce devis la sert, SANS/mono-option
// sinon (voir le commentaire ci-dessus).
export function contexteToDevisPayload(contexte) {
  if (!contexte) return null
  const geo = contexte.geometrie ?? {}
  const cible = cibleActiveDuContexte(contexte)
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

// CAL37 — MODE CALEPINAGE. Jumeau NEUTRE de la projection devis ci-dessus, pour
// le contexte servi par `GET /calepinage/calepinages/<pk>/design-context/`
// (contrat `apps/calepinage/contract_samples/calepinage_design_context.json`).
// Le contexte NOMME le repère `pin` et le contour `outline`, exactement comme
// côté devis : cette projection est le SEUL endroit qui les renomme pour le
// builder.
//
// LA CIBLE N'EST JAMAIS INVENTÉE (décision du contrat, verbatim) : `cible` vaut
// `null` quand le calepinage n'a ni devis lié ni facture exploitable — les
// trois champs restent alors nuls, et l'optimiseur travaille librement comme il
// le fait pour un lead sans facture. Fabriquer ici une puissance « par défaut »
// ferait dessiner un toit qui ne correspond à aucun devis.
//
// `id: null` — un calepinage N'EST PAS un devis, et rien ici ne prétend le
// contraire. L'hydratation passe par le MÊME emplacement `hydrate.devis` parce
// que c'est, côté builder, le créneau « géométrie déjà dessinée + cible
// éventuellement imposée » — pas un créneau propre au document devis.
export function contexteCalepinageVersPayload(contexte) {
  if (!contexte) return null
  const geo = contexte.geometrie ?? {}
  const cible = contexte.cible ?? {}
  const titre = (contexte.calepinage?.titre ?? '').trim()
  // Un contour VIDE (`[]`, la valeur du contrat quand la source manque) n'est
  // pas un polygone : on ne l'envoie pas au builder, qui n'aurait rien à en
  // faire sinon l'ignorer silencieusement.
  const contour = Array.isArray(geo.outline) && geo.outline.length > 0
    ? geo.outline : null
  return {
    id: null,
    geometrie: {
      roof_layout: geo.roof_layout ?? null,
      roof_point: geo.pin ?? null,
      roof_outline: contour,
    },
    cible: {
      panneaux: cible.panneaux ?? null,
      panel_watt: cible.panel_watt ?? null,
      scenario: cible.scenario || null,
    },
    // CAL37 — LE drapeau qui empêche l'atelier de lire « aucune cible » comme
    // « cible vendue de ZÉRO ». Côté devis, un devis sans ligne panneau EST une
    // vente de zéro panneau et l'optimiseur doit refuser de remplir (L2, incident
    // DEV-202608-0016) ; un calepinage sans devis lié, lui, n'a AUCUNE vente
    // derrière lui — le même silence n'y veut pas dire la même chose. Sans ce
    // drapeau, l'atelier ouvert sur un calepinage restait figé : zéro panneau
    // posé, aucune recommandation, aucune production demandée. `true` dès qu'un
    // devis (ou une facture, CAL147) fournit la cible : on retrouve alors
    // EXACTEMENT le comportement du mode devis.
    cibleVendue: contexte.cible != null,
    fullName: titre || undefined,
  }
}

// ACAL192 (D-ACAL-13) — la phrase FRANÇAISE d'un refus serveur des gestes de repère
// (recentrer-sur-lead / garder-repere) : `detail`, sinon le premier message nommé
// (`{calepinage: ['…verrouillé…']}`, `{repere_lead: '…'}`), jamais rédigée ici au-delà
// d'un repli générique quand le serveur n'a rien dit.
export function messageRefusRepere(data) {
  if (typeof data?.detail === 'string' && data.detail) return data.detail
  if (data && typeof data === 'object') {
    for (const valeur of Object.values(data)) {
      if (typeof valeur === 'string' && valeur) return valeur
      if (Array.isArray(valeur) && typeof valeur[0] === 'string') return valeur[0]
    }
  }
  return 'Le repère du calepinage n’a pas pu être mis à jour — réessayez.'
}

// ACAL192 — « ≈ 780 m » / « ≈ 2,4 km » / « ≈ 219 km » : l'écart SERVI (`geometrie.ecart_m`),
// arrondi pour la lecture ; `null` quand le serveur ne l'a pas mesuré.
export function libelleEcartRepere(metres) {
  if (!Number.isFinite(metres)) return null
  if (metres < 1000) return `≈ ${Math.round(metres)} m`
  const km = metres / 1000
  return km < 10 ? `≈ ${km.toFixed(1).replace('.', ',')} km` : `≈ ${Math.round(km)} km`
}

// PV75 — projette `Devis.etude_params.simulation.pr` (étude bancable PV69/PV74 :
// P50/P90, ratio de performance, cascade des pertes) vers le payload `bankable`
// consommé par la fenêtre de production du builder. Le contexte agrégé
// (`devis_design_context.json`, PACT10) NE PORTE PAS `simulation` — on ne l'y
// ajoute pas depuis cette lane, on le lit sur le devis complet (endpoint déjà
// existant, `DevisSerializer` expose `etude_params` en entier). Aucune étude
// lancée/rangée → `pr` absent → null (fenêtre de production inchangée).
export function bankableFromDevis(devis) {
  const pr = devis?.etude_params?.simulation?.pr
  if (!pr) return null
  return {
    p50_kwh: pr.p50_kwh,
    p90_kwh: pr.p90_kwh,
    performance_ratio: pr.performance_ratio,
    loss_breakdown: pr.loss_breakdown ?? {},
  }
}

// CALX104/CALX403 câblage — les réglages d'atelier PORTÉS PAR LE CONTEXTE agrégé
// (mode DEVIS). Le mode DEVIS tient une garantie testée — « un seul appel : rien
// n'est complété par une requête annexe » — donc `zones_types` et `degagements`
// voyagent DANS `devis_design_context` au lieu d'une seconde porte. `null` quand
// le contexte ne porte AUCUNE des deux (serveur plus ancien) : l'atelier ne
// propose alors aucun gabarit et ne préremplit aucune cote, exactement comme
// avant — rien n'est inventé côté écran.
export function reglagesAtelierDuContexte(contexte) {
  const zonesTypes = contexte?.zones_types
  const degagements = contexte?.degagements
  if (zonesTypes == null && degagements == null) return null
  return { zones_types: zonesTypes ?? null, degagements: degagements ?? null }
}

// CALX107 câblage — la taille du plan de fond, telle que `GET …/plan-importe/`
// la PUBLIE (pixels naturels lus dans l'en-tête du fichier), ou `null`. Aucune
// étendue n'est supposée : sans dimensions, l'atelier refuse de poser le plan
// avec son propre motif plutôt que de l'étaler au hasard (D-CALX 7).
export function tailleImagePlan(plan) {
  const largeur = plan?.largeur
  const hauteur = plan?.hauteur
  if (!Number.isFinite(largeur) || !Number.isFinite(hauteur)) return null
  if (largeur <= 0 || hauteur <= 0) return null
  return { largeur, hauteur }
}

export function httpMessage(status, responseData) {
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

// CALX68 — accès protégé à `localStorage` : absent (rendu hors navigateur) ou
// qui LÈVE (navigation privée à quota nul) ⇒ `null`, jamais une exception qui
// remonte à l'écran. `features/calepinage/brouillon.js` dégrade alors tout en
// silence — aucune erreur, aucun bandeau — exactement le repli demandé.
export function stockageBrouillonLocal() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

// ACAL84 — même accès protégé à `sessionStorage` : la reprise d'un brouillon
// (« Reprendre ») y est mémorisée le temps d'UN rechargement de l'onglet.
export function stockageSessionLocal() {
  try {
    return typeof window !== 'undefined' ? window.sessionStorage : null
  } catch {
    return null
  }
}

// CALX68 — l'heure du brouillon, pour le bandeau (« Reprendre le brouillon du
// <heure> »). Un horodatage illisible n'affiche rien plutôt qu'une heure
// fabriquée.
export function formaterHeureBrouillon(horodatageIso) {
  const t = Date.parse(horodatageIso)
  if (!Number.isFinite(t)) return ''
  return new Date(t).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

