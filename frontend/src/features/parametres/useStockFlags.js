import { useEffect, useState } from 'react'
import parametresApi from '../../api/parametresApi'

// ZSTK13 — drapeaux de capacité stock (barcode / lots-séries / colisage).
// Tous True par défaut = comportement actuel byte-identique tant que la
// société n'a rien désactivé dans Paramètres → Stock (`StockSection.jsx`,
// seul endroit où ils s'ÉDITENT). Ce hook les LIT seulement, pour masquer
// l'affichage correspondant dans les écrans stock concernés.
const DEFAULTS = {
  stock_lots_series_actif: true,
  stock_colisage_actif: true,
  stock_scan_actif: true,
}

export default function useStockFlags() {
  const [flags, setFlags] = useState(DEFAULTS)

  useEffect(() => {
    let active = true
    parametresApi.getProfile()
      .then((res) => {
        if (!active) return
        setFlags({
          stock_lots_series_actif: res.data?.stock_lots_series_actif ?? true,
          stock_colisage_actif: res.data?.stock_colisage_actif ?? true,
          stock_scan_actif: res.data?.stock_scan_actif ?? true,
        })
      })
      .catch(() => { if (active) setFlags(DEFAULTS) })
    return () => { active = false }
  }, [])

  return flags
}
