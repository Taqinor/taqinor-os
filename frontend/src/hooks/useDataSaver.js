// NTMOB17 — abonnement React au mode « Économie de données ».
// La PRÉFÉRENCE elle-même (persistance localStorage) vit dans
// `pages/preferences/prefs.js` avec toutes les autres — ce hook n'est que le
// pont React : il lit la valeur au montage et se remet à jour quand elle
// bascule, y compris dans un AUTRE onglet (`storage`) ou dans le même onglet
// (`DATA_SAVER_EVENT`, que `localStorage` seul n'émet jamais localement).
import { useEffect, useState } from 'react'
import {
  DATA_SAVER_EVENT, DATA_SAVER_KEY, getDataSaverPref,
} from '../pages/preferences/prefs'

export default function useDataSaver() {
  const [enabled, setEnabled] = useState(getDataSaverPref)

  useEffect(() => {
    const sync = () => setEnabled(getDataSaverPref())
    const onStorage = (e) => {
      if (!e.key || e.key === DATA_SAVER_KEY) sync()
    }
    window.addEventListener(DATA_SAVER_EVENT, sync)
    window.addEventListener('storage', onStorage)
    // Une bascule a pu survenir entre le premier rendu et cet effet.
    sync()
    return () => {
      window.removeEventListener(DATA_SAVER_EVENT, sync)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  return enabled
}
