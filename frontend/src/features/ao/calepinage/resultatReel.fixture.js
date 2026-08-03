/* ============================================================================
   LE RÉSULTAT DE CALEPINAGE — CAPTURÉ, PAS INVENTÉ.
   ----------------------------------------------------------------------------
   Ce fichier est la sortie LITTÉRALE du moteur du dépôt. Il a été produit en
   appelant `apps.ao.calepinage_service.calepiner()` (le code exact que
   `CalculerCalepinageView` appelle) sur un document bâti par
   `apps.ao.calepinage_io.parametres_vers_document`, puis recopié tel quel :

     toiture polygonale 8 m × 12 m, un obstacle relevé (3→5 m × 6→8 m),
     kit AO-TABLE-PORTRAIT (2,382 × 1,134 m, 625 Wc, 2 modules/table),
     preset AOF61 (rives 0,35 m, allée 0,60 m, pas 1 cm, engagement 20).

   POURQUOI CE DÉTOUR. Le bug qu'on répare vient EXACTEMENT de l'inverse : un
   contrat de réponse écrit à la main côté front, que le serveur n'a jamais
   servi. Un test dont la charge utile est inventée aurait re-verrouillé la
   fiction au lieu de la casser. Ici, si le sérialiseur change, la fixture est
   fausse et les tests le disent.

   La clé `company_id` que `calepiner()` ajoute est présente parce qu'elle est
   RÉELLEMENT dans la réponse — aucun écran ne la lit.
   ========================================================================== */

const resultatReel = {
  repere: '05H',
  hash_entree: 'f4e93b8cda949195f43c9f4ee38df04bace365e875aeb6d3292d559bb09d141a',
  version_moteur: '1.0.0',
  schema_version: 1,
  total_modules: 16,
  kwc: 10.0,
  engageable: true,
  motifs_non_engageable: [],
  plans: [
    {
      surface: '05H',
      modules: 16,
      ecart_a_l_optimum: 0,
      rangees: [
        {
          surface: '05H',
          x0: 0.8003,
          y0: 0.8003,
          kit: 'AO-TABLE-PORTRAIT',
          modules: 12,
          emprise_m: 4.6997,
          troncons: [[0.35, 7.65]],
        },
        {
          surface: '05H',
          x0: 6.9503,
          y0: 6.9503,
          kit: 'AO-TABLE-PORTRAIT',
          modules: 4,
          emprise_m: 4.6997,
          troncons: [[0.35, 2.5], [5.5, 7.65]],
        },
      ],
      tables: [
        { x0: 0.35, x1: 1.484, y0: 0.8003, y1: 5.5, kit: 'AO-TABLE-PORTRAIT' },
        { x0: 1.484, x1: 2.618, y0: 0.8003, y1: 5.5, kit: 'AO-TABLE-PORTRAIT' },
        { x0: 2.618, x1: 3.752, y0: 0.8003, y1: 5.5, kit: 'AO-TABLE-PORTRAIT' },
        { x0: 3.752, x1: 4.886, y0: 0.8003, y1: 5.5, kit: 'AO-TABLE-PORTRAIT' },
        { x0: 4.886, x1: 6.02, y0: 0.8003, y1: 5.5, kit: 'AO-TABLE-PORTRAIT' },
        { x0: 6.02, x1: 7.154, y0: 0.8003, y1: 5.5, kit: 'AO-TABLE-PORTRAIT' },
        { x0: 0.35, x1: 1.484, y0: 6.9503, y1: 11.65, kit: 'AO-TABLE-PORTRAIT' },
        { x0: 5.5, x1: 6.634, y0: 6.9503, y1: 11.65, kit: 'AO-TABLE-PORTRAIT' },
      ],
    },
  ],
  rangees: [
    {
      surface: '05H',
      x0: 0.8003,
      y0: 0.8003,
      kit: 'AO-TABLE-PORTRAIT',
      modules: 12,
      emprise_m: 4.6997,
      troncons: [[0.35, 7.65]],
    },
    {
      surface: '05H',
      x0: 6.9503,
      y0: 6.9503,
      kit: 'AO-TABLE-PORTRAIT',
      modules: 4,
      emprise_m: 4.6997,
      troncons: [[0.35, 2.5], [5.5, 7.65]],
    },
  ],
  company_id: 1,
  preuve: {
    total_retenu: 16,
    total_optimal: 16,
    methode: 'dp_exact_1cm',
    methode_exacte: true,
    optimal: true,
    libelle: 'optimum prouvé (16 modules)',
    pas_cm: 1.0,
    nb_optima: 12,
    borne_superieure: 16,
    marge_troncon_min: 0.496,
    marge_bande_min: 0.0,
    rangee_critique: 'y0=0.800 (AO-TABLE-PORTRAIT)',
    obstacle_critique: 'A',
    controles: [
      'orientation',
      'dessine_egale_compte',
      'compte_annonce',
      'non_chevauchement',
      'rive_laterale',
      'rive_extremite',
      'hors_developpe',
      'coupure',
      'degagement_obstacle',
    ],
    version_moteur: '1.0.0',
  },
  engagement_modules: 20,
}

export default resultatReel
