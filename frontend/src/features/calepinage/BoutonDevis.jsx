import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import CarteDevisCree from './CarteDevisCree'
import ApercuMaterielDevis from './commun/ApercuMaterielDevis'
import { Icone } from './atelier/coque/primitives'
import { libelleEtat } from './electrique/etatVerdict'
import calepinageApi from '../../api/calepinageApi'
import { formatMAD, formatNumber } from '../../lib/format'
import { toastWarning } from '../../lib/toast'
import { reviserEtOuvrir } from '../ventes/reviserDevis'
import {
  LIBELLE_CHAMP, MESSAGE_DEROGATION_RESERVEE, MESSAGE_MOTIF_OBLIGATOIRE,
  bloquageElectrique, refusServeur, texteBloquant,
} from './refusDevis'
import usePeutGenererDevis from './usePeutGenererDevis'

/* ============================================================================
   CAL38 — LA SORTIE VERS LE DEVIS d'un calepinage, et elle n'existait nulle
   part.
   ----------------------------------------------------------------------------
   DÉCISION FONDATEUR D3 : un calepinage SANS devis est de première classe. Il
   lui faut donc une sortie EXPLICITE — sans elle, une conception dessinée dans
   le module autonome n'a aucun moyen de devenir un chiffrage, et l'écran est
   une impasse.

   DEUX GESTES, JAMAIS DEUX BOUTONS EN MÊME TEMPS :
   * aucun devis lié  → « Générer le devis » (CAL24, `generer-devis`) ;
   * un devis lié     → « Resynchroniser le devis » (CAL25, `sync-devis`).
   C'est l'état SERVEUR (`calepinage.devis` de l'agrégat de détail) qui tranche,
   jamais une supposition d'écran.

   AUCUN TEXTE DE REFUS N'EST FABRIQUÉ ICI. Le pré-vol de composition (422) et
   le conflit « devis figé » (409 : accepté, refusé, expiré ou remplacé ; un
   devis envoyé se corrige sur place, tracé) portent déjà leur phrase FRANÇAISE,
   écrite par le serveur ventes et propagée MOT POUR MOT par
   `services/devis.py::_refus_devis`. La réécrire côté client, c'est apprendre
   deux règles différentes à l'utilisateur pour un seul comportement. Le seul
   texte que ce fichier écrit lui-même est celui des cas où le serveur n'a RIEN
   dit (panne réseau) — et il le dit.

   L'ERREUR NOMME SON CHAMP (règle fondateur 08/09) : le refus serveur est une
   paire `{champ: message}` ; le bandeau NOMME le champ en français et le
   message s'affiche dessous, tel quel. Jamais un « non enregistré » générique.
   ========================================================================== */

/* Lot 2 critique #23 / #29 — le décodeur des refus (libellés de champ,
   refus électrique 422, refus serveur) est PARTAGÉ avec la route devis
   (`refusDevis.js`) : une seule lecture des refus du pont devis. */
export { MESSAGE_DEROGATION_RESERVEE, MESSAGE_MOTIF_OBLIGATOIRE } from './refusDevis'

/* Le dossier « À compléter » d'un succès : les manquantes, sans rien bloquer.
   ACAL935 — lit `electrique.etat` (ACAL934) ; un serveur qui ne le sert pas
   encore garde la lecture `verdict: 'indetermine'`. */
function manquantesElectriques(data) {
  const electrique = data?.electrique
  const aCompleter = electrique?.etat
    ? electrique.etat === 'a_completer'
    : electrique?.verdict === 'indetermine'
  if (!aCompleter) return []
  return (Array.isArray(electrique.manquantes) ? electrique.manquantes : [])
    .filter((m) => typeof m === 'string' && m.trim()).map((m) => m.trim())
}

/* ACAL935 — le titre du cadre : les mots de `etatVerdict.js`, seule source. */
function titreEtatElectrique(data, manquantes) {
  const electrique = data?.electrique
  const lu = electrique?.etat
    ? libelleEtat(electrique.etat, electrique.points)
    : libelleEtat('a_completer', manquantes.length)
  return lu?.libelle ?? null
}

/* ACAL95 — CE QUE LA GÉNÉRATION ET LA RESYNCHRO N'ONT PAS PU FAIRE se lit à
   l'écran AVANT toute navigation ou rechargement (contrat
   `calepinage_publication.json`) : avertissements et marques manquantes du
   serveur, MOT POUR MOT ; lignes de kit ajoutées ; « Aucun changement ». Sans
   rien à dire, le geste reste celui d'aujourd'hui (navigation / rechargement). */
function messagesDuServeur(data, cles = ['avertissements', 'marques_manquantes']) {
  const messages = []
  for (const cle of cles) {
    for (const m of Array.isArray(data?.[cle]) ? data[cle] : []) {
      if (typeof m === 'string' && m.trim()) messages.push(m.trim())
    }
  }
  return messages
}

function libelleLignesAjoutees(n) {
  const nombre = Number(n) || 0
  if (nombre <= 0) return null
  return nombre === 1 ? '1 ligne ajoutée au devis' : `${nombre} lignes ajoutées au devis`
}

/* ACAL94 — l'écran est ENREGISTRÉ avant « Générer / Resynchroniser » (prop
   `enregistrerAvant`, l'UNIQUE fonction d'enregistrement de l'atelier) : le
   serveur compose sur la conception que l'on VOIT, jamais sur l'ancienne.
   Échec d'enregistrement ⇒ aucun geste serveur, aucun rechargement. « Réviser »
   prévient des retouches non enregistrées (`aDesRetouches`) sans jamais
   refuser (D-QJR5-2). */
export const MESSAGE_ENREGISTREMENT_ECHOUE = 'La conception à l’écran n’a pas pu être '
  + 'enregistrée : rien n’a été envoyé au devis. Corrigez puis réessayez.'
export const MESSAGE_RETOUCHES_NON_ENREGISTREES = 'Retouches non enregistrées : elles ne '
  + 'seront pas reprises dans la V2.'
/** T4-X7-016 — le libellé du geste nomme la version SUIVANTE, jamais « (v2) » sur un devis déjà V2. */
export const LIBELLE_REVISER = 'Réviser (nouvelle version)'
export const MESSAGE_REVISION_ECHOUEE = 'La nouvelle version n’a pas été créée : le devis est inchangé. Réessayez, '
  + 'ou ouvrez le devis depuis la liste des devis.'

// ACAL1414 — les clés des surfaces que le devis lié ne chiffre PAS (`chiffree === false`, servi par ACAL1413) ;
// `null` (sans devis lié ou sans sélection écrite) ne décoche rien : tout est coché à l'ouverture (ACAL968).
function surfacesNonChiffrees(detail) {
  const surfaces = Array.isArray(detail?.surfaces_chiffrables) ? detail.surfaces_chiffrables : []
  return surfaces.filter((s) => s.chiffree === false).map((s) => s.cle)
}

/* Recette R2-23 — l'enregistrement a RÉUSSI mais la resynchronisation du devis lié est
   refusée : `enregistrerAvant` rend `{ enregistre: true, devisModifie: false, motif }`
   (au lieu de `false`), `motif` = le texte du SERVEUR mot pour mot ; l'écran dit alors la
   vérité au lieu de « non enregistrée ». */
function messageDevisNonModifie(motif, devis = null) {
  const texte = typeof motif === 'string' ? motif.trim() : ''
  const reference = devis?.reference ? ` ${devis.reference}` : ''
  const quel = `le devis lié${reference}`
  return `La conception est enregistrée, mais ${quel} n’a pas été modifié${texte ? ` : ${texte}` : '.'}`
}

/* ACAL1320 (D-ACAL-73 = corriger_dire) — « Resynchroniser le devis » DIT d'abord ce qu'il changera
   (`apercu-resync`, contrat `calepinage_apercu_resync.json` : la resynchronisation réelle jouée puis
   annulée par le serveur), puis demande de confirmer ; rien n'est écrit avant la confirmation. Un devis
   ENVOYÉ est corrigé sur place (règle QJR5) : la carte le dit avant d'agir. */
export const MESSAGE_RIEN_A_CHANGER = 'Rien à changer : le devis porte déjà cette conception. Rien n’a été écrit.'
export const MESSAGE_ENVOYE_CORRIGE = 'Ce devis a déjà été envoyé au client : il sera corrigé sur place. Sa page et '
  + 'son PDF montreront la version corrigée, et la correction sera notée sur le devis.'
export const MESSAGE_ENVOYE_INVISIBLE = 'Ce devis a déjà été envoyé au client : ce qu’il voit ne change pas ; le devis '
  + 'suit la conception.'
export const MESSAGE_BROUILLON_MIS_A_JOUR = 'Le devis brouillon sera mis à jour.'
/* Revue du 26/11 — la confirmation est liée à l'aperçu (jeton) et la vérification électrique se fait à ce moment-là. */
export const MESSAGE_VERIFICATION_A_LA_CONFIRMATION = 'La vérification électrique se fait à la confirmation : si elle '
  + 'bloque, rien n’est écrit et l’écran dit pourquoi.'
export const MESSAGE_APERCU_RELU = 'La conception ou le devis a changé depuis l’aperçu : voici ce que la '
  + 'resynchronisation changera maintenant.'
export const MESSAGE_APERCU_FERME = 'La conception a été retouchée : l’aperçu est fermé, rien n’a été écrit. '
  + '« Resynchroniser le devis » montre ce qui changera maintenant.'
const DELAI_SURVEILLANCE_RETOUCHES_MS = 500

function phraseStatutApercu(apercu) {
  if (apercu?.statut === 'envoye') return apercu.corrige_apres_envoi ? MESSAGE_ENVOYE_CORRIGE : MESSAGE_ENVOYE_INVISIBLE
  return MESSAGE_BROUILLON_MIS_A_JOUR
}

const quantite = (q) => (q == null ? '?' : formatNumber(q, { maxDecimals: 2 }))
const montant = (avant, apres) => (avant == null && apres == null ? ''
  : ` · ${avant == null ? '' : `${formatMAD(avant)} → `}${apres == null ? '' : formatMAD(apres)} HT`)

function lignesApercu(apercu) {
  const lignes = []
  for (const c of apercu?.changements ?? []) {
    const nom = c.designation_avant === c.designation_apres ? c.designation_apres
      : `${c.designation_avant} → ${c.designation_apres}`
    lignes.push(`${nom} : quantité ${quantite(c.quantite_avant)} → ${quantite(c.quantite_apres)}`
      + montant(c.total_ht_avant, c.total_ht_apres))
  }
  for (const a of apercu?.ajouts ?? []) {
    lignes.push(`Ajoutée : ${a.designation} × ${quantite(a.quantite)}${a.total_ht == null ? '' : ` · ${formatMAD(a.total_ht)} HT`}`)
  }
  for (const r of apercu?.retraits ?? []) {
    lignes.push(`Retirée : ${r.designation} × ${quantite(r.quantite)}${r.total_ht == null ? '' : ` · ${formatMAD(r.total_ht)} HT`}`)
  }
  return lignes
}

function ApercuResync({ apercu, avis, enCours, onConfirmer, onAnnuler }) {
  const lignes = lignesApercu(apercu)
  const totaux = apercu?.totaux
  const avertissements = (apercu?.avertissements ?? []).filter((m) => typeof m === 'string' && m.trim())
  return (
    <div className="border border-warning/40 bg-warning/10 p-3" data-testid="cal-devis-resync-apercu">
      {avis && <p className="mb-2 text-sm text-foreground" role="status" data-testid="cal-devis-resync-avis">{avis}</p>}
      <p className="text-sm font-semibold text-foreground" role="alert" data-testid="cal-devis-resync-statut">
        {apercu?.reference ? `Devis ${apercu.reference} — ` : ''}{phraseStatutApercu(apercu)}
      </p>
      <ul className="mt-2 space-y-1 text-sm text-foreground">
        {lignes.length > 0 ? lignes.map((l) => <li key={l}>{l}</li>)
          : <li>Aucune ligne du devis ne change.</li>}
      </ul>
      {totaux?.avant && totaux?.apres && (
        <p className="mt-2 text-sm text-foreground">
          {`Total TTC : ${formatMAD(totaux.avant.ttc)} → ${formatMAD(totaux.apres.ttc)}`}
        </p>
      )}
      {avertissements.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-primary-text">
          {avertissements.map((m) => <li key={m}>{m}</li>)}
        </ul>
      )}
      <p className="mt-2 text-xs text-muted-foreground">{MESSAGE_VERIFICATION_A_LA_CONFIRMATION}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" onClick={onConfirmer} disabled={enCours} data-testid="cal-devis-resync-confirmer"
          className="inline-flex min-h-[44px] items-center border border-brass-400 px-4 py-2 text-sm font-bold text-primary-text disabled:cursor-not-allowed disabled:opacity-60">
          {apercu?.statut === 'envoye' ? 'Corriger le devis envoyé' : 'Confirmer et resynchroniser'}
        </button>
        <button type="button" onClick={onAnnuler} disabled={enCours} data-testid="cal-devis-resync-annuler"
          className="inline-flex min-h-[44px] items-center border border-border px-4 py-2 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-60">
          Annuler
        </button>
      </div>
    </div>
  )
}

function BoutonDevisCalepinage({
  calepinageId, detail = null, lectureSeule = false, onRecharger, onRelire,
  enregistrerAvant = null, aDesRetouches = null, revisionPossible = false,
  // ACAL311 (rejeu P5.5) — faux tant que la scène de l'atelier n'est pas hydratée :
  // `enregistrerAvant` refuserait (rien n'est écrit avant l'hydratation).
  atelierPret = true,
  // ACAL2002 — vrai quand ce bouton EST l'action de l'étape (Documents en Guidé) : il prend alors le bouton doré v2.
  // Ailleurs (panneau Expert) il reste un bouton à filet : l'or est réservé à la seule action suivante (ACAL1802).
  actionEtape = false,
  // Étape Documents (demande croisée du 24/11) : `compact` replie les surfaces chiffrées sur UNE ligne qui se déplie
  // (la liste des contrôles ne défile plus dans la carte) ; `fleche` met le pictogramme « suivant » dans le bouton.
  // Par défaut : ceux de l'action de l'étape ; le panneau Expert garde la forme dépliée, sans flèche.
  compact = actionEtape,
  fleche = actionEtape,
}) {
  const navigate = useNavigate()
  const classeDuBouton = actionEtape ? 'cal-bouton-or cal-bouton-or-grand'
    : 'inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-primary-text disabled:cursor-not-allowed disabled:opacity-60'
  // ACAL171 — le droit SERVI par l'agrégat (`permissions.peut_deroger`,
  // calepinage_approuver), jamais deviné côté écran.
  const peutDeroger = !!detail?.permissions?.peut_deroger
  const [enCours, setEnCours] = useState(false)
  // ACAL171 — le refus électrique : `{geste, detail, bloquants, derogationPossible}`.
  const [bloquage, setBloquage] = useState(null)
  const [motif, setMotif] = useState('')
  const [motifErreur, setMotifErreur] = useState(null)
  const [refus, setRefus] = useState(null)
  const [conflit, setConflit] = useState(null)
  // ACAL923 — la question du 409 `confirmation_taille` (ACAL922) : `{detail, refus}` du serveur.
  const [confirmation, setConfirmation] = useState(null)
  // Recette R2-22 — le 409 `devis_existant` : `{detail, devis, reference}` du serveur.
  const [devisExistant, setDevisExistant] = useState(null)
  // Le corps du dernier « Générer » : une réponse à une question le complète, sans perdre l'autre.
  const dernierCorps = useRef({})
  // Revue du 26/11 — le corps de la dernière resynchro CONFIRMÉE (sans dérogation), rejoué par « Passer outre ».
  const dernierCorpsSync = useRef({})
  // ACAL95 — le retour du serveur à LIRE avant de poursuivre :
  // `{messages, lignes, inchange, devisId, suite: 'recharger' | 'ouvrir' | null}`.
  const [retour, setRetour] = useState(null)
  // ACAL1320 — l'aperçu servi de la resynchronisation, à confirmer (`null` : rien en attente).
  const [apercuResync, setApercuResync] = useState(null)
  const [avisApercu, setAvisApercu] = useState(null) // revue du 26/11 — pourquoi l'aperçu a été relu
  const [apercuFerme, setApercuFerme] = useState(false) // la carte fermée par une retouche de la scène
  const apercuPerime = useRef(false) // le dernier sync-devis a répondu 409 `apercu_perime`
  // Revue du 26/11 — la carte se ferme dès que la scène est retouchée (`aDesRetouches`) : son aperçu ne
  // décrirait plus ce qui serait écrit ; « Resynchroniser le devis » le relit (enregistré d'abord).
  useEffect(() => {
    if (!apercuResync || typeof aDesRetouches !== 'function') return undefined
    const minuterie = setInterval(() => {
      let retouchee = false
      try { retouchee = !!aDesRetouches() } catch { retouchee = false }
      if (retouchee) {
        setApercuResync(null)
        setApercuFerme(true)
      }
    }, DELAI_SURVEILLANCE_RETOUCHES_MS)
    return () => clearInterval(minuterie)
  }, [apercuResync, aDesRetouches])
  // ACAL94 — avertissement (jamais un refus) avant une révision.
  const [retouches, setRetouches] = useState(false)
  const [refusRevision, setRefusRevision] = useState(null) // T4-X7-016 — `{texte, successeur}`
  const gesteEnCours = useRef(false) // ACON46 — garde ré-entrante (voir unSeulGeste)
  // ACAL968 — clés des surfaces décochées ; ACAL1414 : à l'ouverture, celles que le devis lié ne chiffre PAS.
  const [decochees, setDecochees] = useState(() => surfacesNonChiffrees(detail))
  // À la réouverture (et quand le serveur change la sélection du devis, ex. après « Générer »), l'écran relit ce choix.
  const signatureChoix = JSON.stringify(surfacesNonChiffrees(detail))
  const [choixLu, setChoixLu] = useState(signatureChoix)
  if (choixLu !== signatureChoix) { // ajustement d'état pendant le rendu (React) : le choix du serveur a changé
    setChoixLu(signatureChoix)
    setDecochees(JSON.parse(signatureChoix))
  }

  // L'ÉTAT VIENT DU SERVEUR, et d'UNE SEULE lecture : l'agrégat de détail
  // (CAL17) est chargé par `AtelierPanneaux` et descendu ici en prop. Le
  // charger une seconde fois ferait deux appels pour la même vérité — et deux
  // vérités le jour où l'une des deux serait périmée.
  // ACAL93 — en LECTURE SEULE, le seul geste offert est « Réviser (nouvelle version) », quand
  // le serveur le dit possible (jamais masqué par rôle ni refusé).
  if (!detail || (lectureSeule && !(revisionPossible && detail?.devis?.id))) return null

  const devisLie = detail.devis ?? null
  // ACAL915 (D-ACAL-5) — dès deux surfaces posées, ce que le devis additionne, DIT avant le prix ;
  // ACAL968 (D-ACAL-37) — toit ET champ au sol : une case par surface, toutes cochées à l'ouverture.
  const surfaces = Array.isArray(detail.surfaces_chiffrables) ? detail.surfaces_chiffrables : []
  const choixSurfaces = surfaces.some((s) => s.kind === 'toit') && surfaces.some((s) => s.kind !== 'toit')
  const cochees = surfaces.filter((s) => !(choixSurfaces && decochees.includes(s.cle)))
  const aucuneCochee = choixSurfaces && cochees.length === 0
  // Tout coché ⇒ aucun corps (absent = tout, côté serveur) : seule une sélection part.
  const selection = choixSurfaces && cochees.length < surfaces.length
    ? { surfaces_chiffrees: cochees.map((s) => s.cle) } : {}
  const phraseSurfaces = surfaces.length >= 2 && cochees.length > 0
    ? `Le devis chiffre : ${cochees.map((s) => `${s.libelle} (${s.modules})`).join(' + ')} = ${
      cochees.reduce((total, s) => total + Number(s.modules || 0), 0)} modules`
    : null
  const variantes = detail.variantes ?? {}
  const totalVariantes = Number(variantes.total) || 0
  // GARDE DES VARIANTES (CAL38) : quand ce calepinage porte PLUSIEURS options
  // et qu'AUCUNE n'est retenue, chiffrer reviendrait à choisir à la place du
  // commercial. Sans aucune variante, c'est la conception du calepinage
  // elle-même que le serveur chiffre (`services/devis.py::_exiger_layout`) —
  // il n'y a alors rien à choisir, et bloquer là ferait un bouton mort.
  const varianteManquante = totalVariantes > 0 && !variantes.retenue_id
  const desactive = enCours || varianteManquante || !atelierPret || aucuneCochee

  const executer = async (appel) => {
    if (enCours) return
    setRefus(null)
    setConflit(null)
    setConfirmation(null)
    setDevisExistant(null)
    setRetour(null)
    setEnCours(true)
    try {
      return await appel()
    } catch (erreur) {
      const statut = erreur?.response?.status
      const data = erreur?.response?.data
      const electrique = bloquageElectrique(erreur)
      if (electrique) {
        setBloquage((avant) => ({ ...electrique, geste: avant?.geste ?? null }))
        return null
      }
      // ACAL171 — un motif refusé par le serveur se lit SOUS le champ.
      if (statut === 400 && data?.derogation_electrique) {
        setMotifErreur(refusServeur(erreur).message)
        return null
      }
      // ACAL923 — rien ne dimensionne le devis : une QUESTION, jamais « devis figé ».
      if (statut === 409 && data?.code === 'confirmation_taille') {
        setConfirmation({ detail: data.detail, refus: data.refus })
        return null
      }
      // Revue du 26/11 — l'aperçu confirmé ne décrit plus ce qui serait écrit : il est relu (`syncConfirmee`).
      if (statut === 409 && data?.code === 'apercu_perime') {
        apercuPerime.current = true
        return null
      }
      // Recette R2-22 — le lead a déjà un brouillon libre : rattacher, ou créer un autre devis.
      if (statut === 409 && data?.code === 'devis_existant') {
        setDevisExistant({ detail: data.detail, devis: data.devis, reference: data.reference })
        return null
      }
      // Le pré-vol de composition (`errors`) et le refus par champ se lisent
      // sous le champ qu'ils nomment : seul un `detail` nu est un conflit.
      if (statut === 409 && data?.detail && !Array.isArray(data?.errors)) {
        setConflit({
          detail: refusServeur(erreur).message,
          revision_possible: !!data?.revision_possible,
        })
        return null
      }
      setRefus(refusServeur(erreur))
      return null
    } finally {
      setEnCours(false)
    }
  }

  // ACON46 — garde RÉ-ENTRANTE posée AVANT l'enregistrement préalable : un double
  // clic rapide ne lance qu'UN enregistrement et UN POST (libérée au `finally`).
  const unSeulGeste = (geste) => async (...args) => {
    if (enCours || gesteEnCours.current) return
    gesteEnCours.current = true
    try { return await geste(...args) } finally { gesteEnCours.current = false }
  }

  // ACAL94 — range l'écran d'abord ; `false` = rien ne part au serveur.
  // ACAL1320 — `sansDevis` (resynchroniser) : l'enregistrement ne touche pas au devis lié (la route devis le
  // resynchronisait en même temps) ; le devis attend l'aperçu et la confirmation.
  const enregistrerDabord = async ({ sansDevis = false } = {}) => {
    if (typeof enregistrerAvant !== 'function') return true
    setRefus(null)
    setConflit(null)
    setRetour(null)
    let resultat = false
    try {
      // ACAL1275 — pas de toast « Aucun changement » avant le devis.
      resultat = await enregistrerAvant(sansDevis ? { silencieux: true, sansDevis: true } : { silencieux: true })
    } catch {
      resultat = false
    }
    // Recette R2-23 — enregistrée, mais devis lié refusé : le motif du serveur, jamais « non enregistrée ».
    if (resultat?.enregistre === true && resultat.devisModifie === false) {
      setRefus({ champ: 'devis', message: messageDevisNonModifie(resultat.motif, devisLie) })
      return false
    }
    const ok = resultat !== false
    if (!ok) setRefus({ champ: 'roof_layout', message: MESSAGE_ENREGISTREMENT_ECHOUE })
    return ok
  }

  const generer = unSeulGeste(async (corps = {}) => {
    if (!(await enregistrerDabord())) return
    if (!corps.derogation_electrique) setBloquage({ geste: 'generer' })
    dernierCorps.current = corps
    const res = await executer(
      // T4-X5-007 — chaque refus est dit par cet écran (`executer`) : le toast global le répétait.
      () => calepinageApi.calepinages.genererDevis(calepinageId, { ...selection, ...corps }, { suppressErrorToast: true }))
    const nouveau = res?.data?.devis
    if (!nouveau) return
    setBloquage(null)
    setMotif('')
    // Recette R2-22 — rattaché à un brouillon EXISTANT : le dire (jamais « Devis … créé »).
    if (corps.rattacher_devis != null) {
      const manquantesRattache = manquantesElectriques(res.data)
      setRetour({
        messages: [`Calepinage rattaché au devis ${res.data?.reference ?? `#${nouveau}`} : le devis suit `
          + 'maintenant cette conception.', ...messagesDuServeur(res.data)],
        manquantes: manquantesRattache,
        etatTitre: titreEtatElectrique(res.data, manquantesRattache),
        lignes: null,
        inchange: false,
        devisId: null,
        rattache: nouveau,
        suite: 'recharger',
      })
      return
    }
    // ACAL866 — AVEC ou SANS message : la carte « Devis … créé » (jamais de navigation immédiate),
    // les lignes techniques (ACAL95, ACAL171) repliées dessous ; la référence est celle du serveur.
    const manquantes = manquantesElectriques(res.data)
    setRetour({
      // T4-X7-008 — les avertissements de composition (« ce panneau ne convient pas à cet onduleur »…)
      // se lisent SUR la carte du devis créé, jamais repliés ; le technique reste sous « Détails ».
      alertes: messagesDuServeur(res.data, ['avertissements']),
      messages: messagesDuServeur(res.data, ['marques_manquantes']),
      manquantes,
      etatTitre: titreEtatElectrique(res.data, manquantes),
      lignes: null,
      inchange: false,
      devisId: nouveau,
      reference: res.data?.reference ?? null,
      suite: 'ouvrir',
    })
  })

  const relireEtRecharger = async () => {
    // On RELIT l'agrégat plutôt que de deviner le nouvel état du devis.
    await onRelire?.()
    await onRecharger?.()
  }

  // ACAL1320 — 1er temps : enregistrer l'écran (sans toucher au devis), lire l'aperçu, le montrer. Rien d'écrit au
  // devis. « Rien à changer » se dit et s'arrête là. Revue du 26/11 — `avis` : pourquoi l'aperçu est relu.
  const lireApercu = async (avis = null) => {
    setApercuResync(null)
    setAvisApercu(avis)
    setApercuFerme(false)
    if (!(await enregistrerDabord({ sansDevis: true }))) return
    const params = selection.surfaces_chiffrees ? { surfaces: selection.surfaces_chiffrees.join(',') } : null
    const res = await executer(() => calepinageApi.calepinages.apercuResync(calepinageId,
      params ? { params, suppressErrorToast: true } : { suppressErrorToast: true }))
    if (!res) return
    const data = res.data ?? {}
    if (data.inchange) {
      setRetour({ messages: messagesDuServeur(data, ['avertissements']), manquantes: [], etatTitre: null, lignes: null,
        inchange: true, texteInchange: MESSAGE_RIEN_A_CHANGER, devisId: null, suite: null })
      return
    }
    setApercuResync(data)
  }
  const apercevoir = unSeulGeste(() => lireApercu())

  // 2d temps (confirmé) : la resynchronisation réelle, `sync-devis`, avec ou sans dérogation électrique.
  // Revue du 26/11 (D-ACAL-73) — `apercu_confirme` + `jeton_apercu` (le jeton de L'aperçu montré) ne partent QUE
  // de la carte : sans eux, le serveur n'applique pas les désignations à un envoyé ; jeton périmé ⇒ 409
  // `apercu_perime`, rien n'est écrit et l'aperçu est relu. « Passer outre » rejoue le même corps.
  const syncConfirmee = async (corps = {}) => {
    setApercuResync(null)
    const { derogation_electrique: _derogation, ...confirmation } = corps
    dernierCorpsSync.current = confirmation
    if (!corps.derogation_electrique) setBloquage({ geste: 'sync' })
    apercuPerime.current = false
    const res = await executer(
      () => calepinageApi.calepinages.syncDevis(calepinageId, { ...selection, ...corps }, { suppressErrorToast: true }))
    if (!res && apercuPerime.current) {
      apercuPerime.current = false
      setBloquage(null)
      await lireApercu(MESSAGE_APERCU_RELU)
      return
    }
    if (!res) return
    setBloquage(null)
    setMotif('')
    const data = res?.data ?? {}
    const messages = messagesDuServeur(data)
    const manquantes = manquantesElectriques(data)
    const etatTitre = titreEtatElectrique(data, manquantes)
    const lignes = libelleLignesAjoutees(data.lignes_ajoutees)
    // ACAL95 — « Aucun changement » se DIT ; rien n'a bougé, rien à recharger.
    if (data.inchange) {
      setRetour({ messages, manquantes, etatTitre, lignes: null, inchange: true, devisId: null, suite: null })
      return
    }
    // Quelque chose à lire : le rechargement attend « J'ai lu ».
    if (messages.length > 0 || manquantes.length > 0 || lignes) {
      setRetour({ messages, manquantes, etatTitre, lignes, inchange: false, devisId: null, suite: 'recharger' })
      return
    }
    await relireEtRecharger()
  }
  const resynchroniser = unSeulGeste(syncConfirmee)

  const sceneRetouchee = () => {
    try { return typeof aDesRetouches === 'function' && !!aDesRetouches() } catch { return false }
  }
  // La carte confirmée : une scène retouchée depuis l'aperçu ⇒ l'aperçu est relu (enregistré d'abord), jamais confirmé.
  const confirmerApercu = unSeulGeste(async () => {
    if (sceneRetouchee()) {
      await lireApercu(MESSAGE_APERCU_RELU)
      return
    }
    await syncConfirmee({ apercu_confirme: true, jeton_apercu: apercuResync?.jeton })
  })

  // ACAL171 — « Passer outre et générer » : le MÊME geste, relancé avec
  // `derogation_electrique: {motif}` ; un motif vide est refusé sous le champ.
  const passerOutre = async () => {
    const saisi = motif.trim()
    if (!saisi) {
      setMotifErreur(MESSAGE_MOTIF_OBLIGATOIRE)
      return
    }
    setMotifErreur(null)
    const corps = { derogation_electrique: { motif: saisi } }
    if (bloquage?.geste === 'sync') await resynchroniser({ ...dernierCorpsSync.current, ...corps })
    else await generer(corps)
  }

  const confirmerLecture = async () => {
    setRetour(null)
    await relireEtRecharger()
  }

  const reviser = async () => {
    if (!devisLie?.id) return
    // ACAL94 — avertir des retouches non enregistrées, et réviser QUAND MÊME.
    let nonEnregistrees = false
    try { nonEnregistrees = typeof aDesRetouches === 'function' && !!aDesRetouches() } catch { nonEnregistrees = false }
    setRetouches(nonEnregistrees)
    if (nonEnregistrees) toastWarning(MESSAGE_RETOUCHES_NON_ENREGISTREES)
    // ACAL93 — UNE seule fonction de révision (`reviserEtOuvrir`) ; la V2
    // s'ouvre sur sa CONCEPTION.
    if (enCours) return
    setEnCours(true)
    setRefusRevision(null)
    let v2 = null
    try {
      const rendu = await reviserEtOuvrir({
        devis: devisLie,
        onApres: (nouveau) => { v2 = nouveau },
        navigate: () => { if (v2?.id != null) navigate(`/ventes/devis/${v2.id}/design`) },
        // T4-X7-016 — un refus qui nomme un autre devis se lit sous le bouton (jamais un clic muet).
        onConflit: ({ conflit: texte, successeur }) => setRefusRevision({ texte, successeur }),
      })
      if (rendu == null) setRefusRevision((avant) => avant ?? { texte: MESSAGE_REVISION_ECHOUEE, successeur: null })
    } catch {
      setRefusRevision({ texte: MESSAGE_REVISION_ECHOUEE, successeur: null })
    } finally {
      setEnCours(false)
    }
  }
  // T4-X7-016 — ce que la révision a répondu, sous le bouton : le motif du serveur, ou l'échec dit.
  const refusDeRevision = refusRevision && (
    <p className="text-xs text-destructive" role="alert" data-testid="cal-devis-reviser-refus">
      {refusRevision.texte}
      {refusRevision.successeur && (
        <>
          {' '}
          <Link to={`/ventes/devis?devis=${refusRevision.successeur.id}`} className="underline">
            {`Ouvrir ${refusRevision.successeur.reference}`}
          </Link>
        </>
      )}
    </p>
  )

  if (lectureSeule) {
    return (
      <div className="space-y-2" data-testid="cal-bouton-devis">
        <button
          type="button"
          onClick={reviser}
          disabled={enCours}
          data-testid="cal-devis-reviser-lecture-seule"
          className="inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-primary-text disabled:cursor-not-allowed disabled:opacity-60"
        >
          {enCours ? 'Création de la nouvelle version…' : LIBELLE_REVISER}
        </button>
        {refusDeRevision}
        {retouches && (
          <p className="text-xs text-primary-text" role="status" data-testid="cal-devis-retouches">
            {MESSAGE_RETOUCHES_NON_ENREGISTREES}
          </p>
        )}
      </div>
    )
  }

  const casesSurfaces = (
    <fieldset>
      <legend className="text-xs font-semibold text-muted-foreground">Surfaces chiffrées par le devis</legend>
      {surfaces.map((s) => (
        <label key={s.cle} className="flex min-h-[44px] items-center gap-2 text-xs text-foreground">
          <input type="checkbox" className="h-5 w-5" checked={!decochees.includes(s.cle)}
            onChange={() => setDecochees((d) => (d.includes(s.cle)
              ? d.filter((c) => c !== s.cle) : [...d, s.cle]))} />
          {`${s.libelle} (${s.modules} modules)`}
        </label>
      ))}
    </fieldset>
  )
  const pictoFleche = fleche ? <Icone nom="suivant" taille={18} epaisseur={2.2} /> : null
  return (
    <div data-testid="cal-bouton-devis" className={compact
      ? 'flex flex-wrap items-center justify-end gap-x-4 gap-y-2 [&>*:not(details):not(button)]:basis-full' : 'space-y-2'}>
      {choixSurfaces && compact ? (
        <details className="group min-w-0 flex-1 text-xs open:basis-full" data-testid="cal-devis-surfaces">
          <summary className="flex min-h-[44px] cursor-pointer list-none items-center gap-2 text-foreground">
            <span role="status" className="line-clamp-2 min-w-0 group-open:line-clamp-none">{phraseSurfaces || 'Surfaces chiffrées par le devis'}</span>
            <Icone nom="chevron" taille={16} className="flex-none" />
          </summary>
          {casesSurfaces}
        </details>
      ) : null}
      {choixSurfaces && !compact ? casesSurfaces : null}
      {choixSurfaces && aucuneCochee && <p className="text-xs text-destructive" role="status">Cochez au moins une surface</p>}
      {phraseSurfaces && !(choixSurfaces && compact) && <p className="text-xs text-foreground" role="status">{phraseSurfaces}</p>}
      {devisLie ? (
        <button
          type="button"
          onClick={() => apercevoir()}
          disabled={desactive}
          data-testid="cal-resynchroniser-devis"
          className={classeDuBouton}
        >
          {enCours ? 'Resynchronisation…' : 'Resynchroniser le devis'}
          {pictoFleche}
        </button>
      ) : (
        <>
        {/* Lane E9 (T4-X5-010) — avant le bouton : le matériel que chaque option du devis portera. */}
        {!lectureSeule && <ApercuMaterielDevis calepinageId={calepinageId} signature={detail?.layout_hash ?? ''}
          surfaces={selection.surfaces_chiffrees ?? null} />}
        <button
          type="button"
          onClick={() => generer()}
          disabled={desactive}
          data-testid="cal-generer-devis"
          className={classeDuBouton}
        >
          {enCours ? 'Génération…' : 'Générer le devis'}
          {pictoFleche}
        </button>
        </>
      )}

      {/* ACAL1705 — le devis lié se rouvre d'un clic après rechargement : le lien est lu sur
          `Calepinage.devis` (agrégat servi), jamais sur l'état de la séance. */}
      {devisLie?.reference && (
        <p className="text-xs text-muted-foreground">
          Devis lié :{' '}
          {devisLie.id ? (
            <Link to={`/ventes/devis?devis=${devisLie.id}`} data-testid="cal-devis-lie-lien"
              className="inline-flex min-h-11 items-center font-semibold text-primary-text underline">
              {devisLie.reference}
            </Link>
          ) : <span className="text-foreground">{devisLie.reference}</span>}
        </p>
      )}

      {/* ACAL109 (D-ACAL-2) — ce que « Générer le devis » chiffre, DIT : la
          conception courante, dont la variante retenue fait partie. */}
      {totalVariantes > 0 && variantes.retenue_id && (
        <p className="text-xs text-muted-foreground" data-testid="cal-devis-ce-qui-est-chiffre">
          Générer le devis chiffre la conception courante : la variante retenue en
          fait partie (la retenir l’y a écrite).
        </p>
      )}

      {/* La raison de la désactivation, TOUJOURS dite : un bouton grisé sans
          explication est une impasse silencieuse. */}
      {varianteManquante && (
        <p className="text-xs text-muted-foreground" role="status"
          data-testid="cal-devis-variante-manquante">
          Choisissez d’abord une variante retenue.
        </p>
      )}

      {/* REFUS SERVEUR — le bandeau NOMME le champ, le message est celui du
          serveur, mot pour mot. */}
      {refus && (
        <div className="border border-alert-300/40 p-3" data-testid="cal-devis-refus">
          <p className="text-xs font-semibold uppercase tracking-wide text-destructive">
            {LIBELLE_CHAMP[refus.champ] || refus.champ}
          </p>
          <p className="mt-1 text-sm text-destructive" role="alert">{refus.message}</p>
        </div>
      )}

      {/* ACAL171 — refus ÉLECTRIQUE : les bloquants du serveur, mot pour mot ;
          la dérogation n'est offerte qu'à un approbateur. */}
      {bloquage?.bloquants && (
        <div className="border border-alert-300/40 p-3" data-testid="cal-devis-bloquants">
          {bloquage.detail && (
            <p className="text-sm text-destructive" role="alert">{bloquage.detail}</p>
          )}
          <ul className="mt-1 space-y-1 text-sm text-destructive">
            {bloquage.bloquants.map((b, i) => (
              <li key={`${b?.code ?? 'b'}-${i}`} data-testid="cal-devis-bloquant">
                {texteBloquant(b)}
                {b?.detail && <span className="block text-xs text-muted-foreground">{texteBloquant(b.detail)}</span>}
              </li>
            ))}
          </ul>
          {bloquage.derogationPossible && (peutDeroger ? (
            <div className="mt-3 space-y-2">
              <label className="block text-xs text-foreground" htmlFor="cal-devis-motif">
                Motif de la dérogation
              </label>
              <textarea
                id="cal-devis-motif"
                value={motif}
                onChange={(e) => { setMotif(e.target.value); setMotifErreur(null) }}
                data-testid="cal-devis-motif"
                className="w-full border border-border bg-transparent p-2 text-sm"
              />
              {motifErreur && (
                <p className="text-xs text-destructive" role="alert" data-testid="cal-devis-motif-erreur">
                  {motifErreur}
                </p>
              )}
              <button
                type="button"
                onClick={passerOutre}
                disabled={enCours}
                data-testid="cal-devis-passer-outre"
                className="inline-flex items-center gap-2 border border-alert-300 px-4 py-2 text-sm font-bold text-destructive disabled:cursor-not-allowed disabled:opacity-60"
              >
                {bloquage.geste === 'sync' ? 'Passer outre et resynchroniser' : 'Passer outre et générer'}
              </button>
            </div>
          ) : (
            <p className="mt-2 text-xs text-muted-foreground" data-testid="cal-devis-derogation-reservee">
              {MESSAGE_DEROGATION_RESERVEE}
            </p>
          ))}
        </div>
      )}

      {/* ACAL94 — la révision part, mais les retouches non enregistrées sont DITES. */}
      {retouches && (
        <p className="text-xs text-primary-text" role="status" data-testid="cal-devis-retouches">
          {MESSAGE_RETOUCHES_NON_ENREGISTREES}
        </p>
      )}

      {/* ACAL1320 — ce que la resynchronisation changera, DIT avant d'agir ; rien n'est écrit avant « Confirmer ». */}
      {apercuResync && (
        <ApercuResync apercu={apercuResync} avis={avisApercu} enCours={enCours}
          onConfirmer={() => confirmerApercu()} onAnnuler={() => setApercuResync(null)} />
      )}
      {apercuFerme && !apercuResync && (
        <p className="text-xs text-primary-text" role="status" data-testid="cal-devis-resync-ferme">{MESSAGE_APERCU_FERME}</p>
      )}

      {/* ACAL95 — le retour du serveur, LU avant de poursuivre. */}
      {retour && retour.suite === 'ouvrir' && retour.devisId && (
        <CarteDevisCree
          devisId={retour.devisId}
          reference={retour.reference}
          onRevenir={() => setRetour(null)}
          alertes={retour.alertes ?? []}
          aDetails={retour.messages.length > 0 || retour.manquantes?.length > 0}
        >
          <div data-testid="cal-devis-avertissements">
            {retour.manquantes?.length > 0 && (
              <div data-testid="cal-devis-indetermine">
                <p className="text-sm text-foreground" role="status">
                  {retour.etatTitre}
                </p>
                <ul className="mt-1 space-y-1 text-sm text-primary-text">
                  {retour.manquantes.map((m) => <li key={m}>{m}</li>)}
                </ul>
              </div>
            )}
            {retour.messages.length > 0 && (
              <ul className="mt-1 space-y-1 text-sm text-primary-text">
                {retour.messages.map((m) => <li key={m}>{m}</li>)}
              </ul>
            )}
          </div>
        </CarteDevisCree>
      )}
      {retour && !(retour.suite === 'ouvrir' && retour.devisId) && (
        <div className="border border-brass-400/40 p-3" data-testid="cal-devis-avertissements">
          {retour.inchange && (
            <p className="text-sm text-foreground" role="status">{retour.texteInchange ?? 'Aucun changement'}</p>
          )}
          {retour.lignes && (
            <p className="text-sm text-foreground" role="status">{retour.lignes}</p>
          )}
          {retour.manquantes?.length > 0 && (
            <div data-testid="cal-devis-indetermine">
              <p className="text-sm text-foreground" role="status">
                {retour.etatTitre}
              </p>
              <ul className="mt-1 space-y-1 text-sm text-primary-text">
                {retour.manquantes.map((m) => <li key={m}>{m}</li>)}
              </ul>
            </div>
          )}
          {retour.messages.length > 0 && (
            <ul className="mt-1 space-y-1 text-sm text-primary-text" role="status">
              {retour.messages.map((m) => <li key={m}>{m}</li>)}
            </ul>
          )}
          {retour.rattache && (
            <Link to={`/ventes/devis?devis=${retour.rattache}`}
              className="mt-2 inline-flex min-h-[44px] items-center text-sm text-foreground underline">
              Voir le devis
            </Link>
          )}
          {retour.suite === 'recharger' && (
            <button
              type="button"
              onClick={confirmerLecture}
              data-testid="cal-devis-j-ai-lu"
              className="mt-3 inline-flex items-center gap-2 border border-brass-400 px-4 py-2 text-sm font-bold text-primary-text"
            >
              J’ai lu
            </button>
          )}
        </div>
      )}

      {/* ACAL923 — la question de confirmation : le texte du serveur, mot pour mot. */}
      {confirmation && (
        <div className="border border-warning/40 bg-warning/10 p-3" data-testid="cal-devis-confirmation-taille">
          <p className="text-sm text-foreground" role="alert">{confirmation.detail}</p>
          {confirmation.refus && <p className="mt-1 text-xs text-muted-foreground">{confirmation.refus}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => generer({ ...dernierCorps.current, confirmer_taille: true })}
              disabled={enCours}
              className="inline-flex min-h-[44px] items-center border border-brass-400 px-4 py-2 text-sm font-bold text-primary-text disabled:cursor-not-allowed disabled:opacity-60"
            >
              Confirmer et générer
            </button>
            {detail.lead?.id && (
              <Link to={`/crm/leads/${detail.lead.id}`}
                className="inline-flex min-h-[44px] items-center px-4 py-2 text-sm text-foreground underline">
                Renseigner la facture du lead
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Recette R2-22 (D-ACAL-1) — le lead a déjà un brouillon libre : le texte du serveur, et
          le choix explicite. Un devis envoyé ou accepté n'est jamais proposé (refus serveur). */}
      {devisExistant && (
        <div className="border border-warning/40 bg-warning/10 p-3" data-testid="cal-devis-existant">
          <p className="text-sm text-foreground" role="alert">{devisExistant.detail}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => generer({ ...dernierCorps.current, rattacher_devis: devisExistant.devis })}
              disabled={enCours}
              className="inline-flex min-h-[44px] items-center border border-brass-400 px-4 py-2 text-sm font-bold text-primary-text disabled:cursor-not-allowed disabled:opacity-60"
            >
              {`Rattacher ce calepinage au devis ${devisExistant.reference ?? `#${devisExistant.devis}`}`}
            </button>
            <button
              type="button"
              onClick={() => generer({ ...dernierCorps.current, creer_autre_devis: true })}
              disabled={enCours}
              className="inline-flex min-h-[44px] items-center border border-border px-4 py-2 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-60"
            >
              Créer un autre devis
            </button>
            <Link to={`/ventes/devis?devis=${devisExistant.devis}`}
              className="inline-flex min-h-[44px] items-center px-4 py-2 text-sm text-foreground underline">
              Ouvrir le devis existant
            </Link>
          </div>
        </div>
      )}

      {/* 409 — le devis est figé (accepté, refusé, expiré ou remplacé). Le motif
          est celui du serveur ; l'écran choisit seulement d'offrir, ou non, la révision. */}
      {conflit && (
        <div className="border border-brass-400/40 p-3" data-testid="cal-devis-conflit">
          <p className="text-sm text-foreground" role="status">{conflit.detail}</p>
          {conflit.revision_possible && (
            <button
              type="button"
              onClick={reviser}
              disabled={enCours}
              data-testid="cal-devis-reviser"
              className="mt-3 inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-primary-text disabled:cursor-not-allowed disabled:opacity-60"
            >
              {enCours ? 'Création de la nouvelle version…' : LIBELLE_REVISER}
            </button>
          )}
          {refusDeRevision}
        </div>
      )}
    </div>
  )
}

/** D-ACAL-106 — sans le droit de la route `generer-devis` (`calepinage_gerer`, usePeutGenererDevis), ni génération, ni resynchronisation,
    ni révision n'est proposée (le Technicien relève, il ne chiffre pas). Le serveur reste l'autorité. */
export default function BoutonDevis(props) {
  const peut = usePeutGenererDevis()
  return peut ? <BoutonDevisCalepinage {...props} /> : null
}
