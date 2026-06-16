import { useParams } from 'react-router-dom'
import DocumentsArchive from './DocumentsArchive'

// N32 — Page archive documentaire d'un client (route /reporting/archive/client/:id).
export default function ArchiveClientPage() {
  const { id } = useParams()
  return (
    <div className="page" style={{ maxWidth: 1000 }}>
      <div className="page-header">
        <h2>Archive documentaire — client</h2>
      </div>
      <DocumentsArchive kind="client" id={id} />
    </div>
  )
}
