/* eslint-disable react-refresh/only-export-components --
   `STRATEGIES`, `depuisEntree` et `corpsDeclaration` sont des constantes et des fonctions PURES que le
   test confronte directement (même dérogation que `Raccordement.jsx`). */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber, formatPercent } from '../../../lib/format'
import { Button, Card, Input, Label, Spinner, Stat } from '../../../ui'
import { nombreOuNull, refusParChamp, texteOuNull } from '../electrique/entreeElectrique'
import { BoutonCalculer } from '../production/PanneauProduction'

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

   PAS DE STRATÉGIE PAR DÉFAUT (décision fondateur, D-CALX 7) : la stratégie, les
   packs, le couplage, les seuils et le mode hors réseau se DÉCLARENT dans
   l'entrée électrique du calepinage (ACAL167 : `POST entree-electrique/`
   {batterie, hors_reseau}, relue par `GET entree-electrique/`), lue ensuite
   par la simulation. Rien n'est supposé : un champ laissé vide reste « non
   saisi », le serveur refuse une forme invalide EN NOMMANT le champ, et le
   produit comme les packs prennent par défaut la ligne batterie du devis lié.
   Le geste suivant est de RELANCER la simulation (`POST simuler/`,
   `forcer: true`) — jamais un chiffre calculé côté écran.
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
  plafond_injection: 'Plafond d’injection',
  heures_tarif: 'Heures du tarif',
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

/* ============================================================================
   ACAL167 — DÉCLARER LA BATTERIE ET LE MODE HORS RÉSEAU.
   Les champs se pré-remplissent de l'entrée STOCKÉE (`GET entree-electrique/`) ; le corps
   posté ne porte que `batterie` et `hors_reseau` (la fusion par clé du serveur laisse le
   reste intact). Un champ vidé vaut `null`, jamais 0 ; une clé jamais saisie et absente du
   stock n'est pas inventée.
   ========================================================================== */

export const STRATEGIES = [
  'autoconso', 'peak_shaving', 'backup', 'decalage', 'plafond_injection', 'heures_tarif',
]

const CHAMPS_BATTERIE = [
  { cle: 'packs', libelle: 'Nombre de packs', genre: 'nombre' },
  { cle: 'seuil_effacement_kw', libelle: 'Seuil d’effacement (kW)', genre: 'nombre' },
  { cle: 'reserve_backup_kwh', libelle: 'Réserve de secours (kWh)', genre: 'nombre' },
  { cle: 'heures_charge', libelle: 'Heures de charge (0-23, séparées par des virgules)', genre: 'heures' },
  { cle: 'heures_decharge', libelle: 'Heures de décharge (0-23, séparées par des virgules)', genre: 'heures' },
]

const enTexte = (v) => (v === null || v === undefined ? '' : Array.isArray(v) ? v.join(', ') : String(v))
const estObjet = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)

/** L'entrée stockée → l'état du formulaire (chaînes) ; rien n'est inventé. */
export function depuisEntree(entree) {
  const b = estObjet(entree?.batterie) ? entree.batterie : {}
  const h = estObjet(entree?.hors_reseau) ? entree.hors_reseau : {}
  const etat = { strategie: enTexte(b.strategie), couplage: enTexte(b.couplage), actif: h.actif === true, jours: enTexte(h.jours_autonomie) }
  for (const { cle } of CHAMPS_BATTERIE) etat[cle] = enTexte(b[cle])
  return etat
}

const lireHeures = (texte) => String(texte).split(/[,;]/).map((t) => t.trim()).filter(Boolean).map(Number)

/** Le corps POSTÉ : `{batterie?, hors_reseau?}`, fusionné sur l'existant (clés inconnues conservées). */
export function corpsDeclaration(etat, entree) {
  const stockeB = estObjet(entree?.batterie) ? entree.batterie : null
  const batterie = { ...(stockeB ?? {}) }
  const pose = (cle, valeur) => {
    if (valeur !== null || cle in batterie) batterie[cle] = valeur
  }
  pose('strategie', texteOuNull(etat.strategie))
  pose('couplage', texteOuNull(etat.couplage))
  for (const { cle, genre } of CHAMPS_BATTERIE) {
    pose(cle, genre === 'heures'
      ? (String(etat[cle]).trim() === '' ? null : lireHeures(etat[cle]))
      : nombreOuNull(etat[cle]))
  }
  const stockeH = estObjet(entree?.hors_reseau) ? entree.hors_reseau : null
  const horsReseau = { ...(stockeH ?? {}) }
  const jours = nombreOuNull(etat.jours)
  if (etat.actif || stockeH) horsReseau.actif = Boolean(etat.actif)
  if (jours !== null || 'jours_autonomie' in horsReseau) horsReseau.jours_autonomie = jours
  const corps = {}
  if (stockeB || Object.keys(batterie).length) corps.batterie = batterie
  if (stockeH || Object.keys(horsReseau).length) corps.hors_reseau = horsReseau
  return corps
}

function DeclarationBatterie({ id, onRelancer }) {
  const [entree, setEntree] = useState(null)
  const [etat, setEtat] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [message, setMessage] = useState(null)
  const [enCours, setEnCours] = useState(false)

  const lire = () => Promise.resolve(calepinageApi.calepinages.entreeElectrique(id))
    .then((res) => {
      const lue = res?.data?.entree ?? {}
      setEntree(lue)
      setEtat(depuisEntree(lue))
    })
    .catch(() => { setEntree({}); setEtat(depuisEntree({})) })

  useEffect(() => { lire() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps -- lecture au montage / changement de calepinage

  if (!etat) return null
  const poser = (cle, valeur) => setEtat((s) => ({ ...s, [cle]: valeur }))

  const enregistrer = (relancer) => (evenement) => {
    evenement.preventDefault()
    setEnCours(true)
    setErreurs({})
    setMessage(null)
    calepinageApi.calepinages.enregistrerEntreeElectrique(id, corpsDeclaration(etat, entree))
      .then(() => lire())
      .then(() => {
        setMessage('Déclaration enregistrée.')
        if (relancer) onRelancer?.()
      })
      .catch((err) => {
        const parChamp = refusParChamp(err?.response?.data)
        setErreurs(Object.keys(parChamp).length ? parChamp : { declaration: 'Déclaration non enregistrée : le serveur n’a pas accepté la saisie.' })
      })
      .finally(() => setEnCours(false))
  }

  const erreur = (cle) => erreurs[`batterie.${cle}`]
  const champ = (cle, libelle, valeur, onChange, type = 'text', refus = erreur(cle)) => (
    <div key={cle} className="flex flex-col gap-1">
      <Label htmlFor={`acal167-${cle}`}>{libelle}</Label>
      <Input
        id={`acal167-${cle}`}
        type={type}
        step={type === 'number' ? 'any' : undefined}
        invalid={Boolean(refus)}
        value={valeur}
        onChange={(e) => onChange(e.target.value)}
      />
      {refus ? <p className="text-xs text-destructive" data-testid={`acal167-erreur-${cle}`}>{refus}</p> : null}
    </div>
  )
  const liste = (cle, libelle, valeur, options, refus) => (
    <div key={cle} className="flex flex-col gap-1">
      <Label htmlFor={`acal167-${cle}`}>{libelle}</Label>
      <select
        id={`acal167-${cle}`}
        value={valeur}
        onChange={(e) => poser(cle, e.target.value)}
        aria-invalid={refus ? 'true' : undefined}
        className="w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
      >
        <option value="">— non choisi —</option>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
      {refus ? <p className="text-xs text-destructive" data-testid={`acal167-erreur-${cle}`}>{refus}</p> : null}
    </div>
  )

  return (
    <form
      className="flex flex-col gap-3 border-b border-border/60 pb-4"
      onSubmit={enregistrer(false)}
      data-testid="acal167-declaration"
    >
      <h3 className="text-sm font-semibold">Déclarer la batterie</h3>
      <p className="text-xs text-muted-foreground">
        Aucune stratégie n’est choisie à votre place : sans elle, le bloc batterie est omis et le dit.
        Le produit et le nombre de packs reprennent la ligne batterie du devis lié.
      </p>
      {erreurs.declaration
        ? <p role="alert" className="text-sm text-destructive" data-testid="acal167-bandeau">{erreurs.declaration}</p>
        : null}
      <div className="grid gap-3 sm:grid-cols-2">
        {liste('strategie', 'Stratégie', etat.strategie, STRATEGIES.map((v) => [v, libelleStrategie(v)]), erreur('strategie'))}
        {liste('couplage', 'Couplage', etat.couplage, [['ac', 'AC'], ['dc', 'DC']], erreur('couplage'))}
        {CHAMPS_BATTERIE.map((c) => champ(c.cle, c.libelle, etat[c.cle], (v) => poser(c.cle, v), c.genre === 'nombre' ? 'number' : 'text'))}
      </div>
      <fieldset className="flex flex-col gap-2" data-testid="acal167-hors-reseau">
        <legend className="text-sm font-semibold">Mode hors réseau</legend>
        <label className="flex items-center gap-2 text-sm" htmlFor="acal167-actif">
          <input id="acal167-actif" type="checkbox" checked={etat.actif} onChange={(e) => poser('actif', e.target.checked)} />
          Le site est hors réseau
        </label>
        {champ('jours', 'Jours d’autonomie', etat.jours, (v) => poser('jours', v), 'number', erreurs['hors_reseau.jours_autonomie'])}
      </fieldset>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="sm" disabled={enCours} data-testid="acal167-enregistrer">Enregistrer</Button>
        <Button type="button" size="sm" variant="outline" disabled={enCours} onClick={enregistrer(true)} data-testid="acal167-enregistrer-relancer">
          Enregistrer et relancer la simulation
        </Button>
      </div>
      {message ? <p className="text-xs text-muted-foreground" role="status" data-testid="acal167-message">{message}</p> : null}
    </form>
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

export default function PanneauBatterie({ calepinageId, intervalleMs = 2000 }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error, refetch } = useResource(
    () => calepinageApi.calepinages.resultat(id), id,
    { select: (r) => r.data, errorMessage: 'Batterie indisponible.' },
  )

  // ACAL167 — « Enregistrer et relancer » : le compteur déclenche la relance du bouton partagé.
  const [relance, setRelance] = useState(0)

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
      <DeclarationBatterie id={id} onRelancer={() => setRelance((n) => n + 1)} />
      <BoutonCalculer calepinageId={id} data={data} onTermine={refetch} declenchement={relance} intervalleMs={intervalleMs} />
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
