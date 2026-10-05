"""SPL114 — lecture fiche technique (PV6) : ``type_fiche_produit``,
``specs_for_produit``, ``dimensions_de_pose``, ``produits_modules_qs`` et
``kit_from_produit``, déplacés tels quels depuis ``selectors.py`` (move only).

``apps.stock.selectors`` (façade inter-app) les ré-exporte : les autres apps
continuent de les lire PAR LA FAÇADE. Aucun import de niveau module : les
imports restent locaux aux fonctions."""


# ── PV6 — Specs & Kit de calepinage DÉRIVÉS de FicheTechnique (PV5) ─────────
# Point d'entrée cross-app LECTURE SEULE : le moteur de calepinage
# (core.calepinage) et les autres apps lisent les caractéristiques d'un
# produit à travers ces deux fonctions plutôt qu'en touchant
# `apps.stock.models.FicheTechnique` directement.

def type_fiche_produit(produit):
    """CAL243 — la famille ``FicheTechnique.type_fiche`` du produit
    (``'module'``/``'onduleur'``/``'batterie'``/``'optimiseur'``/``'autre'``),
    ou ``''`` sans fiche. Lecture seule ; c'est le sélecteur MINCE qui
    permet à ``apps.calepinage`` de ranger un produit dans la bonne famille
    d'équipement sans importer ``apps.stock.models``."""
    fiche = getattr(produit, 'fiche_technique', None)
    return fiche.type_fiche if fiche is not None else ''


def specs_for_produit(produit):
    """PV6 — sous-ensemble de spécifications électriques/dimensions d'un
    produit, lues sur sa FicheTechnique (PV5) et scopées par son
    ``type_fiche`` :

      * ``module`` → ``{vmp_v, voc_v, isc_a, imp_a, pmax_wc,
        temp_coeff_voc_pct_c, temp_coeff_pmax_pct_c, longueur_mm,
        largeur_mm, epaisseur_mm, poids_kg, rendement_pct, techno_cellule,
        bifacial, noct_c, uc_w_m2k, uv_w_m3sk, bifacialite_pct,
        degradation_annuelle_pct, degradation_annee1_pct,
        garantie_pct_a_10_ans, garantie_pct_a_25_ans,
        rendement_par_irradiance, tolerance_pmax_min_pct,
        tolerance_pmax_max_pct}`` (CAL114 : poids, épaisseur, rendement,
        technologie de cellule et bifacial étaient déjà sur la fiche mais
        omis de ce bloc — cf. CAL111-113 ; les trois dernières, CALX60) ;
      * ``onduleur`` → ``{n_mppt, mppt_v_min, mppt_v_max, v_max_abs,
        i_max_mppt_a, ac_kw, phases, rendement_euro_pct, v_demarrage_v,
        isc_max_mppt_a, bat_max_charge_kw, bat_max_decharge_kw,
        entrees_par_mppt, chaines_max_par_mppt, s_max_kva, dc_max_kwc,
        rendement_par_charge, rendement_max_pct, rendement_cec_pct,
        conso_nuit_w}`` (CAL115 pour les quatre du milieu ; les quatre
        dernières, CALX60 — ``rendement_par_charge`` porte le champ
        ``ond_courbe_rendement``) ;
      * ``batterie`` → ``{kwh_nominal, kwh_usable, dod_pct, v_nominal,
        max_charge_kw, max_decharge_kw, max_modules_par_banc,
        rendement_ar_pct, cycles_publies, retention_fin_de_vie_pct,
        garantie_annees, c_rate_charge, c_rate_decharge, chimie,
        temp_min_c, temp_max_c, eol_pct}`` (CAL118 au milieu ; les six
        dernières, CALX60 — ``eol_pct`` est le MÊME champ que
        ``retention_fin_de_vie_pct``, publié sous le nom que lit
        l'électrique) ;
      * ``optimiseur`` (CAL116) → ``{pmax_in_w, v_in_min, v_in_max,
        i_in_max_a, rendement_pct, modules_par_optimiseur, ac_kw,
        ac_tension_v, ac_i_max_a, ac_unites_max_par_branche,
        v_out_nominal_v, v_out_min, v_out_max, i_out_max_a, pmax_out_w,
        modules_max_par_chaine}`` (les dix dernières, CALX60 — la SORTIE
        du composant, que CAL116 n'avait pas).

    ⚠ LE DICT RENDU EST PLAT — c'est le BLOC du ``type_fiche``, pas un dict de
    blocs : lire ``specs_for_produit(p)['batterie']`` rend toujours ``None``.
    (Ce faux pas a réellement coûté un moteur muet, cf. L-DECH.)

    Une clé dont la valeur est NULL sur la fiche est OMISE (jamais rendue à
    ``None``) : un appelant qui fait ``{**DEFAUT, **specs_for_produit(p)}``
    obtient un résultat byte-identique à l'absence de fiche pour tout champ
    non saisi. Produit sans fiche, ou ``type_fiche`` sans bloc connu (vide
    ou ``autre``) → dict VIDE. Lecture seule."""
    fiche = getattr(produit, 'fiche_technique', None)
    if fiche is None:
        return {}

    def _put(d, key, value):
        if value is not None:
            d[key] = value

    out = {}
    if fiche.type_fiche == 'module':
        for key, value in (
            ('vmp_v', fiche.vmp_v), ('voc_v', fiche.voc_v),
            ('isc_a', fiche.isc_a), ('imp_a', fiche.imp_a),
            ('pmax_wc', fiche.pmax_wc),
            ('temp_coeff_voc_pct_c', fiche.temp_coeff_voc_pct_c),
            ('temp_coeff_pmax_pct_c', fiche.temp_coeff_pmax_pct_c),
            ('longueur_mm', fiche.longueur_mm),
            ('largeur_mm', fiche.largeur_mm),
            # CAL114 — clés déjà présentes sur la fiche (AUD835/PV5) mais
            # jusqu'ici OMISES de ce bloc : le poids est indispensable au
            # lestage (g), les dimensions/épaisseur au kit de calepinage (h).
            # getattr : les doubles de test (_FausseFiche) ne portent pas
            # forcément les champs récents — absent ≡ NULL (non évaluable).
            ('epaisseur_mm', getattr(fiche, 'epaisseur_mm', None)),
            ('poids_kg', getattr(fiche, 'poids_kg', None)),
            ('rendement_pct', getattr(fiche, 'rendement_pct', None)),
            ('techno_cellule', getattr(fiche, 'techno_cellule', None) or None),
            ('bifacial', getattr(fiche, 'bifacial', None)),
            # CAL111 — modèle thermique NOCT / Uc-Uv (optionnel).
            ('noct_c', getattr(fiche, 'noct_c', None)),
            ('uc_w_m2k', getattr(fiche, 'uc_w_m2k', None)),
            ('uv_w_m3sk', getattr(fiche, 'uv_w_m3sk', None)),
            # CAL112 — facteur de bifacialité publié (optionnel).
            ('bifacialite_pct', getattr(fiche, 'bifacialite_pct', None)),
            # CAL113 — dégradation annuelle & paliers de garantie (optionnels).
            ('degradation_annuelle_pct',
             getattr(fiche, 'degradation_annuelle_pct', None)),
            ('degradation_annee1_pct',
             getattr(fiche, 'degradation_annee1_pct', None)),
            ('garantie_pct_a_10_ans',
             getattr(fiche, 'garantie_pct_a_10_ans', None)),
            ('garantie_pct_a_25_ans',
             getattr(fiche, 'garantie_pct_a_25_ans', None)),
            # CALX60 — ce que les étapes de la chaîne de pertes lisent, SOUS
            # LE NOM QU'ELLES LISENT : « niveau d'irradiance » (CALX162)
            # demande ``rendement_par_irradiance``, « qualité module »
            # (CALX165) les deux bornes de tolérance. getattr : les doubles
            # de test (_FausseFiche) ne portent pas forcément les champs
            # récents — absent ≡ NULL (étape omise en nommant le champ).
            ('rendement_par_irradiance',
             getattr(fiche, 'rendement_par_irradiance', None)),
            ('tolerance_pmax_min_pct',
             getattr(fiche, 'tolerance_pmax_min_pct', None)),
            ('tolerance_pmax_max_pct',
             getattr(fiche, 'tolerance_pmax_max_pct', None)),
        ):
            _put(out, key, value)
    elif fiche.type_fiche == 'onduleur':
        for key, value in (
            ('n_mppt', fiche.ond_n_mppt),
            ('mppt_v_min', fiche.ond_mppt_v_min),
            ('mppt_v_max', fiche.ond_mppt_v_max),
            ('v_max_abs', fiche.ond_v_max_abs),
            ('i_max_mppt_a', fiche.ond_i_max_mppt_a),
            ('ac_kw', fiche.ond_ac_kw),
            ('phases', fiche.ond_phases),
            ('rendement_euro_pct', fiche.ond_rendement_euro_pct),
            # PVOND-H (2026-08-19) — le moteur (SpecOnduleur) sait déjà lire
            # ces deux variables ; elles n'avaient simplement aucun champ pour
            # les porter jusqu'ici (cf. le nouveau bloc PVOND-H du modèle).
            ('v_demarrage_v', fiche.ond_v_demarrage_v),
            ('isc_max_mppt_a', fiche.ond_isc_max_mppt_a),
            # L-DECH (2026-08-24) — le PORT BATTERIE de l'hybride, deuxième
            # goulot du chemin batterie : le moteur horaire borne la puissance
            # servie/absorbée par ``min(Σ packs, port onduleur)``.
            # getattr : les doubles de test (_FausseFiche) ne portent pas
            # forcément les champs récents — absent ≡ NULL (non évaluable).
            ('bat_max_charge_kw', getattr(fiche, 'ond_bat_max_charge_kw', None)),
            ('bat_max_decharge_kw', getattr(fiche, 'ond_bat_max_decharge_kw', None)),
            # CAL115 — chaînes/entrées par MPPT, puissance apparente et DC
            # max. getattr : les doubles de test (_FausseFiche) ne portent
            # pas forcément les champs récents — absent ≡ NULL (non publié).
            ('entrees_par_mppt', getattr(fiche, 'ond_entrees_par_mppt', None)),
            ('chaines_max_par_mppt',
             getattr(fiche, 'ond_chaines_max_par_mppt', None)),
            ('s_max_kva', getattr(fiche, 'ond_s_max_kva', None)),
            ('dc_max_kwc', getattr(fiche, 'ond_dc_max_kwc', None)),
            # CALX60 — l'étape « onduleur » (CALX170) lit la courbe sous le
            # nom ``rendement_par_charge`` (ce qu'elle EST : un rendement en
            # fonction de la charge) et non sous le nom du champ ; l'étape
            # « auxiliaires » (CALX175) lit ``conso_nuit_w``. getattr : les
            # doubles de test (_FausseFiche) ne portent pas forcément les
            # champs récents — absent ≡ NULL (étape omise, jamais un
            # forfait).
            ('rendement_par_charge',
             getattr(fiche, 'ond_courbe_rendement', None)),
            ('rendement_max_pct',
             getattr(fiche, 'ond_rendement_max_pct', None)),
            ('rendement_cec_pct',
             getattr(fiche, 'ond_rendement_cec_pct', None)),
            ('conso_nuit_w', getattr(fiche, 'ond_conso_nuit_w', None)),
        ):
            _put(out, key, value)
    elif fiche.type_fiche == 'batterie':
        for key, value in (
            ('kwh_nominal', fiche.bat_kwh_nominal),
            ('kwh_usable', fiche.bat_kwh_usable),
            ('dod_pct', fiche.bat_dod_pct),
            ('v_nominal', fiche.bat_v_nominal),
            ('max_charge_kw', fiche.bat_max_charge_kw),
            # L-DECH (2026-08-24) — la puissance de décharge PAR PACK, celle
            # que ``apps/ventes/etude_horaire.py`` attendait par son nom.
            # getattr : les doubles de test (_FausseFiche) ne portent pas
            # forcément les champs récents — absent ≡ NULL (non évaluable).
            ('max_decharge_kw', getattr(fiche, 'bat_max_decharge_kw', None)),
            # BATHOMO (2026-08-26) — le plafond fondateur du nombre de
            # modules IDENTIQUES admis dans un même banc. getattr : les
            # doubles de test (_FausseFiche) ne portent pas forcément le
            # champ récent — absent ≡ NULL (illimité, comportement inchangé).
            ('max_modules_par_banc',
             getattr(fiche, 'bat_max_modules_par_banc', None)),
            # QJR137 (2026-08-30) — le rendement aller-retour PUBLIÉ. Sans lui,
            # le moteur horaire n'avait que le forfait 0,90 de
            # ``quote_engine.pricing`` pour borner ce que la batterie restitue,
            # donc l'économie « avec batterie » montrée au client. getattr :
            # les doubles de test (_FausseFiche) ne portent pas forcément le
            # champ récent — absent ≡ NULL (non publié, hypothèse déclarée).
            ('rendement_ar_pct',
             getattr(fiche, 'bat_rendement_ar_pct', None)),
            # CAL118 — nombre de cycles publié & vieillissement calendaire.
            # getattr : les doubles de test (_FausseFiche) ne portent pas
            # forcément les champs récents — absent ≡ NULL (non publié).
            ('cycles_publies', getattr(fiche, 'bat_cycles_publies', None)),
            ('retention_fin_de_vie_pct',
             getattr(fiche, 'bat_retention_fin_de_vie_pct', None)),
            ('garantie_annees', getattr(fiche, 'bat_garantie_annees', None)),
            # CALX60 — C-rate, chimie et plage de température du pack.
            # ``eol_pct`` est publié depuis ``bat_retention_fin_de_vie_pct``
            # (CAL118) : la rétention de capacité en fin de vie garantie EST
            # cette grandeur, et une seconde colonne aurait donné deux
            # vérités pour une seule donnée. getattr : les doubles de test
            # (_FausseFiche) ne portent pas forcément les champs récents —
            # absent ≡ NULL (non publié).
            ('c_rate_charge', getattr(fiche, 'bat_c_rate_charge', None)),
            ('c_rate_decharge',
             getattr(fiche, 'bat_c_rate_decharge', None)),
            ('chimie', getattr(fiche, 'bat_chimie', None) or None),
            ('temp_min_c', getattr(fiche, 'bat_temp_min_c', None)),
            ('temp_max_c', getattr(fiche, 'bat_temp_max_c', None)),
            ('eol_pct',
             getattr(fiche, 'bat_retention_fin_de_vie_pct', None)),
        ):
            _put(out, key, value)
    elif fiche.type_fiche == 'optimiseur':
        # CAL116 — optimiseur de puissance / micro-onduleur : bloc neuf,
        # aucune fiche existante n'en porte le type avant cette tâche.
        for key, value in (
            ('pmax_in_w', getattr(fiche, 'opt_pmax_in_w', None)),
            ('v_in_min', getattr(fiche, 'opt_v_in_min', None)),
            ('v_in_max', getattr(fiche, 'opt_v_in_max', None)),
            ('i_in_max_a', getattr(fiche, 'opt_i_in_max_a', None)),
            ('rendement_pct', getattr(fiche, 'opt_rendement_pct', None)),
            ('modules_par_optimiseur',
             getattr(fiche, 'opt_modules_par_optimiseur', None)),
            # CALX60 — LA SORTIE du composant, que CAL116 n'avait pas : les
            # ``ac_*`` décrivent le micro-onduleur (sortie alternative), les
            # ``v_out_*``/``i_out_*``/``pmax_out_w`` l'optimiseur (sortie
            # continue). getattr : les doubles de test (_FausseFiche) ne
            # portent pas forcément les champs récents — absent ≡ NULL (non
            # publié).
            ('ac_kw', getattr(fiche, 'opt_ac_kw', None)),
            ('ac_tension_v', getattr(fiche, 'opt_ac_tension_v', None)),
            ('ac_i_max_a', getattr(fiche, 'opt_ac_i_max_a', None)),
            ('ac_unites_max_par_branche',
             getattr(fiche, 'opt_ac_unites_max_par_branche', None)),
            ('v_out_nominal_v',
             getattr(fiche, 'opt_v_out_nominal_v', None)),
            ('v_out_min', getattr(fiche, 'opt_v_out_min', None)),
            ('v_out_max', getattr(fiche, 'opt_v_out_max', None)),
            ('i_out_max_a', getattr(fiche, 'opt_i_out_max_a', None)),
            ('pmax_out_w', getattr(fiche, 'opt_pmax_out_w', None)),
            ('modules_max_par_chaine',
             getattr(fiche, 'opt_modules_max_par_chaine', None)),
        ):
            _put(out, key, value)
    return out


def dimensions_de_pose(produit):
    """CAL119 — sélecteur « dimensions de pose », pour construire un kit de
    calepinage depuis un produit réel.

    ``core/calepinage`` travaillait sur des ``Kit`` aux dimensions écrites
    en dur (``core/calepinage/types.py``) et l'unique passerelle
    produit→kit vivait côté AO (``apps/ao/services.py``
    ``kit_panneau_du_produit``), inaccessible à une autre app sans un lien
    direct vers ce module. Ce sélecteur rend le même sous-ensemble, lu
    directement sur ``FicheTechnique`` (PV5/CAL111-118), pour que
    ``apps.calepinage`` construise son kit sans dépendre du module AO ni de
    ``apps.stock.models``.

    Rend ``{longueur_mm, largeur_mm, epaisseur_mm, poids_kg, puissance_wc}``
    — clé ABSENTE (jamais ``None``) si non saisie sur la fiche. Produit sans
    fiche, ou fiche dont ``type_fiche`` n'est pas ``'module'`` → dict VIDE
    (un kit de pose se construit depuis un MODULE, jamais un onduleur/une
    batterie). Lecture seule."""
    fiche = getattr(produit, 'fiche_technique', None)
    if fiche is None or fiche.type_fiche != 'module':
        return {}

    out = {}
    for key, value in (
        ('longueur_mm', fiche.longueur_mm),
        ('largeur_mm', fiche.largeur_mm),
        ('epaisseur_mm', fiche.epaisseur_mm),
        ('poids_kg', fiche.poids_kg),
        ('puissance_wc', fiche.pmax_wc),
    ):
        if value is not None:
            out[key] = value
    return out


def produits_modules_qs(company):
    """CALX109 — les produits MODULE PV du catalogue d'une société.

    ``dimensions_de_pose`` ci-dessus rend les cotes d'UN produit ; il manquait
    la porte qui dit LESQUELS : l'atelier 3D ne connaissait qu'un module, écrit
    en dur dans ``apps/web/src/lib/roofPro2.ts``, alors que les vraies cotes
    dorment sur les fiches (PV5/CAL111-114). Point d'entrée cross-app LECTURE
    SEULE : ``apps.calepinage`` liste ses modules PAR ICI, jamais en important
    ``stock.models``.

    Filtres : la société de l'appelant (jamais un corps de requête), une fiche
    technique de type ``module``, et les produits archivés EXCLUS — même règle
    que la liste catalogue (cf. ``nb_produits_par_entite``). Trié par nom puis
    identifiant, pour que deux appels rendent le même ordre. Rend un QuerySet
    (``select_related`` sur la fiche : une requête, pas une par produit)."""
    from .models import Produit

    return (Produit.objects
            .filter(company=company,
                    fiche_technique__type_fiche='module',
                    is_archived=False)
            .select_related('fiche_technique')
            .order_by('nom', 'id'))


def kit_from_produit(produit):
    """PV6 — construit un ``core.calepinage.types.Kit`` à partir des
    dimensions/puissance de la fiche technique MODULE (PV5) d'un produit.

    Mirrors la construction de ``KIT_VILLA_720`` : 1 module par table,
    orientation PORTRAIT, inclinaison 13°, sans faîtage — les seules valeurs
    fixes que la fiche technique ne porte pas encore ; seules les dimensions
    (``longueur_mm``/``largeur_mm``, converties en mètres) et la puissance
    (``pmax_wc``) viennent du produit. Toute valeur requise absente (produit
    sans fiche, ou l'un des trois champs non renseigné) → ``None`` : le
    moteur de calepinage ne devine jamais une géométrie. Lecture seule."""
    fiche = getattr(produit, 'fiche_technique', None)
    if fiche is None:
        return None
    if (fiche.longueur_mm is None or fiche.largeur_mm is None
            or fiche.pmax_wc is None):
        return None

    from core.calepinage.types import Kit, OrientationModule
    try:
        return Kit(
            code=produit.sku or ('PRODUIT_%s' % produit.pk),
            libelle=produit.nom,
            module_long_m=float(fiche.longueur_mm) / 1000.0,
            module_court_m=float(fiche.largeur_mm) / 1000.0,
            puissance_module_wc=float(fiche.pmax_wc),
            inclinaison_deg=13.0,
            orientation=OrientationModule.PORTRAIT,
            modules_par_table=1,
            faitage_m=0.0,
        )
    except ValueError:
        # dimensions incohérentes (ex. largeur > longueur) — jamais deviner.
        return None
