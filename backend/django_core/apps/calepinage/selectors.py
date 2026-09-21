"""Sélecteurs (lectures) du module Calepinage.

FRONTIÈRE INTER-APPS (import-linter) — une AUTRE app qui a besoin de LIRE des
données de ce module passe par une fonction de CE fichier, jamais en important
``apps.calepinage.models`` / ``.views``. Symétriquement, les lectures dont ce
module a besoin chez crm / ventes / ao passent par LEURS ``selectors.py``.

Toutes les fonctions sont en LECTURE PURE et BORNÉES SOCIÉTÉ : la société est
toujours celle passée en argument, jamais lue d'un corps de requête.
"""
from __future__ import annotations

#: CAL45 — les sections de réglages, dans l'ordre du contrat publié
#: (``contract_samples/parametres_calepinage.json``). Source unique de la FORME
#: rendue : l'endpoint, l'écran et les tests lisent la même liste.
SECTIONS_PARAMETRES = (
    'imagerie',
    'degagements',
    'zones_types',
    'gabarits_disposition',
    'presets',
    'favoris_materiel',
    'gabarits_dossier',
    # CAL130 — norme électrique applicable + coefficients SAISIS. Section
    # vide = aucune norme choisie (règle D5 : rien n'est supposé au Maroc).
    'norme_electrique',
    # CAL163 — paramètres de lestage SAISIS avec leur source. Section vide =
    # aucun coefficient connu, donc aucune feuille calculée.
    'lestage',
    # CALX145 — réglages de simulation, clés déclarées une par une dans
    # ``services/parametres_cles.py``. Section vide = rien de saisi, donc
    # chaque étape qui en dépend est OMISE en nommant ce qui manque.
    'simulation',
    # CALX145 — seuils électriques de la société (polystring, déséquilibre,
    # DC/AC, nomenclature, cos φ). Section vide = aucun verdict rendu.
    'electrique_societe',
)

#: CAL246 — clés DÉRIVÉES publiées par ``GET /parametres/`` mais JAMAIS écrites :
#: elles ne sont pas des sections (aucune n'entre dans ``enregistrer_parametres``).
#: Le contrat les porte ; les gardes de cohérence les retirent avant de comparer.
#: CALX145/69 — ``registre`` rejoint ``kits`` : même mécanique, lecture seule.
SECTIONS_LECTURE_SEULE = ('kits', 'registre')


def liste_calepinages(company, *, lead_id=None, client_id=None, statut=None,
                      depuis=None, q=None, inclure_archives=False):
    """CAL10 — les calepinages de ``company``, filtrés, en lecture pure.

    Args:
        company: la société — TOUJOURS celle passée, jamais lue d'un corps de
            requête. ``None`` renvoie un queryset VIDE (un filtre absent ne
            doit jamais se muer en absence de filtre).
        lead_id / client_id: restreint à un lead ou à un client.
        statut: ``brouillon`` / ``valide`` / ``perime``.
        depuis: date/heure — ne rend que ce qui a été créé à partir d'elle.
        q: recherche libre sur le TITRE (rien d'autre : on n'énumère pas
            l'annuaire client depuis ce module).
        inclure_archives: CAL208 — ``False`` (défaut) exclut les calepinages
            ARCHIVÉS (corbeille, ``apps.trash``) de la liste — un calepinage
            archivé n'est jamais soft-supprimé, il sort juste de la vue par
            défaut. ``True`` les inclut (écran corbeille).

    Returns:
        Un ``QuerySet`` ordonné du plus récent au plus ancien.
    """
    from .models import Calepinage

    if company is None:
        return Calepinage.objects.none()
    return appliquer_filtres_liste(
        Calepinage.objects.filter(company=company),
        lead_id=lead_id, client_id=client_id, statut=statut, depuis=depuis,
        q=q, inclure_archives=inclure_archives)


def appliquer_filtres_liste(lignes, *, lead_id=None, client_id=None,
                            statut=None, depuis=None, q=None,
                            inclure_archives=False):
    """CAL16 — LES filtres de la liste, écrits UNE fois.

    Le viewset (``views/calepinages.py``) et ce sélecteur servent la même
    liste : sans cette fonction, ils auraient deux jeux de filtres qui
    divergeraient au premier ajout — et la leçon PV22 est qu'un filtre IGNORÉ
    (``?statut=`` servi à l'identique) fait ouvrir le mauvais objet. Un filtre
    absent ne filtre rien ; un filtre présent filtre RÉELLEMENT.

    CAL208 — ``inclure_archives=False`` (le défaut, y compris pour le
    viewset qui n'appelle PAS cet argument) exclut les calepinages archivés
    (corbeille, ``apps.trash.selectors.ids_dans_corbeille`` — jamais un
    import direct de ``ElementSupprime``, frontière inter-apps).

    L'ordre est celui du plus récent au plus ancien, dans les deux chemins.
    """
    if lead_id:
        lignes = lignes.filter(lead_id=lead_id)
    if client_id:
        lignes = lignes.filter(client_id=client_id)
    if statut:
        lignes = lignes.filter(statut=statut)
    if depuis:
        lignes = lignes.filter(created_at__gte=depuis)
    terme = (q or '').strip()
    if terme:
        lignes = lignes.filter(titre__icontains=terme)
    if not inclure_archives:
        from apps.trash.selectors import ids_dans_corbeille

        lignes = lignes.exclude(
            pk__in=list(ids_dans_corbeille('calepinage.calepinage')))
    return lignes.order_by('-created_at', '-id')


def calepinage_detail(pk, company):
    """CAL10 — UN calepinage borné société, ou ``None``.

    Un calepinage d'une autre société est INTROUVABLE (``None``), jamais
    « interdit » : l'appelant répond 404 et n'apprend rien de son existence.
    """
    from .models import Calepinage

    if company is None or not pk:
        return None
    return (Calepinage.objects
            .filter(pk=pk, company=company)
            .select_related('client', 'devis')
            .first())


def versions(calepinage):
    """CAL10 — l'historique d'un calepinage, du plus récent au plus ancien."""
    from .models import CalepinageVersion

    if calepinage is None or not getattr(calepinage, 'pk', None):
        return CalepinageVersion.objects.none()
    return (CalepinageVersion.objects
            .filter(calepinage=calepinage)
            .order_by('-created_at', '-id'))


def variantes(calepinage):
    """CAL10 — les variantes d'un calepinage, la RETENUE en tête."""
    from .models import CalepinageVariante

    if calepinage is None or not getattr(calepinage, 'pk', None):
        return CalepinageVariante.objects.none()
    return (CalepinageVariante.objects
            .filter(calepinage=calepinage)
            .order_by('-retenue', 'id'))


#: CAL21 — les postes de production du comparatif. TOUJOURS présents, à
#: ``None`` quand la variante n'a pas été simulée : une variante non simulée
#: n'est pas une variante à « zéro kWh ».
CLES_PRODUCTION = ('p50_kwh', 'p75_kwh', 'p90_kwh', 'performance_ratio',
                   'specific_yield_kwh_kwc', 'self_consumption_rate')


def comparer_variantes(calepinage):
    """CAL21 — le comparatif des variantes, à la forme du contrat CAL3.

    Forme : ``{calepinage, retenue_id, reference_modules, introuvables,
    lignes}`` (``contract_samples/variantes_comparer.json``).

    TROIS DISCIPLINES, tenues ici et pas dans l'écran :

    * une variante NON SIMULÉE le DIT (``simulee: false``) et TOUTES ses
      grandeurs de production valent ``None`` — jamais ``0``, qui se lirait
      « zéro kWh » là où personne n'a lancé de simulation ;
    * l'écart est TOUJOURS relatif à la RETENUE : elle porte donc ``0`` (un
      écart MESURÉ, nul par construction), et sans point de comparaison (une
      seule variante, ou aucune retenue) les écarts valent ``None`` — il n'y a
      rien à quoi se comparer, ce n'est pas un écart nul ;
    * aucune grandeur n'est recalculée ici : tout est LU dans le ``resultat``
      déposé par le moteur. Ce comparatif compare, il ne calcule pas.
    """
    lignes = list(variantes(calepinage))
    retenue = next((v for v in lignes if v.retenue), None)
    reference = _mesures_variante(retenue) if retenue is not None else {}
    # CAL145 — la RÉFÉRENCE de production est calculée par le même chemin de
    # lecture que les autres lignes : une retenue périmée ne sert donc pas de
    # référence, et l'écart des autres vaut ``None`` plutôt qu'un écart
    # mesuré contre un chiffre qui ne décrit plus ce toit.
    reference_p50 = None
    if retenue is not None:
        simulee_ref, production_ref, _ = _production_comparee(retenue)
        if simulee_ref:
            reference_p50 = production_ref.get('p50_kwh')
    return {
        'calepinage': getattr(calepinage, 'pk', None),
        'retenue_id': retenue.pk if retenue is not None else None,
        'reference_modules': reference.get('total_modules'),
        'introuvables': [],
        'lignes': [_ligne_comparaison(v, reference, len(lignes),
                                      reference_p50=reference_p50)
                   for v in lignes],
    }


def _mesures_variante(variante):
    """Les grandeurs LUES dans le ``resultat`` du moteur, jamais recalculées."""
    resultat = getattr(variante, 'resultat', None)
    return resultat if isinstance(resultat, dict) else {}


def _production_comparee(variante):
    """CAL145 — les colonnes de production, CALCULÉES À LA LECTURE.

    Le service de comparaison lit le résultat déposé par le moteur (forme
    imbriquée du module ou forme plate du parcours devis) et déclare « non
    simulée » toute variante sans production — ou dont la production a été
    calculée sur une AUTRE empreinte de layout que celle d'aujourd'hui. Rien
    n'est stocké : le comparatif suit l'empreinte sans invalidation.
    """
    from .services.comparaison import colonnes_production

    return colonnes_production(_mesures_variante(variante),
                               layout_hash=getattr(variante, 'layout_hash',
                                                   '') or None)


def _ligne_comparaison(variante, reference, nombre_de_lignes,
                       reference_p50=None):
    mesures = _mesures_variante(variante)
    simulee, production, _motif = _production_comparee(variante)
    comparable = nombre_de_lignes > 1 and bool(reference)
    return {
        'id': variante.pk,
        'nom': variante.nom,
        'role': mesures.get('role') or '',
        'statut': mesures.get('statut') or '',
        'est_retenue': bool(variante.retenue),
        'simulee': simulee,
        'total_modules': mesures.get('total_modules'),
        'kwc': mesures.get('kwc'),
        'total_optimal': mesures.get('total_optimal'),
        'optimal': mesures.get('optimal'),
        'methode': mesures.get('methode'),
        'orientation': mesures.get('orientation'),
        'marge_troncon_min': mesures.get('marge_troncon_min'),
        'marge_bande_min': mesures.get('marge_bande_min'),
        'marges': mesures.get('marges'),
        'production': dict(
            {cle: (production.get(cle) if simulee else None)
             for cle in CLES_PRODUCTION},
            # TOUJOURS une liste, jamais ``None`` — simulée comme non
            # simulée : « aucun poste de perte dominant » se lit, « pas
            # de liste » ne se lit pas. C'est la forme publiée par le
            # contrat ``variantes_comparer.json`` (ligne « non simulée »
            # : toutes les grandeurs à ``null`` ET
            # ``pertes_dominantes: []``).
            pertes_dominantes=list(
                production.get('pertes_dominantes') or [])),
        'ecart_modules': _ecart(mesures.get('total_modules'),
                                reference.get('total_modules'), comparable),
        'ecart_kwc': _ecart(mesures.get('kwc'), reference.get('kwc'),
                            comparable),
        'ecart_p50_kwh': _ecart(
            production.get('p50_kwh') if simulee else None,
            reference_p50, comparable),
        'version_moteur': mesures.get('version_moteur') or '',
        'entree_hash': mesures.get('entree_hash') or '',
    }


def _ecart(valeur, reference, comparable):
    """L'écart MESURÉ, ou ``None`` quand il n'y a rien à quoi se comparer."""
    if not comparable or valeur is None or reference is None:
        return None
    try:
        if isinstance(valeur, int) and isinstance(reference, int) \
                and not isinstance(valeur, bool):
            return valeur - reference
        return round(float(valeur) - float(reference), 3)
    except (TypeError, ValueError):
        return None


def calepinage_du_devis(devis_id, company):
    """CAL10 — le calepinage rattaché à ce devis, ou ``None``.

    Point d'entrée cross-app : ``ventes`` sait si un devis a une conception
    sans jamais importer ``apps.calepinage.models``.
    """
    from .models import Calepinage

    if company is None or not devis_id:
        return None
    return (Calepinage.objects
            .filter(company=company, devis_id=devis_id)
            .order_by('-created_at', '-id')
            .first())


def calepinage_retenu_pour_devis(devis_id, company):
    """CAL209 — le calepinage RETENU d'un devis : id, kWc, nb modules, lien.

    Point d'entrée cross-app pour le chantier (``apps.installations``), qui ne
    porte AUCUN champ calepinage — règle fondateur 12/09/2026 « le module
    chantier ne garde QUE son cœur » : il se BRANCHE sur ce sélecteur, il
    n'absorbe pas la donnée. Renvoie ``None`` quand le devis est absent, quand
    aucun calepinage ne lui est rattaché, ou quand aucune variante n'y est
    RETENUE (``CalepinageVariante.retenue``) — un calepinage sans option
    choisie ne désigne rien de concret à renvoyer.

    Le kWc et le nombre de modules sont lus, dans l'ordre : le résultat du
    moteur (``variante.resultat['pose']`` — chaîné/simulé, CAL126+) puis, à
    défaut, le résumé posé par l'atelier 3D (``variante.roof_layout['result']``
    — présent dès qu'une pose a été dessinée, avant toute simulation). Aucune
    valeur n'est recalculée ici : c'est une LECTURE pure, bornée société.
    """
    from .models import CalepinageVariante

    calepinage = calepinage_du_devis(devis_id, company)
    if calepinage is None:
        return None
    variante = (CalepinageVariante.objects
                .filter(calepinage=calepinage, retenue=True)
                .first())
    if variante is None:
        return None

    kwc = None
    nb_modules = None
    resultat = variante.resultat if isinstance(variante.resultat, dict) else None
    pose = resultat.get('pose') if resultat else None
    if isinstance(pose, dict):
        kwc = pose.get('kwc')
        nb_modules = pose.get('total_modules')
    if kwc is None and nb_modules is None:
        roof_layout = (variante.roof_layout
                       if isinstance(variante.roof_layout, dict) else None)
        result = roof_layout.get('result') if roof_layout else None
        if isinstance(result, dict):
            kwc = result.get('kwc')
            nb_modules = result.get('panels')

    return {
        'id': calepinage.id,
        'kwc': kwc,
        'nb_modules': nb_modules,
        'planche_url': f'/calepinage/{calepinage.id}',
    }


#: CAL185 — les clés de la nomenclature d'une variante retenue. TOUJOURS
#: toutes présentes : un appelant n'a jamais à deviner si une clé existe.
CLES_NOMENCLATURE_RETENUE = ('calepinage', 'variante', 'nom', 'layout',
                             'layout_hash')


def nomenclature_variante_retenue(calepinage_id, company):
    """CAL185 — la conception de la variante RETENUE, prête à être CHIFFRÉE.

    Point d'entrée cross-app : ``apps.ventes`` chiffre la variante choisie
    sans jamais importer ``apps.calepinage.models``. Ce que rend cette
    fonction est la CONCEPTION (le document ``roof_layout`` de la variante) et
    son empreinte — pas une liste de produits : le schéma v2 ne porte aucune
    référence catalogue (cf. ``services.equipements``), et c'est la
    composition ventes qui résout les produits. Une deuxième façon de choisir
    un produit serait une deuxième vérité de chiffrage.

    ``None`` quand le calepinage n'existe pas dans cette société, quand
    AUCUNE variante n'y est retenue, ou quand la variante retenue ne porte
    pas de conception — une variante sans dessin n'a rien à chiffrer, et on
    ne retombe JAMAIS en silence sur la conception du calepinage parent (ce
    serait chiffrer autre chose que ce que le commercial a retenu).
    """
    from .models import Calepinage, CalepinageVariante

    if company is None or not calepinage_id:
        return None
    calepinage = (Calepinage.objects
                  .filter(company=company, pk=calepinage_id)
                  .first())
    if calepinage is None:
        return None
    variante = (CalepinageVariante.objects
                .filter(calepinage=calepinage, retenue=True)
                .first())
    if variante is None:
        return None
    layout = variante.roof_layout
    if not isinstance(layout, dict) or not layout:
        return None
    return {
        'calepinage': calepinage.pk,
        'variante': variante.pk,
        'nom': variante.nom or '',
        'layout': layout,
        'layout_hash': variante.layout_hash or '',
    }


def calepinage_de_l_affaire(appel_offre_id, company):
    """CAL10 — le calepinage rattaché à cette affaire d'AO, ou ``None``."""
    from .models import Calepinage

    if company is None or not appel_offre_id:
        return None
    return (Calepinage.objects
            .filter(company=company, appel_offre_id=appel_offre_id)
            .order_by('-created_at', '-id')
            .first())


#: CAL15 — les clés du contexte géographique. TOUJOURS toutes présentes.
CLES_CONTEXTE_GEO = ('pin', 'outline', 'adresse', 'ville', 'source')

#: Les provenances possibles de l'épingle — aucune autre n'est inventée.
SOURCE_ROOF_POINT = 'lead_roof_point'   # le client a POINTÉ son bâtiment
SOURCE_GPS_LEAD = 'lead_gps'            # coordonnées GPS saisies sur le lead


def contexte_geographique(calepinage):
    """CAL15 — de quoi PRÉ-REMPLIR la carte : pin, contour, adresse, ville.

    Les cinq clés sont TOUJOURS présentes, à ``None`` quand la donnée est
    inconnue. C'est la moitié importante : un écran ne doit jamais avoir à
    deviner si une clé manque parce qu'elle est vide ou parce que le serveur
    l'a omise.

    **JAMAIS une coordonnée devinée.** Sans aucune source, ``pin`` vaut
    ``None`` et ``source`` vaut ``None`` — pas un centre du Maroc inventé.
    Un chiffre montré doit être réel ou absent ; il n'y a pas de troisième
    possibilité.

    L'ordre de repli reprend celui de l'atelier existant : l'épingle POSÉE par
    le client (``Lead.roof_point``) prime sur les coordonnées GPS saisies sur
    le lead. Le client (fiche structurée) n'apporte qu'une adresse — il ne
    porte aucune géométrie.

    Les lectures crm passent par ``apps.crm.selectors`` uniquement (jamais un
    import de ``apps.crm.models``), et tout est borné à la société du
    calepinage.
    """
    from apps.crm.selectors import get_company_client, get_company_lead

    vide = {cle: None for cle in CLES_CONTEXTE_GEO}
    if calepinage is None:
        return vide
    company = getattr(calepinage, 'company', None)
    if company is None:
        return vide

    contexte = dict(vide)

    lead = get_company_lead(company, getattr(calepinage, 'lead_id', None))
    if lead is not None:
        contexte['adresse'] = _texte(getattr(lead, 'adresse', None))
        contexte['ville'] = _texte(getattr(lead, 'ville', None))
        contexte['outline'] = _contour(getattr(lead, 'roof_outline', None))
        pin = _pin_depuis_point(getattr(lead, 'roof_point', None))
        if pin is not None:
            contexte['pin'] = pin
            contexte['source'] = SOURCE_ROOF_POINT
        else:
            pin = _pin_depuis_gps(getattr(lead, 'gps_lat', None),
                                  getattr(lead, 'gps_lng', None))
            if pin is not None:
                contexte['pin'] = pin
                contexte['source'] = SOURCE_GPS_LEAD

    if contexte['adresse'] is None:
        client = get_company_client(
            company, getattr(calepinage, 'client_id', None))
        if client is not None:
            contexte['adresse'] = _texte(getattr(client, 'adresse', None))

    return contexte


def _texte(valeur):
    """Une chaîne non vide, ou ``None`` — jamais une chaîne vide trompeuse."""
    texte = (valeur or '').strip() if isinstance(valeur, str) else ''
    return texte or None


def _nombre(valeur):
    """``float`` lisible, ou ``None`` si la valeur n'en est pas un."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _pin_depuis_point(point):
    """``{'lat', 'lng'}`` depuis ``Lead.roof_point``, ou ``None``."""
    if not isinstance(point, dict):
        return None
    lat = _nombre(point.get('lat'))
    lng = _nombre(point.get('lng'))
    if lat is None or lng is None:
        return None
    return {'lat': lat, 'lng': lng}


def _pin_depuis_gps(lat, lng):
    """``{'lat', 'lng'}`` depuis les coordonnées du lead, ou ``None``."""
    lat, lng = _nombre(lat), _nombre(lng)
    if lat is None or lng is None:
        return None
    return {'lat': lat, 'lng': lng}


def _contour(outline):
    """Le contour TEL QUEL (liste de points), ou ``None``.

    Aucune reprojection, aucun lissage : ce que le client a dessiné est ce
    que l'atelier doit afficher.
    """
    if isinstance(outline, list) and outline:
        return outline
    return None


def parametres_de_societe(company):
    """CAL45 — les réglages calepinage de ``company``, TOUJOURS complets.

    ÉQUIVALENCE GARANTIE : une société qui n'a JAMAIS réglé quoi que ce soit
    reçoit les sept sections à ``{}`` — c'est-à-dire « comportement
    d'aujourd'hui, strictement inchangé ». Les clés sont toutes présentes dans
    les deux cas : un appelant n'a jamais à deviner si une section manque
    parce qu'elle est vide ou parce que le serveur l'a omise.

    Lecture PURE : aucun enregistrement n'est créé ici (un GET qui écrit en
    base est un GET qui ment).
    """
    from .models import ParametresCalepinage

    vide = {section: {} for section in SECTIONS_PARAMETRES}
    if company is None:
        return vide
    reglages = (ParametresCalepinage.objects
                .filter(company=company)
                .order_by('id')
                .first())
    if reglages is None:
        return vide
    return {
        section: (getattr(reglages, section, None) or {})
        for section in SECTIONS_PARAMETRES
    }


def imagerie_site(company):
    """CAL47 — la section « imagerie & pays » RÉSOLUE, toujours complète.

    ``parametres_de_societe`` rend la section BRUTE (``{}`` tant que la
    société n'a rien réglé) : c'est ce qui garantit l'équivalence stricte de
    CAL45 sur l'endpoint. Un CONSOMMATEUR, lui, a besoin des huit clés du
    contrat CAL46 (``contract_samples/site_imagerie.json``) pour ne jamais
    tester l'absence de clé au lieu de l'absence de donnée : cette fonction
    les lui donne, valeurs à ``null`` (ou ``[]``) quand rien n'est réglé.

    Huit valeurs nulles veulent dire « comportement d'aujourd'hui » — pas
    « pas de carte ». Aucun pays, aucun fournisseur, aucune altitude n'est
    inventé ici : ce que la société n'a pas saisi reste inconnu.

    Lecture PURE, bornée société (``company=None`` ⇒ tout inconnu).
    """
    from .services.site import section_vide

    section = section_vide()
    if company is None:
        return section
    section.update(parametres_de_societe(company).get('imagerie') or {})
    return section


def photos_site(calepinage):
    """CAL52 — les photos de site d'un calepinage, prêtes à l'affichage.

    Ordre : la plus récemment PRISE d'abord (jamais la plus récemment
    importée — c'est la date de prise de vue qui situe le toit). Lecture
    PURE ; un calepinage sans photo rend ``[]`` et jamais ``null``.
    """
    from .services.photos import photo_en_ligne

    if calepinage is None or calepinage.pk is None:
        return []
    lignes = (calepinage.photos_site
              .select_related('attachment', 'ajoutee_par')
              .order_by('-prise_le', '-id'))
    return [photo_en_ligne(photo) for photo in lignes]


def releves_terrain(calepinage):
    """CAL64 — les relevés terrain d'un calepinage, du plus récent au plus
    ancien (par date de RELEVÉ, jamais par date d'envoi : le terrain et le
    réseau ne coïncident pas).

    Lecture PURE ; un calepinage sans relevé rend ``[]`` et jamais ``null``.
    """
    from .services.releve import releve_en_ligne

    if calepinage is None or calepinage.pk is None:
        return []
    lignes = (calepinage.releves_terrain
              .select_related('releve_par')
              .prefetch_related('photos__attachment', 'photos__ajoutee_par')
              .order_by('-releve_le', '-id'))
    return [releve_en_ligne(releve) for releve in lignes]


def presets_de_societe(company):
    """CAL197 — les presets de conception disponibles pour l'atelier.

    ``module`` porte les jeux PROPRES au module, section ``presets.jeux`` de
    ``ParametresCalepinage`` (``services.presets.jeux_de_societe``).

    SOLMVP15 — il y avait une SECONDE source : les presets de portée société du
    module d'appels d'offres, lus tels quels à côté des jeux maison (jamais
    copiés dedans). Ce module-là sort du produit, sa table part avec lui : il
    n'en reste donc qu'une source, celle du module. Les jeux maison, eux, sont
    intacts — aucun preset de l'atelier n'a été perdu ni déplacé.

    Lecture PURE, bornée société — ``None`` rend une liste vide.
    """
    from .services.presets import jeux_de_societe

    return {'module': jeux_de_societe(company)}


def kits_de_pose_disponibles(company):
    """CAL198 — les kits de pose du catalogue, tels que le module les voit.

    Lecture PURE : point d'entrée unique pour l'atelier
    (``services.kits_catalogue.kits_de_societe``). SOLMVP15 — le catalogue
    vivait dans une table du module d'appels d'offres ; il vit désormais dans
    la section ``presets.kits`` des réglages société du module, à forme
    publiée IDENTIQUE (contrat ``contract_samples/
    parametres_calepinage.json``). Aucune donnée n'est recopiée nulle part."""
    from .services.kits_catalogue import kits_de_societe

    if company is None:
        return []
    return kits_de_societe(company)


def registre_des_reglages():
    """CALX145/69 — le registre LABEL/UNITÉ/RÉFÉRENCE des deux sections à
    registre (« simulation », « electrique_societe »), publié en LECTURE
    SEULE par ``GET /parametres/`` — même mécanique que ``kits`` (CAL246) :
    une clé DÉRIVÉE, jamais stockée, jamais acceptée en écriture (``PUT`` la
    refuse comme toute clé inconnue, ``ParametresCalepinage.SECTIONS`` ne la
    connaît pas).

    Chaque déclaration de ``services/parametres_cles.py::REGISTRES`` devient
    une ligne ``{cle, libelle, unite, reference}`` — LISTE, dans l'ordre du
    registre (celui-ci fige l'ordre d'ajout, jamais réordonné). Avant cette
    fonction, l'écran (``ReglagesSimulation.jsx``) redéclarait ces mêmes
    lignes à la main : une seconde source de vérité que
    ``scripts/check_api_shapes.py`` existe justement pour repérer.

    Lecture PURE : aucune valeur, aucun défaut, aucun accès base — la
    déclaration seule, sans dépendre de ``company``.
    """
    from .services.parametres_cles import REGISTRES

    return {
        section: [
            {'cle': cle, 'libelle': libelle, 'unite': unite,
             'reference': reference}
            for cle, libelle, unite, reference in declarations
        ]
        for section, declarations in REGISTRES.items()
    }


def favoris_materiel_de_societe(company):
    """CAL200 — le matériel « favori conception » de la société, résolu.

    La section ``favoris_materiel`` de ``ParametresCalepinage`` (CAL45) ne
    porte que des identifiants produit (``{'modules': [...], 'onduleurs':
    [...]}``) — ce sélecteur les résout sur le catalogue stock
    (``apps.stock.selectors``) pour rendre marque/puissance/dimensions,
    JAMAIS une fiche technique inventée. Un produit favori dont l'id est
    devenu introuvable est simplement OMIS (le favori pointe dans le vide) ;
    un produit trouvé mais SANS dimensions reste dans la liste, signalé
    ``dimensions_renseignees: False`` — jamais une taille par défaut.
    """
    from apps.stock.selectors import dimensions_de_pose, get_produit_scoped

    favoris = (parametres_de_societe(company).get('favoris_materiel') or {})
    resultat = {}
    for categorie, ids in favoris.items():
        if not isinstance(ids, list):
            continue
        lignes = []
        for produit_id in ids:
            produit = get_produit_scoped(company, produit_id)
            if produit is None:
                continue
            dims = dimensions_de_pose(produit)
            lignes.append({
                'id': produit.pk,
                'nom': produit.nom,
                'marque': getattr(produit, 'marque', '') or '',
                'puissance_wc': dims.get('puissance_wc'),
                'longueur_mm': dims.get('longueur_mm'),
                'largeur_mm': dims.get('largeur_mm'),
                'dimensions_renseignees': bool(
                    dims.get('longueur_mm') and dims.get('largeur_mm')),
                'archive': bool(getattr(produit, 'is_archived', False)),
            })
        resultat[categorie] = lignes
    return resultat


# ── SOLMVP15b — lecture cross-app du moteur VILLA, sans projet AO ──────────
#
# ``apps.ventes`` (villa / devis résidentiel) lisait ce moteur par le sélecteur
# du module AO ; AO sortant du produit, la porte est ICI. Le calcul reste sans
# effet de bord : aucune ligne n'est créée, aucune n'est lue (hors résolution
# du produit panneau, qui passe par ``apps.stock.selectors``).

def calepinage_villa(area, *, ordre='lnglat', kit=None, produit_panneau=None,
                     company=None, retrait_m=None, pas_recherche_m=0.01,
                     famille=None):
    """Calepine une toiture villa (``AreaRecord``) — LECTURE PURE.

    ``ordre`` reste un argument EXPLICITE jusqu'ici : aucun appelant ne doit
    pouvoir hériter d'un défaut deviné sur l'ordre lat/lng.

    ``produit_panneau`` (PV12) — identifiant OU instance de ``stock.Produit``,
    résolu DANS ``company`` : le calepinage est alors posé sur le panneau
    réellement vendu. Une fiche technique incomplète retombe sur le kit villa
    par défaut, jamais sur une géométrie devinée.

    ``famille`` (PV66) — ``SUD`` ou ``EST_OUEST`` : la forme de table, pas le
    panneau. Absente, le calcul est celui d'avant PV66, à l'identique.
    """
    from .villa_service import calepiner_villa

    return calepiner_villa(area, ordre=ordre, kit=kit,
                           produit_panneau=produit_panneau, company=company,
                           retrait_m=retrait_m,
                           pas_recherche_m=pas_recherche_m, famille=famille)
