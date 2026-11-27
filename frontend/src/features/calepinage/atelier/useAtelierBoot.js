import { useEffect, useEffectEvent } from 'react'
import api from '../../../api/axios'
import ventesApi from '../../../api/ventesApi'
import crmApi from '../../../api/crmApi'
import calepinageApi from '../../../api/calepinageApi'
import { urlFichierCalepinage } from '../../../lib/calage/fichierCalepinage'
import { refusServeur } from '../commun/refusServeur'
import { formatNumber } from '../../../lib/format'
import { demandeMoteur, motifRefus } from '../ModeTerrain.helpers' // ACAL918
import { fallbackPerKwc } from '@rooflib/productionEngine'
import { choisirPaletteAcces } from '@rooflib/shadingEngine'
import { lireModulesDisponibles, moduleDeDepart } from '@roofpro/moduleSelect'
import { cibleAuModule } from './cibleAuModule'
import { brouillonPertinent, consommerReprise, purgerBrouillonsOrphelins } from '../brouillon.js'
import { brouillonLocalAProposer, lireBrouillonServeur } from '../brouillonServeur.js'
import { lireAvecReprise } from '../delaiReseau'
import { contourExploitable } from '../../crm/workspace/traceToit.js'
import {
  repereDuLead, leadToBuilderPayload,
  contexteCalepinageVersPayload, bankableFromDevis,
  stockageBrouillonLocal, stockageSessionLocal, tailleImagePlan, messageRefusRepere,
  reglagesAtelierDesParametres, phraseCalepinageCharge, siteLocaliseInitial, ecouterDevisGenere, oublierIssuesDevis,
} from './contexteAtelier.js'

// R2-20 — le refus de DROIT (403) n'est pas « introuvable — réessayez » : l'écran le DIT et masque ses outils.
export const MESSAGE_ACCES_REFUSE = 'Vous n’avez pas accès à ce calepinage.'

// R2-03 — « adresse, ville » sans répéter la ville quand l'adresse la porte déjà (« …, Agadir » + « Agadir »).
export function adresseSansDoublon(adresse, ville) {
  const a = (adresse ?? '').trim()
  const v = (ville ?? '').trim()
  if (!a || !v) return a || v
  const norme = (t) => t.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
  const dernier = norme(a.split(',').pop().trim())
  return dernier === norme(v) || norme(a).includes(norme(v)) ? a : `${a}, ${v}`
}

// SPL214 — effet de boot de l'atelier (chargement lead/devis/calepinage puis
// initialisation du builder), déplacé VERBATIM depuis pages/ventes/ToitureDesign.jsx
// (move only : le corps de l'effet est inchangé ; seuls les imports et la
// déstructuration de `ctx` en tête sont ajoutés).

// ERR-ACAL311-PANNEAU-ABSENT-ERP — l'ERP n'a ni fenêtre de production ni la route
// `/api/roof-production` d'apps/web : sans plan de production, « Affiner ma consommation »
// restait masqué. La production PAR 1 kWc vient du repli PARTAGÉ `fallbackPerKwc` (productible
// du devis, même calcul que quote_engine/productible.py), étiqueté « estimation » — aucune requête.
const productionAtelierErp = () => fallbackPerKwc()

// ACAL994 — mode calepinage : la production PAR kWc de l'atelier est celle du bloc `chiffrage` servi par
// design-context (ACAL993) quand `production_annuelle_kwh` ET `kwc` sont `servi` — kWc × ce rendement rend
// alors la valeur du serveur à la pose servie ; sinon le repli de table, sans rien inventer. Reste étiquetée
// « estimation » (source `estimate`) : entre deux enregistrements le navigateur n'a qu'une mise à l'échelle.
export function productionAtelierDepuisChiffrage(chiffrage) {
  const prod = chiffrage?.production_annuelle_kwh
  const kwc = chiffrage?.kwc
  if (prod?.etat !== 'servi' || kwc?.etat !== 'servi' || !(prod.valeur > 0) || !(kwc.valeur > 0)) {
    return productionAtelierErp
  }
  return () => fallbackPerKwc(prod.valeur / kwc.valeur)
}

/**
 * ACAL286 — pousse au builder la table d'affectation SERVIE (`electrique.affectation[]`, avec
 * `couleur_chaine` / `couleur_mppt`) pour teinter les modules du pan actif. Best-effort : un
 * résultat illisible ou absent éteint la teinte (comportement d'avant), jamais une erreur
 * d'écran. Aucune écriture : la teinte est dérivée du résultat serveur.
 */
export async function pousserAffectationAtelier(builder, calepinageId) {
  if (!builder || typeof builder.setAffectationChaines !== 'function' || !calepinageId) return
  let lignes = null
  try {
    const res = await calepinageApi.calepinages.resultat(calepinageId)
    lignes = res?.data?.electrique?.affectation ?? null
  } catch {
    lignes = null
  }
  builder.setAffectationChaines(Array.isArray(lignes) ? lignes : null, 'chaine')
}

// F6 (maquettes 22/11) — l'atelier ERP relève le plafond de cadrage (19 sur le site public) :
// MapLibre sur-échantillonne la dernière tuile servie, et le fond neutre n'en dépend pas.
export const ZOOM_MAX_CADRAGE_ATELIER = 22

// ACAL1421 — le contexte d'imagerie de l'atelier, tiré des réglages DÉJÀ lus (`imagerie.pays`, jamais une seconde
// lecture) : la ligne « Image : fournisseur — résolution » s'affiche et l'adresse est cherchée dans le pays réglé.
// Société MUETTE (aucun pays réglé) ⇒ aucun contexte : un contexte, même sans pays, fait passer le fond satellite
// par le registre de fournisseurs, qui retient alors le premier déclaré au lieu du fond historique (critique de la
// vague A du 23/11/2026). Le fond ne change donc que pour une société qui a réglé son imagerie.
// ACAL1754 — tout le contexte RÉGLÉ (fournisseur choisi, fournisseurs admis, mention légale), lu par
// `roofConfig.ts::resolveImageryProvider` : une société qui a choisi son fournisseur le voit sur la carte.
export function imageryDesReglages(reglagesAtelier) {
  if (reglagesAtelier?.imagerie) return reglagesAtelier.imagerie
  const pays = reglagesAtelier?.pays ?? null
  return pays ? { pays } : undefined
}

/**
 * F6 — cadre la caméra sur TOUS les pans (le toit ≈ 40 % de la carte), sans animation. Caméra
 * seule : rien de sérialisé, aucun brouillon, la scène n'est pas marquée modifiée. Sans effet
 * si le constructeur n'expose pas `cadrerToit` (ancien build) ou pendant un tracé.
 */
export function cadrerToitAtelier(builder, racine = typeof document !== 'undefined' ? document : null) {
  return typeof builder?.cadrerToit === 'function'
    ? builder.cadrerToit({ zoomMax: ZOOM_MAX_CADRAGE_ATELIER, basPx: hauteurCouverteParTiroir(racine) }) : false
}

/**
 * H1 (tour 3) — tablette / téléphone : le tiroir du bas (`#rp9-studio-inspecteur[data-tiroir="1"]`) couvre le bas de la
 * carte ; le cadrage vise la partie VISIBLE, au-dessus. Rend les pixels couverts (0 au bureau, sans tiroir ou sans DOM).
 */
export function hauteurCouverteParTiroir(racine) {
  const carte = racine?.getElementById?.('rp9-map')
  const tiroir = racine?.querySelector?.('#rp9-studio-inspecteur[data-tiroir="1"]:not([hidden])')
  if (!carte || !tiroir) return 0
  const bas = carte.getBoundingClientRect().bottom - tiroir.getBoundingClientRect().top
  return Number.isFinite(bas) && bas > 0 ? Math.round(bas) : 0
}

/**
 * ACAL918 — l'option `demanderPlanSurface` de l'atelier : la demande au moteur (`calepinageApi.moteur.pose`) d'une
 * surface de pose enregistrée. Le contour tracé voyage tel quel (`contourM`), la latitude de l'épingle part dans `sol`
 * (ACAL606) ; l'atelier ne parle jamais à Django. Rend la réponse du moteur, ou rejette avec le motif français.
 */
export function demanderPlanSurfaceDepuis(ctx) {
  const latitude = Number(ctx?.geometrie?.pin?.lat)
  return async (surface) => {
    // `demandeMoteur` pose kit, axe et paramètres ; le contour (rectangle de convenance) est remplacé par le tracé.
    const base = demandeMoteur({
      repere: surface.id, largeurM: 1, profondeurM: 1, rowAzimuthDeg: surface.rowAzimuthDeg, tiltDeg: surface.tiltDeg,
      moduleLongM: surface.moduleLongM, moduleCourtM: surface.moduleCourtM, puissanceWc: surface.moduleWc,
      modulesParTable: surface.modulesParTable, alleeM: surface.alleeM,
    })
    if (!base || !Array.isArray(surface.contourM) || surface.contourM.length < 3) {
      throw new Error('contour ou module incomplet : rien n’est envoyé au moteur')
    }
    const demande = { ...base, contour: surface.contourM, surfaces: [{ ...base.surfaces[0], contour: surface.contourM }] }
    try {
      const res = await calepinageApi.moteur.pose({ demande, ...(Number.isFinite(latitude) ? { sol: { latitude_deg: latitude } } : {}) })
      return res.data
    } catch (e) {
      throw new Error(motifRefus(e?.response?.data) || 'le moteur n’a pas répondu')
    }
  }
}

/** ACAL777 — « Facture du lead : 900 MAD/mois » sous la carte Recommandation (rien si la facture est inconnue). */
export function poserLigneFactureLead(facture) {
  const hote = document.getElementById('rp9-reco-savings')?.parentElement
  if (!hote) return
  hote.parentElement?.querySelector('[data-facture-lead]')?.remove()
  if (!(Number(facture) > 0)) return
  const ligne = document.createElement('p')
  ligne.setAttribute('data-facture-lead', '')
  ligne.className = 'mt-2 text-xs text-muted-foreground'
  ligne.textContent = `Facture du lead : ${formatNumber(Number(facture), { locale: 'fr' })} MAD/mois`
  hote.insertAdjacentElement('afterend', ligne)
}

export function useAtelierBoot(ctx) {
  // Identifiants et drapeaux de mode, puis refs, puis setters d'état.
  // ACAL37 — plus de mode devis écrivain : `devisId` = le devis SYNCHRONISÉ du flux
  // `/ventes/devis/:id/design` (atelier calepinage), lu pour l'étude bancable (PV75).
  const { cibleId, calepinageId, devisId, leadId, estCalepinage } = ctx
  const { paramsContexte } = ctx
  // ACON80 — `{devis}` quand le devis synchronisé est porté par une VARIANTE.
  // parametres-requete: devis
  const lireContexte = () => (paramsContexte
    ? calepinageApi.calepinages.designContext(calepinageId, paramsContexte)
    : calepinageApi.calepinages.designContext(calepinageId))
  const { builderApi, reducedMotion, utilisateurCourantId } = ctx
  const { setBrouillonPropose, setBuilderApiActuel, setBuilderReady, setContexte } = ctx
  const { setCatalogueIndisponible } = ctx
  const { setContourMessage, setHashBaseBrouillon, setLead, setLoadError, setStatus } = ctx
  // ACAL85 — « la scène est hydratée » : posé par `onHydrationTerminee` dans les TROIS
  // modes. `onApiReady` arrive AVANT l'hydratation (roof-tool-pro11) : une référence
  // prise là compterait l'hydratation elle-même comme une modification.
  const { setSceneHydratee } = ctx
  // T4-U4-013 — l'état de localisation du site, suivi par l'atelier (bandeau « Site non localisé »).
  const { setSiteLocalise } = ctx
  // ACAL192 — refus serveur du recentrage automatique (calepinage verrouillé…), en français.
  const { setRepereErreur } = ctx
  // ACAL311 — la porte `consommation/proposer/` (ToitureDesign), liée au calepinage ouvert :
  // l'atelier reçoit la réponse 200, ou le refus DÉCODÉ `{message, champs}` (refusServeur).
  const { proposerConsommation } = ctx
  const proposerPourAtelier = (typeof proposerConsommation === 'function' && calepinageId)
    ? (corps) => proposerConsommation(calepinageId, corps).then(
      (res) => res?.data, (err) => { throw refusServeur(err) })
    : null
  // ACAL840 — « Lire une photo de facture » : disponibilité + lecture, liées au calepinage ouvert.
  const lireFacture = (calepinageId && calepinageApi.calepinages.lireFactureConsommation)
    ? {
      disponible: () => calepinageApi.calepinages.lireFactureDisponible(calepinageId).then((res) => res?.data),
      lire: (fichier) => {
        const corps = new FormData()
        corps.append('fichier', fichier)
        return calepinageApi.calepinages.lireFactureConsommation(calepinageId, corps).then((res) => res?.data)
      },
    }
    : null
  // ENF22 — le corps du boot lit `ctx` (setters/refs du parent) a l'instant de
  // l'effet : un evenement d'effet, relance seulement par la liste ci-dessous.
  const demarrerBoot = useEffectEvent(() => {
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

    // CALX104/CALX403 câblage — les DEUX sections des réglages société que l'atelier
    // consomme (`zones_types` : les gabarits d'obstacle de la société ; `degagements` :
    // la largeur d'allée de circulation par pays). L'outil ne parle JAMAIS à Django : la
    // page les lit et les transmet TELLES QUELLES, comme elle le fait déjà pour le
    // catalogue de modules (CALX109). Best-effort : un refus de droits ou une panne
    // réseau ne bloque pas le boot — l'atelier ne propose alors AUCUN gabarit et ne
    // préremplit AUCUNE largeur (jamais une cote de repli).
    function chargerReglagesAtelier() {
      return Promise.resolve()
        .then(() => calepinageApi.parametres.get())
        .then((res) => reglagesAtelierDesParametres(res?.data))
        .catch(() => null)
    }

    // CALX107 câblage — LE CALQUE DE FOND DU DOCUMENT. `mapDraw.setFond` existait et
    // n'avait AUCUN appelant : un calepinage rouvert perdait sa photo de site calée, alors
    // que le document la portait (`underlay`). L'atelier ne parle jamais à Django, donc
    // c'est l'écran qui va chercher le FICHIER (URL pré-signée) et le lui redonne.
    //
    // Les DEUX genres sont servis. Une « photo » de site porte son URL et son calage à
    // quatre coins (`GET …/photos/`, CAL52/CAL53) ; un « plan » importé désigne une pièce
    // jointe, dont `GET …/plan-importe/` (CALX107) publie l'URL servie et la taille en
    // PIXELS NATURELS. Une taille inconnue reste inconnue : `tailleImage` vaut alors
    // `null` et le constructeur refuse le plan avec SA phrase, plutôt que d'étaler
    // l'image sur une étendue supposée.
    // Le MOTIF d'un fond non affiché vient TOUJOURS du constructeur (`poserFond`) : une
    // seule formulation dans tout l'atelier, jamais une phrase recopiée ici.
    async function poserFondDuDocument(api) {
      const fond = api?.fondDuDocument?.()
      if (!fond) {
        // Un `underlay` ILLISIBLE ne disparaît pas en silence : son motif nomme le
        // champ fautif (contrat CALX86).
        const motif = api?.motifFondRefuse?.()
        if (motif) setStatus(motif)
        return
      }
      if (!api?.poserFond) return
      let ressource = {}
      if (fond.kind === 'photo' && fond.photoSiteId && calepinageId) {
        try {
          const res = await calepinageApi.calepinages.photos(calepinageId)
          const photo = (res?.data?.photos ?? [])
            .find((p) => String(p?.id) === String(fond.photoSiteId))
          if (photo?.url) ressource = { url: urlFichierCalepinage(photo.url), calagePhoto: photo.calage }
        } catch {
          console.warn("useAtelierBoot (poserFondDuDocument) : pas de fichier : le constructeur dira POURQUOI le fond n'est pas affiché")
        }
      } else if (fond.kind === 'plan' && fond.attachmentId && calepinageId) {
        // CALX107 câblage — la pièce jointe du plan : URL servie + pixels naturels.
        try {
          const res = await calepinageApi.calepinages.planImporte(calepinageId)
          const plan = res?.data
          if (plan?.url) {
            ressource = { url: urlFichierCalepinage(plan.url), tailleImage: tailleImagePlan(plan) }
          }
        } catch {
          console.warn("useAtelierBoot (poserFondDuDocument) : pas de fichier : le constructeur dira POURQUOI le fond n'est pas affiché")
        }
      }
      if (cancelled) return
      const pose = api.poserFond(fond, ressource)
      if (!pose?.ok && pose?.motif) setStatus(pose.motif)
    }

    async function boot() {
      choisirPaletteAcces('site') // F6 — mode lead : la palette du site (rouge → vert), jamais celle de l'atelier
      // CALX104/CALX403 — lancés EN PARALLÈLE du lead (best-effort, cf. ci-dessus).
      const reglagesPromise = chargerReglagesAtelier()
      // CALX132 — l'empreinte OSM du bâtiment, lue plus bas avec le contour et
      // proposée au panneau « Bâtiment » une fois le builder monté.
      let batimentOsm = null
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

      // WIR227/QJ25 — le contour OSM du bâtiment épinglé (roof-footprint,
      // Overpass) n'était jamais consommé par l'atelier : la carte démarrait
      // TOUJOURS sans contour, même quand le lead porte déjà une épingle.
      // Best-effort, jamais bloquant — un échec réseau laisse le tracé manuel
      // intact, exactement comme le repli existant. Ne s'applique QUE si le
      // lead n'a pas déjà de contour (tracé manuel déjà posé = jamais écrasé).
      if (!leadData.roof_outline && repereDuLead(leadData)) {
        try {
          const fp = await crmApi.getRoofFootprint(leadId)
          // CALX132 câblage — la MÊME réponse porte un bloc `batiment`
          // (hauteur/niveaux OSM + provenance, contrat CALX106) qui était JETÉ :
          // l'atelier extrudait donc toujours ses 6 m de convention. Il part
          // vers le panneau « Bâtiment » comme une PROPOSITION (le module
          // `shadingUi` affiche un bouton « Reprendre la hauteur OSM… ») — rien
          // n'est écrit dans le document sans un clic. Mémorisé ici parce que le
          // builder n'est pas encore monté : la pose se fait dans `onApiReady`.
          batimentOsm = fp?.data?.batiment ?? null
          const polygon = fp?.data?.polygon
          if (Array.isArray(polygon) && polygon.length >= 3) {
            // Fable review — le serveur (roof_detect.py) renvoie des points
            // `{lat, lng}` ; le contrat de l'atelier (roofPro11/prefill.ts
            // hydrateFromLead) exige des PAIRES `[lat, lng]` et rejette
            // silencieusement (Array.isArray(p)) tout sommet qui n'en est
            // pas — sans cette conversion, TOUS les sommets OSM étaient
            // éliminés et la carte ne bootait que sur le pin. Conversion
            // faite ICI, jamais dans apps/web (non touché).
            const paires = polygon
              .map((p) => [Number(p?.lat), Number(p?.lng)])
              .filter(([lat, lng]) => Number.isFinite(lat) && Number.isFinite(lng))
            if (paires.length >= 3) {
              // ACAL251 — l'emprise OSM est cherchée AUTOUR du repère servi :
              // elle l'entoure, donc elle ensemence le pan (contour utilisable).
              leadData = {
                ...leadData, roof_outline: paires,
                repere_toit: { ...leadData.repere_toit, contour_utilisable: true },
              }
            }
          } else if (fp?.data?.message) {
            setContourMessage(fp.data.message)
          }
        } catch {
          console.warn('useAtelierBoot (boot) : repli silencieux : tracé manuel toujours disponible')
        }
      }
      if (cancelled) return

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
        console.warn('useAtelierBoot (boot) : repli : message ci-dessous')
      }
      if (cancelled) return
      if (!maptilerKey) {
        setStatus('Carte indisponible (clé MapTiler manquante côté serveur).')
        setLoadError('Carte indisponible : la clé MapTiler n’est pas configurée sur le serveur ERP.')
        return
      }

      // Le DOM `rp9-*` est déjà rendu (JSX ci-dessous) : on boote le builder.
      const mod = await import('@roofbuilder')
      const reglagesAtelier = await reglagesPromise
      if (cancelled) return
      window.__taqinorRoofBooted = true
      mod.initRoofToolPro8({
        // ACAL80 — l'ERP ne sert pas `/api/roof-yield` (route d'apps/web) : aucune requête,
        // repli sur la table committée — plus aucune erreur 405 à l'ouverture.
        rendementPvgis: null,
        // ACAL311 — mode lead : aucun calepinage, kWh affichés « estimation (barème indicatif) ».
        proposerConsommation: null,
        productionAtelier: productionAtelierErp,
        maptilerKey,
        mapboxToken,
        reducedMotion: !!reducedMotion,
        hydrate: { lead: leadToBuilderPayload(leadData) },
        // CALX104/CALX403 câblage — gabarits d'obstacle + largeur d'allée de la société,
        // transmis TELS QUELS ; `null` = aucun réglage, aucune cote de repli.
        reglagesAtelier,
        imagery: imageryDesReglages(reglagesAtelier), // ACAL1421
        // L-MAP — le contour ORIGINAL du client, géo-référencé sur la carte
        // (calque passif, roofPro11/prefill.ts referenceContourRing). Gardé
        // par le MÊME `contourExploitable` que la légende/bascule (revue
        // adversariale 26/08) : un contour que l'écran refuse déjà (hors
        // bornes, forme inconnue) ne part JAMAIS vers le builder — pas de
        // polygone orphelin sans bascule pour le masquer.
        referenceContour: contourExploitable(leadData.roof_outline) ? leadData.roof_outline : null,
        onApiReady: (a) => {
          builderApi.current = a; setBuilderReady(true); setBuilderApiActuel(a)
          // CALX132 câblage — la proposition OSM ne part QUE si le serveur en a
          // renvoyé une : sans bloc `batiment`, AUCUNE hauteur n'est proposée (et
          // l'atelier garde sa convention d'extrusion, affichée comme telle).
          if (batimentOsm) a.setBatimentOsmPropose?.(batimentOsm)
        },
        // ACAL85 — la référence « non modifiée » se prend APRÈS l'hydratation.
        onHydrationTerminee: () => { setSceneHydratee?.(true) },
      })
      // Pré-remplit l'adresse depuis la ville du lead (champ de recherche).
      const addrEl = document.getElementById('rp9-address')
      if (addrEl && leadData.ville) addrEl.value = String(leadData.ville)
      setStatus('Repère du client chargé. Dessinez / ajustez, puis « Générer le devis ».')
    }

    // ── CAL37 — MODE CALEPINAGE : boot en UN SEUL appel (design-context) ──
    // Jumeau NEUTRE de `bootDevis` : le contrat
    // `calepinage_design_context.json` sert les SEPT mêmes clés, toujours
    // présentes. Les différences sont celles du domaine, jamais des inventions
    // d'écran : aucun contexte de devis n'est exigé (D3), `cible` peut valoir
    // `null` (aucun devis lié, aucune facture) et l'écran l'affiche alors « non
    // renseignée » plutôt que de deviner une puissance, et il n'y a ni étude
    // bancable ni panneau de livraison client — rien de tout cela n'existe sur
    // un calepinage, et l'inventer produirait des boutons morts.
    // H1 (tour 3) — la lecture de démarrage dépasse parfois les 20 s du client sur un poste chargé : elle est relancée
    // UNE fois quand AUCUNE réponse n'est arrivée (délai, réseau), jamais sur un refus servi (4xx/5xx avec corps).
    // L'écran reste « en chargement » pendant ce second essai ; seul son échec affiche « Impossible de charger ».
    async function lireContexteAvecReprise() {
      try {
        return await lireContexte()
      } catch (err) {
        if (cancelled || err?.response) throw err
        setStatus('Le serveur met du temps à répondre — nouvel essai de chargement…')
        return lireContexte()
      }
    }

    async function bootCalepinage() {
      choisirPaletteAcces('atelier') // F6 — bleu nuit → or (maquette Panneaux) dès le boot, toute étape et Expert
      // CALX109 — le CATALOGUE DE MODULES de la société, lu EN PARALLÈLE du
      // design-context : best-effort exactement comme l'étude bancable de
      // `bootDevis` — il ne bloque jamais le boot et n'invente rien. Sans lui
      // (droits, réseau, société sans fiche « module »), l'atelier pose le
      // module par défaut, NOMMÉ. Le contexte agrégé ne le porte pas (contrat
      // `calepinage_design_context.json`, PACT10) : c'est sa propre porte.
      // ACAL30 — un catalogue ILLISIBLE ne bloque pas l'ouverture (on regarde la
      // conception), mais il INTERDIT l'enregistrement : sans lui, le module de chaque
      // pan retomberait en silence sur le module par défaut (720 Wc).
      // T4-B4-002 — une lecture restée SANS réponse (délai de 20 s dépassé sur une pile chargée : « annulée » au réseau)
      // est relancée une fois ; seul un second échec (ou un refus servi) rend le catalogue indisponible.
      const modulesPromise = Promise.resolve()
        // T4-U4-026 — l'échec est dit par la barre (« Réessayer ») : aucun toast global en plus.
        .then(() => lireAvecReprise(() => calepinageApi.calepinages.modulesDisponibles(calepinageId, { suppressErrorToast: true })))
        .then((res) => res.data)
        .catch(() => {
          setCatalogueIndisponible?.(true)
          return null
        })
      // CALX104/CALX403 — même porte, même discipline best-effort.
      const reglagesPromise = chargerReglagesAtelier()
      // PV75 / ACAL37 — l'étude bancable du devis SYNCHRONISÉ (flux
      // `/ventes/devis/:id/design`), best-effort, jamais bloquante.
      const bankablePromise = devisId
        ? Promise.resolve()
          .then(() => ventesApi.getDevisById(devisId))
          .then((res) => bankableFromDevis(res.data))
          .catch(() => null)
        : Promise.resolve(undefined)

      let ctx = null
      try {
        const res = await lireContexteAvecReprise()
        ctx = res.data
      } catch (err) {
        if (cancelled) return
        const code = err?.response?.status
        setLoadError(
          code === 403 ? MESSAGE_ACCES_REFUSE
            : code === 404
              ? 'Calepinage introuvable.'
              : 'Impossible de charger le calepinage — réessayez.'
        )
        setStatus(code === 403 ? MESSAGE_ACCES_REFUSE : `Calepinage introuvable (erreur ${code ?? '?'}).`)
        return
      }
      if (cancelled) return
      // H1 (tour 3) — une lecture RÉUSSIE efface l'échec d'un essai précédent (relance du boot) : l'écran ne garde
      // jamais « Impossible de charger » sur une conception chargée, ni ne bloque l'enregistrement à tort.
      setLoadError(null)
      // ACAL192 (D-ACAL-13, D-QJR5-15) — l'épingle SUIT le lead (`derive.etat ===
      // 'automatique'`) et le GPS du lead a été corrigé : le SERVEUR recentre UNE fois
      // (translation versionnée), puis le contexte est relu AVANT de booter le
      // constructeur — la carte s'ouvre sur la géométrie corrigée. Aucune translation
      // décidée ici ; un refus (verrou…) est DIT et l'atelier boote sur l'existant.
      if (ctx?.geometrie?.derive?.etat === 'automatique' && ctx?.modifiable) {
        try {
          await calepinageApi.calepinages.recentrerSurLead(calepinageId)
          const relu = await lireContexte()
          if (relu?.data) ctx = relu.data
        } catch (err) {
          setRepereErreur?.(messageRefusRepere(err?.response?.data))
        }
        if (cancelled) return
      }
      setContexte(ctx)

      const carte = ctx?.carte ?? {}
      if (!carte.available || !carte.maptilerKey) {
        setStatus('Carte indisponible (clé MapTiler manquante côté serveur).')
        setLoadError('Carte indisponible : la clé MapTiler n’est pas configurée sur le serveur ERP.')
        return
      }

      // CALX68 — poursuit le boot du constructeur, éventuellement avec un
      // LAYOUT DE SUBSTITUTION (le brouillon repris) au lieu de celui du
      // serveur. Extrait de `bootCalepinage` pour pouvoir être rappelé PLUS
      // TARD, une fois que l'utilisateur a choisi « Reprendre » ou
      // « Ignorer » (voir plus bas) — jamais avant.
      async function poursuivreBootCalepinage(layoutSubstitue) {
        const mod = await import('@roofbuilder')
        // CALX109 — le catalogue est attendu ICI, après le design-context :
        // la promesse a couru pendant, et un échec vaut « aucun catalogue »
        // (le module par défaut de l'atelier reste posé), jamais un boot raté.
        const modulesDisponibles = await modulesPromise
        const reglagesAtelier = await reglagesPromise
        const bankable = await bankablePromise
        if (cancelled) return
        window.__taqinorRoofBooted = true
        const payload = contexteCalepinageVersPayload(ctx)
        // T4-X3-009 — la première pose automatique pose la cible comptée dans le module DE DÉPART du constructeur
        // (`moduleDeDepart`, le même lecteur que lui) : le compte servi (`panneaux_selon_watt`), jamais les 8 de 550 W.
        if (payload?.cible?.panneaux != null && modulesDisponibles) {
          const depart = moduleDeDepart(lireModulesDisponibles(modulesDisponibles))
          payload.cible.panneaux = cibleAuModule({ panneaux: payload.cible.panneaux, kwc: ctx?.cible?.kwc,
            wattConception: payload.cible.panel_watt }, depart?.pmaxWc, modulesDisponibles.panneaux_selon_watt)?.panneaux ?? null
        }
        // T4-X8-012 — la table SERVIE du besoin de la facture par puissance de module : le champ « Panneaux nécessaires » de
        // l'Expert la lit sur « le plus de panneaux » (le compte du module posé), jamais le plafond 400.
        if (payload && modulesDisponibles) payload.panneauxSelonWatt = modulesDisponibles.panneaux_selon_watt ?? {}
        if (payload && layoutSubstitue !== undefined) {
          payload.geometrie = { ...payload.geometrie, roof_layout: layoutSubstitue }
        }
        // Un calepinage non modifiable (devis lié déjà parti chez le client, la
        // raison venant du serveur ventes MOT POUR MOT) BOOTE quand même : on
        // peut regarder la conception — seule l'action d'enregistrement
        // disparaît, exactement comme en mode devis.
        mod.initRoofToolPro8({
          // ACAL80 — l'ERP ne sert pas `/api/roof-yield` (route d'apps/web) : aucune requête,
          // repli sur la table committée — plus aucune erreur 405 à l'ouverture.
          rendementPvgis: null,
          // ACAL311 — kWh au barème société (null hors calepinage : « estimation »).
          proposerConsommation: proposerPourAtelier,
          lireFactureConsommation: lireFacture,
          productionAtelier: productionAtelierDepuisChiffrage(ctx?.chiffrage),
          maptilerKey: carte.maptilerKey,
          mapboxToken: carte.mapboxToken || undefined,
          reducedMotion: !!reducedMotion,
          hydrate: { devis: payload },
          // L-MAP — le contour ORIGINAL du client (jamais celui, déjà édité, de
          // la conception courante), sous la MÊME garde `contourExploitable` que
          // la légende/bascule : voir les commentaires jumeaux ci-dessus.
          referenceContour: contourExploitable(ctx?.geometrie?.contour_client)
            ? ctx.geometrie.contour_client : null,
          // CALX109 — le catalogue de modules de la société, transmis TEL QUEL
          // (l'outil ne parle jamais à Django) ; `null` = aucun catalogue.
          modulesDisponibles,
          // CALX104/CALX403 câblage — voir `boot()` plus haut.
          reglagesAtelier,
          imagery: imageryDesReglages(reglagesAtelier), // ACAL1421
          // ACAL918 — le plan du moteur pour « Enregistrer le contour tracé » (surface de pose).
          demanderPlanSurface: demanderPlanSurfaceDepuis(ctx),
          // T4-U4-013 — l'atelier écrit `siteLocalise` (le serveur n'utilise l'épingle que localisée)
          // et nous dit, à chaque geste, si le site est localisé (bandeau).
          suiviSite: {
            initial: siteLocaliseInitial(payload?.geometrie?.roof_layout, ctx?.geometrie?.source_repere),
            ecouter: (etat) => setSiteLocalise?.(etat),
            // T4-X2-005 — le point de repli SERVI : site non localisé, l'atelier calcule au lieu de la simulation.
            repli: ctx?.calepinage?.site_de_repli_point ?? null,
          },
          // ACAL777 — la facture du lead, repli d'affichage des cartes (jamais écrite au document).
          factureMensuelleMad: payload?.factureMensuelleMad ?? null,
          // ACAL778 — un devis lié ⇒ la carte Économies renvoie vers l'onglet Économie.
          devisLie: ctx?.calepinage?.devis_lie != null,
          // ACAL994 — l'économie SERVIE (ou `null` : non servie ⇒ la carte dit « estimation »), relue ensuite par majChiffrage.
          chiffrage: ctx?.chiffrage ?? null,
          // PV75 / ACAL37 — l'étude bancable du devis synchronisé (absente hors flux devis).
          ...(devisId ? { bankable } : {}),
          onApiReady: (a) => {
            builderApi.current = a; setBuilderReady(true); setBuilderApiActuel(a)
          },
          // CALX107 câblage — le document peut demander un CALQUE DE FOND
          // (`underlay`) : l'atelier sait le peindre mais ne parle jamais à
          // Django, c'est donc à l'écran d'aller chercher le fichier. ACAL68 :
          // APRÈS l'hydratation (jamais depuis `onApiReady`, où `fondDuDocument()`
          // vaut null ou le fond du document précédent en navigation SPA).
          onHydrationTerminee: () => {
            // ACAL85 — brouillon et garde de sortie partent de la scène HYDRATÉE.
            setSceneHydratee?.(true)
            poserFondDuDocument(builderApi.current)
            // ACAL286 — la teinte par chaîne vient de la table servie (best-effort).
            pousserAffectationAtelier(builderApi.current, calepinageId)
            cadrerToitAtelier(builderApi.current) // F6 — le toit remplit la carte, une fois par boot
          },
        })
        // La barre de recherche d'adresse part PRÉ-REMPLIE, exactement comme en
        // mode devis (`bootDevis` ci-dessus, PV23bis) et en mode lead (`boot()`).
        // C'était la dernière divergence connue du mode calepinage : le commercial
        // ouvrait l'atelier sur une barre VIDE et devait retaper l'adresse que le
        // serveur connaît déjà. Le contexte la porte sous les MÊMES noms que le
        // contrat devis (`client_adresse`/`client_ville`) — aucune clé devinée,
        // aucune adresse composée ici au-delà de la jointure des deux morceaux.
        poserLigneFactureLead(payload?.factureMensuelleMad)
        const addrEl = document.getElementById('rp9-address')
        const adresse = adresseSansDoublon(ctx?.calepinage?.client_adresse, ctx?.calepinage?.client_ville)
        if (addrEl && adresse) addrEl.value = adresse
        const titre = (ctx?.calepinage?.titre ?? '').trim()
        setStatus(phraseCalepinageCharge(titre, calepinageId, ctx?.modifiable))
      }

      // CALX68 — brouillon local : détecté AVANT de booter le constructeur,
      // pour pouvoir substituer `roof_layout` SANS second boot si le
      // commercial choisit de reprendre. `hashBase` est l'empreinte du
      // layout SERVEUR lue MAINTENANT (voir l'en-tête de `brouillon.js` —
      // elle tient lieu d'`updated_at`, absent du contrat design-context) ;
      // elle reste constante pour toute la session d'édition qui suit.
      // ACAL84 — la clé porte l'empreinte « document » SERVEUR
      // (design-context), jamais un djb2 de l'objet client : l'ordre des clés
      // jsonb diffère de la sérialisation et la clé changeait sans changement.
      // Sans document (aucune conception encore), le segment le DIT.
      const hashServeur = ctx?.geometrie?.empreinte_document || 'aucun-document'
      if (!cancelled) setHashBaseBrouillon(hashServeur)
      const idsBrouillon = { calepinageId, utilisateurId: utilisateurCourantId }
      // ACAL84 — les brouillons d'empreintes PÉRIMÉES de ce calepinage et de
      // cet utilisateur sont purgés à l'ouverture (jamais réhydratés).
      purgerBrouillonsOrphelins({
        storage: stockageBrouillonLocal(), ...idsBrouillon, hashBase: hashServeur,
      })
      // ACAL84 — « Reprendre » (geste explicite) a mémorisé le brouillon puis
      // rechargé : ce boot-ci part de lui, sans re-proposer le bandeau.
      const reprise = consommerReprise(stockageSessionLocal(), idsBrouillon)
      if (reprise) {
        await poursuivreBootCalepinage(reprise.layout)
        return
      }
      // T4-U1-013 — un brouillon local IDENTIQUE au document servi (dernier enregistrement) n'est pas proposé.
      const brouillon = brouillonLocalAProposer(brouillonPertinent({
        storage: stockageBrouillonLocal(),
        ...idsBrouillon,
        hashBase: hashServeur,
      }), ctx?.geometrie?.roof_layout ?? null)
      // ACAL400 — sans brouillon LOCAL, le brouillon SERVEUR de l'utilisateur
      // (écrit sur un autre poste) est proposé par le MÊME bandeau, sans
      // retarder le boot.
      if (!brouillon) {
        lireBrouillonServeur({
          lire: calepinageApi.calepinages.brouillon, calepinageId, hashBase: hashServeur,
          layoutServi: ctx?.geometrie?.roof_layout ?? null, // R2-04 — identique au document servi : rien à reprendre
        }).then((serveur) => { if (!cancelled && serveur) setBrouillonPropose(serveur) })
      }
      // ACAL84 — le bandeau ne BLOQUE plus le chargement (ANON-08) : l'atelier
      // boote sur la conception serveur ; « rien n'est réhydraté sans le
      // geste » reste vrai (Reprendre recharge sur le brouillon, Ignorer ne
      // fait que fermer le bandeau).
      if (!cancelled && brouillon) setBrouillonPropose(brouillon)
      await poursuivreBootCalepinage(undefined)
    }

    if (estCalepinage) bootCalepinage()
    else boot()
    return () => { cancelled = true }
  })
  useEffect(() => demarrerBoot(), [cibleId, devisId, leadId, calepinageId,
    estCalepinage, reducedMotion, utilisateurCourantId])
  // ACAL1957 — après le 201 de « Générer le devis », la MÊME lecture du contexte : la cible lit le devis créé.
  const relireApresDevis = useEffectEvent(() => {
    lireContexte().then((res) => { if (res?.data) setContexte(res.data) }).catch(() => {})
  })
  useEffect(() => (estCalepinage ? ecouterDevisGenere(calepinageId, () => relireApresDevis()) : undefined),
    [calepinageId, estCalepinage])
  // Revue ACAL1946 — l'issue retenue de « Générer le devis » vit le temps de CET atelier : le quitter (la page se
  // démonte, y compris à la déconnexion), changer de calepinage ou d'utilisateur l'oublie.
  useEffect(() => (calepinageId ? () => oublierIssuesDevis(calepinageId) : undefined),
    [calepinageId, utilisateurCourantId])
}
