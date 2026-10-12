import { Button } from '../../ui'

/* Pied « Précédent / Page n / N / Suivant » des listes paginées des Paramètres
   (Corbeille, Pièces jointes). `testId` pose l'ancre e2e du compteur de page. */
export default function PaginationPrecedentSuivant({ page, pages, setPage, testId }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <Button type="button" size="sm" variant="outline"
              disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
        Précédent
      </Button>
      <span data-testid={testId}>
        Page {page} / {pages}
      </span>
      <Button type="button" size="sm" variant="outline"
              disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
        Suivant
      </Button>
    </div>
  )
}
