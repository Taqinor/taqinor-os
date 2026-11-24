import RailGuide from '../../commun/RailGuide'

/* Coque — le rail de gauche (maquette Main : 96 px, fond carte, filet droit ; Tablette :
   72 px, pictogrammes seuls — par la feuille 56-coque-responsive). Les cinq étapes du
   parcours (états et « N à régler » servis par `parcours/`) et « Avancé » en bas. */
export default function RailEtapes({ calepinageId = null, etapeActive, parcours, onChoisir, avance, onAvance, cache = false }) {
  return (
    <RailGuide vertical calepinageId={calepinageId} etapeActive={etapeActive} etats={parcours?.etats ?? {}} cache={cache}
      manque={parcours?.manque ?? []} onChoisir={onChoisir} avance={avance} onAvance={onAvance} />
  )
}
