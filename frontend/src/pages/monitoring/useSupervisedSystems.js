import { useEffect, useState } from 'react'
import installationsApi from '../../api/installationsApi'
import monitoringApi from '../../api/monitoringApi'
import fetchAllPages from '../../utils/fetchAllPages'

/* WR6 — Hook partagé des écrans O&M : charge les configs de supervision (une
   par système) et les noms lisibles du parc installé, puis expose des entrées
   { id (config), installation, label, config }. */
export default function useSupervisedSystems() {
  const [systems, setSystems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    Promise.all([
      fetchAllPages((page, { page_size: pageSize } = {}) =>
        monitoringApi.getConfigs({ page, page_size: pageSize }).then((r) => r.data)),
      fetchAllPages((page, { page_size: pageSize } = {}) =>
        installationsApi.getInstallations({ parc: 1, page, page_size: pageSize }).then((r) => r.data)),
    ])
      .then(([c, i]) => {
        if (!active) return
        const configs = (Array.isArray(c) ? c : (c?.results ?? []))
        const insts = (Array.isArray(i) ? i : (i?.results ?? []))
        const names = new Map(insts.map((x) => [x.id, x]))
        setSystems(configs.map((cfg) => {
          const inst = names.get(cfg.installation)
          const label = inst
            ? `${inst.reference}${inst.client_nom ? ` — ${inst.client_nom}` : ''}`
            : `Système #${cfg.installation}`
          return { id: cfg.id, installation: cfg.installation, label, config: cfg }
        }))
      })
      .catch(() => { if (active) setSystems([]) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  return { systems, loading }
}
