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
      // `aria-label` du SelectTrigger reporté aussi (écrans sans <label htmlFor>).
      const label = kids.find((c) => c && c.props && c.props['aria-label'])?.props?.['aria-label']
      return (
        <select role="combobox" id={id} aria-label={label} value={value ?? ''} disabled={disabled}
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

// Remplace les primitives Radix par un <select> natif : `Select` est fourni
// par l'appelant (les variantes d'attributs diffèrent d'un écran à l'autre).
export function primitivesSelectNatif(actual, Select) {
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select,
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
}

// Variantes simples du <select> natif (écrans Monitoring / CRM / SAV /
// Ventes / fiche chantier). `role`, `label` (aria-label fixe), `labelDeProp`
// (aria-label du Select, repli « select »), `optionVide` (option vide en tête),
// `idDuTrigger` (id du SelectTrigger reporté + `disabled` + valeur ?? '').
export function avecSelectNatifSimple(actual, {
  role, label, labelDeProp = false, optionVide = true, idDuTrigger = false,
} = {}) {
  const Select = ({ value, onValueChange, children, disabled, 'aria-label': ariaLabel }) => {
    const kids = Array.isArray(children) ? children : [children]
    const id = idDuTrigger ? kids.find((c) => c && c.props && c.props.id)?.props?.id : undefined
    return (
      <select
        role={role}
        id={id}
        aria-label={labelDeProp ? (ariaLabel || 'select') : label}
        value={idDuTrigger ? (value ?? '') : value}
        disabled={idDuTrigger ? disabled : undefined}
        onChange={(e) => onValueChange(e.target.value)}
      >
        {optionVide && <option value="" />}
        {children}
      </select>
    )
  }
  return primitivesSelectNatif(actual, Select)
}

const vide = () => Promise.resolve({ data: [] })

export const savApiMock = {
  default: { getEquipements: vide, getTickets: vide, getContrats: vide },
}

export const crmApiMock = {
  default: { getAssignableUsers: vide },
}

export const ventesApiMock = {
  default: {
    getDevisById: () => Promise.resolve({ data: { lignes: [] } }),
    getReglementaire: () => Promise.resolve({ data: { results: [] } }),
  },
}

// Lectures de fond que la fiche chantier lance toujours au montage.
export const installationsLecturesVides = {
  getHistorique: vide,
  getTypesIntervention: vide,
}

// Stubs des trois blocs de l'onglet « Jalons & gates » (hors périmètre).
export const composantNul = { default: () => null }
