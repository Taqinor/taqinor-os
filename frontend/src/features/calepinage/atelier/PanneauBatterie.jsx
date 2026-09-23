import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber, formatPercent } from '../../../lib/format'
import { Button, Card, Spinner, Stat } from '../../../ui'

/* ============================================================================
   CALX14 — LE PANNEAU « BATTERIE », ET CE QUE LA CHAÎNE CALCULE DEVIENT ENFIN
   VISIBLE.
   ----------------------------------------------------------------------------
   Constat : `services/batterie.py::simuler_batterie` (dispatch horaire, quatre
   stratégies) et `specs_batterie` n'avaient AUCUN appelant hors la chaîne de
   simulation elle-même (CALX188 écrit `resultat['batterie']`, CALX191
   `resultat['hors_reseau']`) — et rien côté navigateur ne les affichait.
   Parité OpenSolar (dispatch horaire de batterie) et PV*SOL (commande horaire
   réglable) :
   https://support.opensolar.com/hc/en-us/articles/12382460685455
   https://help.valentin-software.com/pvsol/en/pages/battery-system/timed-control/

   AUCUN CALCUL CÔTÉ ÉCRAN. Chaque grandeur affichée est EXACTEMENT celle que
   `GET resultat/` (CALX70) sert sous `batterie`/`hors_reseau` — ce panneau ne
   fait que la mettre en forme.

   TROIS ÉTATS DISTINCTS DU BLOC `batterie` (et, séparément, `hors_reseau`) —
   jamais confondus :
     1. `data.batterie === null` — LA SIMULATION ENTIÈRE n'a jamais tourné ou
        est PÉRIMÉE (CALX70) : le bandeau partagé (non-simulé / périmé) porte
        déjà le motif, ce panneau n'affiche alors aucun chiffre.
     2. `{groupes: [], total: null, motif_absence: "<texte nommé>"}` — la
        simulation A tourné mais CE bloc précis est OMIS (aucune fiche
        batterie déclarée, aucune stratégie choisie, un paramètre de stratégie
        manquant — seuil, réserve, heures de décalage — ou, pour
        `hors_reseau`, un calepinage simplement RACCORDÉ au réseau, cas le
        plus fréquent). Le panneau affiche ALORS le `motif_absence` du
        serveur, textuel, et AUCUN chiffre (Done).
     3. Le bloc porte un `total` (et, pour `hors_reseau`, des grandeurs non
        nulles) : la simulation a produit un résultat, affiché tel quel.

   PAS DE STRATÉGIE PAR DÉFAUT (décision fondateur, D-CALX 7) : la stratégie
   vit sur le DOCUMENT (`roof_layout.battery.strategie`, résolue par
   `services/simulation.py::_declaration_batterie`) — AUCUNE porte HTTP ne
   permet aujourd'hui de l'écrire séparément (elle voyage avec la conception
   complète, `POST …/layout/`, hors du périmètre de ce panneau). Le geste
   RÉELLEMENT actionnable depuis ici est donc de RELANCER la simulation
   (`POST simuler/`, `forcer: true`) — utile après qu'une stratégie a été
   déclarée ailleurs dans l'atelier — jamais un sélecteur qui prétendrait
   changer une stratégie sans le pouvoir vraiment (zéro affordance inventée).
   ========================================================================== */

const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

const STRATEGIE_LABELS = {
  autoconso: 'Autoconsommation',
  peak_shaving: 'Effacement de pointe',
  backup: 'Secours (backup)',
  decalage: 'Décalage horaire',
}

const libelleStrategie = (s) => (s ? (STRATEGIE_LABELS[s] || s) : null)

function nonCalculee(valeur, rendu) {
  return valeur === null || valeur === undefined ? 'non calculée' : rendu(valeur)
}

const kwh = (v) => nonCalculee(v, (x) => `${formatNumber(x, { decimals: 0 })} kWh`)
const heuresFmt = (v) => nonCalculee(v, (x) => `${formatNumber(x, { decimals: 0 })} h`)
const pourcent01 = (v) => nonCalculee(v, (x) => formatPercent(x * 100, { decimals: 1 }))
const pourcentBrut = (v) => nonCalculee(v, (x) => formatPercent(x, { decimals: 1 }))
const libelleMois = (m) => (m === null || m === undefined ? 'non calculé' : (MOIS[m - 1] || String(m)))

/* CALX48 — le même bandeau de péremption : `simulation_perimee` (CALX70)
   remplace tous les blocs par `null`, jamais un chiffre trompeur. */
function BandeauPerime({ motif }) {
  const texte = motif
    || 'Simulation périmée : le document a changé depuis le dernier calcul.'
  return (
    <div
      className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm"
      data-testid="calx14-perime"
      role="status"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
      <span>{texte}</span>
    </div>
  )
}

function BandeauNonSimule({ avertissements }) {
  const raison = avertissements?.[0]
    || 'Calepinage non simulé : aucune valeur de batterie n\'a encore été calculée.'
  return (
    <div
      className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm"
      data-testid="calx14-non-simule"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
      <span>{raison}</span>
    </div>
  )
}

/** Le motif d'un bloc OMIS (`motif_absence` non vide) — SEUL rendu, aucun
    chiffre à côté (Done : « sans fiche batterie… aucun chiffre »). */
function MotifAbsence({ motif, testId }) {
  return (
    <p
      className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-sm text-muted-foreground"
      data-testid={testId}
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span>{motif}</span>
    </p>
  )
}

const JOB_EN_ATTENTE = new Set(['PENDING', 'STARTED', 'RETRY'])

/**
 * CALX14 — relance la simulation (`POST simuler/`, `forcer: true`) et suit le
 * travail de fond par `moteur/resultat/<job_id>/` (même patron que
 * `RemplissageProuve.jsx`, CAL79, et `PanneauProduction.jsx`, CALX48— repris
 * ici plutôt qu'importé : ce panneau reste dans SON fichier, D-CALX 13).
 * AUCUN calcul n'est refait côté navigateur.
 */
function BoutonRelancerSimulation({ calepinageId, onTermine }) {
  const [enCours, setEnCours] = useState(false)
  const [job, setJob] = useState(null)
  const [refus, setRefus] = useState(null)
  const minuterie = useRef(null)

  useEffect(() => () => {
    if (minuterie.current) clearTimeout(minuterie.current)
  }, [])

  const suivre = (jobId) => {
    Promise.resolve(calepinageApi.moteur.resultat(jobId))
      .then((res) => {
        const suivi = res?.data ?? null
        setJob(suivi)
        if (JOB_EN_ATTENTE.has(String(suivi?.statut || '').toUpperCase())) {
          minuterie.current = setTimeout(() => suivre(jobId), 2000)
          return
        }
        setEnCours(false)
        if (suivi?.resultat) {
          onTermine?.()
        } else {
          setRefus(suivi?.message_erreur || 'La simulation a échoué.')
        }
      })
      .catch(() => {
        setEnCours(false)
        setRefus('Le suivi du calcul de fond a été interrompu.')
      })
  }

  const relancer = () => {
    if (!calepinageId) return
    setRefus(null)
    setEnCours(true)
    Promise.resolve(calepinageApi.calepinages.simuler(calepinageId, { forcer: true }))
      .then((res) => {
        const donnees = res?.data ?? null
        if (donnees?.job_id) {
          setJob(donnees)
          suivre(donnees.job_id)
          return
        }
        setEnCours(false)
        onTermine?.()
      })
      .catch((e) => {
        setEnCours(false)
        const corps = e?.response?.data
        let motif = null
        if (corps && typeof corps === 'object') {
          const valeur = Object.values(corps)[0]
          motif = Array.isArray(valeur) ? valeur[0] : valeur
        }
        setRefus((typeof motif === 'string' && motif) || 'Relance refusée par le serveur.')
      })
  }

  return (
    <div className="flex flex-col gap-2" data-testid="calx14-relancer">
      <Button
        type="button"
        size="sm"
        onClick={relancer}
        disabled={enCours || !calepinageId}
        data-testid="calx14-relancer-bouton"
        className="w-fit"
      >
        {enCours ? 'Relance en cours…' : 'Relancer la simulation (stratégie actuelle)'}
      </Button>
      {enCours && job?.job_id && (
        <p className="text-xs text-muted-foreground" role="status" data-testid="calx14-avancement">
          Calcul de fond n°{job.job_id} —{' '}
          {job.progress_pct === null || job.progress_pct === undefined
            ? 'avancement non publié'
            : `${job.progress_pct} %`}
        </p>
      )}
      {refus && (
        <p className="text-sm text-destructive" role="alert" data-testid="calx14-refus">
          {refus}
        </p>
      )}
    </div>
  )
}

function LigneGroupe({ groupe }) {
  return (
    <tr className="border-t border-border/60" data-testid="calx14-groupe">
      <td className="py-1">{groupe.groupe}</td>
      <td className="py-1 text-right tabular-nums">{formatNumber(groupe.packs, { decimals: 0 })}</td>
      <td className="py-1 text-right tabular-nums">{kwh(groupe.capacite_utile_kwh)}</td>
      <td className="py-1">{libelleStrategie(groupe.strategie) || 'non calculée'}</td>
      <td className="py-1 text-right tabular-nums">{kwh(groupe.energie_restituee_kwh)}</td>
      <td className="py-1 text-right tabular-nums">
        {nonCalculee(groupe.profondeur_decharge_pct, (x) => `${formatNumber(x, { decimals: 0 })} %`)}
      </td>
    </tr>
  )
}

function BlocBatterie({ batterie }) {
  if (!batterie || batterie.motif_absence) {
    return (
      <MotifAbsence
        testId="calx14-batterie-motif"
        motif={batterie?.motif_absence
          || 'Aucune batterie déclarée sur ce calepinage : le bloc « batterie » '
            + 'est omis.'}
      />
    )
  }
  const { groupes = [], total } = batterie
  return (
    <div className="flex flex-col gap-3" data-testid="calx14-batterie">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="calx14-batterie-total">
        <Stat label="Stratégie retenue" value={libelleStrategie(total?.strategie) || 'non calculée'} />
        <Stat label="Capacité utile" value={kwh(total?.capacite_utile_kwh)} />
        <Stat label="Énergie stockée" value={kwh(total?.energie_stockee_kwh)} />
        <Stat label="Énergie restituée" value={kwh(total?.energie_restituee_kwh)} />
        <Stat label="Taux d'autonomie" value={pourcent01(total?.taux_autonomie)} />
        <Stat label="Heures sans import réseau" value={heuresFmt(total?.heures_sans_import)} />
      </div>
      {total?.definition && (
        <p className="text-xs text-muted-foreground" data-testid="calx14-batterie-definition">
          {total.definition}
        </p>
      )}
      {total?.energie && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="calx14-batterie-energie">
          <Stat label="Production" value={kwh(total.energie.production_kwh)} />
          <Stat label="Consommation" value={kwh(total.energie.consommation_kwh)} />
          <Stat label="Autoconsommée" value={kwh(total.energie.autoconsomme_kwh)} />
          <Stat label="Exportée" value={kwh(total.energie.export_kwh)} />
          <Stat label="Importée du réseau" value={kwh(total.energie.import_reseau_kwh)} />
          <Stat label="Pertes de la batterie" value={kwh(total.energie.pertes_batterie_kwh)} />
        </div>
      )}
      {groupes.length > 0 && (
        <table className="w-full text-sm" data-testid="calx14-groupes">
          <thead>
            <tr className="text-left text-xs text-muted-foreground">
              <th className="py-1 font-normal">Groupe</th>
              <th className="py-1 text-right font-normal">Packs</th>
              <th className="py-1 text-right font-normal">Capacité utile</th>
              <th className="py-1 font-normal">Stratégie</th>
              <th className="py-1 text-right font-normal">Énergie restituée</th>
              <th className="py-1 text-right font-normal">DoD</th>
            </tr>
          </thead>
          <tbody>
            {groupes.map((groupe) => <LigneGroupe key={groupe.groupe} groupe={groupe} />)}
          </tbody>
        </table>
      )}
      {batterie.avertissements?.length > 0 && (
        <ul className="list-disc pl-5 text-xs text-muted-foreground" data-testid="calx14-batterie-avertissements">
          {batterie.avertissements.map((a) => <li key={a}>{a}</li>)}
        </ul>
      )}
    </div>
  )
}

/* ============================================================================
   CALX271 — « COMPARER DES CAPACITÉS DU STOCK », SANS AUCUN PRIX.
   ----------------------------------------------------------------------------
   La chaîne de simulation compare les batteries du STOCK de la société (leurs
   fiches, jamais une capacité inventée) sur la série réelle et publie, pour
   chacune des trois motivations d'OpenSolar (Battery Design Assistant), une
   liste ORDONNÉE avec son critère écrit en toutes lettres
   (`resultat.batterie.capacites_candidates`, contrat
   `calepinage_simulation.json`). Ce bloc ne fait que l'AFFICHER : aucun
   classement n'est refait ici, aucun montant n'y transite, et aucune
   capacité n'est « recommandée » — la liste et son critère, rien de plus.
   Sans capacité au stock, le bouton est INACTIF et le motif du serveur est
   lu à côté. */
const MOTIF_SANS_COMPARAISON = 'La simulation enregistrée ne compare pas encore '
  + 'les capacités du stock : relancez la simulation pour obtenir la comparaison.'

const LIBELLES_INDICATEUR = {
  taux_autoconsommation: 'Taux d’autoconsommation',
  taux_couverture: 'Taux de couverture',
  pointe_apres_kw: 'Pointe après effacement',
}

function valeurIndicateur(indicateur, valeur) {
  if (valeur === null || valeur === undefined) return 'non calculée'
  if (indicateur === 'pointe_apres_kw') return `${formatNumber(valeur, { decimals: 1 })} kW`
  return formatPercent(valeur * 100, { decimals: 1 })
}

function ListeCandidates({ liste }) {
  if (!liste) return null
  if (liste.motif_absence) {
    return <MotifAbsence testId="calx271-motivation-motif" motif={liste.motif_absence} />
  }
  const entete = LIBELLES_INDICATEUR[liste.indicateur] || liste.indicateur
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground" data-testid="calx271-critere">
        <span className="font-medium">Critère : </span>
        {liste.critere}
      </p>
      <table className="w-full text-sm" data-testid="calx271-candidates">
        <thead>
          <tr className="text-left text-xs text-muted-foreground">
            <th className="py-1 font-normal">Rang</th>
            <th className="py-1 font-normal">Batterie du stock</th>
            <th className="py-1 text-right font-normal">Capacité utile</th>
            <th className="py-1 text-right font-normal">{entete}</th>
          </tr>
        </thead>
        <tbody>
          {(liste.candidates || []).map((ligne) => (
            <tr key={`${ligne.rang}-${ligne.libelle}`} className="border-t border-border/60" data-testid="calx271-candidate">
              <td className="py-1 tabular-nums">{ligne.rang}</td>
              <td className="py-1">
                {ligne.libelle}
                {ligne.motif_absence && (
                  <span className="block text-xs text-muted-foreground">{ligne.motif_absence}</span>
                )}
              </td>
              <td className="py-1 text-right tabular-nums">{kwh(ligne.capacite_utile_kwh)}</td>
              <td className="py-1 text-right tabular-nums">{valeurIndicateur(liste.indicateur, ligne.valeur)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {liste.avertissements?.length > 0 && (
        <ul className="list-disc pl-5 text-xs text-muted-foreground" data-testid="calx271-avertissements">
          {liste.avertissements.map((a) => <li key={a}>{a}</li>)}
        </ul>
      )}
    </div>
  )
}

function ComparateurCapacites({ bloc }) {
  const [ouvert, setOuvert] = useState(false)
  const [choix, setChoix] = useState(null)

  const parMotivation = bloc?.par_motivation || null
  const motivations = parMotivation ? Object.keys(parMotivation) : []
  const actif = Boolean(parMotivation) && motivations.length > 0
    && (bloc?.capacites_stock?.length ?? 0) > 0 && !bloc?.motif_absence
  const declaree = bloc?.motivation_declaree && parMotivation?.[bloc.motivation_declaree]
    ? bloc.motivation_declaree : null
  const motivation = choix || declaree || motivations[0]

  return (
    <div className="flex flex-col gap-2 border-t border-border/60 pt-3" data-testid="calx271-comparateur">
      <Button
        type="button"
        size="sm"
        className="w-fit"
        disabled={!actif}
        aria-expanded={actif && ouvert}
        onClick={() => setOuvert((valeur) => !valeur)}
        data-testid="calx271-comparer"
      >
        Comparer des capacités du stock
      </Button>
      {!actif && (
        <p className="text-sm text-muted-foreground" data-testid="calx271-motif">
          {bloc?.motif_absence || MOTIF_SANS_COMPARAISON}
        </p>
      )}
      {actif && ouvert && (
        <div className="flex flex-col gap-2" data-testid="calx271-liste">
          {declaree && (
            <p className="text-xs text-muted-foreground" data-testid="calx271-motivation-declaree">
              Motivation déclarée par le client : {parMotivation[declaree].libelle}
            </p>
          )}
          <div className="flex flex-wrap gap-2" role="group" aria-label="Motivation du client">
            {motivations.map((nom) => (
              <Button
                key={nom}
                type="button"
                size="sm"
                variant={nom === motivation ? 'default' : 'outline'}
                aria-pressed={nom === motivation}
                onClick={() => setChoix(nom)}
                data-testid={`calx271-motivation-${nom}`}
              >
                {parMotivation[nom].libelle || nom}
              </Button>
            ))}
          </div>
          <ListeCandidates liste={parMotivation[motivation]} />
        </div>
      )}
    </div>
  )
}

function TableauParMois({ parMois }) {
  if (!parMois?.length) return null
  return (
    <table className="w-full text-sm" data-testid="calx14-hors-reseau-par-mois">
      <thead>
        <tr className="text-left text-xs text-muted-foreground">
          <th className="py-1 font-normal">Mois</th>
          <th className="py-1 text-right font-normal">Défaillance</th>
          <th className="py-1 text-right font-normal">Heures défaillantes</th>
        </tr>
      </thead>
      <tbody>
        {parMois.map((point) => (
          <tr key={point.mois} className="border-t border-border/60">
            <td className="py-1">{libelleMois(point.mois)}</td>
            <td className="py-1 text-right tabular-nums">{kwh(point.defaillance_kwh)}</td>
            <td className="py-1 text-right tabular-nums">{heuresFmt(point.heures_defaillantes)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function BlocHorsReseau({ horsReseau }) {
  if (!horsReseau || horsReseau.motif_absence) {
    return (
      <MotifAbsence
        testId="calx14-hors-reseau-motif"
        motif={horsReseau?.motif_absence
          || 'Ce calepinage est raccordé au réseau : le hors-réseau ne '
            + 's’applique pas.'}
      />
    )
  }
  return (
    <div className="flex flex-col gap-3" data-testid="calx14-hors-reseau">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="calx14-hors-reseau-total">
        <Stat label="Défaillance annuelle" value={kwh(horsReseau.defaillance_kwh)} />
        <Stat label="Heures défaillantes" value={heuresFmt(horsReseau.heures_defaillantes)} />
        <Stat label="Taux de défaillance" value={pourcent01(horsReseau.taux_defaillance)} />
        <Stat label="Pire mois" value={libelleMois(horsReseau.mois_le_plus_defavorable)} />
        <Stat label="Servi" value={kwh(horsReseau.servi_kwh)} />
        <Stat label="Surplus perdu" value={kwh(horsReseau.surplus_perdu_kwh)} />
      </div>
      {horsReseau.banque && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="calx14-hors-reseau-banque">
          <Stat label="Capacité utile" value={kwh(horsReseau.banque.capacite_utile_kwh)} />
          <Stat label="Capacité nominale" value={kwh(horsReseau.banque.capacite_nominale_kwh)} />
          <Stat label="Jours d'autonomie" value={nonCalculee(horsReseau.banque.jours_autonomie,
            (x) => `${formatNumber(x, { decimals: 0 })} j`)}
          />
          <Stat label="Profondeur de décharge (fiche)" value={pourcentBrut(horsReseau.banque.dod_pct)} />
        </div>
      )}
      {horsReseau.quantiles_publiables === false && horsReseau.motif_quantiles && (
        <p className="text-xs text-muted-foreground" data-testid="calx14-hors-reseau-quantiles">
          {horsReseau.motif_quantiles}
        </p>
      )}
      <TableauParMois parMois={horsReseau.par_mois} />
      {horsReseau.mentions?.length > 0 && (
        <ul className="list-disc pl-5 text-xs text-muted-foreground" data-testid="calx14-hors-reseau-mentions">
          {horsReseau.mentions.map((m) => <li key={m}>{m}</li>)}
        </ul>
      )}
    </div>
  )
}

export default function PanneauBatterie({ calepinageId }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error, refetch } = useResource(
    () => calepinageApi.calepinages.resultat(id), id,
    { select: (r) => r.data, errorMessage: 'Batterie indisponible.' },
  )

  if (loading) return <Spinner />
  if (error) {
    return <p className="text-sm text-destructive" data-testid="calx14-erreur">{error}</p>
  }

  const perime = data?.simulation_perimee === true

  return (
    <Card className="flex flex-col gap-4 p-4" data-testid="calx14-panneau">
      <h2 className="text-base font-semibold">Batterie</h2>
      {perime
        ? <BandeauPerime motif={data?.motif} />
        : (!data?.simule && <BandeauNonSimule avertissements={data?.avertissements} />)}
      {!data?.simule && (
        <BoutonRelancerSimulation calepinageId={id} onTermine={refetch} />
      )}
      {!perime && data?.simule && (
        <>
          <BlocBatterie batterie={data?.batterie} />
          <ComparateurCapacites bloc={data?.batterie?.capacites_candidates} />
          <div className="border-t border-border/60 pt-3">
            <h3 className="mb-2 text-sm font-semibold">Hors réseau</h3>
            <BlocHorsReseau horsReseau={data?.hors_reseau} />
          </div>
        </>
      )}
    </Card>
  )
}
