import { useEffect, useState } from 'react'
import calepinageApi from '../../api/calepinageApi'
import { useHasPermission } from '../../hooks/useHasPermission'
import { Badge, Card, Spinner } from '../../ui'

/* ============================================================================
   CAL201 — L'ÉCRAN « BIBLIOTHÈQUE » DU MODULE (presets, kits, modèles,
   favoris), SOCIÉTÉ ACTIVE RESPECTÉE.
   ----------------------------------------------------------------------------
   Constat : aucune surface frontend n'exposait ces réglages hors du studio
   d'appels d'offres — le module autonome n'avait nulle part où les consulter.

   LES QUATRE LISTES VIENNENT DE DEUX ENDPOINTS, JAMAIS D'UNE TROISIÈME
   FORME (CAL233/CAL246) :
     * `GET /calepinage/parametres/` sert `presets`, `favoris_materiel` (les
       deux sections de `ParametresCalepinage`, CAL197/CAL200) et `kits` (le
       catalogue du module, résolu à la lecture, CAL198/SOLMVP15) ;
     * `GET /calepinage/calepinages/modeles/` sert les calepinages marqués
       MODÈLE (drapeau `records.Tag`, CAL199).

   LECTURE SEULE SANS `calepinage_gerer` (Done de la tâche) : l'écran affiche
   TOUJOURS les quatre listes — seule l'ÉDITION des presets/favoris (les deux
   sections que `PUT /calepinage/parametres/` accepte SANS normaliseur dédié,
   `services/parametres.py::_normaliseurs`) est gardée par la permission.
   Kits et modèles restent lecture seule ICI QUEL QUE SOIT LE DROIT : aucun
   endpoint d'écriture n'existe pour eux depuis cet écran — la tâche ne
   l'invente pas, elle le DIT (PACT159, jamais une promesse en prose).
   ========================================================================== */

function Section({ titre, sousTitre, children }) {
  return (
    <Card className="p-4" data-testid={`cal-biblio-${titre.toLowerCase()}`}>
      <p className="text-sm font-semibold text-foreground">{titre}</p>
      {sousTitre && <p className="mt-0.5 text-xs text-muted-foreground">{sousTitre}</p>}
      <div className="mt-3">{children}</div>
    </Card>
  )
}

function ListeVide({ enfant }) {
  return <p className="text-sm text-muted-foreground">{enfant}</p>
}

/* ============================================================================
   CALX30 — LES PROFILS TYPES DE CONSOMMATION, ÉDITABLES ICI.
   ----------------------------------------------------------------------------
   `views/consommation.py` sert `GET/PUT parametres/profils-types/` depuis
   CAL149 et n'avait AUCUN consommateur : la société ne pouvait pas saisir la
   forme de ses journées, donc tout le dépôt retombait sur les profils CODÉS
   (`apps/ventes/solar_design.py`) — ceux qui décident du taux
   d'autoconsommation, donc de la taille du champ et de la batterie vendus.

   LES DEUX RÈGLES QUE CET ÉCRAN NE PEUT PAS ENFREINDRE :
   1. **Un repli reste un repli.** Le serveur l'étiquette `hypothese_interne`
      et publie sa provenance ; l'écran l'AFFICHE comme tel, ne l'édite pas et
      ne le renvoie JAMAIS dans le PUT — sinon une hypothèse interne
      deviendrait une « saisie de la société », c'est-à-dire une mesure.
   2. **Aucune valeur n'est inventée ici.** Un profil neuf part avec ses
      champs VIDES : c'est le serveur (`ProfilTypeConsommation.clean`) qui
      refuse une provenance vide ou une courbe absente, et son motif s'affiche
      SOUS le profil fautif.
   ========================================================================== */

//: Le serveur étiquette ainsi tout profil qui n'est PAS une saisie société.
const SOURCE_REPLI = 'hypothese_interne'

//: `ProfilTypeConsommation.Famille` — les familles ADMISES par le serveur.
const FAMILLES = [
  ['residentiel', 'Résidentiel'],
  ['commercial', 'Commercial / tertiaire'],
  ['industriel', 'Industriel'],
  ['agricole', 'Agricole'],
  ['autre', 'Autre'],
]

/** `{rang, message}` du refus serveur, ramené au profil ENVOYÉ qu'il NOMME.
 *
 * `services/profils_types.py` nomme son champ de quatre façons :
 * `profils`, `profils[N].cle`, `<cle>` et `<cle>.<champ>`. `rang` est
 * l'indice DANS LA LISTE ENVOYÉE, `null` quand le refus porte sur la liste
 * entière (ou sur la société). Le message est celui du serveur, mot pour mot.
 */
function refusProfil(erreur, clesEnvoyees) {
  const aucunMotif = {
    rang: null,
    message: "Le serveur n’a rendu aucun motif : rien n’a été enregistré.",
  }
  const corps = erreur?.response?.data
  if (!corps || typeof corps !== 'object') return aucunMotif
  const entree = Object.entries(corps)[0]
  if (!entree) return aucunMotif
  const [champ, brut] = entree
  const message = Array.isArray(brut) ? brut.join(' ') : String(brut)
  const indice = /^profils\[(\d+)\]/.exec(champ)
  if (indice) return { rang: Number(indice[1]), message }
  const racine = champ.split('.')[0]
  const rang = clesEnvoyees.indexOf(racine)
  return { rang: rang >= 0 ? rang : null, message }
}

/** La courbe annuelle SERVIE, telle quelle — jamais arrondie (arrondir un
 *  poids, c'est le changer). Les autres saisons ne sont pas éditées ici et
 *  traversent intactes. */
function texteCourbeAnnuelle(profil) {
  const annuel = (profil.courbes ?? {}).annuel
  return Array.isArray(annuel) ? annuel.join(', ') : ''
}

/** Le profil, sous la forme que `PUT profils-types/` attend (`courbe`, au
 *  singulier — le GET sert `courbes`, normalisées). */
function corpsProfil(profil) {
  const courbe = { ...(profil.courbes ?? {}) }
  const texte = (profil.courbeTexte ?? '').trim()
  if (texte) {
    // Une valeur illisible part TELLE QUELLE : c'est le serveur qui juge et
    // qui nomme le champ, pas l'écran qui devine un nombre de remplacement.
    courbe.annuel = texte.split(',').map((brut) => {
      const valeur = brut.trim()
      const nombre = Number(valeur)
      return valeur !== '' && Number.isFinite(nombre) ? nombre : valeur
    })
  } else {
    delete courbe.annuel
  }
  const corps = {
    cle: profil.cle,
    libelle: profil.libelle,
    courbe,
    provenance: profil.provenance,
    actif: profil.actif !== false,
  }
  // Famille non choisie : on ne l'envoie PAS — le serveur applique alors son
  // propre défaut documenté, plutôt que l'écran qui en invente un.
  if (profil.famille) corps.famille = profil.famille
  return corps
}

/* ============================================================================
   CALX43 — PRÉRÉGLAGES ET FAVORIS MATÉRIEL : ÉDITABLES, ENFIN.
   ----------------------------------------------------------------------------
   Les deux sections s'écrivaient DÉJÀ par `PUT /calepinage/parametres/`
   (`services/parametres.py`, mise à jour partielle au niveau SECTION), et cet
   écran se contentait d'expliquer que « la création/édition n'est pas
   proposée ici ». Elle l'est maintenant, par cette même porte — aucune
   seconde route n'est inventée.

   CE QUE L'ÉCRAN NE TOUCHE PAS. La section `presets` porte aussi deux
   entrées de LISTE qui appartiennent à d'autres chemins d'écriture :
   `jeux` (les presets maison, `services/presets.py`) et `kits` (le catalogue
   de pose, réglé depuis le stock). `enregistrer_parametres` REMPLACE la
   section entière : ces deux entrées sont donc relues et renvoyées TELLES
   QUELLES, exactement comme `services/presets.py::_section` le fait déjà —
   sans quoi une édition de préréglage effacerait le catalogue de kits.

   LA PROVENANCE. `presets` et `favoris_materiel` n'ont AUJOURD'HUI aucun
   normaliseur serveur (`services/parametres.py::_normaliseurs` n'en déclare
   que cinq : imagerie, zones_types, degagements, gabarits_disposition,
   lestage) : rien côté serveur ne refuse une valeur sans source. C'est donc
   l'écran qui refuse AVANT d'envoyer, en pointant la ligne — et tout refus
   que le serveur rendrait s'affiche au MÊME endroit, sous la même ligne.
   ========================================================================== */

//: La clé qui porte la PROVENANCE d'un préréglage, dans son propre objet.
const CLE_SOURCE = 'source'

//: Les entrées de `presets` qui ne sont PAS des préréglages de cet écran :
//: elles ont leur propre chemin d'écriture et traversent intactes.
const PRESETS_RESERVES = ['jeux', 'kits']

/** Les champs d'un préréglage, un « champ = valeur » par ligne. */
function texteChamps(valeur) {
  return Object.entries(valeur ?? {})
    .filter(([champ]) => champ !== CLE_SOURCE)
    .map(([champ, brut]) => `${champ} = ${brut}`)
    .join('\n')
}

/** `{champs, erreur}` — une ligne sans « = » est refusée en la citant. */
function champsDepuisTexte(texte) {
  const champs = {}
  for (const ligne of String(texte || '').split('\n')) {
    const brut = ligne.trim()
    if (!brut) continue
    const coupe = brut.indexOf('=')
    if (coupe <= 0) {
      return {
        champs: null,
        erreur: `Ligne « ${brut} » : chaque valeur s’écrit « champ = valeur ».`,
      }
    }
    const champ = brut.slice(0, coupe).trim()
    const valeur = brut.slice(coupe + 1).trim()
    const nombre = Number(valeur)
    champs[champ] = valeur !== '' && Number.isFinite(nombre) ? nombre : valeur
  }
  return { champs, erreur: null }
}

/** La section `presets` ENTIÈRE, réservés compris — ou le refus, ligne visée. */
function sectionPresets(lignes, reserves) {
  const section = { ...reserves }
  for (let rang = 0; rang < lignes.length; rang += 1) {
    const ligne = lignes[rang]
    const cle = (ligne.cle || '').trim()
    if (!cle) {
      return { section: null, refus: { rang, message: 'Ce préréglage n’a pas de nom : donnez-lui-en un, ou retirez-le.' } }
    }
    if (PRESETS_RESERVES.includes(cle)) {
      return { section: null, refus: { rang, message: `« ${cle} » est réservé (il a son propre écran) : choisissez un autre nom.` } }
    }
    const { champs, erreur } = champsDepuisTexte(ligne.champsTexte)
    if (erreur) return { section: null, refus: { rang, message: erreur } }
    if (Object.keys(champs).length === 0) {
      return { section: null, refus: { rang, message: 'Ce préréglage ne porte aucune valeur : ajoutez-en une, ou retirez-le.' } }
    }
    const source = (ligne.source || '').trim()
    if (!source) {
      return { section: null, refus: { rang, message: 'Chaque valeur doit porter sa source : d’où vient ce préréglage ? Sans source, il n’est pas enregistré.' } }
    }
    section[cle] = { ...champs, [CLE_SOURCE]: source }
  }
  return { section, refus: null }
}

/** La section `favoris_materiel` ENTIÈRE — ou le refus, ligne visée. */
function sectionFavoris(lignes) {
  const section = {}
  for (let rang = 0; rang < lignes.length; rang += 1) {
    const ligne = lignes[rang]
    const role = (ligne.role || '').trim()
    if (!role) {
      return { section: null, refus: { rang, message: 'Ce favori n’a pas de rôle : nommez-le, ou retirez-le.' } }
    }
    const ids = []
    for (const brut of String(ligne.idsTexte || '').split(',')) {
      const valeur = brut.trim()
      if (!valeur) continue
      // Un favori DÉSIGNE un produit du catalogue par son identifiant : une
      // valeur qui n'en est pas un ne désigne rien, et n'est pas enregistrée.
      if (!/^\d+$/.test(valeur)) {
        return { section: null, refus: { rang, message: `« ${valeur} » n’est pas un identifiant de produit : un favori désigne une fiche du catalogue.` } }
      }
      ids.push(Number(valeur))
    }
    if (ids.length === 0) {
      return { section: null, refus: { rang, message: 'Ce favori ne désigne aucun produit : indiquez au moins un identifiant, ou retirez la ligne.' } }
    }
    section[role] = ids
  }
  return { section, refus: null }
}

/** Les BROUILLONS d'édition, dérivés des réglages servis. Fonction PURE (hors
 *  composant) : l'effet de chargement la lit sans devenir une dépendance. */
function brouillonsDepuis(reglages) {
  const presets = reglages?.presets ?? {}
  const favoris = reglages?.favoris_materiel ?? {}
  const reserves = {}
  const lignes = []
  for (const [cle, valeur] of Object.entries(presets)) {
    // Ce qui n'est pas un objet de valeurs (les listes `jeux`/`kits`) n'est
    // pas un préréglage de cet écran : il est GARDÉ, jamais réécrit.
    const editable = valeur && typeof valeur === 'object'
      && !Array.isArray(valeur) && !PRESETS_RESERVES.includes(cle)
    if (!editable) {
      reserves[cle] = valeur
      continue
    }
    lignes.push({
      cle,
      champsTexte: texteChamps(valeur),
      source: typeof valeur[CLE_SOURCE] === 'string' ? valeur[CLE_SOURCE] : '',
    })
  }
  return {
    presets: lignes,
    reserves,
    favoris: Object.entries(favoris).map(([role, ids]) => ({
      role,
      idsTexte: Array.isArray(ids) ? ids.join(', ') : String(ids ?? ''),
    })),
  }
}

/** Le refus SERVEUR d'un `PUT parametres/` : `{<section>: "<motif>"}`. */
function refusSection(erreur) {
  const corps = erreur?.response?.data
  if (corps && typeof corps === 'object') {
    const entree = Object.entries(corps)[0]
    if (entree) {
      const brut = Array.isArray(entree[1]) ? entree[1].join(' ') : entree[1]
      if (brut) return String(brut)
    }
  }
  return "Le serveur n’a rendu aucun motif : rien n’a été enregistré."
}

export default function Bibliotheque() {
  const peutGerer = useHasPermission('calepinage_gerer')

  const [parametres, setParametres] = useState(null)
  const [modeles, setModeles] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState(null)
  // CALX30 — les profils types, SERVIS puis édités sur place. `refusProfils`
  // porte la clé du profil fautif : l'erreur s'affiche SOUS lui, jamais en
  // haut de page comme un « non enregistré » anonyme.
  const [profils, setProfils] = useState(null)
  const [refusProfils, setRefusProfils] = useState(null)
  const [enregistrementProfils, setEnregistrementProfils] = useState(false)
  // CALX43 — les deux sections éditables, en brouillon local jusqu'au PUT.
  const [presetsEdit, setPresetsEdit] = useState([])
  const [presetsReserves, setPresetsReserves] = useState({})
  const [refusPresets, setRefusPresets] = useState(null)
  const [ecriturePresets, setEcriturePresets] = useState(false)
  const [favorisEdit, setFavorisEdit] = useState([])
  const [refusFavoris, setRefusFavoris] = useState(null)
  const [ecritureFavoris, setEcritureFavoris] = useState(false)
  // CALX42 — « Partir de ce modèle » : le modèle ouvert, la saisie du NOUVEAU
  // rattachement, le refus du serveur, et le calepinage créé.
  const [modeleOuvert, setModeleOuvert] = useState(null)
  const [depart, setDepart] = useState({ lead: '', client: '' })
  const [refusDepart, setRefusDepart] = useState(null)
  const [creation, setCreation] = useState(false)
  const [calepinageCree, setCalepinageCree] = useState(null)

  useEffect(() => {
    let annule = false
    Promise.all([
      Promise.resolve(calepinageApi.parametres.get()),
      Promise.resolve(calepinageApi.calepinages.modeles()),
      Promise.resolve(calepinageApi.parametres.profilsTypes()),
    ])
      .then(([resParametres, resModeles, resProfils]) => {
        if (annule) return
        setParametres(resParametres?.data ?? null)
        const brouillons = brouillonsDepuis(resParametres?.data ?? null)
        setPresetsEdit(brouillons.presets)
        setPresetsReserves(brouillons.reserves)
        setFavorisEdit(brouillons.favoris)
        const liste = resModeles?.data
        setModeles(Array.isArray(liste) ? liste : (liste?.results ?? []))
        const servis = resProfils?.data?.profils
        setProfils((Array.isArray(servis) ? servis : []).map((profil) => ({
          ...profil, courbeTexte: texteCourbeAnnuelle(profil),
        })))
      })
      .catch((e) => {
        if (annule) return
        setErreur(e?.response?.data?.detail
          || 'La bibliothèque n’a pas pu être chargée.')
      })
      .finally(() => { if (!annule) setChargement(false) })
    return () => { annule = true }
  }, [])

  if (chargement) {
    return <div className="page" data-testid="cal-bibliotheque"><Spinner /></div>
  }
  if (erreur) {
    return (
      <div className="page" data-testid="cal-bibliotheque">
        <p role="alert" className="text-sm text-destructive"
          data-testid="cal-biblio-erreur">{erreur}</p>
      </div>
    )
  }

  const presets = parametres?.presets ?? {}
  const favoris = parametres?.favoris_materiel ?? {}
  const kits = Array.isArray(parametres?.kits) ? parametres.kits : []

  const clesPresets = Object.keys(presets)
  const clesFavoris = Object.keys(favoris)

  // ── CALX30 — les gestes des profils types ────────────────────────────────
  const lignesProfils = profils ?? []
  const estRepli = (profil) => profil.source === SOURCE_REPLI

  const majProfil = (rang, champ, valeur) => {
    setProfils((liste) => (liste ?? []).map(
      (profil, i) => (i === rang ? { ...profil, [champ]: valeur } : profil)))
  }
  const retirerProfil = (rang) => {
    setRefusProfils(null)
    setProfils((liste) => (liste ?? []).filter((_, i) => i !== rang))
  }
  const ajouterProfil = () => {
    setRefusProfils(null)
    // TOUT VIDE : aucune valeur par défaut n'est inventée ici. C'est le
    // serveur qui refuse, et son motif s'affiche sous ce profil.
    setProfils((liste) => [...(liste ?? []), {
      id: null, cle: '', libelle: '', famille: '', provenance: '',
      source: 'societe', courbes: {}, courbeTexte: '',
    }])
  }

  // Les rangs AFFICHÉS des profils qui partent au serveur (les replis, eux,
  // ne partent jamais) : c'est la table de correspondance qui ramène un refus
  // « profils[N] » sur la bonne ligne de l'écran.
  const rangsEnvoyes = lignesProfils
    .map((profil, rang) => (estRepli(profil) ? null : rang))
    .filter((rang) => rang !== null)
  const rangFautif = refusProfils && refusProfils.rang !== null
    ? rangsEnvoyes[refusProfils.rang] ?? null
    : null

  // ── CALX43 — les gestes des préréglages et des favoris ───────────────────
  const majPreset = (rang, champ, valeur) => {
    setPresetsEdit((liste) => liste.map(
      (ligne, i) => (i === rang ? { ...ligne, [champ]: valeur } : ligne)))
  }
  const retirerPreset = (rang) => {
    setRefusPresets(null)
    setPresetsEdit((liste) => liste.filter((_, i) => i !== rang))
  }
  const ajouterPreset = () => {
    setRefusPresets(null)
    // Tout vide : aucun préréglage n'est créé avec une valeur inventée.
    setPresetsEdit((liste) => [...liste,
      { cle: '', champsTexte: '', source: '' }])
  }

  const enregistrerPresets = async () => {
    const { section, refus } = sectionPresets(presetsEdit, presetsReserves)
    if (refus) {
      setRefusPresets(refus)
      return
    }
    setEcriturePresets(true)
    setRefusPresets(null)
    try {
      const res = await calepinageApi.parametres.update({ presets: section })
      // La réponse du PUT ne porte pas `kits` (clé DÉRIVÉE, ajoutée par le
      // GET seul) : on fusionne pour ne pas faire disparaître le catalogue.
      if (res?.data) setParametres((avant) => ({ ...(avant ?? {}), ...res.data }))
    } catch (e) {
      setRefusPresets({ rang: null, message: refusSection(e) })
    } finally {
      setEcriturePresets(false)
    }
  }

  const majFavori = (rang, champ, valeur) => {
    setFavorisEdit((liste) => liste.map(
      (ligne, i) => (i === rang ? { ...ligne, [champ]: valeur } : ligne)))
  }
  const retirerFavori = (rang) => {
    setRefusFavoris(null)
    setFavorisEdit((liste) => liste.filter((_, i) => i !== rang))
  }
  const ajouterFavori = () => {
    setRefusFavoris(null)
    setFavorisEdit((liste) => [...liste, { role: '', idsTexte: '' }])
  }

  const enregistrerFavoris = async () => {
    const { section, refus } = sectionFavoris(favorisEdit)
    if (refus) {
      setRefusFavoris(refus)
      return
    }
    setEcritureFavoris(true)
    setRefusFavoris(null)
    try {
      const res = await calepinageApi.parametres.update(
        { favoris_materiel: section })
      if (res?.data) setParametres((avant) => ({ ...(avant ?? {}), ...res.data }))
    } catch (e) {
      setRefusFavoris({ rang: null, message: refusSection(e) })
    } finally {
      setEcritureFavoris(false)
    }
  }

  // ── CALX42 — partir d'un modèle ──────────────────────────────────────────
  const ouvrirDepart = (modeleId) => {
    setRefusDepart(null)
    setCalepinageCree(null)
    setDepart({ lead: '', client: '' })
    setModeleOuvert(modeleId)
  }

  const partirDuModele = async () => {
    setCreation(true)
    setRefusDepart(null)
    try {
      // Le rattachement n'est PAS deviné : ce qui est laissé vide n'est pas
      // envoyé, et le serveur refuse quand les deux manquent, en nommant le
      // champ (`services/modeles.py::creer_depuis_modele`).
      const corps = { modele: modeleOuvert }
      if (depart.lead.trim()) corps.lead = depart.lead.trim()
      if (depart.client.trim()) corps.client = depart.client.trim()
      const res = await calepinageApi.calepinages.creerDepuisModele(corps)
      const cree = res?.data?.id ?? null
      setCalepinageCree(cree)
      if (cree) setModeleOuvert(null)
    } catch (e) {
      setRefusDepart(refusSection(e))
    } finally {
      setCreation(false)
    }
  }

  const enregistrerProfils = async () => {
    const aSoumettre = lignesProfils.filter((profil) => !estRepli(profil))
    setEnregistrementProfils(true)
    setRefusProfils(null)
    try {
      const res = await calepinageApi.parametres.enregistrerProfilsTypes(
        aSoumettre.map(corpsProfil))
      const servis = res?.data?.profils
      if (Array.isArray(servis)) {
        setProfils(servis.map((profil) => ({
          ...profil, courbeTexte: texteCourbeAnnuelle(profil),
        })))
      }
    } catch (e) {
      setRefusProfils(refusProfil(e, aSoumettre.map((p) => p.cle)))
    } finally {
      setEnregistrementProfils(false)
    }
  }

  return (
    <div className="page" data-testid="cal-bibliotheque">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="text-lg font-semibold text-foreground">Bibliothèque</h1>
        {!peutGerer && (
          <Badge variant="outline" data-testid="cal-biblio-lecture-seule">
            Lecture seule
          </Badge>
        )}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Presets, kits de pose, calepinages modèles et matériel favori de votre
        société — réutilisés à chaque conception, jamais réinventés.
      </p>
      {/* CALX69 — les réglages de simulation et d'électrique vivent sur leur
          propre écran (une ligne par clé, provenance obligatoire) : un lien
          plutôt qu'un `<Link>` de routeur, cet écran restant testé sans
          contexte de routeur. */}
      <p className="mt-2 text-sm">
        <a href="/calepinage/reglages" className="underline" data-testid="cal-biblio-lien-reglages">
          Réglages de simulation et d’électrique
        </a>
      </p>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Section titre="Presets"
          sousTitre="Marges, espacements et dégagements réutilisés (CAL197)">
          {clesPresets.length === 0
            ? <ListeVide enfant="Aucun preset réglé : les valeurs de l’atelier s’appliquent." />
            : (
              <ul className="space-y-1 text-sm text-foreground" data-testid="cal-biblio-presets-liste">
                {clesPresets.map((cle) => (
                  <li key={cle} data-testid={`cal-biblio-preset-${cle}`}>
                    <span className="font-medium">{cle}</span>
                    {' — '}
                    <span className="text-muted-foreground">
                      {Object.entries(presets[cle] ?? {})
                        .map(([champ, valeur]) => `${champ} : ${valeur}`)
                        .join(', ') || 'aucun champ'}
                    </span>
                  </li>
                ))}
              </ul>
            )}

          {/* CALX43 — L'ÉDITION, par la porte `parametres` existante. */}
          {peutGerer ? (
            <div className="mt-3 space-y-3" data-testid="cal-biblio-presets-edition">
              {presetsEdit.map((ligne, rang) => (
                <div key={`preset-${rang}`} className="border border-border p-2"
                  data-testid={`cal-biblio-preset-ligne-${rang}`}>
                  <label className="text-xs text-muted-foreground">
                    Nom du préréglage
                    <input type="text" value={ligne.cle} disabled={ecriturePresets}
                      data-testid={`cal-biblio-preset-cle-${rang}`}
                      onChange={(e) => majPreset(rang, 'cle', e.target.value)}
                      className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                  </label>
                  <label className="mt-2 block text-xs text-muted-foreground">
                    Valeurs — une par ligne, « champ = valeur »
                    <textarea rows={3} value={ligne.champsTexte}
                      disabled={ecriturePresets}
                      data-testid={`cal-biblio-preset-champs-${rang}`}
                      onChange={(e) => majPreset(rang, 'champsTexte', e.target.value)}
                      className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                  </label>
                  <label className="mt-2 block text-xs text-muted-foreground">
                    Source (obligatoire) — d’où viennent ces valeurs
                    <input type="text" value={ligne.source} disabled={ecriturePresets}
                      data-testid={`cal-biblio-preset-source-${rang}`}
                      onChange={(e) => majPreset(rang, 'source', e.target.value)}
                      className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                  </label>
                  <button type="button" disabled={ecriturePresets}
                    className="mt-2 text-xs text-destructive underline"
                    data-testid={`cal-biblio-preset-retirer-${rang}`}
                    onClick={() => retirerPreset(rang)}>
                    Retirer ce préréglage
                  </button>
                  {/* LE MOTIF SOUS LA LIGNE FAUTIVE, jamais ailleurs. */}
                  {refusPresets?.rang === rang && (
                    <p className="mt-2 text-xs text-destructive" role="alert"
                      data-testid={`cal-biblio-preset-erreur-${rang}`}>
                      {refusPresets.message}
                    </p>
                  )}
                </div>
              ))}
              <div className="flex flex-wrap items-center gap-3">
                <button type="button" disabled={ecriturePresets}
                  className="text-sm font-semibold underline"
                  data-testid="cal-biblio-preset-ajouter" onClick={ajouterPreset}>
                  Ajouter un préréglage
                </button>
                <button type="button" disabled={ecriturePresets}
                  className="text-sm font-semibold underline"
                  data-testid="cal-biblio-presets-enregistrer"
                  onClick={enregistrerPresets}>
                  Enregistrer les préréglages
                </button>
              </div>
              {refusPresets && refusPresets.rang === null && (
                <p className="text-xs text-destructive" role="alert"
                  data-testid="cal-biblio-presets-erreur">
                  {refusPresets.message}
                </p>
              )}
            </div>
          ) : (
            <p className="mt-2 text-xs text-muted-foreground">
              Sans le droit « gérer le calepinage », la création/édition des
              presets n’est pas proposée ici.
            </p>
          )}
        </Section>

        <Section titre="Kits"
          sousTitre="Catalogue de pose du stock, lu (jamais dupliqué, CAL198)">
          {kits.length === 0
            ? <ListeVide enfant="Aucun kit de pose disponible pour votre société." />
            : (
              <ul className="space-y-1 text-sm text-foreground" data-testid="cal-biblio-kits-liste">
                {kits.map((kit) => (
                  <li key={kit.id} data-testid={`cal-biblio-kit-${kit.id}`}>
                    <span className="font-medium">{kit.libelle || kit.code}</span>
                    {' — '}
                    <span className="text-muted-foreground">
                      {kit.modules_par_kit != null
                        ? `${kit.modules_par_kit} module(s)/kit`
                        : 'composition non renseignée'}
                      {kit.puissance_module_w ? ` · ${kit.puissance_module_w} W` : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          <p className="mt-2 text-xs text-muted-foreground">
            Catalogue en lecture seule depuis cet écran : gérez-le depuis le
            stock.
          </p>
        </Section>

        <Section titre="Modèles"
          sousTitre="Calepinages marqués réutilisables (CAL199)">
          {(modeles ?? []).length === 0
            ? <ListeVide enfant="Aucun calepinage n’est marqué modèle." />
            : (
              <ul className="space-y-1 text-sm text-foreground" data-testid="cal-biblio-modeles-liste">
                {modeles.map((modele) => (
                  <li key={modele.id} data-testid={`cal-biblio-modele-${modele.id}`}>
                    <span className="font-medium">
                      {modele.titre || `Calepinage #${modele.id}`}
                    </span>
                    {modele.statut_libelle && (
                      <span className="text-muted-foreground"> — {modele.statut_libelle}</span>
                    )}

                    {/* CALX42 — « Partir de ce modèle » : le rattachement est
                        SAISI, jamais repris du modèle. */}
                    {peutGerer && modeleOuvert !== modele.id && (
                      <button type="button" disabled={creation}
                        className="ml-2 text-xs font-semibold underline"
                        data-testid={`cal-biblio-modele-partir-${modele.id}`}
                        onClick={() => ouvrirDepart(modele.id)}>
                        Partir de ce modèle
                      </button>
                    )}

                    {peutGerer && modeleOuvert === modele.id && (
                      <div className="mt-2 border border-border p-2"
                        data-testid={`cal-biblio-modele-depart-${modele.id}`}>
                        <p className="text-xs text-muted-foreground">
                          Le lead ou le client du modèle n’est jamais recopié :
                          désignez le NOUVEAU rattachement.
                        </p>
                        <label className="mt-2 block text-xs text-muted-foreground">
                          Lead (identifiant)
                          <input type="text" value={depart.lead} disabled={creation}
                            data-testid="cal-biblio-modele-lead"
                            onChange={(e) => setDepart((d) => ({ ...d, lead: e.target.value }))}
                            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                        </label>
                        <label className="mt-2 block text-xs text-muted-foreground">
                          Client (identifiant)
                          <input type="text" value={depart.client} disabled={creation}
                            data-testid="cal-biblio-modele-client"
                            onChange={(e) => setDepart((d) => ({ ...d, client: e.target.value }))}
                            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                        </label>
                        <div className="mt-2 flex flex-wrap items-center gap-3">
                          <button type="button" disabled={creation}
                            className="text-xs font-semibold underline"
                            data-testid="cal-biblio-modele-creer"
                            onClick={partirDuModele}>
                            Créer le calepinage
                          </button>
                          <button type="button" disabled={creation}
                            className="text-xs underline"
                            data-testid="cal-biblio-modele-annuler"
                            onClick={() => { setModeleOuvert(null); setRefusDepart(null) }}>
                            Annuler
                          </button>
                        </div>
                        {refusDepart && (
                          <p className="mt-2 text-xs text-destructive" role="alert"
                            data-testid="cal-biblio-modele-erreur">
                            {refusDepart}
                          </p>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}

          {/* CALX42 — le calepinage CRÉÉ, ouvert depuis ici. Lien simple :
              cet écran ne dépend d'aucun routeur, et ouvrir l'atelier d'un
              calepinage neuf est un geste ponctuel. */}
          {calepinageCree && (
            <p className="mt-3 text-sm" role="status">
              <a className="font-semibold underline"
                data-testid="cal-biblio-modele-ouvrir"
                href={`/calepinage/${calepinageCree}`}>
                Ouvrir le calepinage créé (#{calepinageCree})
              </a>
            </p>
          )}
        </Section>

        <Section titre="Favoris matériel"
          sousTitre="Modules et onduleurs favoris du catalogue (CAL200)">
          {clesFavoris.length === 0
            ? <ListeVide enfant="Aucun matériel favori réglé pour votre société." />
            : (
              <ul className="space-y-1 text-sm text-foreground" data-testid="cal-biblio-favoris-liste">
                {clesFavoris.map((cle) => {
                  const ids = Array.isArray(favoris[cle]) ? favoris[cle] : []
                  return (
                    <li key={cle} data-testid={`cal-biblio-favori-${cle}`}>
                      <span className="font-medium">{cle}</span>
                      {' — '}
                      <span className="text-muted-foreground">
                        {ids.length > 0
                          ? `${ids.length} produit(s) (#${ids.join(', #')})`
                          : 'aucun produit'}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}

          {/* CALX43 — L'ÉDITION des favoris, même porte `parametres`. */}
          {peutGerer ? (
            <div className="mt-3 space-y-3" data-testid="cal-biblio-favoris-edition">
              {favorisEdit.map((ligne, rang) => (
                <div key={`favori-${rang}`} className="border border-border p-2"
                  data-testid={`cal-biblio-favori-ligne-${rang}`}>
                  <label className="text-xs text-muted-foreground">
                    Rôle (panneau, onduleur_hybride, …)
                    <input type="text" value={ligne.role} disabled={ecritureFavoris}
                      data-testid={`cal-biblio-favori-role-${rang}`}
                      onChange={(e) => majFavori(rang, 'role', e.target.value)}
                      className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                  </label>
                  <label className="mt-2 block text-xs text-muted-foreground">
                    Identifiants produits du catalogue, séparés par des virgules
                    <input type="text" value={ligne.idsTexte}
                      disabled={ecritureFavoris}
                      data-testid={`cal-biblio-favori-ids-${rang}`}
                      onChange={(e) => majFavori(rang, 'idsTexte', e.target.value)}
                      className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                  </label>
                  <button type="button" disabled={ecritureFavoris}
                    className="mt-2 text-xs text-destructive underline"
                    data-testid={`cal-biblio-favori-retirer-${rang}`}
                    onClick={() => retirerFavori(rang)}>
                    Retirer ce favori
                  </button>
                  {refusFavoris?.rang === rang && (
                    <p className="mt-2 text-xs text-destructive" role="alert"
                      data-testid={`cal-biblio-favori-erreur-${rang}`}>
                      {refusFavoris.message}
                    </p>
                  )}
                </div>
              ))}
              <div className="flex flex-wrap items-center gap-3">
                <button type="button" disabled={ecritureFavoris}
                  className="text-sm font-semibold underline"
                  data-testid="cal-biblio-favori-ajouter" onClick={ajouterFavori}>
                  Ajouter un favori
                </button>
                <button type="button" disabled={ecritureFavoris}
                  className="text-sm font-semibold underline"
                  data-testid="cal-biblio-favoris-enregistrer"
                  onClick={enregistrerFavoris}>
                  Enregistrer les favoris
                </button>
              </div>
              {refusFavoris && refusFavoris.rang === null && (
                <p className="text-xs text-destructive" role="alert"
                  data-testid="cal-biblio-favoris-erreur">
                  {refusFavoris.message}
                </p>
              )}
            </div>
          ) : (
            <p className="mt-2 text-xs text-muted-foreground">
              Sans le droit « gérer le calepinage », la création/édition des
              favoris n’est pas proposée ici.
            </p>
          )}
        </Section>
      </div>

      {/* CALX30 — LES PROFILS TYPES, la section éditable. Elle est SOUS la
          grille parce qu'une courbe de 24 poids ne tient pas dans une demi-
          colonne. */}
      <div className="mt-4">
        <Section titre="Profils types"
          sousTitre="Courbes de consommation de la société (CAL149) — la saisie de la société l’emporte toujours sur un repli">
          {lignesProfils.length === 0
            ? <ListeVide enfant="Aucun profil type servi pour votre société." />
            : (
              <ul className="space-y-3" data-testid="cal-biblio-profils-liste">
                {lignesProfils.map((profil, rang) => (
                  <li key={profil.id ?? `rang-${rang}`}
                    className="border border-border p-3"
                    data-testid={`cal-biblio-profil-${rang}`}>
                    {estRepli(profil) ? (
                      <>
                        {/* UN REPLI RESTE UN REPLI : étiqueté, non éditable,
                            jamais renvoyé comme une saisie de la société. */}
                        <p className="text-sm font-medium text-foreground">
                          {profil.libelle || profil.cle}
                          {' '}
                          <Badge variant="outline"
                            data-testid={`cal-biblio-profil-repli-${rang}`}>
                            Hypothèse interne
                          </Badge>
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground"
                          data-testid={`cal-biblio-profil-provenance-${rang}`}>
                          {profil.provenance}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          Ce profil n’est PAS une mesure : il n’est pas
                          modifiable ici et n’est jamais enregistré comme un
                          profil de votre société. Ajoutez le vôtre pour qu’il
                          prenne sa place.
                        </p>
                      </>
                    ) : (
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <label className="text-xs text-muted-foreground">
                          Clé
                          <input type="text" value={profil.cle ?? ''}
                            disabled={!peutGerer || enregistrementProfils}
                            data-testid={`cal-biblio-profil-cle-${rang}`}
                            onChange={(e) => majProfil(rang, 'cle', e.target.value)}
                            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                        </label>
                        <label className="text-xs text-muted-foreground">
                          Libellé
                          <input type="text" value={profil.libelle ?? ''}
                            disabled={!peutGerer || enregistrementProfils}
                            data-testid={`cal-biblio-profil-libelle-${rang}`}
                            onChange={(e) => majProfil(rang, 'libelle', e.target.value)}
                            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                        </label>
                        <label className="text-xs text-muted-foreground">
                          Famille
                          <select value={profil.famille ?? ''}
                            disabled={!peutGerer || enregistrementProfils}
                            data-testid={`cal-biblio-profil-famille-${rang}`}
                            onChange={(e) => majProfil(rang, 'famille', e.target.value)}
                            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground">
                            <option value="">Choisir une famille</option>
                            {FAMILLES.map(([code, libelle]) => (
                              <option key={code} value={code}>{libelle}</option>
                            ))}
                          </select>
                        </label>
                        <label className="text-xs text-muted-foreground">
                          Provenance (obligatoire)
                          <input type="text" value={profil.provenance ?? ''}
                            disabled={!peutGerer || enregistrementProfils}
                            data-testid={`cal-biblio-profil-provenance-${rang}`}
                            onChange={(e) => majProfil(rang, 'provenance', e.target.value)}
                            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                        </label>
                        <label className="text-xs text-muted-foreground sm:col-span-2">
                          Courbe annuelle — 24 poids séparés par des virgules
                          <input type="text" value={profil.courbeTexte ?? ''}
                            disabled={!peutGerer || enregistrementProfils}
                            data-testid={`cal-biblio-profil-courbe-${rang}`}
                            onChange={(e) => majProfil(rang, 'courbeTexte', e.target.value)}
                            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground" />
                        </label>
                        {peutGerer && (
                          <div className="sm:col-span-2">
                            <button type="button" disabled={enregistrementProfils}
                              className="text-xs text-destructive underline"
                              data-testid={`cal-biblio-profil-retirer-${rang}`}
                              onClick={() => retirerProfil(rang)}>
                              Retirer ce profil
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* L'ERREUR SOUS LE PROFIL FAUTIF, celui que le serveur
                        a NOMMÉ — jamais ailleurs. */}
                    {rangFautif === rang && (
                      <p className="mt-2 text-xs text-destructive" role="alert"
                        data-testid={`cal-biblio-profil-erreur-${rang}`}>
                        {refusProfils.message}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}

          {peutGerer ? (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button type="button" disabled={enregistrementProfils}
                className="text-sm font-semibold underline"
                data-testid="cal-biblio-profil-ajouter"
                onClick={ajouterProfil}>
                Ajouter un profil
              </button>
              <button type="button" disabled={enregistrementProfils}
                className="text-sm font-semibold underline"
                data-testid="cal-biblio-profils-enregistrer"
                onClick={enregistrerProfils}>
                Enregistrer les profils
              </button>
            </div>
          ) : (
            <p className="mt-2 text-xs text-muted-foreground">
              Sans le droit « gérer le calepinage », les profils types se
              consultent mais ne se modifient pas ici.
            </p>
          )}

          {/* Un refus qui ne vise AUCUN profil (la liste entière) : il est
              dit ici, avec le motif du serveur, jamais réécrit. */}
          {refusProfils && rangFautif === null && (
            <p className="mt-2 text-xs text-destructive" role="alert"
              data-testid="cal-biblio-profils-erreur">
              {refusProfils.message}
            </p>
          )}
        </Section>
      </div>
    </div>
  )
}
