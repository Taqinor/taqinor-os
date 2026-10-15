import { expect } from 'vitest'

/* Vérifie l'entrée de menu d'un `module.config` : libellé, rôles gardés, icône
   présente. Retourne l'entrée pour les assertions propres à la suite. */
export function verifierEntreeMenu(config, path, label, roles) {
  const navItem = config.nav.items.find((i) => i.to === path)
  expect(navItem).toBeTruthy()
  expect(navItem.label).toBe(label)
  expect(navItem.roles).toEqual(roles)
  expect(navItem.icon).toBeTruthy()
  return navItem
}
