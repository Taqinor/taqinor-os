import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import calepinageApi from '../../api/calepinageApi'
import useResource from '../../hooks/useResource'
import { renderTrustedSvg } from '../../lib/trustedSvg'
import { Button, Card, Input, Label } from '../../ui'
import RetourAtelier from './atelier/RetourAtelier'
import { telechargerBlob } from './exportImage'
import { corpsEdition, exporterSchemaPng, exporterSchemaSvg, motifDuRefusDxf, nomFichierSchema } from './SchemaUnifilairePanel.helpers'
import EtatEcranAtelier from './atelier/EtatEcranAtelier'

/* ACAL44 — le motif d'un bouton d'écriture en lecture seule (devis lié figé). */
const MOTIF_LECTURE_SEULE = 'Conception figée : révisez le devis (nouvelle version) pour la modifier.'

const LISTES = [
  { cle: 'manquantes', titre: 'Fiche technique incomplète' },
  { cle: 'bloquants', titre: 'Conception non conforme' },
]

function Motifs({ donnees }) {
  const blocs = LISTES
    .map(({ cle, titre }) => ({ titre, cle, lignes: donnees?.[cle] || [] }))
    .filter((bloc) => bloc.lignes.length > 0)
  if (!blocs.length) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="cal195-sans-motif">
        Aucun schéma pour cette conception.
      </p>
    )
  }
  return blocs.map((bloc) => (
    <div key={bloc.cle} className="flex flex-col gap-1" data-testid={`cal195-${bloc.cle}`}>
      <div className="flex items-center gap-2 text-sm font-medium">
        <AlertCircle size={15} aria-hidden="true" />
        {bloc.titre}
      </div>
      <ul className="list-disc pl-5 text-sm text-muted-foreground">
        {bloc.lignes.map((ligne) => <li key={ligne}>{ligne}</li>)}
      </ul>
    </div>
  ))
}

function EditionSchema({ id, donnees, onPoste, lectureSeule = false }) {
  const blocs = Array.isArray(donnees?.blocs) ? donnees.blocs : []
  const [saisie, setSaisie] = useState({ libelles: {}, reperes: {} })
  const [erreurs, setErreurs] = useState({})
  const [enCours, setEnCours] = useState(false)
  if (blocs.length === 0) return null

  const corps = corpsEdition(blocs, saisie)
  const modifie = Object.keys(corps).length > 0
  const poser = (rubrique, clef, valeur) => setSaisie((s) => ({ ...s, [rubrique]: { ...s[rubrique], [clef]: valeur } }))

  const enregistrer = (evenement) => {
    evenement.preventDefault()
    setEnCours(true)
    setErreurs({})
    calepinageApi.calepinages.enregistrerEditionSld(id, corps)
      .then((reponse) => {
        onPoste(reponse?.data)
        setSaisie({ libelles: {}, reperes: {} })
      })
      .catch((err) => {
        const donneesRefus = err?.response?.data
        const parChamp = {}
        if (donneesRefus && typeof donneesRefus === 'object') {
          for (const [cle, m] of Object.entries(donneesRefus)) parChamp[cle] = Array.isArray(m) ? m.join(' ') : String(m)
        }
        setErreurs(Object.keys(parChamp).length ? parChamp : { edition: 'Édition non enregistrée : le serveur n’a pas accepté la saisie.' })
      })
      .finally(() => setEnCours(false))
  }

  const refus = (rubrique, clef) => erreurs[`edition.${rubrique}.${clef}`]
  const connus = new Set(blocs.flatMap((b) => [`edition.libelles.${b.clef}`, `edition.reperes.${b.clef}`]))
  const generaux = Object.entries(erreurs).filter(([cle]) => !connus.has(cle))

  return (
    <form className="flex flex-col gap-3" onSubmit={enregistrer} data-testid="acal161-edition">
      <h3 className="text-sm font-semibold">Libellés et repères des blocs</h3>
      {generaux.map(([cle, m]) => (
        <p key={cle} role="alert" className="text-sm text-destructive" data-testid="acal161-bandeau">{`${cle} : ${m}`}</p>
      ))}
      <ul className="flex flex-col gap-2">
        {blocs.map((bloc) => (
          <li key={bloc.clef} className="grid gap-2 sm:grid-cols-2" data-testid={`acal161-bloc-${bloc.clef}`}>
            {[['libelles', 'titre', 'Libellé'], ['reperes', 'repere', 'Repère']].map(([rubrique, cle, libelle]) => (
              <div key={rubrique} className="flex flex-col gap-1">
                <Label htmlFor={`acal161-${rubrique}-${bloc.clef}`}>{`${libelle} — ${bloc.clef}`}</Label>
                <Input
                  id={`acal161-${rubrique}-${bloc.clef}`}
                  value={saisie[rubrique][bloc.clef] ?? (bloc[cle] ?? '')}
                  invalid={Boolean(refus(rubrique, bloc.clef))}
                  onChange={(e) => poser(rubrique, bloc.clef, e.target.value)}
                />
                {refus(rubrique, bloc.clef)
                  ? <p className="text-xs text-destructive" data-testid={`acal161-erreur-${rubrique}-${bloc.clef}`}>{refus(rubrique, bloc.clef)}</p>
                  : null}
              </div>
            ))}
          </li>
        ))}
      </ul>
      <div>
        <Button
          type="submit"
          disabled={lectureSeule || !modifie || enCours}
          title={lectureSeule ? MOTIF_LECTURE_SEULE : undefined}
          data-testid="acal161-enregistrer"
        >
          {enCours ? 'Enregistrement…' : 'Enregistrer l’édition'}
        </Button>
      </div>
    </form>
  )
}

export default function SchemaUnifilairePanel({ calepinageId, lectureSeule = false }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data: lu, loading, error } = useResource(
    () => calepinageApi.calepinages.schemaUnifilaire(id), id,
    { select: (r) => r.data, errorMessage: 'Schéma unifilaire indisponible.' },
  )
  // ACAL161 — la réponse du POST d'édition (le MÊME document, édition appliquée) remplace
  // la lecture : le SVG relu porte le texte, sans second GET.
  const [poste, setPoste] = useState(null)
  const data = poste ?? lu

  const balisage = renderTrustedSvg(data?.svg)
  const [motifExport, setMotifExport] = useState(null)
  const [dxfEnCours, setDxfEnCours] = useState(false)

  // CALX236 — le clic sérialise le SVG déjà reçu (`data.svg`) : aucun second
  // appel à `schemaUnifilaire()`, aucune route neuve.
  const exporterPng = () => {
    setMotifExport(null)
    exporterSchemaPng(data.svg, nomFichierSchema(data?.calepinage, 'png'))
      .catch((err) => setMotifExport(err?.message || 'Export PNG impossible sur ce navigateur.'))
  }
  const telechargerSvg = () => {
    exporterSchemaSvg(data.svg, nomFichierSchema(data?.calepinage, 'svg'))
  }
  // CALX235 — le SEUL appel réseau de ce panneau : le DXF est produit par le
  // serveur depuis le même dessin, il n'est pas dans le DOM.
  const telechargerDxf = () => {
    setMotifExport(null)
    setDxfEnCours(true)
    calepinageApi.calepinages.sldDxf(id)
      .then((reponse) => {
        telechargerBlob(reponse.data, nomFichierSchema(data?.calepinage, 'dxf'))
      })
      .catch(async (err) => { setMotifExport(await motifDuRefusDxf(err)) })
      .finally(() => setDxfEnCours(false))
  }

  if (loading || error) {
    return <EtatEcranAtelier id={id} loading={loading} error={error} testIdErreur="cal195-erreur" />
  }

  return (
    <>
      <RetourAtelier calepinageId={id} />
      <Card className="flex flex-col gap-3 p-4" data-testid="cal195-panneau">
      <h2 className="text-base font-semibold">Schéma unifilaire</h2>
      {balisage
        ? (
          <>
            <div
              data-testid="cal195-svg"
              /* Le SVG vient du serveur, jamais d'une saisie. Il passe malgré
                 tout par `renderTrustedSvg` (VX120, défense en profondeur) :
                 un balisage capable d'exécuter du code n'est PAS inséré — on
                 montre alors les motifs plutôt qu'un cadre piégé. */
              dangerouslySetInnerHTML={balisage}
            />
            {/* CALX236 — les boutons n'existent QUE quand un schéma est
                affiché : `svg` nul n'a rien à exporter. */}
            <div className="flex flex-wrap gap-2" data-testid="calx236-export">
              <Button type="button" onClick={exporterPng} data-testid="calx236-exporter-png">
                Exporter en PNG
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={telechargerSvg}
                data-testid="calx236-telecharger-svg"
              >
                Télécharger le SVG
              </Button>
              {/* CALX235/236 — le DXF : même dessin, repris par un bureau
                  d'études. Produit par le serveur, donc un appel réseau. */}
              <Button
                type="button"
                variant="outline"
                onClick={telechargerDxf}
                disabled={dxfEnCours}
                data-testid="calx235-telecharger-dxf"
              >
                {dxfEnCours ? 'Préparation du DXF…' : 'Télécharger le DXF'}
              </Button>
            </div>
            {motifExport
              ? <p className="text-sm text-destructive" data-testid="calx236-erreur-export">{motifExport}</p>
              : null}
            <EditionSchema id={id} donnees={data} onPoste={setPoste} lectureSeule={lectureSeule} />
          </>
        )
        : <Motifs donnees={data} />}
    </Card>
    </>
  )
}
