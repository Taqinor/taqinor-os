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
 *   3. UN SEUL bouton « Générer le devis » (ACAL335 : rien n'est envoyé ici) enchaîne :
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
import { useCallback, useEffect, useEffectEvent, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { X } from 'lucide-react'
import api from '../../api/axios'
import { store } from '../../store'
import crmApi from '../../api/crmApi'
// CAL37 — TROISIÈME mode du MÊME builder : un CALEPINAGE autonome (module
// `apps/calepinage`), c'est-à-dire sans devis exigé. Voir le bloc de
// commentaire de `bootCalepinage` plus bas.
import calepinageApi from '../../api/calepinageApi'
// Lot 2 critique #27 — lecture du calepinage d'un devis (fiche devis) quand la
// porte de résolution est refusée (403, droit de VOIR seulement).
import ventesApi from '../../api/ventesApi'
// Lot 2 critique #23 / #29 — LE décodeur des refus du pont devis (partagé
// avec « Générer / Resynchroniser le devis »).
import {
  MESSAGE_MOTIF_OBLIGATOIRE, bloquageElectrique, refusServeur,
} from '../../features/calepinage/refusDevis'
// Coque (22/11) — le mode calepinage s'ouvre dans l'atelier plein écran des maquettes (AtelierPanneaux,
// l'enregistrement et les groupes du constructeur y sont placés par `atelier/coque/AtelierCoque.jsx`).
import AtelierCoque from '../../features/calepinage/atelier/coque/AtelierCoque'
import InspecteurBuilder from '../../features/calepinage/atelier/InspecteurBuilder.jsx'
import AlertesEnregistrement from '../../features/calepinage/atelier/AlertesEnregistrement.jsx'
// CAL103 — le panneau de CALQUES de l'atelier (visibilité + opacité, ordre de rendu
// déterminé, état persisté par utilisateur). Additif : les bascules historiques
// (tracé client, photo réelle) restent en place et continuent de fonctionner.
// CAL180 — export « image HD » : rendu HORS ÉCRAN 2×/3× de la scène, rendu au
// navigateur. L'affiche client (`roof-image`) n'est pas touchée.
// CAL104 — vue 2D PLAN orthographique (cotée, nord en haut) + plein écran, montée en
// ONGLET à côté de la 3D : le plan PROJETTE ce que la 3D a posé, il ne re-pave rien.
// CALX65 — le bandeau qui NOMME laquelle des deux productions parle (estimation
// rapide du constructeur vs simulation) ; ne modifie AUCUN chiffre de la carte
// « Recommandation » (`rp9-results` ci-dessous), il se contente de la commenter.
import BandeauProvenanceProduction from '../../features/calepinage/production/BandeauProvenanceProduction'
import { suivreSimulationDuServeur } from '../../features/calepinage/production/simulationAuto' // ACAL1987
// CALX68 — brouillon LOCAL de l'atelier (mode calepinage) : minuterie/repli +
// bandeau de reprise. Logique pure, voir l'en-tête de ce module.
import { construireCle, creerGestionnaireBrouillon, effacerBrouillon, estPanneReseau, memoriserReprise } from '../../features/calepinage/brouillon'
import { ecrireOuRelire } from '../../features/calepinage/delaiReseau'
import { creerStockageMiroir, sansVue, empreinteSansVue, suivreGestes } from '../../features/calepinage/brouillonServeur' // ACAL400 ; H1 : sans l'état de vue ; ACAL1345
import { appliquerSectionEcrite } from '../../features/calepinage/useDocumentCalepinage' // ACAL1816
import { toastInfo } from '../../lib/toast'
// L2 — confirmation maison (APX17 : jamais une popup système) avant une écriture qui
// diverge de la cible vendue du devis.
import { useConfirmDialog } from '../../ui/confirm'
import ResumeAtelier from '../../features/calepinage/atelier/ResumeAtelier'
import { chiffrageAvecSimulation, useSimulationFraiche } from '../../features/calepinage/atelier/simulationFraiche' // T4-X2-006
import BandeauConceptionRapide from '../../features/calepinage/atelier/BandeauConceptionRapide' // ACAL1007
import { useDirtyGuard, confirmLeaveIfDirty } from '../../ui/useDirtyGuard'
import { reviserEtOuvrir } from '../../features/ventes/reviserDevis'
// L-MAP (fondateur 26/08/2026) — le contour dessiné par le client, VISIBLE sur
// la carte du calepinage 3D (voir ToitClientOverlay.jsx pour le pourquoi).
import { contourExploitable } from '../../features/crm/workspace/traceToit'
// VT13 — la photo réelle du toit calée en visite terrain (porte VT12).
import { normaliserTextureToit } from '../../features/crm/workspace/photoToit'
// CALX129 — bascule plein écran RÉVERSIBLE du conteneur de la scène 3D, MÊME
// mécanique que celle de `Vue2DPlan.jsx` (CAL104) — voir l'en-tête du module.
import {
  dataUrlToBlob, repereDuLead, contourUtilisableDuLead, httpMessage,
  stockageBrouillonLocal, stockageSessionLocal, formaterHeureBrouillon,
  messageRefusRepere, libelleEcartRepere, libelleCibleEstimee, phraseToitureLead,
  cibleActiveDuContexte, phraseSiteNonLocalise, estAtelierPompage,
} from '../../features/calepinage/atelier/contexteAtelier.js'
import BuilderDom from '../../features/calepinage/atelier/BuilderDom.jsx'
import OutilsVue from '../../features/calepinage/atelier/OutilsVue.jsx'
import OutilPosePompage from '../../features/calepinage/commun/OutilPosePompage.jsx'
import { useAtelierVues } from '../../features/calepinage/atelier/useAtelierVues.js'
import { useAtelierBoot, pousserAffectationAtelier, MESSAGE_ACCES_REFUSE } from '../../features/calepinage/atelier/useAtelierBoot.js'
import '../../styles/roofbuilder.css'
const MESSAGE_INTROUVABLE = 'Calepinage introuvable.' // = le texte posé par useAtelierBoot sur un 404
// T4-U4-027 — l'écriture du document : l'écran dit lui-même chaque refus (bannière 409, message sous la barre) — pas de toast.
const SANS_TOAST = { suppressErrorToast: true }
// T4-U4-027 — la phrase de l'écran quand le serveur n'en sert aucune (une seule phrase, en entier).
const MESSAGE_DOCUMENT_MODIFIE = 'La conception a été modifiée ailleurs (onglet, autre navigateur) : rien n’est écrasé — rechargez avant d’enregistrer.'
const MESSAGE_CATALOGUE_INDISPONIBLE = 'Catalogue des modules indisponible : rien n’est enregistré. « Réessayer » le relit sans perdre votre tracé.'
/** Lot 2 critique #23 — la conception est enregistrée, la resynchro du devis
 *  est refusée : le motif SERVEUR, jamais un « données invalides » générique. */
const messageResyncRefusee = (raison) => (
  `Conception enregistrée — devis NON resynchronisé : ${raison}`)
const MESSAGE_RESYNC_RESEAU = 'Conception enregistrée — resynchronisation du devis impossible (réseau)'
/** Revue du 26/11 (D-ACAL-73) — un devis envoyé ne se corrige que par la carte d'aperçu. */
const MESSAGE_DEVIS_ENVOYE_PAR_LA_CARTE = 'Le devis envoyé n’est pas modifié par l’enregistrement : '
  + '« Resynchroniser le devis » montre d’abord ce qui change, puis le corrige.'

function AtelierToiture({
  mode = 'lead', calepinageImpose = null, devisSynchronise = null, lectureSeuleImposee = false,
  varianteDuDevis = false,
}) {
  const { id: idParam } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  // L2 — confirmation maison (APX17) avant d'écrire un calepinage qui diverge de la
  // cible vendue du devis.
  const { confirm } = useConfirmDialog()
  // PV20 — deux modes sur le MÊME écran. `lead` (défaut) est le flux d'origine,
  // strictement inchangé ; `devis` démarre SUR un devis existant.
  // ACAL37 (D-ACAL-1) — l'ancien mode `devis` n'existe plus comme écrivain : la route
  // `/ventes/devis/:id/design` résout le CALEPINAGE lié (`ConceptionDuDevis`, plus bas)
  // et ouvre CE mode calepinage, avec `devisSynchronise` = le devis à resynchroniser.
  // Mode `calepinage` (CAL37) — TROISIÈME mode, MÊME écran et MÊME builder,
  // pour un CALEPINAGE du module autonome. La seule chose qu'il retire au mode
  // devis, c'est l'EXIGENCE d'un devis (décision fondateur D3 : un calepinage
  // sans devis est un objet de première classe).
  const estCalepinage = mode === 'calepinage'
  // Le mode d'ORIGINE (fiche lead). Écrit UNE fois : sans ce prédicat, chaque
  // bloc réservé au lead s'écrirait « ni devis, ni calepinage… » et le
  // prochain mode en oublierait mécaniquement un.
  // SOLMVP41 — le mode `ao` (affaire d'appel d'offres) est parti avec l'app ao
  // (Groupe SOLMVP) : aucune route ne passe plus `mode="ao"`.
  const estLead = !estCalepinage
  // Accepte /devis-design/:id ET ?lead=<id> (parité avec l'ancien lien public).
  const leadId = estLead ? (idParam || searchParams.get('lead') || '') : ''
  const devisId = devisSynchronise ? String(devisSynchronise) : ''
  const calepinageId = estCalepinage ? String(calepinageImpose || idParam || '') : ''
  const cibleId = estCalepinage ? calepinageId : leadId
  // ACON80 (D-ACON-2) — un second devis actif du lead, porté par une VARIANTE du
  // calepinage : le contexte (`?devis=`) sert la variante et son document (lu par
  // `conception_du_devis`, contrat calepinage_conception_du_devis.json), l'atelier l'enregistre.
  const paramsContexte = varianteDuDevis && devisId ? { devis: Number(devisId) } : null

  // ACAL209 — le mode lead ne lit plus de mesures en query params (pente/
  // orientation/longueur/largeur) : elles n'avaient aucun effet persistant. Le
  // bureau d'études ouvre le module Calepinage, onglet « Reprise de la visite ».

  const reducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  // État initial dérivé de la présence du leadId (évite un setState synchrone
  // dans l'effet) : sans identifiant, on affiche directement le message d'erreur.
  const [status, setStatus] = useState(() => {
    if (cibleId) {
      if (estCalepinage) return 'Chargement du calepinage…'
      return 'Chargement du lead…'
    }
    if (estCalepinage) return 'Aucun calepinage indiqué (identifiant manquant).'
    return 'Aucun lead indiqué (identifiant manquant).'
  })
  const [lead, setLead] = useState(null)
  // PV20 — contexte agrégé du devis (mode devis uniquement) : identité, cible,
  // `modifiable` + `raison_lecture_seule`. Toujours null en mode lead.
  const [contexte, setContexte] = useState(null)
  const [loadError, setLoadError] = useState(() => {
    if (cibleId) return null
    if (estCalepinage) return 'Aucun calepinage indiqué.'
    return 'Aucun lead indiqué.'
  })

  // API exposée par le builder (serializeLayout / snapshot), posée à onApiReady.
  const builderApi = useRef(null)

  // — État de la génération du devis —
  const [sending, setSending] = useState(false)
  // ACAL30 — le catalogue des modules n'a pas pu être lu : l'enregistrement est REFUSÉ
  // (jamais un retour silencieux au module par défaut 720 Wc).
  const [catalogueIndisponible, setCatalogueIndisponible] = useState(false)
  const [genError, setGenError] = useState(null)
  const [genStatus, setGenStatus] = useState(null)
  // L-SECT — ne porte plus que { reference } : le lien, le menu WhatsApp, le
  // mailto et le bouton copier ont quitté cet écran pour la fiche lead.
  const [deliver, setDeliver] = useState(null) // { reference }
  // PV21 — conflit 409 renvoyé par sync-layout : {detail, revision_possible}.
  // Le texte est TOUJOURS celui du serveur ; l'écran choisit seulement entre
  // l'encart « Réviser (v2) » et le bandeau de document clos.
  const [conflit, setConflit] = useState(null)
  // ACAL23 — 409 `document_modifie` du mode calepinage : la conception a été
  // modifiée AILLEURS (un onglet du rail, un autre navigateur) depuis que la
  // page l'a lue. DISTINCT du conflit verrou ci-dessus : rien n'est écrasé et
  // la seule sortie est « Recharger ». Texte = celui du serveur.
  const [documentModifie, setDocumentModifie] = useState(null)
  // ACAL192 (D-ACAL-13) — refus serveur d'un geste de repère (recentrer / garder), texte
  // du SERVEUR ; `repereEnCours` désactive les deux boutons pendant l'appel.
  const [repereErreur, setRepereErreur] = useState(null)
  const [repereEnCours, setRepereEnCours] = useState(false)
  // ACAL23 — le jeton d'écriture (empreinte « document », contrat
  // `calepinage_layout_section.json`) RENDU par la dernière écriture réussie ;
  // tant qu'aucune n'a eu lieu, c'est celui lu au boot (design-context,
  // `geometrie.empreinte_document`). Jamais `layout_hash`.
  const [empreinteEcrite, setEmpreinteEcrite] = useState(null)
  const empreinteDocument = empreinteEcrite
    ?? contexte?.geometrie?.empreinte_document ?? null
  // PVHEAL — avertissements renvoyés par l'enregistrement (kit non complété,
  // composant absent du catalogue, deux onduleurs…). Le TEXTE est celui du
  // serveur, jamais rédigé ici : sans cet affichage, le devis repartait amputé
  // en silence.
  const [avertissementsSync, setAvertissementsSync] = useState([])
  // Lot 2 critique #29 — refus électrique de la resynchro du devis lié :
  // `{detail, bloquants, derogationPossible, peutDeroger}` + le motif saisi.
  const [bloquageSync, setBloquageSync] = useState(null)
  const [motifDerogation, setMotifDerogation] = useState('')
  const [motifDerogationErreur, setMotifDerogationErreur] = useState(null)
  // ACAL87 — l'aperçu de toiture n'a pas pu être capturé (image vide) ou
  // téléversé : on le DIT, au lieu d'un « Conception enregistrée » muet.
  const [apercuMessage, setApercuMessage] = useState(null)
  // L-MAP — bascule d'affichage du calque « Toit dessiné par le client »
  // (rp9-chip, comme les autres bascules de l'écran). Défaut ON — le
  // fondateur veut le voir SANS geste supplémentaire ; le bouton ne sert
  // qu'à le masquer temporairement s'il gêne une lecture de la carte.
  const [toitClientVisible, setToitClientVisible] = useState(true)
  // O3 (revue adversariale 26/08) — `builderApi` est une REF : la poser
  // n'entraîne aucun re-rendu, donc un effet qui ne dépend que de
  // `toitClientVisible` peut s'exécuter AVANT que le builder soit prêt (clic
  // pendant le boot) et ne JAMAIS rattraper l'état voulu. Cet état, lui,
  // déclenche un re-rendu à l'arrivée de l'API — voir l'effet plus bas.
  const [builderReady, setBuilderReady] = useState(false)
  // CALX8 — MÊME objet que `builderApi.current`, mais en ÉTAT plutôt qu'en
  // ref : `react-hooks/refs` (v7) refuse désormais de lire `ref.current`
  // PENDANT le rendu (seuls les effets/gestionnaires le peuvent), et
  // `AtelierPanneaux` a besoin de l'OBJET — jamais de la ref nue, qui ne
  // change jamais d'identité et aurait fait voyager `undefined` pour
  // toujours (CALX8). Posé par les mêmes `onApiReady` que `builderApi.current`
  // ci-dessous, jamais lu ailleurs : tout le reste du fichier continue de lire
  // `builderApi.current` dans des effets/gestionnaires, où c'est autorisé.
  const [builderApiActuel, setBuilderApiActuel] = useState(null)
  // CAL103 — clé de persistance des calques : l'utilisateur connecté. Lu sur le store
  // (et non par `useSelector`) pour que cet écran reste montable SANS Provider, comme
  // le font déjà ses tests ; store indisponible ⇒ null ⇒ clé « anonyme », jamais une
  // exception.
  const utilisateurCourantId = useMemo(() => {
    try { return store.getState()?.auth?.user?.id ?? null } catch { return null }
  }, [])
  // CALX68 — intervalle d'autosauvegarde du brouillon, lu sur les réglages de
  // l'utilisateur connecté (MÊME patron `store.getState()` que
  // `utilisateurCourantId` ci-dessus, CAL103 — jamais un `useSelector`,
  // l'écran reste montable sans Provider). AUCUN réglage de ce nom n'existe
  // encore dans le produit aujourd'hui (grep `uxviews`/`reglages` sous
  // `frontend/src` : aucun réglage utilisateur numérique de ce type) — en son
  // ABSENCE, aucun nombre n'est inventé ici : la valeur reste `null` et
  // `creerGestionnaireBrouillon` (`features/calepinage/brouillon.js`) bascule
  // sur son repli « à chaque geste » (D-CALX 7).
  const intervalleBrouillonSecondes = useMemo(() => {
    try {
      const brut = store.getState()
        ?.auth?.user?.reglages?.calepinage?.brouillon_intervalle_secondes
      return Number.isFinite(brut) && brut > 0 ? brut : null
    } catch { return null }
  }, [])
  // CALX68 — brouillon LOCAL de l'atelier (mode calepinage). `hashBaseBrouillon`
  // est l'empreinte du layout SERVEUR lue à l'ouverture (voir `bootCalepinage`
  // et l'en-tête de `brouillon.js`) : elle change après chaque enregistrement
  // réussi, ce qui fait démarrer une minuterie/clé neuve et orpheline
  // l'ancien brouillon (jamais réhydraté par erreur). `brouillonPropose` porte
  // le brouillon TROUVÉ à l'ouverture, tant que l'utilisateur n'a pas choisi
  // « Reprendre » ou « Ignorer » — rien n'est réhydraté sans ce geste.
  // ACAL84 — `hashBaseBrouillon` est l'empreinte « document » SERVEUR
  // (design-context au boot, puis celle rendue par chaque écriture), jamais un
  // djb2 de l'objet client ; et le boot n'attend plus la décision (bandeau
  // non bloquant).
  const [hashBaseBrouillon, setHashBaseBrouillon] = useState(null)
  const [brouillonPropose, setBrouillonPropose] = useState(null)
  const gestionnaireBrouillonRef = useRef(null)
  const enregistrementEnVolRef = useRef(false) // T4-U4-025 — aucun brouillon pendant un enregistrement réel
  // ACAL85 — la scène est HYDRATÉE (`onHydrationTerminee`, posé par le boot dans
  // les trois modes). `onApiReady` arrive avant l'hydratation : toute référence
  // « non modifiée » (garde de sortie, amorce du brouillon) se prend APRÈS.
  const [sceneHydratee, setSceneHydratee] = useState(false)
  // T4-U4-013 — le site est-il localisé ? (suivi par l'atelier : provenance, `null` = non, `undefined` = document ancien)
  const [siteLocalise, setSiteLocalise] = useState(undefined)
  // ACAL311 (CI vague 10) — sans clé carte servie (`contexte.carte`), le boot s'arrête sur
  // « Carte indisponible » : AUCUNE scène n'est construite, `onHydrationTerminee` n'arrive
  // jamais. Générer / Resynchroniser restent alors CLIQUABLES (comme avant la garde) et
  // gardent `enregistrerAvant` : sans constructeur, l'enregistrement refuse (« Outil non
  // prêt ») et le bandeau `cal-devis-refus` le dit — rien n'est écrit ni envoyé au devis.
  const atelierSansCarte = !!contexte && !(contexte.carte?.available && contexte.carte?.maptilerKey)
  // ACAL85 — empreinte de la scène au boot (après hydratation) puis à chaque
  // enregistrement réussi ; `sceneModifiee` arme `useDirtyGuard`.
  const hashSceneReferenceRef = useRef(null)
  const gestesRef = useRef(null) // ACAL1661 — aucun geste depuis l'ouverture ⇒ rien à enregistrer (la référence suit la scène)
  const [sceneModifiee, setSceneModifiee] = useState(false)
  const [enregistreLe, setEnregistreLe] = useState(null) // ACAL399 — heure de la dernière réponse 2xx
  // ACAL868 — l'étape du rail (publiée par la coque) : son niveau expert ouvre les volets avancés du constructeur.
  const [etapeAtelier, setEtapeAtelier] = useState(null)
  // ACAL945 — hors ligne : l'écriture (même document, même empreinte) attend l'événement `online`, UNE fois.
  const [renvoiReseau, setRenvoiReseau] = useState(null)
  // WIR227/QJ25 — contour OSM du bâtiment épinglé (mode lead uniquement) :
  // message serveur (« Aucun bâtiment trouvé… ») quand Overpass ne renvoie
  // rien, jamais rédigé ici. Le tracé manuel reste toujours disponible.
  const [contourMessage, setContourMessage] = useState('')
  // VT13 — photo RÉELLE du toit du lead (visite terrain validée + calée), lue
  // par la porte VT12 `crmApi.getLeadPhotoToit` : {visite_id, url,
  // texture_calage}, les trois clés nulles quand il n'y a rien à montrer.
  // Elle se drape en calque de fond du contour (ToitClientOverlay) ; la
  // bascule « Photo réelle » la masque quand elle gêne la lecture du tracé.
  const [photoToitCharge, setPhotoToitCharge] = useState(null)
  const [photoToitVisible, setPhotoToitVisible] = useState(true)

  const {
    vue2d, setVue2d, plan2d, panId2d, ouvrirVue2d,
    hdBusy, hdMessage, exporterHd, gltfBusy, gltfMessage, exporterGltf,
    mapWrapRef, pleinEcran3d, basculerPleinEcran3d,
  } = useAtelierVues({ builderApi, calepinageId, devisId })

  // ── Boot : charge lead + config carte, puis initialise le builder ──────────
  useAtelierBoot({
    builderApi,
    calepinageId,
    cibleId,
    devisId,
    estCalepinage,
    leadId,
    paramsContexte,
    reducedMotion,
    setBrouillonPropose,
    setBuilderApiActuel,
    setBuilderReady,
    setCatalogueIndisponible,
    setContexte,
    setContourMessage,
    setHashBaseBrouillon,
    setLead,
    setLoadError,
    setSceneHydratee,
    setSiteLocalise,
    setRepereErreur,
    setStatus,
    utilisateurCourantId,
    // ACAL311 — la consommation proposée par le serveur (barème société), pour l'atelier.
    proposerConsommation: calepinageApi.calepinages.proposerConsommation,
  })

  // ── ACAL85 — GARDE DE SORTIE (les trois modes) ─────────────────────────────
  // `dirty` = hacherLayout(serializeLayout()) ≠ l'empreinte prise au boot (scène
  // hydratée) ou au dernier enregistrement réussi. La scène vit dans le
  // constructeur 3D, hors de React : un sondage léger la compare, et
  // `useDirtyGuard` (la garde commune, déjà adoptée par DevisGenerator) arme
  // `beforeunload` ; « Fermer » confirme par `confirmLeaveIfDirty`.
  const hacherScene = useCallback(() => {
    try {
      const layout = builderApi.current?.serializeLayout?.()
      return layout == null ? null : empreinteSansVue(layout) // H1 — regarder le soleil, ACAL1345 — choisir un pan : pas une modification
    } catch {
      return null
    }
  }, [])
  const sceneEstModifiee = useCallback(() => {
    const courant = hacherScene()
    if (courant === null) return false
    if (gestesRef.current && !gestesRef.current.aGeste()) { hashSceneReferenceRef.current = courant; return false } // ACAL1661
    if (hashSceneReferenceRef.current === null) {
      hashSceneReferenceRef.current = courant
      return false
    }
    return courant !== hashSceneReferenceRef.current
  }, [hacherScene])
  useEffect(() => { // ACAL1661 — le premier geste fige la référence d'AVANT lui
    if (!builderReady || !sceneHydratee) return undefined
    const suivi = suivreGestes(document, () => { hashSceneReferenceRef.current = hacherScene() })
    gestesRef.current = suivi
    return () => { suivi.arreter(); gestesRef.current = null }
  }, [builderReady, sceneHydratee, hacherScene])
  const marquerSceneEnregistree = (layout) => {
    try {
      hashSceneReferenceRef.current = layout == null ? hacherScene() : empreinteSansVue(layout)
    } catch (err) {
      // Référence inchangée.
      console.warn('ToitureDesign.marquerSceneEnregistree : référence de scène inchangée', err)
    }
    setSceneModifiee(false)
  }

  // CALX68 — décision du bandeau de reprise : « Reprendre » substitue le
  // layout du brouillon AVANT le boot du constructeur (le seul moment où
  // c'est possible — le builder n'expose aucune méthode de rechargement
  // post-boot) ; « Ignorer » (T4-X8-010 : « Effacer ce brouillon ») boote avec
  // le layout SERVEUR, sans y toucher — le document serveur reste intact dans
  // les deux cas.
  // ACAL84 — l'atelier a DÉJÀ booté sur la conception serveur (bandeau non
  // bloquant) : « Reprendre » mémorise le brouillon pour le PROCHAIN boot
  // (sessionStorage, consommé une fois par `useAtelierBoot`) puis recharge —
  // le seul moyen d'hydrater le constructeur sur un autre document.
  // « Effacer ce brouillon » ferme le bandeau ET efface ce brouillon (local et
  // copie serveur) : la conception serveur est déjà à l'écran (T4-X8-010).
  const reprendreBrouillon = () => {
    const brouillon = brouillonPropose
    if (!brouillon) return
    const ok = memoriserReprise(stockageSessionLocal(),
      { calepinageId, utilisateurId: utilisateurCourantId }, brouillon.layout)
    if (!ok) {
      setGenError('Reprise impossible : le stockage local de ce navigateur est indisponible.')
      return
    }
    setBrouillonPropose(null)
    window.location.reload()
  }
  // T4-B4-002 — catalogue illisible : « Réessayer » garde le tracé courant pour la reprise (même porte que
  // « Reprendre le brouillon ») puis recharge l'atelier, qui relit le catalogue. Jamais un message mort.
  const reessayerCatalogue = () => {
    let layout = null
    try { layout = builderApi.current?.serializeLayout?.() ?? null } catch { layout = null }
    if (layout != null) {
      memoriserReprise(stockageSessionLocal(), { calepinageId, utilisateurId: utilisateurCourantId }, layout)
    }
    window.location.reload()
  }
  const ignorerBrouillon = () => {
    setBrouillonPropose(null)
    // T4-X8-010 — « Effacer ce brouillon » efface CE brouillon pour de bon : la copie locale (sa clé, empreinte serveur de
    // l'ouverture) — sinon le bandeau revenait à chaque ouverture — et, ACAL400, la copie SERVEUR. De nouveaux gestes
    // écrivent un brouillon plus récent, qui relève le bandeau à l'ouverture suivante.
    effacerBrouillon(stockageBrouillonLocal(),
      construireCle({ calepinageId, utilisateurId: utilisateurCourantId, hashBase: hashBaseBrouillon }))
    Promise.resolve(calepinageApi.calepinages.effacerBrouillon?.(calepinageId)).catch(() => {})
  }

  // ACAL84 — en lecture seule, aucun brouillon n'est écrit : il n'y aurait
  // rien à reprendre (aucun enregistrement possible).
  // Lot 2 critique #27 — `lectureSeuleImposee` : l'utilisateur n'a que le
  // droit de VOIR (403 sur la porte de résolution) ; aucun brouillon non plus.
  // T4-U4-026 — un catalogue illisible se dit dès l'ouverture (avec « Réessayer »), pas seulement au clic sur Enregistrer.
  const erreurBarre = genError ?? (catalogueIndisponible ? MESSAGE_CATALOGUE_INDISPONIBLE : null)
  const lectureSeuleContexte = (contexte != null && !contexte.modifiable)
    || lectureSeuleImposee

  // CALX68 — le planificateur d'écriture du brouillon : démarre une fois le
  // constructeur prêt (`builderReady`) et une empreinte de base connue
  // (`hashBaseBrouillon`, posée par `bootCalepinage` — jamais avant, sans
  // quoi la clé serait fausse). `obtenirLayout` relit `serializeLayout()` —
  // LA MÊME fonction que « Enregistrer le calepinage » (CAL37) — donc un
  // brouillon repris est strictement au format d'un enregistrement normal.
  useEffect(() => {
    if (!estCalepinage || !builderReady || !sceneHydratee || !hashBaseBrouillon || loadError // H1 — chargement raté : aucun brouillon
      || lectureSeuleContexte) return undefined
    const gestionnaire = creerGestionnaireBrouillon({
      // ACAL400 — miroir : localStorage d'abord, copie serveur (autre poste).
      storage: creerStockageMiroir({
        base: stockageBrouillonLocal(), calepinageId,
        envoyer: calepinageApi.calepinages.envoyerBrouillon,
        effacer: calepinageApi.calepinages.effacerBrouillon,
      }),
      calepinageId,
      utilisateurId: utilisateurCourantId,
      hashBase: hashBaseBrouillon,
      intervalleSecondes: intervalleBrouillonSecondes,
      obtenirLayout: () => sansVue(builderApi.current?.serializeLayout?.() ?? null), // H1 — jamais un brouillon de vue
      enPause: () => builderApi.current?.ajoutDePanEnCours?.() === true, // ACAL1329 — rien avant le dernier point
      hacher: empreinteSansVue, // ACAL1345 — choisir un pan dans la liste n'écrit aucun brouillon
      enregistrementEnCours: () => enregistrementEnVolRef.current, // T4-U4-025
      referenceInitiale: () => hashSceneReferenceRef.current, // T4-U4-025 — clé neuve : référence = document enregistré
    })
    gestionnaireBrouillonRef.current = gestionnaire
    gestionnaire.demarrer()
    return () => {
      gestionnaire.arreter()
      if (gestionnaireBrouillonRef.current === gestionnaire) gestionnaireBrouillonRef.current = null
    }
  }, [estCalepinage, builderReady, sceneHydratee, calepinageId, utilisateurCourantId,
    hashBaseBrouillon, intervalleBrouillonSecondes, lectureSeuleContexte, loadError])

  // ACAL85 — la référence se prend sur la scène HYDRATÉE, puis un sondage
  // (1,5 s) tient `sceneModifiee` à jour. Rien en lecture seule (rien à perdre).
  useEffect(() => {
    if (!builderReady || !sceneHydratee || lectureSeuleContexte || loadError) return undefined
    if (hashSceneReferenceRef.current === null) hashSceneReferenceRef.current = hacherScene()
    const id = window.setInterval(() => setSceneModifiee(sceneEstModifiee()), 1500)
    return () => window.clearInterval(id)
  }, [builderReady, sceneHydratee, lectureSeuleContexte, hacherScene, sceneEstModifiee, loadError])
  useDirtyGuard(sceneModifiee && !lectureSeuleContexte && !loadError)

  // VT13 — la photo réelle du toit se demande sur le LEAD, jamais sur la
  // visite : mode lead (l'id de l'URL) ou mode devis QUAND le devis porte un
  // lead (`contexte.devis.lead`). L'échec est SILENCIEUX — sans photo, l'écran
  // est byte-identique à avant VT13.
  // CAL37 — mode calepinage : le lead est celui que le CALEPINAGE porte
  // (`calepinage.lead` du contexte, nul quand il est né d'un client seul).
  const leadPourPhoto = estCalepinage ? (contexte?.calepinage?.lead ?? null)
    : (leadId || null)
  // La texture est mémorisée AVEC l'id du lead : aucun `setState` synchrone
  // dans le corps de l'effet (react-hooks v7) et jamais la photo d'un lead
  // précédent — un id qui ne correspond plus n'est simplement pas lu.
  // R5D-N2 — un écran ne demande pas ce qu'il sait refusé : sans le droit de lire les leads (`crm_voir`, la permission de la
  // porte VT12 — un Technicien ne l'a pas), la photo n'est pas demandée (ni 403, ni toast à chaque ouverture, ni erreur de
  // console). Lue sur le store comme le reste de l'écran ; liste vide (compte hérité) ou store absent : on demande, le serveur juge.
  const droitLireLeads = () => {
    try {
      const permissions = store.getState()?.auth?.permissions
      return !Array.isArray(permissions) || permissions.length === 0 || permissions.includes('crm_voir')
    } catch { return true }
  }
  useEffect(() => {
    if (!leadPourPhoto || !droitLireLeads()) return undefined
    let annule = false
    crmApi.getLeadPhotoToit(leadPourPhoto)
      .then((res) => {
        if (!annule) {
          setPhotoToitCharge({
            leadId: leadPourPhoto, texture: normaliserTextureToit(res?.data),
          })
        }
      })
      .catch(() => {
        if (!annule) setPhotoToitCharge({ leadId: leadPourPhoto, texture: null })
      })
    return () => { annule = true }
  }, [leadPourPhoto])
  const photoToit = photoToitCharge && photoToitCharge.leadId === leadPourPhoto
    ? photoToitCharge.texture : null

  // L-MAP — la bascule (rp9-chip) pilote le calque GÉO-RÉFÉRENCÉ du builder,
  // pas seulement la légende React. O3 (revue adversariale 26/08) — sans
  // `builderReady` dans les dépendances, un clic PENDANT le boot (builder pas
  // encore prêt) était un no-op DÉFINITIF : `toitClientVisible` ne change
  // plus tant qu'on ne reclique pas, donc l'état voulu ne se rattrapait
  // jamais quand `builderApi.current` finissait par exister. `builderReady`
  // (état, pas ref) déclenche un re-rendu à l'arrivée de l'API et rejoue la
  // valeur COURANTE de `toitClientVisible` à ce moment-là.
  useEffect(() => {
    builderApi.current?.setReferenceContourVisible?.(toitClientVisible)
  }, [toitClientVisible, builderReady])

  // ACAL994 — après « Enregistrer », le contexte relu (rafraichirContexte) porte le chiffrage SERVI : la carte
  // Économies et le Total passent de l'estimation à la valeur du serveur. Mode lead : aucun chiffrage, rien à poser.
  // T4-X2-006 — la production SIMULÉE fraîche de la pose (relue après chaque enregistrement et tant que la simulation
  // automatique tourne) : le Total de la vue Expert la lit quand aucune conception ne la chiffre à cette taille.
  const p50Simulation = useSimulationFraiche(estCalepinage ? calepinageId : null, enregistreLe)
  useEffect(() => {
    // R2-13 — le compte « · K au devis » suit le devis relu ; `cible.panneaux` n'est celui du DEVIS que si `source === 'devis'`.
    if (estCalepinage && contexte) {
      const cibleActive = cibleActiveDuContexte(contexte) // QJR40 : jamais contexte.cible seul
      builderApi.current?.majChiffrage?.(chiffrageAvecSimulation(contexte.chiffrage ?? null, p50Simulation),
        cibleActive.source === 'devis' ? (cibleActive.panneaux ?? null) : null)
    }
  }, [contexte, builderReady, estCalepinage, p50Simulation])

  // ACAL83 — UNE fonction relit design-context après chaque enregistrement
  // réussi : `contexte` (geometrie, avertissements, modifiable, cible) n'était
  // posé qu'au boot, si bien que la note « calepinage automatique — à
  // vérifier » et son bouton Recommencer survivaient à l'enregistrement
  // jusqu'au F5. Mode lead : aucun contexte agrégé, rien à relire. Échec =
  // best-effort, l'écran garde le contexte précédent (jamais d'état inventé).
  const rafraichirContexte = async () => {
    try {
      let res = null
      if (estCalepinage && calepinageId) {
        res = await (paramsContexte
          ? calepinageApi.calepinages.designContext(calepinageId, paramsContexte)
          : calepinageApi.calepinages.designContext(calepinageId))
      } else {
        return
      }
      if (res?.data) {
        setContexte(res.data)
        // Le jeton relu au serveur fait foi (ACAL23) : plus besoin de celui
        // rendu par la dernière écriture.
        setEmpreinteEcrite(null)
      }
    } catch (err) {
      // Best-effort : le contexte précédent reste affiché.
      console.warn('ToitureDesign.rafraichirContexte : contexte non relu', err)
    }
  }

  // ACAL87 — capture (asynchrone : lue APRÈS un rendu réel, null si l'image est
  // entièrement transparente) puis téléversement de l'aperçu. Rend le message à
  // afficher, ou null quand tout a réussi. Un PNG vide n'est JAMAIS envoyé, et
  // l'échec d'envoi n'est plus avalé.
  const capturerEtEnvoyerApercu = async (apiTool, nomFichier, envoyer) => {
    let png = null
    try {
      png = await apiTool.snapshot?.()
    } catch {
      png = null
    }
    const blob = png ? dataUrlToBlob(png) : null
    if (!blob) {
      return 'Aperçu 3D non capturé — la conception est enregistrée, mais sans image de toiture.'
    }
    const form = new FormData()
    form.append('image', blob, nomFichier)
    try {
      await envoyer(form)
      return null
    } catch {
      return 'Aperçu 3D non envoyé — la conception est enregistrée, mais l’image de toiture n’a pas pu être téléversée.'
    }
  }

  // ── UN SEUL BOUTON : devis + snapshot + livraison ──────────────────────────
  const generer = async () => {
    if (sending) return
    setGenError(null)
    setApercuMessage(null) // ACAL87
    setAvertissementsSync([])
    const apiTool = builderApi.current
    if (!apiTool) {
      setGenError('Outil non prêt — tracez le toit puis réessayez.')
      return
    }
    setSending(true)
    setGenStatus('Génération du devis…')
    try {
      const layout = apiTool.serializeLayout(null, { engagerNumeros: true }) // suite ACAL1720 — seul l'enregistrement engage les numéros
      // 1) Crée le devis depuis le layout (cookie = auth, pas de Bearer).
      //    QJ17 — le backend renvoie 200 si un brouillon identique existe déjà
      //    (idempotency par lead + hash du layout), 201 pour un nouveau devis, et
      //    409 (ENF11, refus d'état) avec un message FR clair si la composition est invalide (catalogue
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

      // 2) ACAL97 — PLUS de re-POST du layout BRUT sur /ventes/devis/<id>/layout/ :
      //    from-layout (étape 1) range DÉJÀ la conception, ENRICHIE côté serveur
      //    (`_pans_geometry`…) ; ce second envoi « best-effort » l'écrasait.

      // 3) Capture le PNG de la 3D et l'envoie (multipart, best-effort).
      setGenStatus('Capture de la vue 3D…')
      setApercuMessage(await capturerEtEnvoyerApercu(apiTool, `devis-${devis.id}.png`,
        (form) => api.post(`/ventes/devis/${devis.id}/roof-image/`, form)))

      // 4) L-SECT — bascule sur le bloc de confirmation. L'envoi lui-même a
      //    quitté cet écran : il se fait depuis la fiche lead, onglet Devis,
      //    où le commercial choisit niveau / OTP / sections (voir blocLivraison).
      setDeliver({ reference: devis.reference })
      setGenStatus(null)
      setSending(false)
      setStatus(`Devis ${devis.reference} créé — à envoyer depuis la fiche lead.`)
      marquerSceneEnregistree(layout) // ACAL85
      await rafraichirContexte() // ACAL83 — no-op en mode lead (aucun contexte agrégé)
    } catch {
      setGenStatus(null)
      setGenError('Erreur réseau pendant la génération. Vérifiez votre connexion puis réessayez.')
      setSending(false)
    }
  }

  // ── CAL37 — MODE CALEPINAGE : enregistrement de la conception ──────────
  // MÊMES sémantiques d'enregistrement que le mode devis, MOINS le devis : le
  // document de conception se range sur le calepinage (`POST …/layout/`,
  // CAL18), le serveur y dépose une VERSION quand — et seulement quand — la
  // conception a changé, et répond `{inchange: true}` sinon. AUCUN statut
  // n'est écrit ici (règle #4) ; le devis, lui, se génère par son propre
  // bouton (CAL38), jamais en effet de bord d'un enregistrement.
  // ACAL94 — rend `true` quand la conception de l'écran est rangée (écrite ou
  // « inchangée »), `false` sinon : « Générer / Resynchroniser » l'appellent
  // AVANT leur geste serveur (prop `enregistrerAvant`), UNE seule fonction.
  // ACAL37 (D-ACAL-1) — flux `/ventes/devis/:id/design` : la conception est rangée sur le
  // CALEPINAGE, PUIS le devis est resynchronisé par l'enveloppe du module
  // (`calepinages/<id>/sync-devis/`, D02-T09) — jamais `ventesApi.syncDevisLayout`.
  // Serveur qui refuse (409 : devis accepté, refusé ou expiré, révisable ou clos ; un devis envoyé se corrige sur
  // place, tracé) : R2-23 — la conception EST enregistrée, on rend `{enregistre: true, devisModifie: false, motif}`
  // (motif = texte du serveur) pour que « Générer / Resynchroniser » le DISENT (BoutonDevis), jamais `false`.
  // ACON80 — la variante qui porte le devis synchronisé (servie par le contexte), ou null.
  const varianteId = paramsContexte ? (contexte?.variante?.id ?? null) : null
  const resynchroniserDevisLie = async (corps = {}) => {
    const refus = (motif) => ({ enregistre: true, devisModifie: false, motif })
    if (!devisSynchronise || !calepinageId) return true
    try {
      const res = await calepinageApi.calepinages.syncDevis(calepinageId,
        varianteId ? { ...corps, devis: Number(devisSynchronise) } : corps)
      const donnees = res?.data ?? {}
      setAvertissementsSync(Array.isArray(donnees.avertissements) ? donnees.avertissements : [])
      setBloquageSync(null)
      setMotifDerogation('')
      setMotifDerogationErreur(null)
      return true
    } catch (err) {
      const code = err?.response?.status
      const data = err?.response?.data
      if (code === 409) {
        const detail = data?.detail || 'Ce devis ne peut plus être resynchronisé.'
        setConflit({ detail, revision_possible: !!data?.revision_possible })
        return refus(detail)
      }
      // Lot 2 critique #23 — la conception EST enregistrée ; c'est la
      // resynchro du devis qui est refusée : le motif du SERVEUR, décodé par
      // le décodeur partagé (`refusDevis.js`), jamais « données invalides ».
      if (!code) {
        setGenError(MESSAGE_RESYNC_RESEAU)
        return refus('resynchronisation impossible (réseau)')
      }
      // Lot 2 critique #29 — refus ÉLECTRIQUE (422) : la liste des bloquants
      // et, pour un approbateur (`permissions.peut_deroger` SERVI), « Passer
      // outre » — la même règle que « Resynchroniser le devis ».
      const electrique = bloquageElectrique(err)
      if (electrique) {
        let peutDeroger = false
        try {
          const detail = await calepinageApi.calepinages.get(calepinageId)
          peutDeroger = !!detail?.data?.permissions?.peut_deroger
        } catch { peutDeroger = false }
        setBloquageSync({ ...electrique, peutDeroger })
        const motif = electrique.detail || refusServeur(err).message
        setGenError(messageResyncRefusee(motif))
        return refus(motif)
      }
      if (code === 400 && data?.derogation_electrique) {
        setMotifDerogationErreur(refusServeur(err).message)
        return refus(refusServeur(err).message)
      }
      const motif = refusServeur(err).message
      setGenError(messageResyncRefusee(motif))
      return refus(motif)
    }
  }

  // Lot 2 critique #29 — « Passer outre et resynchroniser » : la MÊME resynchro,
  // relancée avec `derogation_electrique: {motif}` (motif vide refusé sous le champ).
  const passerOutreSync = async () => {
    const saisi = motifDerogation.trim()
    if (!saisi) {
      setMotifDerogationErreur(MESSAGE_MOTIF_OBLIGATOIRE)
      return
    }
    setMotifDerogationErreur(null)
    setSending(true)
    try {
      const ok = await resynchroniserDevisLie({ derogation_electrique: { motif: saisi } })
      if (ok === true) {
        setGenError(null)
        setStatus('Devis resynchronisé (dérogation électrique consignée).')
      }
    } finally {
      setSending(false)
    }
  }

  // ACAL1275 — `{ silencieux: true }` (« Générer / Resynchroniser » : enregistrement préalable) : un document inchangé
  // ne montre pas « Aucun changement » avant la réponse du devis ; le bouton « Enregistrer » (événement) le garde.
  // ACAL1320 (D-ACAL-73) — `{ sansDevis: true }` (« Resynchroniser le devis ») : la conception est rangée, le devis lié
  // n'est PAS resynchronisé ici — il le sera après l'aperçu, à la confirmation (rien d'écrit au devis avant).
  // Revue du 26/11 (D-ACAL-73, « le dire AVANT ») — un devis lié ENVOYÉ n'est jamais corrigé par un enregistrement
  // (« Enregistrer », « Vérifier ») : la conception est rangée et l'écran renvoie à « Resynchroniser le devis », qui
  // montre ce qui change avant de corriger.
  const enregistrerCalepinage = async (options) => {
    const silencieux = options?.silencieux === true
    const devisEnvoye = !!devisSynchronise && contexte?.calepinage?.devis_lie?.statut === 'envoye'
    const sansDevis = options?.sansDevis === true || devisEnvoye
    const suiteEnvoye = devisEnvoye && options?.sansDevis !== true ? ` ${MESSAGE_DEVIS_ENVOYE_PAR_LA_CARTE}` : ''
    if (sending) return false
    setGenError(null)
    setApercuMessage(null) // ACAL87
    setConflit(null)
    setDocumentModifie(null)
    setAvertissementsSync([])
    setBloquageSync(null) // Lot 2 critique #29
    const apiTool = builderApi.current
    if (!apiTool) {
      setGenError('Outil non prêt — ajustez la conception puis réessayez.')
      return false
    }
    // ACAL311 (rejeu P5.5, vague 10) — `onApiReady` précède l'hydratation (faite au `load` de
    // la carte) : sérialiser AVANT réécrivait le document sans ses blocs relus (la
    // consommation au barème société disparaissait après F5 + Enregistrer). Rien n'est écrit
    // tant que la scène n'est pas hydratée.
    if (!sceneHydratee || loadError) { // H1 — chargement raté : jamais une scène vide écrite sur le vrai toit
      setGenError(loadError ? 'Le calepinage n’a pas pu être chargé : rien n’est enregistré. Cliquez sur « Réessayer ».' : 'Conception en cours de chargement : rien n’est enregistré, réessayez dans un instant.')
      return false
    }
    if (catalogueIndisponible) {
      setGenError(MESSAGE_CATALOGUE_INDISPONIBLE)
      return false
    }
    setSending(true)
    enregistrementEnVolRef.current = true // T4-U4-025
    setGenStatus('Enregistrement du calepinage…')
    try {
      const layout = apiTool.serializeLayout(null, { engagerNumeros: true }) // suite ACAL1720 — seul l'enregistrement engage les numéros
      let resultat
      let heureReponse = null
      try {
        // ACAL23 — l'écriture COMPLÈTE porte If-Match = l'empreinte « document »
        // lue au boot puis remplacée par celle de chaque réponse 2xx.
        const res = varianteId
          ? await calepinageApi.calepinages.modifierVariante(calepinageId, varianteId, { roof_layout: layout })
          // ACAL1905 — réponse trop lente : l'écran RELIT l'empreinte du serveur (l'écriture a pu aboutir) avant de parler.
          : await ecrireOuRelire(() => calepinageApi.calepinages
            .enregistrerLayoutCalepinageConditionnel(calepinageId, layout, empreinteDocument, SANS_TOAST), calepinageId, empreinteDocument,
          (relu) => relu != null && empreinteSansVue(relu) === empreinteSansVue(layout)) // la NÔTRE, pas celle d'un autre onglet
        resultat = varianteId ? {} : (res?.data ?? {})
        heureReponse = res?.headers?.date || new Date().toISOString() // ACAL399
      } catch (err) {
        const code = err?.response?.status
        const data = err?.response?.data
        setGenStatus(null)
        setSending(false)
        if (estPanneReseau(err)) {
          // ACAL945 — aucune réponse : le brouillon est écrit, jamais « erreur 0 », l'envoi repart au retour du réseau.
          gestionnaireBrouillonRef.current?.enregistrerMaintenant()
          setRenvoiReseau({ layout, empreinte: empreinteDocument })
          setGenStatus('Pas de réseau — enregistré sur ce téléphone, envoi automatique au retour du réseau.')
          return false
        }
        if (code === 409 && data?.code === 'document_modifie') {
          // ACAL23 — la conception a changé AILLEURS : rien n'est écrasé, et ce
          // n'est PAS le verrou (bannière distincte, seule sortie : Recharger).
          setDocumentModifie({
            detail: typeof data.detail === 'string' && data.detail.trim()
              ? data.detail : MESSAGE_DOCUMENT_MODIFIE,
          })
          return false
        }
        if (code === 409) {
          // Un calepinage dont le devis est parti chez le client : le motif
          // est celui du SERVEUR, jamais reformulé ici (`{detail}` ou le
          // `{roof_layout: [msg]}` du verrou).
          const motifVerrou = Array.isArray(data?.roof_layout)
            ? data.roof_layout[0] : data?.roof_layout
          setConflit({
            // ACAL44 — la forme RÉELLE du verrou est `{roof_layout: [motif]}` :
            // son motif passe EN PREMIER.
            detail: (typeof motifVerrou === 'string' && motifVerrou) || data?.detail
              || 'Ce calepinage ne peut plus être modifié.',
            revision_possible: false,
          })
          return false
        }
        // Le 400 de CAL18 NOMME son champ (`roof_layout`) : on affiche le
        // message du serveur tel quel plutôt qu'un « non enregistré » générique.
        const champ = data && typeof data === 'object' ? data.roof_layout : null
        setGenError(typeof champ === 'string' && champ.trim()
          ? champ : httpMessage(code ?? 0, data))
        return false
      }

      // ACAL23 — le jeton de la PROCHAINE écriture est celui que le serveur vient de rendre.
      if (resultat?.empreinte_document) setEmpreinteEcrite(resultat.empreinte_document)

      // ACAL286 — l'affectation servie a pu changer avec ce document : la teinte est relue.
      pousserAffectationAtelier(apiTool, calepinageId)

      // Même conception → ZÉRO écriture serveur, et on le DIT : aucune
      // version n'a été créée, rien ne doit prétendre le contraire.
      if (resultat?.inchange) {
        // CALX68 — le document POSTÉ est, par définition ici, celui que le
        // serveur sert déjà : le brouillon local ne porte donc plus rien de
        // plus récent, il s'efface (repli sur `layout` si `serializeLayout()`
        // n'est déjà plus joignable).
        gestionnaireBrouillonRef.current?.effacerEtAmorcer(sansVue(layout)) // T4-U4-025 — référence = document enregistré
        setHashBaseBrouillon(resultat?.empreinte_document || hashBaseBrouillon) // ACAL84
        if (!silencieux) toastInfo('Aucun changement')
        setGenStatus(null)
        setSending(false)
        setStatus(`Conception inchangée — le calepinage n’a pas bougé.${suiteEnvoye}`)
        marquerSceneEnregistree(layout) // ACAL85
        setEnregistreLe(heureReponse) // ACAL399
        await rafraichirContexte() // ACAL83
        return sansDevis ? true : resynchroniserDevisLie() // ACAL37 ; ACAL1320 : sansDevis
      }

      // L'aperçu de toiture, même patron que les autres modes (best-effort,
      // MÊME service de stockage MinIO — jamais un second magasin).
      setGenStatus('Capture de la vue 3D…')
      // ACON80 — l'aperçu d'une VARIANTE n'écrase jamais celui du calepinage.
      setApercuMessage(varianteId ? null : await capturerEtEnvoyerApercu(apiTool, `calepinage-${calepinageId}.png`,
        (form) => calepinageApi.calepinages.envoyerImage(calepinageId, form)))
      // CALX68 — enregistrement réussi : le brouillon local ne porte plus
      // rien de plus récent que le serveur, il s'efface. Le layout SERVEUR
      // vient de changer (nouvelle version) : son empreinte change avec lui,
      // ce qui fait démarrer une minuterie/clé neuve pour la suite de la
      // session (l'effet dédié plus haut réagit à `hashBaseBrouillon`).
      gestionnaireBrouillonRef.current?.effacerEtAmorcer(sansVue(layout)) // T4-U4-025 — référence = document enregistré
      // ACAL84 — la clé suivante est l'empreinte SERVEUR rendue par l'écriture.
      setHashBaseBrouillon(resultat?.empreinte_document || hashBaseBrouillon)
      setGenStatus(null)
      setSending(false)
      // R2-04 — `resultat.version` est l'identifiant GLOBAL de la version, pas son rang : jamais affiché.
      setStatus(`Conception enregistrée.${suiteEnvoye}`)
      // ACAL1987 — un seul déclencheur : le SERVEUR lance la simulation d'une pose complète. Le navigateur ne poste
      // plus `simuler/` ; il lit l'état servi et retient le job pour l'onglet Production.
      if (!varianteId) suivreSimulationDuServeur(calepinageId)

      marquerSceneEnregistree(layout) // ACAL85
      setEnregistreLe(heureReponse) // ACAL399
      await rafraichirContexte() // ACAL83
      return sansDevis ? true : resynchroniserDevisLie() // ACAL37 ; ACAL1320 : sansDevis
    } catch (err) {
      setGenStatus(null)
      // ACAL64 — un document que l'atelier REFUSE d'émettre (pans de même identifiant) porte
      // son propre message : on l'affiche tel quel, jamais « erreur réseau ».
      setGenError(err?.name === 'ErreurDocumentAtelier' && err.message
        ? err.message
        : 'Erreur réseau pendant l’enregistrement. Vérifiez votre connexion puis réessayez.')
      setSending(false)
      return false
    } finally {
      enregistrementEnVolRef.current = false // T4-U4-025
    }
  }

  // ACAL945 — le renvoi UNIQUE au retour du réseau : même document, même empreinte (un autre poste a écrit entre-temps ⇒ 409, bannière).
  const renvoyerApresPanne = useEffectEvent(async ({ layout, empreinte }) => {
    setRenvoiReseau(null)
    try {
      const res = await calepinageApi.calepinages.enregistrerLayoutCalepinageConditionnel(calepinageId, layout, empreinte, SANS_TOAST)
      const nouvelle = res?.data?.empreinte_document
      if (nouvelle) setEmpreinteEcrite(nouvelle)
      gestionnaireBrouillonRef.current?.effacer()
      setHashBaseBrouillon(nouvelle || hashBaseBrouillon)
      marquerSceneEnregistree(layout)
      setEnregistreLe(res?.headers?.date || new Date().toISOString())
      setGenStatus(null)
      setStatus('Conception enregistrée au retour du réseau.')
    } catch (err) {
      const data = err?.response?.data
      setGenStatus(null)
      if (err?.response?.status === 409 && data?.code === 'document_modifie') setDocumentModifie({ detail: data.detail || MESSAGE_DOCUMENT_MODIFIE })
      else setGenError(httpMessage(err?.response?.status ?? 0, data))
    }
  })
  useEffect(() => {
    if (!renvoiReseau) return undefined
    const surRetour = () => renvoyerApresPanne(renvoiReseau)
    window.addEventListener('online', surRetour, { once: true })
    return () => window.removeEventListener('online', surRetour)
  }, [renvoiReseau])

  // PV21 / ACAL93 — « Réviser (v2) » : le devis est figé (accepté, refusé ou expiré ; un
  // envoyé se corrige sur place), on en crée une NOUVELLE version (brouillon) et on rouvre la conception dessus.
  // UNE seule fonction de révision dans tout le produit : `reviserEtOuvrir`
  // (avertit d'un chantier en cours, dit l'échec du serveur) — jamais masquée
  // ni refusée (D-QJR5-2). Ici, la V2 s'ouvre sur sa CONCEPTION.
  const reviser = async (idDevis = devisId, reference = '') => {
    if (sending || !idDevis) return
    setSending(true)
    setGenError(null)
    setGenStatus('Création de la révision…')
    let v2 = null
    try {
      await reviserEtOuvrir({
        devis: { id: idDevis, reference },
        onApres: (nouveau) => { v2 = nouveau; setConflit(null) },
        navigate: () => { if (v2?.id != null) navigate(`/ventes/devis/${v2.id}/design`) },
      })
    } finally {
      setGenStatus(null)
      setSending(false)
    }
  }
  // ACAL93 — le devis à réviser depuis le bandeau « Lecture seule » : celui du
  // mode devis, ou le devis LIÉ du calepinage (contexte, ACAL36).
  const devisARevise = contexte?.calepinage?.devis_lie?.id != null
    ? { id: contexte.calepinage.devis_lie.id, reference: contexte.calepinage.devis_lie.reference ?? '' }
    : null

  // Fondateur 18/08 — bouton Fermer (X, haut-droite) : cette fenêtre de
  // calepinage 3D n'avait aucune sortie visible une fois ouverte (lead,
  // liste des devis, générateur, ou la nouvelle entrée « Conception 3D » du
  // nav Ventes en amènent tous ici par un `navigate()` SPA). `navigate(-1)`
  // referme exactement comme le geste qui a ouvert l'écran l'a amené — jamais
  // une cible en dur qui pourrait diverger d'un appelant à l'autre. Le tracé
  // en cours n'est jamais perdu silencieusement : rien n'est envoyé ici, on
  // quitte seulement la vue (comme un retour navigateur).
  // ACAL85 — une conception NON enregistrée n'est plus perdue en silence :
  // « Fermer » confirme d'abord (calcul frais au clic, pas seulement le sondage).
  const fermer = () => {
    const modifiee = sceneHydratee && !lectureSeuleContexte && sceneEstModifiee()
    confirmLeaveIfDirty(modifiee,
      'La conception porte des modifications non enregistrées — fermer quand même ?').then((ok) => ok && navigate(-1))
  }

  // ACAL23 — L'UNIQUE rechargement de l'atelier (relayé par le Rail à chaque
  // onglet, et porté par la bannière « modifiée ailleurs »). Le constructeur
  // n'a aucun rechargement post-boot : la page est rechargée, ce qui relit
  // design-context et le document serveur. Si la scène porte des
  // modifications non enregistrées (sérialisation ≠ base serveur), on
  // CONFIRME d'abord — sinon rechargement direct.
  const rechargerAtelier = async () => {
    // ACAL85 — MÊME mesure que la garde de sortie (référence = scène hydratée
    // ou dernier enregistrement), jamais l'empreinte serveur du brouillon.
    const modifiee = sceneHydratee && sceneEstModifiee()
    if (modifiee) {
      const ok = await confirm({
        title: 'Modifications non enregistrées',
        description: 'La scène porte des modifications non enregistrées : elles seront perdues. Recharger quand même ?',
        confirmLabel: 'Recharger quand même',
      })
      if (!ok) return
    }
    window.location.reload()
  }

  // ACAL23 — le document VIVANT confié aux onglets du Rail : le jeton
  // d'écriture courant, et la façon d'appliquer à la scène une section qu'un
  // onglet vient d'écrire (`layout/section/`) en reprenant le jeton rendu.
  // ACAL1816 — une section écrite est enregistrée : référence de scène reprise (si elle était propre).
  const documentVivant = useMemo(() => ({
    empreinte: empreinteDocument,
    appliquerSection: (cle, valeur, empreinteApres) => appliquerSectionEcrite({
      appliquerALaScene: (c, v) => builderApi.current?.appliquerSection?.(c, v),
      poserEmpreinte: setEmpreinteEcrite,
      sceneModifiee: () => sceneHydratee && sceneEstModifiee(),
      rebaserScene: () => {
        hashSceneReferenceRef.current = hacherScene()
        setSceneModifiee(false)
        setEnregistreLe(new Date().toISOString())
      },
    }, cle, valeur, empreinteApres),
  }), [empreinteDocument, sceneHydratee, sceneEstModifiee, hacherScene])

  // PVHEAL — le bandeau d'avertissements du serveur, partagé par les deux
  // modes. Il reste affiché APRÈS le passage au bloc « Prêt à envoyer » : un
  // kit incomplet doit se voir au moment où l'on s'apprête à envoyer.
  const blocAvertissements = () => (
    avertissementsSync.length > 0 && (
      <div className="mt-4 border border-brass-400/40 p-4" data-testid="pvheal-avertissements">
        <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">À vérifier</p>
        <ul className="mt-2 space-y-1 text-sm text-foreground" role="status">
          {avertissementsSync.map((a) => <li key={a}>{a}</li>)}
        </ul>
      </div>
    )
  )

  const leadLabel = lead ? `${lead.nom ?? ''} ${lead.prenom ?? ''}`.trim() : ''
  // PV20 — en mode devis, le titre porte la référence + le client servis par le
  // contexte ; en lecture seule, le motif AFFICHÉ est celui du serveur.
  // ACAL37 — l'en-tête DEVIS du flux `/ventes/devis/:id/design` est lu sur le devis LIÉ
  // du calepinage (`calepinage.devis_lie`, contexte ACAL36), jamais recomposé.
  const devisLie = devisSynchronise ? (contexte?.calepinage?.devis_lie ?? null) : null
  const devisLabel = (devisLie?.client_nom ?? '').trim()
  const devisReference = devisLie?.reference ?? ''
  // CAL37 — le titre du calepinage est celui que le serveur sert ; il n'y a
  // AUCUNE référence inventée côté écran (un calepinage neuf s'appelle
  // « Calepinage sans titre » côté serveur, pas ici).
  const calepinageTitre = (contexte?.calepinage?.titre ?? '').trim()
  const lectureSeule = estCalepinage
    && ((contexte != null && !contexte.modifiable) || lectureSeuleImposee)
  const raisonLectureSeule = (contexte?.raison_lecture_seule ?? '').trim()
    || (lectureSeuleImposee ? RAISON_LECTURE_SEULE_DROIT : '')
  const avertissements = Array.isArray(contexte?.avertissements)
    ? contexte.avertissements : []
  // ACAL192 (D-ACAL-13) — le GPS du lead a été corrigé APRÈS le tracé et l'épingle a été
  // posée à la main (ou sa provenance est inconnue) : le serveur dit « a_decider », la
  // bannière OFFRE les deux gestes. « automatique » est traité au boot (recentrage d'office),
  // « aucune » n'affiche rien. Toute translation est décidée par le SERVEUR.
  // ACAL195 — refus nommé du moteur, affiché tel quel. ACAL1805 — une cible estimée SANS refus n'ouvre plus de bande
  // (absente des maquettes v2) : elle se lit dans la pilule « Besoin d'après la facture » de l'étape Toit.
  const cibleEstimee = estCalepinage && contexte?.cible?.refus
    ? libelleCibleEstimee(contexte?.cible, { sansLead: !contexte?.calepinage?.lead }) : null // T4-X9-013
  const toitureLead = estCalepinage ? phraseToitureLead(contexte?.toiture_lead) : null // R2-15 — lecture seule
  const deriveRepere = estCalepinage ? contexte?.geometrie?.derive?.etat ?? null : null
  const ecartRepere = libelleEcartRepere(contexte?.geometrie?.ecart_m)
  const gesteRepere = async (geste) => {
    if (!calepinageId || repereEnCours) return
    setRepereEnCours(true)
    setRepereErreur(null)
    try {
      await geste(calepinageId)
    } catch (err) {
      setRepereErreur(messageRefusRepere(err?.response?.data))
      setRepereEnCours(false)
      return
    }
    // La conception a changé CÔTÉ SERVEUR (nouvelle version) : l'atelier repart du
    // document relu — la carte se recentre sur la nouvelle épingle.
    window.location.reload()
  }

  // Correction fondateur 24/08 — sans AUCUNE position (ni pin posé, ni GPS de
  // fiche), la carte reste au niveau Maroc : comportement inchangé, mais on le
  // DIT discrètement plutôt que de laisser deviner pourquoi la carte est loin
  // de chez le client. Mode AO non concerné (affaire, pas de repli GPS ici).
  const sansPositionGps = !loadError && (
    (estLead && !!lead && !repereDuLead(lead))
    || (estCalepinage && !!contexte && !contexte?.geometrie?.pin && siteLocalise === undefined)
  )
  // T4-U4-013 — calepinage : l'atelier SAIT que personne n'a localisé le site (tracé à l'échelle
  // du pays, aucune adresse retenue) ; le bandeau le dit avec le geste, et s'efface dès qu'il est fait.
  const siteNonLocalise = !loadError && estCalepinage && siteLocalise === null

  const inputClass =
    'w-full border border-border bg-muted px-3 py-3 text-base text-foreground outline-none focus:border-brass-400'
  const chipClass = 'rp9-chip'

  // L-MAP (fondateur 26/08/2026) — le contour BRUT du client, tel quel
  // ([lat, lng] × n, la forme de `Lead.roof_outline`) : en mode lead, le lead
  // fraîchement chargé le porte directement ; en mode devis, le contexte
  // agrégé le porte SÉPARÉMENT de `geometrie.outline` (qui peut déjà être le
  // contour COURANT du calepinage, une fois édité — voir
  // `contexte_conception_devis`, apps/ventes/selectors.py). Mode AO : aucune
  // source (les affaires ne portent pas de dessin du tunnel public) — le
  // calque reste absent, comportement inchangé.
  // CAL37 — le contexte calepinage porte `contour_client` à la MÊME place et
  // sous le MÊME nom que le contexte devis (contrat jumeau) : aucune clé n'est
  // devinée, et un contour absent vaut `[]`, que `contourExploitable` refuse.
  const contourClientBrut = estCalepinage
    ? (contexte?.geometrie?.contour_client ?? null)
    : (estLead ? (lead?.roof_outline ?? null) : null)
  const toitClientPresent = useMemo(
    () => contourExploitable(contourClientBrut), [contourClientBrut])

  // AP-F2 (fondateur 26/08/2026) — note « calepinage automatique » : visible quand
  // les panneaux à l'écran viennent d'un SEMIS AUTOMATIQUE depuis le tracé client
  // (roofPro11 applyHydration / applyDevisHydration, repli lead-like), jamais d'un
  // calepinage enregistré par un commercial — celui-ci reste libre de VÉRIFIER avant
  // d'envoyer. Mode lead : dès qu'un contour exploitable existe — MÊME garde que la
  // bascule L-MAP (`toitClientPresent`), jamais un second prédicat. Mode devis :
  // seulement si le devis n'a JAMAIS reçu de design enregistré (`roof_layout` sans
  // zones — sinon un commercial a déjà calepiné et rien ne doit le recouvrir) ET
  // qu'un contour exploitable existe (`contour_client`, sinon `outline` — même repli
  // que le serveur quand `roof_layout` est absent, apps/ventes/selectors.py). Mode
  // AO : jamais affichée (hors périmètre — une affaire n'a pas de tunnel public).
  // AP2 — un devis créé AUTOMATIQUEMENT à l'arrivée du lead porte désormais la zone
  // du client DANS son layout (apps/ventes/services.zone_toit_depuis_contour), donc
  // `zones` n'est plus vide alors que PERSONNE n'a validé ce calepinage : le serveur
  // l'estampille `_origine_calepinage: 'contour_client'`. Ce marqueur disparaît dès
  // que le commercial enregistre sa conception (`sync-layout` REMPLACE le layout par
  // la sérialisation du builder, qui ne l'émet jamais) — c'est exactement le moment
  // où la note doit s'éteindre.
  const layoutPoseAutomatiquement =
    contexte?.geometrie?.roof_layout?._origine_calepinage === 'contour_client'
  const devisRoofLayoutSansZones = !(contexte?.geometrie?.roof_layout?.zones?.length > 0)
  const contourClientOuOutlinePourNote = contourExploitable(contexte?.geometrie?.contour_client)
    ? contexte?.geometrie?.contour_client
    : contexte?.geometrie?.outline
  // CAL37 — le mode calepinage suit la règle du mode DEVIS, pas celle du mode
  // lead : son contexte porte aussi `geometrie.roof_layout`, donc dès qu'une
  // conception avec zones existe, quelqu'un a déjà calepiné et la note
  // « automatique » n'a plus lieu d'être.
  const calepinageAutomatiqueVisible = estCalepinage
    ? (layoutPoseAutomatiquement
      || (devisRoofLayoutSansZones && contourExploitable(contourClientOuOutlinePourNote)))
    : (estLead && toitClientPresent && contourUtilisableDuLead(lead))
  // Le bouton « Recommencer » relit `opts.referenceContour`, c'est-à-dire le contour
  // CLIENT et lui seul : il n'est proposé que si ce contour-là existe encore. Sans ce
  // garde-fou la branche `layoutPoseAutomatiquement` pourrait afficher un bouton
  // inerte (layout estampillé, mais tracé du lead effacé depuis).
  const recommencerDisponible = estCalepinage
    ? contourExploitable(contexte?.geometrie?.contour_client)
    : (estLead && toitClientPresent && contourUtilisableDuLead(lead))

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
  const leadFiche = lead?.id ?? (leadId || null)
  const blocLivraison = () => (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Conception enregistrée</p>
        <p className="text-sm text-foreground">Devis <span className="font-semibold text-foreground">{deliver.reference}</span></p>
      </div>
      <p className="text-sm text-foreground">
        Le devis est créé et la vue 3D enregistrée.
        {' '}
        L’envoi au client se fait depuis la fiche lead, onglet Devis : c’est là
        que vous choisissez le niveau, le code de lecture et les sections que le
        client reçoit.
      </p>
      {leadFiche && (
        <Link
          to={`/crm/leads/${leadFiche}`}
          data-testid="rp9-vers-fiche-lead"
          className="inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-primary-text"
        >
          Ouvrir la fiche lead
        </Link>
      )}
    </div>
  )

  // R2-20 — un compte sans droit sur le calepinage (403) : le message DIT le refus, aucun outil d'édition n'est monté.
  // ACAL1246 — un 404 (« Calepinage introuvable. », texte de `useAtelierBoot`) : MÊME écran sans outils, hook propre.
  const refusOuIntrouvable = estCalepinage && (loadError === MESSAGE_ACCES_REFUSE || loadError === MESSAGE_INTROUVABLE)
  if (refusOuIntrouvable) {
    return (
      <div className="rp9-host">
        <div className="rp9-topbar">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Interne · conception toiture</p>
          <button type="button" onClick={fermer} className="rp9-close"
            aria-label="Fermer la conception 3D" data-testid="rp9-fermer">
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>
        <p className="mt-6 text-sm text-destructive" role="alert" data-testid={loadError === MESSAGE_ACCES_REFUSE ? 'cal-acces-refuse' : 'cal-introuvable'}>{loadError}</p>
      </div>
    )
  }

  // Coque (22/11) — les bandeaux d'état et la note « calepinage automatique » : MÊMES blocs pour les deux
  // écrans (le lead les garde dans sa colonne, la coque du module en tête de son panneau d'étape).
  const bandeaux = (
    <>
        <p className={estCalepinage ? 'sr-only' : 'mt-2 text-sm text-muted-foreground'} aria-live="polite">{status}</p>
        {apercuMessage && (
          <p className="mt-1 text-sm text-primary-text" role="status" data-testid="apercu-3d-avertissement">
            {apercuMessage}
          </p>
        )}

        {/* CALX68 — LE BANDEAU DE REPRISE DE BROUILLON. N'existe QUE tant que
            l'utilisateur n'a pas choisi. ACAL84 — NON BLOQUANT : l'atelier a
            déjà booté sur la conception serveur ; « Reprendre » recharge sur
            le brouillon, « Effacer ce brouillon » l'efface — « rien n'est
            réhydraté sans le geste ». */}
        {estCalepinage && brouillonPropose && (
          <div className="rounded-xl border border-border bg-card mt-4 border-brass-400/40 p-4"
            data-testid="cal-brouillon-bandeau">
            <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">
              {brouillonPropose.serveur ? 'Brouillon d’un autre poste' : 'Brouillon local'}
            </p>
            <p className="mt-1 text-sm text-foreground" role="status">
              Un brouillon non enregistré du{' '}
              {formaterHeureBrouillon(brouillonPropose.horodatage)} a été
              trouvé {brouillonPropose.serveur ? 'sur le serveur (enregistré par votre compte depuis un autre poste)' : 'sur cet appareil'} — reprendre où vous en étiez, ou
              l’effacer et garder la dernière conception enregistrée.
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={reprendreBrouillon}
                data-testid="cal-brouillon-reprendre"
                className="inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-primary-text"
              >
                {`Reprendre le brouillon du ${formaterHeureBrouillon(brouillonPropose.horodatage)}`}
              </button>
              <button
                type="button"
                onClick={ignorerBrouillon}
                data-testid="cal-brouillon-ignorer"
                className="inline-flex items-center gap-2 px-5 py-3 text-base font-semibold text-muted-foreground"
              >
                Effacer ce brouillon
              </button>
            </div>
          </div>
        )}

        {/* Correction fondateur 24/08 — discret, jamais bloquant : dit
            pourquoi la carte reste au niveau Maroc quand ni épingle ni GPS
            de fiche n'existent, plutôt que de laisser deviner. */}
        {sansPositionGps && (
          <p className="mt-1 text-xs text-muted-foreground/70" data-testid="pv-sans-gps">
            Pas de position GPS sur la fiche — carte au niveau Maroc.
          </p>
        )}
        {siteNonLocalise && (
          <p className="mt-1 text-sm text-foreground" role="status" data-testid="pv-sans-gps">
            {phraseSiteNonLocalise(contexte?.calepinage?.site_de_repli)}
          </p>
        )}

        {/* WIR227/QJ25 — le contour OSM n'a rien renvoyé pour cette épingle
            (message SERVEUR, jamais rédigé ici) : le tracé manuel reste
            disponible, un bouton relance simplement une nouvelle tentative
            (l'atelier n'a pas d'API pour injecter un contour a posteriori —
            même patron de rechargement que `window.__taqinorRoofBooted`). */}
        {estLead && contourMessage && (
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground/70" data-testid="pv-contour-osm-absent">
            <p>{contourMessage}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="underline"
            >
              Relancer la détection du contour
            </button>
          </div>
        )}

        {loadError && (
          <p className="mt-3 text-sm text-destructive" role="alert" data-testid="cal-erreur-chargement">{loadError}{estCalepinage && <> Rien n’a été modifié. <button type="button" className="ml-2 font-semibold underline" data-testid="cal-reessayer-chargement" onClick={() => window.location.reload()}>Réessayer</button></>}</p>
        )}

        {/* PV20 — LECTURE SEULE : le motif vient du serveur, jamais rédigé ici. */}
        {lectureSeule && (
          <div className="rounded-xl border border-border bg-card mt-6 border-brass-400/40 p-5" data-testid="pv20-lecture-seule">
            <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Lecture seule</p>
            <p className="mt-3 text-sm text-foreground" role="status">
              {raisonLectureSeule || (estCalepinage
                ? 'Ce calepinage ne peut plus être modifié.'
                : 'Ce devis ne peut plus être modifié.')}
            </p>
            {/* La visionneuse 3D plein écran est une route DEVIS
                (`/ventes/devis/:id/3d`) : hors mode devis elle n'existe pas,
                et un lien mort serait pire que pas de lien. */}
            {devisSynchronise && (
              <Link
                to={`/ventes/devis/${devisId}/3d`}
                className="mt-4 inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-primary-text"
              >
                Voir en 3D
              </Link>
            )}
            {/* ACAL93 — le serveur dit que la révision est possible : le
                bandeau l'OFFRE (jamais masquée par rôle, jamais refusée). */}
            {contexte?.revision_possible && devisARevise && (
              <button
                type="button"
                onClick={() => reviser(devisARevise.id, devisARevise.reference)}
                disabled={sending}
                data-testid="acal-reviser-lecture-seule"
                className="mt-4 ml-3 inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-primary-text disabled:cursor-not-allowed disabled:opacity-60"
              >
                Réviser (nouvelle version)
              </button>
            )}
          </div>
        )}

        {/* ACAL192 (D-ACAL-13) — GPS du lead corrigé après le tracé : décider. */}
        {deriveRepere === 'a_decider' && (
          <div className="rounded-xl border border-border bg-card mt-6 border-brass-400/40 p-5" data-testid="acal-derive-repere">
            <p className="text-sm text-primary-text" role="status">
              {`Le GPS du lead a été corrigé${ecartRepere ? ` (${ecartRepere})` : ''}.`}
            </p>
            <p className="mt-1 text-xs text-foreground">
              Recentrer déplace toute la conception sur le nouveau repère (une version est créée) ;
              garder conserve l’emplacement dessiné.
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => gesteRepere(calepinageApi.calepinages.recentrerSurLead)}
                disabled={repereEnCours || lectureSeule}
                data-testid="acal-derive-recentrer"
                className="inline-flex items-center border border-brass-400 px-4 py-2 text-sm font-semibold text-primary-text disabled:cursor-not-allowed disabled:opacity-60"
              >
                Recentrer sur le GPS du lead
              </button>
              <button
                type="button"
                onClick={() => gesteRepere(calepinageApi.calepinages.garderRepere)}
                disabled={repereEnCours || lectureSeule}
                data-testid="acal-derive-garder"
                className="inline-flex items-center border border-brass-400/60 px-4 py-2 text-sm font-semibold text-foreground disabled:cursor-not-allowed disabled:opacity-60"
              >
                Garder ce repère
              </button>
            </div>
          </div>
        )}
        {estCalepinage && repereErreur && (
          <p className="mt-3 text-sm text-destructive" role="alert" data-testid="acal-derive-erreur">
            {repereErreur}
          </p>
        )}

        {cibleEstimee && (
          <p className="mt-3 text-xs text-foreground" role="status" data-testid="acal-cible-estimee">
            {cibleEstimee}
            {/* ACAL965 — le refus n'est dit qu'une fois ; le lien mène à la fiche pour le corriger. */}
            {contexte?.cible?.refus && contexte?.calepinage?.lead != null && (
              <> <Link className="inline-flex min-h-11 items-center underline" to={`/crm/leads/${contexte.calepinage.lead}`}>Ouvrir la fiche du lead</Link></>
            )}
          </p>
        )}

        {/* R2-15 / R2-01 (Q1) — ce que le lead déclare de sa toiture, en lecture : rien n'en est prérempli. */}
        {toitureLead && (
          <p className="mt-3 text-xs text-muted-foreground" data-testid="acal-toiture-lead">
            {toitureLead}
            {contexte?.calepinage?.lead != null && (
              <> <Link className="inline-flex min-h-11 items-center underline" to={`/crm/leads/${contexte.calepinage.lead}`}>Voir la fiche du lead</Link></>
            )}
          </p>
        )}

        {/* PV20 — avertissements serveur (multi-villa, aucune ligne panneau…). */}
        {estCalepinage && avertissements.length > 0 && (
          <ul className="mt-4 space-y-1 text-xs text-muted-foreground" data-testid="pv20-avertissements">
            {avertissements.map((a) => <li key={a}>{a}</li>)}
          </ul>
        )}
    </>
  )
  const noteAuto = (
    <>
        {/* AP-F2 (fondateur 26/08/2026) — note explicite quand les panneaux à
            l'écran viennent d'un SEMIS AUTOMATIQUE depuis le tracé client, jamais
            d'un calepinage enregistré par un commercial (voir calepinageAutomatiqueVisible
            ci-dessus). Le bouton reseme la zone active depuis CE MÊME contour et relance
            l'optimiseur (roof-tool-pro11.ts recommencerDepuisTraceClient) — n'est rendu
            que si un contour exploitable existe (la condition de la note l'implique déjà). */}
        {calepinageAutomatiqueVisible && (
          <div
            className="mt-6 flex flex-wrap items-center justify-between gap-3 border border-brass-400/40 p-4"
            data-testid="rp9-calepinage-auto-note"
          >
            <p className="text-sm text-foreground" role="status">
              Calepinage automatique depuis le tracé client — à vérifier
            </p>
            {recommencerDisponible && (
              <button
                type="button"
                className={chipClass}
                onClick={() => builderApi.current?.recommencerDepuisTraceClient?.()}
                data-testid="rp9-recommencer-trace-client"
              >
                Recommencer depuis le tracé client
              </button>
            )}
          </div>
        )}
    </>
  )
  const proprietesBuilder = {
    expert: !!etapeAtelier?.expert, // ACAL869 — « Réglages avancés » ouvert d'office en expert
    basculerPleinEcran3d, chipClass, contourClientBrut, inputClass, mapWrapRef, photoToit, photoToitVisible,
    pleinEcran3d, setPhotoToitVisible, setToitClientVisible, toitClientPresent, toitClientVisible,
  }

  // Coque (22/11) — MODE CALEPINAGE (module et `/ventes/devis/:id/design`) : l'atelier plein écran des
  // maquettes. Les groupes du constructeur y sont montés une fois pour toute la session (jamais démontés).
  if (estCalepinage) {
    return (
      <AtelierCoque
        calepinageId={calepinageId} contexte={contexte} devisId={devisId} devisReference={devisReference}
        devisLabel={devisLabel} calepinageTitre={calepinageTitre} lectureSeule={lectureSeule}
        enregistrement={lectureSeule ? null : {
          libelle: devisSynchronise ? 'Enregistrer la conception' : 'Enregistrer le calepinage',
          enCours: sending, desactive: sending || !sceneHydratee || !!loadError, onEnregistrer: enregistrerCalepinage,
          modifiee: sceneModifiee && !loadError, enregistreLe, statut: genStatus, erreur: erreurBarre,
          refus: documentModifie ? 'Non enregistré : modifié ailleurs' : null, // T4-U4-027 — jamais « ✓ Enregistré » à côté du refus
          hydratee: sceneHydratee && !loadError, // T4-U4-016 — la barre ne lit le document qu'une fois la scène hydratée
          actionErreur: erreurBarre === MESSAGE_CATALOGUE_INDISPONIBLE ? { libelle: 'Réessayer', onClick: reessayerCatalogue } : null,
        }}
        proprietesBuilder={proprietesBuilder} enregistreLe={enregistreLe} onEtape={setEtapeAtelier} onFermer={fermer}
        ecranProps={{
          builderApi: builderApiActuel, onRecharger: rechargerAtelier,
          lectureSeule: lectureSeule || !!varianteId, documentVivant, contexte,
          // L'atelier charge (ou relance) encore son design-context : les étapes attendent, sans lecture à elles.
          contexteEnCours: contexte == null && !loadError,
        }}
        alertes={(
          <>
            {bandeaux}
            {estAtelierPompage(contexte) && (
              <OutilPosePompage contexte={contexte}
                phrase="Atelier d’un lead de pompage : un outil de pose seulement. Il n’affiche ni économies ni énergie du réseau ; la pose est limitée au champ de panneaux du devis agricole." />
            )}
            {noteAuto}
            <BandeauConceptionRapide calepinageId={calepinageId} rechargerLe={enregistreLe}
              onVerifier={lectureSeule || varianteId ? null : enregistrerCalepinage} />
            {!lectureSeule && (
              <AlertesEnregistrement bloquageSync={bloquageSync} motifDerogation={motifDerogation}
                setMotifDerogation={setMotifDerogation} motifDerogationErreur={motifDerogationErreur}
                setMotifDerogationErreur={setMotifDerogationErreur} passerOutreSync={passerOutreSync} sending={sending}
                documentModifie={documentModifie} rechargerAtelier={rechargerAtelier} conflit={conflit}
                devisId={devisId} reviser={reviser} devisReference={devisReference} />
            )}
          </>
        )}
        avance={(
          <>
        {/* CALX65 — sous la carte du constructeur, en mode calepinage
            UNIQUEMENT : dit laquelle des deux productions on regarde, sans
            jamais toucher un seul chiffre de `rp9-results` ci-dessus. */}
        {estCalepinage && calepinageId && !estAtelierPompage(contexte) && ( // ACAL1268 : aucun kWh de réseau pour un pompage
          <BandeauProvenanceProduction calepinageId={calepinageId} chiffrage={contexte?.chiffrage}
            devisLie={Boolean(contexte?.calepinage?.devis_lie || contexte?.calepinage?.devis || contexte?.variante?.devis)}
            variante={Boolean(contexte?.variante)} />
        )}
            <OutilsVue builderReady={builderReady} utilisateurCourantId={utilisateurCourantId}
              builderApiActuel={builderApiActuel} builderApi={builderApi} chipClass={chipClass}
              vue2d={vue2d} setVue2d={setVue2d} plan2d={plan2d} panId2d={panId2d} ouvrirVue2d={ouvrirVue2d}
              hdBusy={hdBusy} hdMessage={hdMessage} exporterHd={exporterHd}
              gltfBusy={gltfBusy} gltfMessage={gltfMessage} exporterGltf={exporterGltf} />
            {!estAtelierPompage(contexte) && (
              <ResumeAtelier calepinageId={calepinageId} rechargerLe={enregistreLe}
                lireLayout={() => (sceneHydratee ? builderApi.current?.serializeLayout?.() ?? null : null)} />
            )}
          </>
        )}
        atelierPanneaux={contexte && {
          // CALX8 — l'OBJET du constructeur (`builderApiActuel`, un état), jamais la ref nue.
          builderApi: builderApiActuel,
          // ACON80 — en mode variante, lecture seule jusqu'à ce que la route connaisse les variantes.
          lectureSeule: lectureSeule || !!varianteId, onRecharger: rechargerAtelier, documentVivant,
          // ACAL94 — Générer / Resynchroniser rangent d'abord l'écran ; Réviser sait s'il reste des retouches.
          enregistrerAvant: enregistrerCalepinage, aDesRetouches: () => sceneHydratee && sceneEstModifiee(),
          atelierPret: sceneHydratee || atelierSansCarte,
        }}
      />
    )
  }

  return (
    <div className="rp9-host">
      {/* Fondateur 18/08 — barre haute : le libellé d'origine à gauche, le
          bouton Fermer (X) à droite. Toujours présent, quel que soit le mode
          (lead/devis/AO) — c'est LE MÊME écran, jamais une fenêtre qu'on ne
          peut refermer que par le bouton retour du navigateur. */}
      <div className="rp9-topbar">
        <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Interne · conception toiture</p>
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
          {estLead && (
            <h1 className="display text-xl text-foreground sm:text-2xl">
              Lead <span className="text-primary-text">{leadId || '—'}</span> ·{' '}
              <span className="text-foreground">{leadLabel || '—'}</span>
            </h1>
          )}
        </div>
        {bandeaux}

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
        {estLead && (
        <div className="rounded-xl border border-border bg-card mt-6 p-5">
          <label htmlFor="rp9-bill" className="block text-sm text-foreground">
            Facture d'électricité moyenne par mois (MAD)
          </label>
          <div className="mt-2 flex items-center gap-3">
            <input id="rp9-bill" name="bill" type="text" inputMode="decimal" step="any"
              placeholder="ex. 1 500" className={`${inputClass} max-w-[12rem]`} />
            <span className="text-xs text-muted-foreground">≈ <span id="rp9-bill-kwh" className="fig">—</span> par an</span>
          </div>
        </div>
        )}

        {noteAuto}

        <BuilderDom {...proprietesBuilder} />
        <InspecteurBuilder estCalepinage={estCalepinage} />

        {/* UN SEUL BOUTON — génère le devis, capture la 3D, mint le lien.
            PV20 — mode lead UNIQUEMENT : un devis existant n'est jamais recréé
            depuis cet écran (sa boucle d'enregistrement arrive en PV21).
            Mode AO : une affaire ne « génère » aucun devis depuis la toiture —
            le devis d'un appel d'offres naît du BORDEREAU DES PRIX (action
            « Créer le devis » de l'écran Bordereau), pas d'un calepinage. */}
        {estLead && (
        <div className="rounded-xl border border-border bg-card mt-6 p-6">
          {!deliver ? (
            <div>
              <button type="button" onClick={generer} disabled={sending}
                className="inline-flex w-full items-center justify-center gap-3 bg-success px-6 py-4 text-base font-bold text-success-foreground disabled:cursor-not-allowed disabled:opacity-60"
>
                {sending && (
                  <span aria-hidden="true"
                    className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-border border-t-white"></span>
                )}
                <span>{sending ? 'Génération en cours…' : 'Générer le devis'}</span>
              </button>
              <p className="mt-3 text-xs text-muted-foreground">
                Un seul clic : le devis est créé et la vue 3D enregistrée ; l’envoi se fait depuis la fiche lead.
              </p>
              {genStatus && <p className="mt-3 text-sm text-foreground" aria-live="polite">{genStatus}</p>}
              {genError && <p className="mt-3 text-sm text-destructive" aria-live="assertive">{genError}</p>}
            </div>
          ) : blocLivraison()}
          {blocAvertissements()}
        </div>
        )}

        {/* CAL37 — MODE CALEPINAGE : l'UNIQUE emplacement des panneaux du
            module (cible servie par le serveur, comparatif des variantes, et
            les boutons que les tâches suivantes y accrochent). Rendu AUSSI en
            lecture seule : consulter une conception figée reste utile, seule
            l'écriture disparaît. */}
        <OutilsVue
          builderReady={builderReady}
          utilisateurCourantId={utilisateurCourantId}
          builderApiActuel={builderApiActuel}
          builderApi={builderApi}
          chipClass={chipClass}
          vue2d={vue2d} setVue2d={setVue2d} plan2d={plan2d} panId2d={panId2d}
          ouvrirVue2d={ouvrirVue2d}
          hdBusy={hdBusy} hdMessage={hdMessage} exporterHd={exporterHd}
          gltfBusy={gltfBusy} gltfMessage={gltfMessage} exporterGltf={exporterGltf}
        />

      </div>
    </div>
  )
}


/* ============================================================================
   ACAL37 (D-ACAL-1) — `/ventes/devis/:id/design` OUVRE LE CALEPINAGE LIÉ.
   ----------------------------------------------------------------------------
   Le calepinage est l'UNIQUE conception d'un devis : la route devis résout
   (ou crée / adopte) le calepinage lié par `POST calepinages/depuis-modele/
   {devis_id}` (porte `obtenir_ou_creer_pour_devis`, D02-T10), puis ouvre le
   MÊME atelier que le module calepinage — fond de plan, catalogue de modules,
   brouillon, versions — avec l'en-tête du devis et, après chaque
   enregistrement, la resynchronisation du devis (`sync-devis`). Plus aucune
   conception n'est éditée dans `Devis.roof_layout` depuis cet écran.
   ========================================================================== */
function messageResolution(err) {
  const code = err?.response?.status
  const data = err?.response?.data
  if (data && typeof data === 'object') {
    if (typeof data.detail === 'string' && data.detail.trim()) return data.detail.trim()
    const premier = Object.values(data).find((v) => v)
    if (premier) return Array.isArray(premier) ? premier.join(' ') : String(premier)
  }
  if (code === 404) return 'Devis introuvable.'
  return 'Impossible d’ouvrir la conception de ce devis — réessayez.'
}

/** Lot 2 critique #22 (ACAL92) — la notice d'un devis RÉVISÉ : la route d'une
 *  version remplacée ouvre la conception de la version EN VIGUEUR. */
const noticeDevisRevise = (reference) => (
  `Ce devis a été révisé — conception de la version en vigueur${reference ? ` (${reference})` : ''}`)

/** Lot 2 critique #27 (ACAL37) — un utilisateur qui n'a que le droit de VOIR
 *  ouvre la conception du devis en LECTURE SEULE, par une porte de lecture. */
const RAISON_LECTURE_SEULE_DROIT = 'Lecture seule : vous pouvez consulter cette conception, pas la modifier.'
const AUCUNE_CONCEPTION_LECTURE = 'Aucune conception pour ce devis — un utilisateur habilité doit la créer.'

function ConceptionDuDevis() {
  const { id: devisId } = useParams()
  const navigate = useNavigate()
  const [resolution, setResolution] = useState(() => (devisId
    ? { calepinageId: null, erreur: null }
    : { calepinageId: null, erreur: 'Aucun devis indiqué.' }))

  useEffect(() => {
    if (!devisId) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.depuisModele({ devis_id: Number(devisId) }))
      .then((res) => {
        if (annule) return
        const calepinageId = res?.data?.id ?? null
        // Lot 2 critique #22 (ACAL92) — le calepinage résolu est lié à une
        // AUTRE version (ce devis a été révisé, la conception suit la V2) :
        // jamais l'atelier éditable sous l'URL de la version remplacée.
        const lie = res?.data?.devis
        if (calepinageId && lie?.id != null && String(lie.id) !== String(devisId)) {
          // ACON80 — un second devis actif porté par une VARIANTE n'est pas une révision.
          Promise.resolve()
            .then(() => calepinageApi.calepinages.designContext(calepinageId, { devis: Number(devisId) }))
            .catch(() => null)
            .then((ctx) => {
              if (annule) return
              if (ctx?.data?.variante) {
                setResolution({ calepinageId, erreur: null, varianteDuDevis: true })
                return
              }
              toastInfo(noticeDevisRevise(lie.reference))
              navigate(`/ventes/devis/${lie.id}/design`, { replace: true })
            })
          return
        }
        setResolution(calepinageId
          ? { calepinageId, erreur: null }
          : { calepinageId: null, erreur: 'Impossible d’ouvrir la conception de ce devis — réessayez.' })
      })
      .catch((err) => {
        if (annule) return
        if (err?.response?.status !== 403) {
          setResolution({ calepinageId: null, erreur: messageResolution(err) })
          return
        }
        // Lot 2 critique #27 — la porte de résolution est une ÉCRITURE
        // possible (créer / adopter) : sans ce droit, le calepinage existant
        // est lu sur la fiche devis (`calepinage.id`, lecture), puis ouvert
        // en LECTURE SEULE. Aucune écriture n'est tentée.
        Promise.resolve(ventesApi.getDevisById(devisId))
          .then((res) => {
            if (annule) return
            const lu = res?.data?.calepinage?.id ?? null
            setResolution(lu
              ? { calepinageId: lu, erreur: null, lectureSeule: true }
              : { calepinageId: null, erreur: AUCUNE_CONCEPTION_LECTURE })
          })
          .catch((errLecture) => {
            if (!annule) setResolution({ calepinageId: null, erreur: messageResolution(errLecture) })
          })
      })
    return () => { annule = true }
  }, [devisId, navigate])

  if (resolution.calepinageId) {
    return (
      <AtelierToiture
        mode="calepinage"
        calepinageImpose={resolution.calepinageId}
        devisSynchronise={devisId}
        lectureSeuleImposee={!!resolution.lectureSeule}
        varianteDuDevis={!!resolution.varianteDuDevis}
      />
    )
  }
  return (
    <div className="rp9-host" data-testid="acal37-resolution">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Interne · conception toiture</p>
      {resolution.erreur
        ? <p className="mt-3 text-sm text-destructive" role="alert">{resolution.erreur}</p>
        : <p className="mt-3 text-sm text-muted-foreground" aria-live="polite">Ouverture de la conception du devis…</p>}
    </div>
  )
}

export default function ToitureDesign({ mode = 'lead', lectureSeuleImposee = false }) {
  if (mode === 'devis') return <ConceptionDuDevis />
  return <AtelierToiture mode={mode} lectureSeuleImposee={lectureSeuleImposee} />
}
