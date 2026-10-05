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
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { X } from 'lucide-react'
import api from '../../api/axios'
import { store } from '../../store'
import ventesApi from '../../api/ventesApi'
import crmApi from '../../api/crmApi'
// CAL37 — TROISIÈME mode du MÊME builder : un CALEPINAGE autonome (module
// `apps/calepinage`), c'est-à-dire sans devis exigé. Voir le bloc de
// commentaire de `bootCalepinage` plus bas.
import calepinageApi from '../../api/calepinageApi'
// CAL37 — l'UNIQUE emplacement où les tâches suivantes (CAL38 le bouton devis,
// CAL180 l'export image) posent leurs panneaux : aucune d'elles n'a donc à
// rouvrir ce fichier. SOLMVP15 a retiré CAL242 (reprise de contour AO) avec
// l'app ao (Groupe SOLMVP).
import AtelierPanneaux from '../../features/calepinage/AtelierPanneaux'
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
// CALX68 — brouillon LOCAL de l'atelier (mode calepinage) : minuterie/repli +
// bandeau de reprise. Logique pure, voir l'en-tête de ce module.
import { hacherLayout, creerGestionnaireBrouillon } from '../../features/calepinage/brouillon'
import { toastInfo } from '../../lib/toast'
// L2 — confirmation maison (APX17 : jamais une popup système) avant une écriture qui
// diverge de la cible vendue du devis (voir enregistrerConception ci-dessous).
import { useConfirmDialog } from '../../ui/confirm'
// L-MAP (fondateur 26/08/2026) — le contour dessiné par le client, VISIBLE sur
// la carte du calepinage 3D (voir ToitClientOverlay.jsx pour le pourquoi).
import { contourExploitable } from '../../features/crm/workspace/traceToit'
// VT13 — la photo réelle du toit calée en visite terrain (porte VT12).
import { normaliserTextureToit } from '../../features/crm/workspace/photoToit'
// CALX129 — bascule plein écran RÉVERSIBLE du conteneur de la scène 3D, MÊME
// mécanique que celle de `Vue2DPlan.jsx` (CAL104) — voir l'en-tête du module.
import {
  dataUrlToBlob, pinDepuisLead, cibleActiveDuContexte, httpMessage,
  stockageBrouillonLocal, formaterHeureBrouillon,
} from '../../features/calepinage/atelier/contexteAtelier.js'
import BuilderDom from '../../features/calepinage/atelier/BuilderDom.jsx'
import OutilsVue from '../../features/calepinage/atelier/OutilsVue.jsx'
import { useAtelierVues } from '../../features/calepinage/atelier/useAtelierVues.js'
import { useAtelierBoot, pousserAffectationAtelier } from '../../features/calepinage/atelier/useAtelierBoot.js'
import '../../styles/roofbuilder.css'

export default function ToitureDesign({ mode = 'lead' }) {
  const { id: idParam } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  // L2 — confirmation maison (APX17) avant d'écrire un calepinage qui diverge de la
  // cible vendue du devis — voir enregistrerConception.
  const { confirm } = useConfirmDialog()
  // PV20 — deux modes sur le MÊME écran. `lead` (défaut) est le flux d'origine,
  // strictement inchangé ; `devis` démarre SUR un devis existant.
  const estDevis = mode === 'devis'
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
  const estLead = !estDevis && !estCalepinage
  // Accepte /devis-design/:id ET ?lead=<id> (parité avec l'ancien lien public).
  const leadId = estLead ? (idParam || searchParams.get('lead') || '') : ''
  const devisId = estDevis ? (idParam || '') : ''
  const calepinageId = estCalepinage ? (idParam || '') : ''
  const cibleId = estDevis ? devisId
    : (estCalepinage ? calepinageId : leadId)

  // VT8 — mesures de la visite terrain, transmises en query params optionnels
  // par VisiteBureauEtudesPage.jsx (« Ouvrir l'atelier 3D »). `null` si
  // absent — jamais une valeur par défaut inventée pour un champ non mesuré.
  const mesuresVisiteTerrain = (estLead && (
    searchParams.get('pente') || searchParams.get('orientation')
    || searchParams.get('longueur') || searchParams.get('largeur')
  )) ? {
    pente: searchParams.get('pente'),
    orientation: searchParams.get('orientation'),
    longueur: searchParams.get('longueur'),
    largeur: searchParams.get('largeur'),
  } : null

  const reducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  // État initial dérivé de la présence du leadId (évite un setState synchrone
  // dans l'effet) : sans identifiant, on affiche directement le message d'erreur.
  const [status, setStatus] = useState(() => {
    if (cibleId) {
      if (estDevis) return 'Chargement du devis…'
      if (estCalepinage) return 'Chargement du calepinage…'
      return 'Chargement du lead…'
    }
    if (estDevis) return 'Aucun devis indiqué (identifiant manquant).'
    if (estCalepinage) return 'Aucun calepinage indiqué (identifiant manquant).'
    return 'Aucun lead indiqué (identifiant manquant).'
  })
  const [lead, setLead] = useState(null)
  // PV20 — contexte agrégé du devis (mode devis uniquement) : identité, cible,
  // `modifiable` + `raison_lecture_seule`. Toujours null en mode lead.
  const [contexte, setContexte] = useState(null)
  const [loadError, setLoadError] = useState(() => {
    if (cibleId) return null
    if (estDevis) return 'Aucun devis indiqué.'
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
  // PVHEAL — avertissements renvoyés par l'enregistrement (kit non complété,
  // composant absent du catalogue, deux onduleurs…). Le TEXTE est celui du
  // serveur, jamais rédigé ici : sans cet affichage, le devis repartait amputé
  // en silence.
  const [avertissementsSync, setAvertissementsSync] = useState([])
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
  // « Reprendre » ou « Ignorer » — rien n'est réhydraté sans ce geste : le
  // boot du constructeur ATTEND cette décision (voir `bootCalepinage`).
  const [hashBaseBrouillon, setHashBaseBrouillon] = useState(null)
  const [brouillonPropose, setBrouillonPropose] = useState(null)
  const gestionnaireBrouillonRef = useRef(null)
  const poursuivreBootRef = useRef(null)
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
    hdBusy, hdMessage, exporterHd,
    mapWrapRef, pleinEcran3d, basculerPleinEcran3d,
  } = useAtelierVues({ builderApi, calepinageId, devisId })

  // ── Boot : charge lead + config carte, puis initialise le builder ──────────
  useAtelierBoot({
    builderApi,
    calepinageId,
    cibleId,
    devisId,
    estCalepinage,
    estDevis,
    leadId,
    poursuivreBootRef,
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
    setStatus,
    utilisateurCourantId,
  })

  // CALX68 — décision du bandeau de reprise : « Reprendre » substitue le
  // layout du brouillon AVANT le boot du constructeur (le seul moment où
  // c'est possible — le builder n'expose aucune méthode de rechargement
  // post-boot) ; « Ignorer » boote avec le layout SERVEUR, sans y toucher —
  // le brouillon local n'est PAS effacé pour autant (seul un enregistrement
  // réussi l'efface, CALX68), mais le document serveur, lui, reste intact
  // dans les deux cas : ni l'un ni l'autre ne fait le moindre appel réseau.
  const reprendreBrouillon = async () => {
    const poursuivre = poursuivreBootRef.current
    const brouillon = brouillonPropose
    setBrouillonPropose(null)
    if (poursuivre && brouillon) await poursuivre(brouillon.layout)
  }
  const ignorerBrouillon = async () => {
    const poursuivre = poursuivreBootRef.current
    setBrouillonPropose(null)
    if (poursuivre) await poursuivre(undefined)
  }

  // CALX68 — le planificateur d'écriture du brouillon : démarre une fois le
  // constructeur prêt (`builderReady`) et une empreinte de base connue
  // (`hashBaseBrouillon`, posée par `bootCalepinage` — jamais avant, sans
  // quoi la clé serait fausse). `obtenirLayout` relit `serializeLayout()` —
  // LA MÊME fonction que « Enregistrer le calepinage » (CAL37) — donc un
  // brouillon repris est strictement au format d'un enregistrement normal.
  useEffect(() => {
    if (!estCalepinage || !builderReady || !hashBaseBrouillon) return undefined
    const gestionnaire = creerGestionnaireBrouillon({
      storage: stockageBrouillonLocal(),
      calepinageId,
      utilisateurId: utilisateurCourantId,
      hashBase: hashBaseBrouillon,
      intervalleSecondes: intervalleBrouillonSecondes,
      obtenirLayout: () => builderApi.current?.serializeLayout?.() ?? null,
    })
    gestionnaireBrouillonRef.current = gestionnaire
    gestionnaire.demarrer()
    return () => {
      gestionnaire.arreter()
      if (gestionnaireBrouillonRef.current === gestionnaire) gestionnaireBrouillonRef.current = null
    }
  }, [estCalepinage, builderReady, calepinageId, utilisateurCourantId,
    hashBaseBrouillon, intervalleBrouillonSecondes])

  // VT13 — la photo réelle du toit se demande sur le LEAD, jamais sur la
  // visite : mode lead (l'id de l'URL) ou mode devis QUAND le devis porte un
  // lead (`contexte.devis.lead`). L'échec est SILENCIEUX — sans photo, l'écran
  // est byte-identique à avant VT13.
  // CAL37 — mode calepinage : le lead est celui que le CALEPINAGE porte
  // (`calepinage.lead` du contexte, nul quand il est né d'un client seul).
  const leadPourPhoto = estDevis ? (contexte?.devis?.lead ?? null)
    : (estCalepinage ? (contexte?.calepinage?.lead ?? null)
      : (leadId || null))
  // La texture est mémorisée AVEC l'id du lead : aucun `setState` synchrone
  // dans le corps de l'effet (react-hooks v7) et jamais la photo d'un lead
  // précédent — un id qui ne correspond plus n'est simplement pas lu.
  useEffect(() => {
    if (!leadPourPhoto) return undefined
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
    // QJR40 — MÊME cible que celle booté dans le builder (cibleActiveDuContexte :
    // AVEC quand ce devis la sert, sinon `cible`). Comparer contre `contexte.cible`
    // seul recréerait ici la divergence SANS/AVEC que ce correctif supprime côté
    // boot : un devis « Les deux » déclencherait alors ce dialogue à CHAQUE
    // enregistrement, même sans aucun écart réel.
    const panneauxDevis = Number(cibleActiveDuContexte(contexte).panneaux) || 0
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

  // ── CAL37 — MODE CALEPINAGE : enregistrement de la conception ──────────
  // MÊMES sémantiques d'enregistrement que le mode devis, MOINS le devis : le
  // document de conception se range sur le calepinage (`POST …/layout/`,
  // CAL18), le serveur y dépose une VERSION quand — et seulement quand — la
  // conception a changé, et répond `{inchange: true}` sinon. AUCUN statut
  // n'est écrit ici (règle #4) ; le devis, lui, se génère par son propre
  // bouton (CAL38), jamais en effet de bord d'un enregistrement.
  const enregistrerCalepinage = async () => {
    if (sending) return
    setGenError(null)
    setConflit(null)
    setAvertissementsSync([])
    const apiTool = builderApi.current
    if (!apiTool) {
      setGenError('Outil non prêt — ajustez la conception puis réessayez.')
      return
    }
    if (catalogueIndisponible) {
      setGenError('Catalogue des modules indisponible : rien n’est enregistré, rechargez la page.')
      return
    }
    setSending(true)
    setGenStatus('Enregistrement du calepinage…')
    try {
      const layout = apiTool.serializeLayout()
      let resultat
      try {
        const res = await calepinageApi.calepinages
          .enregistrerLayoutCalepinage(calepinageId, layout)
        resultat = res?.data ?? {}
      } catch (err) {
        const code = err?.response?.status
        const data = err?.response?.data
        setGenStatus(null)
        setSending(false)
        if (code === 409) {
          // Un calepinage dont le devis est parti chez le client : le motif
          // est celui du SERVEUR, jamais reformulé ici.
          setConflit({
            detail: data?.detail || 'Ce calepinage ne peut plus être modifié.',
            revision_possible: false,
          })
          return
        }
        // Le 400 de CAL18 NOMME son champ (`roof_layout`) : on affiche le
        // message du serveur tel quel plutôt qu'un « non enregistré » générique.
        const champ = data && typeof data === 'object' ? data.roof_layout : null
        setGenError(typeof champ === 'string' && champ.trim()
          ? champ : httpMessage(code ?? 0, data))
        return
      }

      // ACAL286 — l'affectation servie a pu changer avec ce document : la teinte est relue.
      pousserAffectationAtelier(apiTool, calepinageId)

      // Même conception → ZÉRO écriture serveur, et on le DIT : aucune
      // version n'a été créée, rien ne doit prétendre le contraire.
      if (resultat?.inchange) {
        // CALX68 — le document POSTÉ est, par définition ici, celui que le
        // serveur sert déjà : le brouillon local ne porte donc plus rien de
        // plus récent, il s'efface (repli sur `layout` si `serializeLayout()`
        // n'est déjà plus joignable).
        gestionnaireBrouillonRef.current?.effacer()
        setHashBaseBrouillon(hacherLayout(layout))
        toastInfo('Aucun changement')
        setGenStatus(null)
        setSending(false)
        setStatus('Conception inchangée — le calepinage n’a pas bougé.')
        return
      }

      // L'aperçu de toiture, même patron que les autres modes (best-effort,
      // MÊME service de stockage MinIO — jamais un second magasin).
      setGenStatus('Capture de la vue 3D…')
      const png = apiTool.snapshot()
      if (png) {
        const blob = dataUrlToBlob(png)
        if (blob) {
          const form = new FormData()
          form.append('image', blob, `calepinage-${calepinageId}.png`)
          try {
            await calepinageApi.calepinages.envoyerImage(calepinageId, form)
          } catch { /* image best-effort */ }
        }
      }
      // CALX68 — enregistrement réussi : le brouillon local ne porte plus
      // rien de plus récent que le serveur, il s'efface. Le layout SERVEUR
      // vient de changer (nouvelle version) : son empreinte change avec lui,
      // ce qui fait démarrer une minuterie/clé neuve pour la suite de la
      // session (l'effet dédié plus haut réagit à `hashBaseBrouillon`).
      gestionnaireBrouillonRef.current?.effacer()
      setHashBaseBrouillon(hacherLayout(layout))
      setGenStatus(null)
      setSending(false)
      setStatus(
        resultat?.version
          ? `Conception enregistrée — version ${resultat.version}.`
          : 'Conception enregistrée.'
      )
    } catch (err) {
      setGenStatus(null)
      // ACAL64 — un document que l'atelier REFUSE d'émettre (pans de même identifiant) porte
      // son propre message : on l'affiche tel quel, jamais « erreur réseau ».
      setGenError(err?.name === 'ErreurDocumentAtelier' && err.message
        ? err.message
        : 'Erreur réseau pendant l’enregistrement. Vérifiez votre connexion puis réessayez.')
      setSending(false)
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
  // CAL37 — le titre du calepinage est celui que le serveur sert ; il n'y a
  // AUCUNE référence inventée côté écran (un calepinage neuf s'appelle
  // « Calepinage sans titre » côté serveur, pas ici).
  const calepinageTitre = (contexte?.calepinage?.titre ?? '').trim()
  const lectureSeule = (estDevis || estCalepinage)
    && contexte != null && !contexte.modifiable
  const raisonLectureSeule = (contexte?.raison_lecture_seule ?? '').trim()
  const avertissements = Array.isArray(contexte?.avertissements)
    ? contexte.avertissements : []

  // Correction fondateur 24/08 — sans AUCUNE position (ni pin posé, ni GPS de
  // fiche), la carte reste au niveau Maroc : comportement inchangé, mais on le
  // DIT discrètement plutôt que de laisser deviner pourquoi la carte est loin
  // de chez le client. Mode AO non concerné (affaire, pas de repli GPS ici).
  const sansPositionGps = !loadError && (
    (estLead && !!lead && !pinDepuisLead(lead))
    || ((estDevis || estCalepinage) && !!contexte && !contexte?.geometrie?.pin)
  )

  const inputClass =
    'w-full border border-white/15 bg-white/5 px-3 py-3 text-base text-white outline-none focus:border-brass-400'
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
  const contourClientBrut = (estDevis || estCalepinage)
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
  const calepinageAutomatiqueVisible = (estDevis || estCalepinage)
    ? (layoutPoseAutomatiquement
      || (devisRoofLayoutSansZones && contourExploitable(contourClientOuOutlinePourNote)))
    : (estLead && toitClientPresent)
  // Le bouton « Recommencer » relit `opts.referenceContour`, c'est-à-dire le contour
  // CLIENT et lui seul : il n'est proposé que si ce contour-là existe encore. Sans ce
  // garde-fou la branche `layoutPoseAutomatiquement` pourrait afficher un bouton
  // inerte (layout estampillé, mais tracé du lead effacé depuis).
  const recommencerDisponible = (estDevis || estCalepinage)
    ? contourExploitable(contexte?.geometrie?.contour_client)
    : (estLead && toitClientPresent)

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
          {estCalepinage && (
            <h1 className="display text-xl text-white sm:text-2xl">
              Calepinage <span className="text-brass-300">{calepinageId || '—'}</span> ·{' '}
              <span className="text-lune-soft">{calepinageTitre || '—'}</span>
            </h1>
          )}
          {estLead && (
            <h1 className="display text-xl text-white sm:text-2xl">
              Lead <span className="text-brass-300">{leadId || '—'}</span> ·{' '}
              <span className="text-lune-soft">{leadLabel || '—'}</span>
            </h1>
          )}
        </div>
        <p className="mt-2 text-sm text-lune-faint" aria-live="polite">{status}</p>

        {/* CALX68 — LE BANDEAU DE REPRISE DE BROUILLON. N'existe QUE tant que
            l'utilisateur n'a pas choisi : le constructeur 3D n'a pas encore
            booté (voir `bootCalepinage`/`poursuivreBootCalepinage`), donc
            « rien n'est réhydraté sans le geste ». */}
        {estCalepinage && brouillonPropose && (
          <div className="cine-card mt-4 border border-brass-400/40 p-4"
            data-testid="cal-brouillon-bandeau">
            <p className="tech-label text-brass-300">Brouillon local</p>
            <p className="mt-1 text-sm text-lune-soft" role="status">
              Un brouillon non enregistré du{' '}
              {formaterHeureBrouillon(brouillonPropose.horodatage)} a été
              trouvé sur cet appareil — reprendre où vous en étiez, ou
              l’ignorer et ouvrir la dernière conception enregistrée.
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={reprendreBrouillon}
                data-testid="cal-brouillon-reprendre"
                className="inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300"
              >
                {`Reprendre le brouillon du ${formaterHeureBrouillon(brouillonPropose.horodatage)}`}
              </button>
              <button
                type="button"
                onClick={ignorerBrouillon}
                data-testid="cal-brouillon-ignorer"
                className="inline-flex items-center gap-2 px-5 py-3 text-base font-semibold text-lune-faint"
              >
                Ignorer
              </button>
            </div>
          </div>
        )}

        {/* Correction fondateur 24/08 — discret, jamais bloquant : dit
            pourquoi la carte reste au niveau Maroc quand ni épingle ni GPS
            de fiche n'existent, plutôt que de laisser deviner. */}
        {sansPositionGps && (
          <p className="mt-1 text-xs text-lune-faint/70" data-testid="pv-sans-gps">
            Pas de position GPS sur la fiche — carte au niveau Maroc.
          </p>
        )}

        {/* WIR227/QJ25 — le contour OSM n'a rien renvoyé pour cette épingle
            (message SERVEUR, jamais rédigé ici) : le tracé manuel reste
            disponible, un bouton relance simplement une nouvelle tentative
            (l'atelier n'a pas d'API pour injecter un contour a posteriori —
            même patron de rechargement que `window.__taqinorRoofBooted`). */}
        {estLead && contourMessage && (
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-lune-faint/70" data-testid="pv-contour-osm-absent">
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

        {/* VT8 — « Ouvrir l'atelier 3D » depuis la revue bureau d'études
            (VisiteBureauEtudesPage.jsx) porte les mesures RÉELLEMENT prises
            pendant la visite terrain en query params optionnels (jamais
            inventées pour un champ non mesuré — simplement omis). Le builder
            vendored (`@roofbuilder`, jamais édité) n'expose pas d'API pour
            piloter ses contrôles pente/orientation depuis l'extérieur : ce
            bandeau les AFFICHE pour que le bureau d'études les reporte
            manuellement dans l'outil, plutôt que d'inventer un pré-remplissage
            qui ne serait pas fiable. */}
        {estLead && mesuresVisiteTerrain && (
          <div className="mt-2 cine-card border border-brass-400/30 p-3 text-xs text-lune-soft" data-testid="pv-mesures-visite-terrain">
            <p className="tech-label rule-brass text-brass-300">Mesures de la visite terrain</p>
            <p className="mt-1">
              {[
                mesuresVisiteTerrain.longueur && mesuresVisiteTerrain.largeur
                  ? `${mesuresVisiteTerrain.longueur} m × ${mesuresVisiteTerrain.largeur} m` : null,
                mesuresVisiteTerrain.pente ? `pente ${mesuresVisiteTerrain.pente}°` : null,
                mesuresVisiteTerrain.orientation ? `orientation ${mesuresVisiteTerrain.orientation}` : null,
              ].filter(Boolean).join(' · ')}
            </p>
          </div>
        )}

        {loadError && (
          <p className="mt-3 text-sm text-alert-300" role="alert">{loadError}</p>
        )}

        {/* PV20 — LECTURE SEULE : le motif vient du serveur, jamais rédigé ici. */}
        {lectureSeule && (
          <div className="cine-card mt-6 border border-brass-400/40 p-5" data-testid="pv20-lecture-seule">
            <p className="tech-label rule-brass text-brass-300">Lecture seule</p>
            <p className="mt-3 text-sm text-lune-soft" role="status">
              {raisonLectureSeule || (estCalepinage
                ? 'Ce calepinage ne peut plus être modifié.'
                : 'Ce devis ne peut plus être modifié.')}
            </p>
            {/* La visionneuse 3D plein écran est une route DEVIS
                (`/ventes/devis/:id/3d`) : hors mode devis elle n'existe pas,
                et un lien mort serait pire que pas de lien. */}
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

        {/* PV20 — avertissements serveur (multi-villa, aucune ligne panneau…). */}
        {(estDevis || estCalepinage) && avertissements.length > 0 && (
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
        {estLead && (
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
            <p className="text-sm text-lune-soft" role="status">
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

        <BuilderDom
          basculerPleinEcran3d={basculerPleinEcran3d}
          chipClass={chipClass}
          contourClientBrut={contourClientBrut}
          inputClass={inputClass}
          mapWrapRef={mapWrapRef}
          photoToit={photoToit}
          photoToitVisible={photoToitVisible}
          pleinEcran3d={pleinEcran3d}
          setPhotoToitVisible={setPhotoToitVisible}
          setToitClientVisible={setToitClientVisible}
          toitClientPresent={toitClientPresent}
          toitClientVisible={toitClientVisible}
        />

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

        {/* CALX94/CALX109 — L'ANCRAGE ATTENDU par `roofPro11/edgesUi.ts` (« Corriger le
            type d'une arête », CALX94) et `roofPro11/zones.ts` (sélecteur de module du pan
            actif, CALX109) : les deux s'accrochent à `ctx.dom.areasWindowEl`, lu depuis
            `#rp9-areas-window` (`roof-tool-pro11.ts`). Cet id n'existait QUE sur la page de
            démonstration publique (`pages/preview/toiture-3d-pro-11.astro`) — absent d'ici,
            il rendait les deux gestes injoignables sur l'écran RÉELLEMENT servi par
            `/calepinage/:id` comme par `/devis-design/:id` (voir l'en-tête de
            `frontend/e2e/calepinage-parcours.spec.js`, CALX130). `edgesUi.ts` retombe sur
            ce même conteneur dès que `#rp9-edges-host` est absent (son repli documenté) :
            un seul ancrage suffit aux deux modules, aucun besoin d'un second conteneur.
            Même contenu/emplacement que la page publique, juste après `#rp9-results` :
            masqué par défaut, affiché par le script dès qu'une zone a un résultat
            (`zones.ts renderAreasPanel`). Non conditionnel au mode — comme `#rp9-results`
            ci-dessus, c'est un module du CONSTRUCTEUR partagé par les trois modes ; un
            conteneur `hidden` par défaut ne change rien au mode devis. */}
        <div id="rp9-areas-window" hidden className="cine-card mt-6 p-5 sm:p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <p className="tech-label rule-brass text-brass-300">Total — toutes les zones</p>
            <p className="text-xs text-lune-faint">Chaque zone est dimensionnée puis ajustable ; les totaux additionnent toutes les zones.</p>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4" aria-live="polite">
            <div>
              <dd id="rp9-areas-total-panels" className="fig text-lg text-white sm:text-xl">—</dd>
              <dt className="tech-label mt-0.5 text-lune-faint">Panneaux</dt>
            </div>
            <div>
              <dd id="rp9-areas-total-kwc" className="fig text-lg text-white sm:text-xl">—</dd>
              <dt className="tech-label mt-0.5 text-lune-faint">Puissance</dt>
            </div>
            <div>
              <dd id="rp9-areas-total-prod" className="fig text-lg text-white sm:text-xl">—</dd>
              <dt className="tech-label mt-0.5 text-lune-faint">Production estimée</dt>
            </div>
            <div>
              <dd id="rp9-areas-total-savings" className="fig text-lg text-brass-300 sm:text-xl">—</dd>
              <dt className="tech-label mt-0.5 text-lune-faint">Économies estimées</dt>
            </div>
          </dl>
          {/* Liste des zones (script-rendu) : libellé, panneaux, kWc, « Voir » + suppr. La
              zone active est mise en évidence. `edgesUi.ts`/`zones.ts` (module picker,
              CALX109) ajoutent aussi leurs propres panneaux ICI (`appendChild`, patron
              `obstaclesUi.ts ensureTypePicker`) — rien d'autre à câbler côté écran. */}
          <ul id="rp9-areas-list" className="mt-5 space-y-2"></ul>
          <p className="mt-3 text-xs leading-relaxed text-lune-faint">
            « + Ajouter une zone » fige la zone tracée et démarre un nouveau tracé sur la même
            facture. La 3D et les graphes détaillés affichent la zone sélectionnée (« Voir ») ;
            les totaux ci-dessus restent la somme de toutes les zones. Chiffres indicatifs, pas un devis.
          </p>
        </div>

        {/* CALX65 — sous la carte du constructeur, en mode calepinage
            UNIQUEMENT : dit laquelle des deux productions on regarde, sans
            jamais toucher un seul chiffre de `rp9-results` ci-dessus. */}
        {estCalepinage && calepinageId && (
          <BandeauProvenanceProduction calepinageId={calepinageId} />
        )}

        {/* UN SEUL BOUTON — génère le devis, capture la 3D, mint le lien.
            PV20 — mode lead UNIQUEMENT : un devis existant n'est jamais recréé
            depuis cet écran (sa boucle d'enregistrement arrive en PV21).
            Mode AO : une affaire ne « génère » aucun devis depuis la toiture —
            le devis d'un appel d'offres naît du BORDEREAU DES PRIX (action
            « Créer le devis » de l'écran Bordereau), pas d'un calepinage. */}
        {estLead && (
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
        />

        {estCalepinage && contexte && (
          <AtelierPanneaux
            calepinageId={calepinageId}
            contexte={contexte}
            // CALX8 — `builderApi` (ci-dessus) est une REF `useRef` (O3) : elle
            // ne change JAMAIS d'identité, donc la passer telle quelle a envoyé
            // `undefined` pour toujours à `AtelierPanneaux` (`.entreeMoteur`,
            // `.appliquerPlan`, `.raccourcis` lus SUR la ref au lieu de
            // l'objet posé par le builder). Il faut transmettre l'OBJET —
            // `builderApiActuel`, un ÉTAT posé par les mêmes `onApiReady`
            // (jamais `builderApi.current` ici : `react-hooks/refs` interdit
            // de lire une ref PENDANT le rendu, seuls les effets/gestionnaires
            // le peuvent ; le reste du fichier continue de lire
            // `builderApi.current` dans ce cadre-là, inchangé).
            builderApi={builderApiActuel}
            lectureSeule={lectureSeule}
            onRecharger={() => window.location.reload()}
          />
        )}

        {/* CAL37 — MODE CALEPINAGE : « Enregistrer le calepinage ». La
            conception se range sur le calepinage (une VERSION n'est déposée
            que si elle a changé) ; aucun statut n'est écrit et aucun devis
            n'est touché — le devis a son propre bouton (CAL38). Absent en
            lecture seule, comme dans les deux autres modes. */}
        {estCalepinage && !lectureSeule && (
        <div className="cine-card mt-6 p-6" data-testid="cal-enregistrer-calepinage">
          <button type="button" onClick={enregistrerCalepinage} disabled={sending}
            className="inline-flex w-full items-center justify-center gap-3 bg-ok-600 px-6 py-4 text-base font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
            style={{ background: 'var(--rp-ok-600)' }}>
            {sending && (
              <span aria-hidden="true"
                className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
            )}
            <span>{sending ? 'Enregistrement en cours…' : 'Enregistrer le calepinage'}</span>
          </button>
          <p className="mt-3 text-xs text-lune-faint">
            La conception est rangée sur le calepinage, avec une nouvelle
            version dès qu'elle a changé. Aucun statut n'est modifié ; le devis,
            lui, se génère par son propre bouton.
          </p>
          {genStatus && <p className="mt-3 text-sm text-lune-soft" aria-live="polite">{genStatus}</p>}
          {genError && <p className="mt-3 text-sm text-alert-300" aria-live="assertive" data-testid="cal-erreur-enregistrement">{genError}</p>}

          {/* 409 : le devis lié est parti chez le client — motif du SERVEUR. */}
          {conflit && (
            <div className="mt-4 border border-alert-300/40 p-4" data-testid="cal-conflit-lecture-seule">
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
