"""VT2 — API de la visite technique terrain (``apps.visites``).

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
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import HasPermissionOrLegacy
from core.permissions import _user_has_or_legacy
from core.viewsets import CompanyScopedModelViewSet

from . import selectors, services, visite_checklist as checklist
from .models import VisiteMedia, VisiteTerrain
from .serializers import VisiteRenvoiSerializer, VisiteTerrainSerializer

#: Types MIME acceptés pour une photo de visite. ``records.storage`` valide
#: déjà les octets magiques et la taille (10 Mo) ; on restreint en plus aux
#: IMAGES — un PDF n'est pas une photo de toit.
MIMES_PHOTO = ('image/png', 'image/jpeg', 'image/webp')


def _erreur(champ, message, code=status.HTTP_400_BAD_REQUEST):
    """400 qui NOMME le champ fautif (règle maison)."""
    return Response({'erreurs': {champ: message}}, status=code)


# VTA10 — la validation/écriture d'une mesure vit dans ``services.py`` : la
# MÊME fonction sert la route en ligne (ci-dessous) et le rejeu hors-ligne du
# moteur ``apps.offlinesync``. Deux copies seraient deux vérités.


class VisiteTerrainViewSet(CompanyScopedModelViewSet):
    """Visites techniques terrain — CRUD + actions de terrain (VT2/VT3/VT9)."""

    queryset = VisiteTerrain.objects.select_related('lead', 'commercial').all()
    serializer_class = VisiteTerrainSerializer
    read_permission = 'visites_voir'

    #: Codes d'écriture par action (le reste retombe sur ``visites_modifier``).
    PERMISSIONS_ECRITURE = {
        'create': 'visites_creer',
        'valider': 'visites_valider',
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
            getattr(self, 'action', None), 'visites_modifier')

    # -- VTA6 : PORTEE DURE "MES VISITES" -------------------------------------
    #
    # Avant VTA6, ne voir que ses visites etait un OPT-IN du client
    # (``?mine=1``) : un commercial terrain curieux -- ou un ecran mal cable --
    # listait toute la societe. Depuis que l'app a son propre utilisateur
    # (role "Commercial terrain", VTA4), la restriction est imposee par le
    # SERVEUR, sur TOUTES les routes du viewset (liste, detail, actions) :
    #
    #   * sans ``visites_valider``, on ne voit QUE ``commercial=self`` ;
    #   * avec ``visites_valider`` (bureau d'etudes / responsable), on voit
    #     l'equipe -- c'est son metier d'arbitrer les dossiers des autres.
    #
    # Consequence voulue : un GET sur la visite d'un collegue rend 404 (elle
    # n'est pas dans le queryset), jamais 403 -- on ne confirme pas l'existence
    # d'un enregistrement qu'on n'a pas le droit de voir. Le ``?mine=1``
    # historique reste accepte : il RESTREINT encore un valideur a ses propres
    # visites, il n'elargit jamais la portee de personne.

    def _voit_toute_l_equipe(self):
        """Vrai si l'appelant porte ``visites_valider`` (ou en tient lieu)."""
        return _user_has_or_legacy(self.request.user, 'visites_valider')

    def get_queryset(self):
        qs = super().get_queryset()
        if not self._voit_toute_l_equipe():
            return qs.filter(commercial=self.request.user)
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
        # VTA7 — l'assigne apprend tout de suite que sa journee a change.
        services.notifier_assignation(visite, acteur=request.user)
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
        visite = self.get_object()
        refus = self._refus_si_gelee(visite)
        if refus is not None:
            return refus
        # VTA7 — on releve l'assigne AVANT l'ecriture : une REASSIGNATION
        # (changement reel d'assigne) previent le nouveau. Un PATCH qui ne
        # touche pas `commercial` ne notifie personne -- sinon chaque
        # correction de notes sonnerait la cloche.
        avant = visite.commercial_id
        reponse = super().update(request, *args, **kwargs)
        visite.refresh_from_db()
        if visite.commercial_id != avant:
            services.notifier_assignation(visite, acteur=request.user)
        return reponse

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
        visite, erreurs = services.enregistrer_mesures(
            visite, categorie, request.data.get('valeurs'))
        if erreurs:
            return Response({'erreurs': erreurs},
                            status=status.HTTP_400_BAD_REQUEST)
        return self._agregat(visite)

    # -- VTA6 : PROGRESSION TERRAIN (deux boutons au pouce) -------------------
    #
    # "En route" puis "Arrive". L'heure vient TOUJOURS du serveur : un
    # telephone dont l'horloge derive (ou qu'on avance expres) ne peut pas
    # ecrire une heure d'arrivee. Les deux actions sont IDEMPOTENTES -- un
    # double tap dans une zone a reseau faible ne repousse pas le jalon -- et
    # reservees a l'ASSIGNE : un valideur voit la journee de son equipe, il ne
    # pointe pas l'arrivee a la place du commercial qui roule.

    def _refus_si_pas_l_assigne(self, visite):
        if visite.commercial_id == self.request.user.id:
            return None
        return _erreur(
            'commercial',
            "Seul le commercial assigne a cette visite peut pointer sa "
            "progression sur le terrain.",
            status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['post'], url_path='demarrer-route')
    def demarrer_route(self, request, pk=None):
        """Pointe le DEPART vers le site (horodatage serveur, idempotent)."""
        visite = self.get_object()
        refus = self._refus_si_gelee(visite) or self._refus_si_pas_l_assigne(
            visite)
        if refus is not None:
            return refus
        if visite.en_route_le is None:
            visite.en_route_le = timezone.now()
            visite.save(update_fields=['en_route_le'])
        return self._agregat(visite)

    @action(detail=True, methods=['post'], url_path='arriver')
    def arriver(self, request, pk=None):
        """Pointe l'ARRIVEE sur le site (horodatage serveur, idempotent).

        Ne reclame PAS que "En route" ait ete pointe : un commercial deja sur
        place quand il ouvre l'app doit pouvoir dire qu'il est arrive -- lui
        refuser l'arrivee parce qu'il a oublie un bouton serait une donnee
        perdue pour rien. Le depart reste alors simplement ``null``, ce qui est
        la verite.
        """
        visite = self.get_object()
        refus = self._refus_si_gelee(visite) or self._refus_si_pas_l_assigne(
            visite)
        if refus is not None:
            return refus
        if visite.arrivee_le is None:
            visite.arrivee_le = timezone.now()
            visite.save(update_fields=['arrivee_le'])
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
        """Feu vert calepinage — réservé au code ``visites_valider``."""
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


def _coordonnee(brute):
    """(Decimal|None, message|None) — une coordonnée GPS optionnelle."""
    if brute in (None, ''):
        return None, None
    try:
        return Decimal(str(brute)), None
    except (InvalidOperation, ValueError, TypeError):
        return None, 'Coordonnée GPS invalide.'


#: VTA10 — alias du service (source unique, partagée avec le rejeu hors-ligne).
_marquer_en_cours = services.marquer_en_cours


# -- VTA6 : "MA JOURNEE", L'ACCUEIL DE L'APP ---------------------------------
#
# Recherche field-service : l'ecran d'accueil d'un terrain est SA JOURNEE, pas
# un tableau de bord. Endpoint LITTERAL du contrat VTA0
# (``apps/visites/contract_samples/ma_journee.json``) :
# ``GET /api/django/visites/ma-journee/`` -- un segment de MODULE, pas une
# ressource du routeur, d'ou un ``path()`` explicite dans ``urls.py``.

class MaJourneeView(APIView):
    """Les visites du JOUR + celles EN RETARD de l'appelant.

    Portee, dans cet ordre et toujours cote serveur :

    1. la SOCIETE (``request.user.company``) -- jamais lue du corps ni de la
       query ;
    2. la portee dure "mes visites" : sans ``visites_valider``, on ne voit que
       ``commercial=self``. Un valideur voit sa propre journee par defaut et
       celle de l'EQUIPE avec ``?tous=1`` -- un elargissement qu'un terrain ne
       peut pas s'accorder, puisqu'il est conditionne a la permission.

    La date vient de l'horloge SERVEUR dans le fuseau du projet
    (``timezone.localdate()``) : le telephone ne choisit pas quel jour on est.
    """

    permission_classes = [HasPermissionOrLegacy('visites_voir')]

    @extend_schema(
        parameters=[OpenApiParameter(
            'tous', bool, OpenApiParameter.QUERY,
            description=("Reserve aux porteurs de visites_valider : la "
                         "journee de toute l'equipe au lieu de la sienne."))],
        responses=inline_serializer(
            name='VisitesMaJournee',
            fields={
                'date': serializers.CharField(),
                'en_retard_count': serializers.IntegerField(),
                'visites': serializers.ListField(
                    child=serializers.DictField()),
            }))
    def get(self, request):
        visites = (VisiteTerrain.objects
                   .select_related('lead', 'commercial')
                   .filter(company=request.user.company))
        tous = str(request.query_params.get('tous', '')).strip() in ('1',
                                                                     'true')
        if not (tous and _user_has_or_legacy(request.user,
                                             'visites_valider')):
            visites = visites.filter(commercial=request.user)
        return Response(selectors.ma_journee(
            visites, aujourdhui=timezone.localdate()))


# -- VTA16 : CHOISIR LE CLIENT D'UNE VISITE A PLANIFIER ----------------------
#
# L'ecran "Planifier une visite" doit retrouver un lead par son nom ou son
# telephone. Il ne tape PAS la liste CRM : il tape cet endpoint, qui sert
# EXACTEMENT {id, nom, ville, telephone} et rien d'autre (ni email, ni etape de
# pipeline, ni montant) via `apps.crm.selectors.rechercher_leads_minimal` --
# frontiere M3, jamais les models du CRM.
#
# La PORTE est portee par L'ENDPOINT (`visites_valider`), pas par l'ecran : un
# commercial terrain qui ne planifie pas ne doit pas pouvoir enumerer le
# fichier leads au moteur de recherche. Un ecran qui cache le champ ne protege
# rien -- la garde est ici, cote serveur (AUD421 : la permission est NOMMEE sur
# la vue, jamais devinee).

class LeadsRechercheView(APIView):
    """Recherche lead MINIMALE, bornee societe — contrat `leads_recherche`."""

    permission_classes = [HasPermissionOrLegacy('visites_valider')]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                'q', str, OpenApiParameter.QUERY,
                description=('Terme recherche dans le nom OU le telephone. '
                             'Vide : aucun resultat (on n’enumere pas '
                             'l’annuaire).')),
            OpenApiParameter(
                'limit', int, OpenApiParameter.QUERY,
                description='Nombre maximum de resultats (defaut 10, max 50).'),
        ],
        responses=inline_serializer(
            name='VisitesLeadsRecherche',
            fields={'results': serializers.ListField(
                child=serializers.DictField())}))
    def get(self, request):
        from apps.crm import selectors as crm_selectors

        return Response({'results': crm_selectors.rechercher_leads_minimal(
            request.user.company,
            request.query_params.get('q'),
            limit=request.query_params.get('limit') or 10)})
