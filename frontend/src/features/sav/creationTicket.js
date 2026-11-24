/* T4-U2-016 — le droit « gérer le SAV » (`sav_gerer`, grille des rôles) ouvre un ticket ; rôles qui le portent PAR
   DÉFAUT (apps/roles/permissions_registre.py) — la grille reste modifiable dans Paramètres. Une seule phrase, lue par la
   liste des tickets (/sav) et par la fiche du chantier (onglet « Interventions »). */
export const SAV_CREATION_RESERVEE = 'Ouvrir un ticket SAV est réservé aux rôles qui ont le droit « Gérer le SAV » '
  + '(par défaut : Directeur, Administrateur, Commercial responsable, techniciens). Demandez-le à l’un d’eux, ou à '
  + 'l’administrateur d’ajouter ce droit à votre rôle (Paramètres → Rôles).'
