// EDC3 — la table des lignes est enrobée par la barre de défilement collante :
// l'en-tête porte la classe collante (`lines-thead-collant`), la table la
// classe `separate` (`lines-table-separe` : les bordures survivent au
// collage), le conteneur garde `lines-table-wrap` (empilement mobile inchangé)
// et la barre proxy suit le conteneur en frère.
// Run : npx vitest run src/pages/ventes/generator/LigneTable.edc3.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import LigneTable from './LigneTable'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

// R2 — une ligne rendue monte <DevisLineRow> → <ProduitPicker> (Redux) : mocké,
// comme dans DevisLineRow.test.jsx (la table est testée, pas le sélecteur).
vi.mock('../../../components/ProduitPicker', () => ({
  default: function ProduitPickerMock(props) {
    return <div data-testid="produit-picker-mock">{props.value ?? 'aucun'}</div>
  },
}))

const noop = vi.fn()

function rendre(props = {}) {
  return render(
    <ThemeProvider><LigneTable
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
    /></ThemeProvider>,
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

// ── R2 (fondateur 28/10/2026) — en-tête de groupe client dans la table ──────
// Run : npx vitest run src/pages/ventes/generator/LigneTable.edc3.test.jsx
describe('R2 — LigneTable : « Tableau de protection AC/DC — total HT » au-dessus des composants, toujours éditables', () => {
  const lignes = [
    { _key: 'k1', produit: '12', designation: 'Panneau', quantite: '10', prix_unit_ttc: '1200', taux_tva: '20', typeLigne: 'produit', groupeClient: null },
    { _key: 'k2', produit: '88', designation: 'Coffret DC C&I', quantite: '2', prix_unit_ttc: '1800', taux_tva: '20', typeLigne: 'produit', groupeClient: 'tableau_ci' },
    { _key: 'k3', produit: '90', designation: 'Câble AC', quantite: '30', prix_unit_ttc: '60', taux_tva: '20', typeLigne: 'produit', groupeClient: null },
    { _key: 'k4', produit: '91', designation: 'Smart Meter', quantite: '1', prix_unit_ttc: '2160', taux_tva: '20', typeLigne: 'produit', groupeClient: 'tableau_ci' },
  ]

  it('un en-tête par groupe, total HT du groupe, composants regroupés dessous et toujours des lignes éditables', () => {
    const { container } = rendre({ lines: lignes, lignesRemiseesTtc: [null, null, null, null] })
    const entetes = container.querySelectorAll('tr.lines-groupe-client')
    expect(entetes).toHaveLength(1)
    expect(entetes[0]).toHaveAttribute('data-groupe-client', 'tableau_ci')
    expect(entetes[0].textContent).toContain('Tableau de protection AC/DC')
    expect(entetes[0].textContent).toContain('2 composants')
    // 2 × 1 500 HT + 1 × 1 800 HT = 4 800 HT (TTC saisi à 20 %).
    expect(entetes[0].querySelector('[data-groupe-total-ht]').textContent.replace(/[\s\u202f\u00a0]/g, '')).toMatch(/^4800/)
    const ordre = [...container.querySelectorAll('tbody tr')].map((tr) =>
      tr.classList.contains('lines-groupe-client') ? 'entete' : tr.getAttribute('data-line-key'))
    expect(ordre).toEqual(['k1', 'entete', 'k2', 'k4', 'k3'])
    // Chaque composant garde sa propre ligne éditable (quantité saisissable).
    for (const key of ['k2', 'k4']) {
      const tr = container.querySelector(`tr[data-line-key="${key}"]`)
      expect(tr.querySelector('input[type="number"]')).not.toBeNull()
    }
  })

  it('[Coffret DC, Panneau, Parafoudre AC] : bloc affiché c, f puis p ; Monter/Descendre bornés sur la position AFFICHÉE', () => {
    const trio = [
      { _key: 'c', produit: '88', designation: 'Coffret DC C&I', quantite: '1', prix_unit_ttc: '1800', taux_tva: '20', typeLigne: 'produit', groupeClient: 'tableau_ci' },
      { _key: 'p', produit: '12', designation: 'Panneau', quantite: '10', prix_unit_ttc: '1200', taux_tva: '20', typeLigne: 'produit', groupeClient: null },
      { _key: 'f', produit: '91', designation: 'Parafoudre AC', quantite: '1', prix_unit_ttc: '360', taux_tva: '20', typeLigne: 'produit', groupeClient: 'tableau_ci' },
    ]
    const onMoveUp = vi.fn()
    const { container } = rendre({ lines: trio, lignesRemiseesTtc: [null, null, null], onMoveUp })
    const ordre = [...container.querySelectorAll('tbody tr')].map((tr) =>
      tr.classList.contains('lines-groupe-client') ? 'entete' : tr.getAttribute('data-line-key'))
    expect(ordre).toEqual(['entete', 'c', 'f', 'p'])
    const boutons = (key) => [...container.querySelectorAll(`tr[data-line-key="${key}"] button`)]
      .filter((b) => /monter|descendre/i.test(b.getAttribute('aria-label') || b.title || ''))
    const etat = (key) => boutons(key).map((b) => b.disabled)
    expect(etat('c')).toEqual([true, false])   // premier affiché : Monter inactif
    expect(etat('f')).toEqual([false, false])  // milieu affiché (index 2 du state) : les deux actifs
    expect(etat('p')).toEqual([false, true])   // dernier affiché : Descendre inactif
    boutons('p')[0].click()
    expect(onMoveUp).toHaveBeenCalledWith('p')
  })

  it('l’en-tête dit le total HT APRÈS remise globale quand le miroir la donne', () => {
    const { container } = rendre({ lines: lignes, lignesRemiseesTtc: [null, 3240, null, 1944], montrerRemise: true })
    // 3 240 + 1 944 TTC remisés ⇒ 2 700 + 1 620 = 4 320 HT (catalogue : 4 800).
    expect(container.querySelector('[data-groupe-total-ht]').textContent.replace(/[\s\u202f\u00a0]/g, '')).toMatch(/^4320/)
  })

  it('R3 — un groupe « supervision_ci » reçoit son en-tête « Supervision & comptage », composants toujours éditables', () => {
    const avecSupervision = [
      { _key: 's1', produit: '91', designation: 'Smart Meter', quantite: '1', prix_unit_ttc: '2160', taux_tva: '20', typeLigne: 'produit', groupeClient: 'supervision_ci' },
      { _key: 's2', produit: '92', designation: 'Clé wifi', quantite: '1', prix_unit_ttc: '600', taux_tva: '20', typeLigne: 'produit', groupeClient: 'supervision_ci' },
    ]
    const { container } = rendre({ lines: avecSupervision, lignesRemiseesTtc: [null, null] })
    const entetes = container.querySelectorAll('tr.lines-groupe-client')
    expect(entetes).toHaveLength(1)
    expect(entetes[0]).toHaveAttribute('data-groupe-client', 'supervision_ci')
    expect(entetes[0].textContent).toContain('Supervision & comptage')
    // 1 800 + 500 = 2 300 HT.
    expect(entetes[0].querySelector('[data-groupe-total-ht]').textContent.replace(/[\s  ]/g, '')).toMatch(/^2300/)
    for (const key of ['s1', 's2']) {
      expect(container.querySelector(`tr[data-line-key="${key}"] input[type="number"]`)).not.toBeNull()
    }
  })

  it('sans groupe_client, aucun en-tête : la table d’hier, ligne par ligne', () => {
    const { container } = rendre({ lines: lignes.map((l) => ({ ...l, groupeClient: null })), lignesRemiseesTtc: [null, null, null, null] })
    expect(container.querySelectorAll('tr.lines-groupe-client')).toHaveLength(0)
    expect([...container.querySelectorAll('tbody tr')].map((tr) => tr.getAttribute('data-line-key'))).toEqual(['k1', 'k2', 'k3', 'k4'])
  })
})
