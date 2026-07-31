import { useState } from 'react'
import { Upload } from 'lucide-react'
import { Button } from '../../ui'
import ExcelImport from '../../components/ExcelImport'

/* ============================================================================
   NTEDU36 — Écran « Import CSV élèves » (migration depuis Excel/ancien
   système). Réutilise EXCLUSIVEMENT le composant d'import générique
   `ExcelImport` (cible serveur `eleves_education`, apps/dataimport) — jamais
   un moteur d'import maison. Une ligne en erreur (ex. classe inconnue) ne
   bloque jamais les lignes valides : le rapport d'erreurs est téléchargeable
   depuis le résultat de l'import (bouton déjà intégré à ExcelImport).
   ========================================================================== */

export default function ImportPage() {
  const [open, setOpen] = useState(false)

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Upload size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Import CSV élèves</h1>
      </div>
      <p style={{ color: '#64748b', marginBottom: 16 }}>
        Migration en masse depuis Excel ou un ancien système (colonnes nom, prénom,
        classe, famille…). Un aperçu des 10 premières lignes s&apos;affiche avant
        l&apos;import ; les lignes en erreur (ex. classe inconnue) n&apos;empêchent
        jamais les lignes valides d&apos;être importées et restent téléchargeables
        en CSV.
      </p>
      <Button onClick={() => setOpen(true)}>Importer un fichier</Button>
      {open && (
        <ExcelImport
          target="eleves_education"
          onClose={() => setOpen(false)}
          onDone={() => setOpen(false)}
        />
      )}
    </div>
  )
}
