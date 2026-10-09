// Doublures partagées des tests de l'écran Contrats de maintenance.
import { vi } from 'vitest'

export function crmApiMock(clients = []) {
  return { default: { getClients: vi.fn(() => Promise.resolve({ data: clients })) } }
}

export function installationsApiMock() {
  return { default: { getInstallations: vi.fn(() => Promise.resolve({ data: [] })) } }
}

export function axiosMock() {
  return { default: { get: vi.fn(() => Promise.resolve({ data: [] })) } }
}

export const CLIENT_ACME = { id: 3, nom: 'ACME', prenom: '' }
