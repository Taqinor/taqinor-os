import { urlFichierCalepinage, crossOriginFichierCalepinage } from '../../../lib/calage/fichierCalepinage'
import { CATEGORIES_PHOTO } from './releveTelephone'

/* Maquette Telephone — « Photos » + « N sur M » + barre dorée + tuiles (pointillées avec
   l'appareil photo quand la catégorie n'a pas encore de photo). Les catégories sont les
   genres RÉELS de `PhotoSite.Genre` (3, pas les 6 sujets d'exemple de la maquette). */

function Appareil() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="3.5" />
    </svg>
  )
}

export default function TuilesPhotos({ photos, genresEnFile, enCours, message, onDeposer }) {
  const tuiles = CATEGORIES_PHOTO.map((c) => ({
    ...c,
    photo: photos.find((p) => p.genre === c.genre) ?? null,
    enFile: genresEnFile.includes(c.genre),
  }))
  const faites = tuiles.filter((t) => t.photo || t.enFile).length
  const total = tuiles.length
  return (
    <section className="cal-tel-section" data-testid="releve-photos">
      <div className="cal-tel-titre-ligne">
        <h1 className="cal-tel-h">Photos</h1>
        <span className="cal-tel-compte" data-testid="releve-photos-compte">{`${faites} sur ${total}`}</span>
      </div>
      <div className="cal-tel-barre" role="progressbar" aria-label="Photos prises"
        aria-valuemin={0} aria-valuemax={total} aria-valuenow={faites}>
        <div className="cal-tel-barre-plein" style={{ width: `${Math.round((faites / total) * 100)}%` }} />
      </div>
      <div className="cal-tel-tuiles">
        {tuiles.map((t) => (t.photo || t.enFile ? (
          <div key={t.genre} className="cal-tel-tuile-photo" data-testid={`releve-photo-${t.genre}`}>
            {t.photo && (
              <img src={urlFichierCalepinage(t.photo.url)} crossOrigin={crossOriginFichierCalepinage()} alt="" />
            )}
            <span className="cal-tel-tuile-etiquette">{t.enFile && !t.photo ? `${t.libelle} · en attente` : t.libelle}</span>
          </div>
        ) : (
          <label key={t.genre} className="cal-tel-tuile-vide" data-testid={`releve-photo-${t.genre}`}>
            <input type="file" accept="image/png,image/jpeg" capture="environment" className="sr-only"
              disabled={enCours !== null} aria-label={`Prendre la photo « ${t.libelle} »`}
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; onDeposer(t.genre, f) }} />
            <Appareil />
            {enCours === t.genre ? 'Envoi…' : t.libelle}
          </label>
        )))}
      </div>
      {message && <p role="alert" className="cal-tel-erreur" data-testid="releve-photos-erreur">{message}</p>}
    </section>
  )
}
