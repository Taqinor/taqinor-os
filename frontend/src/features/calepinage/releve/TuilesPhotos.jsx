import { urlFichierCalepinage, crossOriginFichierCalepinage } from '../../../lib/calage/fichierCalepinage'
import { CATEGORIES_PHOTO } from './releveTelephone'

/* Maquette Telephone v2 — « Photos » + « N sur M » + M traits dorés (un par genre) + tuiles de 64 px (pointillées avec
   l'appareil photo quand la catégorie n'a pas encore de photo). Les catégories sont les
   genres RÉELS de `PhotoSite.Genre` (3, pas les 6 sujets d'exemple de la maquette : D-ACAL-68, ACAL1319). */

/* T4-X8-003 — la photo gardée ne montre pas l'appareil photo (qui inviterait à la reprendre) : une flèche d'envoi. */
function Envoi() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 16V4M7 9l5-5 5 5M5 20h14" />
    </svg>
  )
}

function Appareil() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="3.5" />
    </svg>
  )
}

export default function TuilesPhotos({ photos, genresEnFile, genresEnvoyes = [], enCours, message, onDeposer }) {
  const tuiles = CATEGORIES_PHOTO.map((c) => ({
    ...c,
    photo: photos.find((p) => p.genre === c.genre) ?? null,
    enFile: genresEnFile.includes(c.genre),
    envoyee: genresEnvoyes.includes(c.genre),
  }))
  const faites = tuiles.filter((t) => t.photo || t.enFile || t.envoyee).length
  const total = tuiles.length
  return (
    <section className="cal-tel-section cal-tel-photos" data-testid="releve-photos">
      <div className="cal-tel-titre-ligne">
        <h1 className="cal-tel-h">Photos</h1>
        <span className="cal-tel-compte" data-testid="releve-photos-compte"><b>{faites}</b>{` sur ${total}`}</span>
      </div>
      <div className="cal-tel-barre" role="progressbar" aria-label="Photos prises"
        aria-valuemin={0} aria-valuemax={total} aria-valuenow={faites}>
        {tuiles.map((t, i) => <span key={t.genre} className="cal-tel-barre-trait" data-fait={i < faites ? '' : undefined} />)}
      </div>
      <div className="cal-tel-tuiles">
        {tuiles.map((t) => (t.photo ? (
          <div key={t.genre} className="cal-tel-tuile-photo" data-testid={`releve-photo-${t.genre}`}>
            <img src={urlFichierCalepinage(t.photo.url)} crossOrigin={crossOriginFichierCalepinage()} alt="" />
            <span className="cal-tel-tuile-etiquette">{t.libelle}</span>
          </div>
        ) : t.enFile || t.envoyee ? (
          /* T4-U4-023 — la photo gardée (ou envoyée, en relecture) : le genre et son état sur deux lignes, en encre
             de la feuille — jamais une pastille blanche coupée sur fond clair. */
          <div key={t.genre} className="cal-tel-tuile-attente" data-testid={`releve-photo-${t.genre}`}>
            <Envoi />
            <span className="cal-tel-tuile-attente-genre">{t.libelle}</span>
            <span className="cal-tel-tuile-attente-etat" data-testid={`releve-photo-${t.genre}-etat`}>
              {t.enFile ? 'en attente d’envoi' : 'envoyée'}
            </span>
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
