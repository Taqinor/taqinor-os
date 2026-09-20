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
)


def liste_calepinages(company, *, lead_id=None, client_id=None, statut=None,
                      depuis=None, q=None):
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

    Returns:
        Un ``QuerySet`` ordonné du plus récent au plus ancien.
    """
    from .models import Calepinage

    if company is None:
        return Calepinage.objects.none()
    return appliquer_filtres_liste(
        Calepinage.objects.filter(company=company),
        lead_id=lead_id, client_id=client_id, statut=statut, depuis=depuis,
        q=q)


def appliquer_filtres_liste(lignes, *, lead_id=None, client_id=None,
                            statut=None, depuis=None, q=None):
    """CAL16 — LES filtres de la liste, écrits UNE fois.

    Le viewset (``views/calepinages.py``) et ce sélecteur servent la même
    liste : sans cette fonction, ils auraient deux jeux de filtres qui
    divergeraient au premier ajout — et la leçon PV22 est qu'un filtre IGNORÉ
    (``?statut=`` servi à l'identique) fait ouvrir le mauvais objet. Un filtre
    absent ne filtre rien ; un filtre présent filtre RÉELLEMENT.

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
