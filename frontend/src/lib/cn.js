import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * cn — fusionne des classes conditionnelles (clsx) puis dédoublonne les
 * utilitaires Tailwind en conflit (tailwind-merge). Base de tous les
 * primitifs /src/ui : `cn('px-2 py-1', isActive && 'bg-primary', className)`.
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

export default cn
