import api from './axios'

/* ============================================================================
   Conformité fiscale marocaine (apps/fiscal, Groupe NTMAR). Préfixe `/fiscal/`.
   RÉCONCILIATION (WIR106) : la GESTION des obligations fiscales (CRUD +
   calendrier XACC9) vit déjà dans `apps/compta` (`comptaApi.obligationsFiscales`,
   écran `features/compta/pages/FiscalitePage`). Cette API n'expose donc PAS une
   seconde surface « obligations » : uniquement la vue CONFORMITÉ en lecture
   seule (feu tricolore NTMAR16), les échéances datées et le registre UBO/veille.
   ========================================================================== */

const fiscalApi = {
  // NTMAR16 — feu tricolore de conformité par obligation (lecture seule).
  tableauConformite: () => api.get('/fiscal/tableau-conformite/'),
  // NTMAR14 — échéances datées (lecture seule ; générées via le calendrier).
  echeances: (params) => api.get('/fiscal/echeances/', { params }),
  // NTMAR28 — attestations tenant expirantes.
  attestationsExpirantes: () =>
    api.get('/fiscal/attestations-tenant/expirantes/'),
  // NTMAR — veille réglementaire.
  veille: (params) => api.get('/fiscal/veille/', { params }),
}

export default fiscalApi
