import SystemPicker from './SystemPicker'

/* Barre « choix du système supervisé » PARTAGÉE des écrans O&M : le sélecteur
   à gauche, un éventuel contrôle (fenêtre, période…) en `children` à droite. */
export default function BarreSysteme({
  systems, loading, value, onChange,
  className = 'mb-4 flex flex-wrap items-center justify-between gap-3', children,
}) {
  return (
    <div className={className}>
      <SystemPicker
        systems={systems}
        loading={loading}
        value={value}
        onChange={onChange}
      />
      {children}
    </div>
  )
}
