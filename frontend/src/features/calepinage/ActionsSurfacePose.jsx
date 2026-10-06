/* ACAL345 — les ACTIONS d'une surface de pose (terrain ET ombrière) : calculer,
   enregistrer, liste des surfaces enregistrées, nouvelle, supprimer, état du
   document et message. Une seule copie, pilotée par `useSurfacePose` ; seuls
   le préfixe des `data-testid` et les libellés changent d'un écran à l'autre. */
import { MESSAGE_ILLISIBLE } from './useDocumentCalepinage'

/**
 * @param {object} p
 * @param {object} p.pose       le retour de `useSurfacePose`
 * @param {boolean} p.persister
 * @param {string} p.prefixe    préfixe des `data-testid` (`cal-terrain`, `cal-ombriere`)
 * @param {object} p.libelles   { calculer, enregistrer, groupe, liste, defaut, nouvelle }
 * @param {Function} p.onCalculer construit la demande de l'écran puis `pose.poser`
 */
export default function ActionsSurfacePose({ pose, persister, prefixe, libelles, onCalculer }) {
  const {
    doc, reponse, enCours, message, surfaces, repereCourant, dejaEnregistree,
    enregistrer, supprimer, choisirSurface, nouvelleSurface,
  } = pose
  return (
    <>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onCalculer}
          disabled={enCours}
          data-testid={`${prefixe}-calculer`}
          className="rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200"
        >
          {enCours ? 'Calcul en cours…' : libelles.calculer}
        </button>
        {persister && (
          <button
            type="button"
            onClick={enregistrer}
            disabled={doc.etat !== 'ok' || !reponse}
            title={reponse ? undefined : 'Calculez le plan avant d’enregistrer'}
            data-testid={`${prefixe}-enregistrer`}
            className="rounded border border-white/15 px-4 py-2 text-sm font-semibold text-white"
          >
            {libelles.enregistrer}
          </button>
        )}
      </div>

      {persister && surfaces.length > 0 && (
        <div className="mt-4" role="group" aria-label={libelles.groupe}>
          <p className="tech-label text-lune-faint">{libelles.liste}</p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {surfaces.map((surface) => (
              <li key={surface.id}>
                <button
                  type="button"
                  onClick={() => choisirSurface(surface)}
                  aria-pressed={surface.id === repereCourant}
                  className="rounded border border-white/15 px-3 py-1 text-sm text-white aria-pressed:bg-white/10"
                >
                  {`${surface.label || libelles.defaut} (${surface.id})`}
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={nouvelleSurface}
            className="mt-2 rounded border border-white/15 px-3 py-1 text-sm text-white"
          >
            {libelles.nouvelle}
          </button>
        </div>
      )}

      {persister && dejaEnregistree && (
        <button
          type="button"
          onClick={supprimer}
          disabled={doc.etat !== 'ok'}
          className="mt-3 rounded border border-red-300/40 px-3 py-1 text-sm text-red-300"
        >
          Supprimer cette surface
        </button>
      )}

      {persister && doc.etat === 'erreur' && (
        <p className="mt-3 text-sm text-red-300" role="alert"
         >{MESSAGE_ILLISIBLE}</p>
      )}

      {message && (
        <p className="mt-3 text-sm text-lune-soft" role="status"
          data-testid={`${prefixe}-message`}>{message}</p>
      )}
    </>
  )
}
