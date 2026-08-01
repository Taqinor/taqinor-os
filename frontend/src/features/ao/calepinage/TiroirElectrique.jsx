import { useEffect, useState } from 'react'
import { TriangleAlert } from 'lucide-react'
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger, Badge, Button, Input, Label,
} from '../../../ui'

/* ============================================================================
   AOF99 — Tiroir « Contraintes électriques » + alerte de non-conformité NOMMÉE.
   ----------------------------------------------------------------------------
   La chaîne calepinage → électricité est indissociable : modules → kWc →
   chaînes de N modules (16 par défaut) → onduleurs → ratio DC/AC → conformité
   au CPS. Chaque maillon est recalculé PAR LE MOTEUR à chaque changement de
   calepinage ; ce tiroir n'en affiche que le résultat (garde AOF94).

   Deux exigences de fond :
   • le RESTE de modules n'est pas caché : il est annoncé « en réserve
     d'appoint » — un reste silencieux se retrouve, plus tard, en écart entre
     le bordereau et le chantier ;
   • une non-conformité est NOMMÉE (« 80 kW hors fourchette 0,75-1 »), pas un
     vague « attention » : elle cite la grandeur, sa valeur et la règle du CPS
     violée, et propose la répartition conforme calculée par le moteur.

   `onConformite` remonte l'état de conformité tel quel : c'est lui qui BLOQUE
   la publication du dossier en amont — l'alerte n'est pas décorative.

   ── Contrat de charge utile ───────────────────────────────────────────────
   donnees = {
     chaine?:      { libelle_taille, reste_texte },
     onduleurs?:   { nombre_texte, puissance_texte, plafond_texte },
     ratio_dc_ac?: { texte, fourchette_texte },
     conformite?:  { conforme, bloquant, alerte,
                     repartition_proposee?: { texte, patch } },
   }
   valeurs = { taille_chaine }
   ========================================================================== */

function Ligne({ libelle, valeur, indice }) {
  if (!valeur) return null
  return (
    <div className="flex flex-col">
      <span className="text-xs uppercase tracking-wide text-muted-foreground">{libelle}</span>
      <span className="font-medium tabular-nums">{valeur}</span>
      {indice && <span className="text-xs text-muted-foreground">{indice}</span>}
    </div>
  )
}

export default function TiroirElectrique({ donnees, valeurs = {}, onChange, onConformite }) {
  const conformite = donnees?.conformite ?? null
  const [saisie, setSaisie] = useState(valeurs.taille_chaine ?? '')

  // La conformité remonte telle quelle : la porte de publication est en amont.
  useEffect(() => { onConformite?.(conformite) }, [conformite, onConformite])

  useEffect(() => { setSaisie(valeurs.taille_chaine ?? '') }, [valeurs.taille_chaine])

  if (!donnees) return null

  const onSaisie = (event) => {
    const brut = event.target.value
    setSaisie(brut)
    const nombre = Number.parseFloat(brut)
    if (Number.isFinite(nombre)) onChange?.({ taille_chaine: nombre })
  }

  const proposition = conformite?.repartition_proposee

  return (
    <Accordion type="single" collapsible defaultValue="electrique" data-ao-tiroir="electrique">
      <AccordionItem value="electrique">
        <AccordionTrigger>Contraintes électriques</AccordionTrigger>
        <AccordionContent className="flex flex-col gap-4 text-foreground">
          <form noValidate className="flex flex-col gap-2" onSubmit={(e) => e.preventDefault()}>
            <Label htmlFor="ao-taille-chaine">Modules par chaîne</Label>
            <Input
              id="ao-taille-chaine"
              type="number"
              step="any"
              inputMode="numeric"
              value={saisie}
              onChange={onSaisie}
            />
          </form>

          <div className="grid grid-cols-2 gap-3">
            <Ligne libelle="Chaînes" valeur={donnees.chaine?.libelle_taille} indice={donnees.chaine?.reste_texte} />
            <Ligne libelle="Onduleurs" valeur={donnees.onduleurs?.nombre_texte} indice={donnees.onduleurs?.puissance_texte} />
            <Ligne libelle="Ratio DC/AC" valeur={donnees.ratio_dc_ac?.texte} indice={donnees.ratio_dc_ac?.fourchette_texte} />
            <Ligne libelle="Plafond par onduleur" valeur={donnees.onduleurs?.plafond_texte} />
          </div>

          {conformite && (conformite.conforme
            ? (
              <Badge tone="success" data-conformite="conforme">Conforme au CPS</Badge>
            )
            : (
              <div
                role="alert"
                data-conformite="non-conforme"
                data-bloquant={conformite.bloquant ? 'true' : undefined}
                className="flex flex-col gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-2"
              >
                <p className="flex items-center gap-1.5 text-sm font-medium text-destructive">
                  <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
                  {conformite.alerte}
                </p>
                {conformite.bloquant && (
                  <p className="text-xs text-destructive">
                    Publication bloquée tant que cette non-conformité subsiste.
                  </p>
                )}
                {proposition?.texte && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    data-action="repartition-conforme"
                    onClick={() => onChange?.({ ...proposition.patch })}
                  >
                    Appliquer la répartition conforme : {proposition.texte}
                  </Button>
                )}
              </div>
            ))}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
