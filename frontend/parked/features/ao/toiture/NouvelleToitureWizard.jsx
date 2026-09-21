/* AOF78 — Wizard « Nouvelle toiture » : LE point de création unique.
   ----------------------------------------------------------------------------
   Trois portes d'entrée — importer un plan (PDF/image/DXF), tracer from scratch,
   reprendre le contour depuis la carte — et UN SEUL objet Toiture en sortie, qui
   ouvre UN SEUL éditeur (`ATELIER`). Aucune porte n'a d'écran spécialisé : sinon
   on maintiendrait trois éditeurs, et le plan importé qu'on complète au tracé (ou
   le tracé qui reçoit un fond de plan a posteriori) serait impossible.

   Conséquence directe, verrouillée par les tests : les portes sont CUMULABLES et
   jamais définitives. On peut en cocher zéro, une, deux ou trois ; on peut en
   décocher une après l'avoir cochée ; et la toiture produite porte simplement la
   liste des portes ouvertes — jamais un « type » qui figerait l'écran suivant.

   Les panneaux concrets de chaque porte (ImportDxf/UnderlayPdf, OutilTrace,
   RepriseCarte) sont INJECTÉS par l'atelier via la prop `panneaux` : le wizard ne
   les importe pas, ce qui garde le point de création indépendant de la
   disponibilité de chaque porte (une porte sans panneau reste sélectionnable et
   se complétera dans l'atelier). */
import { useCallback, useMemo, useState } from 'react'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import { Button } from '../../../ui/Button'

/* L'unique éditeur ouvert par les trois branches. Sa valeur est assertée par le
   test : si un jour une porte ouvrait autre chose, le test rougit. */
const ATELIER = 'atelier-toiture'

const PORTES = [
  {
    cle: 'import',
    titre: 'Importer un plan',
    aide: 'PDF, image ou DXF — le plan sert de fond de calque, il ne remplace pas le tracé.',
  },
  {
    cle: 'trace',
    titre: 'Tracer la toiture',
    aide: 'Saisie au clavier ou à la souris, avec chaînes de cotes — sans aucun plan.',
  },
  {
    cle: 'carte',
    titre: 'Reprendre depuis la carte',
    aide: 'Contour repris du lecteur de cartes, puis converti en mètres locaux.',
  },
]

/* Fabrique de l'objet Toiture — IDENTIQUE quelle que soit la porte. Les portes
   n'ajoutent qu'une trace dans `portes` (informative : quelles aides ont servi). */
function fabriquerToiture({ nom, batiment, portes }) {
  return {
    editeur: ATELIER,
    nom: nom.trim(),
    batiment: batiment.trim() || null,
    portes: [...portes],
    // Géométrie et relevé : vides à la création, remplis dans l'atelier quelle
    // que soit la porte utilisée.
    origine_lnglat: null,
    azimut_deg: 0,
    sommets_m: [],
    underlay: null,
    calibration: null,
    chaines: [],
    obstacles: [],
    zones: [],
    statut: 'brouillon',
  }
}

export default function NouvelleToitureWizard({
  open,
  onOpenChange,
  onCreer,
  panneaux = null,
}) {
  const [nom, setNom] = useState('')
  const [batiment, setBatiment] = useState('')
  const [portes, setPortes] = useState([])

  const basculerPorte = useCallback((cle) => {
    setPortes((prec) => (prec.includes(cle) ? prec.filter((p) => p !== cle) : [...prec, cle]))
  }, [])

  const nomValide = nom.trim().length > 0

  const creer = useCallback(() => {
    if (!nomValide) return
    onCreer?.(fabriquerToiture({ nom, batiment, portes }))
    onOpenChange?.(false)
  }, [nomValide, onCreer, onOpenChange, nom, batiment, portes])

  const pied = useMemo(
    () => (
      <div className="ao-wizard-pied">
        <Button variant="ghost" type="button" onClick={() => onOpenChange?.(false)}>
          Annuler
        </Button>
        <Button
          type="button"
          onClick={creer}
          disabled={!nomValide}
          data-ao-wizard-creer
        >
          Ouvrir l&apos;atelier
        </Button>
      </div>
    ),
    [creer, nomValide, onOpenChange],
  )

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Nouvelle toiture"
      description="Choisissez une ou plusieurs portes d'entrée — elles se cumulent, et rien n'est définitif."
      footer={pied}
    >
      <div className="ao-wizard" data-ao-toiture-wizard>
        <label className="ao-champ" htmlFor="ao-toiture-nom">
          <span>Nom de la toiture</span>
          <input
            id="ao-toiture-nom"
            className="form-control"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            autoComplete="off"
          />
        </label>

        <label className="ao-champ" htmlFor="ao-toiture-batiment">
          <span>Bâtiment (facultatif)</span>
          <input
            id="ao-toiture-batiment"
            className="form-control"
            value={batiment}
            onChange={(e) => setBatiment(e.target.value)}
            autoComplete="off"
          />
        </label>

        <fieldset className="ao-portes">
          <legend>Portes d&apos;entrée</legend>
          {PORTES.map((porte) => {
            const active = portes.includes(porte.cle)
            return (
              <div className="ao-porte" key={porte.cle}>
                <button
                  type="button"
                  className="ao-porte-bouton"
                  aria-pressed={active}
                  data-ao-porte={porte.cle}
                  onClick={() => basculerPorte(porte.cle)}
                >
                  {porte.titre}
                </button>
                <p className="ao-porte-aide">{porte.aide}</p>
                {active && panneaux?.[porte.cle] ? (
                  <div className="ao-porte-panneau" data-ao-porte-panneau={porte.cle}>
                    {panneaux[porte.cle]}
                  </div>
                ) : null}
              </div>
            )
          })}
        </fieldset>

        <p className="ao-wizard-note">
          Les portes se cumulent&nbsp;: un plan importé se complète au tracé, un tracé reçoit un
          fond de plan plus tard, et le contour de la carte peut être recalé à la main. Le choix
          fait ici n&apos;est jamais définitif — tout se poursuit dans le même atelier.
        </p>
      </div>
    </ResponsiveDialog>
  )
}
