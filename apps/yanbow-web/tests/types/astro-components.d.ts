/**
 * Pour `tsc -p tsconfig.check.json` : les tests importent des composants
 * `.astro` (rendus par l'API Container). `astro check` les résout lui-même ;
 * `tsc` seul a besoin de cette déclaration générique.
 */
declare module '*.astro' {
  const Composant: Parameters<import('astro/container').experimental_AstroContainer['renderToString']>[0];
  export default Composant;
}
