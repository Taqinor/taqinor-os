import { Button } from '../../../ui'
import { Champ } from './SecoursBatterie'

/* ============================================================================
   ACAL792 — RÉGLAGES PROPRES À LA STRATÉGIE (mode expert).
   « Décalage horaire » : fenêtres de charge et de décharge « de H1 h à H2 h »
   (début inclus, fin exclue) avec un état de charge visé facultatif, 3 par
   sorte au plus (`services/batterie.py::FENETRES_MAX`). « Effacement de
   pointe » : part et plafond effaçables, vides = aucune borne. Rien n'est
   prérempli. Le recouvrement est jugé par le serveur et lu sous la fenêtre
   fautive : aucune copie de la règle ici.
   ========================================================================== */

const FENETRES_MAX = 3
const SORTES = [
  { sorte: 'charge', libelle: 'Fenêtres de charge' },
  { sorte: 'decharge', libelle: 'Fenêtres de décharge' },
]

const FENETRE_VIDE = { debut: '', fin: '', soc: '', brut: null }

/** Le refus du serveur sous une fenêtre : toute clé `batterie.fenetres.<sorte>[<rang>]…`. */
function refusDeFenetre(erreurs, sorte, rang) {
  const prefixe = `batterie.fenetres.${sorte}[${rang}]`
  return Object.entries(erreurs).filter(([cle]) => cle.startsWith(prefixe)).map(([, m]) => m).join(' ')
}

function FenetreLigne({ sorte, rang, fenetre, refus, onChange, onRetirer }) {
  const id = `acal792-${sorte}-${rang}`
  const modifier = (cle, valeur) => onChange({ ...fenetre, [cle]: valeur })
  return (
    <div className="flex flex-col gap-1" data-testid={`acal792-fenetre-${sorte}`}>
      <div className="grid grid-cols-1 items-end gap-3">
        {fenetre.brut
          ? <p className="text-sm">Heures enregistrées : {fenetre.brut.join(', ')}</p>
          : (
            <>
              <Champ id={`${id}-debut`} libelle="De (heure, 0 à 23)" type="number" valeur={fenetre.debut}
                onChange={(v) => modifier('debut', v)} />
              <Champ id={`${id}-fin`} libelle="À (heure exclue, 1 à 24)" type="number" valeur={fenetre.fin}
                onChange={(v) => modifier('fin', v)} />
            </>
          )}
        <Champ id={`${id}-soc`} libelle="Jusqu’à (% de charge visé)" type="number" valeur={fenetre.soc}
          onChange={(v) => modifier('soc', v)} />
        <Button type="button" size="sm" variant="outline" className="min-h-11" onClick={onRetirer}
          data-testid={`acal792-retirer-${sorte}`}>
          Retirer
        </Button>
      </div>
      {refus ? <p role="alert" className="text-xs text-destructive" data-testid={`${id}-erreur`}>{refus}</p> : null}
    </div>
  )
}

export function FenetresBatterie({ fenetres, erreurs = {}, onChange }) {
  const remplacer = (sorte, liste) => onChange({ ...fenetres, [sorte]: liste })
  return (
    <fieldset className="flex flex-col gap-3" data-testid="acal792-fenetres">
      <legend className="text-sm font-semibold">Fenêtres de charge et de décharge</legend>
      <p className="text-xs text-muted-foreground">
        Par exemple « charger de 10 h à 14 h jusqu’à 80 % ». Le début est inclus, la fin est exclue.
        Si vous posez des fenêtres, les deux listes d’heures ci-dessus ne sont plus envoyées.
      </p>
      {erreurs['batterie.fenetres'] ? <p role="alert" className="text-xs text-destructive">{erreurs['batterie.fenetres']}</p> : null}
      {SORTES.map(({ sorte, libelle }) => (
        <div key={sorte} className="flex flex-col gap-2">
          <p className="text-sm">{libelle}</p>
          {erreurs[`batterie.fenetres.${sorte}`]
            ? <p role="alert" className="text-xs text-destructive">{erreurs[`batterie.fenetres.${sorte}`]}</p> : null}
          {fenetres[sorte].map((fenetre, rang) => (
            <FenetreLigne
              key={`${sorte}-${rang}`}
              sorte={sorte}
              rang={rang}
              fenetre={fenetre}
              refus={refusDeFenetre(erreurs, sorte, rang)}
              onChange={(f) => remplacer(sorte, fenetres[sorte].map((x, i) => (i === rang ? f : x)))}
              onRetirer={() => remplacer(sorte, fenetres[sorte].filter((_, i) => i !== rang))}
            />
          ))}
          <Button type="button" size="sm" variant="outline" className="min-h-11 w-fit"
            disabled={fenetres[sorte].length >= FENETRES_MAX}
            onClick={() => remplacer(sorte, [...fenetres[sorte], { ...FENETRE_VIDE }])}
            data-testid={`acal792-ajouter-${sorte}`}>
            Ajouter une fenêtre
          </Button>
        </div>
      ))}
    </fieldset>
  )
}

export function ReglagesPointe({ part, plafond, erreurs = {}, onPart, onPlafond }) {
  return (
    <fieldset className="grid grid-cols-1 gap-3" data-testid="acal792-pointe">
      <legend className="text-sm font-semibold">Part effaçable</legend>
      <Champ id="acal792-part" libelle="Part de la consommation qu’on accepte d’effacer (%)" type="number"
        valeur={part} refus={erreurs['batterie.part_effacable_pct']} onChange={onPart} />
      <Champ id="acal792-plafond" libelle="Puissance effaçable maximale (kW)" type="number"
        valeur={plafond} refus={erreurs['batterie.plafond_effacable_kw']} onChange={onPlafond} />
      <p className="text-xs text-muted-foreground">Vide = aucune borne.</p>
    </fieldset>
  )
}
