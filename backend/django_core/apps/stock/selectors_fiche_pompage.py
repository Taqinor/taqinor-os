"""AGR103 / ACAL817 — les champs de fiche servis par ``produits_pompage``.

Extraits de ``selectors.py`` (fichier au mur) : la liste des clés que
``selectors._fiche_pompage_dict`` recopie d'une fiche ``pompe`` ou
``variateur_pompage`` (forme ``contract_samples/produit_pompage.json``,
bloc ``fiches``). Vide = ``null`` = « non publié », jamais une valeur par
défaut.
"""

_FICHE_POMPE_CHAMPS = (
    'pompe_i_nominal_a', 'pompe_diametre_ext_mm', 'pompe_nb_etages',
    'pompe_immersion_min_m', 'pompe_rendement_pct', 'pompe_q_nominal_m3h',
    'pompe_hmt_nominale_m',
)
_FICHE_VARIATEUR_CHAMPS = (
    'ond_mppt_v_min', 'ond_mppt_v_max', 'ond_v_max_abs', 'ond_i_max_mppt_a',
    'ond_phases', 'ond_v_demarrage_v',
    'var_voc_reco_min_v', 'var_voc_reco_max_v', 'var_v_sortie_v',
    'var_i_sortie_nominal_a', 'var_protection_marche_a_sec',
    'var_rendement_mppt_pct',
    # ACAL817 — tension redressée du bus DC (ACAL816), lue par l'appoint (ACAL818).
    'var_bus_dc_redresse_v',
)
