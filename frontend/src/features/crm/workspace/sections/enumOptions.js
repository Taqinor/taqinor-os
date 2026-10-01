import React from 'react'

// QJR638 — UNE seule définition des <option> d'un select d'énumération
// (auparavant recopiée dans SectionEnergie, SectionPipeline et SectionSite).
export const enumOptions = (labels) => [
  React.createElement('option', { key: '', value: '' }, '—'),
  ...Object.entries(labels).map(([k, l]) =>
    React.createElement('option', { key: k, value: k }, l)),
]

export default enumOptions
