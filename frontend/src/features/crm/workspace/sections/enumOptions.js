import React from 'react'

// QJR638 — UNE seule définition des <option> d'un select d'énumération
// (auparavant recopiée dans SectionEnergie, SectionPipeline et SectionSite).
// T4-U3-002 — `desactives` ({valeur: raison}) : une valeur posée par un autre
// chemin reste AFFICHÉE (elle peut être la valeur enregistrée) mais ne se
// choisit pas, et sa raison est lisible dans la liste.
export const enumOptions = (labels, desactives = {}) => [
  React.createElement('option', { key: '', value: '' }, '—'),
  ...Object.entries(labels).map(([k, l]) => (desactives[k]
    ? React.createElement('option', { key: k, value: k, disabled: true }, `${l} — ${desactives[k]}`)
    : React.createElement('option', { key: k, value: k }, l))),
]

export default enumOptions
