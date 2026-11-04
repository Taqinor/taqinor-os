/**
 * ENF19 — `hasPart` du JSON-LD de /nos-solutions (fr + en + ar) : une entrée Service par solution listée,
 * recalculée depuis la liste réelle. Une seule copie (garde ACAL345).
 */
export function hasPartServices(solutions: { title: string; href: string }[], site: URL | undefined) {
  return solutions.map((s) => ({
    '@type': 'Service',
    name: s.title,
    url: new URL(s.href, site).href,
  }));
}
