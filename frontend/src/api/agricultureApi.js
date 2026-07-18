import api from './axios'
import { makeResourceFactory } from './resource'

/* ============================================================================
   AGRICULTURE (NTAGR1-9) — client API du vertical Agriculture.
   ----------------------------------------------------------------------------
   Miroir FIN des ViewSets DRF de `apps/agriculture` (préfixe `/agriculture/`).
   Toutes les URLs sont relatives : l'intercepteur axios préfixe `/api/django`.
   Les listes acceptent des `params` de filtre transmis tels quels au backend.
   ========================================================================== */

const crud = makeResourceFactory(api, '/agriculture')

const agricultureApi = {
  exploitations: crud('exploitations'),
  parcelles: crud('parcelles'),
  campagnes: {
    ...crud('campagnes'),
    // NTAGR7 — registre phytosanitaire ONSSA imprimable (PDF interne).
    registrePhytoPdf: (id) =>
      api.get(`/agriculture/campagnes/${id}/registre-phyto-pdf/`, { responseType: 'blob' }),
  },
  etapesCampagne: crud('etapes-campagne'),
  intrants: crud('intrants-agricoles'),
  equipesSaisonnieres: crud('equipes-saisonnieres'),
  pointages: crud('pointages'),
  // NTAGR11 — matériel agricole (pattern flotte, heures moteur cumulées).
  materiels: crud('materiels-agricoles'),
  utilisationsMateriel: crud('utilisations-materiel'),
}

export default agricultureApi
