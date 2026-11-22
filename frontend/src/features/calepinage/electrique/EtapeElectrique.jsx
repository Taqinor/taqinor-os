import { Suspense } from 'react'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger, ErrorBoundary, Spinner } from '../../../ui'
import { ongletParCle } from '../atelier/onglets'
import PretAEnvoyer from '../commun/PretAEnvoyer'

/* ============================================================================
   ACAL395 — L'ÉTAPE ÉLECTRIQUE EN UNE PAGE (mode guidé).
   Le panneau « Prêt à envoyer ? » (ACAL865, son compte tient la synthèse)
   — puis les 7 panneaux existants en
   sections repliables, montés avec les MÊMES props que dans le rail. Aucun des
   7 n'est modifié. Ouverte d'office : la section demandée par `?onglet=<cle>`
   (`ouvert`), et le Verdict quand l'étape est `bloque`.
   ========================================================================== */

const SECTIONS_ELECTRIQUES = [
  { cle: 'equipements-electriques', libelle: 'Équipements' },
  { cle: 'verdict-electrique', libelle: 'Verdict' },
  // ACAL1191 — les six autres sections sont rangées sous le seul déclencheur « Réglages avancés ».
  { cle: 'cheminement-cables', libelle: 'Cheminement & câbles', avance: true },
  { cle: 'raccordement', libelle: 'Raccordement', avance: true },
  { cle: 'materiel-electrique', libelle: 'Matériel', avance: true },
  { cle: 'saisies-electriques', libelle: 'Saisies', avance: true },
  { cle: 'decisions-electriques', libelle: 'Décisions', avance: true },
  { cle: 'controle-chaine', libelle: 'Contrôle rapide d’une chaîne', avance: true }, // ACAL628
]
const PRINCIPALES = SECTIONS_ELECTRIQUES.filter((s) => !s.avance)
const AVANCEES = SECTIONS_ELECTRIQUES.filter((s) => s.avance)

/* ACAL865 — la synthèse est désormais le compte du panneau « Prêt à envoyer ? »
   (`commun/PretAEnvoyer.jsx`) : UN seul compte à l'écran, « ce qui manque »
   du parcours n'est plus compté ici (il garde les pastilles d'étape du rail).
   Les props du rail (calepinageId, builderApi, onRecharger, lectureSeule,
   documentVivant) sont relayées TELLES QUELLES à chaque section : `parcours`
   et `ouvert` ne concernent que l'étape. */
function Section({ cle, libelle, propsDuRail }) {
  const Composant = ongletParCle(cle)?.composant
  return (
    <AccordionItem value={cle} data-testid={`cal-electrique-section-${cle}`}>
      <AccordionTrigger>{libelle}</AccordionTrigger>
      <AccordionContent>
        <ErrorBoundary fallback={<p role="alert" className="text-sm text-destructive">{`La section « ${libelle} » n’a pas pu s’afficher.`}</p>}>
          <Suspense fallback={<Spinner />}>
            {Composant && (
              <Composant {...propsDuRail} />
            )}
          </Suspense>
        </ErrorBoundary>
      </AccordionContent>
    </AccordionItem>
  )
}

export default function EtapeElectrique({ parcours = null, ouvert = null, ...propsDuRail }) {
  const ouvertes = new Set()
  if (SECTIONS_ELECTRIQUES.some((s) => s.cle === ouvert)) ouvertes.add(ouvert)
  if (parcours?.etats?.electrique === 'bloque') ouvertes.add('verdict-electrique')
  const avanceeOuverte = AVANCEES.some((s) => ouvertes.has(s.cle))

  return (
    <div data-testid="cal-etape-electrique-ecran" className="mt-3">
      <PretAEnvoyer calepinageId={propsDuRail.calepinageId} testIdCompte="cal-electrique-synthese" />
      <Accordion type="multiple" defaultValue={[...ouvertes].filter((c) => !AVANCEES.some((s) => s.cle === c)).concat(avanceeOuverte ? ['avances'] : [])}>
        {PRINCIPALES.map((s) => <Section key={s.cle} {...s} propsDuRail={propsDuRail} />)}
        <AccordionItem value="avances" data-testid="cal-electrique-avances">
          <AccordionTrigger>Réglages avancés</AccordionTrigger>
          <AccordionContent>
            <Accordion type="multiple" defaultValue={AVANCEES.filter((s) => ouvertes.has(s.cle)).map((s) => s.cle)}>
              {AVANCEES.map((s) => <Section key={s.cle} {...s} propsDuRail={propsDuRail} />)}
            </Accordion>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  )
}
