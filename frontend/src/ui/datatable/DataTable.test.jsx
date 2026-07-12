import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'vitest-axe'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { setStoredDensity } from '../../design/theme.js'
import { DataTable } from './DataTable.jsx'

/* ============================================================================
   H129–O166 — Couche « tableau premium » du moteur DataTable.
   RTL + axe. Le moteur a besoin d'un <Router> (useSearchParams dans le hook)
   et d'un <ThemeProvider> (useDensity). On les fournit via `wrapper`.
   La logique pure est testée séparément (datatable.test.mjs / parité).
   ========================================================================== */

function wrapper({ children }) {
  return (
    <MemoryRouter>
      <ThemeProvider>{children}</ThemeProvider>
    </MemoryRouter>
  )
}

const DATA = [
  { id: 1, nom: 'Kasri', ville: 'Rabat', montant: 1200 },
  { id: 2, nom: 'Benani', ville: 'Casablanca', montant: 800 },
  { id: 3, nom: 'Amine', ville: 'Fès', montant: 2000 },
]

const COLUMNS = [
  { id: 'nom', header: 'Nom' },
  { id: 'ville', header: 'Ville' },
  { id: 'montant', header: 'Montant', align: 'right', numeric: true },
]

function renderTable(props = {}) {
  return render(<DataTable data={DATA} columns={COLUMNS} {...props} />, { wrapper })
}

beforeEach(() => {
  // Densité par défaut connue pour les tests de hauteur de ligne.
  setStoredDensity('comfortable')
})

/* ============================== H129 — VISUEL PREMIUM ============================== */

describe('H129 — passe visuelle « tableau premium »', () => {
  it('aligne à droite et met en chiffres tabulaires les colonnes numériques', () => {
    const { container } = renderTable()
    // La cellule Montant porte tabular-nums + text-right.
    const numeric = container.querySelector('td.tabular-nums')
    expect(numeric).toBeTruthy()
    expect(numeric.className).toContain('text-right')
  })

  it('ne zèbre pas les lignes (aucune classe even/odd de fond)', () => {
    const { container } = renderTable()
    const rows = container.querySelectorAll('tbody tr')
    rows.forEach((tr) => {
      expect(tr.className).not.toMatch(/odd:|even:|nth-child/)
    })
  })

  it('utilise un séparateur horizontal 1px clair, sans bordure verticale', () => {
    const { container } = renderTable()
    const tr = container.querySelector('tbody tr')
    // Séparateur horizontal (border-t) présent.
    expect(tr.className).toContain('border-t')
    // Aucune bordure verticale (border-l / border-r / border-x) sur les cellules.
    container.querySelectorAll('tbody td').forEach((td) => {
      expect(td.className).not.toMatch(/border-l|border-r|border-x/)
    })
  })

  it('applique un survol de ligne discret (≈3–5 %)', () => {
    const { container } = renderTable()
    const tr = container.querySelector('tbody tr')
    // Survol discret : muted/40 au plus (pas un fond plein).
    expect(tr.className).toMatch(/hover:bg-(muted|accent|foreground)\/(3|4|5)/)
  })

  it('rend un en-tête collant (sticky)', () => {
    const { container } = renderTable()
    const thead = container.querySelector('thead')
    expect(thead.className).toContain('sticky')
    expect(thead.className).toContain('top-0')
  })

  it('hauteur de ligne par densité : confort = 40px par défaut', () => {
    const { container } = renderTable()
    const tr = container.querySelector('tbody tr')
    expect(tr.style.height).toBe('40px')
  })

  it('hauteur de ligne par densité : compact = 32px', () => {
    setStoredDensity('compact')
    const { container } = renderTable()
    const tr = container.querySelector('tbody tr')
    expect(tr.style.height).toBe('32px')
  })
})

/* ============================== H130 — ÉPINGLAGE DE COLONNES ============================== */

describe('H130 — épinglage de colonnes', () => {
  it('épingle la première colonne à gauche et la colonne actions à droite via props', () => {
    const cols = [
      { id: 'nom', header: 'Nom', pinned: 'left' },
      { id: 'ville', header: 'Ville' },
      { id: 'montant', header: 'Montant', align: 'right' },
    ]
    const { container } = render(
      <DataTable
        data={DATA}
        columns={cols}
        rowActions={() => [{ id: 'voir', label: 'Voir' }]}
      />,
      { wrapper },
    )
    // Une cellule corps épinglée à gauche est sticky.
    const stickyCell = container.querySelector('tbody td.sticky')
    expect(stickyCell).toBeTruthy()
    // La colonne actions est épinglée à droite (header actions sticky right-0).
    const actionsHeader = container.querySelector('thead th[data-pinned="actions-right"]')
    expect(actionsHeader).toBeTruthy()
    expect(actionsHeader.className).toContain('sticky')
  })

  it('affiche une ombre de bord quand on défile horizontalement', () => {
    const cols = [{ id: 'nom', header: 'Nom', pinned: 'left' }, { id: 'ville', header: 'Ville' }]
    const { container } = render(<DataTable data={DATA} columns={cols} />, { wrapper })
    const scroller = container.querySelector('[data-dt-scroll]')
    expect(scroller).toBeTruthy()
    // Simule un défilement horizontal → l'état d'ombre se marque sur le conteneur.
    fireEvent.scroll(scroller, { target: { scrollLeft: 40 } })
    expect(container.querySelector('[data-pin-shadow-left="true"]')).toBeTruthy()
  })
})

/* ============================== H131 — AFFORDANCES DE LIGNE ============================== */

describe('H131 — affordances de ligne', () => {
  it('révèle les actions rapides au survol (opacity-0 group-hover)', () => {
    const { container } = render(
      <DataTable data={DATA} columns={COLUMNS} rowActions={() => [{ id: 'voir', label: 'Voir' }]} />,
      { wrapper },
    )
    const quick = container.querySelector('[data-row-quick-actions]')
    expect(quick).toBeTruthy()
    expect(quick.className).toContain('opacity-0')
    expect(quick.className).toContain('group-hover:opacity-100')
  })

  it('affiche un menu kebab persistant (toujours visible) dans le tableau desktop', () => {
    const { container } = render(
      <DataTable data={DATA} columns={COLUMNS} rowActions={() => [{ id: 'voir', label: 'Voir' }]} />,
      { wrapper },
    )
    const table = container.querySelector('[data-dt-table]')
    const kebabs = within(table).getAllByLabelText("Plus d'actions sur la ligne")
    expect(kebabs.length).toBe(DATA.length)
  })

  it('sélection par plage au Shift-clic sélectionne toute la plage', async () => {
    const user = userEvent.setup()
    const { container } = render(<DataTable data={DATA} columns={COLUMNS} selectable />, { wrapper })
    const table = container.querySelector('[data-dt-table]')
    const boxes = within(table).getAllByLabelText(/Sélectionner la ligne/)
    await user.click(boxes[0])
    // Shift-clic sur la 3e → sélectionne 1,2,3 → barre de région reflète 3.
    await user.keyboard('{Shift>}')
    await user.click(boxes[2])
    await user.keyboard('{/Shift}')
    // Les 3 cases doivent être cochées.
    boxes.forEach((b) => expect(b).toHaveAttribute('data-state', 'checked'))
  })
})

/* ============================== H132 — BARRE D'ACTIONS GROUPÉES ============================== */

describe('H132 — barre d\'actions groupées flottante', () => {
  it('apparaît dès qu\'une ligne est sélectionnée avec le compte et les actions', async () => {
    const user = userEvent.setup()
    render(
      <DataTable
        data={DATA}
        columns={COLUMNS}
        selectable
        bulkActions={() => [{ id: 'suppr', label: 'Supprimer', destructive: true }]}
      />,
      { wrapper },
    )
    expect(screen.queryByRole('region', { name: /sélectionnée/i })).not.toBeInTheDocument()
    const boxes = screen.getAllByLabelText(/Sélectionner la ligne/)
    await user.click(boxes[0])
    const bar = screen.getByRole('region', { name: /sélectionnée/i })
    expect(bar).toBeInTheDocument()
    expect(within(bar).getByText('Supprimer')).toBeInTheDocument()
    expect(within(bar).getByText('Tout désélectionner')).toBeInTheDocument()
  })

  it('regroupe les actions au-delà de 3 dans un menu « Plus »', async () => {
    const user = userEvent.setup()
    render(
      <DataTable
        data={DATA}
        columns={COLUMNS}
        selectable
        bulkActions={() =>
          Array.from({ length: 5 }, (unused, i) => ({ id: `a${i}`, label: `Action ${i}` }))
        }
      />,
      { wrapper },
    )
    await user.click(screen.getAllByLabelText(/Sélectionner la ligne/)[0])
    expect(screen.getByRole('button', { name: 'Plus' })).toBeInTheDocument()
  })
})

/* ============================== H133 — PERFORMANCE PERÇUE ============================== */

describe('H133 — performance perçue', () => {
  it('affiche des lignes-squelettes calquées sur le nombre de colonnes au chargement', () => {
    const { container } = render(<DataTable data={[]} columns={COLUMNS} loading />, { wrapper })
    const skeletonRows = container.querySelectorAll('[data-skeleton-row]')
    expect(skeletonRows.length).toBeGreaterThan(0)
    // Chaque ligne squelette a une cellule par colonne.
    const cellsPerRow = skeletonRows[0].querySelectorAll('td').length
    expect(cellsPerRow).toBeGreaterThanOrEqual(COLUMNS.length)
  })

  it('ne montre jamais squelette + spinner simultanément', () => {
    const { container } = render(<DataTable data={[]} columns={COLUMNS} loading />, { wrapper })
    expect(container.querySelectorAll('[data-skeleton-row]').length).toBeGreaterThan(0)
    expect(container.querySelector('[role="status"][data-spinner]')).toBeNull()
  })

  // VX132 — le squelette suit `pageSize` (borné à 12) au lieu d'un compte FIXE
  // à 6 : évite le saut brutal vers les vraies lignes (et donc du scroll).
  it('le nombre de lignes-squelettes suit pageSize (pageSize=5 -> 5 lignes)', () => {
    const { container } = render(
      <DataTable data={[]} columns={COLUMNS} loading pageSize={5} />, { wrapper },
    )
    expect(container.querySelectorAll('[data-skeleton-row]').length).toBe(5)
  })

  it('le nombre de lignes-squelettes reste borné à 12 même pour un pageSize=50', () => {
    const { container } = render(
      <DataTable data={[]} columns={COLUMNS} loading pageSize={50} />, { wrapper },
    )
    expect(container.querySelectorAll('[data-skeleton-row]').length).toBe(12)
  })

  it('précharge les données de la ligne au survol/intention via onRowPrefetch', async () => {
    const onRowPrefetch = vi.fn()
    const { container } = render(
      <DataTable data={DATA} columns={COLUMNS} onRowPrefetch={onRowPrefetch} />,
      { wrapper },
    )
    const firstRow = container.querySelector('[data-dt-table] tbody tr[aria-rowindex]')
    fireEvent.mouseEnter(firstRow)
    expect(onRowPrefetch).toHaveBeenCalledWith(DATA[0])
  })
})

/* ============================== M154 — REPLI CARTES MOBILE ============================== */

describe('M154 — repli tableau → cartes sur mobile', () => {
  it('rend une vue cartes masquée en dessous de 768px (dt-desktop:hidden — VX180, PAS sm: = 640px) avec chevron de détail', () => {
    const { container } = render(
      <DataTable data={DATA} columns={COLUMNS} onRowClick={() => {}} />,
      { wrapper },
    )
    const cardsWrap = container.querySelector('[data-dt-cards]')
    expect(cardsWrap).toBeTruthy()
    // VX180 — jsdom n'applique aucune media query : cette assertion ne peut
    // structurellement PROUVER le seuil réel (voir e2e/datatable-breakpoint.spec.js
    // pour la preuve à 700px réels) ; elle vérifie seulement que le composant
    // utilise la variante DÉDIÉE `dt-desktop:` et non plus `sm:` (640px).
    expect(cardsWrap.className).toContain('dt-desktop:hidden')
    expect(cardsWrap.className).not.toContain('sm:hidden')
    // Métrique clé en grand + chevron vers le détail.
    expect(cardsWrap.querySelector('[data-card-chevron]')).toBeTruthy()
  })

  it('masque l\'en-tête de tableau sur mobile (table dans un conteneur dt-desktop:block — VX180, 768px)', () => {
    const { container } = render(<DataTable data={DATA} columns={COLUMNS} />, { wrapper })
    const tableWrap = container.querySelector('[data-dt-table]')
    expect(tableWrap.className).toContain('hidden')
    expect(tableWrap.className).toContain('dt-desktop:block')
    expect(tableWrap.className).not.toContain('sm:block')
  })
})

/* ============================== N160 — ACCESSIBILITÉ ============================== */

describe('N160 — accessibilité du DataTable', () => {
  it('expose les rôles grille (role=grid, aria-rowindex, aria-selected)', () => {
    const { container } = render(<DataTable data={DATA} columns={COLUMNS} selectable />, { wrapper })
    expect(container.querySelector('table[role="grid"]')).toBeTruthy()
    const bodyRows = container.querySelectorAll('tbody tr[aria-rowindex]')
    expect(bodyRows.length).toBe(DATA.length)
    // aria-selected présent sur les lignes sélectionnables.
    expect(container.querySelector('tbody tr[aria-selected]')).toBeTruthy()
  })

  it('navigation clavier : flèches déplacent la ligne active, Entrée ouvre', async () => {
    const onRowClick = vi.fn()
    const user = userEvent.setup()
    const { container } = render(
      <DataTable data={DATA} columns={COLUMNS} onRowClick={onRowClick} />,
      { wrapper },
    )
    const grid = container.querySelector('table[role="grid"]')
    grid.focus()
    await user.keyboard('{ArrowDown}')
    await user.keyboard('{Enter}')
    expect(onRowClick).toHaveBeenCalledWith(DATA[0])
  })

  it('n\'a aucune violation d\'accessibilité détectable', async () => {
    const { container } = render(
      <DataTable data={DATA} columns={COLUMNS} selectable aria-label="Clients" />,
      { wrapper },
    )
    const results = await axe(container)
    expect(results.violations).toEqual([])
  })
})

/* ============================== N162 — ALTERNATIVE AU GLISSER ============================== */

describe('N162 — alternative au glisser + taille de cible', () => {
  it('offre des boutons « déplacer » sans glisser dans le menu d\'en-tête', async () => {
    const user = userEvent.setup()
    render(<DataTable data={DATA} columns={COLUMNS} />, { wrapper })
    // Ouvre le menu d'options de la première colonne.
    const menuBtn = screen.getAllByLabelText(/Options de la colonne/)[0]
    await user.click(menuBtn)
    expect(await screen.findByText('Déplacer à droite')).toBeInTheDocument()
  })

  it('déplacer à droite réordonne effectivement les colonnes', async () => {
    const user = userEvent.setup()
    const { container } = render(<DataTable data={DATA} columns={COLUMNS} />, { wrapper })
    const headersBefore = [...container.querySelectorAll('thead th[scope="col"]')]
      .map((th) => th.textContent)
    await user.click(screen.getAllByLabelText(/Options de la colonne/)[0])
    await user.click(await screen.findByText('Déplacer à droite'))
    const headersAfter = [...container.querySelectorAll('thead th[scope="col"]')]
      .map((th) => th.textContent)
    expect(headersAfter).not.toEqual(headersBefore)
  })
})

/* ============================== O164 — VIRTUALISATION ============================== */

describe('O164 — virtualiser les grandes listes', () => {
  const BIG = Array.from({ length: 1200 }, (unused, i) => ({
    id: i + 1,
    nom: `Client ${i + 1}`,
    ville: 'Rabat',
    montant: i,
  }))

  it('au-delà du seuil (~100), ne rend qu\'une fenêtre de lignes', () => {
    const { container } = render(
      <DataTable data={BIG} columns={COLUMNS} pageSize={2000} virtualize rowHeight={40} maxBodyHeight={400} />,
      { wrapper },
    )
    const rendered = container.querySelectorAll('tbody tr[aria-rowindex]')
    // Bien moins que 1200 lignes rendues (fenêtre + overscan).
    expect(rendered.length).toBeGreaterThan(0)
    expect(rendered.length).toBeLessThan(100)
  })

  it('s\'auto-active au-dessus du seuil même sans prop virtualize', () => {
    const { container } = render(
      <DataTable data={BIG} columns={COLUMNS} pageSize={2000} rowHeight={40} maxBodyHeight={400} />,
      { wrapper },
    )
    const rendered = container.querySelectorAll('tbody tr[aria-rowindex]')
    expect(rendered.length).toBeLessThan(BIG.length)
  })
})

/* ============================== O166 — LARGEURS MÉMOÏSÉES ============================== */

describe('O166 — largeurs de colonnes mémoïsées (variables CSS)', () => {
  it('pousse les largeurs via variables CSS sur la rangée de colgroup, pas par cellule', () => {
    const cols = [
      { id: 'nom', header: 'Nom', width: 200 },
      { id: 'ville', header: 'Ville', width: 140 },
      { id: 'montant', header: 'Montant', align: 'right' },
    ]
    const { container } = render(<DataTable data={DATA} columns={cols} />, { wrapper })
    // Un <colgroup> dimensionne les colonnes une seule fois.
    const cols0 = container.querySelectorAll('colgroup col')
    expect(cols0.length).toBeGreaterThanOrEqual(cols.length)
    const widthCol = [...cols0].find((c) => c.style.width === '200px')
    expect(widthCol).toBeTruthy()
  })

  it('expose les largeurs en variables CSS sur le conteneur du tableau', () => {
    const cols = [{ id: 'nom', header: 'Nom', width: 200 }, { id: 'ville', header: 'Ville' }]
    const { container } = render(<DataTable data={DATA} columns={cols} />, { wrapper })
    const styled = container.querySelector('[style*="--dt-col-"]')
    expect(styled).toBeTruthy()
  })
})

/* ============================== ARC49/ARC53 — ÉCHAPPATOIRES ADDITIVES ============================== */

describe('ARC49/ARC53 — extensions opt-in (chemin de l\'argent)', () => {
  it('tableClassName ajoute une classe à la <table> sans retirer les classes du moteur', () => {
    const { container } = renderTable({ tableClassName: 'data-table' })
    const table = container.querySelector('[data-dt-table] table')
    expect(table.className).toContain('data-table')
    // Les classes historiques du moteur restent présentes.
    expect(table.className).toContain('border-collapse')
  })

  it('tableRole="table" remplace le rôle grid par défaut (getByRole table)', () => {
    const { container } = renderTable({ tableRole: 'table' })
    expect(container.querySelector('[data-dt-table] table[role="table"]')).toBeTruthy()
    expect(container.querySelector('[data-dt-table] table[role="grid"]')).toBeNull()
  })

  it('sans tableRole, le rôle grid par défaut est INCHANGÉ', () => {
    const { container } = renderTable()
    expect(container.querySelector('[data-dt-table] table[role="grid"]')).toBeTruthy()
  })

  it('renderHeaderRow remplace l\'en-tête intégré par des <th> personnalisés', () => {
    const { container } = renderTable({
      renderHeaderRow: () => (
        <>
          <th className="w-8">Sel</th>
          <th>Réf perso</th>
        </>
      ),
    })
    const ths = container.querySelectorAll('[data-dt-table] thead th')
    expect(ths.length).toBe(2)
    expect(ths[1].textContent).toBe('Réf perso')
    // L'en-tête de tri intégré n'est pas rendu (aucun bouton « Trier par »).
    expect(container.querySelector('thead button[aria-label^="Trier par"]')).toBeNull()
  })

  it('renderRow rend une ligne ENTIÈRE custom et n\'ajoute aucune cellule technique', () => {
    const { container } = render(
      <DataTable
        data={DATA}
        columns={COLUMNS}
        selectable
        tableClassName="data-table"
        tableRole="table"
        renderRow={(row, api) => (
          <tr data-custom-row data-key={api.rowKey}>
            <td>{row.nom}</td>
            <td>{row.ville}</td>
          </tr>
        )}
      />,
      { wrapper },
    )
    const rows = container.querySelectorAll('tbody tr[data-custom-row]')
    expect(rows.length).toBe(DATA.length)
    // Chaque ligne custom n'a QUE ses 2 cellules (pas de case/actions injectées).
    expect(rows[0].querySelectorAll('td').length).toBe(2)
    // Pas de vue cartes mobile dupliquée (une seule table data-table).
    expect(container.querySelector('[data-dt-cards]')).toBeNull()
    // Aucun <colgroup> technique injecté en mode ligne custom.
    expect(container.querySelector('[data-dt-table] colgroup')).toBeNull()
  })

  it('renderRow + renderHeaderRow : le moteur n\'ajoute AUCUNE colonne technique', () => {
    const { container } = render(
      <DataTable
        data={DATA}
        columns={COLUMNS}
        selectable
        renderHeaderRow={() => <th>Réf</th>}
        renderRow={(row) => (
          <tr data-custom-row>
            <td>{row.nom}</td>
          </tr>
        )}
      />,
      { wrapper },
    )
    // L'en-tête ne contient QUE le <th> fourni (pas de case « tout sélectionner »).
    const ths = container.querySelectorAll('[data-dt-table] thead th')
    expect(ths.length).toBe(1)
    expect(ths[0].textContent).toBe('Réf')
  })

  it('renderRow expose une API de sélection reliée à l\'état du moteur', async () => {
    const user = userEvent.setup()
    const { container } = render(
      <DataTable
        data={DATA}
        columns={COLUMNS}
        selectable
        bulkActions={() => [{ id: 'x', label: 'Agir' }]}
        renderRow={(row, api) => (
          <tr data-custom-row>
            <td>
              <button type="button" onClick={api.toggleSelect}>
                {api.isSelected ? 'Sélectionné' : `Sélectionner ${row.nom}`}
              </button>
            </td>
          </tr>
        )}
      />,
      { wrapper },
    )
    // Aucune barre de masse tant que rien n'est sélectionné.
    expect(screen.queryByRole('region', { name: /sélectionnée/i })).not.toBeInTheDocument()
    await user.click(screen.getByText('Sélectionner Kasri'))
    // La sélection du moteur reflète le clic → la barre de masse apparaît.
    expect(screen.getByRole('region', { name: /sélectionnée/i })).toBeInTheDocument()
    expect(container.querySelector('tbody')).toBeTruthy()
  })

  it('renderRow : panneaux dépliables nommés à état indépendant par ligne', async () => {
    const user = userEvent.setup()
    render(
      <DataTable
        data={DATA}
        columns={COLUMNS}
        expandedPanels={['A', 'B']}
        renderRow={(row, api) => (
          <>
            <tr data-custom-row>
              <td>
                <button type="button" onClick={() => api.togglePanel('A')}>{`A-${row.id}`}</button>
                <button type="button" onClick={() => api.togglePanel('B')}>{`B-${row.id}`}</button>
              </td>
            </tr>
            {api.isPanelOpen('A') && <tr data-panel-a><td>{`panneau A de ${row.id}`}</td></tr>}
            {api.isPanelOpen('B') && <tr data-panel-b><td>{`panneau B de ${row.id}`}</td></tr>}
          </>
        )}
      />,
      { wrapper },
    )
    // Ouvre le panneau A de la ligne 1 : seul lui apparaît (B fermé, autres lignes fermées).
    await user.click(screen.getByText('A-1'))
    expect(screen.getByText('panneau A de 1')).toBeInTheDocument()
    expect(screen.queryByText('panneau B de 1')).not.toBeInTheDocument()
    expect(screen.queryByText('panneau A de 2')).not.toBeInTheDocument()
    // Ouvre B de la même ligne : A ET B ouverts simultanément (indépendants).
    await user.click(screen.getByText('B-1'))
    expect(screen.getByText('panneau A de 1')).toBeInTheDocument()
    expect(screen.getByText('panneau B de 1')).toBeInTheDocument()
  })

  it('hideToolbar supprime la barre d\'outils intégrée (recherche/export)', () => {
    // Par défaut la barre existe (champ de recherche globale).
    const { container: withBar } = renderTable()
    expect(withBar.querySelector('input[aria-label="Recherche globale"]')).toBeTruthy()
    // Avec hideToolbar, la barre disparaît.
    const { container: noBar } = renderTable({ hideToolbar: true })
    expect(noBar.querySelector('input[aria-label="Recherche globale"]')).toBeNull()
  })
})
