import { ChevronLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

/* La barre « ‹ Projets » des écrans Projet et Archive. */
export default function BarreRetourProjets() {
  const navigate = useNavigate()
  return (
    <div className="ep-barre">
      <button type="button" className="ep-retour" onClick={() => navigate('/taches/projets')}>
        <ChevronLeft className="i" aria-hidden="true" />Projets
      </button>
    </div>
  )
}
