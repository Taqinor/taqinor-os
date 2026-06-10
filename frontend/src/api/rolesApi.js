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
}

export default rolesApi
