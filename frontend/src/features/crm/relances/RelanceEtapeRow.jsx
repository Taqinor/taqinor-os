import { useEffect, useRef, useState } from 'react'
import {
  Check, SkipForward, Phone, MessageCircle, Clock3, ChevronDown, ChevronRight,
  Copy, Mail, Paperclip,
} from 'lucide-react'
import {
  Badge, Button, Textarea, Input, Label,
} from '../../../ui'
import ScoreBadge from '../ScoreBadge'
import { PRIORITE_LABELS } from '../stages'
import { toastInfo } from '../../../lib/toast'
import { formatDate } from '../../../lib/format'
import crmApi from '../../../api/crmApi'
import PanneauProposerVisite from './PanneauProposerVisite'
import PanneauScriptAppel from './PanneauScriptAppel'
import PlanifierVisiteModal from './PlanifierVisiteModal'
import { suiteAnnoncee, suiteDuSaut } from './suite'
import {
  typeEtape, reponsesDeLEtape, estTache, estTacheSansAppel as estTacheSansAppel_,
} from './parcours'

/* ============================================================================
   MRY31 — `RelanceEtapeRow` EXTRAIT de `pages/crm/RelancesDuJourWidget.jsx`
   (MRY14), à l'IDENTIQUE (comportement/markup préservés — les tests existants
   du widget restent verts), pour être PARTAGÉ par trois écrans qui en ont
   chacun besoin dans un contexte différent :
     - le widget Cockpit « Relances du jour » (liste multi-leads, format
       complet) ;
     - l'écran « Suivi des relances » (MRY31, `RelancesSuiviPage.jsx` — liste
       multi-leads + statut, tous jours/tous statuts) ;
     - la frise de la fiche lead (MRY32, `CadenceFrise.jsx` — un seul lead
       déjà visible à l'écran, format compact).

   Props ajoutées par cette extraction (au-delà de celles du widget d'origine) :
     - `compact`    : masque l'en-tête (nom du lead, sous-titre libellé,
                      ScoreBadge, badge de priorité) — la fiche lead sait déjà
                      de qui/quoi il s'agit, et la frise affiche déjà juste
                      au-dessus sa propre ligne cadence/canal/libellé/date ;
                      RÉAFFICHER le libellé ici dupliquerait ce texte (deux
                      correspondances pour `getByText`) — le mode compact
                      va donc directement aux badges + boutons d'action ;
     - `readOnly`   : aucun bouton d'action — une ligne qui se LIT seulement
                      (historique de l'écran de suivi). CAD44 : les jours
                      FUTURS du widget ne sont plus en lecture seule, ils
                      passent `enAvance` (Appeler/WhatsApp/Reporter ouverts,
                      Fait/Sauter verrouillés) ;
     - `showStatut` : ajoute un badge de statut (Fait à HH:MM + auteur /
                      Sautée / À faire / En retard) — l'écran de suivi (MRY31)
                      affiche TOUS les statuts, pas seulement les étapes à
                      faire du widget/de la frise — et la note serveur le cas
                      échéant.
   ========================================================================== */

// Libellés FR des canaux SUGGÉRÉS de la cadence — jamais un envoi, juste
// l'indication du prochain geste attendu (appel/WhatsApp/e-mail/visite).
// Non exportés — react-refresh/only-export-components interdit de mélanger
// composant et constantes dans un fichier de composant (fast-refresh Vite) ;
// aucun autre fichier n'en a besoin (`CadenceFrise.jsx` garde sa PROPRE copie
// locale, motif déjà en place avant cette extraction : page → section, sens
// d'import inverse).
const CANAL_LABELS = {
  appel: 'Appel',
  whatsapp: 'WhatsApp',
  email: 'E-mail',
  visite: 'Visite',
}

// CAD81 — libellés COURTS de la langue du client (valeurs de
// `Lead.langue_preferee`, servies en `lead_langue`).
const LANGUE_LABELS = {
  fr: 'FR',
  darija: 'Darija',
}

const CADENCE_LABELS = {
  contact: 'Contact',
  apres_devis: 'Après devis',
  reveil: 'Réveil',
  generique: 'Générique',
  // CAD128 — la cadence courte d'un client acquis qui revient : son badge
  // affichait la clé brute.
  deuxieme_affaire: 'Deuxième affaire',
}

const CADENCE_TONE = {
  contact: 'info',
  apres_devis: 'primary',
  reveil: 'neutral',
  generique: 'outline',
}

// SUIVI-PARCOURS (30/09/2026) — les questions et les réponses de CHAQUE
// étape viennent de la table `parcours_suivi.json`, lue par `./parcours.js`
// (`typeEtape`, `reponsesDeLEtape`). Plus aucune liste écrite ici par
// cadence : la même table est rejouée par la garde de parcours du serveur et
// génère le guide de la GED. CAD17 reste vrai : la phrase affichée sous une
// réponse choisie vient du SERVEUR (`etape.suites`, dérivée du moteur) et se
// traduit dans `./suite.js` ; `precision` (table) ne porte qu'un geste
// d'ÉCRAN, jamais un effet moteur.
//
// Ce que chaque réponse de la table peut porter :
//   · `outcome` (issue serveur) OU `reponse` (clé de réponse du client) ;
//   · `note` : précision typée envoyée avec l'issue (Répondeur, Occupé…) ;
//   · `date` : la date « Rappeler le » est OBLIGATOIRE ;
//   · `junk` : propose « perdu, motif junk » en un clic (CAD11) ;
//   · `motif_perte` : le motif de perte est OBLIGATOIRE (« Perdu ») ;
//   · `motif_refus` : le motif de refus est PROPOSÉ (CAD10) ;
//   · `geste` : `planification` (visite acceptée — la modale s'ouvre AVANT
//     tout enregistrement), `planification_seule` (« la date est calée » sur
//     l'étape planifier), `replanification` (déplacer la visite existante) ;
//   · `message` : l'accusé PROPOSÉ juste après (aperçu + clic humain, D5).

// Les deux types d'étape de la table qui portent un bouton de plus à côté de
// « Fait » : « Créer le devis » + « Planifier la visite » (devis), et
// « Planifier la visite » (planifier). Identifiants de `parcours_suivi.json`.
const CLE_ETAPE_DEVIS = 'devis'
const CLE_ETAPE_PLANIFIER = 'planifier'

/** SUIVI-BLOCAGE — le message d'un refus qui n'est PAS une erreur de champ :
 *  le rôle (403), une touche déjà traitée, un serveur ou un réseau en panne.
 *  Toujours en clair, sous les réponses — jamais un toast générique. */
function messageRefus(err) {
  const statut = err?.response?.status
  if (statut === 403) {
    return 'Votre rôle ne permet pas de traiter les relances (responsable ou administrateur requis).'
  }
  const detail = err?.response?.data?.detail
  if (statut === 400 && typeof detail === 'string' && detail) return detail
  if (statut >= 500) return 'Le serveur n’a pas pu enregistrer la réponse — réessayez dans un instant.'
  if (!statut) return 'Pas de connexion au serveur — vérifiez le réseau et réessayez.'
  return 'La réponse n’a pas pu être enregistrée — réessayez.'
}

/** Lit la PROCHAINE touche depuis la RÉPONSE serveur du « Fait » (jamais
 *  calculée côté écran — un appel programmé à tort aurait pu fausser
 *  l'agenda). `prochaine_touche` (contrat CKP2, à venir) : `{due_at, canal}`
 *  ou absent tant que la matérialisation réactive n'a rien programmé
 *  (dernière touche, cadence arrêtée…) — silence, jamais un message inventé. */
function messageProchaineTouche(prochaine) {
  if (!prochaine?.due_at) return null
  const t = new Date(prochaine.due_at).getTime()
  if (Number.isNaN(t)) return null
  const quand = new Intl.DateTimeFormat('fr-FR', {
    day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit',
    timeZone: 'Africa/Casablanca',
  }).format(t)
  // SUIVI-BLOCAGE (30/09/2026) — une ÉTAPE posée par le moteur (« Préparer et
  // envoyer le devis », « Planifier la visite »…) porte le canal « appel »
  // par défaut sans être un appel : annoncer « Prochain appel programmé »
  // après un « Client joint » envoyait la commerciale attendre un appel alors
  // que la suite est de préparer le devis. Le serveur sert le LIBELLÉ de
  // l'étape (`prochaine_touche.libelle`, additif) : c'est lui qui est dit.
  if (prochaine.libelle && prochaine.cle) {
    return `Étape suivante : « ${prochaine.libelle} » — pour le ${quand}.`
      + (estTache(typeEtape({ cle: prochaine.cle, libelle: prochaine.libelle }))
        ? ' Vous pouvez la traiter dès maintenant.' : '')
  }
  const canal = CANAL_LABELS[prochaine.canal] ?? prochaine.canal
  return canal
    ? `Prochain${canal === 'Appel' ? ' appel' : ` ${canal.toLowerCase()}`} programmé le ${quand}.`
    : `Prochaine touche programmée le ${quand}.`
}

/** `due_at` (ISO) → « HH:MM » heure Casablanca, ou « maintenant » si déjà
    passé. Repli sur `null` (pas d'heure connue) pour laisser l'appelant
    afficher la date seule. Fuseau EXPLICITE (comme `crm.horaires`, jamais
    l'heure locale du navigateur — un commercial en déplacement verrait sinon
    une heure fausse). */
function heureDue(etape) {
  if (!etape.due_at) return null
  const t = new Date(etape.due_at).getTime()
  if (Number.isNaN(t)) return null
  if (t <= Date.now()) return 'maintenant'
  return new Intl.DateTimeFormat('fr-FR', {
    hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Casablanca',
  }).format(t)
}

/** « AAAA-MM-JJ » d'aujourd'hui À CASABLANCA (jamais le fuseau du
    navigateur : un commercial en déplacement comparerait sinon ses dates à
    une autre journée que celle du serveur). */
function aujourdhuiCasablanca() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date())
}

/** Jours calendaires entre deux dates « AAAA-MM-JJ » (arithmétique pure sur
    les dates, aucun fuseau en jeu). */
function joursEntre(debut, fin) {
  return Math.round((Date.parse(`${fin}T00:00:00Z`) - Date.parse(`${debut}T00:00:00Z`)) / 86400000)
}

// CAD26 — au-delà de ce report (7 à 10 jours dans l'audit : on retient le bas
// de la fourchette), « Mettre en veille jusqu'au… » est PROPOSÉ de lui-même :
// un client qui fixe une date lointaine demande du temps, pas que tout le plan
// glisse. Le serveur, lui, bascule la veille en réveil daté au-delà d'un mois.
const VEILLE_PROPOSEE_APRES_JOURS = 7

// SUIVI-BLOCAGE — dite dans le panneau « Fait » d'une touche À VENIR : c'est
// ce que fait le serveur (`services.touche_traitee_en_avance`, CAD44).
const REPONSE_EN_AVANCE = 'Touche à venir : la réponse est enregistrée à la '
  + 'date d’aujourd’hui (« traitée en avance ») — le reste du suivi garde ses dates.'

// CAD46 — la conséquence COMMUNE de « Reporter au » (décaler) et de
// « À rappeler le… » : `reporter_prochaine_touche` décale la touche, TOUTES
// les suivantes et l'ancre `cadence_depart` du même écart (vérifié par la
// garde CAD17 `GlissementDuPlanTests`). Une seule constante, deux champs.
const GLISSEMENT_DU_PLAN = 'Le reste du suivi glisse du même nombre de jours.'

// RLC3 (relevé fondateur du 08/09/2026) — les canaux dont la touche consiste à
// ÉCRIRE : c'est là, et seulement là, que la question « le message a-t-il été
// ouvert ? » a un sens. Un appel a déjà son issue obligatoire (CKP2/CKP4).
const CANAUX_MESSAGE = ['whatsapp', 'email']

// CAD101 — les pièces qu'un client envoie spontanément (clés servies par le
// serveur, `services.TYPES_PIECE_RECUE`).
const PIECES_RECUES = [
  { cle: 'facture', label: 'Facture' },
  { cle: 'adresse', label: 'Adresse' },
  { cle: 'localisation', label: 'Localisation' },
]

// CAD80 — « Appeler » cède la main au téléphone (`tel:`) : sur mobile la page
// se décharge et se recharge au retour d'appel, et la note déjà tapée dans le
// panneau « Fait » disparaissait. Le BROUILLON (note du panneau « Fait ») est
// donc gardé dans le stockage de SESSION de l'onglet — il survit au
// rechargement, meurt avec l'onglet — et restauré au remontage. Effacé dès
// que la touche est enregistrée ou que le panneau est annulé. Lecture et
// écriture best-effort : un stockage indisponible ne bloque jamais le geste.
const CLE_BROUILLON = (id) => `taqinor.relance.brouillon.${id}`

function lireBrouillon(id) {
  try {
    const brut = window.sessionStorage.getItem(CLE_BROUILLON(id))
    const brouillon = brut ? JSON.parse(brut) : null
    return typeof brouillon?.note === 'string' && brouillon.note ? brouillon : null
  } catch {
    return null
  }
}

function ecrireBrouillon(id, brouillon) {
  try {
    window.sessionStorage.setItem(CLE_BROUILLON(id), JSON.stringify(brouillon))
  } catch {
    // stockage plein ou interdit : la note reste à l'écran, simplement non gardée.
  }
}

function effacerBrouillon(id) {
  try {
    window.sessionStorage.removeItem(CLE_BROUILLON(id))
  } catch {
    // idem — rien à faire.
  }
}

/** `traite_le` (ISO, MRY30/MRY31) → « HH:MM » heure Casablanca — JAMAIS le
    repli « maintenant » de `heureDue` ci-dessus (c'est un horodatage PASSÉ,
    pas une échéance à venir). `null` si absent/invalide. */
function heureTraite(iso) {
  if (!iso) return null
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return null
  return new Intl.DateTimeFormat('fr-FR', {
    hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Casablanca',
  }).format(t)
}

// MRY31 — badge de statut de l'écran de suivi (tous statuts confondus,
// jamais juste les étapes à faire du widget/de la frise).
// CKP1/CKP4 (fondateur 2026-09-10, « vérité des sautées ») — SAUTEE reste
// EXCLUSIVEMENT l'action humaine `sauter` (qui/quand affichés en clair) ;
// ANNULEE est un arrêt du MOTEUR (`arreter_cadence`, reprises…) — jamais
// confondue avec un saut humain, jamais d'auteur (traite_par = null côté
// serveur), seulement le motif conservé en note.
function StatutBadge({ etape }) {
  if (etape.statut === 'fait') {
    const heure = heureTraite(etape.traite_le)
    const qui = etape.traite_par_nom
    return (
      <Badge tone="success">
        Fait{heure ? ` · ${heure}` : ''}{qui ? ` · ${qui}` : ''}
      </Badge>
    )
  }
  if (etape.statut === 'sautee') {
    const heure = heureTraite(etape.traite_le)
    const qui = etape.traite_par_nom
    return (
      <Badge tone="neutral">
        Sautée{qui ? ` · ${qui}` : ''}{heure ? ` · ${heure}` : ''}
      </Badge>
    )
  }
  if (etape.statut === 'annulee') {
    return (
      <Badge tone="outline">
        Annulée (moteur){etape.note ? ` · ${etape.note}` : ''}
      </Badge>
    )
  }
  if (etape.overdue) return <Badge tone="danger">En retard</Badge>
  return <Badge tone="outline">À faire</Badge>
}

// CAD78 — le TEXTE d'une touche lu SANS ouvrir WhatsApp : le texte d'une
// touche e-mail (CAD152 : le script d'une touche d'APPEL vit désormais dans
// `PanneauScriptAppel`, qui le lit par le même GET et y ajoute les questions).
// Bulle DÉPLIABLE au-dessus des boutons (patron « Proposer la visite »
// qui montre déjà son propre script) : le rendu est le MÊME que celui du
// message (`getRelanceEtapeMessage`, forme `relance_etape_message` — le
// serveur ne filtre pas par canal), lu à la demande, par une LECTURE pure :
// aucun POST `/whatsapp/`, donc aucun faux « WhatsApp ouvert » qui horodaterait
// un premier contact (MRY19). « Copier » pour le coller où il faut.
// CAD176 — `destinataire` (contrat `relance_etape_v2`, `lead_email`) : avant,
// le panneau rendait un texte SANS dire à quelle adresse il s'adresse — le
// bouton « E-mail » ouvrait le texte sans destinataire ni lien `mailto:`.
// Chaîne vide masquée (`client_pii_voir`) ou fiche sans adresse : même
// distinction que le téléphone (CAD82), affichée en clair plutôt qu'omise.
function TexteDeTouche({ etape, titre, ouvert, onBasculer, destinataire }) {
  const [etat, setEtat] = useState({ chargement: false, rendu: null, erreur: false })

  // Lu à CHAQUE ouverture (un GET bon marché, toujours le texte du moment) —
  // même patron `queueMicrotask` que `ToucheMessageDialog` (règle react-hooks
  // v7 : aucun setState synchrone dans le corps de l'effet).
  useEffect(() => {
    let active = true
    if (!ouvert) return () => { active = false }
    if (typeof crmApi.getRelanceEtapeMessage !== 'function') {
      queueMicrotask(() => { if (active) setEtat({ chargement: false, rendu: null, erreur: true }) })
      return () => { active = false }
    }
    queueMicrotask(() => { if (active) setEtat((e) => ({ ...e, chargement: true, erreur: false })) })
    crmApi.getRelanceEtapeMessage(etape.id)
      .then((r) => { if (active) setEtat({ chargement: false, rendu: r?.data ?? null, erreur: false }) })
      .catch(() => { if (active) setEtat({ chargement: false, rendu: null, erreur: true }) })
    return () => { active = false }
  }, [ouvert, etape.id])

  const copier = async () => {
    const texte = etat.rendu?.message
    if (!texte) return
    try {
      await navigator.clipboard.writeText(texte)
      toastInfo('Texte copié.')
    } catch {
      // best-effort — presse-papier indisponible : le texte reste lisible.
    }
  }

  const rendu = etat.rendu
  // Écriture de droite à gauche seulement quand le texte EST en darija/arabe
  // (jamais pour une version française partie en repli — CAD64).
  const rtl = Boolean(rendu) && !rendu.repli_langue && ['darija', 'ar'].includes(rendu.langue)

  return (
    <div className="mt-1.5 rounded-md border border-dashed border-border p-2" data-testid="texte-touche">
      <button
        type="button"
        className="flex w-full items-center gap-1.5 text-left text-xs font-medium text-foreground"
        aria-expanded={ouvert}
        onClick={onBasculer}
      >
        {ouvert ? <ChevronDown className="size-3.5 shrink-0" aria-hidden="true" />
          : <ChevronRight className="size-3.5 shrink-0" aria-hidden="true" />}
        <span>{titre}</span>
      </button>
      {ouvert && (
        <div className="mt-1.5 flex flex-col gap-1.5">
          {destinataire !== undefined && (
            <p className="text-xs text-muted-foreground" data-testid="texte-touche-destinataire">
              Destinataire : {destinataire || 'aucune adresse e-mail sur la fiche'}
            </p>
          )}
          {etat.chargement && <p className="text-xs text-muted-foreground">Chargement du texte…</p>}
          {etat.erreur && (
            <p className="text-xs text-muted-foreground">Texte indisponible pour le moment.</p>
          )}
          {rendu && (
            <>
              <p
                className={`whitespace-pre-wrap rounded-md bg-muted/40 p-2 text-sm${rtl ? ' text-right' : ''}`}
                dir={rtl ? 'rtl' : 'auto'} lang={rtl ? 'ar' : 'fr'}
                data-testid="texte-touche-contenu"
              >
                {rendu.message || '—'}
              </p>
              <div className="flex justify-end">
                <Button type="button" size="sm" variant="outline" onClick={copier} disabled={!rendu.message}>
                  <Copy className="size-3.5" /> Copier
                </Button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default function RelanceEtapeRow({
  etape, onFait, onSauter, onReporter, onOuvrirMessage, busyId, navigate,
  compact = false, readOnly = false, showStatut = false,
  // CAD44 (TRANCHÉ 21/09/2026, MRY32 rouverte) — une touche À VENIR n'est
  // plus en lecture seule : Appeler, WhatsApp et Reporter (et le panneau de
  // coaching qui accompagne l'appel) sont actionnables dès maintenant ;
  // « Fait » (et « Sauter ») restent verrouillés jusqu'à l'échéance. Le
  // cockpit ET la frise passent ce même drapeau : les deux écrans ne
  // désignent jamais deux gestes différents (règle CADX).
  enAvance = false,
  // VISCAD6 — appelé après qu'une visite a été planifiée depuis CETTE ligne
  // (panneau de coaching OU issue « Visite acceptée ») pour laisser le
  // parent rafraîchir (même callback que Fait/Sauter/Reporter, ex.
  // `CadenceFrise.onChanged`) — optionnel, une ligne readOnly n'en a pas besoin.
  onVisiteChanged,
  // CAD101 — appelé après une « pièce reçue » enregistrée (la touche est
  // close, une étape « préparer le devis » est née) pour que le parent relise
  // sa file ; à défaut, `onVisiteChanged` (même rôle : « rafraîchis-toi »).
  onPieceRecue,
  // CAD152 — appelé après une réponse enregistrée sur la FICHE depuis le
  // panneau d'appel (le score du lead a été recalculé par le serveur) ; à
  // défaut, `onVisiteChanged` (même rôle : « rafraîchis-toi »).
  onLeadEcrit,
  // SUIVI-BLOCAGE — la ligne se monte avec son panneau d'appel DÉJÀ ouvert
  // (la fenêtre « Appeler » de la fiche lead : script, questions, puis
  // l'issue, sans quitter la fenêtre).
  panneauAppelInitial = false,
}) {
  // CAD80 — un brouillon de note laissé par un appel (page rechargée au
  // retour) rouvre le panneau « Fait » avec SA note, jamais une page vide.
  // Lu UNE fois, au montage (initialiseur paresseux).
  const [brouillon] = useState(() => (readOnly ? null : lireBrouillon(etape.id)))
  // '' | 'sauter' | 'fait' | 'reporter' — un seul panneau ouvert à la fois.
  const [panel, setPanel] = useState(brouillon ? 'fait' : '')
  const [note, setNote] = useState(brouillon?.note ?? '')
  const [reponseIdx, setReponseIdx] = useState(null)
  const [rappelLe, setRappelLe] = useState('')
  const [rappelHeure, setRappelHeure] = useState('')
  const [reportDate, setReportDate] = useState('')
  const [reportHeure, setReportHeure] = useState('')
  // CAD26 — '' = le geste PROPOSÉ selon la date ; 'decaler' | 'veille' = le
  // choix explicite de la commerciale, qui prime toujours.
  const [reportMode, setReportMode] = useState('')
  // CKP4 — erreur DE CHAMP renvoyée par le serveur (400
  // `{erreurs: {outcome: "…"}}` pour un canal APPEL clôturé sans issue) :
  // s'affiche SOUS le contrôle concerné, jamais un toast générique qui
  // masquerait le champ fautif (règle « le champ fautif, message exact »).
  const [erreurOutcome, setErreurOutcome] = useState('')
  // CAD27 — erreur SERVEUR sur la date de rappel (`{erreurs: {rappel_le}}`).
  const [erreurRappel, setErreurRappel] = useState('')
  // CAD10 — le motif de refus FACULTATIF : la liste paramétrée (Paramètres →
  // CRM) n'est chargée qu'au premier refus choisi (`null` = pas encore lue),
  // jamais pour chaque ligne de la file.
  const [motifs, setMotifs] = useState(null)
  const [motifRefus, setMotifRefus] = useState('')
  const [erreurMotif, setErreurMotif] = useState('')
  // CAD11 — la proposition « perdu, motif junk » (case à cocher : le clic
  // humain décide) et le motif junk choisi ('' = celui proposé par défaut).
  const [perduJunk, setPerduJunk] = useState(false)
  const [motifJunk, setMotifJunk] = useState('')
  // VISCAD6 — modale de planification de la visite, PARTAGÉE par le panneau
  // de coaching (ci-dessous) et l'issue « Visite acceptée » du Fait.
  const [planifierOuvert, setPlanifierOuvert] = useState(false)
  // SUIVI-BLOCAGE (30/09/2026) — le GESTE de planification en cours
  // (`planification` : « Visite acceptée » ; `planification_seule` : « la date
  // est calée » ; `replanification` : « reportée ») tant que la modale est
  // ouverte, '' sinon. Avant, la réponse partait D'ABORD et la modale s'ouvrait
  // ensuite — or le succès fait retirer (cockpit) ou recharger (fiche, suivi)
  // la ligne, qui emportait sa modale avec elle : la planification ne
  // s'affichait jamais, et l'étape « Planifier la visite » se re-posait.
  const [gestePlanification, setGestePlanification] = useState('')
  // « Perdu — clore le dossier » : le motif de perte choisi (obligatoire).
  const [motifPerte, setMotifPerte] = useState('')
  // RLC3 — la confirmation explicite « marquer faite sans avoir ouvert le
  // message ? ». Jamais un blocage : la case est TOUJOURS disponible (Meryem
  // peut avoir écrit depuis son téléphone) — elle rend seulement le geste
  // conscient, et le dit dans le chatter.
  const [sansOuverture, setSansOuverture] = useState(false)
  // CAD63 — la réponse « ne parle que darija », saisie AU MOMENT où le client
  // le dit : elle pose la langue sur la fiche une fois pour toutes (champ
  // `langue` du « Fait », seulement si la touche est bien enregistrée).
  const [queDarija, setQueDarija] = useState(false)
  const [erreurLangue, setErreurLangue] = useState('')
  // CAD78 — la bulle du TEXTE de la touche (texte e-mail).
  const [texteOuvert, setTexteOuvert] = useState(false)
  // CAD152 — le panneau d'appel guidé (script + questions + issue) : déplié
  // par sa bascule ou par « Appeler », qui l'ouvre AVANT de composer.
  const [panneauAppelOuvert, setPanneauAppelOuvert] = useState(panneauAppelInitial)
  // CAD101 — le geste « pièce reçue » : quelle pièce, le fichier éventuel,
  // l'envoi en cours et l'erreur de CHAMP renvoyée par le serveur.
  const [typePiece, setTypePiece] = useState('')
  const [fichierPiece, setFichierPiece] = useState(null)
  const [envoiPiece, setEnvoiPiece] = useState(false)
  const [erreurPiece, setErreurPiece] = useState('')
  const busy = busyId === etape.id
  // CAD78/CAD152 — une touche d'APPEL a son panneau d'appel guidé (le script
  // du fondateur quand elle porte un gabarit, et les questions encore à
  // poser) ; une touche E-MAIL a son texte. Ni l'une ni l'autre ne passe par
  // la modale WhatsApp.
  const toucheAppel = etape.canal === 'appel'
  const toucheEmail = etape.canal === 'email'

  // CAD80 — la note du panneau « Fait » est gardée à chaque frappe (elle
  // survit à un rechargement), effacée quand le panneau se ferme ou que la
  // note est vidée. Aucun setState ici : l'effet n'écrit que le stockage.
  useEffect(() => {
    if (readOnly) return
    if (panel === 'fait' && note.trim()) ecrireBrouillon(etape.id, { note })
    else if (panel === '' || panel === 'fait') effacerBrouillon(etape.id)
  }, [panel, note, etape.id, readOnly])

  // CAD82 — un bouton désactivé DIT pourquoi (règle fondateur du 08/09 : le
  // champ fautif, le message exact). Deux causes, jamais confondues : le
  // numéro est MASQUÉ par les droits du rôle (`lead_pii_masquee`, servi par le
  // serveur) ou il n'y a AUCUN numéro sur la fiche.
  const raisonSansNumero = (geste) => (etape.lead_pii_masquee
    ? `« ${geste} » : numéro masqué — votre rôle n’a pas le droit de voir les coordonnées client (client_pii_voir).`
    : `« ${geste} » : aucun numéro de téléphone sur la fiche du lead.`)
  const sansTelephone = !etape.lead_telephone
  // Garde SYMÉTRIQUE : WhatsApp n'est plus un aller-retour réseau vers une
  // impasse que la ligne connaissait déjà (sauf touche e-mail, dont le bouton
  // ouvre le texte en place — aucun numéro requis).
  const sansNumeroWhatsApp = !toucheEmail && !(etape.lead_whatsapp || etape.lead_telephone)
  const whatsappSeulement = etape.lead_contact_preference === 'whatsapp_only'

  // CAD80 — « Appeler » : le brouillon est écrit AVANT de céder la main au
  // téléphone (la page peut être déchargée dans la foulée).
  // CAD178 — compteur BEST-EFFORT du geste, par famille d'appareil : lancé
  // AVANT `tel:` (best-effort — la page peut se décharger dans la foulée),
  // jamais attendu, jamais bloquant pour l'appel lui-même.
  const appeler = () => {
    if (!etape.lead_telephone) return
    if (panel === 'fait' && note.trim()) ecrireBrouillon(etape.id, { note })
    if (typeof crmApi.appelerRelanceEtape === 'function') {
      crmApi.appelerRelanceEtape(etape.id).catch(() => {})
    }
    window.location.href = `tel:${etape.lead_telephone}`
  }

  // CAD152 — « Appeler » ouvre le panneau d'appel AVANT de composer : le
  // script et les questions sont sous les yeux quand le client décroche ;
  // « Composer le numéro » (dans le panneau) passe par `appeler` ci-dessus.
  const ouvrirPanneauAppel = () => {
    if (!etape.lead_telephone) return
    setPanneauAppelOuvert(true)
  }

  const fermer = () => {
    setPanel('')
    setNote(''); setReponseIdx(null); setRappelLe(''); setRappelHeure('')
    setReportDate(''); setReportHeure(''); setErreurOutcome('')
    setSansOuverture(false); setReportMode(''); setErreurRappel('')
    setMotifRefus(''); setErreurMotif(''); setMotifPerte('')
    setPerduJunk(false); setMotifJunk('')
    setQueDarija(false); setErreurLangue('')
    setTypePiece(''); setFichierPiece(null); setErreurPiece('')
  }

  // CAD10 — lecture paresseuse des motifs, au geste (jamais dans un effet) :
  // un échec laisse simplement la liste vide — le motif est FACULTATIF.
  // Vérification réelle du 30/09/2026 (fenêtre « Appeler », mobile) : la liste
  // restait `[]` pendant la lecture et l'écran affichait « Aucun motif de perte
  // n'est paramétré » avant même la réponse du serveur. `motifs` reste `null`
  // tant que rien n'est lu ; la garde anti-double-lecture est une ref.
  const motifsDemandes = useRef(false)
  const chargerMotifs = () => {
    if (motifsDemandes.current) return
    motifsDemandes.current = true
    Promise.resolve()
      .then(() => crmApi.getMotifsPerte())
      .then((r) => setMotifs(
        (r?.data?.results ?? r?.data ?? []).filter((m) => !m.archived)))
      .catch(() => setMotifs([]))
  }

  // SUIVI-PARCOURS — le TYPE d'étape et ses réponses viennent de la table
  // (`./parcours.js`) : par clé d'abord (une société renomme ses barreaux,
  // PARAM-CADENCE E8), puis libellé par défaut, puis cadence + canal.
  const type = typeEtape(etape)
  const questionsTouche = { question: type.question, aide: type.aide }
  // VISCAD6-B — l'étape de filet « devis parti » porte deux actions de plus
  // (« Créer le devis », « Planifier la visite ») ; et l'étape « Planifier la
  // visite » son bouton de planification.
  const estEtapeDevis = type.id === CLE_ETAPE_DEVIS
  const estEtapePlanifier = type.id === CLE_ETAPE_PLANIFIER
  const estToucheVisite = type.famille === 'Visite technique'
  // SUIVI-BLOCAGE — une TÂCHE (préparer le devis, décider la suite, planifier
  // la visite, devis modifié, question de prix) n'est jamais verrouillée « à
  // venir » et ne se « saute » pas ; celles qui ne sont PAS un appel au client
  // n'affichent ni script d'appel d'office, ni Répondeur / Occupé.
  const estTacheLibre = estTache(type)
  const estTacheSansAppel = estTacheSansAppel_(type)
  const reponsesDisponibles = reponsesDeLEtape(type, etape)
  const reponseChoisie = reponseIdx == null
    ? null : reponsesDisponibles[reponseIdx]
  // RLC3 — cette touche consiste-t-elle à écrire, et le message a-t-il été
  // ouvert ? `message_ouvert_le` vient du SERVEUR (activité « WhatsApp
  // ouvert », contrat `relance_etape_v2`) — jamais une mémoire d'écran, qui
  // aurait tout oublié au rechargement de la page.
  const toucheMessage = CANAUX_MESSAGE.includes(etape.canal)
  const messageOuvertLe = toucheMessage
    ? heureTraite(etape.message_ouvert_le) : null
  // SUIVI-PARCOURS — la question « avez-vous ouvert le message ? » ne vaut
  // que pour une réponse qui parle du MESSAGE : « Client joint au téléphone »
  // dit justement qu'on a appelé à la place.
  const reponseParTelephone = reponseChoisie?.id === 'joint_telephone'
  const confirmationOuvertureRequise = (
    toucheMessage && !messageOuvertLe && !sansOuverture && !reponseParTelephone)
  // SUIVI-BLOCAGE (30/09/2026) — le verrou « à venir » (CAD44 : on ne coche
  // pas un geste qui n'a pas eu lieu) ne doit jamais empêcher de DIRE un geste
  // qui A eu lieu. Trois cas ouvrent donc « Fait » avant l'échéance :
  //   · une TÂCHE — la faire tôt est le but ;
  //   · un MESSAGE déjà ouvert depuis l'ERP (trace serveur RLC3) ;
  //   · un APPEL passé en avance : son issue se saisit depuis le panneau
  //     d'appel (« Saisir l'issue de l'appel »), jamais verrouillé.
  // Le bouton « Fait » nu reste caché sur une touche du protocole à venir.
  const faitVerrouille = enAvance && !estTacheLibre
    && !(toucheMessage && messageOuvertLe)
  const sauterVerrouille = estTacheLibre || (enAvance && !estTacheLibre)

  // CAD27 — une date de rappel/report dans le PASSÉ tirait tout le plan en
  // arrière (plusieurs touches « en retard » d'un coup, pour une faute de
  // frappe sur l'année). L'écran la REFUSE : champ borné à aujourd'hui
  // (Casablanca), message sous le champ qui le NOMME, Confirmer désactivé.
  // Le serveur refuse aussi (400 `{erreurs: {rappel_le}}`) — ceinture.
  const aujourdhui = aujourdhuiCasablanca()
  const rappelPasse = Boolean(rappelLe) && rappelLe < aujourdhui
  const reportPasse = Boolean(reportDate) && reportDate < aujourdhui
  const messageRappel = erreurRappel || (rappelPasse
    ? '« Rappeler le » : cette date est déjà passée — choisissez aujourd’hui ou une date à venir.'
    : '')
  // CAD11 — les motifs JUNK de la société ; celui proposé par défaut est le
  // motif nommé par la réponse s'il existe, sinon le premier de la liste.
  const motifsJunk = (motifs ?? []).filter((m) => m.est_junk)
  const motifJunkEffectif = motifJunk
    || (motifsJunk.find((m) => m.nom === reponseChoisie?.junk) ?? motifsJunk[0])?.nom
    || ''

  // SUIVI-BLOCAGE — ce que le serveur a refusé, SOUS le champ fautif (règle
  // fondateur « le champ fautif, le message exact ») ; un refus qui n'est pas
  // une erreur de champ (403 rôle, 400 « déjà traitée », réseau) s'affiche
  // sous les réponses, en clair — jamais un toast générique.
  const afficherRefus = (err) => {
    const statut = err?.response?.status
    const erreurs = statut === 400 ? err?.response?.data?.erreurs : null
    const champ = erreurs?.outcome || erreurs?.reponse || erreurs?.etape
    if (champ) setErreurOutcome(champ)
    // CAD27 — la date refusée par le serveur s'affiche SOUS son champ.
    if (erreurs?.rappel_le) setErreurRappel(erreurs.rappel_le)
    // CAD10 — de même pour le motif de refus, le motif junk (CAD11) et le
    // motif de perte (« Perdu — clore le dossier »).
    if (erreurs?.motif_refus) setErreurMotif(erreurs.motif_refus)
    if (erreurs?.perdu_junk) setErreurMotif(erreurs.perdu_junk)
    if (erreurs?.motif_perte) setErreurMotif(erreurs.motif_perte)
    // CAD63 — la langue refusée s'affiche SOUS sa case.
    if (erreurs?.langue) setErreurLangue(erreurs.langue)
    // SUIVI-REFUS — Fait, Sauter et Reporter passent ici, et le parent ne
    // double plus un refus NOMMÉ par un toast : ce refus ne doit donc JAMAIS
    // rester muet. Une clé que l'écran ne range sous aucun champ (le `mode`
    // d'un report, une clé future du serveur) montre son premier message sous
    // le geste ; sans message du tout, la phrase claire du statut HTTP.
    const rangee = champ || erreurs?.rappel_le || erreurs?.motif_refus
      || erreurs?.perdu_junk || erreurs?.motif_perte || erreurs?.langue
    if (!rangee) {
      const premier = erreurs
        ? Object.values(erreurs).flat().find((m) => typeof m === 'string' && m) : null
      setErreurOutcome(premier || messageRefus(err))
    }
  }

  // CKP4 — `onFait` renvoie une promesse (widget/frise/suivi) : succès →
  // message de confirmation lu de LA RÉPONSE serveur uniquement (jamais
  // calculé ici), panneau refermé (la ligne peut rester à l'écran : une étape
  // déplacée à une date, une ligne que la fiche garde montée) ; 400 →
  // affiché SOUS le contrôle, la ligne reste ouverte (le parent ne l'a pas
  // retirée sur un échec). `messageAPropose` (CAD-A) : le texte d'accusé à
  // PROPOSER après une réponse du client, lu par l'appelant AVANT l'envoi (le
  // state se réinitialise dès le succès dans les parents qui retirent la
  // ligne).
  const envoyerFait = (payload, messageAPropose) => {
    Promise.resolve(onFait(etape.id, payload)).then((data) => {
      // CAD80 — la touche est enregistrée : le brouillon n'a plus d'objet.
      effacerBrouillon(etape.id)
      fermer()
      const message = messageProchaineTouche(data?.prochaine_touche)
      if (message) toastInfo(message)
      // CAD-A — l'accusé convenu (« je ne vous rappellerai plus »…) est
      // PROPOSÉ dans la modale d'aperçu du parent (elle survit au retrait de
      // cette ligne) : rien ne part sans le clic « Ouvrir WhatsApp ».
      if (messageAPropose) onOuvrirMessage?.({ ...etape, message_cle: messageAPropose })
    }).catch(afficherRefus)
  }

  // SUIVI-BLOCAGE — pourquoi « Confirmer » est grisé, DIT à côté du bouton
  // (avant, un bouton mort sans cause : pas de réponse choisie, date absente,
  // motif absent, case du message non cochée).
  const raisonConfirmerGrise = (() => {
    if (!reponseChoisie) return 'Choisissez une réponse.'
    if (reponseChoisie.date && !rappelLe) return 'Indiquez la date convenue.'
    if (reponseChoisie.date && rappelPasse) return 'La date est déjà passée.'
    if (reponseChoisie.motif_perte && !motifPerte) return 'Choisissez le motif de perte.'
    if (confirmationOuvertureRequise) return 'Cochez la case « message non ouvert » ci-dessus.'
    return ''
  })()

  const confirmerFait = () => {
    if (raisonConfirmerGrise) return
    // SUIVI-PARCOURS — les trois gestes de planification n'envoient rien
    // d'eux-mêmes : la modale s'ouvre, et c'est la planification RÉUSSIE qui
    // enregistre (le serveur clôt la touche qui l'a demandée, `etape`).
    //   · planification (« Visite acceptée ») : date saisie → visite créée
    //     ET réponse enregistrée ; « Date pas encore fixée » → la réponse part
    //     seule et le serveur pose « Planifier la visite » ; Annuler → rien ;
    //   · planification_seule (« la date est calée ») : seule la date clôt
    //     l'étape planifier ;
    //   · replanification : la visite existante est déplacée, la touche reste.
    if (reponseChoisie.geste) {
      setGestePlanification(reponseChoisie.geste)
      setPlanifierOuvert(true)
      return
    }
    envoyerFait(composerPayload(), reponseChoisie.message)
  }

  // Le corps envoyé au serveur pour la réponse choisie — lu dans la table.
  const composerPayload = () => {
    const payload = {}
    // CAD13 — la PRÉCISION de la réponse (« Répondeur », « Occupé »,
    // « Numéro invalide »…) SURVIT à la note tapée : elle ouvre la note, la
    // saisie libre la complète (« Répondeur — sonne dans le vide, à retenter
    // le soir »). L'écraser faisait dire « Pas de réponse » à l'historique
    // sans jamais dire qu'un répondeur avait été atteint — ce qui distingue
    // un numéro qui existe d'un numéro mort. Le serveur ne garde qu'un champ.
    const noteTapee = note.trim()
    if (reponseChoisie.note && noteTapee) payload.note = `${reponseChoisie.note} — ${noteTapee}`
    else if (noteTapee) payload.note = noteTapee
    else if (reponseChoisie.note) payload.note = reponseChoisie.note
    if (reponseChoisie.outcome) payload.outcome = reponseChoisie.outcome
    // CAD-A — une réponse du client part sous sa CLÉ ; l'issue est dérivée
    // côté serveur (jamais envoyée d'ici).
    if (reponseChoisie.reponse) payload.reponse = reponseChoisie.reponse
    if (reponseChoisie.date && rappelLe) {
      payload.rappel_le = rappelLe
      if (rappelHeure) payload.rappel_heure = rappelHeure
    }
    // CAD10 — le motif n'accompagne QUE le refus, et seulement s'il est choisi.
    if (reponseChoisie.outcome === 'refuse' && motifRefus) payload.motif_refus = motifRefus
    // « Perdu — clore le dossier » : le motif de perte est obligatoire.
    if (reponseChoisie.motif_perte && motifPerte) payload.motif_perte = motifPerte
    // CAD11 — « perdu, motif junk » seulement si la case est COCHÉE.
    if (reponseChoisie.junk && perduJunk && motifJunkEffectif) {
      payload.perdu_junk = motifJunkEffectif
    }
    // RLC3 — le geste assumé est TRACÉ : `body` s'ajoute à la ligne de chatter
    // de la touche (`marquer_etape_relance`), sans toucher à la note libre.
    if (toucheMessage && !messageOuvertLe && !reponseParTelephone) {
      payload.body = 'Marquée faite sans ouverture du message depuis l’ERP.'
    }
    // CAD63 — « ne parle que darija » : la langue part AVEC la réponse ; le
    // serveur ne la pose sur la fiche que si la touche est enregistrée.
    if (queDarija) payload.langue = 'darija'
    setErreurOutcome(''); setErreurLangue('')
    return payload
  }

  // SUIVI-BLOCAGE — la visite vient d'être planifiée (ou déplacée) depuis la
  // modale : le serveur a déjà clos la touche qui l'a demandée (`etape` du
  // corps) quand il y avait une réponse en attente. Ici : brouillon effacé,
  // panneau refermé, prochaine étape annoncée, parent prévenu (il relit sa
  // file : la planification a fermé, annulé ou décalé des étapes).
  const visitePlanifiee = (data) => {
    if (gestePlanification) effacerBrouillon(etape.id)
    fermer()
    const message = messageProchaineTouche(data?.prochaine_touche)
    if (message) toastInfo(message)
    onVisiteChanged?.(etape.id, data)
  }

  // SUIVI-BLOCAGE — « Date pas encore fixée » : la réponse « Visite acceptée »
  // part seule, le serveur pose « Planifier la visite technique convenue »
  // (aujourd'hui).
  const enregistrerSansDate = () => {
    envoyerFait(composerPayload())
  }

  // CAD26 — le geste de report : décaler (historique) ou mettre en veille.
  const veilleProposee = Boolean(reportDate)
    && joursEntre(aujourdhuiCasablanca(), reportDate) > VEILLE_PROPOSEE_APRES_JOURS
  const modeReport = reportMode || (veilleProposee ? 'veille' : 'decaler')

  const confirmerReporter = () => {
    if (!reportDate || reportPasse) return
    // F1 — forme SÛRE ancrée Casablanca CÔTÉ SERVEUR (`_parse_rappel`) :
    // jamais un `new Date(...).toISOString()`, qui interprète
    // `${date}T${heure}:00` dans le fuseau du NAVIGATEUR et décale l'heure
    // réellement reportée dès que l'agent n'est pas sur ce fuseau.
    const payload = { rappel_le: reportDate, rappel_heure: reportHeure || '09:00' }
    const enVeille = modeReport === 'veille'
    if (enVeille) payload.mode = 'veille'
    // SUIVI-REFUS (incident du double clic sur « Reporter », SUIVI E8) : le
    // serveur répond 400 `erreurs.etape` (touche déjà traitée) — le parent
    // relance l'erreur, le panneau RESTE ouvert et le message exact s'affiche
    // sous le geste, comme pour « Fait ». Avant, l'erreur était avalée : le
    // panneau se refermait « comme réussi » et un toast générique passait seul.
    // Un nouvel envoi efface d'abord le refus du précédent.
    setErreurOutcome(''); setErreurRappel('')
    Promise.resolve(onReporter(etape.id, payload)).then((data) => {
      // SUIVI-BLOCAGE — le panneau se referme : sur la fiche, la ligne reste
      // montée après un report (la touche est déplacée, pas retirée) et
      // affichait encore « Confirmer » cliquable.
      fermer()
      if (!enVeille || !data) return
      // La réponse serveur dit ce qui s'est réellement passé : la touche
      // déplacée (même barreau) ou la première touche d'un réveil daté.
      toastInfo(data.cadence === 'reveil' && etape.cadence !== 'reveil'
        ? 'Plus d’un mois d’attente : la cadence est arrêtée et un réveil est daté.'
        : 'Dossier en veille : la cadence reprendra à cette même touche.')
    }).catch(afficherRefus)
  }

  // SUIVI-REFUS — « Sauter » suit le même chemin que « Fait » et « Reporter » :
  // succès → panneau refermé (la touche est close, le parent retire ou relit la
  // ligne) ; refus → panneau ouvert, note conservée, message exact du serveur
  // SOUS le geste (`erreur-outcome`), jamais un toast générique seul.
  const confirmerSauter = () => {
    setErreurOutcome('')
    Promise.resolve(onSauter(etape.id, note)).then(() => fermer()).catch(afficherRefus)
  }

  // CAD101 — « pièce reçue » : un geste humain, envoyé tel quel au serveur
  // (qui clôt la touche, attache le document et pose « préparer le devis »).
  // La confirmation affichée vient de LA RÉPONSE (`prochaine_touche`),
  // jamais d'un calcul d'écran ; un refus s'affiche SOUS le panneau.
  const confirmerPiece = () => {
    if (!typePiece || envoiPiece) return
    if (typeof crmApi.enregistrerPieceRecue !== 'function') return
    setEnvoiPiece(true); setErreurPiece('')
    Promise.resolve()
      .then(() => crmApi.enregistrerPieceRecue(etape.id, {
        type_piece: typePiece, note: note.trim() || undefined,
        fichier: fichierPiece || undefined,
      }))
      .then((r) => {
        const data = r?.data
        toastInfo(messageProchaineTouche(data?.prochaine_touche)
          ?? 'Pièce reçue enregistrée.')
        fermer()
        const rafraichir = onPieceRecue ?? onVisiteChanged
        rafraichir?.(etape.id, data)
      })
      .catch((err) => {
        const erreurs = err?.response?.status === 400 ? err?.response?.data?.erreurs : null
        setErreurPiece(
          (erreurs && (erreurs.type_piece || erreurs.fichier || erreurs.etape))
          || 'La pièce n’a pas pu être enregistrée — réessayez.')
      })
      .finally(() => setEnvoiPiece(false))
  }

  const heure = heureDue(etape)

  return (
    <li className="rounded-md border border-border p-2" data-testid="relance-etape-row">
      {!compact && (
        <div className="flex items-start justify-between gap-2">
          <button
            type="button"
            className="flex-1 truncate text-left text-sm font-medium hover:underline"
            onClick={() => navigate(`/crm/leads?lead=${etape.lead}`)}
          >
            {etape.lead_nom || 'Lead'}
            <span className="block text-xs font-normal text-muted-foreground">
              {etape.libelle}
              {etape.lead_owner_nom ? ` · ${etape.lead_owner_nom}` : ''}
            </span>
          </button>
          <ScoreBadge lead={{ score: etape.lead_score }} />
        </div>
      )}
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        <Badge tone={CADENCE_TONE[etape.cadence] ?? 'neutral'}>
          {CADENCE_LABELS[etape.cadence] ?? etape.cadence}
        </Badge>
        {etape.overdue ? (
          <Badge tone="danger">En retard{heure ? ` · ${heure}` : ''}</Badge>
        ) : (
          <Badge tone="neutral">{heure ?? '—'}</Badge>
        )}
        <Badge tone="outline">{CANAL_LABELS[etape.canal] ?? etape.canal}</Badge>
        {!compact && etape.lead_priorite && etape.lead_priorite !== 'normale' && (
          <Badge tone={etape.lead_priorite === 'haute' ? 'warning' : 'neutral'}>
            {PRIORITE_LABELS[etape.lead_priorite] ?? etape.lead_priorite}
          </Badge>
        )}
        {/* CAD81 — la langue du client AVANT de décrocher : sur une touche
            d'appel aucune modale ne s'ouvre, et le script affiché (CAD78) ne
            dit pas dans quelle langue attaquer. `lead_langue` vient du
            serveur (contrat `relance_etape_v2`), rendu sur toutes les lignes
            (cockpit comme frise). */}
        {etape.lead_langue && (
          <Badge
            tone={etape.lead_langue === 'fr' ? 'outline' : 'info'}
            title={`Langue du client : ${LANGUE_LABELS[etape.lead_langue] ?? etape.lead_langue}`}
            data-testid="badge-langue"
          >
            {LANGUE_LABELS[etape.lead_langue] ?? etape.lead_langue}
          </Badge>
        )}
        {showStatut && <StatutBadge etape={etape} />}
        {/* CAD11 — `lead_est_junk` (contrat `relance_etape_v2`) : le lead
            est perdu avec un motif junk — visible SUR la touche, pour que la
            qualité des numéros venus des publicités se lise dans la file. */}
        {etape.lead_est_junk && (
          <Badge tone="danger" title="Lead perdu — motif junk (pas un vrai prospect)">
            Junk
          </Badge>
        )}
      </div>
      {/* PARAM-CADENCE (E7, décision fondateur 25/09/2026) — sous le
          libellé, la date de la visite technique du lead (`visite_prevue_le`,
          contrat `relance_etape_v2`, servie sur TOUTE touche du lead — pas
          seulement les quatre gestes de visite) et, quand le retour terrain
          est saisi, un lien direct dessus (`visite_id`). Même chemin que
          `CadenceFrise.jsx` (ancre + `navigate`, jamais `<Link>` : plusieurs
          tests existants de cette ligne la rendent SANS Router — même repli
          que le bouton « Créer le devis » ci-dessus). */}
      {estToucheVisite && (etape.visite_prevue_le || (etape.visite_retour_disponible && etape.visite_id)) && (
        <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground"
           data-testid="visite-infos">
          {etape.visite_prevue_le && (
            <span>Visite prévue le {formatDate(etape.visite_prevue_le)}</span>
          )}
          {etape.visite_retour_disponible && etape.visite_id && (
            <a
              href={`/visites/${etape.visite_id}`}
              className="font-medium text-primary underline"
              onClick={(e) => {
                if (!navigate) return
                e.preventDefault()
                navigate(`/visites/${etape.visite_id}`)
              }}
            >
              Ouvrir le retour
            </a>
          )}
        </p>
      )}
      {showStatut && etape.note && (
        <p className="mt-1 text-xs text-muted-foreground">{etape.note}</p>
      )}
      {/* CAD82 — la PRÉFÉRENCE du client atteint la ligne : Appeler et
          WhatsApp ne sont plus proposés à égalité sans dire qu'il a demandé
          à n'être joint que par écrit (`lead_contact_preference`). */}
      {whatsappSeulement && (
        <p className="mt-1 text-xs font-medium text-warning" data-testid="preference-contact">
          Le client a demandé à être joint par écrit uniquement (WhatsApp) — évitez d’appeler.
        </p>
      )}
      {/* VISCAD — le panneau de coaching se gate lui-même sur cadence ===
          'apres_devis' ; ici on ne gate que sur `readOnly` (une ligne qui se
          LIT seulement — historique du suivi — n'a pas d'action à proposer).
          CAD44 : une touche À VENIR (`enAvance`) le garde — il accompagne
          l'appel passé en avance. Rendu dans les DEUX modes (compact ET
          cockpit), jamais seulement compact. */}
      {!readOnly && (
        <PanneauProposerVisite etape={etape} onPlanifier={() => setPlanifierOuvert(true)} />
      )}
      {/* CAD152 — le panneau d'appel guidé, FRÈRE du coaching visite : gaté
          sur une touche d'APPEL (ou ouvert par « Appeler » sur une autre
          touche), AU-DESSUS du bouton, sans modale ni POST « WhatsApp
          ouvert ». Il remplace la bulle « Script d'appel » de CAD78 (même
          lecture du script, plus les questions). Une touche À VENIR le garde
          (CAD44) : seule l'issue attend l'échéance. */}
      {/* SUIVI-BLOCAGE (30/09/2026) — deux corrections : (1) une TÂCHE qui
          n'est pas un appel (préparer le devis, décider la suite) n'affiche
          plus le script d'appel d'office — juste après l'appel, la ligne
          suivante rouvrait le même script et laissait croire qu'il fallait
          rappeler ; « Appeler » l'ouvre toujours à la demande ; (2) l'issue
          d'un appel PASSÉ EN AVANCE se saisit : elle n'est plus verrouillée
          jusqu'à l'échéance (`enAvance` ne sert plus qu'à le DIRE). */}
      {!readOnly && ((toucheAppel && !estTacheSansAppel) || panneauAppelOuvert) && (
        <PanneauScriptAppel
          leadId={etape.lead}
          etape={etape}
          ouvert={panneauAppelOuvert}
          onBasculer={() => setPanneauAppelOuvert((v) => !v)}
          telephone={etape.lead_telephone}
          onComposer={appeler}
          // SUIVI-REFUS — ce raccourci ouvre « Fait » SANS passer par `fermer` :
          // le refus d'un « Sauter » / « Reporter » resté à l'écran ne doit pas
          // se retrouver sous une autre question.
          onSaisirIssue={() => { setErreurOutcome(''); setErreurRappel(''); setPanel('fait') }}
          issueEnAvance={enAvance}
          onLeadEcrit={() => (onLeadEcrit ?? onVisiteChanged)?.(etape.id)}
        />
      )}
      {/* CAD78 — une touche e-mail montre son texte au même endroit, sans
          ouvrir de modale ni émettre de POST. */}
      {!readOnly && toucheEmail && (
        <TexteDeTouche
          etape={etape}
          titre="Texte de l’e-mail"
          ouvert={texteOuvert}
          onBasculer={() => setTexteOuvert((v) => !v)}
          destinataire={etape.lead_email}
        />
      )}
      {!readOnly && panel === '' && (
        <div className="mt-2 flex flex-wrap justify-end gap-1.5">
          <Button
            size="sm" variant="outline" disabled={busy || !etape.lead_telephone}
            onClick={ouvrirPanneauAppel}
            title="Ouvre le script et les questions avant de composer le numéro."
          >
            <Phone className="size-3.5" /> Appeler
          </Button>
          {/* CAD78 — une touche e-mail ne dit plus « WhatsApp » et n'ouvre plus
              la modale WhatsApp : son bouton déplie le texte de l'e-mail. */}
          {toucheEmail ? (
            <Button
              size="sm" variant="outline" disabled={busy}
              onClick={() => setTexteOuvert(true)}
            >
              <Mail className="size-3.5" /> E-mail
            </Button>
          ) : (
            <Button
              size="sm" variant="outline" disabled={busy || sansNumeroWhatsApp}
              onClick={() => onOuvrirMessage(etape)}
            >
              <MessageCircle className="size-3.5" /> WhatsApp
            </Button>
          )}
          <Button
            size="sm" variant="outline" disabled={busy}
            onClick={() => setPanel('reporter')}
          >
            <Clock3 className="size-3.5" /> Reporter
          </Button>
          {/* CAD101 — le client a envoyé sa facture / son adresse / sa
              localisation : UN geste, sur toute touche ouverte (même à
              venir — c'est un événement réel, pas une coche anticipée). */}
          <Button
            size="sm" variant="outline" disabled={busy}
            onClick={() => setPanel('piece')}
          >
            <Paperclip className="size-3.5" /> Pièce reçue
          </Button>
          {/* VISCAD6-B (fondateur 24/09/2026) — sur l'étape de filet « devis
              parti » SEULE, deux actions RENDENT la touche actionnable au
              lieu de la laisser en texte inerte : créer le devis tout de
              suite (même chemin que `LeadWorkspace.jsx` — `navigate` peut
              manquer en mode compact/frise, l'ancre `href` reste un repli
              qui navigue vraiment), ou planifier la visite (même modale
              PARTAGÉE que le CTA de coaching et l'issue « Visite acceptée »
              ci-dessous, VISCAD6). */}
          {estEtapeDevis && (
            <Button asChild size="sm" variant="outline">
              <a
                href={`/ventes/devis/nouveau?lead=${encodeURIComponent(etape.lead)}`}
                onClick={(e) => {
                  if (!navigate) return
                  e.preventDefault()
                  navigate(`/ventes/devis/nouveau?lead=${encodeURIComponent(etape.lead)}`)
                }}
              >
                Créer le devis
              </a>
            </Button>
          )}
          {(estEtapeDevis || estEtapePlanifier) && (
            <Button
              size="sm" variant="outline" disabled={busy}
              onClick={() => {
                // Sur l'étape « Planifier la visite », le bouton vaut la
                // réponse « la date est calée » : la planification clôt l'étape.
                if (estEtapePlanifier) setGestePlanification('planification_seule')
                setPlanifierOuvert(true)
              }}
            >
              Planifier la visite
            </Button>
          )}
          {/* CAD44 — sur une touche À VENIR, « Fait » (et « Sauter », qui
              clôt la touche comme lui) restent verrouillés : on ne coche pas
              un geste qui n'a pas eu lieu. SUIVI-BLOCAGE — sauf une TÂCHE
              (devis, planifier, décider) et un message DÉJÀ ouvert depuis
              l'ERP (`faitVerrouille`/`sauterVerrouille`, plus haut). */}
          {!sauterVerrouille && (
            <Button
              size="sm" variant="outline" disabled={busy}
              onClick={() => setPanel('sauter')}
            >
              <SkipForward className="size-3.5" /> Sauter
            </Button>
          )}
          {!faitVerrouille && (
            <Button size="sm" disabled={busy} onClick={() => setPanel('fait')}>
              <Check className="size-3.5" /> Fait
            </Button>
          )}
        </div>
      )}
      {/* CAD82 — sous chaque bouton désactivé, sa raison exacte (numéro
          absent vs droits PII), jamais un bouton mort sans cause. */}
      {!readOnly && panel === '' && sansTelephone && (
        <p className="mt-1 text-right text-xs text-muted-foreground" data-testid="raison-appeler">
          {raisonSansNumero('Appeler')}
        </p>
      )}
      {!readOnly && panel === '' && sansNumeroWhatsApp && (
        <p className="mt-1 text-right text-xs text-muted-foreground" data-testid="raison-whatsapp">
          {raisonSansNumero('WhatsApp')}
        </p>
      )}
      {!readOnly && faitVerrouille && panel === '' && (
        <p className="mt-1 text-right text-xs text-muted-foreground" data-testid="touche-en-avance">
          Touche à venir : appeler, écrire ou reporter dès maintenant — « Fait » s’ouvrira à son échéance,
          ou dès que le geste est fait{toucheMessage
            ? ' (message ouvert depuis l’ERP).'
            : ' (appel passé : « Appeler », puis « Saisir l’issue de l’appel »).'}
        </p>
      )}
      {!readOnly && !sauterVerrouille && panel === 'sauter' && (
        <div className="mt-2 flex flex-col gap-1.5">
          <Textarea
            rows={2} placeholder="Note (optionnelle) — pourquoi sauter cette relance ?"
            value={note} onChange={(e) => setNote(e.target.value)}
          />
          {/* CAD47 — « Sauter » faisait peur : rien ne disait que la cadence
              continue. La phrase vient du SERVEUR (`etape.suites.sauter`,
              dérivée du moteur, garde CAD17) : la touche suivante est
              programmée — ou, sur la dernière touche / une étape posée par le
              moteur, ce qui se passe réellement. */}
          <p className="text-xs text-muted-foreground" data-testid="suite-sauter">
            {suiteDuSaut(etape)}
          </p>
          {/* SUIVI-REFUS — ce que le serveur a refusé (touche déjà traitée,
              rôle, réseau…), SOUS le geste et en clair : le même `erreur-outcome`
              que le panneau « Fait » (un seul panneau est ouvert à la fois). */}
          {erreurOutcome && (
            <p className="text-xs text-danger" role="alert" data-testid="erreur-outcome">
              {erreurOutcome}
            </p>
          )}
          <div className="flex justify-end gap-1.5">
            <Button size="sm" variant="outline" disabled={busy} onClick={fermer}>
              Annuler
            </Button>
            <Button size="sm" disabled={busy} onClick={confirmerSauter}>
              Confirmer
            </Button>
          </div>
        </div>
      )}
      {!readOnly && panel === 'fait' && (
        <div className="mt-2 flex flex-col gap-1.5">
          <p className="text-sm font-medium">{questionsTouche.question}</p>
          {/* SUIVI-BLOCAGE — une réponse saisie AVANT l'échéance se dit : le
              serveur la date d'aujourd'hui (« traitée en avance », CAD44) et
              le reste du plan ne bouge pas. */}
          {enAvance && (
            <p className="text-xs text-muted-foreground" data-testid="reponse-en-avance">
              {REPONSE_EN_AVANCE}
            </p>
          )}
          {/* CAD12 — l'issue la plus importante (« le client accepte ») ne
              renvoie plus vers un autre écran à chercher : sur une touche qui
              porte son devis (`etape.devis`, contrat `relance_etape_v2`), un
              LIEN direct ouvre la fiche de CE devis, où « Accepter » est à
              portée de clic. Un lien, jamais une action de statut depuis le
              CRM : la chaîne Devis → BonCommande → Facture reste celle de
              Ventes (règle #4). Sans devis dans l'ERP, l'aide d'origine. */}
          {questionsTouche.aide && (etape.devis ? (
            <p className="text-xs text-muted-foreground" data-testid="aide-devis-accepte">
              Le client accepte ?{' '}
              <a
                href={`/ventes/devis?devis=${etape.devis}`}
                className="font-medium text-primary underline"
                onClick={(e) => {
                  if (!navigate) return
                  e.preventDefault()
                  navigate(`/ventes/devis?devis=${etape.devis}`)
                }}
              >
                Marquer le devis{etape.devis_reference ? ` ${etape.devis_reference}` : ''} accepté
              </a>
              {' '}: le dossier passe en Signé et toutes les relances s’arrêtent.
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">{questionsTouche.aide}</p>
          ))}
          {/* RLC3 — sur une touche MESSAGE, le panneau rappelle d'abord si le
              message a été ouvert. Ouvert : on le dit, et rien n'est demandé.
              Pas ouvert : une confirmation EXPLICITE, jamais un blocage —
              Meryem peut parfaitement avoir écrit depuis son téléphone. */}
          {toucheMessage && messageOuvertLe && (
            <p
              className="text-xs text-muted-foreground"
              data-testid="rappel-message-ouvert"
            >
              Message ouvert à {messageOuvertLe} depuis l’ERP.
            </p>
          )}
          {toucheMessage && !messageOuvertLe && (
            <label
              className="flex items-start gap-1.5 text-xs"
              data-testid="confirmer-sans-ouverture"
            >
              <input
                type="checkbox" className="mt-0.5" checked={sansOuverture}
                onChange={(e) => setSansOuverture(e.target.checked)}
              />
              {/* CAD84 — le canal de la touche est SUGGÉRÉ, jamais imposé
                  (les deux boutons Appeler / WhatsApp sont toujours là) :
                  la question ne présume plus qu'un message devait partir.
                  Même mécanisme (case à cocher, jamais un blocage), formulation
                  neutre. */}
              <span>
                Vous n’avez pas ouvert de message {CANAL_LABELS[etape.canal] ?? etape.canal} pour
                cette touche — c’est normal si vous avez appelé à la place. Cochez
                pour confirmer.
              </span>
            </label>
          )}
          <div className="flex flex-wrap gap-1.5" role="group" aria-label={questionsTouche.question}>
            {reponsesDisponibles.map((r, idx) => (
              <Button
                key={r.label} type="button" size="sm"
                variant={reponseIdx === idx ? 'default' : 'outline'}
                onClick={() => {
                  setReponseIdx((cur) => (cur === idx ? null : idx)); setErreurOutcome('')
                  setErreurMotif('')
                  if (r.outcome === 'refuse' || r.junk || r.motif_perte) chargerMotifs()
                }}
              >
                {r.label}
              </Button>
            ))}
          </div>
          {/* CAD17 — la suite annoncée vient du SERVEUR (`etape.suites`,
              dérivée du moteur) : jamais une phrase écrite par cadence.
              CAD11 — la case « perdu, motif junk » cochée change la suite
              réelle (le lead passe perdu : plus aucune relance, sans suite —
              `suite=False` côté serveur) : la phrase le dit alors. */}
          {reponseChoisie && (
            <p className="text-xs text-muted-foreground" data-testid="suite-reponse">
              {reponseChoisie.junk && perduJunk
                ? 'Le lead passe perdu (motif junk) : toutes ses relances s’arrêtent, sans aucune suite.'
                : suiteAnnoncee(etape, reponseChoisie)}
            </p>
          )}
          {erreurOutcome && (
            <p className="text-xs text-danger" role="alert" data-testid="erreur-outcome">
              {erreurOutcome}
            </p>
          )}
          {reponseChoisie?.date && (
            <div className="flex flex-wrap items-end gap-2">
              <div className="flex flex-col gap-1">
                <Label className="text-xs" htmlFor={`rappel-le-${etape.id}`}>Rappeler le</Label>
                <Input id={`rappel-le-${etape.id}`} type="date" className="w-40"
                       min={aujourdhui} aria-invalid={Boolean(messageRappel)}
                       value={rappelLe}
                       onChange={(e) => { setRappelLe(e.target.value); setErreurRappel('') }} />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs" htmlFor={`rappel-heure-${etape.id}`}>Heure</Label>
                <Input id={`rappel-heure-${etape.id}`} type="time" className="w-28"
                       value={rappelHeure} onChange={(e) => setRappelHeure(e.target.value)} />
              </div>
            </div>
          )}
          {/* CAD46 — « À rappeler le… », le contrôle le PLUS utilisé, passe
              par le même chemin que « Reporter » : il décale tout le reste du
              plan. La même phrase le dit, sous le champ. (« Plus tard » a sa
              propre suite — la veille — annoncée par le serveur.) */}
          {reponseChoisie?.date && reponseChoisie.outcome === 'rappel' && !estTacheLibre && (
            <p className="text-xs text-muted-foreground" data-testid="glissement-plan">
              {GLISSEMENT_DU_PLAN}
            </p>
          )}
          {reponseChoisie?.date && messageRappel && (
            <p className="text-xs text-danger" role="alert" data-testid="erreur-rappel-le">
              {messageRappel}
            </p>
          )}
          {/* CAD10 — le seul moment où la raison du refus est connue : la
              liste courte déjà paramétrée est PROPOSÉE, jamais exigée
              (« perdu » reste une décision humaine). Le motif part sur la
              ligne de chatter de la touche, pas sur le motif de perte. */}
          {reponseChoisie?.outcome === 'refuse' && (
            <div className="flex flex-col gap-1">
              <Label className="text-xs" htmlFor={`motif-refus-${etape.id}`}>
                Motif du refus (facultatif)
              </Label>
              <select
                id={`motif-refus-${etape.id}`}
                className={erreurMotif ? 'form-select is-invalid' : 'form-select'}
                value={motifRefus}
                onChange={(e) => { setMotifRefus(e.target.value); setErreurMotif('') }}
              >
                <option value="">— Sans motif —</option>
                {(motifs ?? []).map((m) => (
                  <option key={m.id ?? m.nom} value={m.nom}>{m.nom}</option>
                ))}
              </select>
              {erreurMotif && (
                <p className="text-xs text-danger" role="alert" data-testid="erreur-motif-refus">
                  {erreurMotif}
                </p>
              )}
            </div>
          )}
          {/* SUIVI-PARCOURS — « Perdu — clore le dossier » (étape « Décider la
              suite ») : le motif de perte est OBLIGATOIRE (MRY22 : « perdu »
              est une décision humaine, avec son motif). La liste est celle de
              Paramètres → CRM ; le lead passe Perdu et toutes ses relances
              s'arrêtent — la phrase de la réponse le dit avant le clic. */}
          {reponseChoisie?.motif_perte && (
            <div className="flex flex-col gap-1" data-testid="motif-perte">
              <Label className="text-xs" htmlFor={`motif-perte-${etape.id}`}>
                Motif de perte (obligatoire)
              </Label>
              <select
                id={`motif-perte-${etape.id}`}
                className={erreurMotif ? 'form-select is-invalid' : 'form-select'}
                value={motifPerte}
                onChange={(e) => { setMotifPerte(e.target.value); setErreurMotif('') }}
              >
                <option value="">— Choisir le motif —</option>
                {(motifs ?? []).map((m) => (
                  <option key={m.id ?? m.nom} value={m.nom}>{m.nom}</option>
                ))}
              </select>
              {motifs !== null && (motifs ?? []).length === 0 && (
                <p className="text-xs text-warning" data-testid="motif-perte-aucun">
                  Aucun motif de perte n’est paramétré (Paramètres → CRM → Motifs de perte).
                </p>
              )}
              {erreurMotif && (
                <p className="text-xs text-danger" role="alert" data-testid="erreur-motif-perte">
                  {erreurMotif}
                </p>
              )}
            </div>
          )}
          {/* CAD11 — la proposition « perdu, motif junk » en UN clic, jamais
              imposée : la case reste décochée tant que la commerciale ne
              décide pas. Sans motif junk paramétré, rien n'est proposé. */}
          {reponseChoisie?.junk && motifsJunk.length > 0 && (
            <div className="flex flex-col gap-1" data-testid="proposition-perdu-junk">
              <label className="flex items-center gap-1.5 text-xs">
                <input
                  type="checkbox" checked={perduJunk}
                  onChange={(e) => { setPerduJunk(e.target.checked); setErreurMotif('') }}
                />
                <span>Marquer le lead perdu — motif junk (pas un vrai prospect)</span>
              </label>
              {perduJunk && (
                <select
                  aria-label="Motif junk"
                  className={erreurMotif ? 'form-select is-invalid' : 'form-select'}
                  value={motifJunkEffectif}
                  onChange={(e) => { setMotifJunk(e.target.value); setErreurMotif('') }}
                >
                  {motifsJunk.map((m) => (
                    <option key={m.id ?? m.nom} value={m.nom}>{m.nom}</option>
                  ))}
                </select>
              )}
              {erreurMotif && (
                <p className="text-xs text-danger" role="alert" data-testid="erreur-perdu-junk">
                  {erreurMotif}
                </p>
              )}
            </div>
          )}
          {/* CAD63 — la langue se découvre au téléphone : la poser ICI, sans
              quitter la touche ni rouvrir la fiche. Jamais cochée d'office. */}
          {etape.lead_langue !== 'darija' && (
            <div className="flex flex-col gap-1">
              <label className="flex items-center gap-1.5 text-xs" data-testid="ne-parle-que-darija">
                <input
                  type="checkbox" checked={queDarija}
                  onChange={(e) => { setQueDarija(e.target.checked); setErreurLangue('') }}
                />
                <span>Le client ne parle que darija — enregistrer sa langue sur la fiche</span>
              </label>
              {erreurLangue && (
                <p className="text-xs text-danger" role="alert" data-testid="erreur-langue">
                  {erreurLangue}
                </p>
              )}
            </div>
          )}
          <Textarea
            rows={2} placeholder="Note (optionnelle)"
            value={note} onChange={(e) => setNote(e.target.value)}
          />
          <div className="flex flex-wrap justify-end gap-1.5">
            {/* CAD80 — rappeler depuis le panneau sans perdre la note : elle
                est gardée avant de céder la main au téléphone et retrouvée au
                retour, même si la page s'est rechargée. */}
            {etape.lead_telephone && (
              <Button size="sm" variant="outline" disabled={busy} onClick={appeler}
                      title="La note tapée est gardée pendant l’appel.">
                <Phone className="size-3.5" /> Appeler (note gardée)
              </Button>
            )}
            <Button size="sm" variant="outline" disabled={busy} onClick={fermer}>
              Annuler
            </Button>
            <Button
              size="sm"
              disabled={busy || Boolean(raisonConfirmerGrise)}
              onClick={confirmerFait}
            >
              Confirmer
            </Button>
          </div>
          {/* SUIVI-BLOCAGE — un bouton grisé dit pourquoi (règle fondateur du
              08/09 : le champ fautif, le message exact). */}
          {raisonConfirmerGrise && !busy && (
            <p className="text-right text-xs text-muted-foreground" data-testid="raison-confirmer">
              {raisonConfirmerGrise}
            </p>
          )}
        </div>
      )}
      {!readOnly && panel === 'piece' && (
        <div className="mt-2 flex flex-col gap-1.5" data-testid="panneau-piece-recue">
          <p className="text-sm font-medium">Qu’a envoyé le client ?</p>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Pièce reçue">
            {PIECES_RECUES.map((p) => (
              <Button
                key={p.cle} type="button" size="sm"
                variant={typePiece === p.cle ? 'default' : 'outline'}
                aria-pressed={typePiece === p.cle}
                onClick={() => { setTypePiece(p.cle); setErreurPiece('') }}
              >
                {p.label}
              </Button>
            ))}
          </div>
          {/* La conséquence est DITE avant le clic (règle CAD17 : jamais un
              effet caché) : c'est exactement ce que le serveur fait. */}
          <p className="text-xs text-muted-foreground" data-testid="suite-piece-recue">
            La touche est close (le client a répondu), le document est joint à la fiche et
            l’étape « Préparer et envoyer le devis » est posée.
          </p>
          <div className="flex flex-col gap-1">
            <Label className="text-xs" htmlFor={`piece-fichier-${etape.id}`}>Fichier (facultatif)</Label>
            <Input
              id={`piece-fichier-${etape.id}`} type="file"
              onChange={(e) => { setFichierPiece(e.target.files?.[0] ?? null); setErreurPiece('') }}
            />
          </div>
          <Textarea
            rows={2} placeholder="Note (facultative) — ex. l’adresse exacte"
            value={note} onChange={(e) => setNote(e.target.value)}
          />
          {erreurPiece && (
            <p className="text-xs text-danger" role="alert" data-testid="erreur-piece-recue">
              {erreurPiece}
            </p>
          )}
          <div className="flex justify-end gap-1.5">
            <Button size="sm" variant="outline" disabled={envoiPiece} onClick={fermer}>
              Annuler
            </Button>
            <Button size="sm" disabled={!typePiece || envoiPiece} loading={envoiPiece} onClick={confirmerPiece}>
              Confirmer
            </Button>
          </div>
        </div>
      )}
      {!readOnly && panel === 'reporter' && (
        <div className="mt-2 flex flex-col gap-1.5">
          {/* CAD26 — DEUX gestes : décaler (quelques jours, la suite glisse)
              ou mettre en veille (la cadence se tait et reprend au même
              barreau ; au-delà d'un mois, réveil daté). Au-delà de 7 jours,
              la veille est proposée d'elle-même — le choix explicite prime. */}
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Geste de report">
            <Button
              type="button" size="sm"
              variant={modeReport === 'decaler' ? 'default' : 'outline'}
              aria-pressed={modeReport === 'decaler'}
              onClick={() => setReportMode('decaler')}
            >
              Décaler ce rappel
            </Button>
            <Button
              type="button" size="sm"
              variant={modeReport === 'veille' ? 'default' : 'outline'}
              aria-pressed={modeReport === 'veille'}
              onClick={() => setReportMode('veille')}
            >
              Mettre en veille jusqu’au…
            </Button>
          </div>
          <p className="text-xs text-muted-foreground" data-testid="suite-report">
            {modeReport === 'veille'
              ? 'La cadence se tait jusqu’à cette date et reprend à cette même touche — aucune relance ne part d’ici là. Au-delà d’un mois, elle bascule en réveil daté.'
              : 'Cette touche est déplacée à la date choisie.'}
          </p>
          {veilleProposee && !reportMode && (
            <p className="text-xs text-warning" data-testid="veille-proposee">
              Report de plus de {VEILLE_PROPOSEE_APRES_JOURS} jours : la mise en veille est proposée.
            </p>
          )}
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex flex-col gap-1">
              <Label className="text-xs" htmlFor={`report-date-${etape.id}`}>Reporter au</Label>
              <Input id={`report-date-${etape.id}`} type="date" className="w-40"
                     min={aujourdhui} aria-invalid={reportPasse || Boolean(erreurRappel)}
                     value={reportDate}
                     onChange={(e) => { setReportDate(e.target.value); setErreurRappel('') }} />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs" htmlFor={`report-heure-${etape.id}`}>Heure</Label>
              <Input id={`report-heure-${etape.id}`} type="time" className="w-28"
                     value={reportHeure} onChange={(e) => setReportHeure(e.target.value)} />
            </div>
          </div>
          {/* CAD46 — décaler une touche décale TOUT le plan (les touches
              suivantes et l'ancre `cadence_depart`, du même écart : garde
              CAD17 `GlissementDuPlanTests`). Sans cette phrase, Meryem croyait
              bouger un rendez-vous et découvrait des semaines plus tard que le
              dossier avait dérivé. */}
          {modeReport === 'decaler' && (
            <p className="text-xs text-muted-foreground" data-testid="glissement-plan">
              {GLISSEMENT_DU_PLAN}
            </p>
          )}
          {/* SUIVI-REFUS — la date refusée par le serveur (400
              `erreurs.rappel_le`, message qui nomme « Reporter au ») s'affiche
              dans le MÊME emplacement que le refus d'écran, sous son champ. */}
          {(reportPasse || erreurRappel) && (
            <p className="text-xs text-danger" role="alert" data-testid="erreur-report-date">
              {reportPasse
                ? '« Reporter au » : cette date est déjà passée — choisissez aujourd’hui ou une date à venir.'
                : erreurRappel}
            </p>
          )}
          {/* SUIVI-REFUS — les autres refus (touche déjà traitée, rôle,
              réseau…) : sous le geste, le même `erreur-outcome` que « Fait ». */}
          {erreurOutcome && (
            <p className="text-xs text-danger" role="alert" data-testid="erreur-outcome">
              {erreurOutcome}
            </p>
          )}
          <div className="flex justify-end gap-1.5">
            <Button size="sm" variant="outline" disabled={busy} onClick={fermer}>
              Annuler
            </Button>
            <Button size="sm" disabled={busy || !reportDate || reportPasse} onClick={confirmerReporter}>
              Confirmer
            </Button>
          </div>
        </div>
      )}
      {/* VISCAD6 — PARTAGÉE par le CTA du panneau de coaching ci-dessus ET
          l'issue « Visite acceptée » de `confirmerFait` — une seule modale,
          un seul appel serveur. `etape.lead` porte l'id du lead (contrat
          `relance_etape_v2.json`) : jamais un second prop à faire remonter
          par les trois appelants de `RelanceEtapeRow`. */}
      {/* SUIVI-BLOCAGE — la modale s'ouvre AVANT tout enregistrement
          (`gestePlanification`) : la ligne est encore montée, la modale ne
          peut plus disparaître sous elle. C'est le serveur qui, à la
          planification réussie, clôt la touche qui l'a demandée (`etape`) ;
          « Date pas encore fixée » (visite acceptée seulement) envoie la
          réponse seule ; « Annuler » ne laisse rien. Une re-planification
          déplace la visite existante et laisse la touche ouverte. */}
      <PlanifierVisiteModal
        leadId={etape.lead}
        open={planifierOuvert}
        onOpenChange={(o) => { setPlanifierOuvert(o); if (!o) setGestePlanification('') }}
        onPlanifie={visitePlanifiee}
        etapeId={gestePlanification && gestePlanification !== 'replanification' ? etape.id : undefined}
        noteEtape={gestePlanification && gestePlanification !== 'replanification' ? note.trim() : undefined}
        replanifier={gestePlanification === 'replanification'}
        onSansDate={gestePlanification === 'planification' ? enregistrerSansDate : undefined}
      />
    </li>
  )
}
