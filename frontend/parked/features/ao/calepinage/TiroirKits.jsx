import { Accordion, AccordionContent, AccordionItem, AccordionTrigger, Badge, Segmented } from '../../../ui'

/* ============================================================================
   AOF95 — Tiroir « Kits » (portrait / paysage / mixte) avec CONTRE-ÉPREUVE.
   ----------------------------------------------------------------------------
   Le choix d'un kit se défend, il ne se décrète pas : le moteur renvoie, pour
   chaque segment, ce que DONNERAIT chaque kit et le motif géométrique qui
   tranche (« ce segment en paysage : 34 · en portrait : 24 — la cage de 5,93
   interdit toute rangée large »). Ce tiroir n'affiche que ça : **aucun chiffre
   de comparaison n'est saisi ni recalculé ici** (garde de code AOF94).

   L'argument commercial « les 2 kits sont ceux des bâtiments déjà
   approvisionnés — aucun approvisionnement nouveau » n'est PAS un slogan : il
   n'apparaît que si le contrôle d'approvisionnement (AOF119) l'a confirmé
   côté serveur. Non confirmé ⇒ rien ne s'affiche (jamais un « probablement »).

   ── Contrat de charge utile ───────────────────────────────────────────────
   donnees = {
     kits:        [{ code, libelle, recommande?: bool }],
     granularites:[{ code, libelle }],            // site / zone / rangée / segment
     recommandation?: { code, libelle },          // chip « recommandé : … »
     composition?:    { texte, total_texte? },    // « 13 rangées : 4 portrait + 9 paysage »
     contre_epreuve?: [{ id, segment, options: [{ code, libelle, texte }], motif? }],
     approvisionnement?: { confirme: bool, argument },   // AOF119
   }
   valeurs = { kit, granularite_kit }
   ========================================================================== */

export default function TiroirKits({ donnees, valeurs = {}, onChange, perime = false }) {
  if (!donnees) return null

  const kits = donnees.kits || []
  const granularites = donnees.granularites || []
  const contreEpreuve = donnees.contre_epreuve || []
  const appro = donnees.approvisionnement

  return (
    <Accordion type="single" collapsible defaultValue="kits" data-ao-tiroir="kits">
      <AccordionItem value="kits">
        <AccordionTrigger>Kits de pose</AccordionTrigger>
        <AccordionContent className="flex flex-col gap-4 text-foreground">
          <div className="flex flex-wrap items-center gap-2">
            <Segmented
              aria-label="Kit de pose admis"
              options={kits.map((kit) => ({ value: kit.code, label: kit.libelle }))}
              value={valeurs.kit}
              onChange={(code) => onChange?.({ kit: code })}
            />
            {/* Chip de recommandation : libellé SERVEUR, jamais un conseil écrit ici. */}
            {donnees.recommandation && (
              <Badge tone="info" data-recommande={donnees.recommandation.code}>
                recommandé : {donnees.recommandation.libelle}
              </Badge>
            )}
          </div>

          {granularites.length > 0 && (
            <div className="flex flex-col gap-1">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">Granularité</span>
              <Segmented
                size="sm"
                aria-label="Granularité du choix de kit"
                options={granularites.map((g) => ({ value: g.code, label: g.libelle }))}
                value={valeurs.granularite_kit}
                onChange={(code) => onChange?.({ granularite_kit: code })}
              />
            </div>
          )}

          {donnees.composition && (
            <div
              className={perime ? 'opacity-40' : undefined}
              data-composition="retenue"
              data-perime={perime ? 'true' : undefined}
            >
              <span className="text-xs uppercase tracking-wide text-muted-foreground">Composition retenue</span>
              <p className="font-medium">{donnees.composition.texte}</p>
              {donnees.composition.total_texte && (
                <p className="text-sm text-muted-foreground">{donnees.composition.total_texte}</p>
              )}
            </div>
          )}

          {contreEpreuve.length > 0 && (
            <div className="flex flex-col gap-2" data-contre-epreuve="moteur">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">Contre-épreuve du moteur</span>
              <ul className="flex flex-col gap-2">
                {contreEpreuve.map((cas) => (
                  <li key={cas.id} className="rounded-md border border-border p-2 text-sm">
                    <span className="font-medium">{cas.segment}</span>
                    <span className="ml-2 text-muted-foreground">
                      {(cas.options || []).map((option) => `${option.libelle} : ${option.texte}`).join(' · ')}
                    </span>
                    {cas.motif && <p className="mt-1 text-xs text-muted-foreground">{cas.motif}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* AOF119 — argument d'approvisionnement : affiché SEULEMENT si confirmé. */}
          {appro?.confirme && appro.argument && (
            <p className="rounded-md bg-success/10 p-2 text-sm text-success" data-approvisionnement="confirme">
              {appro.argument}
            </p>
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
