import { useEffect, useState } from 'react'
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger, Button, Input, Label,
} from '../../../ui'
import AlleeGratuiteChart from './AlleeGratuiteChart'

/* ============================================================================
   AOF96 — Tiroir « Allées » : largeur d'allée + graphe de l'allée GRATUITE.
   ----------------------------------------------------------------------------
   Trois façons de régler la même valeur : les préréglages renvoyés par le
   serveur (« 0,60 minimum », « allée de maintenance »), la saisie libre, et le
   bouton du plateau gratuit (AlleeGratuiteChart) qui applique en un clic la
   plus grande largeur SANS PERTE.

   Discipline de saisie identique à l'écran devis : `noValidate` + `step="any"`
   — **le champ n'arrondit ni ne rejette jamais une valeur légitime**. La
   saisie vit en état local et remonte à chaque frappe exploitable ; c'est le
   serveur qui recalcule (AOF94).

   ── Contrat de charge utile ───────────────────────────────────────────────
   donnees = { presets?: [{ code, libelle, largeur_m }], graphe?: {…} }
   valeurs = { allee_m }
   ========================================================================== */

export default function TiroirAllees({ donnees, valeurs = {}, onChange, perime = false }) {
  const [saisie, setSaisie] = useState(valeurs.allee_m ?? '')

  // La valeur de référence reste celle du serveur : on se recale dessus quand
  // elle change (préréglage, plateau appliqué, recommandation acceptée).
  useEffect(() => { setSaisie(valeurs.allee_m ?? '') }, [valeurs.allee_m])

  if (!donnees) return null

  const appliquerLargeur = (largeur) => {
    setSaisie(largeur)
    onChange?.({ allee_m: largeur })
  }

  const onSaisie = (event) => {
    const brut = event.target.value
    setSaisie(brut)
    const nombre = Number.parseFloat(brut)
    if (Number.isFinite(nombre)) onChange?.({ allee_m: nombre })
  }

  return (
    <Accordion type="single" collapsible defaultValue="allees" data-ao-tiroir="allees">
      <AccordionItem value="allees">
        <AccordionTrigger>Allées</AccordionTrigger>
        <AccordionContent className="flex flex-col gap-4 text-foreground">
          <form noValidate className="flex flex-col gap-2" onSubmit={(e) => e.preventDefault()}>
            <Label htmlFor="ao-allee-largeur">Largeur d&apos;allée (m)</Label>
            <Input
              id="ao-allee-largeur"
              type="number"
              step="any"
              inputMode="decimal"
              value={saisie}
              onChange={onSaisie}
            />
            {(donnees.presets || []).length > 0 && (
              <div className="flex flex-wrap gap-2">
                {donnees.presets.map((preset) => (
                  <Button
                    key={preset.code}
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => appliquerLargeur(preset.largeur_m)}
                  >
                    {preset.libelle}
                  </Button>
                ))}
              </div>
            )}
          </form>

          {donnees.graphe && (
            <AlleeGratuiteChart
              graphe={donnees.graphe}
              perime={perime}
              onAppliquer={appliquerLargeur}
            />
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
