import api from './axios'

const parametresApi = {
  getProfile: () => api.get('/parametres/'),
  updateProfile: (data) => api.patch('/parametres/update/', data),
  uploadLogo: (formData) => api.post('/parametres/upload-logo/', formData),
  deleteLogo: () => api.delete('/parametres/delete-logo/'),
  uploadSignature: (formData) => api.post('/parametres/upload-signature/', formData),
  deleteSignature: () => api.delete('/parametres/delete-signature/'),
  // Modèles de message WhatsApp (FR + Darija) éditables.
  getMessages: () => api.get('/parametres/messages/'),
  saveMessage: (data) => api.put('/parametres/messages/', data),
}

export default parametresApi
