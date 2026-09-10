"""VT2 — API de la visite technique terrain.

UN ViewSet company-scopé (``CompanyScopedModelViewSet`` : queryset filtré sur
``request.user.company``, ``company`` forcée côté serveur au ``perform_create``
— jamais lue du corps de requête) qui sert :

* la LISTE des visites (``?mine=1`` = les miennes), avec le badge de
  complétude calculé serveur ;
* l'AGRÉGAT complet du contrat PACT10 en lecture
  (``selectors.contexte_visite_terrain``) ;
* les actions du terrain : ajout/suppression d'une photo dans un SLOT nommé,
  saisie des mesures par catégorie, et la transition ``terminer`` — REFUSÉE
  tant que la complétude serveur n'est pas atteinte.

Deux règles de la maison sont câblées ici :

* **l'erreur NOMME le champ fautif** — une mesure invalide renvoie
  ``400 {"erreurs": {"<champ>": "<message clair en français>"}}``, jamais un
  « non enregistré » générique ;
* **aucun verdict automatique** — le serveur vérifie la PRÉSENCE et la NATURE
  d'une mesure, jamais si sa valeur est « suffisante ». Aucun seuil technique
  n'existe dans ce module.
"""
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer)
from rest_framework import serializers, status
from rest_framework.decorators import (
    action, api_view, permission_classes)
from rest_framework.response import Response

from authentication.permissions import HasPermissionOrLegacy
from core.viewsets import CompanyScopedModelViewSet

from . import selectors, services, visite_checklist as checklist
from .models import VisiteMedia, VisiteTerrain
from .serializers_visite import VisiteRenvoiSerializer, VisiteTerrainSerializer

#: Types MIME acceptés pour une photo de visite. ``records.storage`` valide
#: déjà les octets magiques et la taille (10 Mo) ; on restreint en plus aux
#: IMAGES — un PDF n'est pas une photo de toit.
MIMES_PHOTO = ('image/png', 'image/jpeg', 'image/webp')


def _erreur(champ, message, code=status.HTTP_400_BAD_REQUEST):
    """400 qui NOMME le champ fautif (règle maison)."""
    return Response({'erreurs': {champ: message}}, status=code)


def _valeur_mesure(declaration, brute):
    """Convertit/valide UNE valeur de mesure. Renvoie (valeur, message)."""
    if brute is None or brute == '':
        return None, None
    nature = declaration['nature']
    if nature == checklist.NOMBRE:
        try:
            nombre = Decimal(str(brute))
        except (InvalidOperation, ValueError, TypeError):
            return None, (f"« {declaration['libelle']} » attend un nombre "
                          f'(reçu : {brute!r}).')
        if nombre < 0:
            return None, (f"« {declaration['libelle']} » ne peut pas être "
                          'négatif.')
        return float(nombre), None
    if nature == checklist.BOOLEEN:
        if isinstance(brute, bool):
            return brute, None
        texte = str(brute).strip().lower()
        if texte in ('true', '1', 'oui'):
            return True, None
        if texte in ('false', '0', 'non'):
            return False, None
        return None, (f"« {declaration['libelle']} » attend oui ou non.")
    if nature == checklist.CHOIX:
        texte = str(brute).strip()
        if texte not in declaration['choix']:
            options = ', '.join(declaration['choix'])
            return None, (f"« {declaration['libelle']} » : valeur inconnue "
                          f'« {texte} ». Choix possibles : {options}.')
        return texte, None
    return str(brute), None


class VisiteTerrainViewSet(CompanyScopedModelViewSet):
    """Visites techniques terrain — CRUD + actions de terrain (VT2/VT3/VT9)."""

    queryset = VisiteTerrain.objects.select_related('lead', 'commercial').all()
    serializer_class = VisiteTerrainSerializer
    read_permission = 'crm_visite_voir'

    #: Codes d'écriture par action (le reste retombe sur ``crm_visite_modifier``).
    PERMISSIONS_ECRITURE = {
        'create': 'crm_visite_creer',
        'valider': 'crm_visite_valider',
    }

    @property
    def write_permission(self):
        """Code exigé côté écriture, par action.

        Exprimé en PROPRIÉTÉ plutôt qu'en ``get_permissions()`` surchargé :
        ``ScopedPermission`` (le défaut de la base) lit cet attribut, donc
        aucune garde déclarée sur une ``@action`` ne peut être écrasée en
        silence (garde AUD421).
        """
        return self.PERMISSIONS_ECRITURE.get(
            getattr(self, 'action', None), 'crm_visite_modifier')

    # ── Lecture ──────────────────────────────────────────────────────────────

    def get_queryset(self):
        qs = super().get_queryset()
        mine = str(self.request.query_params.get('mine', '')).strip()
        if mine in ('1', 'true'):
            qs = qs.filter(commercial=self.request.user)
        return qs

    def list(self, request, *args, **kwargs):
        lignes = [selectors.ligne_visite_terrain(visite)
                  for visite in self.filter_queryset(self.get_queryset())]
        return Response(lignes)

    def retrieve(self, request, *args, **kwargs):
        return Response(selectors.contexte_visite_terrain(self.get_object()))

    def _agregat(self, visite):
        return Response(selectors.contexte_visite_terrain(visite))

    # ── Création ─────────────────────────────────────────────────────────────

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        visite = serializer.instance
        if visite.commercial_id is None:
            visite.commercial = request.user
            visite.save(update_fields=['commercial'])
        services.journaliser_visite(visite, request.user, 'creation')
        return Response(selectors.contexte_visite_terrain(visite),
                        status=status.HTTP_201_CREATED)

    # ── Garde de lecture seule (VT3 : une visite validée est gelée) ───────────

    def _refus_si_gelee(self, visite):
        if visite.modifiable:
            return None
        return Response(
            {'erreurs': {'statut': visite.raison_lecture_seule}},
            status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        refus = self._refus_si_gelee(self.get_object())
        if refus is not None:
            return refus
        return super().update(request, *args, **kwargs)

    # ── Photos par slot ──────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='photos')
    def photos(self, request, pk=None):
        """Ajoute UNE photo dans un slot NOMMÉ de la checklist."""
        visite = self.get_object()
        refus = self._refus_si_gelee(visite)
        if refus is not None:
            return refus

        slot_code = (request.data.get('slot_code') or '').strip()
        if slot_code not in checklist.codes_slots():
            return _erreur(
                'slot_code',
                f'Emplacement photo inconnu « {slot_code} ». La checklist ne '
                'connaît que : ' + ', '.join(sorted(checklist.codes_slots()))
                + '.')
        fichier = request.FILES.get('fichier')
        if fichier is None:
            return _erreur('fichier', 'Aucun fichier reçu.')

        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Attachment
        from apps.records.storage import store_attachment

        meta, message = store_attachment(fichier, company=request.user.company)
        if message:
            return _erreur('fichier', message)
        if meta['mime'] not in MIMES_PHOTO:
            return _erreur(
                'fichier',
                'Une photo de visite doit être une image (PNG, JPEG ou WebP).')

        # La pièce jointe cible le LEAD : elle reste visible dans le panneau
        # de pièces jointes existant — jamais un second magasin de fichiers.
        content_type = ContentType.objects.get(app_label='crm', model='lead')
        attachment = Attachment.objects.create(
            company=request.user.company, content_type=content_type,
            object_id=visite.lead_id, uploaded_by=request.user, **meta)

        gps_lat, message = _coordonnee(request.data.get('gps_lat'))
        if message:
            return _erreur('gps_lat', message)
        gps_lng, message = _coordonnee(request.data.get('gps_lng'))
        if message:
            return _erreur('gps_lng', message)

        VisiteMedia.objects.create(
            company=request.user.company, visite=visite, attachment=attachment,
            slot_code=slot_code,
            commentaire=(request.data.get('commentaire') or '').strip(),
            gps_lat=gps_lat, gps_lng=gps_lng)
        _marquer_en_cours(visite)
        return self._agregat(visite)

    @extend_schema(parameters=[OpenApiParameter(
        'media_id', int, OpenApiParameter.PATH,
        description='Identifiant du VisiteMedia à retirer.')])
    @action(detail=True, methods=['delete'],
            url_path=r'photos/(?P<media_id>[^/.]+)')
    def supprimer_photo(self, request, pk=None, media_id=None):
        visite = self.get_object()
        refus = self._refus_si_gelee(visite)
        if refus is not None:
            return refus
        media = visite.medias.filter(pk=media_id).first()
        if media is None:
            return _erreur('media_id', 'Cette photo n’existe pas sur cette '
                                       'visite.', status.HTTP_404_NOT_FOUND)
        media.delete()
        return self._agregat(visite)

    # ── Mesures par catégorie ────────────────────────────────────────────────

    @action(detail=True, methods=['patch'], url_path='mesures')
    def mesures(self, request, pk=None):
        """Enregistre les mesures d'UNE catégorie, champ par champ."""
        visite = self.get_object()
        refus = self._refus_si_gelee(visite)
        if refus is not None:
            return refus

        categorie = (request.data.get('categorie') or '').strip()
        declaration = checklist.categorie(categorie)
        if declaration is None or not declaration['mesures']:
            return _erreur(
                'categorie',
                f'Catégorie de mesures inconnue « {categorie} ».')
        valeurs = request.data.get('valeurs')
        if not isinstance(valeurs, dict):
            return _erreur('valeurs',
                           'Les valeurs doivent être un objet '
                           '{champ: valeur}.')

        connus = {champ['code']: champ for champ in declaration['mesures']}
        erreurs = {}
        propres = {}
        for code, brute in valeurs.items():
            champ = connus.get(code)
            if champ is None:
                erreurs[code] = (f'Champ inconnu dans la catégorie '
                                 f'« {declaration["libelle"]} ».')
                continue
            valeur, message = _valeur_mesure(champ, brute)
            if message:
                erreurs[code] = message
            else:
                propres[code] = valeur
        if erreurs:
            return Response({'erreurs': erreurs},
                            status=status.HTTP_400_BAD_REQUEST)

        stockees = visite.mesures if isinstance(visite.mesures, dict) else {}
        bloc = dict(stockees.get(categorie) or {})
        bloc.update(propres)
        stockees = dict(stockees)
        stockees[categorie] = bloc
        visite.mesures = stockees
        visite.save(update_fields=['mesures'])
        _marquer_en_cours(visite)
        return self._agregat(visite)

    # ── Transition « terminer » (gate de complétude SERVEUR) ─────────────────

    @action(detail=True, methods=['post'], url_path='terminer')
    def terminer(self, request, pk=None):
        visite = self.get_object()
        refus = self._refus_si_gelee(visite)
        if refus is not None:
            return refus
        manquants = selectors.visite_terrain_manquants(visite)
        if manquants:
            return Response({
                'manquants': manquants,
                'message': (
                    'La visite ne peut pas être terminée : '
                    f'{len(manquants)} élément(s) manquent encore.'),
            }, status=status.HTTP_400_BAD_REQUEST)
        visite.statut = VisiteTerrain.Statut.TERMINEE
        visite.date_realisee = timezone.now()
        visite.save(update_fields=['statut', 'date_realisee'])
        services.journaliser_visite(visite, request.user, 'terminee')
        return self._agregat(visite)

    # ── VT3 — Feu vert du bureau d'études ────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Feu vert calepinage — réservé au code ``crm_visite_valider``."""
        visite = self.get_object()
        if visite.statut == VisiteTerrain.Statut.VALIDEE:
            return _erreur('statut', 'Cette visite est déjà validée.')
        services.valider_visite(visite, request.user)
        return self._agregat(visite)

    @action(detail=True, methods=['post'], url_path='renvoyer')
    def renvoyer(self, request, pk=None):
        """Renvoie la visite au commercial, avec ce qu'il doit refaire."""
        visite = self.get_object()
        serializer = VisiteRenvoiSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'erreurs': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)
        donnees = serializer.validated_data
        message = services.renvoyer_visite(
            visite, request.user,
            photos=donnees['photos'], mesures=donnees['mesures'],
            motif=donnees['motif'])
        if message:
            return _erreur('photos', message)
        return self._agregat(visite)

    # ── VT9 — Toit assemblé (panorama serveur) + VT11 calage ─────────────────

    @action(detail=True, methods=['post'], url_path='assembler-photos')
    def assembler_photos(self, request, pk=None):
        """Lance l'assemblage des photos du toit (tâche Celery).

        Réponse IMMÉDIATE avec ``photo_toit.assemblage_etat = 'en_cours'`` ;
        l'écran suit l'avancement en relisant l'agrégat (le GET est le
        polling — aucun second endpoint d'état à tenir synchrone).
        """
        visite = self.get_object()
        refus = self._refus_si_gelee(visite)
        if refus is not None:
            return refus
        visite.assemblage_etat = VisiteTerrain.Assemblage.EN_COURS
        visite.assemblage_erreur = ''
        visite.save(update_fields=['assemblage_etat', 'assemblage_erreur'])

        from .tasks import assembler_photos_toit_task

        try:
            assembler_photos_toit_task.delay(visite.pk)
        except Exception:  # pragma: no cover - courtier indisponible
            # Sans courtier, on exécute en ligne plutôt que de laisser la
            # visite bloquée « en cours » pour toujours.
            assembler_photos_toit_task(visite.pk)
        visite.refresh_from_db()
        return self._agregat(visite)

    @action(detail=True, methods=['get'], url_path='photo-toit')
    def photo_toit(self, request, pk=None):
        """Sert l'image assemblée par le proxy Django (jamais MinIO direct)."""
        from django.http import HttpResponse

        from apps.records.storage import fetch_attachment

        visite = self.get_object()
        if not visite.photo_toit_key:
            return _erreur('photo_toit', "Aucune image de toit assemblée pour "
                                         'cette visite.',
                           status.HTTP_404_NOT_FOUND)
        data, message = fetch_attachment(visite.photo_toit_key)
        if message:
            return _erreur('photo_toit', message, status.HTTP_404_NOT_FOUND)
        return HttpResponse(data, content_type='image/png')

    @action(detail=True, methods=['patch'], url_path='calage')
    def calage(self, request, pk=None):
        """VT11 — enregistre les 4 coins du drapage sur le contour du toit."""
        visite = self.get_object()
        refus = self._refus_si_gelee(visite)
        if refus is not None:
            return refus
        calage = request.data.get('texture_calage')
        if calage is None:
            visite.texture_calage = None
            visite.save(update_fields=['texture_calage'])
            return self._agregat(visite)
        coins = (calage or {}).get('coins') if isinstance(calage, dict) else None
        if not isinstance(coins, list) or len(coins) != 4:
            return _erreur(
                'texture_calage',
                'Le calage attend exactement 4 coins [latitude, longitude].')
        propres = []
        for coin in coins:
            if not isinstance(coin, (list, tuple)) or len(coin) != 2:
                return _erreur('texture_calage',
                               'Chaque coin doit être une paire '
                               '[latitude, longitude].')
            lat, message = _coordonnee(coin[0])
            if message or lat is None:
                return _erreur('texture_calage',
                               'Latitude de coin invalide.')
            lng, message = _coordonnee(coin[1])
            if message or lng is None:
                return _erreur('texture_calage',
                               'Longitude de coin invalide.')
            propres.append([float(lat), float(lng)])
        visite.texture_calage = {'coins': propres}
        visite.save(update_fields=['texture_calage'])
        return self._agregat(visite)


@extend_schema(responses=inline_serializer(
    name='LeadPhotoToit',
    fields={
        'visite_id': serializers.IntegerField(allow_null=True),
        'url': serializers.CharField(allow_null=True),
        'texture_calage': serializers.JSONField(allow_null=True),
    }))
@api_view(['GET'])
@permission_classes([HasPermissionOrLegacy('crm_voir')])
def lead_photo_toit(request, lead_id):
    """VT12 — ``GET /api/django/crm/leads/<pk>/photo-toit/``.

    La porte par laquelle l'atelier 3D/calepinage et la carte de la fiche lead
    lisent le toit réaliste SANS connaître le module visite : ils demandent la
    texture d'un LEAD, le serveur choisit la dernière visite VALIDÉE.

    JAMAIS 404 : sans visite validée, sans image, ou pour un lead qui n'est pas
    de la société de l'appelant, la réponse porte les MÊMES clés à ``null``
    (``{"visite_id": null, "url": null, "texture_calage": null}``). Une seule
    forme à consommer côté écran, et aucune différence de réponse qui
    laisserait deviner l'existence du lead d'une autre société.

    Permission : ``crm_voir`` — la lecture CRM ordinaire, celle que portent
    déjà le commercial ET l'atelier ; exiger ``crm_visite_voir`` fermerait la
    porte aux écrans qui ne font que peindre le toit.
    """
    from . import selectors  # noqa: PLC0415 - import local (frontière app)
    from .models import Lead  # noqa: PLC0415

    lead = Lead.objects.filter(pk=lead_id,
                               company=request.user.company).first()
    return Response(selectors.texture_toit_pour_lead(lead))


def _coordonnee(brute):
    """(Decimal|None, message|None) — une coordonnée GPS optionnelle."""
    if brute in (None, ''):
        return None, None
    try:
        return Decimal(str(brute)), None
    except (InvalidOperation, ValueError, TypeError):
        return None, 'Coordonnée GPS invalide.'


def _marquer_en_cours(visite):
    """Un brouillon devient « en cours » dès la première contribution."""
    if visite.statut in (VisiteTerrain.Statut.BROUILLON,
                         VisiteTerrain.Statut.A_REFAIRE):
        visite.statut = VisiteTerrain.Statut.EN_COURS
        visite.save(update_fields=['statut'])
