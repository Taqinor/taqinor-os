import { useEffect } from 'react'
import api from '../../../api/axios'
import ventesApi from '../../../api/ventesApi'
import crmApi from '../../../api/crmApi'
import calepinageApi from '../../../api/calepinageApi'
import { hacherLayout, brouillonPertinent } from '../brouillon.js'
import { contourExploitable } from '../../crm/workspace/traceToit.js'
import {
  pinDepuisLead, leadToBuilderPayload, contexteToDevisPayload,
  contexteCalepinageVersPayload, bankableFromDevis, reglagesAtelierDuContexte,
  stockageBrouillonLocal, tailleImagePlan,
} from './contexteAtelier.js'

// SPL214 — effet de boot de l'atelier (chargement lead/devis/calepinage puis
// initialisation du builder), déplacé VERBATIM depuis pages/ventes/ToitureDesign.jsx
// (move only : le corps de l'effet est inchangé ; seuls les imports et la
// déstructuration de `ctx` en tête sont ajoutés).
export function useAtelierBoot(ctx) {
  const {
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
  } = ctx
  useEffect(() => {
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
        .then((res) => {
          const p = res?.data
          if (!p || typeof p !== 'object') return null
          return { zones_types: p.zones_types ?? null, degagements: p.degagements ?? null }
        })
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
          if (photo?.url) ressource = { url: photo.url, calagePhoto: photo.calage }
        } catch {
          /* pas de fichier : le constructeur dira POURQUOI le fond n'est pas affiché */
        }
      } else if (fond.kind === 'plan' && fond.attachmentId && calepinageId) {
        // CALX107 câblage — la pièce jointe du plan : URL servie + pixels naturels.
        try {
          const res = await calepinageApi.calepinages.planImporte(calepinageId)
          const plan = res?.data
          if (plan?.url) {
            ressource = { url: plan.url, tailleImage: tailleImagePlan(plan) }
          }
        } catch {
          /* pas de fichier : le constructeur dira POURQUOI le fond n'est pas affiché */
        }
      }
      if (cancelled) return
      const pose = api.poserFond(fond, ressource)
      if (!pose?.ok && pose?.motif) setStatus(pose.motif)
    }

    async function boot() {
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
      if (!leadData.roof_outline && pinDepuisLead(leadData)) {
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
              leadData = { ...leadData, roof_outline: paires }
            }
          } else if (fp?.data?.message) {
            setContourMessage(fp.data.message)
          }
        } catch {
          /* repli silencieux : tracé manuel toujours disponible */
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
        /* repli : message ci-dessous */
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
        maptilerKey,
        mapboxToken,
        reducedMotion: !!reducedMotion,
        hydrate: { lead: leadToBuilderPayload(leadData) },
        // CALX104/CALX403 câblage — gabarits d'obstacle + largeur d'allée de la société,
        // transmis TELS QUELS ; `null` = aucun réglage, aucune cote de repli.
        reglagesAtelier,
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
      })
      // Pré-remplit l'adresse depuis la ville du lead (champ de recherche).
      const addrEl = document.getElementById('rp9-address')
      if (addrEl && leadData.ville) addrEl.value = String(leadData.ville)
      setStatus('Repère du client chargé. Dessinez / ajustez, puis « Générer le devis & envoyer au client ».')
    }

    // ── PV20 — boot MODE DEVIS : UN SEUL appel CRITIQUE (design-context) ────
    // Identité + géométrie + cible + carte + `modifiable` arrivent ensemble :
    // l'écran ne fait aucune requête de complément et ne devine aucun motif de
    // lecture seule (il vient toujours du serveur).
    async function bootDevis() {
      // PV75 — étude bancable (P50/P90/PR/pertes), lancée EN PARALLÈLE du
      // design-context : best-effort, ne bloque jamais le boot, n'invente rien
      // si l'étude n'a jamais été lancée (endpoint backend `POST .../simuler/`,
      // PV74 — pas encore câblé côté écran) ou n'est pas encore rangée. Le
      // contexte agrégé ne porte pas `simulation` (contrat
      // `devis_design_context.json`, PACT10) donc on la lit à part, sur le devis
      // complet déjà exposé par `getDevisById`.
      const bankablePromise = Promise.resolve()
        .then(() => ventesApi.getDevisById(devisId))
        .then((res) => bankableFromDevis(res.data))
        .catch(() => null)

      let ctx = null
      try {
        const res = await ventesApi.getDevisDesignContext(devisId)
        ctx = res.data
      } catch (err) {
        if (cancelled) return
        const code = err?.response?.status
        setLoadError(
          code === 404
            ? 'Devis introuvable.'
            : 'Impossible de charger le devis — réessayez.'
        )
        setStatus(`Devis introuvable (erreur ${code ?? '?'}).`)
        return
      }
      if (cancelled) return
      setContexte(ctx)

      // L-SECT (fondateur 24/08/2026) — PV86 frappait ICI, AU BOOT, un
      // ShareLink sans aucune option (`shareLinkDevis(devisId)`) pour afficher
      // en permanence un panneau d'envoi en bas de page. Deux problèmes : le
      // lien partait toujours aux DÉFAUTS (jamais le niveau ni les sections
      // choisis), et ouvrir l'outil 3D mintait un lien public sans que
      // personne ne l'ait demandé. L'envoi vit désormais dans la fiche lead
      // (onglet Devis → « Envoyer au client ») : cet écran ne mint plus rien
      // au chargement.

      const carte = ctx?.carte ?? {}
      if (!carte.available || !carte.maptilerKey) {
        setStatus('Carte indisponible (clé MapTiler manquante côté serveur).')
        setLoadError('Carte indisponible : la clé MapTiler n’est pas configurée sur le serveur ERP.')
        return
      }

      const mod = await import('@roofbuilder')
      const bankable = await bankablePromise
      if (cancelled) return
      window.__taqinorRoofBooted = true
      // Un devis en lecture seule BOOTE quand même : on peut regarder le
      // calepinage vendu — seule l'action d'enregistrement disparaît.
      mod.initRoofToolPro8({
        maptilerKey: carte.maptilerKey,
        mapboxToken: carte.mapboxToken || undefined,
        reducedMotion: !!reducedMotion,
        hydrate: { devis: contexteToDevisPayload(ctx) },
        // L-MAP — le contour ORIGINAL du client (jamais celui, déjà édité, du
        // layout courant), géo-référencé sur la carte (calque passif). MÊME
        // garde `contourExploitable` que la légende/bascule (revue
        // adversariale 26/08) : voir le commentaire jumeau dans `boot()`.
        referenceContour: contourExploitable(ctx?.geometrie?.contour_client)
          ? ctx.geometrie.contour_client : null,
        bankable,
        // CALX104/CALX403 câblage — les gabarits d'obstacle (`zones_types`) et la
        // largeur d'allée (`degagements`) de la société, lus DANS le contexte agrégé
        // (`devis_design_context`, PACT10) : AUCUNE requête annexe n'est ajoutée ici,
        // la garantie testée du mode DEVIS (« un seul appel ») reste vraie. Transmis
        // TELS QUELS ; `null` = le contexte ne les porte pas, donc aucun gabarit
        // proposé et aucune cote de repli.
        reglagesAtelier: reglagesAtelierDuContexte(ctx),
        onApiReady: (a) => { builderApi.current = a; setBuilderReady(true); setBuilderApiActuel(a) },
      })
      // PV23bis — pré-remplit la barre de recherche d'adresse depuis
      // adresse+ville du devis, comme le mode lead le fait déjà ci-dessus
      // (`boot()`, `addrEl.value = leadData.ville`) : elle donne à la carte
      // un point de départ tant que le devis n'a pas ENCORE de repère posé ;
      // dès qu'un repère existe, l'hydratation ci-dessus centre déjà la carte
      // et cette barre ne sert plus qu'à chercher ailleurs.
      const addrEl = document.getElementById('rp9-address')
      const adresse = [ctx?.devis?.client_adresse, ctx?.devis?.client_ville]
        .map((v) => (v ?? '').trim())
        .filter(Boolean)
        .join(', ')
      if (addrEl && adresse) addrEl.value = adresse
      const reference = ctx?.devis?.reference ?? ''
      setStatus(
        ctx?.modifiable
          ? `Devis ${reference} chargé. Ajustez le calepinage, puis « Enregistrer la conception ».`
          : `Devis ${reference} en lecture seule — consultation du calepinage vendu.`
      )
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
    async function bootCalepinage() {
      // CALX109 — le CATALOGUE DE MODULES de la société, lu EN PARALLÈLE du
      // design-context : best-effort exactement comme l'étude bancable de
      // `bootDevis` — il ne bloque jamais le boot et n'invente rien. Sans lui
      // (droits, réseau, société sans fiche « module »), l'atelier pose le
      // module par défaut, NOMMÉ. Le contexte agrégé ne le porte pas (contrat
      // `calepinage_design_context.json`, PACT10) : c'est sa propre porte.
      // ACAL30 — un catalogue ILLISIBLE ne bloque pas l'ouverture (on regarde la
      // conception), mais il INTERDIT l'enregistrement : sans lui, le module de chaque
      // pan retomberait en silence sur le module par défaut (720 Wc).
      const modulesPromise = Promise.resolve()
        .then(() => calepinageApi.calepinages.modulesDisponibles(calepinageId))
        .then((res) => res.data)
        .catch(() => {
          setCatalogueIndisponible?.(true)
          return null
        })
      // CALX104/CALX403 — même porte, même discipline best-effort.
      const reglagesPromise = chargerReglagesAtelier()

      let ctx = null
      try {
        const res = await calepinageApi.calepinages.designContext(calepinageId)
        ctx = res.data
      } catch (err) {
        if (cancelled) return
        const code = err?.response?.status
        setLoadError(
          code === 404
            ? 'Calepinage introuvable.'
            : 'Impossible de charger le calepinage — réessayez.'
        )
        setStatus(`Calepinage introuvable (erreur ${code ?? '?'}).`)
        return
      }
      if (cancelled) return
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
        if (cancelled) return
        window.__taqinorRoofBooted = true
        const payload = contexteCalepinageVersPayload(ctx)
        if (payload && layoutSubstitue !== undefined) {
          payload.geometrie = { ...payload.geometrie, roof_layout: layoutSubstitue }
        }
        // Un calepinage non modifiable (devis lié déjà parti chez le client, la
        // raison venant du serveur ventes MOT POUR MOT) BOOTE quand même : on
        // peut regarder la conception — seule l'action d'enregistrement
        // disparaît, exactement comme en mode devis.
        mod.initRoofToolPro8({
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
          onApiReady: (a) => {
            builderApi.current = a; setBuilderReady(true); setBuilderApiActuel(a)
            // CALX107 câblage — le document peut demander un CALQUE DE FOND
            // (`underlay`) : l'atelier sait le peindre mais ne parle jamais à
            // Django, c'est donc à l'écran d'aller chercher le fichier.
            poserFondDuDocument(a)
          },
        })
        // La barre de recherche d'adresse part PRÉ-REMPLIE, exactement comme en
        // mode devis (`bootDevis` ci-dessus, PV23bis) et en mode lead (`boot()`).
        // C'était la dernière divergence connue du mode calepinage : le commercial
        // ouvrait l'atelier sur une barre VIDE et devait retaper l'adresse que le
        // serveur connaît déjà. Le contexte la porte sous les MÊMES noms que le
        // contrat devis (`client_adresse`/`client_ville`) — aucune clé devinée,
        // aucune adresse composée ici au-delà de la jointure des deux morceaux.
        const addrEl = document.getElementById('rp9-address')
        const adresse = [ctx?.calepinage?.client_adresse,
          ctx?.calepinage?.client_ville]
          .map((v) => (v ?? '').trim())
          .filter(Boolean)
          .join(', ')
        if (addrEl && adresse) addrEl.value = adresse
        const titre = (ctx?.calepinage?.titre ?? '').trim()
        setStatus(
          ctx?.modifiable
            ? `Calepinage ${titre || calepinageId} chargé. Ajustez la conception, puis « Enregistrer le calepinage ».`
            : `Calepinage ${titre || calepinageId} en lecture seule — consultation de la conception.`
        )
      }

      // CALX68 — brouillon local : détecté AVANT de booter le constructeur,
      // pour pouvoir substituer `roof_layout` SANS second boot si le
      // commercial choisit de reprendre. `hashBase` est l'empreinte du
      // layout SERVEUR lue MAINTENANT (voir l'en-tête de `brouillon.js` —
      // elle tient lieu d'`updated_at`, absent du contrat design-context) ;
      // elle reste constante pour toute la session d'édition qui suit.
      const hashServeur = hacherLayout(ctx?.geometrie?.roof_layout ?? null)
      if (!cancelled) setHashBaseBrouillon(hashServeur)
      const brouillon = brouillonPertinent({
        storage: stockageBrouillonLocal(),
        calepinageId,
        utilisateurId: utilisateurCourantId,
        hashBase: hashServeur,
      })
      if (!cancelled && brouillon) {
        // « Rien n'est réhydraté sans le geste » : le boot du constructeur
        // ATTEND que l'utilisateur choisisse (bandeau plus bas dans le JSX).
        poursuivreBootRef.current = poursuivreBootCalepinage
        setBrouillonPropose(brouillon)
        return
      }
      await poursuivreBootCalepinage(undefined)
    }

    if (estDevis) bootDevis()
    else if (estCalepinage) bootCalepinage()
    else boot()
    return () => { cancelled = true }
    // CALX68 — `utilisateurCourantId` est un `useMemo([])` (CAL103) :
    // référentiellement stable pour toute la vie du composant, mais listé ici
    // pour que `react-hooks/exhaustive-deps` reste silencieux (`bootCalepinage`
    // le lit désormais pour la clé du brouillon).
  // eslint-disable-next-line react-hooks/exhaustive-deps -- setters/refs de `ctx` : stables (useState/useRef du parent), liste d'origine inchangée
  }, [cibleId, devisId, leadId, calepinageId,
    estDevis, estCalepinage, reducedMotion, utilisateurCourantId])
}
