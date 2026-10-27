"""CIQ103 / CCAT10 — table des articles C&I génériques « prix à renseigner »
(extraite de seed_catalogue.py, fichier-mur ; comportement identique)."""

# ── CIQ103 — articles C&I GÉNÉRIQUES « prix à renseigner » (D-CIQ-12) ───────
# Patron OSP/VEICHI : PRIX VIDES (0, jamais auto-chiffrés), ``role_ci`` /
# ``type_pose`` DÉCLARÉS à la création, aucune marque ni caractéristique
# constructeur inventée. Seule la grandeur qui DÉFINIT l'article (sa
# désignation : section d'un câble, calibre/pôles d'une protection, type de
# pose d'une structure, mode d'un compteur à TC / d'un contrôleur) est posée
# dans sa fiche — la composition C&I (CIQ115) apparie par rôle ET grandeur.
# Tout le reste (pouvoir de coupure, masse, compatibilités, nombre d'onduleurs
# pilotés) reste VIDE = non publié. Sections et calibres = EXACTEMENT les
# listes normalisées du moteur électrique (étendues par CIQ139), IMPORTÉES —
# jamais une liste choisie à la main. Aucun onduleur ni batterie C&I inventés :
# ce sont des produits réels, à saisir par le fondateur.
# (nom, sku, role_ci, type_pose, qte, seuil, fiche ou None)


def _articles_ci():
    from core.electrique.cables import SECTIONS_MM2_CI
    from core.electrique.protections import CALIBRES_DISJONCTEUR_CI_A

    def _fmt(nombre):
        texte = ('%g' % nombre)
        return texte.replace('.', ',')

    lignes = []
    for s in SECTIONS_MM2_CI:
        lignes.append((
            f'Câble AC cuivre 5×{_fmt(s)} mm² (au mètre)',  # 3P+N+PE (26/10/2026)
            f'CI-CAB-AC-CU-{"%g" % s}-M', 'cable_ac', '', 5000, 200,
            {'type_fiche': 'cable', 'cable_cote': 'ac',
             'cable_section_mm2': float(s), 'cable_ame': 'cu'}))
    for prot_type, libelle, prefixe in (
            ('disjoncteur', 'Disjoncteur AC', 'CI-DISJ-AC'),
            ('sectionneur', 'Sectionneur AC', 'CI-SECT-AC')):
        for c in CALIBRES_DISJONCTEUR_CI_A:
            lignes.append((
                f'{libelle} {c} A tétrapolaire (C&I)',
                f'{prefixe}-{c}A-4P', 'protection_ac', '', 100, 5,
                {'type_fiche': 'protection', 'prot_type': prot_type,
                 'prot_cote': 'ac', 'prot_calibre_a': float(c),
                 'prot_poles': 4}))
    lignes.extend([
        # CCAT10 — postes que la composition C&I (``_protections_dc_et_terre``)
        # cherche par rôle ET fiche ; sans article ils étaient SAUTÉS (alerte
        # interne POSTE_ABSENT_CATALOGUE). Fiche = seule grandeur de désignation.
        ('Protection DC C&I', 'CI-PROT-DC', 'protection_dc', '', 100, 5,
         {'type_fiche': 'protection', 'prot_cote': 'dc'}),
        ('Parafoudre DC C&I', 'CI-PARAF-DC', 'protection_dc', '', 20, 2,
         {'type_fiche': 'protection', 'prot_type': 'parafoudre',
          'prot_cote': 'dc'}),
        ('Parafoudre AC C&I', 'CI-PARAF-AC', 'protection_ac', '', 20, 2,
         {'type_fiche': 'protection', 'prot_type': 'parafoudre',
          'prot_cote': 'ac'}),
        ('Mise à la terre C&I', 'CI-TERRE', 'mise_a_la_terre', '', 20, 2,
         None),
        ('Coffret AC C&I', 'CI-COF-AC', 'coffret_ac', '', 20, 2, None),
        ('Coffret DC C&I', 'CI-COF-DC', 'coffret_dc', '', 20, 2, None),
        ('Compteur triphasé à TC (injection)', 'CI-CPT-TC',
         'compteur_injection', '', 20, 2,
         {'type_fiche': 'limiteur', 'lim_mode': 'compteur_tc'}),
        ("Contrôleur d'injection C&I", 'CI-CTRL-INJ', 'controleur_injection',
         '', 20, 2, {'type_fiche': 'limiteur', 'lim_mode': 'controleur'}),
        ('Logger de supervision C&I', 'CI-LOGGER', 'logger_supervision', '',
         20, 2, {'type_fiche': 'logger'}),
        ('Structure bac acier C&I', 'CI-STRUCT-BAC', 'structure_ci',
         'bac_acier', 20, 2,
         {'type_fiche': 'structure', 'struct_type_pose': 'bac_acier'}),
        ('Structure toiture inclinée C&I', 'CI-STRUCT-INCL', 'structure_ci',
         'toiture_inclinee', 20, 2,
         {'type_fiche': 'structure', 'struct_type_pose': 'toiture_inclinee'}),
        ('Structure toit plat fixé C&I', 'CI-STRUCT-PLAT-FIXE',
         'structure_ci', 'toit_plat_fixe', 20, 2,
         {'type_fiche': 'structure', 'struct_type_pose': 'toit_plat_fixe'}),
        ('Structure au sol C&I', 'CI-STRUCT-SOL', 'structure_ci', 'sol', 20,
         2, {'type_fiche': 'structure', 'struct_type_pose': 'sol'}),
        ('Structure toit plat lestée C&I', 'CI-STRUCT-PLAT-LEST',
         'structure_ci', 'toit_plat_leste', 20, 2,
         {'type_fiche': 'structure', 'struct_type_pose': 'toit_plat_leste'}),
        ('Structure ombrière C&I', 'CI-STRUCT-OMBR', 'structure_ci',
         'ombriere', 20, 2,
         {'type_fiche': 'structure', 'struct_type_pose': 'ombriere'}),
        ('Cellule MT (poste de livraison)', 'CI-CELLULE-MT', 'cellule_mt', '',
         20, 2, None),
        # Prestations C&I — jamais le barème résidentiel (L-FORFAIT intouché).
        ('Études et ingénierie C&I', 'CI-ETUDES', 'etudes_ingenierie', '',
         999, 0, None),
        ('Pose de la structure C&I', 'CI-POSE-STRUCT', 'pose_structure', '',
         999, 0, None),
        ('Pose des modules C&I', 'CI-POSE-MOD', 'pose_modules', '', 999, 0,
         None),
        ('Raccordement AC C&I', 'CI-RACC-AC', 'raccordement_ac', '', 999, 0,
         None),
        ('Mise en service C&I', 'CI-MES', 'mise_en_service', '', 999, 0,
         None),
        ('Dossier de raccordement C&I', 'CI-DOSSIER-RACC',
         'dossier_raccordement', '', 999, 0, None),
        ('Levage et accès C&I', 'CI-LEVAGE', 'levage_acces', '', 999, 0,
         None),
        ('Transport C&I', 'CI-TRANSPORT', 'transport_ci', '', 999, 0, None),
        # Option O&M NOMMÉE (D-CIQ-12) — toujours proposée, prix à renseigner.
        ('Exploitation et maintenance (O&M) C&I', 'CI-OM', 'om_ci', '', 999,
         0, None),
    ])
    return lignes


ARTICLES_CI_PRIX_A_RENSEIGNER = _articles_ci()
