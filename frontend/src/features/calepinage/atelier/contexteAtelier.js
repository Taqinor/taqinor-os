// SPL213 — mappeurs purs de l'atelier 3D, déplacés VERBATIM depuis
// pages/ventes/ToitureDesign.jsx (move only : seul `export` a été ajouté).
import { refusServeur } from '../commun/refusServeur.js'
import { formatNumber } from '../../../lib/format.js'

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

// ACAL251 — LE repère toit du lead est celui que le SERVEUR calcule et sert
// (`repere_toit` du GET lead, `crm.selectors.repere_toit` : le GPS corrigé
// prime sur l'épingle du tunnel, sinon l'épingle, sinon le GPS). L'écran ne
// re-décide plus rien (l'ancien `pinDepuisLead` faisait primer `roof_point`) ;
// `null` sans repère — jamais une position devinée.
export function repereDuLead(lead) {
  return lead?.repere_toit?.pin ?? null
}

// ACAL251 — le contour client n'ENSEMENCE un pan éditable que si le serveur le
// dit utilisable (le repère tombe dedans) ; sinon il reste un calque L-MAP.
export function contourUtilisableDuLead(lead) {
  return lead?.repere_toit?.contour_utilisable === true
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
  const utilisable = contourUtilisableDuLead(lead)
  return {
    roof_point: repereDuLead(lead),
    roof_outline: utilisable ? (lead.roof_outline ?? null) : null,
    contour_utilisable: utilisable,
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
// ACAL1268 (D-ACAL-66 = outil_pose) — l'atelier d'un lead de POMPAGE : le marché que le serveur sert dans le bloc
// `chiffrage` du design-context (`chiffrage.marche`, lu du lead par ventes). Un outil de pose seulement : ni économies, ni
// kWh de réseau, ni onduleur, ni batterie.
export function estAtelierPompage(contexte) {
  return contexte?.chiffrage?.marche === 'agricole'
}

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

// T4-X8-012 (une cible) — la source de la cible en mots : UNE table pour la carte « Cible — panneaux » (AtelierPanneaux) et la
// note « N posés / T cible (source) » du constructeur (portée par `libelleOrigineCible`). Une valeur inconnue reste telle quelle.
export const LIBELLES_SOURCE_CIBLE = {
  devis: 'Devis lié',
  lead: 'Taille souhaitée sur la fiche du lead',
  factures: 'Factures du lead',
}
export const libelleSourceCible = (source) => LIBELLES_SOURCE_CIBLE[source] ?? source ?? null
// La MÊME source après « d'après » (« Posé d'après les factures du lead : 8 panneaux ») : une seconde forme de chaque mot de la table
// ci-dessus, jamais le libellé de la carte collé derrière la préposition. Une source inconnue n'a pas de seconde forme (`null`).
export const LIBELLES_APRES_SOURCE_CIBLE = {
  devis: 'le devis lié',
  lead: 'la taille souhaitée sur la fiche du lead',
  factures: 'les factures du lead',
}
export const libelleApresSourceCible = (source) => LIBELLES_APRES_SOURCE_CIBLE[source] ?? null

// CAL37 — MODE CALEPINAGE. Jumeau NEUTRE de la projection devis ci-dessus, pour
// le contexte servi par `GET /calepinage/calepinages/<pk>/design-context/`
// (contrat `apps/calepinage/contract_samples/calepinage_design_context.json`).
// Le contexte NOMME le repère `pin` et le contour `outline`, exactement comme
// côté devis : cette projection est le SEUL endroit qui les renomme pour le
// builder.
//
// LA CIBLE N'EST JAMAIS INVENTÉE (décision du contrat, verbatim) : `cible` vaut
// `null` quand le calepinage n'a ni devis lié ni lead — les trois champs restent
// alors nuls, et l'optimiseur travaille librement comme il le fait pour un lead
// sans facture. ACAL195 — une cible ESTIMÉE (`source` 'lead' ou 'factures' : la
// taille que le devis automatique donnerait au lead, ACAL194) est transmise comme
// POINT DE DÉPART modifiable, jamais comme une vente ; un refus du moteur
// (`cible.refus`, panneaux nuls) n'impose rien.
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
    // posé, aucune recommandation, aucune production demandée. ACAL195 — `true`
    // SEULEMENT quand la cible vient d'un DEVIS (`source: 'devis'`) : on retrouve
    // alors EXACTEMENT le comportement du mode devis. Une cible estimée depuis le
    // lead (taille souhaitée ou factures) n'est PAS vendue : ses panneaux
    // plafonnent le remplissage proposé, et le nombre choisi puis enregistré
    // (`neededPanels` du pan) prime à la réouverture.
    cibleVendue: contexte.cible?.source === 'devis',
    // ACAL1331 (D-ACAL-76 « dimensionner ») — d'où vient la cible servie (`devis` | `factures` | `lead`, `null` sans
    // cible) : sur un calepinage VIERGE, l'atelier pose cette taille dès le toit fermé et DIT « Posé d'après … ».
    origineCible: contexte.cible?.source ?? null,
    // T4-X8-012 (une cible) — la même source, dans les mots de la carte « Cible — panneaux » : la note du nombre de panneaux la reprend.
    libelleOrigineCible: contexte.cible?.source ? libelleSourceCible(contexte.cible.source) : null,
    libelleApresOrigineCible: libelleApresSourceCible(contexte.cible?.source),
    // ACAL1951 — le devis lié (sa référence) et l'option que sa cible suit (`sans` | `avec`, `null` pour une cible estimée) :
    // l'atelier les nomme dans la note du nombre de panneaux.
    referenceDevis: contexte.calepinage?.devis_lie?.reference ?? null,
    optionCible: contexte.cible?.option ?? null,
    fullName: titre || undefined,
    // ACAL777 — la facture mensuelle du lead servie (ACAL776) : repli d'AFFICHAGE des cartes ; `null` = rien inventé.
    factureMensuelleMad: contexte.consommation_lead?.facture_mensuelle_mad ?? null,
  }
}

// ACAL195 — le libellé d'une cible ESTIMÉE (source 'lead' | 'factures'), ou le refus
// NOMMÉ du moteur tel que le serveur l'a écrit ; `null` pour une cible vendue (devis)
// ou absente. Jamais imprimé ailleurs que dans l'atelier (aucune sortie client).
// T4-X9-013 — calepinage SANS lead (`sansLead`) : aucune phrase sur une conception (le refus du moteur, servi pour le
// calepinage porteur, demande de remplir « le lead », qui n'existe pas) ; sa production est celle de sa simulation.
export function libelleCibleEstimee(cible, { sansLead = false } = {}) {
  if (!cible || cible.source === 'devis' || sansLead) return null
  if (typeof cible.refus === 'string' && cible.refus) return cible.refus
  const n = Number(cible.panneaux)
  if (!Number.isFinite(n) || n <= 0) return null
  const origine = cible.source === 'lead'
    ? 'la taille souhaitée du lead' : 'les factures du lead'
  return `Cible estimée depuis ${origine} : ${n} panneaux` // ACAL1733 — « estimée » le dit déjà : jamais « (estimation) » en plus
}

// R2-15 / R2-01 (décision Q1, 22/11) — « Le lead déclare : tuiles · pente 25° · sud-ouest · ombrage partiel
// (palmier) » : ce que la fiche du lead dit de sa toiture (`contexte.toiture_lead`, libellés de fiche servis),
// AFFICHÉ en lecture seulement — aucune valeur n'en est préremplie (D-ACAL-7). `null` quand il ne dit rien.
export function phraseToitureLead(toiture) {
  if (!toiture || typeof toiture !== 'object') return null
  const mot = (v) => (typeof v === 'string' && v.trim() ? v.trim().toLocaleLowerCase('fr') : null)
  const nb = (v) => (Number.isFinite(v) ? formatNumber(v, { locale: 'fr' }) : null)
  const avec = (valeur, gabarit) => (valeur == null ? null : gabarit(valeur))
  const notes = typeof toiture.ombrage_notes === 'string' ? toiture.ombrage_notes.trim() : ''
  const ombrage = mot(toiture.ombrage)
  const parties = [
    mot(toiture.type_surface), mot(toiture.type_toiture),
    avec(nb(toiture.surface_toiture_m2), (s) => `${s} m² disponibles`),
    avec(nb(toiture.inclinaison_deg), (p) => `pente ${p}°`), mot(toiture.orientation),
    ombrage ? `ombrage ${ombrage}${notes ? ` (${notes})` : ''}` : (notes ? `ombrage : ${notes}` : null),
    avec(nb(toiture.nb_etages), (n) => `${n} étage${toiture.nb_etages > 1 ? 's' : ''}`),
    avec(nb(toiture.roof_age), (a) => `toiture de ${a} ans`),
    avec(mot(toiture.structure_pref), (s) => `structure ${s}`),
  ].filter(Boolean)
  return parties.length ? `Le lead déclare : ${parties.join(' · ')}` : null
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

// ACAL967 — « Calepinage <titre> chargé » : le mot « Calepinage » n'est ajouté que si le titre ne le porte pas déjà
// (« Calepinage (copie) » ne devient plus « Calepinage Calepinage (copie) »). Sans titre : le numéro.
export function phraseCalepinageCharge(titre, calepinageId, modifiable) {
  const nom = (titre ?? '').trim() || String(calepinageId)
  const sujet = /^calepinage/i.test(nom) ? nom : `Calepinage ${nom}`
  return modifiable
    ? `${sujet} chargé. Ajustez la conception, puis « Enregistrer le calepinage ».`
    : `${sujet} en lecture seule — consultation de la conception.`
}

// ACAL962 — les réglages d'atelier tirés de `GET parametres/` : `pays` = `imagerie.pays` (null si
// rien n'est réglé), jamais un pays supposé ; `null` si la réponse n'est pas un objet.
export function reglagesAtelierDesParametres(p) {
  if (!p || typeof p !== 'object') return null
  // ACAL714 — les 3 réglages d'ombrage société (`{valeur, source, reference}`), `null` si aucun n'est saisi.
  const sim = p.simulation && typeof p.simulation === 'object' ? p.simulation : {}
  const simulation = {
    seuil_acces_retrait: sim.seuil_acces_retrait ?? null,
    ombrage_borne_courant_pct: sim.ombrage_borne_courant_pct ?? null,
    ombrage_borne_importante_pct: sim.ombrage_borne_importante_pct ?? null,
  }
  const pays = typeof p.imagerie?.pays === 'string' && p.imagerie.pays.trim() ? p.imagerie.pays.trim() : null
  return {
    zones_types: p.zones_types ?? null,
    degagements: p.degagements ?? null,
    pays,
    // La clé n'existe QUE s'il y a un vrai réglage d'imagerie (fournisseur, fournisseurs admis, attribution) : sinon le
    // builder reçoit exactement ce qu'il recevait avant (`pays` seul, `useAtelierBoot.js` en fait le contexte).
    ...(imagerieReglee(p.imagerie, pays) ? { imagerie: imagerieReglee(p.imagerie, pays) } : {}),
    simulation: Object.values(simulation).some((v) => v !== null) ? simulation : null,
  }
}

// ACAL1754 — le contexte d'imagerie RÉGLÉ par la société (contrat `site_imagerie.json`) : pays, fournisseur choisi,
// fournisseurs admis (dans son ordre) et mention légale saisie — seulement les clés renseignées ; `null` si rien.
// Avant, seul `pays` passait : l'atelier affichait le premier fournisseur disponible, pas celui de la société.
function imagerieReglee(imagerie, pays) {
  // Sans pays réglé : AUCUN contexte (comportement historique) — un contexte sans `pays` ferait passer le fond de carte
  // au premier fournisseur déclaré (`useAtelierBoot.js::imageryDesReglages`) : l'attribution seule ne le change pas.
  if (pays === null) return null
  const texte = (v) => (typeof v === 'string' && v.trim() ? v.trim() : null)
  const autorises = Array.isArray(imagerie?.fournisseurs_autorises)
    ? imagerie.fournisseurs_autorises.filter((id) => texte(id)) : []
  const autres = Object.entries({
    fournisseur_imagerie: texte(imagerie?.fournisseur_imagerie),
    fournisseurs_autorises: autorises.length ? autorises : null,
    attribution: texte(imagerie?.attribution),
  }).filter(([, v]) => v !== null)
  return autres.length ? { pays, ...Object.fromEntries(autres) } : null
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
  // ACAL945 — `0` : aucune réponse du serveur (jamais « erreur 0 »).
  if (status === 0) return 'Le serveur n’a pas répondu : vérifiez votre connexion puis réessayez.'
  // QJ17 — the backend returns a structured French error for 409 (ENF11, refus d'état) / 422 (composition
  // pre-flight failures). Surface it directly instead of a generic message.
  if (status === 422 || status === 409) {
    const detail = responseData?.detail
    if (detail) return detail
    const errors = responseData?.errors
    if (Array.isArray(errors) && errors.length > 0) return errors[0]
    // ACAL369 — refus à champ nommé ({hors_reseau}…) : UN décodeur, celui du module (ACAL279).
    return refusServeur({ response: { data: responseData } }).message
      || 'Composition invalide — vérifiez le catalogue produits puis réessayez.'
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

// T4-U4-013 — l'état de LOCALISATION du site à l'ouverture de l'atelier (clé `siteLocalise` du
// document, contrat `roof_layout_v2.schema.json`) : la provenance relue ; un document ANCIEN qui
// porte une épingle sans la clé ⇒ `undefined` (le serveur garde sa règle, rien n'est réécrit) ;
// sinon le repère du lead (`source_repere`) ⇒ 'lead' ; sinon `null` = personne ne l'a localisé.
export function siteLocaliseInitial(roofLayout, sourceRepere) {
  const doc = roofLayout && typeof roofLayout === 'object' ? roofLayout : null
  if (doc && Object.prototype.hasOwnProperty.call(doc, 'siteLocalise')) return doc.siteLocalise ?? null
  const pin = doc?.pin
  if (pin && Number.isFinite(pin.lat) && Number.isFinite(pin.lng)) return undefined
  return sourceRepere ? 'lead' : null
}

// T4-U4-013 — la phrase du bandeau quand le site n'est pas localisé : le geste à faire, et ce
// que le calcul fera sans lui. Relecture M1 — ce « sinon » est SERVI (`calepinage.site_de_repli` :
// libellé de la ville de référence ou de la position GPS de la fiche, `null` = refus) : l'écran
// ne redérive jamais la ville (il lisait `client_ville`, vide pour un client sans lead).
export function phraseSiteNonLocalise(siteDeRepli) {
  const v = typeof siteDeRepli === 'string' ? siteDeRepli.trim() : ''
  const sinon = v
    ? `sinon le calcul se fait sur ${v}`
    : 'sinon le calcul est refusé'
  return `Site non localisé — carte au niveau Maroc. Cherchez l’adresse du client puis « Localiser », ou zoomez jusqu’au toit avant de le tracer : ${sinon}.`
}

