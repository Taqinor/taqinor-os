import { useParams } from 'react-router-dom'
import DocumentsArchive from './DocumentsArchive'

// N32 — Page archive documentaire d'un chantier
// (route /reporting/archive/chantier/:id).
export default function ArchiveChantierPage() {
  const { id } = useParams()
  return (
    <div className="ui-root page" style={{ maxWidth: 1000 }}>
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>Archive documentaire — chantier</h2>
      </div>
      <DocumentsArchive kind="chantier" id={id} />
    </div>
  )
}
