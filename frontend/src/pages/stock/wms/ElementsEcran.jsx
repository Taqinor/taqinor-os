/* ASTK220/ASTK224 — éléments d'écran partagés des nouveaux écrans entrepôt
   (section titrée + ligne « vide »). Un seul endroit : jamais recopiés page
   par page (garde de duplicat littéral). */

export const Section = ({ id, titre, children }) => (
  <section aria-labelledby={id} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
    <h2 id={id} className="mb-3 text-sm font-semibold">{titre}</h2>
    {children}
  </section>
)

export const Vide = ({ children }) => (
  <p className="text-sm text-[var(--muted-foreground)]">{children}</p>
)
