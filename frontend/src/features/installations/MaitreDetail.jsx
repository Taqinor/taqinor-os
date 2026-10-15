import { Spinner, EmptyState } from '../../ui'

/* Disposition « liste à gauche / fiche à droite » PARTAGÉE des écrans de
   paramétrage Chantiers (kits d'assemblage, dossiers d'import) : colonne de
   boutons sélectionnables (chargement → vide → liste) et fiche du dossier
   choisi, ou message de sélection vide. `fiche` est null quand rien n'est
   sélectionné. */
export default function MaitreDetail({
  titre, action, loading, vide, testId, items, selected, onSelect, itemTestId,
  renderItem, fiche, selectionVide,
}) {
  return (
    <div className="flex flex-col gap-4 md:flex-row">
      <aside className="w-full md:w-72 flex-shrink-0 flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">{titre}</h3>
          {action}
        </div>
        {loading ? (
          <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Spinner className="size-4 text-primary" /> Chargement…
          </p>
        ) : items.length === 0 ? (
          <EmptyState title={vide.title} description={vide.description} className="py-4" />
        ) : (
          <ul className="flex flex-col gap-1" data-testid={testId}>
            {items.map((it) => (
              <li key={it.id}>
                <button type="button"
                  data-testid={itemTestId(it)}
                  className={`w-full text-left rounded-lg border px-3 py-2 text-sm ${selected === it.id ? 'border-primary bg-primary/5' : 'border-border'}`}
                  onClick={() => onSelect(it.id)}>
                  {renderItem(it)}
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
      <div className="flex-1 min-w-0">
        {!fiche ? (
          <EmptyState title={selectionVide.title}
            description={selectionVide.description}
            className="py-10" />
        ) : (
          fiche
        )}
      </div>
    </div>
  )
}
