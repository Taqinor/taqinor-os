import { Button, Input, Label } from '../../../ui'
import { formatNumber } from '../../../lib/format'

/* ============================================================================
   ACAL788 — LES APPAREILS À TENIR PENDANT UNE COUPURE, ET LA DURÉE À TENIR.
   Visible seulement en stratégie « Secours ». Rien n'est prérempli : une ligne
   vide se remplit à la main. La réserve affichée est CELLE QUE LE SERVEUR A
   DÉDUITE (`batterie.total.reserve_secours`) — aucun calcul d'écran. Un refus
   du serveur se lit sous son champ (`batterie.appareils[i].<champ>`,
   `batterie.duree_secours_h`, `batterie.appareils`).
   ========================================================================== */

const APPAREIL_VIDE = {
  nom: '', puissance_continue_kw: '', puissance_pointe_kw: '', quantite: '',
}

const CHAMPS = [
  { cle: 'nom', libelle: 'Appareil', type: 'text' },
  { cle: 'puissance_continue_kw', libelle: 'Puissance en marche (kW)', type: 'number' },
  { cle: 'puissance_pointe_kw', libelle: 'Puissance au démarrage (kW)', type: 'number' },
  { cle: 'quantite', libelle: 'Quantité', type: 'number' },
]

export function Champ({ id, libelle, type, valeur, refus, onChange }) {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id}>{libelle}</Label>
      <Input
        id={id}
        type={type}
        step={type === 'number' ? 'any' : undefined}
        invalid={Boolean(refus)}
        className="min-h-11"
        value={valeur}
        onChange={(e) => onChange(e.target.value)}
      />
      {refus ? <p className="text-xs text-destructive" data-testid={`${id}-erreur`}>{refus}</p> : null}
    </div>
  )
}

function ReserveDeduite({ reserve, appareils }) {
  if (!appareils.length) return null
  if (!reserve || typeof reserve !== 'object') {
    return (
      <p className="text-sm text-muted-foreground" data-testid="acal788-reserve">
        Réserve déduite : non calculée. Enregistrez puis relancez la simulation.
      </p>
    )
  }
  return (
    <p className="text-sm" data-testid="acal788-reserve">
      Réserve déduite : {formatNumber(reserve.energie_kwh)} kWh pour{' '}
      {reserve.detail?.length ?? appareils.length} appareils pendant {formatNumber(reserve.duree_h)} h
    </p>
  )
}

/* ACAL799 — les coupures (mode expert) : trois nombres jamais préremplis, postés
   sous `batterie.coupures` ; l'énergie non fournie et les heures tenues sont LUES
   de `batterie.total.secours` (ACAL797-798) — `null` ⇒ « non calculé » + motif. */
const QUESTIONS_COUPURES = [
  { cle: 'nombre_par_an', libelle: 'Combien de coupures par an ?' },
  { cle: 'duree_h', libelle: 'De combien d’heures ?' },
  { cle: 'heure_debut', libelle: 'Vers quelle heure commencent-elles ? (0-23)' },
]

function LectureSecours({ secours }) {
  const c = secours?.coupures
  return (
    <div className="flex flex-col gap-1 text-sm">
      <p data-testid="acal799-energie">
        {c
          ? `Énergie non fournie attendue : ${formatNumber(c.energie_non_fournie_kwh)} kWh par an `
            + `(la pire coupure : ${formatNumber(c.energie_non_fournie_par_coupure_pire_kwh)} kWh)`
          : `Énergie non fournie attendue : non calculé : ${secours?.motif_coupures || 'relancez la simulation.'}`}
      </p>
      {Array.isArray(secours?.appareils)
        ? secours.appareils.map((a) => (
          <p key={a.nom} data-testid="acal799-appareil">
            {a.nom} : {a.heures_tenues === null || a.heures_tenues === undefined
              ? 'non calculé' : `tient ${formatNumber(a.heures_tenues)} h`}
          </p>
        ))
        : (
          <p className="text-muted-foreground" data-testid="acal799-appareils-motif">
            Heures tenues : non calculé : {secours?.motif_appareils || 'relancez la simulation.'}
          </p>
        )}
    </div>
  )
}

function Coupures({ coupures, erreurs, secours, onCoupures }) {
  return (
    <fieldset className="flex flex-col gap-3 border-t border-border/60 pt-3" data-testid="acal799-coupures">
      <legend className="text-sm font-semibold">Coupures</legend>
      <div className="grid grid-cols-1 gap-3">
        {QUESTIONS_COUPURES.map(({ cle, libelle }) => (
          <Champ key={cle} id={`acal799-${cle}`} libelle={libelle} type="number"
            valeur={coupures?.[cle] ?? ''} refus={erreurs[`batterie.coupures.${cle}`]}
            onChange={(v) => onCoupures({ ...coupures, [cle]: v })} />
        ))}
      </div>
      <LectureSecours secours={secours} />
    </fieldset>
  )
}

export default function SecoursBatterie({
  appareils, duree, erreurs = {}, reserve = null, onAppareils, onDuree,
  expert = false, coupures = null, secours = null, onCoupures = null,
}) {
  const modifier = (rang, cle, valeur) => onAppareils(
    appareils.map((ligne, i) => (i === rang ? { ...ligne, [cle]: valeur } : ligne)))
  return (
    <fieldset className="flex flex-col gap-3" data-testid="acal788-secours">
      <legend className="text-sm font-semibold">Appareils à tenir pendant une coupure</legend>
      <p className="text-xs text-muted-foreground">
        Listez les appareils que la batterie doit alimenter. La réserve de secours est alors déduite
        de leur puissance et de la durée de coupure : elle remplace la réserve saisie en bloc.
      </p>
      {erreurs['batterie.appareils']
        ? <p role="alert" className="text-xs text-destructive" data-testid="acal788-erreur-appareils">{erreurs['batterie.appareils']}</p>
        : null}
      {appareils.map((ligne, rang) => (
        <div key={rang} className="grid grid-cols-1 gap-3" data-testid="acal788-appareil">
          {CHAMPS.map(({ cle, libelle, type }) => (
            <Champ
              key={cle}
              id={`acal788-${rang}-${cle}`}
              libelle={libelle}
              type={type}
              valeur={ligne[cle]}
              refus={erreurs[`batterie.appareils[${rang}].${cle}`]}
              onChange={(v) => modifier(rang, cle, v)}
            />
          ))}
          <div className="flex items-end">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="min-h-11"
              onClick={() => onAppareils(appareils.filter((_, i) => i !== rang))}
              data-testid="acal788-retirer"
            >
              Retirer
            </Button>
          </div>
        </div>
      ))}
      <Button
        className="min-h-11 w-fit"
        variant="outline"
        size="sm"
        type="button"
        onClick={() => onAppareils([...appareils, { ...APPAREIL_VIDE }])}
        data-testid="acal788-ajouter"
      >
        Ajouter un appareil
      </Button>
      <Champ
        id="acal788-duree"
        libelle="Durée de coupure à tenir (heures)"
        type="number"
        valeur={duree}
        refus={erreurs['batterie.duree_secours_h']}
        onChange={onDuree}
      />
      <ReserveDeduite reserve={reserve} appareils={appareils} />
      {expert && onCoupures && (
        <Coupures coupures={coupures} erreurs={erreurs} secours={secours} onCoupures={onCoupures} />
      )}
    </fieldset>
  )
}
