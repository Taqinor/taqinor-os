import { useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { Button, Card } from '../../../ui'

/* ============================================================================
   ACAL405 (D-ACAL-31) — « DÉMARRAGE RAPIDE » : LES VALEURS PUBLIÉES PROPOSÉES.
   ----------------------------------------------------------------------------
   `GET calepinages/profil-depart/` (ACAL403, contrat
   `calepinage_profil_depart.json`) sert `{valeurs, sans_source}`. AUCUNE valeur
   n'est écrite ici : « Appliquer aux réglages vides » appelle `POST` (le
   serveur ne touche que les clés VIDES), puis `onChange` fait relire les
   réglages. L'état « à appliquer » / « déjà saisie » se lit sur les réglages
   SERVIS (`reglages[section][cle]`), jamais sur un brouillon.
   ========================================================================== */

const saisie = (reglages, { section, cle }) => {
  const ligne = reglages?.[section]?.[cle]
  return Boolean(ligne) && typeof ligne === 'object'
    && ligne.valeur !== null && ligne.valeur !== undefined
}

const texte = (v) => (typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v))

export default function DemarrageRapide({ reglages, peutApprouver, onChange }) {
  const [profil, setProfil] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [message, setMessage] = useState(null)
  const [occupe, setOccupe] = useState(false)

  useEffect(() => {
    let annule = false
    Promise.resolve(calepinageApi.parametres.profilDepart())
      .then((res) => { if (!annule) setProfil(res?.data ?? null) })
      .catch(() => { if (!annule) setErreur('Profil de départ indisponible.') })
    return () => { annule = true }
  }, [])

  const agir = async (appel, phrase) => {
    setOccupe(true)
    setMessage(null)
    setErreur(null)
    try {
      const res = await appel()
      setMessage(phrase(res?.data ?? {}))
      await onChange?.()
    } catch (e) {
      const detail = e?.response?.data?.detail
      setErreur(typeof detail === 'string' && detail
        ? detail : 'Le geste n’a pas pu être fait : rien n’a changé.')
    } finally {
      setOccupe(false)
    }
  }

  const valeurs = Array.isArray(profil?.valeurs) ? profil.valeurs : []
  const sansSource = Array.isArray(profil?.sans_source) ? profil.sans_source : []

  return (
    <Card className="mt-5 p-4" data-testid="acal405-demarrage">
      <h2 className="text-base font-semibold text-foreground">Démarrage rapide</h2>
      <p className="mt-1 text-xs text-muted-foreground">
        Valeurs publiées par leur source, proposées pour les réglages vides :
        elles ne sont pas mesurées sur vos sites et ne remplacent jamais une saisie.
      </p>
      {erreur && (
        <p role="alert" className="mt-2 text-xs text-destructive" data-testid="acal405-erreur">{erreur}</p>
      )}
      <ul className="mt-2 text-sm">
        {valeurs.map((v) => (
          <li
            key={`${v.section}-${v.cle}`}
            className="border-t border-border/60 py-1"
            data-testid={`acal405-valeur-${v.cle}`}
          >
            <span className="font-medium">{v.cle}</span>{' : '}
            <span className="tabular-nums">{texte(v.valeur)}{v.unite ? ` ${v.unite}` : ''}</span>
            {' — '}
            <span data-testid={`acal405-etat-${v.cle}`}>
              {saisie(reglages, v) ? 'déjà saisie' : 'à appliquer'}
            </span>
            <span className="block text-xs text-muted-foreground">
              {v.reference}{' — '}
              <a href={v.url} target="_blank" rel="noreferrer" className="underline">{v.url}</a>
              {' — lu le '}{v.date_lecture}
            </span>
          </li>
        ))}
      </ul>
      {sansSource.length > 0 && (
        <details className="mt-2 text-xs" data-testid="acal405-sans-source">
          <summary className="cursor-pointer text-muted-foreground">
            {sansSource.length} clés sans source (laissées vides)
          </summary>
          <ul className="mt-1">
            {sansSource.map((s) => <li key={`${s.section}-${s.cle}`}>{s.cle} — {s.motif}</li>)}
          </ul>
        </details>
      )}
      {peutApprouver && (
        <div className="mt-3 flex flex-wrap gap-3">
          <Button
            type="button"
            size="sm"
            disabled={occupe}
            data-testid="acal405-appliquer"
            onClick={() => agir(
              () => calepinageApi.parametres.appliquerProfilDepart(),
              (d) => `${(d.appliquees || []).length} valeurs appliquées`,
            )}
          >
            Appliquer aux réglages vides
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={occupe}
            data-testid="acal405-retirer"
            onClick={() => agir(
              () => calepinageApi.parametres.retirerProfilDepart(),
              (d) => `${(d.retirees || []).length} valeurs retirées`,
            )}
          >
            Retirer le profil
          </Button>
        </div>
      )}
      {message && (
        <p role="status" className="mt-2 text-sm text-muted-foreground" data-testid="acal405-message">{message}</p>
      )}
    </Card>
  )
}
