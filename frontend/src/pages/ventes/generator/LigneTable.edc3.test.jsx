// EDC3 — la table des lignes est enrobée par la barre de défilement collante :
// l'en-tête porte la classe collante (`lines-thead-collant`), la table la
// classe `separate` (`lines-table-separe` : les bordures survivent au
// collage), le conteneur garde `lines-table-wrap` (empilement mobile inchangé)
// et la barre proxy suit le conteneur en frère.
// Run : npx vitest run src/pages/ventes/generator/LigneTable.edc3.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import LigneTable from './LigneTable'

const noop = vi.fn()

function rendre(props = {}) {
  return render(
    <LigneTable
      lines={[]} produits={[]} linesTableRef={{ current: null }} canRenameLine
      tarifBadges={{}} quoteLogic={{ tvaPanneaux: 10, tvaStandard: 20 }}
      onSetField={noop} onDesignationBlur={noop} onProduitChange={noop}
      onProduitCreated={noop} onQuantiteChange={noop} onSetGroupe={noop}
      onRemove={noop} onMoveUp={noop} onMoveDown={noop}
      addLine={noop} addStructureLine={noop} handleSaveOrdreLignes={noop}
      savingOrdreLignes={false} multiMode="none" onMultiModeChange={noop}
      multiAccordionOpen={false} setMultiAccordionOpen={noop}
      nombreProprietes="" setNombreProprietes={noop} multiPreview={null}
      villaGroups={[{ index: 0, label: 'Équipement commun' }]}
      renameVillaGroup={noop} removeVillaGroup={noop} addVillaGroup={noop}
      errorLines={null} accessoiresOnly={false} setAccessoiresOnly={noop}
      lignesRemiseesTtc={[]} montrerRemise={false}
      {...props}
    />,
  )
}

describe('EDC3 — LigneTable : en-tête collant, table separate, barre proxy', () => {
  it('le thead porte la classe collante, la table la classe separate', () => {
    const { container } = rendre()
    const table = container.querySelector('table.lines-table')
    expect(table).toHaveClass('lines-table-separe')
    expect(table.querySelector('thead')).toHaveClass('lines-thead-collant')
  })

  it('le conteneur reste `.lines-table-wrap` (règles mobiles d\'empilement) et la barre proxy le suit', () => {
    const { container } = rendre()
    const wrap = container.querySelector('.lines-table-wrap')
    expect(wrap).toHaveClass('bdc-wrap')
    expect(wrap).toHaveAttribute('data-deborde', 'false')
    expect(wrap.querySelector('table.lines-table')).not.toBeNull()
    const proxy = wrap.nextElementSibling
    expect(proxy).toHaveClass('bdc-proxy')
    expect(proxy.hidden).toBe(true)
  })

  it('le ref de la table (VX90, focus de la nouvelle ligne) pointe toujours sur la table', () => {
    const ref = { current: null }
    const { container } = rendre({ linesTableRef: ref })
    expect(ref.current).toBe(container.querySelector('table.lines-table'))
  })
})
