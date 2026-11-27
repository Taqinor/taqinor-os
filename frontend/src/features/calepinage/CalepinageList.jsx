import { useContext, useMemo, useRef, useState } from 'react'
import { ReactReduxContext } from 'react-redux'
import { messageRefus } from './commun/refusServeur'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  CircleCheck, CircleDashed, CircleX, Columns3, LayoutGrid, Plus, Search, SlidersHorizontal,
  TriangleAlert, User, X,
} from 'lucide-react'
import calepinageApi from '../../api/calepinageApi'
import crmApi from '../../api/crmApi'
import useResource from '../../hooks/useResource'
import { unwrapList } from '../../api/resource'
import {
  Button, Card, Checkbox, Combobox, EmptyState, Input, Label, Spinner,
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../ui'
import { urlImage } from './urlImage'
import { lireAvecReprise } from './delaiReseau'
// CAL188 — le badge « calepinage périmé », lu du MÊME champ serveur que la
// fiche devis et l'en-tête de l'atelier (CAL189), jamais recalculé ici.
import BadgePerime from './BadgePerime'
// CALX344 — le filtre par étiquette libre (`?etiquette=`, CALX343).
import { FiltreEtiquettes } from './Etiquettes'
import {
  STATUTS_CALEPINAGE, STYLE_STATUT, apercuVide, identiteCarte, initiales, modifieDe, morceauxMesures,
  nombreProjets, signalCarte, traceDuToit,
} from './CalepinageList.helpers'

/* ============================================================================
   CAL35 — L'ÉCRAN LISTE `/calepinage` : la porte autonome, enfin.
   ----------------------------------------------------------------------------
   D3 — cette porte n'existait pas : le seul accès au calepinage passait par un
   devis (`router/index.jsx`). Un
   calepinage sans devis est pourtant un objet de PREMIÈRE CLASSE (décision
   fondateur du 19/09/2026) — il lui fallait une liste à lui.

   LES FILTRES SONT CEUX QUE LE SERVEUR SERT VRAIMENT (CAL16) : `lead`,
   `client`, `statut`, `depuis`, `q` — plus `responsable` (CALX406, colonne
   « Responsable »). Aucun autre n'est envoyé. La leçon PV22
   est qu'un filtre IGNORÉ par le serveur fait ouvrir le mauvais objet : une
   liste fausse qui a l'air juste est pire qu'une liste qui refuse de filtrer.
   Chaque champ ci-dessous part donc dans la requête, et le test le prouve.

   AUCUNE IMAGE INVENTÉE. Le serveur publie `image.url` — une URL signée à durée
   de vie courte (contrat `calepinage_detail.json`) — ou `null` quand aucun
   aperçu n'a été produit. Dans ce second cas la vignette rend une CARTE NEUTRE,
   jamais une `<img>` vers une source vide (qui afficherait l'icône d'image
   cassée du navigateur) et jamais une illustration de substitution qui
   laisserait croire qu'un toit a été dessiné.

   LES STATUTS (ACAL197) viennent de `STATUTS_CALEPINAGE`, gardée par un vitest
   contre `calepinage_liste.json.statuts_publies` ; le libellé d'une ligne reste
   celui du serveur (`statut_libelle`).
   ========================================================================== */

/* ACAL197 — `image.url` RELATIVE préfixée par l'origine de l'API : le helper
   partagé avec la fiche (`urlImage.js`). */

/* ACAL197 — le rattachement affiché : la liste publie `client_apercu`
   `{id, nom, ville}` (`client` n'y est qu'un identifiant), le détail un
   `client` objet. « Sans rattachement » seulement si rien n'est rattaché. */
const rattachementDe = (c) => c?.client_apercu?.nom || c?.client?.nom || c?.lead?.nom
  || 'Sans rattachement'

// ACAL279 — LE décodeur commun des refus (motif serveur, sinon le repli).
const errMsg = messageRefus

/* CALX32 — LES 4 CHAMPS RÉELLEMENT SERVIS PAR LA LISTE (`ordering_fields`,
   `views/calepinages.py:173-174`). En inventer un cinquième produirait un
   `ordering=` que le serveur ignore silencieusement — la même leçon PV22 que
   les filtres ci-dessus. */
const CHAMPS_TRI = [
  ['created_at', 'Date de création'],
  ['updated_at', 'Date de modification'],
  ['statut', 'Statut'],
  ['titre', 'Titre'],
]

/* Les filtres, tels qu'ils partent au serveur. Une valeur vide n'est pas
   envoyée du tout : `?statut=` (vide) serait un filtre, pas une absence de
   filtre. */
function paramsServeur({ q, statut, depuis, lead, client, page, ordering, etiquettes, responsable }) {
  const params = {}
  if (q) params.q = q
  if (statut) params.statut = statut
  if (depuis) params.depuis = depuis
  if (lead) params.lead = lead
  if (client) params.client = client
  // CALX406 — `?responsable=<id>`, servi par `views/calepinages.py`.
  if (responsable) params.responsable = responsable
  if (ordering) params.ordering = ordering
  if (page && page > 1) params.page = page
  // CALX344 — `?etiquette=` : ET logique côté serveur. Les identifiants
  // voyagent joints par des virgules (le serveur les découpe) : la
  // sérialisation par défaut d'axios écrirait `etiquette[]=`, que Django ne
  // lit pas. Aucune étiquette retenue ⇒ AUCUN paramètre (liste inchangée).
  if (etiquettes?.length) params.etiquette = etiquettes.map((e) => e.id).join(',')
  return params
}

/** Recherche bornée société côté serveur — jamais un filtrage local. */
const chercherLeads = async (q) => {
  const res = await crmApi.getLeads({ search: q, page_size: 20 })
  return unwrapList(res).map((l) => ({
    value: String(l.id),
    label: l.nom || l.nom_complet || l.raison_sociale || `Lead ${l.id}`,
    description: l.ville || undefined,
  }))
}

const chercherClients = async (q) => {
  const res = await crmApi.searchClients(q)
  return unwrapList(res).map((c) => ({
    value: String(c.id),
    label: c.nom || c.raison_sociale || `Client ${c.id}`,
    description: c.ville || undefined,
  }))
}

/* CALX406 — LE RESPONSABLE d'une ligne, quelle que soit la forme reçue :
   l'agrégat de détail (contrat `calepinage_detail.json`) publie
   `responsable: {id, nom_complet}` ; le sérialiseur de liste publie
   l'identifiant `responsable` et son `responsable_nom`. `null` = personne —
   jamais un nom deviné. */
function responsableDe(ligne) {
  const brut = ligne?.responsable
  if (brut === null || brut === undefined || brut === '') return null
  if (typeof brut === 'object') {
    return { id: String(brut.id), nom: brut.nom_complet || `Utilisateur ${brut.id}` }
  }
  return { id: String(brut), nom: ligne?.responsable_nom || `Utilisateur ${brut}` }
}

/* CALX342 — la BORNE du comparatif de calepinages : celle du serveur
   (`services/comparaison_projets.py::BORNE_PROJETS`, CALX341 — PV*SOL compare
   5 projets). Une case de plus serait refusée 400 sous le champ `ids`. */
const BORNE_COMPARAISON = 5

/* ── La carte (maquette « Liste ») ────────────────────────────────────────
   `image.url` présent ⇒ l'aperçu réel. Absent ⇒ carte neutre « Aucun aperçu »,
   jamais un faux dessin de toit. Chaque chiffre (kWc, panneaux, kWh/an,
   « points à régler ») n'apparaît que lorsque le serveur le SERT.
   CALX342 — `selection` (facultatif) pose une case « Comparer » HORS du lien :
   cocher ne doit jamais ouvrir l'atelier. */
const ICONE_STATUT = {
  brouillon: CircleDashed, valide: CircleCheck, perime: TriangleAlert, refuse: CircleX,
}

/* L'aperçu d'une carte : l'image servie, ou « Aucun aperçu » quand il n'y en a pas, qu'elle ne se charge
   pas (`onError`, fichier vide) ou qu'elle est TOUTE blanche (rendu sans rien dessiné, carte 293). */
function ApercuCarte({ url, alt, trace = null }) {
  const [echec, setEchec] = useState(false)
  const img = useRef(null)
  const verifier = () => {
    const el = img.current
    if (!el) return
    if (!el.naturalWidth) { setEchec(true); return }
    try {
      const toile = document.createElement('canvas')
      toile.width = 24
      toile.height = 24
      const g = toile.getContext('2d')
      g.drawImage(el, 0, 0, 24, 24)
      if (apercuVide(g.getImageData(0, 0, 24, 24).data)) setEchec(true)
    } catch {
      // Image d'une autre origine ou canvas absent : l'aperçu ne peut pas être
      // contrôlé, on garde l'image telle quelle (pas d'erreur à montrer).
      return
    }
  }
  if (url && !echec) {
    return (
      <img ref={img} src={url} alt={alt} onLoad={verifier} onError={() => setEchec(true)}
        className="block h-[168px] w-full flex-none object-cover" data-testid="cal-vignette-image" />
    )
  }
  // ACAL1336 — sans image : le tracé des pans servi (`apercu_toit`), jamais un toit inventé.
  if (trace) {
    return (
      <div className="cliste-toit" data-testid="cal-vignette-toit">
        <svg viewBox={trace.viewBox} role="img" aria-label={alt} preserveAspectRatio="xMidYMid meet">
          {trace.contours.map((points, rang) => <polygon key={rang} points={points} />)}
        </svg>
      </div>
    )
  }
  return (
    <div className="flex h-[168px] w-full flex-none flex-col items-center justify-center gap-2 bg-muted text-muted-foreground"
      data-testid="cal-vignette-sans-image">
      <LayoutGrid size={28} strokeWidth={1.5} aria-hidden="true" />
      <span className="text-xs">Aucun aperçu</span>
    </div>
  )
}

export function VignetteCalepinage({ calepinage, selection = null }) {
  const url = urlImage(calepinage?.image?.url) || null
  const { titre, ville, propre } = identiteCarte(calepinage)
  const [kwc, ...reste] = morceauxMesures(calepinage)
  const modifie = modifieDe(calepinage?.modifie_le)
  const signal = signalCarte(calepinage)
  const resp = responsableDe(calepinage)
  const Icone = ICONE_STATUT[calepinage?.statut] || CircleDashed
  const autres = kwc && !kwc.fort ? [kwc, ...reste] : reste
  return (
    <Card className="cliste-carte relative flex min-h-0 flex-col overflow-hidden">
      {selection ? (
        <label className="absolute right-2 top-2 z-10 flex items-center gap-1.5 rounded-md bg-card/90 px-2 py-1 text-xs shadow-ui-xs">
          <Checkbox
            checked={selection.coche}
            disabled={selection.desactive}
            onCheckedChange={() => selection.basculer(calepinage.id)}
            aria-label={`Comparer ${titre}`}
            data-testid={`cal-comparer-${calepinage.id}`}
          />
          Comparer
        </label>
      ) : null}
      <Link
        to={`/calepinage/${calepinage.id}`}
        className="flex min-h-0 flex-1 flex-col text-foreground no-underline"
        title={`${calepinage?.reference || ''} · ${rattachementDe(calepinage)}`}
        data-testid={`cal-vignette-${calepinage.id}`}
      >
        <div className="cliste-apercu">
          <ApercuCarte url={url} alt={`Aperçu de toiture — ${titre}`} trace={traceDuToit(calepinage?.apercu_toit)} />
          {calepinage?.statut_libelle ? (
            <span className={`cliste-etat ${STYLE_STATUT[calepinage.statut] || STYLE_STATUT.brouillon}`}>
              <Icone size={12} aria-hidden="true" />
              {calepinage.statut_libelle}
            </span>
          ) : null}
        </div>
        <div className="cliste-corps">
          <div className="flex items-start justify-between gap-3">
            <div className="cliste-identite">
              <span className="cliste-nom truncate font-semibold">{titre}</span>
              {ville ? <span className="cliste-ville truncate">{ville}</span> : null}
            </div>
            <BadgePerime layoutStale={calepinage?.layout_stale} layoutNbPanneaux={calepinage?.layout_nb_panneaux} />
          </div>
          {propre ? <span className="truncate text-xs text-muted-foreground" data-testid="liste-vignette-nom">{propre}</span> : null}
          {kwc || autres.length ? (
            <div className="cliste-chiffres">
              {kwc?.fort ? <span className="cliste-kwc">{kwc.nombre} <span className="cliste-unite">{kwc.unite}</span></span> : null}
              {autres.length ? <span className="cliste-reste">{autres.map((m) => m.texte).join(' · ')}</span> : null}
            </div>
          ) : null}
          {/* Référence et rattachement : pour les lecteurs d'écran et en infobulle. */}
          <span className="sr-only">{`${calepinage?.reference || ''} · ${rattachementDe(calepinage)}`}</span>
          <div className="cliste-pied">
            <span>{modifie || '—'}</span>
            {signal ? (
              <span className="cliste-signal" data-ton={signal.ton} data-testid={`cal-signal-${calepinage.id}`}
                title={signal.ton === 'relire' ? 'Le document a changé depuis le dernier « Prêt à envoyer ? »' : undefined}>
                {signal.ton === 'regler' ? <TriangleAlert size={12} aria-hidden="true" /> : null}
                {signal.texte}
              </span>
            ) : null}
            <span className="flex-1" />
            {/* CALX406 — la colonne « Responsable » : initiales, nom complet en clair pour la lecture d'écran. */}
            <span
              className="cliste-avatar"
              title={resp ? resp.nom : 'Sans responsable'}
              data-testid={`cal-responsable-${calepinage.id}`}
            >
              <span aria-hidden="true">{resp ? initiales(resp.nom) : '—'}</span>
              <span className="sr-only">{resp ? `Responsable : ${resp.nom}` : 'Sans responsable'}</span>
            </span>
          </div>
        </div>
      </Link>
    </Card>
  )
}

export default function CalepinageList() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [statut, setStatut] = useState('')
  const [depuis, setDepuis] = useState('')
  const [lead, setLead] = useState(null)
  const [client, setClient] = useState(null)
  const [page, setPage] = useState(1)
  const [etiquettes, setEtiquettes] = useState([])
  // Maquette « Liste » — la barre de filtres est repliée derrière « Filtres » (ACAL957 la
  // repliait déjà sous 768 px) ; un filtre avancé actif la garde ouverte (`filtresVisibles`).
  const [filtresOuverts, setFiltresOuverts] = useState(false)
  // CALX406 — l'identifiant du responsable filtré ('' = tous).
  const [responsable, setResponsable] = useState('')
  // « Mes calepinages » : l'identifiant de la personne connectée (lu du magasin, jamais deviné).
  const contexteRedux = useContext(ReactReduxContext)
  const idMoi = contexteRedux?.store?.getState?.()?.auth?.user?.id

  // CALX32 — le tri vit dans l'URL (`?ordering=`), partageable et rechargeable
  // à l'identique — contrairement aux autres filtres ci-dessus (état local).
  const [searchParams, setSearchParams] = useSearchParams()
  const ordering = searchParams.get('ordering') || ''
  const champTri = ordering.replace(/^-/, '')
  const decroissant = ordering.startsWith('-')

  // CALX342 — le mode « Comparer » : cocher de 2 à 5 calepinages, puis ouvrir
  // `/calepinage/comparaison?ids=…`. `?comparer=1` l'ouvre directement (lien
  // « Choisir dans la liste » de l'écran de comparaison).
  const [modeComparaison, setModeComparaison] = useState(searchParams.get('comparer') === '1')
  const [selection, setSelection] = useState([])
  const basculerSelection = (id) => setSelection((avant) => (
    avant.includes(id)
      ? avant.filter((autre) => autre !== id)
      : (avant.length >= BORNE_COMPARAISON ? avant : [...avant, id])
  ))
  const quitterComparaison = () => { setModeComparaison(false); setSelection([]) }
  const ouvrirComparaison = () => {
    navigate(`/calepinage/comparaison?ids=${selection.join(',')}`)
  }

  const params = useMemo(
    () => paramsServeur({ q, statut, depuis, lead, client, page, ordering, etiquettes, responsable }),
    [q, statut, depuis, lead, client, page, ordering, etiquettes, responsable],
  )

  // T4-B4-002 — une lecture restée sans réponse (délai dépassé) est relancée une fois ; un échec qui dure garde « Réessayer ».
  const { data, loading, error, refetch } = useResource(
    (p) => lireAvecReprise(() => calepinageApi.calepinages.list(p)),
    params,
    {
      initialData: null,
      select: (res) => res?.data ?? null,
      errorMessage: (e) => errMsg(e, 'Impossible de charger les calepinages.'),
    },
  )

  const lignes = useMemo(() => unwrapList({ data }), [data])
  // Effectifs par statut servis avec la liste (une requête groupée côté serveur) : sans eux, aucun nombre.
  const compteurs = Array.isArray(data) ? null : (data?.compteurs_statut ?? null)
  const total = Array.isArray(data) ? data.length : (data?.count ?? lignes.length)
  const pageSuivante = Array.isArray(data) ? null : data?.next
  const pagePrecedente = Array.isArray(data) ? null : data?.previous

  // ACAL197 — options de statut : les trois statuts servis, toujours.
  const optionsStatut = STATUTS_CALEPINAGE

  // CALX406 — options de RESPONSABLE : celles des lignes reçues (même
  // discipline que le statut — aucune liste de personnes recopiée ici).
  const optionsResponsable = useMemo(() => {
    const vus = new Map()
    for (const ligne of lignes) {
      const r = responsableDe(ligne)
      if (r && !vus.has(r.id)) vus.set(r.id, r.nom)
    }
    return [...vus.entries()]
  }, [lignes])

  const reinitialiser = () => {
    setQ(''); setStatut(''); setDepuis(''); setLead(null); setClient(null); setPage(1)
    setEtiquettes([]); setResponsable('')
  }
  const filtreActif = Boolean(q || statut || depuis || lead || client || etiquettes.length
    || responsable)
    const surFiltre = (poser) => (valeur) => { poser(valeur); setPage(1) }
  // Les filtres avancés (hors recherche et puces d'état) : l'un d'eux actif garde la barre ouverte.
  const responsableAvance = responsable && String(responsable) !== String(idMoi) ? responsable : ''
  const nbAvances = [depuis, lead, client, responsableAvance, champTri].filter(Boolean).length
    + (etiquettes.length ? 1 : 0)
  const filtresVisibles = filtresOuverts || nbAvances > 0

  // CALX32 — changer le champ ou le sens relance la requête avec `ordering=`
  // ET remet la pagination à la première page (sinon une page 3 triée
  // autrement s'afficherait vide).
  const changerChampTri = (valeur) => {
    const suivants = new URLSearchParams(searchParams)
    if (!valeur || valeur === '__defaut__') suivants.delete('ordering')
    else suivants.set('ordering', decroissant ? `-${valeur}` : valeur)
    setSearchParams(suivants)
    setPage(1)
  }
  const changerSensTri = (dec) => {
    if (!champTri) return
    const suivants = new URLSearchParams(searchParams)
    suivants.set('ordering', dec ? `-${champTri}` : champTri)
    setSearchParams(suivants)
    setPage(1)
  }

  const puces = [['', 'Tous'], ...optionsStatut]
  const nombreDe = (valeur) => (compteurs ? compteurs[valeur === '' ? 'tous' : valeur] : null)
  const estMoi = idMoi !== undefined && idMoi !== null && String(responsable) === String(idMoi)

  // Les deux boutons discrets de la rangée des puces : 44 px de cible, un libellé visible seulement quand actifs.
  const calme = (actif) => `h-11 gap-2 rounded-full text-sm text-muted-foreground ${actif ? 'px-3' : 'w-11 px-0'}`

  return (
    <div className="cliste cliste-page space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <div className="cliste-tete-titre flex flex-1 items-baseline gap-3">
          <h1 className="cliste-titre">Calepinages</h1>
          <span className="cliste-compteur text-sm" data-testid="liste-compteur">
            {/* T4-B4-013 — rien de lu (lecture en cours, ou échec dit plus bas) : jamais un faux « 0 projet ». */}
            {data == null ? (loading ? 'Chargement…' : '') : nombreProjets(total)}
          </span>
        </div>
        <div className="cliste-recherche relative flex h-11 w-full items-center gap-2 px-3 sm:w-[340px]">
          <Search size={18} className="text-muted-foreground" aria-hidden="true" />
          <label htmlFor="cal-q" className="sr-only">Rechercher un calepinage</label>
          <input
            id="cal-q"
            type="search"
            className="min-w-0 flex-1 border-0 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            value={q}
            placeholder="Client, ville ou lead"
            onChange={(e) => surFiltre(setQ)(e.target.value)}
          />
        </div>
        <Button className="cliste-action h-11 gap-2 px-[18px] font-bold" onClick={() => navigate('/calepinage/nouveau')}>
          <Plus size={18} aria-hidden="true" />
          <span className="cliste-action-texte">Nouveau calepinage</span>
        </Button>
      </div>

      {/* Les puces d'état : celles du serveur (Brouillon, Validé, Périmé, Refusé), chacune avec son effectif quand il est servi. */}
      <div className="flex flex-wrap items-center gap-2">
      <div role="group" aria-label="Filtrer par état" data-testid="cal-liste-filtres-etat"
        className="cliste-puces flex flex-wrap items-center gap-2"
        data-replie={String(!filtresVisibles && !statut && !estMoi)}>
        {puces.map(([valeur, libelle]) => (
          <button key={valeur || 'tous'} type="button" aria-pressed={statut === valeur}
            className="cliste-puce"
            onClick={() => surFiltre(setStatut)(valeur)}>
            {libelle}
            {nombreDe(valeur) !== null && nombreDe(valeur) !== undefined ? (
              <span className="cliste-puce-n">
                {nombreDe(valeur)}
              </span>
            ) : null}
          </button>
        ))}
        {idMoi !== undefined && idMoi !== null ? (
          <>
            <div className="mx-1 h-7 w-px bg-border" aria-hidden="true" />
            <button type="button" className="cliste-puce" aria-pressed={estMoi}
              onClick={() => surFiltre(setResponsable)(estMoi ? '' : String(idMoi))}>
              <User size={16} aria-hidden="true" />
              Mes calepinages
            </button>
          </>
        ) : null}
      </div>
        {/* « Comparer » et « Filtres » : deux vraies fonctions hors maquette — discrètes (pictogramme seul,
            le libellé se lit à voix haute et en infobulle), la recherche et « Nouveau calepinage » dominent. */}
        <span className="ml-auto flex items-center gap-1">
          <Button type="button" variant="ghost" className={calme(modeComparaison)}
            title="Comparer" aria-pressed={modeComparaison}
            onClick={() => (modeComparaison ? quitterComparaison() : setModeComparaison(true))}
            data-testid="cal-mode-comparer">
            <Columns3 size={16} aria-hidden="true" />
            <span className={modeComparaison ? undefined : 'sr-only'}>
              {modeComparaison ? 'Annuler la comparaison' : 'Comparer'}
            </span>
          </Button>
          <Button type="button" variant="ghost" className={calme(nbAvances > 0)} title="Filtres"
            aria-expanded={filtresVisibles} aria-controls="acal957-filtres" data-testid="acal957-filtres-basculer"
            onClick={() => setFiltresOuverts((v) => !v)}>
            <SlidersHorizontal size={16} aria-hidden="true" />
            <span className={nbAvances ? undefined : 'sr-only'}>
              {`Filtres${nbAvances ? ` · ${nbAvances} actif${nbAvances > 1 ? 's' : ''}` : ''}`}
            </span>
          </Button>
        </span>
      </div>

      {modeComparaison ? (
        <Card className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm"
          data-testid="cal-barre-comparaison">
          <span>
            {`${selection.length} / ${BORNE_COMPARAISON} calepinage(s) sélectionné(s)`}
            {selection.length < 2 ? ' — cochez-en au moins deux.' : ''}
          </span>
          <Button size="sm" disabled={selection.length < 2} onClick={ouvrirComparaison}
            data-testid="cal-ouvrir-comparaison">
            Comparer la sélection
          </Button>
        </Card>
      ) : null}

      {/* Les filtres de la liste, TOUS conservés (ACAL957 : « le DOM garde tout ») — repliés par défaut. */}
      <Card className={`${filtresVisibles ? 'grid' : 'hidden'} gap-3 p-3 sm:grid-cols-2 lg:grid-cols-6`}
        id="acal957-filtres" data-testid="acal957-filtres">
        <div className="space-y-1">
          <Label htmlFor="cal-statut">Statut</Label>
          <Select value={statut || '__tous__'} onValueChange={(v) => surFiltre(setStatut)(v === '__tous__' ? '' : v)}>
            <SelectTrigger id="cal-statut"><SelectValue placeholder="Tous les statuts" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__tous__">Tous les statuts</SelectItem>
              {optionsStatut.map(([valeur, libelle]) => (
                <SelectItem key={valeur} value={valeur}>{libelle}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label htmlFor="cal-depuis">Modifié depuis le</Label>
          <Input
            id="cal-depuis"
            type="date"
            value={depuis}
            onChange={(e) => surFiltre(setDepuis)(e.target.value)}
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="cal-lead">Lead</Label>
          <Combobox
            id="cal-lead"
            value={lead}
            onChange={surFiltre(setLead)}
            onSearch={chercherLeads}
            placeholder="Tous les leads"
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="cal-client">Client</Label>
          <Combobox
            id="cal-client"
            value={client}
            onChange={surFiltre(setClient)}
            onSearch={chercherClients}
            placeholder="Tous les clients"
          />
        </div>

        {/* CALX406 — la colonne « Responsable » filtre VRAIMENT (`?responsable=`). */}
        <div className="space-y-1">
          <Label htmlFor="cal-responsable">Responsable</Label>
          <Select value={responsable || '__tous__'}
            onValueChange={(v) => surFiltre(setResponsable)(v === '__tous__' ? '' : v)}>
            <SelectTrigger id="cal-responsable"><SelectValue placeholder="Tous les responsables" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__tous__">Tous les responsables</SelectItem>
              {optionsResponsable.map(([valeur, nom]) => (
                <SelectItem key={valeur} value={valeur}>{nom}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label htmlFor="cal-tri">Tri</Label>
          <Select value={champTri || '__defaut__'} onValueChange={changerChampTri}>
            <SelectTrigger id="cal-tri"><SelectValue placeholder="Tri par défaut" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__defaut__">Tri par défaut</SelectItem>
              {CHAMPS_TRI.map(([valeur, libelle]) => (
                <SelectItem key={valeur} value={valeur}>{libelle}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {champTri ? (
          <div className="space-y-1">
            <Label htmlFor="cal-tri-sens">Ordre</Label>
            <Select value={decroissant ? 'desc' : 'asc'}
              onValueChange={(v) => changerSensTri(v === 'desc')}>
              <SelectTrigger id="cal-tri-sens"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="asc">Croissant</SelectItem>
                <SelectItem value="desc">Décroissant</SelectItem>
              </SelectContent>
            </Select>
          </div>
        ) : null}

        {/* CALX344 — le filtre par étiquette libre (vocabulaire de la société,
            tag système exclu), sur toute la largeur de la carte. */}
        <div className="sm:col-span-2 lg:col-span-6">
          <FiltreEtiquettes valeur={etiquettes} onChange={surFiltre(setEtiquettes)} />
        </div>

        {filtreActif ? (
          <div className="sm:col-span-2 lg:col-span-6">
            <Button size="sm" variant="ghost" onClick={reinitialiser}>
              <X size={15} aria-hidden="true" />
              Réinitialiser les filtres
            </Button>
          </div>
        ) : null}
      </Card>

      {error ? (
        <Card className="flex flex-wrap items-center gap-3 p-4 text-sm text-destructive" role="alert">
          <span className="flex-1">{error}</span>
          <Button type="button" variant="outline" className="h-11" onClick={() => refetch()}>Réessayer</Button>
        </Card>
      ) : null}

      {loading ? (
        <div className="flex justify-center py-10"><Spinner /></div>
      ) : null}

      {!loading && !error && lignes.length === 0 ? (
        <EmptyState
          icon={LayoutGrid}
          title={filtreActif ? 'Aucun calepinage ne correspond à ces filtres' : 'Aucun calepinage pour l’instant'}
          description={filtreActif
            ? 'Élargissez la recherche, ou réinitialisez les filtres pour revoir toute la liste.'
            : 'Un calepinage part d’un lead ou d’un client : choisissez-en un, et l’atelier s’ouvre sur son toit. Vous pourrez ensuite générer le devis depuis le calepinage.'}
          action={filtreActif ? (
            <Button size="sm" variant="outline" onClick={reinitialiser}>Réinitialiser les filtres</Button>
          ) : (
            <Button size="sm" onClick={() => navigate('/calepinage/nouveau')}>
              <Plus size={16} aria-hidden="true" />
              Créer un calepinage
            </Button>
          )}
        />
      ) : null}

      {!loading && lignes.length > 0 ? (
        <>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {lignes.map((ligne) => (
              <VignetteCalepinage
                key={ligne.id}
                calepinage={ligne}
                selection={modeComparaison ? {
                  coche: selection.includes(ligne.id),
                  desactive: !selection.includes(ligne.id)
                    && selection.length >= BORNE_COMPARAISON,
                  basculer: basculerSelection,
                } : null}
              />
            ))}
          </div>
          <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
            <span>{`${lignes.length} calepinage(s) affiché(s)${typeof total === 'number' ? ` sur ${total}` : ''}`}</span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1 || (!Array.isArray(data) && !pagePrecedente)}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Précédent
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!pageSuivante}
                onClick={() => setPage((p) => p + 1)}
              >
                Suivant
              </Button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
