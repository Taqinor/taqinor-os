// COCKPIT-CONTRÔLE (fondateur, 30/09/2026 : « … to make reading the data and if
// the commercial did everything as she should ») — le bloc « Contrôle du suivi »
// du cockpit CRM : UNE lecture répond à « ce qui devait être fait l'a-t-il été ? ».
//
// Deux lecteurs, un même écran (décision de transparence CKP3/CKP5) : la
// commerciale traite sa journée dans « À faire aujourd'hui », le responsable lit ici, en
// quelques secondes, ce qui a été fait, tardé ou oublié. Même bloc pour tous les
// rôles : seule la portée serveur (`scope_queryset` via le lead) borne la lecture ;
// une seule ligne d'aide (sous « Dossiers sans prochaine étape ») est réservée au
// responsable / à l'admin, car la carte qu'elle vise ne s'affiche que pour eux.
//
// REPLIABLE, replié par défaut : le titre, le BANDEAU du verdict, la phrase de la
// période et le bouton « Voir le détail » se lisent toujours ; les sélecteurs, la
// comparaison, la frise, les listes d'exceptions, le détail par étape, le premier
// contact et les résultats sont derrière ce bouton. Le choix (déplié / replié) est
// mémorisé PAR NAVIGATEUR (`CLE_DETAIL`), jamais par rôle ; la requête part au
// montage dans les deux états.
//
// Ce que la recherche (Outreach, HubSpot, Close, Pipedrive, Gong, Zoho, noCRM,
// Odoo ; NN/g) a établi, et qui est appliqué ici :
//   · aucune « note » unique : un VERDICT court, des indicateurs séparés, et la
//     LISTE des dossiers derrière chaque chiffre ;
//   · couleur ET forme ET texte, jamais la couleur seule ; les retards d'abord ;
//   · une liste d'exceptions plutôt que des tableaux ; l'état de l'INSTANT (les
//     exceptions) séparé de l'activité de la PÉRIODE (verdict, frise, détail) ;
//   · une frise d'un jour par case, chaque case ouvre la liste de son jour.
//
// Forme lue : `GET relance-etapes/controle/?jours=&owner=`, contrat committé
// `apps/crm/contract_samples/controle_suivi.json` (PACT10) — les tests montent
// l'exemple du contrat, jamais un objet retapé. Aucun chiffre n'est recalculé
// ici (voir `controleSuiviTexte.js`) ; les noms d'étapes et de réponses sont lus
// dans la table du parcours (`parcours_suivi.json`).
import { useEffect, useId, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ChevronDown, ChevronRight, ChevronUp, ClipboardCheck } from 'lucide-react'
import crmApi from '../../api/crmApi'
import {
  Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle,
  Segmented, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Skeleton,
} from '../../ui'
import { cn } from '../../lib/cn'
import { safeGet, safeSet } from '../../lib/safeStorage'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { STAGE_LABELS } from '../../features/crm/stages'
import {
  comparaisonPrecedent, decimal, dureeAttente, heureCasa, jjmm, jourCourt, jourLong, joursOuvres,
  libelleJour, libelleReponse, nomType, nombre, noteJoursOuvres, numeroJour, phraseAnnulees,
  phraseExceptions, phrasePeriode, phrasePremierContact, phraseReportee, phraseResultats, pl,
} from './controleSuiviTexte'

const PERIODES = [
  { value: 7, label: '7 jours' },
  { value: 14, label: '14 jours' },
  { value: 30, label: '30 jours' },
]
const PERIODE_DEFAUT = 14

// Le détail (sélecteurs, frise, listes…) est REPLIÉ par défaut ; le choix de
// l'utilisateur est mémorisé PAR NAVIGATEUR (jamais par rôle), avec l'aide
// défensive du dépôt (`lib/safeStorage`) : un stockage indisponible = replié.
const CLE_DETAIL = 'crm.cockpit.controle.detail'
const lireDetailOuvert = () => safeGet(CLE_DETAIL) === true

// Le VERDICT : forme + couleur + mot (jamais la couleur seule). Le mot et la
// forme portent le sens ; la teinte ne fait que l'appuyer.
const NIVEAUX = {
  ok: {
    glyphe: '●', mot: 'Tout est à jour',
    bande: 'border-success/40 bg-success/10', texte: 'text-success',
  },
  attention: {
    glyphe: '◆', mot: 'À surveiller',
    bande: 'border-warning/50 bg-warning/10', texte: 'text-warning-text',
  },
  // « Action requise » et non « En retard » : le niveau peut venir d'un dossier
  // sans prochaine étape ou d'un premier contact hors délai, pas d'un retard.
  alerte: {
    glyphe: '▲', mot: 'Action requise',
    bande: 'border-destructive/40 bg-destructive/10', texte: 'text-destructive',
  },
  vide: {
    glyphe: '–', mot: 'Pas encore de données',
    bande: 'border-border bg-muted/50', texte: 'text-muted-foreground',
  },
}
// Un niveau que cet écran ne connaît pas (serveur plus récent) : dit tel quel,
// jamais rabattu sur « Tout est à jour ».
const niveauInconnu = (niveau) => ({
  glyphe: '–', mot: niveau ? `Niveau « ${niveau} »` : 'Niveau inconnu',
  bande: 'border-border bg-muted/50', texte: 'text-muted-foreground',
})

// L'ÉTAT d'un jour de la frise : la forme + le mot de la légende.
const ETATS_JOUR = {
  vert: { glyphe: '●', texte: 'text-success', mot: 'tout traité le jour même' },
  orange: { glyphe: '◆', texte: 'text-warning-text', mot: 'traité en retard ou sauté' },
  // Le retard se compte en JOURS OUVRÉS (contrat `notes.retard`) : « rouge » = il reste
  // une étape ouverte ET en retard ; « en cours » = il en reste, mais aucune n'est
  // encore en retard (aujourd'hui, ou un jour passé sans jour ouvré depuis).
  rouge: { glyphe: '▲', texte: 'text-destructive', mot: 'il en reste en retard' },
  en_cours: { glyphe: '◔', texte: 'text-info', mot: 'encore dans les temps' },
  vide: { glyphe: '–', texte: 'text-muted-foreground', mot: 'rien de dû' },
}
const ORDRE_LEGENDE = ['vert', 'orange', 'rouge', 'en_cours', 'vide']

/** La forme d'un état (rond, losange, triangle, cadran, tiret) : décorative, le
 *  texte voisin porte toujours le sens. */
function Forme({ glyphe, className }) {
  return (
    <span aria-hidden="true" className={cn('inline-block w-4 text-center leading-none', className)}>
      {glyphe}
    </span>
  )
}

/** Lien vers la fiche du lead — même route que la ligne d'étape
 *  (`/crm/leads?lead=<id>`) ; un vrai lien (clic droit, nouvel onglet) qui
 *  navigue sans recharger sur un clic simple. */
function LienLead({ leadId, nom, navigate }) {
  const href = `/crm/leads?lead=${leadId}`
  return (
    <a
      href={href}
      className="font-medium text-primary-text underline-offset-2 hover:underline"
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button > 0) return
        e.preventDefault()
        navigate(href)
      }}
    >
      {nom || `Lead ${leadId}`}
    </a>
  )
}

// ── En-tête : période + commercial ─────────────────────────────────────────
function Selecteurs({
  jours, onJours, ownerId, onOwner, commerciaux, erreurs,
}) {
  const autres = Object.entries(erreurs || {})
    .filter(([champ]) => champ !== 'jours' && champ !== 'owner')
    .map(([, message]) => message)
  return (
    <div className="flex flex-wrap items-start gap-x-3 gap-y-2" data-testid="controle-selecteurs">
      <div className="flex flex-col gap-1">
        <Segmented
          size="sm" aria-label="Période" data-testid="controle-periode"
          options={PERIODES} value={jours} onChange={onJours}
        />
        {erreurs?.jours && (
          <p role="alert" className="text-xs text-destructive" data-testid="controle-erreur-jours">
            {erreurs.jours}
          </p>
        )}
      </div>
      {commerciaux.length > 1 && (
        <div className="flex flex-col gap-1">
          <Select
            value={ownerId === null ? 'tous' : String(ownerId)}
            onValueChange={(v) => onOwner(v === 'tous' ? null : Number(v))}
          >
            <SelectTrigger className="w-48" aria-label="Commercial">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="tous">Toute l&apos;équipe</SelectItem>
              {commerciaux.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {erreurs?.owner && (
            <p role="alert" className="text-xs text-destructive" data-testid="controle-erreur-owner">
              {erreurs.owner}
            </p>
          )}
        </div>
      )}
      {autres.length > 0 && (
        <p role="alert" className="basis-full text-xs text-destructive" data-testid="controle-erreur-autre">
          {autres.join(' ')}
        </p>
      )}
    </div>
  )
}

// ── Bandeau : le verdict et la phrase de la période (toujours visibles) ─────
function Bandeau({ donnees }) {
  const { verdict, exceptions, periode_jours: periode } = donnees
  const niveau = NIVEAUX[verdict?.niveau] ?? niveauInconnu(verdict?.niveau)
  const phrase = phraseExceptions(exceptions, verdict?.niveau)
  return (
    <div className="flex flex-col gap-1.5">
      <div
        role="status" data-testid="controle-verdict" data-niveau={verdict?.niveau}
        className={cn(
          'flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border px-3 py-2.5',
          niveau.bande,
        )}
      >
        <span className={cn('inline-flex items-center gap-1.5 text-base font-semibold', niveau.texte)}>
          <Forme glyphe={niveau.glyphe} />
          {niveau.mot}
        </span>
        {phrase && <span className="text-sm text-foreground">{phrase}</span>}
      </div>
      <p className="text-sm text-muted-foreground" data-testid="controle-phrase-periode">
        {phrasePeriode(verdict, periode)}
      </p>
    </div>
  )
}

/** ↑ / ↓ / → face à la période précédente : dans le détail, pas dans le bandeau. */
function Comparaison({ verdict }) {
  const comparaison = comparaisonPrecedent(verdict)
  if (!comparaison) return null
  return (
    <p
      className={cn(
        'text-xs font-medium',
        comparaison.sens === 'hausse' && 'text-success',
        comparaison.sens === 'baisse' && 'text-destructive',
        comparaison.sens === 'stable' && 'text-muted-foreground',
      )}
      data-testid="controle-comparaison"
    >
      {comparaison.texte}
    </p>
  )
}

// ── Frise ──────────────────────────────────────────────────────────────────
function StatutBadgeJour({ etape }) {
  if (etape.statut === 'a_faire') {
    return etape.overdue
      ? <Badge tone="danger">En retard</Badge>
      : <Badge tone="outline">{etape.statut_libelle || 'À faire'}</Badge>
  }
  if (etape.statut === 'fait') return <Badge tone="success">{etape.statut_libelle || 'Fait'}</Badge>
  if (etape.statut === 'sautee') return <Badge tone="neutral">{etape.statut_libelle || 'Sautée'}</Badge>
  return <Badge tone="outline">{etape.statut_libelle || etape.statut}</Badge>
}

/** Les étapes dues CE jour-là (`GET relance-etapes/suivi/` sur [jour, jour]),
 *  en lecture : un dossier par ligne, jamais un geste de traitement ici. */
function ListeDuJour({
  date, ownerId, navigate, onFermer, id,
}) {
  const [tentative, setTentative] = useState(0)
  const [resultat, setResultat] = useState({ tentative: null, lignes: [], panne: false })

  useEffect(() => {
    let active = true
    const params = { date_debut: date, date_fin: date }
    if (ownerId !== null) params.owner = ownerId
    Promise.resolve()
      .then(() => crmApi.getRelanceEtapesSuivi(params))
      .then((r) => {
        if (active) setResultat({ tentative, lignes: r?.data?.results ?? [], panne: false })
      })
      .catch(() => { if (active) setResultat({ tentative, lignes: [], panne: true }) })
    return () => { active = false }
  }, [date, ownerId, tentative])

  const chargement = resultat.tentative !== tentative
  // Une touche `annulee` a été retirée du plan par le MOTEUR (le client a répondu) :
  // ni due ni manquée. Elle n'a pas de ligne ici — la liste compte alors autant de
  // lignes que le `du` de la case — mais une phrase discrète dit combien ont été
  // mises de côté (les lignes écartées, comme « total − lignes » ailleurs).
  const lignes = resultat.lignes.filter((etape) => etape.statut !== 'annulee')
  const annulees = resultat.lignes.length - lignes.length
  return (
    <div
      id={id} role="region" aria-label={`Étapes du ${jourLong(date)}`}
      className="mt-3 rounded-lg border border-border p-3" data-testid="controle-jour-liste"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold first-letter:uppercase">{jourLong(date)}</h4>
        <Button type="button" size="sm" variant="ghost" onClick={onFermer}>Fermer</Button>
      </div>
      {chargement ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      ) : resultat.panne ? (
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
          <Button type="button" size="sm" variant="outline" onClick={() => setTentative((t) => t + 1)}>
            Réessayer
          </Button>
        </div>
      ) : (
        <>
          {lignes.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune étape n&apos;était due ce jour-là.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {lignes.map((etape) => {
                const traitee = etape.statut === 'fait' || etape.statut === 'sautee'
                const heure = heureCasa(traitee ? etape.traite_le : etape.due_at)
                return (
                  <li
                    key={etape.id} data-testid="controle-jour-ligne"
                    className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border border-border/60 px-2 py-1.5 text-sm"
                  >
                    <LienLead leadId={etape.lead} nom={etape.lead_nom} navigate={navigate} />
                    <span className="text-muted-foreground">{etape.libelle}</span>
                    <StatutBadgeJour etape={etape} />
                    {heure && (
                      <span className="text-xs text-muted-foreground">
                        {traitee ? `traitée à ${heure}` : `prévue à ${heure}`}
                      </span>
                    )}
                    {traitee && etape.traite_par_nom && (
                      <span className="text-xs text-muted-foreground">par {etape.traite_par_nom}</span>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
          {annulees > 0 && (
            <p className="mt-2 text-xs text-muted-foreground" data-testid="controle-jour-annulees">
              {phraseAnnulees(annulees)}
            </p>
          )}
        </>
      )}
    </div>
  )
}

function Frise({ donnees, ownerId, navigate }) {
  const jours = donnees.jours ?? []
  const [ouvert, setOuvert] = useState(null)
  const [tabIdx, setTabIdx] = useState(null)
  const cases = useRef([])
  const idListe = useId()

  if (jours.length === 0) return null

  // Roving tabindex : la frise n'est QU'UN arrêt de tabulation (jusqu'à 30
  // cases), les flèches / Début / Fin y circulent — même patron que `Segmented`.
  const tabulable = tabIdx ?? jours.length - 1
  const onKeyDown = (e) => {
    const courant = Number(e.target?.dataset?.index)
    if (!Number.isInteger(courant)) return
    let cible
    if (e.key === 'ArrowRight') cible = Math.min(jours.length - 1, courant + 1)
    else if (e.key === 'ArrowLeft') cible = Math.max(0, courant - 1)
    else if (e.key === 'Home') cible = 0
    else if (e.key === 'End') cible = jours.length - 1
    else return
    e.preventDefault()
    setTabIdx(cible)
    cases.current[cible]?.focus()
  }

  return (
    <section aria-labelledby={`${idListe}-titre`} data-testid="controle-frise">
      <h4 id={`${idListe}-titre`} className="mb-1.5 text-sm font-semibold">
        Jour par jour
      </h4>
      <ol
        className="grid grid-cols-7 gap-1 sm:grid-cols-[repeat(auto-fit,minmax(2.5rem,1fr))]"
        onKeyDown={onKeyDown}
      >
        {jours.map((j, i) => {
          const etat = ETATS_JOUR[j.etat] ?? ETATS_JOUR.vide
          const estOuvert = ouvert === j.date
          return (
            <li key={j.date} className="min-w-0">
              <button
                type="button"
                ref={(el) => { cases.current[i] = el }}
                data-index={i}
                data-testid={`controle-jour-${j.date}`}
                data-etat={j.etat}
                aria-label={libelleJour(j)}
                aria-expanded={estOuvert}
                aria-controls={idListe}
                tabIndex={i === tabulable ? 0 : -1}
                onFocus={() => setTabIdx(i)}
                onClick={() => setOuvert(estOuvert ? null : j.date)}
                className={cn(
                  'focus-ring flex w-full flex-col items-center gap-0.5 rounded-md border px-1 py-1.5 text-center transition-colors',
                  estOuvert ? 'border-primary bg-muted' : 'border-border bg-card hover:bg-muted',
                  j.aujourdhui && 'ring-2 ring-primary/60',
                  j.ouvre === false && 'opacity-50',
                )}
              >
                <span aria-hidden="true" className="text-[10px] font-medium uppercase leading-none text-muted-foreground">
                  {jourCourt(j.date)}
                </span>
                <span aria-hidden="true" className="text-sm font-semibold leading-none tabular-nums">
                  {numeroJour(j.date)}
                </span>
                <Forme glyphe={etat.glyphe} className={cn('text-base', etat.texte)} />
              </button>
            </li>
          )
        })}
      </ol>
      {/* Légende : la forme ET le mot — la teinte ne porte jamais seule le sens. */}
      <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground" data-testid="controle-legende">
        {ORDRE_LEGENDE.map((cle) => (
          <li key={cle} className="inline-flex items-center gap-1">
            <Forme glyphe={ETATS_JOUR[cle].glyphe} className={ETATS_JOUR[cle].texte} />
            {ETATS_JOUR[cle].mot}
          </li>
        ))}
      </ul>
      {ouvert && (
        <ListeDuJour
          key={`${ouvert}|${ownerId ?? ''}`}
          id={idListe} date={ouvert} ownerId={ownerId} navigate={navigate}
          onFermer={() => setOuvert(null)}
        />
      )}
    </section>
  )
}

// ── Exceptions : « À traiter en priorité » ─────────────────────────────────
/** Un seuil SERVI par le serveur (`seuils.*`) ou `null` : un libellé ne dit jamais
 *  un nombre que le serveur n'a pas servi, ni un nombre écrit dans le code. */
const seuil = (seuils, cle) => (Number.isFinite(seuils?.[cle]) ? seuils[cle] : null)

// Ordre = celui du contrat. `titre(seuils)` dit CE que la liste contient, avec les
// seuils servis (`seuils.tache_attente_jours`, `reports_min`, `premier_contact_heures`) ;
// `detail` dit ce qui rend la ligne exceptionnelle, avec les nombres servis par le
// serveur (jamais recalculés ici).
const LISTES = [
  {
    cle: 'en_retard',
    titre: () => 'En retard',
    tone: 'danger',
    reportee: true,
    // `jours_de_retard` = JOURS OUVRÉS (≥ 1), jamais des jours calendaires.
    detail: (l) => (l.jours_de_retard == null ? ''
      : `en retard de ${joursOuvres(l.jours_de_retard)}`),
  },
  {
    cle: 'taches_en_attente',
    titre: (seuils) => {
      const jours = seuil(seuils, 'tache_attente_jours')
      return jours === null ? 'Tâches en attente'
        : `Tâches en attente depuis ${joursOuvres(jours)} ou plus`
    },
    tone: 'warning',
    reportee: true,
    // `ouverte_depuis_jours` = JOURS OUVRÉS depuis la pose.
    detail: (l) => (l.ouverte_depuis_jours == null ? ''
      : `posée il y a ${joursOuvres(l.ouverte_depuis_jours)}`),
  },
  {
    cle: 'reports',
    titre: (seuils) => {
      const fois = seuil(seuils, 'reports_min')
      return fois === null ? 'Reportées plusieurs fois' : `Reportées ${nombre(fois)} fois ou plus`
    },
    tone: 'warning',
    detail: (l) => (l.nb_reports == null ? ''
      : `${nombre(l.nb_reports)} ${pl(l.nb_reports, 'report', 'reports')} — prévue à l'origine le ${jjmm(l.due_initial)}`),
  },
  {
    cle: 'sans_prochaine_etape',
    titre: () => 'Dossiers sans prochaine étape',
    tone: 'danger',
    // Ligne du contrat (`exemple_alerte`) : `stage` est une clé de STAGES.py,
    // dite avec le libellé FR des constantes du frontend (`features/crm/stages`,
    // miroir strict de STAGES.py) — jamais une liste écrite ici ; une clé que
    // ces constantes ne connaissent pas s'affiche telle quelle.
    etiquette: (l) => (l.stage ? (STAGE_LABELS[l.stage] ?? l.stage) : ''),
    detail: (l) => {
      if (l.depuis_jours == null) return ''
      if (l.depuis_jours === 0) return "sans étape depuis aujourd'hui"
      return `sans étape depuis ${nombre(l.depuis_jours)} ${pl(l.depuis_jours, 'jour', 'jours')}`
    },
    // Sous la liste, pour le responsable / l'admin SEULEMENT : la carte qui sait
    // remettre ces dossiers dans une cadence ne s'affiche que pour eux (elle se gate
    // elle-même), une commerciale ne verrait qu'un renvoi vers rien.
    aideResponsable: 'Pour les remettre dans une cadence : carte « Anciens leads à placer », plus bas.',
  },
  {
    cle: 'premier_contact_hors_delai',
    titre: (seuils) => {
      const heures = seuil(seuils, 'premier_contact_heures')
      return heures === null ? 'Premier contact hors délai'
        : `Premier contact hors délai (${decimal(heures)} h)`
    },
    tone: 'danger',
    // Attente sur l'horloge du délai : « 27,5 h » sous 48 h, sinon « 4 jours ouvrés ».
    detail: (l) => (l.attend_depuis_heures == null ? ''
      : `attend depuis ${dureeAttente(l.attend_depuis_heures)}`),
  },
]

function LigneException({ liste, ligne, navigate }) {
  const type = ligne.type_etape ? nomType(ligne.type_etape) : ''
  const etiquette = liste.etiquette ? liste.etiquette(ligne) : ''
  const meta = [
    type && type !== ligne.libelle ? type : '',
    liste.detail(ligne),
    liste.reportee && ligne.nb_reports >= 1 ? phraseReportee(ligne.nb_reports) : '',
    ligne.owner_nom ? `Responsable : ${ligne.owner_nom}` : '',
  ].filter(Boolean).join(' · ')
  return (
    <li className="rounded-md border border-border p-2 text-sm" data-testid="controle-exception-ligne">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <LienLead leadId={ligne.lead} nom={ligne.lead_nom} navigate={navigate} />
        {ligne.libelle && <span>{ligne.libelle}</span>}
        {etiquette && <Badge tone="outline" data-testid="controle-ligne-etiquette">{etiquette}</Badge>}
        {ligne.est_tache && liste.cle !== 'taches_en_attente' && <Badge tone="primary">Tâche</Badge>}
      </div>
      {meta && <p className="mt-0.5 text-xs text-muted-foreground">{meta}</p>}
    </li>
  )
}

function BlocException({
  liste, bloc, seuils, ouvert, onBasculer, navigate, aide = null,
}) {
  const id = useId()
  const lignes = bloc.lignes ?? []
  const reste = bloc.total - lignes.length
  return (
    <div data-testid={`controle-exception-${liste.cle}`}>
      <h5 className="text-sm font-semibold">
        <button
          type="button" aria-expanded={ouvert} aria-controls={id} onClick={onBasculer}
          className="focus-ring flex w-full items-center gap-1.5 rounded-md py-1 text-left"
        >
          {ouvert
            ? <ChevronDown className="size-4 shrink-0" aria-hidden="true" />
            : <ChevronRight className="size-4 shrink-0" aria-hidden="true" />}
          <span>{liste.titre(seuils)}</span>
          <Badge tone={liste.tone} data-testid={`controle-total-${liste.cle}`}>{nombre(bloc.total)}</Badge>
        </button>
      </h5>
      {ouvert && (
        <div id={id} className="mt-1 flex flex-col gap-1.5">
          <ul className="flex flex-col gap-1.5">
            {lignes.map((ligne) => (
              <LigneException
                key={`${ligne.etape ?? 'lead'}-${ligne.lead}`}
                liste={liste} ligne={ligne} navigate={navigate}
              />
            ))}
          </ul>
          {aide && (
            <p className="text-xs text-muted-foreground" data-testid={`controle-aide-${liste.cle}`}>{aide}</p>
          )}
          {reste > 0 && (
            <p className="text-xs text-muted-foreground" data-testid={`controle-reste-${liste.cle}`}>
              <Link to="/crm/relances" className="font-medium text-primary-text underline-offset-2 hover:underline">
                et {nombre(reste)} {pl(reste, 'autre', 'autres')}
              </Link>
              {' '}— à retrouver dans le suivi des relances.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function Exceptions({ exceptions, seuils, navigate }) {
  // Ouverture par défaut : ouverte quand il y a des dossiers, masquée à 0 ;
  // un clic de l'utilisateur prend le pas sur ce défaut.
  const [surcharge, setSurcharge] = useState({})
  const estResponsable = useIsAdminOrResponsable()
  const presentes = LISTES.filter((l) => (exceptions?.[l.cle]?.total ?? 0) > 0)
  const note = noteJoursOuvres({
    alerteJours: seuil(seuils, 'retard_alerte_jours'),
    listesRetard: presentes.some((l) => l.cle === 'en_retard' || l.cle === 'taches_en_attente'),
  })
  return (
    <section data-testid="controle-exceptions" className="flex flex-col gap-1.5">
      <h4 className="text-sm font-semibold">À traiter en priorité</h4>
      {presentes.length === 0 ? (
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Forme glyphe="●" className="text-success" />
          Aucune exception
        </p>
      ) : (
        presentes.map((liste) => (
          <BlocException
            key={liste.cle} liste={liste} bloc={exceptions[liste.cle]} seuils={seuils}
            navigate={navigate}
            aide={estResponsable ? (liste.aideResponsable ?? null) : null}
            ouvert={surcharge[liste.cle] ?? true}
            onBasculer={() => setSurcharge((s) => ({ ...s, [liste.cle]: !(s[liste.cle] ?? true) }))}
          />
        ))
      )}
      {/* Les seuils des trois autres listes sont dans leurs titres ; celui de
          l'alerte n'a pas de liste à lui : il se lit ici, avec la règle du retard
          (jours OUVRÉS) dès qu'une liste de retard ou d'attente est affichée. */}
      {note && presentes.length > 0 && (
        <p className="text-xs text-muted-foreground" data-testid="controle-seuils">{note}</p>
      )}
    </section>
  )
}

// ── Détail par type d'étape ────────────────────────────────────────────────
function DetailParEtape({ parType }) {
  const [ouvert, setOuvert] = useState(false)
  const id = useId()
  if (!parType || parType.length === 0) return null
  return (
    <section data-testid="controle-detail">
      <h4 className="text-sm font-semibold">
        <button
          type="button" aria-expanded={ouvert} aria-controls={id} onClick={() => setOuvert((o) => !o)}
          className="focus-ring flex items-center gap-1.5 rounded-md py-1 text-left"
        >
          {ouvert
            ? <ChevronDown className="size-4 shrink-0" aria-hidden="true" />
            : <ChevronRight className="size-4 shrink-0" aria-hidden="true" />}
          Détail par étape
        </button>
      </h4>
      {ouvert && (
        <div id={id} className="mt-1 flex flex-col gap-1.5">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th scope="col" className="py-1 pr-2 font-medium">Étape</th>
                  <th scope="col" className="px-1.5 py-1 text-right font-medium">Dues</th>
                  <th scope="col" className="px-1.5 py-1 text-right font-medium">À temps</th>
                  <th scope="col" className="px-1.5 py-1 text-right font-medium">Traitées en retard</th>
                  <th scope="col" className="px-1.5 py-1 text-right font-medium">Sautées</th>
                  <th scope="col" className="px-1.5 py-1 text-right font-medium">Toujours en retard</th>
                  <th scope="col" className="py-1 pl-1.5 text-right font-medium">Reportées</th>
                </tr>
              </thead>
              {/* Un <tbody> par type : la ligne des chiffres, puis — pleine largeur,
                  pour ne pas écraser le nom sur un téléphone — la ligne des
                  réponses en pastilles. */}
              {parType.map((ligne) => {
                const nom = nomType(ligne.type_etape) || ligne.type_etape
                return (
                  <tbody
                    key={ligne.type_etape} data-testid={`controle-type-${ligne.type_etape}`}
                    className="border-b border-border/50"
                  >
                    <tr className="align-top">
                      <th scope="row" className="pb-1 pr-2 pt-1.5 text-left font-normal">
                        <span className="font-medium">{nom}</span>
                        {ligne.est_tache && <Badge tone="primary" className="ml-1.5">Tâche</Badge>}
                      </th>
                      <td className="px-1.5 pb-1 pt-1.5 text-right tabular-nums">{nombre(ligne.du)}</td>
                      <td className="px-1.5 pb-1 pt-1.5 text-right tabular-nums">{nombre(ligne.a_temps)}</td>
                      <td className="px-1.5 pb-1 pt-1.5 text-right tabular-nums">{nombre(ligne.en_retard)}</td>
                      <td className="px-1.5 pb-1 pt-1.5 text-right tabular-nums">{nombre(ligne.sautees)}</td>
                      <td className="px-1.5 pb-1 pt-1.5 text-right tabular-nums">{nombre(ligne.ouvert)}</td>
                      <td className="pb-1 pl-1.5 pt-1.5 text-right tabular-nums">{nombre(ligne.reportees)}</td>
                    </tr>
                    {ligne.reponses?.length > 0 && (
                      <tr>
                        <td colSpan={7} className="pb-1.5">
                          <ul className="flex flex-wrap gap-1" aria-label={`Réponses — ${nom}`}>
                            {ligne.reponses.map((r) => (
                              <li key={r.cle}>
                                <Badge tone="outline" className="whitespace-nowrap">
                                  {`${libelleReponse(ligne.type_etape, r.cle)} ${nombre(r.n)}`}
                                </Badge>
                              </li>
                            ))}
                          </ul>
                        </td>
                      </tr>
                    )}
                  </tbody>
                )
              })}
            </table>
          </div>
          <p className="text-xs text-muted-foreground">
            Traitées en retard : faites après leur jour ; toujours en retard : pas encore faites alors que leur jour est passé ; reportées : décalées au moins une fois.
          </p>
        </div>
      )}
    </section>
  )
}

// ── Premier contact et résultats ───────────────────────────────────────────
function PremierContactEtResultats({ donnees }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <section className="rounded-lg border border-border p-3" data-testid="controle-premier-contact">
        <h4 className="text-sm font-semibold">Premier contact</h4>
        <p className="mt-1 text-sm text-muted-foreground">{phrasePremierContact(donnees.premier_contact)}</p>
      </section>
      <section className="rounded-lg border border-border p-3" data-testid="controle-resultats">
        <h4 className="text-sm font-semibold">Résultats de la période</h4>
        <p className="mt-1 text-sm text-muted-foreground">{phraseResultats(donnees.resultats)}</p>
      </section>
    </div>
  )
}

/** Le bandeau qui arrive : le verdict et la phrase de la période (même hauteur). */
function Squelette() {
  return (
    <div className="flex flex-col gap-3" aria-busy="true" data-testid="controle-squelette">
      <span className="sr-only" role="status">Chargement du contrôle du suivi…</span>
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  )
}

/** Le détail qui arrive (frise et listes) — seulement quand le détail est déplié. */
function SqueletteDetail() {
  return (
    <div className="flex flex-col gap-3" aria-hidden="true" data-testid="controle-squelette-detail">
      <div className="grid grid-cols-7 gap-1">
        {Array.from({ length: 14 }).map((unused, i) => <Skeleton key={i} className="h-14" />)}
      </div>
      <Skeleton className="h-16 w-full" />
    </div>
  )
}

export default function ControleSuiviPanel() {
  const navigate = useNavigate()
  const [jours, setJours] = useState(PERIODE_DEFAUT)
  // `null` = toute l'équipe ; sinon l'identifiant du commercial servi par le
  // serveur (jamais un nom écrit dans le code).
  const [ownerId, setOwnerId] = useState(null)
  const [tentative, setTentative] = useState(0)
  const [commerciaux, setCommerciaux] = useState([])
  const [resultat, setResultat] = useState({
    cle: null, donnees: null, erreurs: null, panne: false,
  })
  // Replié par défaut ; la préférence du navigateur (`CLE_DETAIL`) la rouvre.
  const [detailOuvert, setDetailOuvert] = useState(lireDetailOuvert)
  const idDetail = useId()

  // Une requête = une CLÉ (période, commercial, tentative) : « en chargement »
  // se DÉDUIT de l'écart entre la clé demandée et celle du dernier résultat,
  // sans setState synchrone dans l'effet.
  const cle = `${jours}|${ownerId ?? ''}|${tentative}`
  useEffect(() => {
    let active = true
    const params = { jours }
    if (ownerId !== null) params.owner = ownerId
    Promise.resolve()
      .then(() => crmApi.getControleSuivi(params))
      .then((r) => {
        if (!active) return
        setResultat({ cle, donnees: r?.data ?? null, erreurs: null, panne: false })
        // La liste des commerciaux survit à un refus : sans elle, le sélecteur
        // fautif disparaîtrait avec son message d'erreur.
        if (Array.isArray(r?.data?.commerciaux)) setCommerciaux(r.data.commerciaux)
      })
      .catch((err) => {
        if (!active) return
        // 400 `{erreurs: {champ: message}}` : le message s'affiche SOUS le
        // sélecteur fautif (règle « l'erreur nomme le champ »).
        const erreurs = err?.response?.status === 400 ? err.response.data?.erreurs : null
        const nomme = erreurs && Object.keys(erreurs).length > 0
        setResultat({
          cle, donnees: null, erreurs: nomme ? erreurs : null, panne: !nomme,
        })
        // Les sélecteurs vivent dans le détail : un refus qui NOMME un champ le
        // déplie pour montrer le message sous ce champ (sans toucher à la préférence
        // mémorisée — c'est une ouverture forcée, pas un choix).
        if (nomme) setDetailOuvert(true)
      })
    return () => { active = false }
  }, [cle, jours, ownerId])

  const chargement = resultat.cle !== cle
  const { donnees, erreurs, panne } = resultat

  const changerPeriode = (v) => { setJours(v) }
  const changerCommercial = (v) => { setOwnerId(v) }
  const basculerDetail = () => {
    const suivant = !detailOuvert
    setDetailOuvert(suivant)
    safeSet(CLE_DETAIL, suivant)
  }
  // Le détail (donc les sélecteurs) peut être replié alors qu'un commercial est
  // choisi : le bandeau ne doit jamais passer pour celui de toute l'équipe.
  const commercialActif = ownerId === null
    ? null
    : (commerciaux.find((c) => c.id === ownerId)?.nom ?? null)

  return (
    <Card data-testid="controle-suivi-panel">
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2">
              <ClipboardCheck className="h-4 w-4" aria-hidden="true" /> Contrôle du suivi
            </CardTitle>
            <CardDescription>
              Ce qui devait être fait l&apos;a-t-il été ? Mêmes chiffres pour tous les rôles.
            </CardDescription>
          </div>
          {commercialActif && (
            <Badge tone="outline" data-testid="controle-commercial-actif">
              Commercial : {commercialActif}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {/* TOUJOURS visibles, détail replié ou non : le bandeau du verdict et la
            phrase de la période (ou leur squelette / l'indisponibilité), puis le
            bouton qui déplie le reste. */}
        {chargement && !donnees ? (
          <Squelette />
        ) : !chargement && panne ? (
          <div className="flex flex-wrap items-center gap-2" data-testid="controle-panne">
            <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
            <Button type="button" size="sm" variant="outline" onClick={() => setTentative((t) => t + 1)}>
              Réessayer
            </Button>
          </div>
        ) : donnees ? (
          <div
            className={cn('transition-opacity', chargement && 'opacity-60')}
            aria-busy={chargement || undefined}
          >
            <Bandeau donnees={donnees} />
          </div>
        ) : null}

        <div>
          <Button
            type="button" size="sm" variant="outline" preventDoubleClick={false}
            aria-expanded={detailOuvert} aria-controls={idDetail} onClick={basculerDetail}
            data-testid="controle-bascule-detail"
          >
            {detailOuvert
              ? <ChevronUp aria-hidden="true" />
              : <ChevronDown aria-hidden="true" />}
            {detailOuvert ? 'Masquer le détail' : 'Voir le détail'}
          </Button>
        </div>

        {detailOuvert && (
          <div id={idDetail} className="flex flex-col gap-4" data-testid="controle-detail-corps">
            <Selecteurs
              jours={jours} onJours={changerPeriode}
              ownerId={ownerId} onOwner={changerCommercial}
              commerciaux={commerciaux} erreurs={chargement ? null : erreurs}
            />
            {donnees ? (
              <div
                className={cn('flex flex-col gap-4 transition-opacity', chargement && 'opacity-60')}
                aria-busy={chargement || undefined}
              >
                <Comparaison verdict={donnees.verdict} />
                {/* La clé suit la DEMANDE (période, commercial), pas la réponse : changer
                    de période ou de commercial referme aussitôt la liste d'un jour,
                    sans attendre le serveur (dont les dates peuvent avoir changé). */}
                <Frise
                  key={`${jours}|${ownerId ?? ''}`}
                  donnees={donnees} ownerId={ownerId} navigate={navigate}
                />
                <Exceptions exceptions={donnees.exceptions} seuils={donnees.seuils} navigate={navigate} />
                <DetailParEtape parType={donnees.par_type} />
                <PremierContactEtResultats donnees={donnees} />
              </div>
            ) : chargement ? (
              <SqueletteDetail />
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
