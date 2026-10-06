/* Support partagé des tests de la fiche chantier (CIQ637) : polyfill, Select
   natif et mocks d'API voisines, SANS import de composant (chargé depuis les
   fabriques `vi.mock`, il ne doit créer aucun cycle). */

export function polyfillResizeObserver() {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
}

// Radix Select ne s'ouvre pas de façon fiable sous jsdom (portail + pointer
// events) : les primitives sont remplacées par un <select> natif ; le `id`
// du SelectTrigger est reporté sur le <select> (association label/champ).
export function avecSelectNatif(actual) {
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children, disabled }) => {
      const kids = Array.isArray(children) ? children : [children]
      const id = kids.find((c) => c && c.props && c.props.id)?.props?.id
      return (
        <select role="combobox" id={id} value={value ?? ''} disabled={disabled}
                onChange={(e) => onValueChange(e.target.value)}>
          <option value="" />
          {children}
        </select>
      )
    },
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
}

const vide = () => Promise.resolve({ data: [] })

export const savApiMock = {
  default: { getEquipements: vide, getTickets: vide, getContrats: vide },
}

export const crmApiMock = {
  default: { getAssignableUsers: vide },
}
