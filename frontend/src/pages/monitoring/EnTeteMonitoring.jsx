import MonitoringNav from './MonitoringNav'

/* En-tête PARTAGÉ des écrans Supervision : titre, sous-titre, puis la barre de
   navigation du module. */
export default function EnTeteMonitoring({ titre, sousTitre }) {
  return (
    <>
      <div className="page-header">
        <h1 className="page-title">{titre}</h1>
        <div className="page-subtitle">
          {sousTitre}
        </div>
      </div>
      <MonitoringNav />
    </>
  )
}
