// ENF15 — bandeau d'erreur de chargement (voir loadErrors.js).
export default function LoadErrorNotice({ errors, testId = 'ae-load-error' }) {
  if (!errors || errors.length === 0) return null
  return (
    <p data-testid={testId} role="alert" style={{ color: '#dc2626', margin: '0 0 0.75rem' }}>
      Impossible de charger {errors.join(', ')}. Les données affichées peuvent être
      incomplètes — rechargez la page pour réessayer.
    </p>
  )
}
