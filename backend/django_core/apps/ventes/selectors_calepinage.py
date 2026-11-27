"""Sélecteurs LECTURE SEULE du calepinage et de la conception 3D du devis
(contexte de conception, calepinage et schéma unifilaire du devis, péremption
du layout, comparaison calepinage/devis) — sortis de
``apps/ventes/selectors.py`` par SPL144 (déplacement pur, corps inchangés ;
propriétaire : calepinage).

Les autres apps continuent de lire ces fonctions par la FAÇADE
``apps.ventes.selectors`` (ré-export en fin de fichier) ; ce module est PLAT :
aucun import de ``.selectors`` en tête (cycle).
"""


import logging


def conception_pour_lead(lead, company):
    """PV78 — la conception 3D la plus RÉCENTE d'un lead, en lecture seule.

    Rend TOUJOURS le même dict ``{kwc, image_url}`` — jamais une clé absente,
    jamais un ``None`` global : une fiche lead sans conception affiche deux
    valeurs vides, elle ne plante pas sur ``undefined``.

    * ``kwc`` — ACAL2021 : la puissance crête de la CONCEPTION courante du lead
      (moteur unique, ``conception_courante``), ``None`` sans conception — plus
      celle du dernier devis ni du calepinage ;
    * ``image_url`` — ACAL314 : chemin RELATIF du rendu 3D servi par Django
      (``/api/django/ventes/devis/<id>/roof-image/fichier/``, même origine,
      cookie httpOnly) — jamais une URL pré-signée portant l'hôte interne du
      magasin, jamais une URL de bucket publique.

    Company-scopée : seul un devis de ``company`` est regardé (un lead d'une
    autre société ne fait rien fuiter). Point d'entrée cross-app pour
    ``apps.crm`` — jamais un import des modèles ventes de son côté.
    """
    vide = {'kwc': None, 'image_url': None, 'calepinage': None, 'devis': None}
    lead_id = getattr(lead, 'pk', None) or getattr(lead, 'id', None)
    if not lead_id or company is None:
        return vide
    from .models import Devis
    tous = Devis.objects.filter(lead_id=lead_id, company=company)
    devis = (tous.filter(roof_layout__isnull=False)
             .order_by('-date_creation', '-id').first())

    # ACAL2021 — la pastille lit la CONCEPTION courante (moteur unique) : plus le
    # kWc du dernier devis ni du calepinage. R2-10 — le LIEN vers le calepinage
    # et le devis le plus récent restent servis (devis ou non).
    dernier = tous.order_by('-date_creation', '-id').first()
    ouvert = _calepinage_ouvert_mesure(company, lead_id, avec_kwc=False)
    calepinage = ouvert['calepinage'] if ouvert else None
    kwc = _kwc_de_la_conception(company, lead_id)

    image_url = None
    if devis is not None and (devis.roof_image or '').strip():
        from .domain.stockage_toiture import url_fichier_toiture_devis
        image_url = url_fichier_toiture_devis(devis.pk)
    # Clé ADDITIVE : le devis le plus récent du lead (statut : « vendus » ne se
    # dit que d'un devis accepté).
    return {'kwc': kwc, 'image_url': image_url, 'calepinage': calepinage,
            'devis': ({'id': dernier.pk, 'reference': dernier.reference,
                       'statut': dernier.statut}
                      if dernier is not None else None)}


logger = logging.getLogger(__name__)


def _kwc_de_la_conception(company, lead_id):
    """ACAL2021 — le kWc de l'option retenue de la conception COURANTE du lead
    (``kwc_de_la_conception_courante`` : une requête), ``None`` sans conception, en
    refus ou sans valeur : jamais un kWc supposé."""
    from .selectors_conception import kwc_de_la_conception_courante
    brut = kwc_de_la_conception_courante(company, lead_id)
    try:
        return float(brut) if brut not in (None, '') else None
    except (TypeError, ValueError):
        return None


def _calepinage_ouvert_mesure(company, lead_id, avec_kwc=True):
    """ACAL273 / R2-10 — ``{'kwc', 'calepinage': {id, statut, reference}}`` du
    calepinage OUVERT du lead, lu par ``apps.calepinage.selectors`` (import
    fonction-local, jamais les modèles) ; ``kwc`` (``mesures_du_calepinage``)
    n'est lu que si ``avec_kwc`` (sinon ``None``) ; ``None`` sans calepinage
    ouvert."""
    try:
        from apps.calepinage.selectors import (
            calepinage_ouvert_du_lead, mesures_du_calepinage,
            reference_calepinage,
        )
        calepinage = calepinage_ouvert_du_lead(company, lead_id)
        if calepinage is None:
            return None
        mesure = mesures_du_calepinage(calepinage) if avec_kwc else {}
        kwc = (mesure or {}).get('kwc')
        return {'kwc': float(kwc) if kwc else None,
                'calepinage': {'id': calepinage.pk, 'statut': calepinage.statut,
                               'reference': reference_calepinage(calepinage)}}
    except Exception as exc:  # noqa: BLE001 — une pastille ne casse jamais la fiche (D-ENF22-BLE001)
        logger.warning('ACAL273 : calepinage du lead %s indisponible : %s', lead_id, exc)
        return None


def pose_du_lead(company, lead_id):
    """Relecture E3 M2 — ``(calepinage_id, empreinte_pose)`` du calepinage
    OUVERT du lead (``calepinage_ouvert_du_lead``) quand une pose y est
    enregistrée (``layout_hash`` : l'empreinte que ``pose_enregistree``
    transporte), sinon ``(None, '')``. Lecture seule."""
    from apps.calepinage.selectors import calepinage_ouvert_du_lead
    calepinage = calepinage_ouvert_du_lead(company, lead_id)
    if calepinage is None or not (calepinage.layout_hash or '').strip():
        return None, ''
    return calepinage.pk, calepinage.layout_hash


def calepinage_de_societe(calepinage_id, company):
    """ADEV136 — UN calepinage borné SOCIÉTÉ (appelants système), ou ``None`` ;
    passe par ``apps.calepinage.selectors.calepinage_detail``."""
    from apps.calepinage.selectors import calepinage_detail
    return calepinage_detail(calepinage_id, company)


def calepinage_visible_pour(user, company, calepinage_id):
    """ADEV137 — le calepinage que ``user`` VOIT dans ``company``, ou ``None``
    (``apps.calepinage.selectors.calepinages_visibles``, le prédicat d'accès)."""
    from apps.calepinage.selectors import calepinages_visibles
    if company is None:
        return None
    return calepinages_visibles(user).filter(pk=calepinage_id, company=company).first()


def calepinage_du_devis(devis, company=None):
    """CAL28 — le calepinage qui PILOTE ce devis, ou ``None``.

    Le lien inverse n'existait pas : la fiche devis ne savait pas qu'un
    calepinage la pilote, alors que c'est lui qui porte les versions, les
    variantes et la planche. Cette fonction est le pont — MINCE, en lecture
    seule, et passant par ``apps.calepinage.selectors`` (import FONCTION-LOCAL
    pour éviter le cycle au chargement) : ``ventes`` n'importe JAMAIS
    ``apps.calepinage.models``.

    ``a_jour`` est une COMPARAISON DES DEUX EMPREINTES, jamais un recalcul de
    géométrie : le devis et son calepinage portent la même empreinte tant que
    la conception n'a pas divergé. Empreinte manquante d'un côté ⇒ ``None``
    (inconnu), jamais ``False`` — on ne déclare pas « périmé » ce qu'on n'a pas
    mesuré.
    """
    from apps.calepinage.selectors import calepinage_du_devis as _lire
    from apps.calepinage.selectors import reference_calepinage

    if devis is None:
        return None
    company = company or getattr(devis, 'company', None)
    calepinage = _lire(getattr(devis, 'pk', None), company)
    if calepinage is None:
        return None
    return {
        'id': calepinage.pk,
        'titre': calepinage.titre or '',
        # R2-12 — la référence dérivée, pour nommer un calepinage sans titre.
        'reference': reference_calepinage(calepinage),
        'layout_hash': (calepinage.layout_hash or '') or None,
        'a_jour': _conception_a_jour(devis, calepinage),
    }


def conception_rapide_du_devis(devis):
    """ACAL1196 — ``True`` si la conception du devis est « rapide » (non
    vérifiée). Porte de ``public_views`` vers ``calepinage.selectors``."""
    from apps.calepinage.selectors import calepinage_du_devis as _lire

    calepinage = _lire(getattr(devis, 'pk', None),
                       getattr(devis, 'company', None))
    return getattr(calepinage, 'etat_conception', '') == 'rapide'


def _conception_a_jour(devis, calepinage):
    """ACAL46 — LE prédicat « la conception du devis est celle de son
    calepinage » : comparaison des DEUX empreintes imprimées (ACAL40), jamais
    un recalcul de géométrie. ``True``/``False``, ou ``None`` (inconnu) dès
    qu'une empreinte manque — on ne déclare pas « périmé » ce qu'on n'a pas
    mesuré. Partagé par :func:`calepinage_du_devis` (badge ``a_jour``) et
    :func:`peremption_layout_devis` (``conception_divergente``)."""
    if devis is None or calepinage is None:
        return None
    empreinte_devis = getattr(devis, 'layout_hash', '') or ''
    empreinte_cal = getattr(calepinage, 'layout_hash', '') or ''
    if not (empreinte_devis and empreinte_cal):
        return None
    selection = selection_lue_du_devis(devis, calepinage)
    if selection is not None:
        # ACAL968 — un devis qui ne chiffre qu'une PARTIE des surfaces porte
        # l'empreinte de SA copie : comparée à la même copie du document courant.
        from apps.calepinage.selectors import empreinte_de_la_selection

        empreinte_cal = empreinte_de_la_selection(calepinage, selection)
    return empreinte_devis == empreinte_cal


def surfaces_chiffrees_du_devis(devis):
    """ACAL968 (D-ACAL-37) — les clés des surfaces que CE devis chiffre
    (``roof_layout.choixConception.surfacesChiffrees``), ou ``None`` : le devis
    chiffre tout le document. Lecture seule."""
    document = getattr(devis, 'roof_layout', None)
    choix = document.get('choixConception') if isinstance(document, dict) else None
    selection = choix.get('surfacesChiffrees') if isinstance(choix, dict) else None
    return selection if isinstance(selection, list) else None


def selection_lue_du_devis(devis, calepinage):
    """ACAL1249 — la sélection du devis LUE contre le document de
    ``calepinage`` : un pan existant (Critique D1, jamais vendu) coché avant
    X4 en est retiré ; la sélection rangée n'est pas réécrite."""
    from .domain.geometrie import pans_du_document
    if (selection := surfaces_chiffrees_du_devis(devis)) is None:
        return None
    existants = {p['cle'] for p in pans_du_document(getattr(calepinage, 'roof_layout', None) or {})
                 if p.get('existant')}
    return [cle for cle in selection if cle not in existants]


def figure_stockee_imprimee(devis):
    """ACAL1274 — la production lue SANS rendu (``selectors.
    production_attendue_pour_devis``) est-elle celle que le PDF imprime ? Non
    en C&I ni en agricole (moteur C&I, aucun kWh), ni quand le calepinage l'a
    posée aux règles corrigées (AMOT15 : le moteur du devis la recalcule)."""
    from .domain.etude_schema import PRODUCTION_CALEPINAGE
    from .domain.regles_calcul import calcul_corrige
    if (getattr(devis, 'mode_installation', None) or 'residentiel') != 'residentiel':
        return False
    source = (getattr(devis, 'etude_params', None) or {}).get('production_source')
    return not (source == PRODUCTION_CALEPINAGE and calcul_corrige(devis))


def kwc_lu_du_layout(layout):
    """Critique 22/11 — le kWc du document tel que LA composition le lit
    (``geometrie.lire_layout``), pour la garde ACAL914 du calepinage."""
    from .domain.geometrie import lire_layout

    return lire_layout(layout).kwc


def schema_unifilaire_svg(*, devis=None, entree=None, resultat=None,
                          cartouche=None, standard=False):
    """CAL195 — LE producteur de schéma unifilaire, par SA porte cross-app.

    Le schéma existe depuis PV46, mais il était enfermé : il part d'un DEVIS,
    et le seul chemin vers lui traverse le moteur vendorisé
    (``quote_engine.builder._sld_svg``). Or ce moteur REND — il ne s'importe
    pas (règle #4), et aucune autre app n'a le droit d'atteindre un de ses
    modules internes. Un calepinage sans devis n'avait donc aucun schéma, alors
    que le dessin lui-même est produit par un module PUR
    (``core.electrique.schema``) qui ne connaît ni devis, ni prix, ni statut.

    Cette fonction est la porte, et elle ne DESSINE rien :

    * ``devis=`` — délégation stricte à ``electrical_service.
      rendre_schema_du_devis``, l'appel que ``_sld_svg`` fait déjà. Le SVG
      d'un devis reste donc BYTE-IDENTIQUE : aucun paramètre n'est ajouté,
      aucun repli n'est introduit, et les trois portails (étude présente,
      fiches complètes, conception conforme) restent les siens.
    * ``entree=``/``resultat=`` — un appelant qui porte DÉJÀ les objets du
      moteur électrique (``core.electrique.types``) : c'est le cas d'
      ``apps.calepinage``, dont la ``Conception`` (CAL124) est bâtie sur ces
      mêmes types, chaînes par MPPT (CAL125), câbles dimensionnés (CAL131) et
      check-list d'organes (CAL132) comprises. Le dessin est alors celui du
      MÊME moteur, jamais une seconde planche.

    ``None`` dès qu'il manque de quoi dessiner — même discipline que
    PVFCH-ANNEXE : une fiche incomplète n'obtient PAS un schéma approximatif,
    elle n'en obtient aucun.
    """
    if devis is not None:
        from .electrical_service import rendre_schema_du_devis
        return rendre_schema_du_devis(devis, standard=standard)
    if entree is None or resultat is None:
        return None
    from core.electrique.schema import rendre_schema
    return rendre_schema(entree, resultat, cartouche=cartouche or {},
                         standard=standard)


def lignes_produits_calepinage(devis):
    """CAL243 — les lignes PRODUIT « retenues » d'un devis, pour l'équipement
    d'un calepinage lié.

    Point d'entrée cross-app LECTURE SEULE (``apps.calepinage`` n'importe
    JAMAIS ``apps.ventes.models``) : un objet léger par ligne
    (``produit``, ``designation``, ``quantite``), jamais le modèle
    ``LigneDevis`` lui-même. Ne rend que les lignes de type ``'produit'``
    dont le produit est renseigné, et EXCLUT la variante ``'avec'`` (option
    « avec batterie ») : la disposition retient l'équipement de l'option PAR
    DÉFAUT (commune + « sans »), jamais un mélange des deux options d'un
    devis « Les deux ». Devis ``None`` -> liste vide.
    """
    if devis is None:
        return []
    return [
        {'produit': ligne.produit, 'designation': ligne.designation,
         'quantite': ligne.quantite}
        for ligne in (devis.lignes
                      .filter(type_ligne='produit', produit_id__isnull=False)
                      .exclude(variante='avec')
                      .select_related('produit')
                      .order_by('id'))
    ]


def cible_du_devis_agricole_du_lead(lead_id, company):
    """ACAL1268 (D-ACAL-66 = outil_pose) — le CHAMP DE PANNEAUX du devis agricole
    du lead : ``{panneaux, kwc, panel_watt, devis: {id, reference}}``, lu dans les
    lignes du devis agricole courant (ni refusé, ni expiré, ni remplacé) le plus
    récent QUI PORTE DES PANNEAUX (un brouillon vide plus récent ne masque pas un
    devis plus ancien), ou ``None``. La MÊME lecture que l'atelier devis
    (``cible_depuis_lignes``) : aucun second dimensionnement. Lecture seule,
    bornée par ``company``."""
    from .models import Devis
    from .selectors import devis_en_jeu
    from .services import cible_depuis_lignes
    if not lead_id or company is None:
        return None
    candidats = (devis_en_jeu(Devis.objects.filter(
        company=company, lead_id=lead_id,
        mode_installation=Devis.ModeInstallation.AGRICOLE))
        .exclude(statut__in=[Devis.Statut.REFUSE, Devis.Statut.EXPIRE])
        .order_by('-id'))
    for devis in candidats:
        cible = cible_depuis_lignes(devis)
        if cible.get('panneaux'):
            return {'panneaux': int(cible['panneaux']), 'kwc': cible.get('kwc'),
                    'panel_watt': cible.get('panel_watt'),
                    'devis': {'id': devis.pk, 'reference': devis.reference or ''}}
    return None


def dernier_devis_recu_du_lead(company, lead_id):
    """ACAL1955 — le dernier devis ACTIF du lead que le client a reçu (envoyé ou
    accepté ; le plus récemment envoyé), ou ``None``. Borné société, lecture
    seule."""
    from .models import Devis

    if company is None or not lead_id:
        return None
    return (Devis.objects
            .filter(company=company, lead_id=lead_id, is_active=True,
                    statut__in=STATUTS_DEVIS_RECU)
            .order_by('-date_envoi', '-id').first())


def autre_famille_d_onduleur_par_nom(nom):
    """D-HYB-1 — la famille d'onduleur AUTRE qu'hybride que le classifieur du catalogue lit
    dans le NOM d'un produit : ``'micro_onduleur'`` (``solar_classification.est_micro_onduleur``),
    ``'onduleur_offgrid'`` (``domain.catalogue.classer_produit``), ``''`` sinon — et ``''``
    quand le nom dit « onduleur hybride » (un micro-onduleur hybride reste hybride, ADCG45)."""
    from .domain.catalogue import classer_produit
    from .solar_classification import est_micro_onduleur

    classe = classer_produit(nom or '')
    if classe == 'onduleur_hybride':
        return ''
    if est_micro_onduleur(nom or ''):
        return 'micro_onduleur'
    return classe if classe == 'onduleur_offgrid' else ''


def borne_dc_ac_du_moteur_devis(mode_installation=None):
    """ACAL1954 / D-ACAL-91 — la borne haute du ratio DC/AC que le MOTEUR DE
    DEVIS applique quand la société n'a réglé aucune fourchette, LUE à sa
    source (jamais recopiée) : moteur C&I = borne usuelle de
    ``core.electrique.onduleurs.bornes_dc_ac`` (``moteur_ci/onduleurs``),
    résidentiel = ``solar_design.MAX_DC_AC``. Un nombre (kWc par kW AC)."""
    if (mode_installation or '') in ('commercial', 'industriel'):
        from core.electrique.onduleurs import bornes_dc_ac

        return float(bornes_dc_ac().borne_usuelle.valeur)
    from .solar_design import MAX_DC_AC

    return float(MAX_DC_AC)


#: ACAL1950 — les statuts d'un devis que le client a déjà reçu.
STATUTS_DEVIS_RECU = ('envoye', 'accepte')


def conception_retenue_du_devis_id(devis_id, company):
    """ACAL1950 — :func:`conception_retenue_du_devis` du devis ``devis_id``
    de ``company`` (``None`` s'il n'existe pas ou appartient à une autre
    société), en UNE requête quand le devis a des lignes (lignes, produit et
    devis joints) : budget de requêtes des écrans du calepinage."""
    from .models import Devis, LigneDevis

    if not devis_id or company is None:
        return None
    lignes = list(LigneDevis.objects.filter(devis_id=devis_id, devis__company=company)
                  .select_related('devis', 'produit').order_by('id'))
    devis = (lignes[0].devis if lignes
             else Devis.objects.filter(pk=devis_id, company=company).first())
    if devis is not None:
        _garder_devis_lu(devis)
    return conception_retenue_du_devis(devis, lignes=lignes) if devis is not None else None


def _cle_devis_lu(devis_id):
    return ('ventes.selectors_calepinage.devis_lu', devis_id)


def _garder_devis_lu(devis):
    """Coût des requêtes (lot 4) — le devis que :func:`conception_retenue_du_devis_id` vient de lire
    est gardé pour la requête (``core.request_cache``, aucun effet hors requête)."""
    from core import request_cache

    request_cache.memoize(_cle_devis_lu(devis.pk), lambda: devis)


def devis_lu_par_pk(devis_id):
    """Le devis ``devis_id`` (non borné : l'appelant vérifie la société) : celui déjà lu par
    :func:`conception_retenue_du_devis_id` dans la requête, sinon ``ventes.selectors.get_devis_by_pk``.
    Lecture pour un écran (écart d'un devis reçu), jamais avant une écriture."""
    from core import request_cache

    from .selectors import get_devis_by_pk

    return request_cache.memoize(_cle_devis_lu(devis_id), lambda: get_devis_by_pk(devis_id))


def conception_retenue_du_devis(devis, lignes=None):
    """ACAL1950 — LA conception que le devis a retenue, LUE (rien n'est
    recalculé, rien n'est écrit) : ce que le calepinage d'un devis envoyé doit
    reprendre au lieu de refaire son propre dimensionnement.

    Rend ``None`` sans devis, sinon (contrat
    ``apps/calepinage/contract_samples/calepinage_conception_retenue.json``) ::

        {devis, reference, statut, recu, option, deux_options, module,
         onduleurs, chaines, production_annuelle_kwh, production_origine}

    * ``option`` — ``'sans'`` | ``'avec'``. Un devis à DEUX options (lignes
      variantées, ou scénario « Les deux » — et l'option « avec » servable,
      ``option_avec_servable``) retient l'option RECOMMANDÉE
      (``recommended_option``, registre d'abord : ``scenario.
      recommended_option_effective``) ; sans recommandation lisible, la même
      option que le PDF met en avant (« Avec batterie »). Un devis à option
      unique retient celle qu'il sert.
    * ``module`` — ``{produit, designation, quantite, watt}`` de l'option
      (quantité = somme des lignes panneau de l'option, même classifieur que
      ``cible_depuis_lignes`` ; ``watt`` = libellé, sinon fiche, sinon
      ``None``) ; ``None`` sans ligne panneau.
    * ``onduleurs`` — ``[{produit, designation, quantite}]`` de l'option.
    * ``chaines`` — ``{nombre, longueurs, longueur}`` lus dans la conception
      électrique RANGÉE du devis (``electrical_design.chaines``), ``None``
      quand le devis n'en porte pas OU quand elle décrit l'autre option (la
      conception électrique d'un devis à deux options est celle de l'option
      « avec », ``electrical_service._option_choisie``) — jamais un mélange.
    * ``production_annuelle_kwh`` — la production annuelle que le devis a
      retenue : C&I ``etude_ci.bilan`` (option « avec » :
      ``etude_ci.option_avec.bilan``) ; résidentiel ``etude_horaire.annuel``
      (option « sans » d'un devis divergent : ``etude_horaire_sans``), à
      défaut ``production_annuelle`` (figure recalée, ACAL101) quand les deux
      options ont le même champ. Clé absente ⇒ ``None``, jamais un nombre
      supposé ; agricole ⇒ ``None``.
    """
    if devis is None:
        return None
    from . import solar_classification as classification
    from .domain import lignes as _lignes
    from .domain.scenario import (
        SCENARIO_LES_DEUX, SCENARIO_SANS_BATTERIE, recommended_option_effective)

    from .utils.options import familles_des_lignes, familles_servables

    etude = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    # UNE lecture des lignes (produit joint) : budget de requêtes des écrans ;
    # ``lignes`` déjà lues par l'appelant (``conception_retenue_du_devis_id``).
    if lignes is None:
        lignes = devis.lignes.select_related('produit').all()
    lignes = [li for li in lignes if getattr(li, 'type_ligne', 'produit') == 'produit']
    variantee = any((getattr(li, 'variante', '') or '') in ('sans', 'avec')
                    for li in lignes)
    # Même critère que ``option_avec_servable``, sur les lignes déjà lues.
    avec_servable = familles_servables(**familles_des_lignes(
        _lignes.lignes_de_variante(lignes, 'avec')))[1]
    deux_options = bool(avec_servable and (
        variantee or etude.get('scenario') == SCENARIO_LES_DEUX))
    if deux_options:
        reco = recommended_option_effective(devis, etude.get('recommended_option'))
        option = 'sans' if reco == SCENARIO_SANS_BATTERIE else 'avec'
    else:
        option = 'avec' if avec_servable else 'sans'
    lignes_option = _lignes.lignes_de_variante(lignes, option)
    panneaux = [li for li in lignes_option
                if _lignes._classe_ligne(li, _lignes._is_panel)]
    onduleurs = [li for li in lignes_option
                 if _lignes._classe_ligne(li, classification.is_inverter)]
    divergent = deux_options and (
        _compte_panneaux(lignes, 'sans', _lignes)
        != _compte_panneaux(lignes, 'avec', _lignes))
    production, origine = _production_retenue(devis, etude, option, divergent)
    return {
        'devis': devis.pk,
        'reference': devis.reference,
        'statut': devis.statut,
        'recu': devis.statut in STATUTS_DEVIS_RECU,
        'option': option,
        'deux_options': deux_options,
        'module': _module_retenu(panneaux, _lignes),
        'onduleurs': [{'produit': li.produit_id,
                       'designation': li.designation or getattr(li.produit, 'nom', '') or '',
                       'quantite': _quantite_entiere(li.quantite)}
                      for li in onduleurs],
        'chaines': (_chaines_rangees(devis)
                    if not deux_options or option == 'avec' else None),
        'production_annuelle_kwh': production,
        'production_origine': origine,
    }


def _quantite_entiere(valeur):
    """ACAL1950 — une quantité de ligne en entier (0 si illisible)."""
    from decimal import Decimal

    try:
        return int(Decimal(str(valeur or 0)))
    except (ArithmeticError, TypeError, ValueError):
        return 0


def _compte_panneaux(lignes, option, _lignes):
    """ACAL1950 — le nombre de panneaux de l'option ``option``."""
    return sum(_quantite_entiere(li.quantite)
               for li in _lignes.lignes_de_variante(lignes, option)
               if _lignes._classe_ligne(li, _lignes._is_panel))


def _module_retenu(panneaux, _lignes):
    """ACAL1950 — ``{produit, designation, quantite, watt}`` ou ``None``."""
    from decimal import Decimal

    from . import solar_classification as classification

    if not panneaux:
        return None
    dominante = max(panneaux, key=lambda li: Decimal(str(li.quantite or 0)))
    nom = dominante.designation or getattr(dominante.produit, 'nom', '') or ''
    # Le libellé d'abord (aucune requête), la fiche seulement s'il est muet.
    watt = (classification.parse_watt(dominante.designation or '')
            or classification.parse_watt(getattr(dominante.produit, 'nom', '') or '')
            or _lignes._pmax_wc_du_produit(dominante.produit))
    return {'produit': dominante.produit_id, 'designation': nom,
            'quantite': sum(_quantite_entiere(li.quantite) for li in panneaux),
            'watt': float(watt) if watt else None}


def _chaines_rangees(devis):
    """ACAL1950 — ``{nombre, longueurs, longueur}`` de la conception électrique
    rangée du devis, ou ``None`` (aucune chaîne lisible)."""
    design = getattr(devis, 'electrical_design', None)
    chaines = design.get('chaines') if isinstance(design, dict) else None
    longueurs = [_quantite_entiere(c.get('nb_modules'))
                 for c in (chaines if isinstance(chaines, list) else [])
                 if isinstance(c, dict)]
    longueurs = [n for n in longueurs if n > 0]
    if not longueurs:
        return None
    return {'nombre': len(longueurs), 'longueurs': longueurs,
            'longueur': max(longueurs)}


def _nombre_positif(valeur):
    """ACAL1950 — un nombre fini > 0, sinon ``None``."""
    import math

    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return nombre if math.isfinite(nombre) and nombre > 0 else None


def _production_retenue(devis, etude, option, divergent):
    """ACAL1950 — ``(kWh/an, origine)`` retenus par le devis, ``(None, None)``
    quand la clé manque. Aucun recalcul."""
    marche = (getattr(devis, 'mode_installation', '') or 'residentiel')
    if marche == 'agricole':
        return None, None
    if marche in ('commercial', 'industriel'):
        etude_ci = etude.get('etude_ci') if isinstance(etude.get('etude_ci'), dict) else {}
        bloc, origine = etude_ci, 'etude_ci'
        if option == 'avec' and isinstance(etude_ci.get('option_avec'), dict):
            bloc, origine = etude_ci['option_avec'], 'etude_ci.option_avec'
        bilan = bloc.get('bilan') if isinstance(bloc.get('bilan'), dict) else {}
        production = _nombre_positif(bilan.get('production_kwh'))
        return (production, origine) if production is not None else (None, None)
    cle = 'etude_horaire_sans' if (option == 'sans' and divergent
                                   and isinstance(etude.get('etude_horaire_sans'), dict)) else 'etude_horaire'
    horaire = etude.get(cle) if isinstance(etude.get(cle), dict) else {}
    annuel = horaire.get('annuel') if isinstance(horaire.get('annuel'), dict) else {}
    production = _nombre_positif(annuel.get('production_kwh'))
    if production is not None and (cle == 'etude_horaire_sans' or not divergent or option == 'avec'):
        return production, cle
    if not divergent:
        from .domain.scenario import figure_production_du_devis

        production = _nombre_positif(figure_production_du_devis(devis))
        if production is not None:
            return production, 'production_annuelle'
    return None, None


def peremption_layout_devis(devis, calepinage=None):
    """CAL189 — ``{layout_stale, layout_nb_panneaux}`` d'un devis.

    LE MÊME CALCUL QUE LA PAGE PUBLIQUE, pas un second. ``layout_stale``
    n'était publié que dans la charge utile de la proposition
    (``public_views.py`` ← ``quote_engine/builder.py``) : l'API interne ne
    l'exposait nulle part, donc l'écran ERP ne pouvait pas dire au commercial
    que sa 3D ne décrit plus ce que le devis vend. Le compte de modules du
    layout est lu par le MÊME lecteur que le moteur PDF (ACAL60 :
    ``geometrie.lire_layout`` — un champ au sol compte).

    ACAL46 (C-ACAL-112) — les comptes des LIGNES viennent de LA règle
    partagée ``domain.dimensionnement_devis.comptes_panneaux_valides`` (lignes
    comptées dans les totaux — jamais une ligne optionnelle —, classifieur
    désignation + nom du produit, deux options sans/avec) : le moteur PDF lit
    la même, le recompte local est SUPPRIMÉ.

    Un document à DEUX OPTIONS a DEUX comptes valides (LAYSTALE) : le
    calepinage n'est périmé que s'il ne correspond à AUCUNE des deux — sinon on
    afficherait au client un avertissement FAUX.

    ``layout_stale`` vaut ``False`` quand le devis ne porte AUCUNE ligne de
    panneau : il n'y a alors rien à comparer, et un « périmé » là-dessus serait
    une alerte inventée.

    ACAL46 — ``calepinage`` (optionnel, le calepinage lié déjà lu par
    l'appelant) : la réponse porte en plus ``conception_divergente`` (les deux
    empreintes diffèrent — :func:`_conception_a_jour`, le prédicat du badge
    ``a_jour``) et ``calepinage_nb_panneaux``. Sans calepinage fourni, ces
    deux clés valent ``None`` (inconnu) et AUCUNE requête n'est ajoutée.
    Clés INTERNES : jamais dans la charge publique.
    """
    from apps.ventes.domain.dimensionnement_devis import (
        comptes_panneaux_valides)
    from apps.ventes.quote_engine.builder import (
        _compte_du_layout as _panneaux_du_layout)

    if devis is None:
        return {'layout_stale': None, 'layout_nb_panneaux': None,
                'conception_divergente': None,
                'calepinage_nb_panneaux': None}
    layout_nb_panneaux = _panneaux_du_layout(
        getattr(devis, 'roof_layout', None))
    valides = comptes_panneaux_valides(devis)
    a_jour = _conception_a_jour(devis, calepinage)
    return {
        'layout_stale': bool(layout_nb_panneaux and valides
                             and layout_nb_panneaux not in valides),
        'layout_nb_panneaux': layout_nb_panneaux,
        'conception_divergente': (None if a_jour is None else not a_jour),
        'calepinage_nb_panneaux': (
            _panneaux_du_layout(getattr(calepinage, 'roof_layout', None))
            if calepinage is not None else None),
    }


#: ACON90 — le marché d'un devis / d'un lead, dit en clair.
_LIBELLES_MARCHE = {'residentiel': 'résidentiel', 'industriel': 'industriel',
                    'commercial': 'commercial', 'agricole': 'agricole'}


def refus_marche_du_brouillon(devis, lead):
    """ACON90 (D-ACON-1) — LE refus des portes de dédup (« Générer le
    devis », ``from-layout``) : le brouillon ``devis`` n'est pas au marché du
    ``lead`` (``type_installation``, résidentiel par défaut). Le message, ou
    ``None`` quand les marchés concordent (ou sans lead)."""
    from .models import Devis

    if devis is None or lead is None:
        return None
    marches = Devis.ModeInstallation
    attendu = (getattr(lead, 'type_installation', '') or '').lower()
    attendu = attendu if attendu in marches.values else marches.RESIDENTIEL
    actuel = devis.mode_installation or marches.RESIDENTIEL
    if actuel == attendu:
        return None
    return (f'Le devis {devis.reference} est au marché '
            f'{_LIBELLES_MARCHE.get(actuel, actuel)}, le lead est '
            f'{_LIBELLES_MARCHE.get(attendu, attendu)} : archivez ce brouillon '
            '(ou corrigez son marché) puis générez à nouveau.')


def refus_kwh_declare_du_devis(devis):
    """ADVS26 — la garde kWh déclaré / factures, lue par le module calepinage (une
    seule règle : ``etude_horaire.controle_kwh_declare_du_devis``) : le corps
    ``{detail, code}`` du refus, ou ``None`` quand rien ne contredit."""
    from .etude_horaire import controle_kwh_declare_du_devis as controle
    from .horaire.conso import CODE_KWH_INCOHERENT, MESSAGE_KWH_INCOHERENT
    resultat = controle(devis)
    if resultat is None or resultat['coherent']:
        return None
    return {'detail': MESSAGE_KWH_INCOHERENT, 'code': CODE_KWH_INCOHERENT}


def compatibilite_du_materiel(panneau_id, onduleur_id, company, batterie_id=None):
    """ACAL901 — la compatibilité du matériel DÉSIGNÉ au calepinage, RELAYÉE
    telle quelle de ``compatibilites.verdict_panneau_onduleur`` /
    ``verdict_batterie_onduleur`` (aucun recalcul, aucune correspondance).

    Produits lus bornés société (``get_produit_scoped``) : un id inconnu ou
    d'une autre société ⇒ ``inconnu`` nommé. Rend ``{panneau_onduleur:
    {statut, raisons}, batterie_onduleur: {statut, raisons} | None}`` ; aucun
    verdict optimiseur n'existe dans ventes, il n'est pas servi."""
    from apps.stock.selectors import get_produit_scoped

    from .compatibilites import (
        STATUT_INCONNU, verdict_batterie_onduleur, verdict_panneau_onduleur)

    def produit(identifiant):
        if identifiant in (None, '') or company is None:
            return None
        return get_produit_scoped(company, identifiant)

    def introuvable(*paires):
        manquants = [nom for nom, objet in paires if objet is None]
        return {'statut': STATUT_INCONNU, 'raisons': [
            '%s introuvable dans le catalogue de la société' % nom
            for nom in manquants]}

    def relayer(verdict):
        return {'statut': verdict.get('statut'),
                'raisons': list(verdict.get('raisons') or [])}

    panneau, onduleur = produit(panneau_id), produit(onduleur_id)
    sortie = {'panneau_onduleur': (
        relayer(verdict_panneau_onduleur(panneau, onduleur))
        if panneau is not None and onduleur is not None
        else introuvable(('panneau', panneau), ('onduleur', onduleur))),
        'batterie_onduleur': None}
    if batterie_id not in (None, ''):
        batterie = produit(batterie_id)
        sortie['batterie_onduleur'] = (
            relayer(verdict_batterie_onduleur(batterie, onduleur))
            if batterie is not None and onduleur is not None
            else introuvable(('batterie', batterie), ('onduleur', onduleur)))
    return sortie


def production_annoncee_du_devis(devis_id, company):
    """ACAL1171 — ce que le PDF du devis imprimera comme production : celle de
    la pose réelle SERVIE par le calepinage, ou le standard de la ville.

    Relaye le résolveur du marché (``diagnostic_plan_pose_pompage`` pour
    l'agricole, ``diagnostic_base_de_production`` sinon) : rien n'est recalculé.
    Rend ``{regles_a_jour, servie, motif}`` — ``motif`` dit pourquoi la ville
    sert quand ``servie`` est faux — ou ``None`` (devis inconnu / d'une autre
    société). Lecture pure, ne lève pas."""
    from .domain.regles_calcul import REGLES_POSE_REELLE_2111, regles_au_moins
    from .models import Devis

    if company is None or not devis_id:
        return None
    devis = Devis.objects.filter(company=company, pk=devis_id).first()
    if devis is None:
        return None
    if devis.mode_installation == Devis.ModeInstallation.AGRICOLE:
        from .domain.pompage_pose import diagnostic_plan_pose_pompage as lire
    else:
        from .horaire.productible_pose import (
            diagnostic_base_de_production as lire)
    base, motif = lire(devis)
    return {'regles_a_jour': regles_au_moins(devis, REGLES_POSE_REELLE_2111),
            'servie': base is not None, 'motif': motif}


def pose_reelle_au_niveau(niveau):
    """Relecture du lot 4, m2 — vrai quand un résultat rangé au niveau de règles ``niveau``
    (``ConceptionLead.niveau_regles``) suit les règles de la pose réelle (niveau 15,
    ``REGLES_POSE_REELLE_2111``) ; ``None`` suit les règles courantes. Lecture pure."""
    from types import SimpleNamespace

    from .domain.regles_calcul import REGLES_POSE_REELLE_2111, regles_au_moins

    return regles_au_moins(None if niveau is None else SimpleNamespace(regles_calcul=niveau),
                           REGLES_POSE_REELLE_2111)


def liaison_dc_tracee_ouverte(jour=None):
    """Liaison DC tracée (suite ACAL1317) — un calcul du calepinage fait le ``jour``
    (aujourd'hui, fuseau du projet, par défaut) prend-il le tracé DC du plan ? Voir
    ``domain.regles_calcul.COUPURE_LIAISON_DC_TRACEE``. Lecture pure."""
    from django.utils import timezone

    from .domain.regles_calcul import liaison_dc_tracee_ouverte as ouverte

    return ouverte(jour if jour is not None else timezone.localdate())


def production_imprimee_du_devis(devis):
    """R2-14 (D-ACAL-6) — LA production annuelle (kWh, ``Decimal``) que le PDF
    ``/proposal`` imprime pour ce devis (instance) : le MÊME rendu que
    ``chiffrage_conception._depuis_devis`` (``build_quote_data(devis,
    {'pdf_mode': 'full'})``), lu par ``quote_engine.figures.
    production_imprimee``. ``None`` sans devis, sans production imprimée
    (pompage, options divergentes, production nulle) ou rendu en échec.

    UN APPEL = UN RENDU, qui n'est pas une lecture pure (le rendu crée le
    profil société absent, ACON87) : réservé à un DOCUMENT généré à la demande
    (présentation compacte). Jamais dans ``resultat_calepinage`` : le rendu du
    devis relit ce résultat (ombrage servi, D-RES-2710-1) — boucle — et le
    profil créé périmerait la simulation lue juste avant."""
    from .quote_engine.builder import build_quote_data
    from .quote_engine.figures import production_imprimee

    if devis is None:
        return None
    try:
        return production_imprimee(build_quote_data(devis, {'pdf_mode': 'full'}))
    except Exception:  # noqa: BLE001 — document jamais bloqué par le rendu (D-ENF22-BLE001)
        logger.warning('production imprimée indisponible', exc_info=True)
        return None


def devis_brouillon_pour_layout(company, lead_id, empreinte):
    """CAL24 — le BROUILLON déjà né de ce calepinage, ou ``None``.

    C'est la dédup de QJ17 (``lead`` + ``layout_hash``), rendue lisible aux
    autres apps : re-cliquer « Générer le devis » doit redonner le brouillon
    EXISTANT, jamais un doublon. Elle vivait inline dans la vue ``from-layout``
    de ventes ; tout autre créateur (le module Calepinage) l'aurait recopiée,
    donc fait dériver.

    Scopée société, et seulement les BROUILLONS : un devis déjà envoyé ne se
    « réutilise » pas — il se révise.

    ACAL88 (C-ACAL-104) — et seulement les brouillons ACTIFS : un brouillon
    archivé (``is_active=False``, QJR661) n'est plus jamais rendu.
    """
    from .models import Devis

    if company is None or not lead_id or not empreinte:
        return None
    return (Devis.objects
            .filter(company=company, lead_id=lead_id, is_active=True,
                    statut=Devis.Statut.BROUILLON, layout_hash=empreinte)
            .order_by('-date_creation')
            .first())


# ── AOF164 — comparaison A/B du calepinage d'un devis (LECTURE SEULE) ───────
#
# C'est le SEUL endroit qui confronte le compte d'un devis EXISTANT au compte
# du moteur. Il ne récrit rien : ni les lignes, ni ``etude_params``, ni
# ``layout_hash``. **Un devis déjà émis ne doit jamais voir son compte bouger
# rétroactivement** — un client qui a reçu « 24 panneaux » a reçu 24 panneaux,
# quelle que soit l'opinion ultérieure du moteur. La fonction refuse donc
# explicitement tout devis hors ``brouillon``, avec un motif en français.

#: Le seul statut dont le compte est encore malléable.
STATUT_RECALCULABLE = 'brouillon'


def comparaison_calepinage_devis(devis):
    """Compare le compte STOCKÉ du devis au compte du moteur — sans rien écrire.

    Rend un dict ``{'recalculable', 'motif', 'compte_stocke', 'compte_moteur',
    'ecart'}``. ``recalculable`` est ``False`` dès que le devis a quitté le
    brouillon : la comparaison reste LISIBLE (elle informe l'arbitrage), mais
    aucun appelant n'a le droit de l'appliquer.
    """
    from .services import _is_panel, compte_moteur_du_layout

    if devis is None:
        return None
    statut = getattr(devis, 'statut', '')
    stocke = 0
    for ligne in devis.lignes.all():
        if _is_panel(ligne.designation):
            stocke += int(ligne.quantite or 0)

    if statut != STATUT_RECALCULABLE:
        return {
            'recalculable': False,
            'motif': ("Devis %s au statut « %s » : un devis déjà émis n'est "
                      'jamais recalculé.'
                      % (devis.reference, devis.get_statut_display())),
            'compte_stocke': stocke,
            'compte_moteur': None,
            'ecart': None,
        }

    # PV42 — le moteur calepine sur le PANNEAU du devis (kit-produit, PV12) :
    # sans lui, cette comparaison opposerait un compte posé sur le module vendu
    # à un compte posé sur le kit générique — un écart inventé de toutes pièces.
    mesure = compte_moteur_du_layout(
        devis.roof_layout, company=getattr(devis, 'company', None),
        devis=devis)
    if mesure is None:
        return {
            'recalculable': True,
            'motif': ('Aucune géométrie exploitable : le moteur ne se '
                      'prononce pas sur ce devis.'),
            'compte_stocke': stocke,
            'compte_moteur': None,
            'ecart': None,
        }
    return {
        'recalculable': True,
        'motif': '',
        'compte_stocke': stocke,
        'compte_moteur': int(mesure['modules']),
        'ecart': int(mesure['modules']) - stocke,
    }


# ── PV17 — contexte COMPLET de l'écran de conception 3D d'un devis ──────────
#
# UN SEUL appel, UN SEUL dict, TOUTES les clés TOUJOURS présentes (contrat
# ``apps/ventes/contract_samples/devis_design_context.json``). L'écran ne doit
# jamais avoir à deviner : une clé absente, c'est un ``.map()`` sur
# ``undefined`` en production — l'incident exact que ``check_api_shapes.py``
# garde. Un panier vide vaut ``[]``, une valeur inconnue vaut ``None`` ou
# ``''``, jamais une clé manquante.
#
# LECTURE PURE : aucun statut, aucune ligne, aucun layout n'est écrit ici.


def config_carte():
    """ACAL282 — LA lecture UNIQUE des clés carte du builder 3D.

    ``PUBLIC_MAPTILER_KEY`` / ``PUBLIC_MAPBOX_TOKEN`` (déclarées dans
    ``.env.example``), forme ``{available, maptilerKey, mapboxToken}`` : servie
    telle quelle par ``GET /ventes/roof-config/``, par le contexte de conception
    devis et par le design-context calepinage (import fonction-local) — trois
    portes, une réponse. Aucune donnée société, aucune écriture.
    """
    import os

    maptiler = os.environ.get('PUBLIC_MAPTILER_KEY', '') or ''
    mapbox = os.environ.get('PUBLIC_MAPBOX_TOKEN', '') or ''
    return {
        'available': bool(maptiler),
        'maptilerKey': maptiler,
        'mapboxToken': mapbox or None,
    }


#: CALX104/CALX403 — les sections de réglages société que l'atelier 3D lit
#: (option de boot ``reglagesAtelier``). Les NOMS sont ceux de
#: ``apps.calepinage.selectors.SECTIONS_PARAMETRES`` : l'atelier les consomme
#: sans traduction de clé, donc on ne les renomme pas au passage.
SECTIONS_ATELIER_3D = ('zones_types', 'degagements')


def _reglages_atelier(company):
    """CALX104/CALX403 — les deux sections de réglages que l'atelier 3D lit.

    ``zones_types`` porte les gabarits d'obstacle saisis par la société,
    ``degagements`` le retrait de rive et la largeur d'allée. L'écran de
    conception en mode DEVIS tient une garantie testée — « un seul appel :
    rien n'est complété par une requête annexe » — donc ces deux sections
    voyagent DANS le contexte agrégé plutôt que par une seconde porte.

    FRONTIÈRE INTER-APPS : la lecture passe par le selector de l'app
    propriétaire (``apps.calepinage.selectors``), jamais par ses modèles.

    ÉQUIVALENCE : une société qui n'a rien réglé reçoit ``{}`` pour chacune —
    donc aucun gabarit proposé, aucune largeur préremplie, l'atelier
    d'aujourd'hui exactement. Rien n'est inventé ici.
    """
    from apps.calepinage.selectors import parametres_de_societe

    reglages = parametres_de_societe(company) or {}
    return {section: (reglages.get(section) or {})
            for section in SECTIONS_ATELIER_3D}


def devis_concevables(qs):
    """QJR636 — les devis de ``qs`` dont la toiture se calepine encore.

    La règle de statut est LUE dans la table de ``domain/modifiabilite``
    (geste CALEPINAGE, devis actif) — jamais recopiée ici ; s'y ajoutent les
    deux exclusions propres à l'écran 3D : un devis agricole (pompage) et un
    devis multi-villa (une ligne ``groupe_index >= 1``). Ne borne pas la
    société : l'appelant passe un queryset déjà scopé. Présence ici ⇔
    ``contexte_conception_devis(...)['modifiable']``.
    """
    from django.db.models import Exists, OuterRef

    from .domain.modifiabilite import CALEPINAGE, GESTES
    from .models import Devis, LigneDevis
    return (qs.filter(is_active=True, statut__in=GESTES[CALEPINAGE])
            .exclude(mode_installation=Devis.ModeInstallation.AGRICOLE)
            .exclude(Exists(LigneDevis.objects.filter(
                devis=OuterRef('pk'), groupe_index__gte=1))))


def raison_lecture_seule_conception(devis):
    """ACAL373 — raison de lecture seule de la conception toiture (``''`` si
    modifiable) : UNE règle (``devis_concevables``, QJR636), les branches la
    NOMMENT. Lue par l'écran (``contexte_conception_devis``) ET par la porte
    d'écriture du calepinage (``verrou.verifier_ecriture_autorisee``)."""
    from .domain.modifiabilite import CALEPINAGE, verdict as _verdict
    from .models import Devis
    if devis_concevables(Devis.objects.filter(pk=devis.pk)).exists():
        return ''
    if not _verdict(devis, CALEPINAGE)['modifiable']:
        return ('Devis « %s » : le calepinage n\'est plus modifiable. Utilisez '
                '« Réviser » pour en créer une nouvelle version.'
                % devis.get_statut_display())
    if devis.mode_installation == Devis.ModeInstallation.AGRICOLE:
        return ('Devis agricole (pompage) — le calepinage de toiture ne '
                's\'applique pas.')
    return ('Devis multi-villa : chaque villa porte son propre '
            'calepinage — cet écran ne peut pas en modifier une seule.')


def contexte_conception_devis(devis, company):
    """PV17 — tout ce que l'écran de conception toiture doit savoir d'un devis.

    Rend ``None`` quand le devis appartient à une AUTRE société (l'appelant
    répond alors 404 — jamais d'oracle d'existence). Sinon un dict à la forme
    FIXE :

        {devis: {id, reference, statut, mode_installation, lead, client,
                 client_nom},
         geometrie: {source, roof_layout, pin, outline, contour_client},
         cible: {panneaux, kwc, panel_watt, scenario, batterie,
                 avertissements, bill_kwh},
         carte: {available, maptilerKey, mapboxToken},
         modifiable, raison_lecture_seule, avertissements}

    L-MAP (fondateur 26/08/2026 : « i want it visible on the map in the 3D
    layouter ») — ``geometrie.contour_client`` porte TOUJOURS le contour
    ORIGINAL dessiné par le client sur le tunnel public (``Lead.roof_outline``,
    tel quel, jamais recalculé), À PART de ``outline`` qui peut déjà être le
    contour COURANT du calepinage une fois le devis édité (``layout.get
    ('outline')``). Sans ce champ distinct, un devis déjà calepiné perdait
    toute trace de ce que le client avait réellement tracé. Liste vide (jamais
    ``None``) sans lead ou sans contour posé.

    CTX3D (25/08/2026) — ``cible`` décrit L'OPTION 1 (« sans batterie »), celle
    que l'écran dessine par défaut : son compte de panneaux ET son scénario
    viennent maintenant du MÊME sous-ensemble de lignes (avant, le scénario
    était lu sur tout le devis et pouvait annoncer « avec_batterie » au-dessus
    d'un compte de panneaux « sans »).

    UNE CLÉ SŒUR OPTIONNELLE, ``cible_avec`` (même forme que ``cible``, ses six
    clés PV16 — sans ``bill_kwh``, la consommation du client étant unique et
    déjà portée par ``cible``), décrit L'OPTION 2 d'un devis qui la sert
    réellement. Elle n'est présente QUE si les lignes peuvent livrer l'option
    « Avec batterie » — onduleur hybride ET batterie, le MÊME critère
    ``avec_ok`` que le moteur PDF, ``variantes_servables`` et
    ``dimensionnement_options`` (``services.option_avec_servable``) — et ABSENTE
    sinon : jamais une option que ce devis ne peut pas livrer. Un écran qui ne
    la lit pas est strictement inchangé (clé purement additive).

    ``geometrie.source`` vaut ``'devis'`` (le devis porte déjà un layout 3D),
    ``'lead'`` (repli sur l'épingle/le contour posés au diagnostic) ou
    ``'none'``. ``modifiable`` est faux — avec une raison FRANÇAISE dans
    ``raison_lecture_seule`` — pour un devis sorti du cycle d'édition
    (accepté/refusé/expiré), un devis agricole (pompage) et un devis
    multi-villa. ``raison_lecture_seule`` vaut ``''`` quand le devis est
    modifiable, jamais ``None``.
    """
    from .services import cible_depuis_lignes, option_avec_servable

    if devis is None:
        return None
    # Garde société DÉFENSIVE (le queryset de l'appelant borne déjà) : un
    # superutilisateur sans société passe outre, comme partout ailleurs.
    company_id = getattr(company, 'id', None)
    if company_id is not None and devis.company_id != company_id:
        return None

    lead = getattr(devis, 'lead', None)
    # O4 (revue adversariale 26/08/2026, défense en profondeur) — un
    # `devis.lead` ne devrait JAMAIS appartenir à une AUTRE société que le
    # devis lui-même (la garde ci-dessus ne borne que `devis.company_id`),
    # mais si cet invariant était un jour rompu (bug ailleurs, migration de
    # données), aucun champ du lead (contour, GPS, téléphone, adresse…) ne
    # doit fuiter par cet endpoint : on le traite comme absent, exactement
    # le repli déjà utilisé partout ci-dessous (`if lead else None`).
    if lead is not None and company_id is not None \
            and getattr(lead, 'company_id', None) != company_id:
        lead = None

    # L-MAP (fondateur 26/08/2026) — le contour ORIGINAL du client, capturé
    # UNE FOIS pour toutes ici, AVANT toute logique de layout : `outline`
    # ci-dessous peut déjà être le contour COURANT du calepinage (celui du
    # layout, potentiellement édité par le commercial) ; `contour_client` ne
    # bouge JAMAIS avec lui. La validation (>= 3 sommets exploitables) est
    # déjà l'affaire de `traceToit.js` côté écran (MÊME fonction que la fiche
    # lead, PR #568) — on ne la refait pas ici, on transmet tel quel.
    contour_lead_brut = getattr(lead, 'roof_outline', None) if lead else None
    contour_client = contour_lead_brut if isinstance(contour_lead_brut, list) else []

    # ── Cible : ce que le devis DIT aujourd'hui (PV16) + la conso du lead ──
    cible = cible_depuis_lignes(devis)
    bill_kwh = getattr(lead, 'bill_kwh', None) if lead is not None else None
    try:
        cible['bill_kwh'] = float(bill_kwh) if bill_kwh is not None else None
    except (TypeError, ValueError):
        cible['bill_kwh'] = None

    # CTX3D — L'OPTION 2, quand ce devis la sert VRAIMENT. Sur un devis « Les
    # deux » les deux options n'ont ni le même champ ni le même scénario : la
    # cible seule ne pouvait en décrire qu'une, et l'écran n'avait aucun moyen
    # de savoir que l'autre existait. Critère = celui du moteur PDF (onduleur
    # hybride ET batterie dans le panier « avec »), jamais une option inventée.
    cible_avec = (cible_depuis_lignes(devis, variante='avec')
                  if option_avec_servable(devis) else None)

    # ── Géométrie : le layout du devis PRIME sur le repère du lead ──
    # QJR598 — LE repère toit du lead (crm.selectors.repere_toit) : le GPS
    # corrigé prime sur l'épingle du tunnel, sinon l'épingle, sinon le GPS.
    # ACAL250 — le drapeau ``contour_utilisable`` est PUBLIÉ, jamais jeté :
    # un contour où le repère ne tombe pas reste le calque ``contour_client``
    # mais n'ensemence aucun pan (``outline`` = []).
    from apps.crm.selectors import REPERE_SOURCE_GPS, repere_toit
    pin_lead, source_lead, contour_utilisable = (
        repere_toit(lead) if lead is not None else (None, None, False))
    source_repere = ('gps' if source_lead == REPERE_SOURCE_GPS
                     else 'roof_point' if source_lead else None)
    contour_graine = contour_client if contour_utilisable else []
    layout = devis.roof_layout if isinstance(devis.roof_layout, dict) else None
    # ACON80 (D-ACON-2) — un devis porté par une VARIANTE dessine SON document.
    from apps.calepinage.selectors import conception_du_devis
    variante = (conception_du_devis(devis.pk, company) or {}).get('variante')
    if variante is not None and isinstance(variante.roof_layout, dict):
        layout = variante.roof_layout
    if layout:
        source = 'devis'
        roof_layout = layout
        pin_brut = layout.get('pin')
        contour = layout.get('outline')
        pin = pin_brut if isinstance(pin_brut, dict) else None
        outline = contour if isinstance(contour, list) else []
        # ── AUTO-PIPELINE (ordre fondateur 26/08/2026) — LE TRACÉ DU CLIENT
        # NE DOIT JAMAIS SE PERDRE DERRIÈRE UN LAYOUT SANS GÉOMÉTRIE ──────────
        # Un devis peut porter un `roof_layout` qui ne décrit AUCUNE géométrie :
        # c'est le cas de tout devis AUTOMATIQUE d'avant ce lot (le layout de
        # `build_devis_auto` ne portait que `result`/`panelWatt`/`scenario`).
        # `outline` valait alors `[]` et `zones` était absent : côté écran,
        # `hydrateFromDevis` ne trouvait ni zone ni contour, retombait sur
        # l'épingle seule, et le commercial devait RE-DESSINER le toit pour voir
        # un seul panneau — alors que le tracé du client était là, juste à côté,
        # dessiné en calque passif (`contour_client`). C'était LA cause du
        # « le calepinage ne se fait pas tout seul ».
        #
        # Repli STRICTEMENT non destructif : il ne s'applique que si le layout
        # ne dit RIEN de la géométrie (ni `outline` exploitable, ni `zones`) —
        # un devis déjà calepiné garde son dessin, intact, en toutes
        # circonstances. Le contour rendu reste celui du CLIENT (`contour_client`,
        # `Lead.roof_outline` tel quel), jamais une géométrie inventée.
        if not outline and not (layout.get('zones') or layout.get('areas')):
            outline = contour_graine
    else:
        roof_layout = None
        pin = pin_lead
        outline = contour_graine
        source = 'lead' if (pin or contour_client) else 'none'
    # Un layout sans épingle centre quand même la carte sur le repère du lead
    # (n'écrit rien nulle part ; jamais une valeur inventée).
    if pin is None and pin_lead is not None:
        pin = pin_lead
        if source == 'none':
            source = 'lead'

    # ── Modifiable ? UNE raison de lecture seule (ACAL373), partagée avec la
    # porte d'écriture du calepinage ──
    raison = raison_lecture_seule_conception(devis)

    avertissements = list(cible['avertissements'])
    if source == 'none':
        avertissements.append(
            'Aucune géométrie de toiture connue pour ce devis : commencez par '
            'situer le bâtiment sur la carte.')

    client = getattr(devis, 'client', None)
    # PV23bis (fondateur 20/08/2026 : « link this 3D layouter to the quote »)
    # — l'outil 3D doit connaître le CLIENT du devis, pas seulement son nom :
    # téléphone, ville et adresse alimentent le formulaire du builder
    # (`hydrateFromDevis` sait déjà les lire) et le centrage de la carte quand
    # aucune géométrie n'existe. Client d'abord, repli sur le lead (même
    # priorité whatsapp > téléphone que le mode lead de l'écran) ; vide quand
    # personne ne le sait — jamais une valeur inventée.
    telephone = (getattr(client, 'telephone', '') or '').strip() if client else ''
    adresse = (getattr(client, 'adresse', '') or '').strip() if client else ''
    ville = ''  # crm.Client ne porte pas de ville — elle vient du lead.
    if lead is not None:
        telephone = telephone or (getattr(lead, 'whatsapp', '') or '').strip() \
            or (getattr(lead, 'telephone', '') or '').strip()
        adresse = adresse or (getattr(lead, 'adresse', '') or '').strip()
        ville = (getattr(lead, 'ville', '') or '').strip()
    contexte = {
        'devis': {
            'id': devis.pk,
            'reference': devis.reference,
            'statut': devis.statut,
            'mode_installation': devis.mode_installation or '',
            'lead': devis.lead_id,
            'client': devis.client_id,
            'client_nom': (getattr(client, 'nom', '') or '') if client else '',
            'client_telephone': telephone,
            'client_ville': ville,
            'client_adresse': adresse,
        },
        'geometrie': {
            'source': source,
            'roof_layout': roof_layout,
            'pin': pin,
            'outline': outline,
            'contour_client': contour_client,
            'contour_utilisable': bool(contour_utilisable),
            'source_repere': source_repere,
        },
        'cible': cible,
        'carte': config_carte(),
        'modifiable': not raison,
        'raison_lecture_seule': raison,
        'avertissements': avertissements,
        # CALX104/CALX403 câblage — les DEUX sections de réglages société que
        # l'atelier 3D consomme (`reglagesAtelier`) : les gabarits d'obstacle
        # (`zones_types`) et la largeur d'allée / le retrait de rive
        # (`degagements`). Les modes lead et calepinage les lisent sur
        # ``GET /api/django/calepinage/parametres/`` ; le mode DEVIS, lui, tient
        # la garantie testée « un seul appel : rien n'est complété par une
        # requête annexe », donc elles voyagent ICI.
        #
        # Servies TELLES QUELLES, par le selector de l'app propriétaire (jamais
        # ses modèles — frontière cross-app). ÉQUIVALENCE : une société qui n'a
        # rien réglé reçoit ``{}`` pour chacune, donc aucun gabarit proposé et
        # aucune largeur préremplie : l'atelier d'aujourd'hui exactement.
        **_reglages_atelier(company),
    }
    # CTX3D — clé OPTIONNELLE : présente seulement quand l'option 2 est
    # réellement servable. Absente (et non ``None``) sinon : un écran qui teste
    # sa présence sait alors qu'il n'y a rien à proposer, sans avoir à
    # distinguer « pas d'option » de « option vide ».
    if cible_avec is not None:
        contexte['cible_avec'] = cible_avec
    return contexte


def logo_entete_html(uri, *, variante='clair', role='entete', alt='logo'):
    """ACHT112 — le logo société en en-tête d'un document hors devis (rapport
    énergie du chantier, actes du dossier contractuel) : MÊME module image que
    les devis (rognage, détourage, bloc et taille du rôle), par la porte
    cross-app de ventes — jamais un import du moteur de devis depuis une autre
    app (CAL195). ``variante`` : ``clair`` sur fond clair, ``sombre`` sur un
    en-tête bleu nuit (encre sombre passée en blanc, comme la couverture du
    devis) ; ``role`` : un emplacement de ``quote_engine.logo.CAPITALE_MM``.
    ``None`` si l'image n'est pas un raster lisible (SVG, corrompu) :
    l'appelant garde son repli."""
    from .quote_engine import logo
    b64 = logo.societe_b64(uri, variante=variante) if uri else None
    if not b64:
        return None
    return logo.img_html(logo.pour_role(b64, role), role, alt=alt)


def logos_societe_html(company, roles=('entete',), *, variante='clair',
                       alt='logo'):
    """« Un seul logo partout » (fondateur, 24/11/2026) — les balises du logo
    du DEVIS de la société ``company``, une par rôle demandé : ``{rôle:
    balise}``. Le logo est celui du profil (``CompanyProfile.logo_key``), lu
    UNE fois en data URI par le contexte des PDF, puis rendu par
    ``logo_entete_html`` (même module image que les devis). Porte cross-app
    des documents du calepinage, qui n'importent jamais le moteur (règle
    n° 4). Chaque balise vaut ``''`` sans société, sans logo ou sur toute
    erreur — journalisée, jamais levée : un logo ne fait jamais tomber une
    pièce."""
    vide = {role: '' for role in roles}
    if company is None:
        return vide
    try:
        from apps.parametres.models import CompanyProfile

        from .utils.pdf import _company_context

        # Lecture PURE : ``_company_context`` passe par ``CompanyProfile.get``
        # qui CRÉE le profil absent (défauts, dont le fuseau du site) — lire
        # un logo ne doit rien écrire ; sans profil, il n'y a pas de logo.
        if not CompanyProfile.objects.filter(company=company).exists():
            return vide
        uri = (_company_context(company) or {}).get('logo_uri')
        return {role: logo_entete_html(uri, variante=variante, role=role,
                                       alt=alt) or '' for role in roles}
    except Exception:  # un logo ne fait jamais tomber une pièce
        logger.warning("logos societe : échec ignoré, pièce sans logo",
                       exc_info=True)
        return vide


def poids_solaires_mensuels():
    """AMON29 / règle #4 — profil mensuel de production imprimé au devis
    (``MOROCCO_SOLAR_MONTHLY_WEIGHTS``, somme = 1), lu par le monitoring sans
    importer le moteur hors d'``apps.ventes``."""
    from .quote_engine.constants import MOROCCO_SOLAR_MONTHLY_WEIGHTS
    return MOROCCO_SOLAR_MONTHLY_WEIGHTS


def plafond_injection_loi_8221():
    """ACAL783 — le plafond légal d'injection de la loi 82-21 (art. 12) et la
    mention « aucune revente en basse tension », lus de la constante du moteur
    C&I : le calepinage n'en recopie aucune valeur."""
    from .quote_engine.constants_82_21 import (
        MENTION_BT, PLAFOND_INJECTION_PCT, PLAFOND_INJECTION_SOURCE,
    )
    return {'pct': PLAFOND_INJECTION_PCT, 'source': PLAFOND_INJECTION_SOURCE,
            'mention_bt': MENTION_BT}


def forme_horaire_du_lead(lead):
    """ACAL1967 — la forme horaire de consommation que le DEVIS prend pour ce
    lead : la silhouette 24 h (somme = 1) de sa présence en journée
    (``crm.Lead.occupation_jour``), PRÉSENCE par défaut (décision fondateur D4
    du 29/08/2026) — le même traducteur (``occupation_du_lead``) et la même
    silhouette que le moteur de devis, jamais une seconde règle.

    Rend ``{forme, occupation, libelle, suppose, reponse}`` : ``suppose`` vrai
    quand l'occupation est un défaut appliqué (le champ ``occupation_jour`` n'a
    pas de réponse), ``reponse`` la valeur brute du champ ; ``None`` si la
    silhouette n'est pas lisible. Lecture pure."""
    from . import courbes_journalieres as cj

    drapeau, source = cj.occupation_du_lead(lead)
    forme = cj.silhouette_occupation(drapeau)
    if forme is None:
        return None
    libelles = {cj.OCCUPATION_PRESENCE: 'présence en journée',
                cj.OCCUPATION_ABSENCE: 'absence en journée',
                cj.OCCUPATION_PARTIELLE: 'présence partielle en journée'}
    return {'forme': list(forme), 'occupation': drapeau,
            'libelle': libelles.get(drapeau, drapeau),
            'suppose': cj.profil_suppose(source),
            'reponse': str(getattr(lead, 'occupation_jour', '') or '')}


def devis_suit_les_designations(devis):
    """Relecture D-ACAL-148 round 4 — le devis est-il NÉ sous la règle des désignations (il porte le
    marqueur privé de sa création depuis un calepinage) ? Lecture seule, lue par l'aperçu du calepinage."""
    from .domain.creation_calepinage import suit_les_designations

    return suit_les_designations(devis)
