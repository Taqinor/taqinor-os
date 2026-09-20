"""Le viewset PIVOT du module Calepinage — CAL16.

UNE SEULE FORME D'URL (CAL233) : tout l'objet métier est servi sous
``/api/django/calepinage/calepinages/<pk>/…``, les sous-ressources en
``@action`` du routeur DRF. Aucune seconde famille d'URL n'est ouverte ici.

CE QUI EST GARANTI PAR LE SOCLE, ET PAS RECODÉ
-----------------------------------------------
* ``core.viewsets.CompanyScopedModelViewSet`` (ARC2) : le queryset est filtré
  sur ``request.user.company`` et la société est POSÉE côté serveur — un
  ``company`` envoyé dans le corps n'existe pas pour le sérialiseur, donc il
  est ignoré, et un calepinage d'une autre société est INTROUVABLE (404),
  jamais « interdit » (un 403 confirmerait son existence) ;
* ``core.permissions.ScopedPermission`` + ``read_permission``/
  ``write_permission`` : lecture gardée par ``calepinage_voir``, écriture par
  ``calepinage_gerer`` (codes lus de ``apps/calepinage/permissions.py``, jamais
  écrits en littéral ici) ;
* chaque ``@action`` déclare EN PLUS sa propre garde (``PeutVoirCalepinage`` /
  ``PeutGererCalepinage``). ``get_permissions`` CUMULE les deux (patron
  ``apps/ao/viewsets.py``) : la garde déclarée par l'action est un plafond
  supplémentaire, jamais une substitution qui jetterait la garde du domaine.

LES FILTRES SONT RÉELLEMENT SERVIS (leçon PV22)
------------------------------------------------
``?lead=`` ``?client=`` ``?statut=`` ``?depuis=`` ``?q=`` passent par
``selectors.appliquer_filtres_liste`` — la MÊME fonction que le sélecteur
public. Un filtre ILLISIBLE (statut inconnu, date invalide) est REFUSÉ 400 en
nommant le champ, jamais avalé en silence : un filtre ignoré fait ouvrir le
mauvais objet (``LeadWorkspace.jsx`` l'a montré).
"""
from __future__ import annotations

from datetime import timedelta

from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DrfValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from core.permissions import ScopedPermission, declared_action_permissions
from core.viewsets import CompanyScopedModelViewSet

from .. import selectors
from ..models import Calepinage
from ..permissions import (
    CAL_GERER, CAL_VOIR, PeutGererCalepinage, PeutLireOuEcrireCalepinage,
)
from ..serializers import CalepinageSerializer
from ..services.layout import LayoutRefuse, enregistrer_layout

__all__ = ['CalepinageViewSet', 'detail_calepinage']

#: Durée de validité de l'URL présignée du rendu (celle du stockage ventes).
DUREE_URL_IMAGE = timedelta(hours=1)


class CalepinageViewSet(CompanyScopedModelViewSet):
    """CRUD du pivot ``Calepinage`` + ses sous-ressources en ``@action``."""

    queryset = Calepinage.objects.select_related('client', 'devis').all()
    serializer_class = CalepinageSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at', 'statut', 'titre']

    read_permission = CAL_VOIR
    write_permission = CAL_GERER

    def get_permissions(self):
        """``ScopedPermission`` TOUJOURS, + la garde déclarée par l'action.

        Cumul et jamais substitution : sans ``declared_action_permissions``,
        le ``permission_classes=`` d'une ``@action`` serait complètement
        inopérant (cf. ``core.permissions``).
        """
        permissions = [ScopedPermission()]
        declared = declared_action_permissions(self)
        if declared is not None:
            permissions.extend(declared)
        return permissions

    # ── Liste : des filtres qui filtrent VRAIMENT ──────────────────────────
    def get_queryset(self):
        params = getattr(self.request, 'query_params', {}) or {}
        return selectors.appliquer_filtres_liste(
            super().get_queryset(),
            lead_id=_entier(params.get('lead'), 'lead'),
            client_id=_entier(params.get('client'), 'client'),
            statut=_statut(params.get('statut')),
            depuis=_moment(params.get('depuis')),
            q=params.get('q'))

    def perform_create(self, serializer):
        """Société ET auteur posés côté serveur — jamais lus du corps."""
        serializer.save(company=self.request.user.company,
                        cree_par=self.request.user)

    # ── Détail : l'agrégat du contrat CAL1 ─────────────────────────────────
    def retrieve(self, request, *args, **kwargs):
        """CAL17 — TOUT ce que la fiche calepinage affiche, en UN appel.

        Sans agrégat, l'écran ouvrirait quatre requêtes et chaque lane
        inventerait sa forme (incident PACT10 du 03/08/2026). La forme est
        celle de ``contract_samples/calepinage_detail.json`` : toutes les clés
        TOUJOURS présentes, une grandeur non mesurée à ``null`` et jamais à
        ``0``. Lecture PURE (aucun statut, aucun layout n'est écrit) ; un
        calepinage d'une autre société est introuvable (404, get_queryset).
        """
        return Response(detail_calepinage(self.get_object(), request))

    # ── La conception elle-même ────────────────────────────────────────────
    @action(detail=True, methods=['get', 'post'], url_path='layout',
            permission_classes=[PeutLireOuEcrireCalepinage])
    def layout(self, request, pk=None):
        """CAL18 — lit (GET) ou enregistre (POST) la conception du calepinage.

        Patron exact de ``apps/ao/views.py::AppelOffreViewSet.layout`` : le
        corps POST EST le layout sérialisé, et les enveloppes
        ``{"layout": …}`` / ``{"roof_layout": …}`` sont acceptées telles
        quelles. SEULS ``roof_layout`` / ``layout_hash`` sont touchés — aucun
        statut n'est écrit (règle #4).

        L'écriture passe par ``services.enregistrer_layout`` (CAL13), jamais
        par une écriture directe de vue : c'est lui qui calcule l'empreinte
        (``apps.ventes.services.layout_hash``, jamais recodée) et qui dépose
        une VERSION quand — et seulement quand — la conception a changé. Un
        renvoi à l'identique répond donc ``{"inchange": true}`` sans créer de
        version. Un corps vide est refusé en français ; un calepinage d'une
        autre société est introuvable (404, ``get_queryset``).
        """
        calepinage = self.get_object()  # borné société par get_queryset
        if request.method.lower() == 'get':
            return Response({'roof_layout': calepinage.roof_layout,
                             'layout_hash': calepinage.layout_hash or None})

        payload = _corps_de_layout(request.data)
        if payload is None:
            return Response(
                {'roof_layout': "Conception manquante ou invalide : le corps "
                                "attendu est le document de conception."},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = enregistrer_layout(calepinage, payload,
                                          user=request.user)
        except LayoutRefuse as refus:
            return Response({refus.champ or 'roof_layout': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        version = resultat['version']
        return Response({
            'roof_layout': calepinage.roof_layout,
            'layout_hash': resultat['layout_hash'] or None,
            'inchange': resultat['inchange'],
            'version': version.pk if version is not None else None,
        })

    @action(detail=True, methods=['post'], url_path='roof-image',
            permission_classes=[PeutGererCalepinage],
            parser_classes=[MultiPartParser, FormParser])
    def roof_image(self, request, pk=None):
        """CAL19 — réceptionne le rendu (PNG/JPEG) et le range dans MinIO.

        AUCUN second chemin de stockage : la validation magic-bytes, le bucket
        et l'URL présignée 1 h sont ceux du chemin ventes, exposés par les
        fonctions minces ``apps.ventes.services.type_image_toiture`` /
        ``stocker_image_toiture`` / ``url_image_toiture`` (CAL19). Ce module
        n'importe ni une vue ni un modèle ventes.

        La clé est DÉRIVÉE côté serveur et porte la société
        (``roofs/<company_id>/calepinage-<pk>.<ext>``) : rien n'est lu du corps
        hors le fichier lui-même. Un fichier qui n'est pas une image est refusé
        avec le motif du SERVEUR. Aucun statut ne bouge (règle #4).
        """
        from apps.ventes import services as ventes_services

        fichier = request.FILES.get('image') or request.FILES.get('file')
        if fichier is None:
            return Response(
                {'image': "Fichier image manquant (champ « image »)."},
                status=status.HTTP_400_BAD_REQUEST)
        donnees = fichier.read()
        extension, mime = ventes_services.type_image_toiture(donnees)
        if extension is None:
            return Response({'image': 'Image invalide (PNG ou JPEG attendu).'},
                            status=status.HTTP_400_BAD_REQUEST)

        calepinage = self.get_object()  # borné société par get_queryset
        cle = (f'roofs/{calepinage.company_id or 0}/'
               f'calepinage-{calepinage.pk}.{extension}')
        ventes_services.stocker_image_toiture(donnees, cle,
                                              content_type=mime)
        calepinage.roof_image = cle
        calepinage.save(update_fields=['roof_image', 'updated_at'])
        return Response(
            {'roof_image': cle,
             'url': ventes_services.url_image_toiture(cle)},
            status=status.HTTP_201_CREATED)


def _corps_de_layout(donnees):
    """Le document de conception d'un corps de requête, ou ``None``.

    Accepte le layout NU et les deux enveloppes historiques (``layout`` /
    ``roof_layout``) — les mêmes que côté ventes et côté AO, pour qu'un même
    client puisse parler aux trois portes sans se reformater.
    """
    if isinstance(donnees, dict):
        for enveloppe in ('layout', 'roof_layout'):
            if set(donnees.keys()) == {enveloppe}:
                donnees = donnees[enveloppe]
                break
    if not isinstance(donnees, dict) or not donnees:
        return None
    return donnees


# ── CAL17 — L'AGRÉGAT DE DÉTAIL (la forme est le contrat) ──────────────────

def detail_calepinage(calepinage, request=None):
    """Le dictionnaire servi par ``GET /calepinages/<pk>/``.

    Écrit en DICTIONNAIRE LITTÉRAL, et pas monté clé par clé : c'est ce qui
    permet à ``scripts/check_api_shapes.py`` de lire la forme réellement
    renvoyée et de la confronter à l'échantillon committé. Une clé en trop ou
    en moins d'un côté rougit — l'écran ne peut plus diverger en silence.

    Les lectures cross-app passent par ``apps.crm.selectors`` /
    ``apps.ventes.selectors`` (jamais leurs modèles).
    """
    from .. import selectors as cal_selectors

    company = getattr(calepinage, 'company', None)
    layout = getattr(calepinage, 'roof_layout', None)
    return {
        'id': calepinage.pk,
        'reference': _reference(calepinage),
        'nom': _texte(getattr(calepinage, 'titre', '')) or str(calepinage),
        'statut': calepinage.statut,
        'statut_libelle': calepinage.get_statut_display(),
        'cree_le': _horodatage(getattr(calepinage, 'created_at', None)),
        'modifie_le': _horodatage(getattr(calepinage, 'updated_at', None)),
        'cree_par': _personne(getattr(calepinage, 'cree_par', None)),
        'responsable': _responsable(calepinage, company),
        'lead': _lead(calepinage, company),
        'client': _client(calepinage),
        'devis': _devis(calepinage, company),
        'layout_present': bool(layout),
        'layout_hash': _texte(getattr(calepinage, 'layout_hash', '')),
        'layout_schema_version': _schema_version(layout),
        'version_moteur': _texte(getattr(calepinage, 'version_moteur', '')),
        'versions': _compteur_versions(calepinage),
        'variantes': _compteur_variantes(calepinage),
        'image': _image(calepinage),
        'contexte_geographique': cal_selectors.contexte_geographique(
            calepinage),
        'permissions': _permissions(calepinage, request),
    }


def _reference(calepinage):
    """« CAL-AAMM-0001 » — DÉRIVÉE, jamais un numéro stocké.

    Le modèle ne porte pas de référence (aucune migration n'est ajoutée par
    cette lane) : l'étiquette est déduite de la date de création et de
    l'identifiant, donc elle est stable dans le temps et ne peut pas
    « rétrécir » comme un ``count()+1``. Le jour où une vraie numérotation
    arrivera, elle passera par ``apps/ventes/utils/references.py``.
    """
    cree = getattr(calepinage, 'created_at', None)
    if cree is None:
        return f'CAL-{calepinage.pk:04d}'
    return f'CAL-{cree.strftime("%y%m")}-{calepinage.pk:04d}'


def _texte(valeur):
    """Une chaîne non vide, ou ``None`` — jamais une chaîne vide trompeuse."""
    texte = (valeur or '').strip() if isinstance(valeur, str) else ''
    return texte or None


def _horodatage(moment):
    return moment.isoformat() if moment is not None else None


def _personne(user):
    """``{id, nom_complet}`` d'un compte, ou ``None``."""
    if user is None:
        return None
    nom = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    return {'id': user.pk,
            'nom_complet': nom or getattr(user, 'username', '')}


def _responsable(calepinage, company):
    """Le responsable du LEAD rattaché, ou ``None``.

    Le calepinage ne porte pas de responsable propre : plutôt que d'en
    inventer un (ou de coder en dur un prénom, ce que la règle fondateur
    interdit), on rend celui du lead — la personne qui répond réellement du
    dossier — et ``None`` quand il n'y en a pas.
    """
    lead = _lead_objet(calepinage, company)
    return _personne(getattr(lead, 'owner', None)) if lead is not None \
        else None


def _lead_objet(calepinage, company):
    from apps.crm.selectors import get_company_lead

    return get_company_lead(company, getattr(calepinage, 'lead_id', None))


def _lead(calepinage, company):
    """``{id, nom, ville}`` du lead rattaché, ou ``None``."""
    lead = _lead_objet(calepinage, company)
    if lead is None:
        return None
    nom = ' '.join(p for p in [getattr(lead, 'nom', ''),
                               getattr(lead, 'prenom', '') or ''] if p).strip()
    return {'id': lead.pk, 'nom': nom or f'Lead #{lead.pk}',
            'ville': _texte(getattr(lead, 'ville', ''))}


def _client(calepinage):
    """``{id, nom, ville}`` du client rattaché, ou ``None``."""
    client = getattr(calepinage, 'client', None)
    if client is None:
        return None
    return {'id': client.pk, 'nom': str(client),
            'ville': _texte(getattr(client, 'ville', ''))}


def _devis(calepinage, company):
    """``{id, reference, statut}`` du devis lié, ou ``None``.

    Lu par ``apps.ventes.selectors`` et RE-BORNÉ à la société : un calepinage
    ne peut pas servir de passerelle vers le devis d'une autre société.
    """
    from apps.ventes.selectors import get_devis_by_pk

    devis_id = getattr(calepinage, 'devis_id', None)
    if not devis_id or company is None:
        return None
    devis = get_devis_by_pk(devis_id)
    if devis is None or devis.company_id != company.pk:
        return None
    return {'id': devis.pk, 'reference': devis.reference,
            'statut': devis.statut}


def _schema_version(layout):
    """La version de schéma DÉCLARÉE par le document, ou ``None``.

    Jamais une version supposée : un layout qui ne dit pas sa version n'en a
    pas, et l'écran doit pouvoir le lire tel quel.
    """
    if not isinstance(layout, dict):
        return None
    for cle in ('schema_version', 'schemaVersion', 'version'):
        valeur = layout.get(cle)
        if isinstance(valeur, int) and not isinstance(valeur, bool):
            return valeur
    return None


def _compteur_versions(calepinage):
    """``{total, courante_id, derniere_le}`` — ``null`` quand il n'y a rien.

    Discipline du contrat : un calepinage SANS historique rend ``null``, pas
    ``0``. Publier un zéro ferait lire « aucune version enregistrée » là où
    rien n'a encore été mesuré.
    """
    from .. import selectors as cal_selectors

    derniere = cal_selectors.versions(calepinage).first()
    if derniere is None:
        return {'total': None, 'courante_id': None, 'derniere_le': None}
    return {
        'total': cal_selectors.versions(calepinage).count(),
        'courante_id': derniere.pk,
        'derniere_le': _horodatage(derniere.created_at),
    }


def _compteur_variantes(calepinage):
    """``{total, retenue_id, non_simulees}`` — ``null`` quand il n'y en a pas.

    ``non_simulees`` compte les variantes sans résultat de moteur : ce sont
    celles dont aucune grandeur de production n'est connue (elles ne valent
    pas « zéro kWh »).
    """
    from .. import selectors as cal_selectors

    lignes = list(cal_selectors.variantes(calepinage))
    if not lignes:
        return {'total': None, 'retenue_id': None, 'non_simulees': None}
    retenue = next((v for v in lignes if v.retenue), None)
    return {
        'total': len(lignes),
        'retenue_id': retenue.pk if retenue is not None else None,
        'non_simulees': len([v for v in lignes if not v.resultat]),
    }


def _image(calepinage):
    """``{url, genere_le, expire_le}`` du rendu stocké, ou trois ``null``.

    L'URL est PRÉSIGNÉE (lecture seule, 1 h) et fabriquée par le stockage
    ventes — jamais un second chemin de stockage (CAL19). Tant que la
    fonction mince de ``apps.ventes.services`` n'est pas là, l'URL vaut
    ``None`` : on ne fabrique jamais une URL qui ne mène nulle part.
    """
    from django.utils import timezone

    cle = _texte(getattr(calepinage, 'roof_image', ''))
    url = url_image_toiture(cle) if cle else None
    if url is None:
        return {'url': None, 'genere_le': None, 'expire_le': None}
    maintenant = timezone.now()
    return {
        'url': url,
        'genere_le': _horodatage(maintenant),
        'expire_le': _horodatage(maintenant + DUREE_URL_IMAGE),
    }


def url_image_toiture(cle):
    """L'URL présignée d'un rendu, par le stockage VENTES (jamais un second).

    Import FONCTION-LOCAL et résolution par ``getattr`` : la fonction mince
    côté ventes est posée par CAL19 ; avant elle, on rend ``None`` plutôt
    qu'une URL inventée. ``apps.calepinage`` n'importe ni une vue ni un modèle
    ventes (contrat import-linter).
    """
    if not cle:
        return None
    from apps.ventes import services as ventes_services

    fabrique = getattr(ventes_services, 'url_image_toiture', None)
    if fabrique is None:
        return None
    try:
        return fabrique(cle)
    except Exception:  # noqa: BLE001 — un stockage muet n'efface pas la fiche
        return None


def _permissions(calepinage, request):
    """Ce que L'APPELANT a le droit de faire — jamais un drapeau décoratif."""
    user = getattr(request, 'user', None) if request is not None else None
    peut_gerer = bool(user) and PeutGererCalepinage().has_permission(
        request, None)
    return {
        'peut_modifier': peut_gerer,
        'peut_supprimer': peut_gerer and not getattr(calepinage, 'devis_id',
                                                     None),
        'peut_retenir_variante': peut_gerer and bool(
            getattr(calepinage, 'variantes', None)
            and calepinage.variantes.exists()),
    }


# ── Lecture des paramètres de requête : refusée en NOMMANT le champ ────────

def _entier(valeur, champ):
    """Un identifiant entier, ou ``None`` quand le filtre est absent."""
    if valeur in (None, ''):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        raise DrfValidationError({
            champ: (f"Le filtre « {champ} » attend un identifiant "
                    f"(reçu : {valeur!r})."),
        })


def _statut(valeur):
    """Un statut du vocabulaire du serveur, ou ``None``.

    Un statut INCONNU est refusé : l'avaler rendrait la liste ENTIÈRE là où
    l'écran croit lire un sous-ensemble — exactement le mode de panne PV22.
    """
    if valeur in (None, ''):
        return None
    admis = [choix for choix, _ in Calepinage.Statut.choices]
    if valeur not in admis:
        raise DrfValidationError({
            'statut': (f"Statut inconnu : « {valeur} ». Statuts admis : "
                       f"{', '.join(admis)}."),
        })
    return valeur


def _moment(valeur):
    """Une date (ou un horodatage ISO), ou ``None`` — jamais une date devinée."""
    if valeur in (None, ''):
        return None
    moment = parse_datetime(valeur) or parse_date(valeur)
    if moment is None:
        raise DrfValidationError({
            'depuis': (f"Date illisible : « {valeur} ». Format attendu : "
                       "AAAA-MM-JJ (ou un horodatage ISO 8601)."),
        })
    return moment
