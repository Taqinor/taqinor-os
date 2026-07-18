// LW10 — Placeholder du centre (zone sections). REMPLACÉ par le SectionsPane
// complet en LW11 (registre de sections, nav-chips sticky scroll-spy, repli
// persisté, port 1:1 des champs). Ici : un conteneur scrollable + le wrapper
// `<form className="lw-form">` (display:contents) UNIQUEMENT en création, pour
// que le mode création fonctionne dès le shell.
export default function SectionsPane({ mode, formId, onSubmit }) {
  const inner = (
    <div className="lw-zone lw-center">
      <p className="lw-rail-hint">Sections — construites par LW11 (port 1:1 des champs).</p>
    </div>
  )
  if (mode === 'create') {
    return (
      <form id={formId} className="lw-form" noValidate onSubmit={onSubmit}>
        {inner}
      </form>
    )
  }
  return inner
}
