import { Suspense } from 'react'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger, ErrorBoundary, Spinner } from '../../../ui'
import { ongletParCle } from '../atelier/onglets'

/* ============================================================================
   ACAL395 — L'ÉTAPE ÉLECTRIQUE EN UNE PAGE (mode guidé).
   Une synthèse — « Conforme » (étape `fait`) ou « n points à régler » (n =
   lignes `etape: electrique` de la liste « ce qui manque » du parcours,
   contrat `calepinage_parcours_guide.json`) — puis les 7 panneaux existants en
   sections repliables, montés avec les MÊMES props que dans le rail. Aucun des
   7 n'est modifié. Ouverte d'office : la section demandée par `?onglet=<cle>`
   (`ouvert`), et le Verdict quand l'étape est `bloque`.
   ========================================================================== */

const SECTIONS_ELECTRIQUES = [
  { cle: 'equipements-electriques', libelle: 'Équipements' },
  { cle: 'cheminement-cables', libelle: 'Cheminement & câbles' },
  { cle: 'raccordement', libelle: 'Raccordement' },
  { cle: 'verdict-electrique', libelle: 'Verdict' },
  { cle: 'materiel-electrique', libelle: 'Matériel' },
  { cle: 'saisies-electriques', libelle: 'Saisies' },
  { cle: 'decisions-electriques', libelle: 'Décisions' },
]

function syntheseElectrique(parcours) {
  const etat = parcours?.etats?.electrique
  const n = (parcours?.manque ?? []).filter((m) => m?.etape === 'electrique').length
  if (etat === 'fait') return 'Conforme'
  if (n > 0) return `${n} point${n > 1 ? 's' : ''} à régler`
  return 'Aucun point à régler pour l’instant'
}

export default function EtapeElectrique({
  calepinageId = null, builderApi = null, onRecharger = null, lectureSeule = false,
  documentVivant = null, parcours = null, ouvert = null,
}) {
  const ouvertes = new Set()
  if (SECTIONS_ELECTRIQUES.some((s) => s.cle === ouvert)) ouvertes.add(ouvert)
  if (parcours?.etats?.electrique === 'bloque') ouvertes.add('verdict-electrique')

  return (
    <div data-testid="cal-etape-electrique-ecran" className="mt-3">
      <p data-testid="cal-electrique-synthese" className="mb-2 text-sm font-medium">
        {syntheseElectrique(parcours)}
      </p>
      <Accordion type="multiple" defaultValue={[...ouvertes]}>
        {SECTIONS_ELECTRIQUES.map(({ cle, libelle }) => {
          const Composant = ongletParCle(cle)?.composant
          return (
            <AccordionItem key={cle} value={cle} data-testid={`cal-electrique-section-${cle}`}>
              <AccordionTrigger>{libelle}</AccordionTrigger>
              <AccordionContent>
                <ErrorBoundary fallback={<p role="alert" className="text-sm text-destructive">{`La section « ${libelle} » n’a pas pu s’afficher.`}</p>}>
                  <Suspense fallback={<Spinner />}>
                    {Composant && (
                      <Composant
                        calepinageId={calepinageId}
                        builderApi={builderApi}
                        onRecharger={onRecharger}
                        lectureSeule={lectureSeule}
                        documentVivant={documentVivant}
                      />
                    )}
                  </Suspense>
                </ErrorBoundary>
              </AccordionContent>
            </AccordionItem>
          )
        })}
      </Accordion>
    </div>
  )
}
