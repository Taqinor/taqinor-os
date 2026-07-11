import api from './axios'

const rolesApi = {
  getRoles: () => api.get('/roles/'),
  getRole: (id) => api.get(`/roles/${id}/`),
  createRole: (data) => api.post('/roles/', data),
  updateRole: (id, data) => api.put(`/roles/${id}/`, data),
  patchRole: (id, data) => api.patch(`/roles/${id}/`, data),
  deleteRole: (id) => api.delete(`/roles/${id}/`),
  getPermissionsDisponibles: () =>
    api.get('/roles/permissions-disponibles/'),
  // YRBAC10 — catalogue unique (admin) : ALL_PERMISSIONS + carte route→rôles
  // enforced (dérivée de la matrice canonique YRBAC2). Source du gating
  // front↔back ; consommé par l'écran Rôles et le test de dérive.
  getPermissionCatalog: () =>
    api.get('/roles/permission-catalog/'),
}

export default rolesApi
