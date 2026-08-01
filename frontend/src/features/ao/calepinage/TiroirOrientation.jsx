import { Ban } from 'lucide-react'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../../ui'
import { cn } from '../../../lib/cn'

/* ============================================================================
   AOF98 — Tiroir « Orientation & segments » avec REFUS des orientations
   inconstructibles.
   ----------------------------------------------------------------------------
   POINT DUR, PIÈGE RÉEL ET DÉJÀ PAYÉ. Une table dos-à-dos est-ouest a
   FORCÉMENT son faîtage nord-sud, donc une rangée court nord-sud.
   `vue_bat_A.py` v1 a calepiné la barre en rangées est-ouest — faîtage E-O,
   donc modules face NORD, donc inconstructible — et TOUTE la planche A a dû
   être refaite. Une orientation incompatible ne se dessine pas « pour voir » :
   elle est REFUSÉE, avec son motif.

   **Cet écran est la SECONDE ligne de défense.** La première est
   `ErreurOrientation` côté moteur (AOF45), qui refuse la combinaison quoi
   qu'affiche l'écran. Conséquence directe sur ce composant : l'infobulle
   REPREND le motif renvoyé par le serveur — elle n'en rédige aucun. Si le
   serveur ne dit pas pourquoi, l'écran ne le devine pas.

   L'infobulle est le `title` natif (doublé d'une ligne de motif VISIBLE) et
   non un tooltip Radix : un déclencheur Radix ne s'ouvre pas sur un contrôle
   désactivé, et une explication de refus doit rester lisible sans survol —
   au clavier comme à la lecture d'écran.

   ── Contrat de charge utile ───────────────────────────────────────────────
   donnees = {
     sens_rangees:        [{ code, libelle, disponible, motif? }],
     orientations_tables: [{ code, libelle, disponible, motif? }],
     segmentations:       [{ code, libelle, disponible, motif? }],
     formes_l:            [{ code, libelle, disponible, motif? }],
   }
   valeurs = { sens_rangees, orientation_table, segmentation, forme_l }
   ========================================================================== */

const GROUPES = [
  { champ: 'sens_rangees', cle: 'sens_rangees', libelle: 'Sens des rangées' },
  { champ: 'orientations_tables', cle: 'orientation_table', libelle: 'Orientation des tables' },
  { champ: 'segmentations', cle: 'segmentation', libelle: 'Découpage en segments' },
  { champ: 'formes_l', cle: 'forme_l', libelle: 'Traitement du L' },
]

function GroupeOptions({ libelle, options, valeur, onChoisir }) {
  if (!Array.isArray(options) || options.length === 0) return null
  return (
    <div className="flex flex-col gap-1" data-groupe={libelle}>
      <span className="text-xs uppercase tracking-wide text-muted-foreground">{libelle}</span>
      <div role="radiogroup" aria-label={libelle} className="flex flex-wrap gap-1">
        {options.map((option) => {
          const refuse = option.disponible === false
          return (
            <button
              key={option.code}
              type="button"
              role="radio"
              aria-checked={valeur === option.code}
              aria-disabled={refuse || undefined}
              disabled={refuse}
              // Motif SERVEUR, jamais un texte rédigé ici.
              title={refuse ? option.motif : undefined}
              data-refuse={refuse ? 'true' : undefined}
              onClick={() => { if (!refuse) onChoisir?.(option.code) }}
              className={cn(
                'inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-sm transition-colors focus-ring',
                valeur === option.code
                  ? 'border-primary bg-primary/10 text-foreground'
                  : 'border-border text-muted-foreground hover:text-foreground',
                refuse && 'cursor-not-allowed opacity-60',
              )}
            >
              {refuse && <Ban className="size-3.5" aria-hidden="true" />}
              {option.libelle}
            </button>
          )
        })}
      </div>
      {options.filter((option) => option.disponible === false && option.motif).map((option) => (
        <p key={`motif-${option.code}`} className="text-xs text-destructive" data-motif-refus={option.code}>
          {option.libelle} — {option.motif}
        </p>
      ))}
    </div>
  )
}

export default function TiroirOrientation({ donnees, valeurs = {}, onChange }) {
  if (!donnees) return null

  return (
    <Accordion type="single" collapsible defaultValue="orientation" data-ao-tiroir="orientation">
      <AccordionItem value="orientation">
        <AccordionTrigger>Orientation &amp; segments</AccordionTrigger>
        <AccordionContent className="flex flex-col gap-4 text-foreground">
          {GROUPES.map((groupe) => (
            <GroupeOptions
              key={groupe.cle}
              libelle={groupe.libelle}
              options={donnees[groupe.champ]}
              valeur={valeurs[groupe.cle]}
              onChoisir={(code) => onChange?.({ [groupe.cle]: code })}
            />
          ))}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
