import { useState } from 'react'
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger, Badge, Button, Input, Label,
} from '../../../ui'

/* ============================================================================
   AOF97 — Tiroir « Rives & dégagements ».
   ----------------------------------------------------------------------------
   Rives latérales, rives d'extrémité, dégagement standard et dégagement de
   « nature inconnue » (l'obstacle qu'on n'a pas pu identifier sur le relevé :
   il coûte plus large, et il faut que ça se voie).

   Deux disciplines héritées d'écrans qui ont déjà saigné :
   1. **Aucun champ ne rejette ni n'arrondit une saisie légitime** (même règle
      que l'écran devis : `noValidate`, `step="any"`). Les bornes du CPS sont
      affichées comme un AVERTISSEMENT français, jamais comme un blocage — un
      champ qui « corrige » silencieusement une saisie fait douter de tout le
      reste du dossier.
   2. **L'impact chiffré s'affiche AVANT l'application** et vient du moteur
      (passe de sensibilité) : si une valeur saisie n'a pas été chiffrée par
      le moteur, on l'écrit — on n'estime pas (garde de code AOF94).

   La variante conservatrice historique (1,50 / 0,50 / 0,50) est proposée en
   un clic comme COMPARAISON D'INFORMATION, avec l'écart renvoyé par le
   moteur ; ce n'est pas un défaut recommandé.

   ── Contrat de charge utile ───────────────────────────────────────────────
   donnees = {
     champs: [{ code, libelle, unite?, min?, max?, message_borne?,
                impacts?: [{ valeur, texte_valeur, impact_texte, sens? }] }],
     variante_conservatrice?: { libelle, valeurs: {code: valeur}, comparaison_texte? },
   }
   valeurs = { <code>: valeur, … }
   ========================================================================== */

const TONS_IMPACT = { gain: 'success', perte: 'danger', neutre: 'neutral' }

export default function TiroirRives({ donnees, valeurs = {}, onChange }) {
  // Surcharges LOCALES de saisie : elles n'existent que le temps de la frappe
  // (« 1, » n'est pas encore un nombre) et sont effacées dès qu'une action
  // explicite repose les valeurs.
  const [saisies, setSaisies] = useState({})

  if (!donnees) return null

  const champs = donnees.champs || []
  const variante = donnees.variante_conservatrice

  const affichee = (code) => (saisies[code] !== undefined ? saisies[code] : (valeurs[code] ?? ''))

  const onSaisie = (code) => (event) => {
    const brut = event.target.value
    setSaisies((courantes) => ({ ...courantes, [code]: brut }))
    const nombre = Number.parseFloat(brut)
    if (Number.isFinite(nombre)) onChange?.({ [code]: nombre })
  }

  const appliquerVariante = () => {
    setSaisies({})
    onChange?.({ ...variante.valeurs })
  }

  const horsBornes = (champ, brut) => {
    const nombre = Number.parseFloat(brut)
    if (!Number.isFinite(nombre)) return false
    if (Number.isFinite(champ.min) && nombre < champ.min) return true
    return Number.isFinite(champ.max) && nombre > champ.max
  }

  const impactDe = (champ, brut) => {
    const nombre = Number.parseFloat(brut)
    if (!Number.isFinite(nombre)) return null
    return (champ.impacts || []).find((impact) => impact.valeur === nombre) || null
  }

  return (
    <Accordion type="single" collapsible defaultValue="rives" data-ao-tiroir="rives">
      <AccordionItem value="rives">
        <AccordionTrigger>Rives &amp; dégagements</AccordionTrigger>
        <AccordionContent className="flex flex-col gap-4 text-foreground">
          <form noValidate className="flex flex-col gap-4" onSubmit={(e) => e.preventDefault()}>
            {champs.map((champ) => {
              const brut = affichee(champ.code)
              const impact = impactDe(champ, brut)
              const deborde = horsBornes(champ, brut)
              return (
                <div key={champ.code} className="flex flex-col gap-1" data-champ={champ.code}>
                  <Label htmlFor={`ao-rive-${champ.code}`}>
                    {champ.libelle}{champ.unite ? ` (${champ.unite})` : ''}
                  </Label>
                  <Input
                    id={`ao-rive-${champ.code}`}
                    type="number"
                    step="any"
                    inputMode="decimal"
                    value={brut}
                    onChange={onSaisie(champ.code)}
                  />
                  {/* Borne = avertissement, JAMAIS un rejet ni un arrondi. */}
                  {deborde && champ.message_borne && (
                    <p className="text-xs text-warning" role="status" data-borne="avertissement">
                      {champ.message_borne}
                    </p>
                  )}
                  {impact ? (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground" data-impact={champ.code}>
                      Impact prévu :
                      <Badge tone={TONS_IMPACT[impact.sens] || 'neutral'}>{impact.impact_texte}</Badge>
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground" data-impact-inconnu={champ.code}>
                      Impact non chiffré par le moteur pour cette valeur — lancez le recalcul.
                    </span>
                  )}
                </div>
              )
            })}
          </form>

          {variante && (
            <div className="flex flex-col gap-1 rounded-md border border-border p-2" data-variante="conservatrice">
              <Button type="button" size="sm" variant="outline" onClick={appliquerVariante}>
                {variante.libelle}
              </Button>
              {variante.comparaison_texte && (
                <p className="text-xs text-muted-foreground">{variante.comparaison_texte}</p>
              )}
            </div>
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
