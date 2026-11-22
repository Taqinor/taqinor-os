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

export default function SecoursBatterie({
  appareils, duree, erreurs = {}, reserve = null, onAppareils, onDuree,
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
        <div key={rang} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5" data-testid="acal788-appareil">
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
    </fieldset>
  )
}
