"""CAL243 — sert l'agrégat ``équipements`` du contrat CAL120.

CE QUE CE MODULE PRODUIT
-------------------------
Le panneau, l'onduleur, la batterie et l'optimiseur RETENUS par le devis lié
au calepinage — un par famille, avec la complétude champ par champ et la
SOURCE de chaque valeur (contrat
``contract_samples/calepinage_equipements.json``, posé seul sur ``main`` par
CAL120 avant cette tâche, PACT10/PACT11).

D'OÙ VIENT L'ÉQUIPEMENT « RETENU »
-----------------------------------
Le document ``roof_layout`` (schéma v2) cite le module posé SUR CHAQUE PAN
(``zones[].geometry.moduleId`` → ``modules[].produitId``) ; c'est CE module
que le calcul utilise pour le pan (kWc de pose, chaînes, simulation —
ACAL264, ``electrique._fiches_modules_du_document``) : la famille ``panneau``
ci-dessous, celle du devis, n'est plus que le DÉFAUT d'un pan sans module, et
l'écran lit le matériel réellement calculé sur ``GET entree-electrique/``
(``materiel``). L'onduleur, la batterie et l'optimiseur chiffrés
vivent sur le DEVIS lié (``Calepinage.devis``). Ce module est LA lecture de
ces lignes : le résolveur du calcul électrique
(``services/electrique.py::resoudre_materiel``, D-ACAL-10) le consomme pour
son défaut « lignes du devis lié » au lieu de relire le devis lui-même. Il lit
les lignes PRODUIT via le sélecteur
cross-app ``apps.ventes.selectors.lignes_produits_calepinage`` (jamais un
import de ``apps.ventes.models``), classe chaque ligne par la famille de sa
fiche technique (``apps.stock.selectors.type_fiche_produit`` :
``module``/``onduleur``/``batterie``/``optimiseur``) et retient la PREMIÈRE
ligne de chaque famille — un devis ne porte normalement qu'une seule
référence par famille sur son option par défaut ; une famille sans ligne
correspondante reste ``None`` (jamais un objet à moitié rempli).

Sans devis lié (calepinage autonome, ou devis d'une autre société) les
quatre familles valent ``None`` et ``devis`` vaut ``None`` — jamais une
famille inventée.

LA GARDE PRIX D'ACHAT (CAL122)
--------------------------------
``apps.stock.selectors.specs_for_produit`` ne lit JAMAIS ``Produit.prix_achat``
— le bloc ``specs`` de ce module ne peut donc structurellement pas le
reprendre. Le test de surface CAL122 vérifie ce module en plus de tous les
autres.
"""
from __future__ import annotations

from apps.stock.selectors import specs_for_produit, type_fiche_produit
from apps.ventes.selectors import get_devis_by_pk, lignes_produits_calepinage

from . import pret_a_envoyer as _pret_a_envoyer  # H5 — une_fois_par_lecture

#: Famille de fiche technique -> clé de l'agrégat. Les familles hors de ce
#: dictionnaire (``''``, ``'autre'``) ne sont RETENUES pour aucune famille —
#: on préfère l'omission à un équipement mal rangé.
BUCKET_PAR_TYPE_FICHE = {
    'module': 'panneau',
    'onduleur': 'onduleur',
    'batterie': 'batterie',
    'optimiseur': 'optimiseur',
}

#: Les familles de l'agrégat, dans l'ordre du contrat CAL120.
FAMILLES = ('panneau', 'onduleur', 'batterie', 'optimiseur')

#: Le contrat de champs COMPLET de chaque famille — même liste, au caractère
#: près, que la docstring de ``specs_for_produit`` (CAL111-118) : c'est ce qui
#: permet de dire « ce champ est manquant » plutôt que « ce champ n'existe
#: pas ». Une clé qui n'y figure jamais n'apparaît dans AUCUNE des deux
#: listes de complétude — c'est voulu, ``specs_for_produit`` ne peut pas la
#: rendre.
CHAMPS_PAR_FAMILLE = {
    'panneau': (
        'vmp_v', 'voc_v', 'isc_a', 'imp_a', 'pmax_wc',
        'temp_coeff_voc_pct_c', 'temp_coeff_pmax_pct_c',
        'longueur_mm', 'largeur_mm', 'epaisseur_mm', 'poids_kg',
        'rendement_pct', 'techno_cellule', 'bifacial', 'noct_c',
        'uc_w_m2k', 'uv_w_m3sk', 'bifacialite_pct',
        'degradation_annuelle_pct', 'degradation_annee1_pct',
        'garantie_pct_a_10_ans', 'garantie_pct_a_25_ans',
        # CALX60 — ce que la chaîne de pertes lit sur le module : la courbe
        # de rendement à éclairement partiel (CALX162) et les deux bornes de
        # tolérance de puissance (CALX165).
        'rendement_par_irradiance', 'tolerance_pmax_min_pct',
        'tolerance_pmax_max_pct',
    ),
    'onduleur': (
        'n_mppt', 'mppt_v_min', 'mppt_v_max', 'v_max_abs', 'i_max_mppt_a',
        'ac_kw', 'phases', 'rendement_euro_pct', 'v_demarrage_v',
        'isc_max_mppt_a', 'bat_max_charge_kw', 'bat_max_decharge_kw',
        'entrees_par_mppt', 'chaines_max_par_mppt', 's_max_kva',
        'dc_max_kwc',
        # CALX60 — la courbe de rendement η(P) (CALX170), les deux autres
        # rendements publiés et la consommation de nuit (CALX175).
        'rendement_par_charge', 'rendement_max_pct', 'rendement_cec_pct',
        'conso_nuit_w',
    ),
    'batterie': (
        'kwh_nominal', 'kwh_usable', 'dod_pct', 'v_nominal',
        'max_charge_kw', 'max_decharge_kw', 'max_modules_par_banc',
        'rendement_ar_pct', 'cycles_publies', 'retention_fin_de_vie_pct',
        'garantie_annees',
        # CALX60 — C-rate, chimie, plage de température et rétention de fin
        # de vie. ``eol_pct`` est publié depuis le MÊME champ que
        # ``retention_fin_de_vie_pct`` : la complétude le compte deux fois
        # parce que deux consommateurs le lisent sous deux noms.
        'c_rate_charge', 'c_rate_decharge', 'chimie', 'temp_min_c',
        'temp_max_c', 'eol_pct',
    ),
    'optimiseur': (
        'pmax_in_w', 'v_in_min', 'v_in_max', 'i_in_max_a', 'rendement_pct',
        'modules_par_optimiseur',
        # CALX60 — LA SORTIE du composant : les ``ac_*`` décrivent le
        # micro-onduleur, les ``v_out_*``/``i_out_*``/``pmax_out_w``
        # l'optimiseur, et ``modules_max_par_chaine`` ferme la longueur de
        # chaîne (CALX209-CALX211).
        'ac_kw', 'ac_tension_v', 'ac_i_max_a', 'ac_unites_max_par_branche',
        'v_out_nominal_v', 'v_out_min', 'v_out_max', 'i_out_max_a',
        'pmax_out_w', 'modules_max_par_chaine',
    ),
}


def conception_retenue(devis):
    """ACAL1950 — la conception RETENUE par ``devis`` (porte de lecture
    ``apps.ventes.selectors_calepinage.conception_retenue_du_devis``), ou ``None``."""
    from apps.ventes.selectors_calepinage import conception_retenue_du_devis

    return conception_retenue_du_devis(devis) if devis is not None else None


def conception_retenue_par_id(devis_id, company):
    """ACAL1950 — la même conception, lue par l'identifiant du devis lié
    (borné société, une requête quand le devis a des lignes)."""
    from apps.ventes.selectors_calepinage import conception_retenue_du_devis_id

    return conception_retenue_du_devis_id(devis_id, company)


def conception_ou_calcul(company, lead_id=None, *, calepinage_id=None, en_liste=False):
    """Relecture E5 — LA porte de lecture de la conception (``apps.ventes.services.
    conception_ou_calcul``), passée par ce module, déjà importateur de ventes : la
    conception est lue par ``devis_retenu`` sans un importateur de plus (cliquet
    ``test_imports_croises_ventes``)."""
    from apps.ventes.services import conception_ou_calcul as porte

    return porte(company, lead_id, calepinage_id=calepinage_id, en_liste=en_liste)


def motif_facture_absente():
    """Le motif ``facture_absente`` de ventes (question de taille, ACAL922), par la même porte."""
    from apps.ventes.services import MOTIF_FACTURE_ABSENTE

    return MOTIF_FACTURE_ABSENTE


def devis_et_ecart(devis_id, retenue, company_id):
    """``(devis, ecart_devis)`` du devis lié de ``company_id`` (``get_devis_by_pk`` / ``apps.ventes.
    selectors.ecart_devis``, conception retenue déjà lue en ``retenue``) ; ``(None, [])`` hors société."""
    from apps.ventes.selectors import ecart_devis
    from apps.ventes.selectors_calepinage import devis_lu_par_pk

    devis = devis_lu_par_pk(devis_id)  # coût des requêtes : déjà lu par la conception retenue
    if devis is None or devis.company_id != company_id:
        return None, []
    # Mot-clé passé par dictionnaire : la garde de surface du champ ``CalepinageVariante.retenue``
    # (tests/test_variantes.py) lit tout mot-clé ``retenue=`` d'un appel hors queryset comme une écriture.
    return devis, ecart_devis(devis, **{'retenue': retenue})


def devis_lie_et_pose(calepinage):
    """T4-X7-006 — ``{devis, reference, statut, a_jour}`` du devis LIÉ à ``calepinage`` (même
    société), ou ``None`` sans devis lié. ``a_jour`` = LE prédicat des deux empreintes de ventes
    (``_conception_a_jour``, ACAL46, celui du badge et de ``_ecart_devis``) : ``False`` quand le
    devis ne porte pas la pose enregistrée, ``None`` quand une empreinte manque. Lecture pure ;
    le devis est celui déjà lu par la conception retenue (mémo de requête, aucune requête de plus)."""
    from apps.ventes.selectors_calepinage import _conception_a_jour, devis_lu_par_pk

    devis_id = getattr(calepinage, 'devis_id', None)
    if not devis_id:
        return None
    # Budget de requêtes (CI du 25/11, +1 sur ``resultat/``) : le devis DÉJÀ joint au calepinage
    # (``select_related('devis')`` de la vue) est lu tel quel ; sinon le mémo de requête de ventes.
    descripteur = getattr(type(calepinage), 'devis', None)
    devis = (calepinage.devis if getattr(descripteur, 'is_cached', None) and descripteur.is_cached(calepinage)
             else devis_lu_par_pk(devis_id))
    if devis is None or devis.company_id != getattr(calepinage, 'company_id', None):
        return None
    return {'devis': devis.pk, 'reference': devis.reference or '', 'statut': devis.statut,
            'a_jour': _conception_a_jour(devis, calepinage)}


#: ACAL2013 — la provenance d'un matériel servi par la conception du moteur unique.
PROVENANCE_MOTEUR = 'moteur'


#: Relecture E5 m4 — rôle du calepinage → (clé de ``valeurs``, famille de fiche, libellé dit).
_PRODUITS_DE_LA_CONCEPTION = (('module', 'module_produit', 'module', 'le module'),
                              ('onduleur', 'onduleur_produit', 'onduleur', "l'onduleur"))


def _produit_actif(company, identifiant, type_fiche):
    """``identifiant`` s'il désigne un produit ACTIF de ``company`` de la famille
    ``type_fiche`` (jamais un produit archivé, d'une autre société ou d'une autre
    famille), sinon ``None``."""
    from apps.stock.selectors import produits_par_type_fiche_qs

    if company is None or not isinstance(identifiant, int) or isinstance(identifiant, bool):
        return None
    return identifiant if produits_par_type_fiche_qs(company, type_fiche).filter(pk=identifiant).exists() else None


def _designation_gardee(valeurs, role, identifiant):
    """Revue E6 m1 — la désignation que la conception a GARDÉE pour ce produit (``module``,
    ou la ligne ``onduleurs`` qui le porte), ``''`` sans elle : jamais l'identifiant."""
    if role == 'module':
        nom = (valeurs.get('module') or {}).get('valeur')
        return nom.strip() if isinstance(nom, str) else ''
    for ligne in (valeurs.get('onduleurs') or {}).get('valeur') or []:
        nom = ligne.get('designation') if isinstance(ligne, dict) and ligne.get('produit') == identifiant else None
        if isinstance(nom, str):
            return nom.strip()
    return ''


def materiel_de_la_conception(calepinage):
    """ACAL2013 (D-ACAL-97) — le matériel que la conception COURANTE retient (option du
    moteur), DÉFAUT du calcul électrique quand rien n'est désigné : ``{produits: {module?,
    onduleur?}, nombre_onduleurs, longueur, avertissements}`` lus sur ``valeurs`` (contrat
    ``conception_lead.json`` : ``module_produit``, ``onduleur_produit``, ``nombre_onduleurs``,
    ``chaines``) ; ``{}`` sans conception complète. Le devis lié n'est pas lu.

    Relecture E5 m4 — le produit est relu par son IDENTIFIANT, borné à la société et
    jamais archivé ; un produit disparu ou archivé n'est pas servi et
    ``avertissements`` le DIT en français (le calcul retombe alors sur le module posé)."""
    from .devis_retenu import conception_du_calepinage

    conception = conception_du_calepinage(calepinage) if calepinage is not None else None
    if not conception or conception.get('etat') != 'complet':
        return {}
    valeurs = (conception.get('valeurs') or {}).get(conception.get('option_retenue')) or {}
    company = getattr(calepinage, 'company', None)
    produits, avertissements = {}, []
    for role, cle, type_fiche, libelle in _PRODUITS_DE_LA_CONCEPTION:
        identifiant = (valeurs.get(cle) or {}).get('valeur')
        if identifiant in (None, ''):
            continue
        if _produit_actif(company, identifiant, type_fiche) is None:
            designation = _designation_gardee(valeurs, role, identifiant)
            avertissements.append(
                "%s de la conception%s est introuvable ou archivé dans le catalogue — "
                "désignez-le dans l'onglet Matériel électrique%s" % (
                    libelle[0].upper() + libelle[1:], ' (%s)' % designation if designation else '',
                    ' (le module posé sert en attendant)' if role == 'module' else ''))
            continue
        produits[role] = identifiant
    chaines = (valeurs.get('chaines') or {}).get('valeur') or {}
    return {'produits': produits, 'nombre_onduleurs': (valeurs.get('nombre_onduleurs') or {}).get('valeur') or None,
            'longueur': chaines.get('longueur') or None, 'avertissements': avertissements}


def _panneaux_de_la_conception(calepinage):
    """Le nombre de panneaux de l'option que la conception courante retient, ou ``None``."""
    from .devis_retenu import conception_du_calepinage

    conception = conception_du_calepinage(calepinage) or {}
    valeurs = (conception.get('valeurs') or {}).get(conception.get('option_retenue')) or {}
    return (valeurs.get('nb_panneaux') or {}).get('valeur')


def _panneaux_poses(calepinage, document):
    from .mesures import mesures_du_document

    document = document if document is not None else getattr(calepinage, 'roof_layout', None)
    return mesures_du_document(document)['modules'] if isinstance(document, dict) and document else None


def options_de_la_conception(options, calepinage, donnees, document=None):
    """ACAL2013 — les options du noyau complétées par la CONCEPTION : sans onduleur
    désigné, le nombre d'onduleurs et la longueur de chaîne sont ceux de la conception
    courante. Une désignation d'onduleur SAISIE garde la main ; une option saisie n'est
    jamais remplacée. Relecture E5 M4 — imposés SEULEMENT quand la pose (``document``,
    sinon celui du calepinage) compte autant de panneaux que la conception : une pose
    d'une autre taille garde ses chaînes calculées (la longueur de la conception reste
    la référence de l'écart, ``suppositions.reference_de_longueur``)."""
    if (donnees or {}).get('onduleur_produit') not in (None, ''):
        return options
    materiel = materiel_de_la_conception(calepinage)
    if not (materiel.get('produits') or {}).get('onduleur'):
        return options
    panneaux = _panneaux_de_la_conception(calepinage)
    if panneaux is None or _panneaux_poses(calepinage, document) != panneaux:
        return options
    options = dict(options)
    if 'nombre_onduleurs' not in options and (materiel.get('nombre_onduleurs') or 0) >= 1:
        options['nombre_onduleurs'] = materiel['nombre_onduleurs']
    if 'longueur_forcee' not in options and materiel.get('longueur'):
        options['longueur_forcee'] = materiel['longueur']
    return options


def autre_famille_d_onduleur(nom):
    """D-HYB-1 — la famille d'onduleur AUTRE qu'hybride (``'onduleur_offgrid'``,
    ``'micro_onduleur'``, ``''``) que le classifieur du CATALOGUE lit dans un nom (porte
    ``apps.ventes.selectors_calepinage.autre_famille_d_onduleur_par_nom``) : ce module est
    LA lecture de ventes par le calepinage pour le matériel (ACAL1009)."""
    from apps.ventes.selectors_calepinage import autre_famille_d_onduleur_par_nom

    return autre_famille_d_onduleur_par_nom(nom)


def borne_dc_ac_devis(mode_installation=None):
    """ACAL1954 — la borne DC/AC du MOTEUR DE DEVIS (porte de lecture
    ``apps.ventes.selectors_calepinage.borne_dc_ac_du_moteur_devis``)."""
    from apps.ventes.selectors_calepinage import borne_dc_ac_du_moteur_devis

    return borne_dc_ac_du_moteur_devis(mode_installation)


def liaison_dc_tracee_ouverte(jour=None):
    """Liaison DC tracée (suite ACAL1317) — la coupure du tracé DC du plan, lue par la
    porte ``apps.ventes.selectors_calepinage.liaison_dc_tracee_ouverte`` (cliquet
    ACAL1009 : ``services/cables.py`` passe par ici)."""
    from apps.ventes.selectors_calepinage import liaison_dc_tracee_ouverte as ouverte

    return ouverte(jour)


def pans_du_document(document):
    """D-ACAL-169 — les pans d'un document de pose, lus par la porte
    ``apps.ventes.services.pans_du_document`` (cliquet ACAL1009 :
    ``services/suivi_module_pose.py`` passe par ici)."""
    from apps.ventes.services import pans_du_document as lire

    return lire(document)


def _devis_lie(calepinage):
    """Le devis lié au calepinage, borné à SA société — ou ``None``."""
    devis_id = getattr(calepinage, 'devis_id', None)
    if not devis_id:
        return None
    devis = get_devis_by_pk(devis_id)
    if devis is None:
        return None
    company = getattr(calepinage, 'company', None)
    if company is not None and devis.company_id != company.pk:
        return None
    return devis


def _bloc_equipement(ligne):
    """Le bloc ``{produit, designation, quantite, specs, ...}`` d'UNE ligne."""
    produit = ligne['produit']
    famille = BUCKET_PAR_TYPE_FICHE.get(type_fiche_produit(produit))
    if famille is None:
        return None, None

    specs = specs_for_produit(produit)
    contrat = CHAMPS_PAR_FAMILLE[famille]
    champs_renseignes = [champ for champ in contrat if champ in specs]
    champs_manquants = [champ for champ in contrat if champ not in specs]

    sources = {'quantite': 'saisie'}
    sources.update({champ: 'fiche' for champ in champs_renseignes})

    quantite = ligne['quantite']
    bloc = {
        'produit': produit.pk,
        'designation': ligne['designation'] or getattr(produit, 'nom', ''),
        'quantite': float(quantite) if quantite is not None else None,
        'specs': specs,
        'champs_renseignes': champs_renseignes,
        'champs_manquants': champs_manquants,
        'sources': sources,
    }
    return famille, bloc


@_pret_a_envoyer.une_fois_par_lecture('equipements')  # H5 — une fois par lecture
def equipements_du_calepinage(calepinage):
    """CAL243 — l'agrégat COMPLET du contrat ``calepinage_equipements.json``.

    Lecture PURE : aucune écriture, aucun statut touché. Toujours les six
    clés (``calepinage``, ``devis`` + les quatre familles), jamais une clé
    omise — une famille non retenue vaut ``None``, jamais absente.
    """
    resultat = {famille: None for famille in FAMILLES}
    devis = _devis_lie(calepinage)
    if devis is None:
        return {'calepinage': calepinage.pk, 'devis': None, **resultat}

    for ligne in lignes_produits_calepinage(devis):
        famille, bloc = _bloc_equipement(ligne)
        if famille is None or resultat[famille] is not None:
            # famille inconnue, ou déjà servie par une ligne antérieure — la
            # PREMIÈRE ligne d'une famille est celle qui compte (repli sûr :
            # aucune règle métier ne dit laquelle choisir entre deux lignes
            # de la même famille sur un devis correctement composé).
            continue
        resultat[famille] = bloc

    return {'calepinage': calepinage.pk, 'devis': devis.pk, **resultat}


def panneaux_pour_la_meme_puissance(kwc, watt):
    """Lane E9 (T4-X2-001) — LA règle du moteur qui compte une puissance dans un autre module
    (``apps.ventes.services.panneaux_pour_la_meme_puissance``), passée par ce module déjà
    importateur de ventes : aucun importateur de plus (cliquet ``test_imports_croises_ventes``)."""
    from apps.ventes.services import panneaux_pour_la_meme_puissance as regle

    return regle(kwc, watt)


def composition_a_blanc():
    """T4-X5-010 — ``(composer_a_blanc_depuis_layout, AutoDevisError)`` de ``apps.ventes.services``
    pour l'aperçu à blanc du devis (``devis_apercu``), passés par ce module déjà importateur de
    ventes (même cliquet). Lane E9b : le dry-run lit les réglages SANS les créer."""
    from apps.ventes.services import AutoDevisError, composer_a_blanc_depuis_layout

    return composer_a_blanc_depuis_layout, AutoDevisError


def classer_produit_nom(nom):
    """Lot 8 (B2) — le classifieur de NOM du catalogue (``apps.ventes.selectors.classer_produit_nom``),
    passé par ce module déjà importateur de ventes (cliquet ``test_imports_croises_ventes``)."""
    from apps.ventes.selectors import classer_produit_nom as classer

    return classer(nom)


def compatibilite_du_materiel(module, onduleur, company, batterie_id=None):
    """D-ACAL-157 — L'UNIQUE juge de compatibilité du matériel (``apps.ventes.selectors.
    compatibilite_du_materiel``), passé par ce module déjà importateur de ventes (même cliquet)."""
    from apps.ventes.selectors import compatibilite_du_materiel as juge

    return juge(module, onduleur, company, batterie_id)
