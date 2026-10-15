/* VX239 — avertissement doublon EN DIRECT : un contact déjà connu porte ce
   téléphone/email (`matches` : { id, nom, prenom }[]). `avecCompte` ajoute le
   nombre de contacts après « existe déjà » ; `className` / `testId` ciblent
   le paragraphe. Rien n'est rendu sans doublon. */
export default function AvertissementDoublons({ matches, className, testId, avecCompte = false }) {
  if (matches.length === 0) return null
  return (
    <p className={className} role="status" data-testid={testId}>
      ⚠️ Un contact avec ce téléphone/email existe déjà
      {avecCompte && matches.length > 1 ? ` (${matches.length})` : ''} :{' '}
      {matches.slice(0, 3).map((d, i) => (
        <span key={d.id}>
          {i > 0 && ', '}
          {`${d.nom} ${d.prenom || ''}`.trim() || `#${d.id}`}
        </span>
      ))}
      {matches.length > 3 && '…'}
    </p>
  )
}
