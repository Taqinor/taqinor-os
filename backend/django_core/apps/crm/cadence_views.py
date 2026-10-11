"""SPL74 — cadence de relance : RelanceEtapeViewSet (cockpit des relances),
MessageTemplateViewSet et leurs aides, déplacés de ``views.py`` à
l'identique (move only).

Nom imposé ``cadence_views.py`` : ``core/action_permission_scan.py`` ne lit que
``views.py``, ``views/`` ou ``*_views.py``. Règle d'import : ce module
n'importe JAMAIS ``views.py`` (``views.py`` importe ce module, jamais
l'inverse).
"""
import logging

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import filters, mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from core.mixins import TenantMixin
from core.viewsets import CompanyScopedModelViewSet
from .models import MessageTemplate, RelanceEtape
from .serializers_cadence import MessageTemplateSerializer, RelanceEtapeSerializer
from . import schema_docs as sd
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin, IsAdminRole

logger = logging.getLogger(__name__)


def _best_effort(libelle, fn, *args, **kwargs):
    """ALEA30 — effet secondaire NON critique : exécuté dans son propre point
    de sauvegarde (une erreur SQL n'empoisonne pas la transaction appelante),
    sa panne est journalisée et n'échoue jamais l'appelant."""
    from django.db import transaction
    try:
        with transaction.atomic():
            return fn(*args, **kwargs)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('ALEA30: effet secondaire « %s » échoué', libelle,
                       exc_info=True)
        return None


class GesteToucheEchoue(APIException):
    """ACRM22 — un geste de touche (fait, sauter, réponse, pièce reçue,
    note, report, WhatsApp) a échoué en cours d'écriture : la transaction
    est annulée, RIEN n'est écrit (ni touche close, ni chatter, ni pièce),
    et la réponse le dit explicitement."""
    status_code = 500
    default_detail = ('Le geste n’a pas pu être enregistré : rien n’a été '
                      'écrit. Réessayez.')
    default_code = 'geste_touche_echoue'


def _geste_atomique(methode):
    """ACRM22 (C-ACRM-015) — exécute un geste de touche dans
    ``transaction.atomic()`` : une panne du 2ᵉ ou 3ᵉ appel (report de la
    prochaine touche, enregistrement de la pièce…) annule AUSSI les
    écritures des appels précédents. Les fichiers déjà poussés au stockage
    par le geste (``request._acrm22_cles``) sont supprimés si la transaction
    échoue — jamais une pièce orpheline. Les refus (400/403/404) passent
    tels quels."""
    import functools

    @functools.wraps(methode)
    def enveloppe(self, request, *args, **kwargs):
        from django.core.exceptions import PermissionDenied
        from django.db import transaction
        from django.http import Http404

        request._acrm22_cles = []
        try:
            with transaction.atomic():
                return methode(self, request, *args, **kwargs)
        except (APIException, Http404, PermissionDenied):
            _supprimer_fichiers_du_geste(request)
            raise
        except Exception as exc:
            _supprimer_fichiers_du_geste(request)
            logger.warning('ACRM22: geste de touche annulé (%s)',
                           getattr(methode, '__name__', '?'), exc_info=True)
            raise GesteToucheEchoue() from exc
    return enveloppe


def _supprimer_fichiers_du_geste(request):
    """ACRM22 — retire du stockage les fichiers poussés par un geste dont
    la transaction n'a pas été validée (best-effort)."""
    from apps.records.storage import delete_attachment
    for cle in getattr(request, '_acrm22_cles', None) or []:
        delete_attachment(cle)


def _parse_rappel(date_str, heure_str=''):
    """MRY10 — « AAAA-MM-JJ » (+ « HH:MM » optionnel) → datetime AWARE local.

    Renvoie ``None`` si la saisie est invalide : l'appelant répond alors 400
    plutôt que de reporter la touche à une date fantaisiste."""
    import datetime as _dt

    from apps.crm import horaires as _horaires
    try:
        jour = _dt.date.fromisoformat(str(date_str).strip())
    except (TypeError, ValueError):
        return None
    heure = _dt.time(9, 0)
    texte = (heure_str or '').strip()
    if texte:
        try:
            heure = _dt.time.fromisoformat(texte)
        except (TypeError, ValueError):
            return None
    return _dt.datetime.combine(jour, heure, tzinfo=_horaires.CASABLANCA)


def _refus_date_passee(quand, libelle_champ):
    """CAD27 — le message d'erreur si ``quand`` tombe AVANT la journée en
    cours (heure de Casablanca), sinon ``None``.

    Une faute de frappe sur l'année reportait la touche dans le passé et
    tirait tout le plan en arrière (le delta s'appliquait sans contrôle de
    signe) : plusieurs touches apparaissaient d'un coup « en retard ». Le
    contrôle vit ICI, à la frontière de la saisie humaine : AUJOURD'HUI reste
    accepté (avancer une touche à aujourd'hui est un geste utile), et les
    recalages INTERNES du moteur (visite, reprise) ne passent pas par là.
    Le message NOMME le champ, tel que l'écran l'affiche (règle fondateur du
    08/09/2026)."""
    import datetime as _dt

    from django.utils import timezone as _tz

    from apps.crm import horaires as _horaires
    from core.dates import aujourd_hui_local

    if _tz.is_naive(quand):
        quand = _tz.make_aware(quand, _dt.timezone.utc)
    jour = quand.astimezone(_horaires.CASABLANCA).date()
    if jour >= aujourd_hui_local():
        return None
    return (f'« {libelle_champ} » : le {jour:%d/%m/%Y} est déjà passé — '
            'choisissez aujourd’hui ou une date à venir.')


#: CAD4 (résiduel) — le refus d'un appel coché « Fait » sans issue NOMME les
#: réponses que le panneau propose RÉELLEMENT (`RelanceEtapeRow.jsx`,
#: QUESTIONS) : « Intéressé » n'existe plus à l'écran depuis CAD4 (un seul mot,
#: « Client joint »), le citer ici renvoyait vers un bouton introuvable.
MESSAGE_ISSUE_APPEL_OBLIGATOIRE = (
    "Issue de l'appel obligatoire : Client joint, Pas de réponse, "
    'À rappeler le… ou Refus. C\'est elle qui programme le prochain geste.')


#: SUIVI E8 (30/09/2026) — « Fait », « Sauter » et « Reporter » sur une
#: touche DÉJÀ traitée (deux onglets, double clic, liste périmée) rejouaient
#: toute la suite du moteur sur une touche close. Refus nommé, sous le champ
#: ``etape`` (même esprit que ``refus_reponse_touche`` / ``refus_piece_recue``).
MESSAGE_ETAPE_DEJA_TRAITEE = (
    'Cette étape est déjà traitée — rechargez la liste.')


#: SUIVI E2 (30/09/2026) — « refus » n'est pas une réponse de « Décider la
#: suite » : c'est la décision elle-même qui se prend ici.
MESSAGE_REFUS_SUR_DECIDER_SUITE = (
    '« Décider la suite » : choisissez « Perdu — clore le dossier » (avec '
    'son motif) ou une relance ultérieure.')


#: COCKPIT-CONTRÔLE B4 (30/09/2026) — une TÂCHE (préparer le devis, planifier
#: la visite, décider la suite, devis modifié, question de prix) ne se saute
#: pas : l'écran masquait le bouton, le serveur ne gardait rien — un « Sauter »
#: envoyé à la main effaçait une tâche du cockpit sans trace de traitement.
MESSAGE_TACHE_NON_SAUTABLE = (
    '« Sauter » : une tâche ne se saute pas — traitez-la ou reportez-la.')


def _prochaine_touche_publique(etape):
    """SUIVI E9 (30/09/2026) — la forme PUBLIQUE de l'étape qu'un « Fait »
    annonce (``prochaine_touche`` des réponses de ``fait``, du report d'une
    étape de filet et de ``piece-recue``), ou ``None``.

    Elle ne portait que ``{due_at, due_date, canal}`` : l'écran annonçait
    « Prochain appel programmé » pour « Préparer et envoyer le devis ». Elle
    NOMME désormais l'étape (ADDITIF) : ``libelle`` (celui de l'étape, tel que
    la société l'a réglé) et ``cle`` (``cadence_config.cle_de`` : la clé
    moteur, retrouvée aussi pour une étape posée avant la clé ; ``''`` pour un
    barreau du protocole). Fonction PURE, aucune requête."""
    if etape is None:
        return None
    from .cadence_config import cle_de

    return {
        'due_at': etape.due_at.isoformat() if etape.due_at else None,
        'due_date': etape.due_date.isoformat() if etape.due_date else None,
        'canal': etape.canal,
        'libelle': etape.libelle or '',
        'cle': cle_de(etape),
    }


# ── RELANCE FOUNDATION — file « Relances du jour » + actions Fait/Sauter ────
@extend_schema_view(list=extend_schema(parameters=[sd.P_LEAD, sd.P_OWNER, sd.P_SCOPE], responses=sd.OBJ))
class RelanceEtapeViewSet(TenantMixin, mixins.ListModelMixin,
                          viewsets.GenericViewSet):
    """Étapes de plan de relance structuré (``RelanceEtape``). AUCUNE création/
    édition brute exposée : les étapes sont matérialisées UNIQUEMENT par
    ``LeadViewSet.initialiser_relance`` (jamais un POST/PUT client direct) —
    seules ``list`` (la file due) et les deux actions ``fait``/``sauter`` sont
    routées. Aucun envoi automatique (WhatsApp/e-mail) n'est jamais déclenché
    ici : ce sont des rappels VISUELS pour le commercial."""
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = RelanceEtape.objects.select_related('lead', 'lead__owner').all()
    serializer_class = RelanceEtapeSerializer

    def get_permissions(self):
        # MRY10/MRY13 — `reporter` et `message` sont listées EXPLICITEMENT :
        # get_permissions() PRIME sur le `permission_classes` de l'@action
        # (bug CI #25), une action non listée retomberait silencieusement sur
        # la mauvaise garde. `message` est une LECTURE (préparer le texte
        # n'engage rien) ; `whatsapp` ÉCRIT (touche faite, activité, premier
        # contact, AuditLog) et reste donc réservée.
        # MRY30 — `suivi` est une LECTURE pure (la file PAR PÉRIODE, tous
        # statuts) : même garde que `list`, et listée ICI parce que
        # get_permissions() PRIME sur le `permission_classes` de l'@action.
        # CKP3 — `kpi_adherence` et `mes_stats` sont des LECTURES pures,
        # ouvertes à TOUS les rôles : décision fondateur de TRANSPARENCE
        # TOTALE (2026-09-10, « on voit la même chose moi et elle »). Elles
        # sont listées ICI, nommément, parce que get_permissions() PRIME sur
        # le `permission_classes` de l'@action (garde AUD421 / bug CI #25) :
        # sans ces noms, la déclaration inline serait décorative et l'action
        # retomberait sur `IsResponsableOrAdmin`.
        # RLC2 — `journal` est une LECTURE PURE (le sélecteur n'écrit rien) :
        # même garde que `list`, et listée ICI nommément parce que
        # get_permissions() PRIME sur le `permission_classes` de l'@action.
        # CAD99 — `cadences_echues` est une LECTURE PURE (le sélecteur CAD75
        # ne clôt rien, n'écrit rien) : même garde que `list`, listée ICI
        # nommément pour la même raison que `journal`.
        # Chaîne commerciale (25/09/2026) — `chaine_commerciale` est une
        # LECTURE PURE du cockpit : même garde que `mes_stats`, listée ICI
        # nommément pour la même raison.
        # COCKPIT-CONTRÔLE (30/09/2026) — `controle` est une LECTURE PURE du
        # cockpit, ouverte à tous les rôles comme `kpi_adherence` (décision
        # de transparence CKP3) : listée ICI nommément, même raison.
        if self.action in ('list', 'message', 'suivi',
                           'kpi_adherence', 'mes_stats', 'journal',
                           'cadences_echues', 'chaine_commerciale',
                           'controle'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        # TenantMixin.get_queryset() borne déjà à la société ; on ajoute ici
        # la portée de visibilité (Feature F, même convention que LeadViewSet)
        # de façon INCONDITIONNELLE (get_object() des actions fait/sauter
        # passe aussi par ici — jamais filtrée par le scope date de `list()`,
        # sinon une étape EN RETARD deviendrait introuvable pour l'action).
        qs = super().get_queryset()
        if not self.request.user.company_id:
            return qs
        # ACRM28 — portée propriétaire ET périmètre d'entités (une seule
        # définition, ``selectors.leads_visibles``).
        from .selectors import leads_visibles
        visibles = leads_visibles(
            self.request.user, self.request.user.company)
        return qs.filter(lead_id__in=visibles.values('id'))

    def list(self, request, *args, **kwargs):
        """File « Relances du jour ». ``?scope=overdue|today|all`` (défaut
        today) + ``?owner=<id>``.

        MRY5 — ``?lead=<id>`` renvoie TOUTES les touches de CE lead, tous
        statuts et toutes cadences confondus (tri cadence puis ordre) : c'est
        la FRISE de la fiche lead, qui doit montrer le passé autant que le
        futur — `scope` est alors ignoré. La visibilité reste garantie par
        ``get_queryset`` : un lead hors portée renvoie une liste vide, jamais
        un 403 qui confirmerait son existence.

        COCKPIT-CONTRÔLE (30/09/2026) — ``?scope=all`` est la file du cockpit
        (« maintenant » : échéances du jour et en retard PLUS les tâches
        ouvertes), et la réponse porte alors le bloc ``file`` (compteurs
        ``maintenant`` / ``demain`` / ``semaine`` / ``traitees_aujourdhui``,
        ``selectors.file_du_cockpit``) — servi SEULEMENT quand ``scope`` est
        demandé, dans la même portée (et le même ``owner``) que la liste."""
        lead_id = request.query_params.get('lead')
        owner = request.query_params.get('owner')
        if lead_id:
            # APRF21 — ``traite_par`` chargé (``traite_par_nom`` par touche).
            qs = (self.get_queryset().filter(lead_id=lead_id)
                  .select_related('lead', 'lead__owner', 'devis',
                                  'traite_par')
                  .order_by('cadence', 'ordre', 'due_date'))
        else:
            from .selectors import relance_etapes_dues
            scope = request.query_params.get('scope', 'today')
            qs = relance_etapes_dues(
                request.user.company, request.user, scope=scope, owner=owner)
        serializer = self.get_serializer(qs, many=True)
        payload = {'count': qs.count(), 'results': serializer.data}
        if not lead_id and 'scope' in request.query_params:
            from .selectors import file_du_cockpit
            payload['file'] = file_du_cockpit(
                request.user.company, request.user, owner=owner)
        return Response(payload)

    @extend_schema(parameters=[sd.param('date_debut', OpenApiTypes.DATE, required=True), sd.param('date_fin', OpenApiTypes.DATE, required=True), sd.P_OWNER, sd.param('statut')], responses=sd.OBJ)
    @action(detail=False, methods=['get'], url_path='suivi',
            permission_classes=[IsAnyRole])
    def suivi(self, request):
        """MRY30 — « Suivi des relances » : TOUTES les touches d'une PÉRIODE,
        tous statuts (forme `relance_etapes_suivi`).

        ``?date_debut=&date_fin=`` (AAAA-MM-JJ, OBLIGATOIRES, 62 jours d'écart
        au plus) ``&owner=<id>&statut=a_faire|fait|sautee|annulee|en_retard``.

        CKP1 — ``annulee`` (« Annulée (moteur) ») s'AJOUTE aux statuts filtrables
        et au ``resume`` : une touche retirée du plan par le moteur (cadence
        arrêtée parce que le client a répondu) n'est PAS un saut humain, et la
        vue d'adhérence ne doit jamais la compter comme un manquement. Aucune
        clé du ``resume`` n'est retirée — l'écran existant continue de lire
        ``sautee`` à l'identique.

        Une action DISTINCTE de ``list`` — et non un paramètre de plus — parce
        que les deux répondent à deux questions opposées : ``list`` sert la
        FILE (ce qu'il reste à faire aujourd'hui, statut `a_faire` seulement)
        et ``suivi`` sert le JOURNAL (ce qui a été fait, sauté ou oublié sur
        une période). Mélanger les deux dans une même route obligeait l'écran
        à deviner lequel des deux contrats il venait de recevoir.

        ``resume`` est compté CÔTÉ SERVEUR sur la période, jamais recompté à
        l'écran depuis ``results`` (qui, lui, est filtré par ``statut``)."""
        from django.utils.dateparse import parse_date

        from .selectors import (
            SUIVI_JOURS_MAX, STATUTS_SUIVI, relance_etapes_periode)

        bornes = {}
        for nom in ('date_debut', 'date_fin'):
            brut = (request.query_params.get(nom) or '').strip()
            if not brut:
                return Response(
                    {nom: 'Borne obligatoire (AAAA-MM-JJ attendu).'},
                    status=status.HTTP_400_BAD_REQUEST)
            try:
                valeur = parse_date(brut)
            except ValueError:
                valeur = None
            if valeur is None:
                return Response(
                    {nom: 'Date invalide (AAAA-MM-JJ attendu).'},
                    status=status.HTTP_400_BAD_REQUEST)
            bornes[nom] = valeur
        date_debut, date_fin = bornes['date_debut'], bornes['date_fin']
        if date_fin < date_debut:
            return Response(
                {'date_fin': 'La borne de fin précède la borne de début.'},
                status=status.HTTP_400_BAD_REQUEST)
        if (date_fin - date_debut).days > SUIVI_JOURS_MAX:
            # Au-delà, ce n'est plus une période de travail mais un export :
            # un refus net vaut mieux qu'un écran qui met dix secondes.
            return Response(
                {'date_fin': f'Période trop longue ({SUIVI_JOURS_MAX} jours '
                             'au plus).'},
                status=status.HTTP_400_BAD_REQUEST)
        statut = (request.query_params.get('statut') or '').strip()
        if statut and statut not in STATUTS_SUIVI:
            return Response(
                {'statut': 'Statut inconnu. Choisir parmi : '
                           + ', '.join(STATUTS_SUIVI) + '.'},
                status=status.HTTP_400_BAD_REQUEST)
        owner = (request.query_params.get('owner') or '').strip()
        if owner and not owner.isdigit():
            # Un identifiant non numérique atteindrait le `filter()` et y
            # lèverait une ValueError — un 500 pour une faute de frappe.
            return Response(
                {'owner': 'Identifiant de responsable invalide.'},
                status=status.HTTP_400_BAD_REQUEST)

        etapes, resume = relance_etapes_periode(
            request.user.company, request.user,
            date_debut=date_debut, date_fin=date_fin,
            owner=owner or None, statut=statut or None)
        lignes = self.get_serializer(etapes, many=True).data
        return Response({
            'count': len(lignes),
            'date_debut': date_debut.isoformat(),
            'date_fin': date_fin.isoformat(),
            'resume': resume,
            'results': lignes,
        })

    @extend_schema(parameters=[sd.P_LEAD_REQ], responses=inline_serializer('CrmJournalRelance', {
        'lead': serializers.IntegerField(),
        'etat': serializers.DictField(),
        'lignes': serializers.ListField(child=serializers.DictField()),
    }))
    @action(detail=False, methods=['get'], url_path='journal',
            permission_classes=[IsAnyRole])
    def journal(self, request):
        """RLC2 — le journal « ce qui s'est passé » du plan de relance d'un lead,
        et son état courant en une phrase (forme `journal_relance`).

        ``?lead=<id>`` OBLIGATOIRE. LECTURE PURE : le sélecteur
        ``journal_relance`` fusionne les touches traitées et la tranche utile du
        chatter — aucune écriture, aucun nouveau journal.

        404 « Lead inconnu. » quand le lead n'existe pas OU sort de la portée de
        visibilité du demandeur : les deux cas sont indistinguables exprès — un
        message différent servirait d'oracle d'existence."""
        from .selectors import journal_relance

        brut = (request.query_params.get('lead') or '').strip()
        if not brut.isdigit():
            return Response(
                {'lead': 'Identifiant de lead obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        journal = journal_relance(
            request.user.company, request.user, int(brut))
        if journal is None:
            return Response({'detail': 'Lead inconnu.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(journal)

    @extend_schema(parameters=[sd.param('jours', OpenApiTypes.INT, required=True)], responses=inline_serializer('CrmCadencesEchues', {
        'count': serializers.IntegerField(),
        'jours': serializers.IntegerField(),
        'results': serializers.ListField(child=serializers.DictField()),
    }))
    @action(detail=False, methods=['get'], url_path='cadences-echues',
            permission_classes=[IsAnyRole])
    def cadences_echues(self, request):
        """CAD99 — la liste « cadences échues à clore » (forme
        `cadences_echues`), moitié écran de CAD75.

        ``?jours=`` OBLIGATOIRE : le seuil de retard, en jours, que l'écran
        AFFICHE — ni la tâche ni aucun réglage société ne porte ce nombre, le
        sélecteur ``cadences_echues_a_clore`` refuse donc d'en inventer un.
        Refus 400 ``{"jours": …}`` qui nomme le champ.

        LECTURE PURE — garde-fou de la tâche : rien n'est clos, rien n'est
        écrit ; la clôture reste une décision humaine, prise sur la fiche. La
        portée de visibilité du demandeur s'applique (sélecteur)."""
        from .selectors import cadences_echues_a_clore

        brut = (request.query_params.get('jours') or '').strip()
        if not brut.isdigit():
            # Levée : la forme versionnée reste celle de la réponse.
            raise DRFValidationError({'jours': (
                '« Retard de plus de (jours) » : un nombre entier de jours '
                '(0 ou plus) est obligatoire.')})
        jours = int(brut)
        lignes = cadences_echues_a_clore(
            request.user.company, request.user, jours=jours)
        return Response({'count': len(lignes), 'jours': jours,
                         'results': lignes})

    @extend_schema(parameters=[sd.P_JOURS], responses=inline_serializer('CrmKpiAdherence', {
        'periode_jours': serializers.IntegerField(),
        'a_lheure_pct': serializers.FloatField(allow_null=True),
        'touches_faites': serializers.IntegerField(),
        'touches_en_retard_ouvertes': serializers.IntegerField(),
        'sautees_humaines': serializers.IntegerField(),
        'annulees_moteur': serializers.IntegerField(),
        'vitesse_premier_contact': serializers.DictField(),
        'tendance_a_lheure': serializers.ListField(
            child=serializers.DictField()),
        'par_etape': serializers.ListField(child=serializers.DictField()),
        'leads_sans_touche': serializers.ListField(
            child=serializers.DictField()),
        # CAD35 — les périodes d'absence déclarées de la fenêtre.
        'absences_declarees': serializers.ListField(
            child=serializers.DictField()),
        'conversion_par_stage': serializers.ListField(
            child=serializers.DictField()),
    }))
    @action(detail=False, methods=['get'], url_path='kpi-adherence',
            permission_classes=[IsAnyRole])
    def kpi_adherence(self, request):
        """CKP3 — la vue ADHÉRENCE du cockpit CRM (forme `kpi_adherence`).

        ``?jours=`` (30 par défaut, 1-365). Les étapes du protocole sont-elles
        suivies, à l'heure, et OÙ décrochent-elles ?

        LECTURE OUVERTE À TOUS LES RÔLES — décision fondateur du 10/09/2026 :
        transparence totale, Meryem voit exactement ce que Reda voit ; seule
        la mise en page diffère à l'écran (elle = sa file, lui = la vue
        stratégique). La portée de visibilité du demandeur s'applique quand
        même (``scope_queryset`` via le lead) : la transparence ne perce pas
        le cloisonnement, elle supprime le tableau caché."""
        from .selectors import kpi_adherence

        # « Normaliser plutôt que refuser » (règle fondateur 08/09) : un
        # ``jours`` illisible retombe sur 30, un excès est borné à 1-365 —
        # un tableau de bord ne renvoie jamais une erreur pour un paramètre
        # d'affichage.
        brut = (request.query_params.get('jours') or '').strip()
        jours = int(brut) if brut.isdigit() else 30
        jours = min(max(jours, 1), 365)
        return Response(
            kpi_adherence(request.user.company, request.user, jours))

    @extend_schema(responses=inline_serializer('CrmMesStatsRelance', {
        'a_faire_maintenant': serializers.IntegerField(),
        'en_retard': serializers.IntegerField(),
        'a_lheure_7j_pct': serializers.FloatField(allow_null=True),
        'cadences_completees_14j': serializers.IntegerField(),
        'serie_jours_sans_retard': serializers.IntegerField(),
    }))
    @action(detail=False, methods=['get'], url_path='mes-stats',
            permission_classes=[IsAnyRole])
    def mes_stats(self, request):
        """CKP3 — les tuiles PERSONNELLES du commercial (forme
        `mes_stats_relance`).

        Sa file du moment, ses retards, son à-l'heure 7 jours, ses cadences
        menées à terme, sa série de jours sans retard. Actionnables, JAMAIS
        comparatives : aucune donnée d'un autre commercial n'y entre, et rien
        n'est servi sous forme de classement. Périmètre : les leads dont le
        demandeur est le RESPONSABLE."""
        from .selectors import mes_stats_relance

        return Response(
            mes_stats_relance(request.user.company, request.user))

    @extend_schema(responses=inline_serializer('CrmChaineCommerciale', {
        'joints_sans_devis': serializers.DictField(),
        'visites_a_venir': serializers.DictField(),
        'devis_a_preparer': serializers.DictField(),
        'limite': serializers.IntegerField(),
    }))
    @action(detail=False, methods=['get'], url_path='chaine-commerciale',
            permission_classes=[IsAnyRole])
    def chaine_commerciale(self, request):
        """Les trois compteurs de la chaîne commerciale du cockpit (forme
        ``chaine_commerciale`` — décision fondateur du 25/09/2026) : joints
        sans devis, visites à venir, devis à préparer, chacun avec ses
        dossiers les plus urgents et son total. LECTURE PURE, même portée que
        la file du jour ; jamais un classement entre commerciaux."""
        from .selectors import chaine_commerciale

        return Response(
            chaine_commerciale(request.user, request.user.company))

    @extend_schema(parameters=[sd.param('jours', OpenApiTypes.INT, enum=[7, 14, 30]), sd.P_OWNER, sd.param('segment')], responses=inline_serializer('CrmControleSuivi', {
        'periode_jours': serializers.IntegerField(),
        'owner': serializers.IntegerField(allow_null=True),
        'commerciaux': serializers.ListField(child=serializers.DictField()),
        'seuils': serializers.DictField(),
        'verdict': serializers.DictField(),
        'jours': serializers.ListField(child=serializers.DictField()),
        'exceptions': serializers.DictField(),
        'par_type': serializers.ListField(child=serializers.DictField()),
        'premier_contact': serializers.DictField(),
        'resultats': serializers.DictField(),
    }))
    @action(detail=False, methods=['get'], url_path='controle',
            permission_classes=[IsAnyRole])
    def controle(self, request):
        """COCKPIT-CONTRÔLE (fondateur, 30/09/2026) — le bloc « Contrôle du
        suivi » du cockpit (forme ``controle_suivi``) : verdict, frise d'un
        jour par case, exceptions de l'instant, détail par type d'étape,
        premier contact, résultats. ``?jours=7|14|30`` (14 par défaut),
        ``?owner=<id>`` (un responsable de la portée, facultatif).

        LECTURE OUVERTE À TOUS LES RÔLES (même garde que ``kpi_adherence``,
        transparence CKP3) ; seule la portée de visibilité (``scope_queryset``
        via le lead) borne ce qui est lu. Refus 400 ``{"erreurs": {champ:
        message}}`` qui NOMME le champ : ``jours`` hors 7/14/30, ``owner``
        inconnu ou hors portée — levés (``DRFValidationError``) pour que la
        forme versionnée reste celle de la réponse."""
        from .controle_suivi import (
            controle_suivi, parametre_segment, parametres_controle,
        )

        jours, owner, erreurs = parametres_controle(
            request.user.company, request.user,
            request.query_params.get('jours'),
            request.query_params.get('owner'))
        # AGR542 — ``?segment=`` (type du lead, ``non_renseigne`` = vide) ;
        # une valeur inconnue est refusée en nommant ``segment``.
        segment, erreur_segment = parametre_segment(
            request.query_params.get('segment'))
        if erreur_segment:
            erreurs = {**erreurs, 'segment': erreur_segment}
        if erreurs:
            raise DRFValidationError({'erreurs': erreurs})
        return Response(controle_suivi(
            request.user.company, request.user, jours=jours, owner=owner,
            segment=segment))

    @_geste_atomique
    def _marquer(self, request, statut):
        etape = self.get_object()
        if etape.statut != RelanceEtape.Statut.A_FAIRE:
            # SUIVI E8 — jamais un second « Fait » sur une touche close.
            return Response(
                {'erreurs': {'etape': MESSAGE_ETAPE_DEJA_TRAITEE}},
                status=status.HTTP_400_BAD_REQUEST)
        # COCKPIT-CONTRÔLE B4 — « Sauter » est refusé sur une TÂCHE, AVANT
        # toute écriture (« déjà traitée » prime, SUIVI E8). La table du
        # parcours ne le propose pas ; le serveur le tient désormais aussi.
        from .suite_touche import est_tache
        if statut == RelanceEtape.Statut.SAUTEE and est_tache(etape):
            return Response(
                {'erreurs': {'etape': MESSAGE_TACHE_NON_SAUTABLE}},
                status=status.HTTP_400_BAD_REQUEST)
        note = (request.data.get('note') or '').strip()
        outcome = (request.data.get('outcome') or '').strip()
        body = (request.data.get('body') or '').strip()
        from .models import LeadActivity as _LeadActivity
        if outcome and outcome not in {
                k for k, _ in _LeadActivity.OUTCOMES}:
            return Response(
                {'outcome': 'Issue inconnue.'},
                status=status.HTTP_400_BAD_REQUEST)
        # SUIVI E2 (30/09/2026) — « refus » sur « Décider la suite » re-posait
        # la même étape à l'infini (le filet du récepteur MRY9 ne connaît pas
        # la clé de la touche close : la ceinture anti-tapis-roulant ne
        # jouait pas). La décision se prend par « Perdu » (avec son motif) ou
        # par une relance ultérieure.
        from .cadence_config import CLE_DECIDER_SUITE, est_etape
        if outcome == 'refuse' and est_etape(etape, CLE_DECIDER_SUITE):
            return Response(
                {'erreurs': {'outcome': MESSAGE_REFUS_SUR_DECIDER_SUITE}},
                status=status.HTTP_400_BAD_REQUEST)
        # CAD10 — le motif de refus, FACULTATIF : seulement avec l'issue
        # « refus », seulement un motif de la liste paramétrée, et journalisé
        # sur la ligne de chatter de la touche (jamais sur `motif_perte` :
        # « perdu » reste une décision humaine, MRY22).
        motif_refus = (request.data.get('motif_refus') or '').strip()
        if motif_refus:
            from .cadence_reponses import mention_motif_refus
            from .leads_socle import motif_refus_valide
            if outcome != 'refuse':
                return Response(
                    {'erreurs': {'motif_refus': (
                        '« Motif du refus » ne vaut qu’avec la réponse '
                        '« Refus ».')}},
                    status=status.HTTP_400_BAD_REQUEST)
            nom = motif_refus_valide(etape.company, motif_refus)
            if nom is None:
                return Response(
                    {'erreurs': {'motif_refus': (
                        f'« Motif du refus » : « {motif_refus} » n’est pas '
                        'un motif de la liste (Paramètres → CRM).')}},
                    status=status.HTTP_400_BAD_REQUEST)
            body = f'{body} {mention_motif_refus(nom)}'.strip()
        # CAD11 — « Numéro invalide / a bloqué » : la PROPOSITION « perdu,
        # motif junk » acceptée en un clic. Seulement sur une touche close
        # « non joint » (le patron Répondeur/Occupé), seulement avec un motif
        # JUNK de la liste de la société — le clic humain décide (MRY22).
        perdu_junk = (request.data.get('perdu_junk') or '').strip()
        motif_junk = None
        if perdu_junk:
            from .cadence_reponses import motif_junk_valide
            if statut != RelanceEtape.Statut.FAIT or outcome != 'non_joint':
                return Response(
                    {'erreurs': {'perdu_junk': (
                        '« Marquer perdu (junk) » ne vaut qu’avec une touche '
                        'faite « Numéro invalide » ou « A bloqué ».')}},
                    status=status.HTTP_400_BAD_REQUEST)
            motif_junk = motif_junk_valide(etape.company, perdu_junk)
            if motif_junk is None:
                return Response(
                    {'erreurs': {'perdu_junk': (
                        f'« Marquer perdu (junk) » : « {perdu_junk} » n’est '
                        'pas un motif junk de la liste (Paramètres → CRM).')}},
                    status=status.HTTP_400_BAD_REQUEST)
        # VISITE-CADENCE — « Visite acceptée » vaut sur TOUTE touche : prise
        # de contact, réveil, étape du filet, suivi de proposition. Décision
        # fondateur du 24/09/2026 (« après l'appel il n'y a plus rien à faire,
        # sauf organiser la visite ») : la visite peut se caler dès la prise
        # de contact. L'ancienne garde (revue Fable 15/09) refusait l'issue
        # hors du suivi de proposition, si bien que la file ne proposait
        # jamais la visite après un appel de prise de contact — alors que la
        # doctrine CAD123 AVERTIT d'une visite sans devis, elle ne la BLOQUE
        # pas. La suite est décidée par le moteur, pas ici
        # (``CADENCES_ARRETEES_PAR_ISSUE`` + filet « planifier la visite »).
        # CKP2 — l'ISSUE est OBLIGATOIRE pour clore un APPEL « fait » : c'est
        # elle, et elle seule, qui programme la suite du protocole (cadence
        # réactive) et qui arrête la cadence quand le client a répondu. Un
        # appel coché sans issue laissait le dossier sans prochain geste et
        # sans trace de ce qui s'était dit. Les autres canaux
        # (WhatsApp/e-mail/visite) gardent l'issue FACULTATIVE : envoyer un
        # message n'a pas d'issue tant que personne n'a répondu.
        # EXCEPTION filets « generique » (fondateur 15/09/2026, capture à
        # l'appui) : « Fait — passer à la suite » sur un filet part SANS
        # issue PAR CONSTRUCTION — c'est CE clic qui vaut « devis parti »
        # (QJ-FUNNEL) ou clôt l'étape posée par le moteur, et le panneau ne
        # propose volontairement pas Joint/Non joint. Exiger ici une issue
        # que l'écran n'offre pas était un mur sans porte.
        # L'erreur NOMME le champ fautif (règle fondateur 08/09/2026) —
        # jamais un « non enregistré » générique.
        # EXCEPTION CAD45 — la touche d'appel TRAITÉE PAR ÉCRIT : le message de
        # cette touche a été ouvert depuis l'ERP (trace RLC3). Aucun appel n'a
        # eu lieu, exiger « Joint / Non joint » demanderait l'issue d'un appel
        # qui n'existe pas. L'issue reste obligatoire sur un appel réellement
        # passé — c'est elle qui alimente l'adhérence CKP3.
        # SUIVI E13 (30/09/2026) — EXCEPTION « Préparer le devis modifié » :
        # c'est une TÂCHE (comme l'étape devis), son « Fait » sans issue vaut
        # « devis modifié envoyé ».
        from .cadence_config import CLE_DEVIS_MODIFIE
        if (statut == RelanceEtape.Statut.FAIT
                and etape.canal == RelanceEtape.Canal.APPEL
                and etape.cadence != 'generique'
                and not outcome
                and not est_etape(etape, CLE_DEVIS_MODIFIE)
                and not _message_ouvert_sur_touche(etape)):
            return Response(
                {'erreurs': {'outcome': MESSAGE_ISSUE_APPEL_OBLIGATOIRE}},
                status=status.HTTP_400_BAD_REQUEST)
        # MRY10 — « rappelez-moi jeudi » saisi DEPUIS la touche : elle est
        # reportée, plutôt que marquée faite et oubliée.
        rappel_le = (request.data.get('rappel_le') or '').strip()
        quand = None
        if rappel_le:
            quand = _parse_rappel(
                rappel_le, (request.data.get('rappel_heure') or '').strip())
            if quand is None:
                return Response(
                    {'rappel_le': 'Date invalide (AAAA-MM-JJ attendu, '
                                  'heure HH:MM optionnelle).'},
                    status=status.HTTP_400_BAD_REQUEST)
            # CAD27 — jamais un rappel dans le passé (le champ est nommé).
            refus = _refus_date_passee(quand, 'Rappeler le')
            if refus:
                return Response({'erreurs': {'rappel_le': refus}},
                                status=status.HTTP_400_BAD_REQUEST)
        from .cadence_config import CLE_MESSAGE_CRENEAU, CLE_PLANIFIER
        from .cadence_touche import marquer_etape_relance
        from .cadence_plan import est_etape_de_filet, reporter_prochaine_touche
        from .cadence_reperes import est_etape_de_visite
        from .cadence_reponses import (
            est_derniere_touche_de_contact,
            est_derniere_touche_du_suivi,
            est_dernier_reveil,
            repondre_planifier_sans_reponse,
            repondre_rappel_convenu,
        )
        # SUIVI E12 (30/09/2026) — « Planifier la visite » sans réponse :
        # l'appel compte et l'étape est REPOSÉE pour demain — jamais
        # « Préparer et envoyer le devis » (le client a accepté la visite).
        if (statut == RelanceEtape.Statut.FAIT and outcome == 'non_joint'
                and motif_junk is None and est_etape(etape, CLE_PLANIFIER)):
            etape, _nouvelle = repondre_planifier_sans_reponse(
                etape, request.user, note=note, body=body)
            if quand is not None:
                # COCKPIT-CONTRÔLE — la date PLACE l'étape que la réponse
                # vient de reposer : ce n'est pas un report (rien de compté).
                reporter_prochaine_touche(etape.lead, request.user, quand,
                                          compter_report=False)
            return self._reponse_fait(etape)
        # SUIVI E10 (30/09/2026) — « Créneau convenu le… » sur l'étape
        # « Message — proposer un créneau pour l'appel » : le créneau convenu
        # devient un APPEL. L'étape message est close et « Rappeler le
        # client — rappel convenu » est posée à la date ET à l'heure
        # convenues (avant, l'étape message était déplacée telle quelle).
        # SUIVI I7 (30/09/2026) — sur les trois branches ci-dessous comme
        # partout : ``prochaine_touche`` est TOUJOURS la plus proche touche
        # OUVERTE du lead (``_reponse_fait``), jamais l'étape que la branche
        # vient de poser ou de déplacer — une autre touche peut tomber avant.
        if (statut == RelanceEtape.Statut.FAIT and outcome == 'rappel'
                and quand is not None
                and est_etape(etape, CLE_MESSAGE_CRENEAU)):
            etape, _rappel = repondre_rappel_convenu(
                etape, request.user, quand, note=note, body=body)
            return self._reponse_fait(etape)
        # SUIVI E17 (30/09/2026) — « À rappeler le… » sur le DERNIER réveil :
        # aucun réveil suivant ne pouvait porter la date, elle était perdue
        # (le dossier restait au Froid sans rien). Le dossier sort du Froid et
        # « Rappeler le client — rappel convenu » est posée à la date et à
        # l'heure choisies.
        if (statut == RelanceEtape.Statut.FAIT and outcome == 'rappel'
                and quand is not None and est_dernier_reveil(etape)):
            etape, _rappel = repondre_rappel_convenu(
                etape, request.user, quand, note=note, body=body,
                sortir_du_froid=True)
            return self._reponse_fait(etape)
        # SUIVI E23 (décision fondateur du 30/09/2026) — « À rappeler le… »
        # sur la DERNIÈRE touche de la prise de contact (appel ou message) :
        # aucune touche suivante ne peut porter la date, et le filet posait
        # « Préparer et envoyer le devis » à la date choisie. La touche est
        # close « à rappeler » et l'APPEL « Rappeler le client — rappel
        # convenu » est posé à la date ET à l'heure convenues, recalées sur
        # la fenêtre d'appel ; le dossier garde son étape.
        # SUIVI E24 — la « deuxième affaire » (un client acquis qui revient,
        # rangée par la table sous les mêmes types) suit la même règle
        # (``est_derniere_touche_de_contact`` lit les deux cadences).
        # SUIVI E25 — la DERNIÈRE touche du suivi de proposition aussi : plus
        # jamais « Préparer et envoyer le devis » (déjà parti) à la date.
        if (statut == RelanceEtape.Statut.FAIT and outcome == 'rappel'
                and quand is not None
                and (est_derniere_touche_de_contact(etape)
                     or est_derniere_touche_du_suivi(etape))):
            etape, _rappel = repondre_rappel_convenu(
                etape, request.user, quand, note=note, body=body)
            return self._reponse_fait(etape)
        # CAD3 — « À rappeler le… » sur une étape de FILET la REPORTE, elle ne
        # la consomme pas. L'écran promet « L'étape est déplacée à la date
        # choisie » ; la clore rendait la main au filet, qui posait une AUTRE
        # étape, renommée « Décider la suite — perdu (motif) ou relance
        # ultérieure » par la ceinture anti-tapis-roulant, avant que la date
        # choisie ne lui soit appliquée. Un client qui dit « rappelez-moi la
        # semaine prochaine » n'a rien arbitré. Même chemin que le bouton
        # « Reporter » (action `reporter` plus bas) : la touche garde son
        # identité, sa cadence et son libellé.
        # SUIVI E3 (30/09/2026) — même branche pour une étape de VISITE
        # (planifier, débrief, devis modifié) : close, elle laissait le filet
        # poser « Préparer et envoyer le devis » à sa place, et c'était CETTE
        # étape-là qui était déplacée — la visite à planifier ou le débrief
        # disparaissait de la file.
        if (statut == RelanceEtape.Statut.FAIT and outcome == 'rappel'
                and quand is not None
                and (est_etape_de_filet(etape)
                     or est_etape_de_visite(etape))):
            reportee = reporter_prochaine_touche(
                etape.lead, request.user, quand, etape=etape)
            if reportee is not None:
                etape = reportee
                if note:
                    etape.note = note
                    etape.save(update_fields=['note'])
                # SUIVI I7 — la plus proche touche ouverte du lead, pas
                # forcément l'étape déplacée.
                return self._reponse_fait(etape)
        # CAD11 — un lead qu'on marque perdu n'a pas de suite : ni barreau
        # suivant, ni clôture au froid avec réveils (``suite=False``).
        etape = marquer_etape_relance(
            etape, request.user, statut, note=note, outcome=outcome,
            body=body, suite=motif_junk is None)
        if motif_junk is not None:
            from .cadence_reponses import marquer_lead_perdu_junk
            marquer_lead_perdu_junk(etape.lead, request.user, motif_junk)
        if quand is not None:
            # COCKPIT-CONTRÔLE — la touche est CLOSE ; la date place la
            # touche qui lui succède (« touche suivante à la date ») : un
            # placement, jamais un report compté (seul un geste qui GARDE
            # l'étape en est un — branche CAD3/E3 plus haut, action
            # ``reporter``).
            reporter_prochaine_touche(etape.lead, request.user, quand,
                                      compter_report=False)
        return self._reponse_fait(etape)

    def _reponse_fait(self, etape):
        """La réponse d'un « Fait » : la touche (forme `relance_etape_v2`) et
        la PROCHAINE étape à faire du LEAD, toutes cadences confondues.

        CKP2/CKP4 — c'est elle (et jamais un calcul d'écran) qui alimente le
        message « prochain appel programmé le … ». ``prochaine_touche`` vaut
        ``None`` quand plus rien n'est ouvert sur le lead.

        Relevé du 25/09/2026 (décision fondateur du 24/09) : la suite d'une
        touche vit souvent dans une AUTRE cadence que la sienne — « visite
        acceptée » sur un appel de prise de contact pose « Planifier la visite
        technique convenue » (cadence du suivi), « joint » pose l'étape devis
        (cadence générique). Lue par cadence, la réponse annonçait « rien »
        alors qu'une étape du jour attendait. C'est désormais la MÊME lecture
        que ``Lead.relance_date`` (``services._prochaine_touche_a_faire``).

        SUIVI E9 — elle NOMME l'étape (``libelle``, ``cle``) :
        ``_prochaine_touche_publique``."""
        from .cadence_plan import _prochaine_touche_a_faire

        data = self.get_serializer(etape).data
        data['prochaine_touche'] = _prochaine_touche_publique(
            _prochaine_touche_a_faire(etape.lead))
        return Response(data)

    @_geste_atomique
    def _repondre(self, request, reponse):
        """CAD-A — une RÉPONSE du client saisie sur la touche (``reponse``).

        La clé est validée par le SERVEUR (``services.REPONSES_TOUCHE``) :
        l'issue enregistrée en est dérivée ici, jamais envoyée par l'écran.
        Refus en 400 ``{"erreurs": {"reponse": …}}`` — le message nomme la
        réponse et dit où elle vaut."""
        from .cadence_reponses import (
            REPONSE_DECISION_FAMILLE,
            REPONSE_DECISION_PROPRIETAIRE,
            REPONSE_ATTENTE_ACCORD,
            REPONSE_DEVIS_MODIFIE,
            REPONSE_JOINT_TELEPHONE,
            REPONSE_NE_PLUS_CONTACTER,
            REPONSE_PERDU,
            REPONSE_PLUS_TARD,
            REPONSE_QUESTION_PRIX,
            REPONSE_VISITE_ABANDONNEE,
            refus_motif_perte,
            refus_raison_attente,
            refus_reponse_touche,
            repondre_attente_accord,
            repondre_decision_a_plusieurs,
            repondre_devis_modifie,
            repondre_joint_telephone,
            repondre_ne_plus_contacter,
            repondre_perdu,
            repondre_plus_tard,
            repondre_question_prix,
            repondre_visite_abandonnee,
            reponse_touche,
        )

        etape = self.get_object()
        if etape.statut != RelanceEtape.Statut.A_FAIRE:
            # SUIVI E8 — « déjà traitée » PRIME sur tout autre refus, sous le
            # même champ que pour « Fait » / « Sauter » / « Reporter ».
            return Response(
                {'erreurs': {'etape': MESSAGE_ETAPE_DEJA_TRAITEE}},
                status=status.HTTP_400_BAD_REQUEST)
        refus = refus_reponse_touche(etape, reponse)
        if refus:
            return Response({'erreurs': {'reponse': refus}},
                            status=status.HTTP_400_BAD_REQUEST)
        spec = reponse_touche(reponse)
        note = (request.data.get('note') or '').strip()
        body = (request.data.get('body') or '').strip()
        # SUIVI E2 — « Perdu » exige un motif ACTIF de la société : absent ou
        # hors liste, le refus NOMME le champ, avant toute écriture.
        motif_perte = None
        if spec.get('motif_perte_requis'):
            motif_perte, refus = refus_motif_perte(
                etape.company, request.data.get('motif_perte'))
            if refus:
                return Response({'erreurs': {'motif_perte': refus}},
                                status=status.HTTP_400_BAD_REQUEST)
        # La date convenue avec le client (« Rappeler le »), quand la réponse
        # en exige une — même lecture, mêmes refus nommés que « À rappeler
        # le… » (format, puis CAD27 : jamais dans le passé).
        quand = None
        rappel_le = (request.data.get('rappel_le') or '').strip()
        if spec.get('date_requise') and not rappel_le:
            return Response(
                {'erreurs': {'rappel_le': (
                    '« Rappeler le » : la date convenue avec le client est '
                    f'obligatoire pour « {spec["libelle"]} ».')}},
                status=status.HTTP_400_BAD_REQUEST)
        # CIQ508 — la RAISON de l'attente (liste fermée) est obligatoire :
        # absente ou inconnue, le refus NOMME le champ et LISTE les valeurs.
        raison_attente = (request.data.get('raison_attente') or '').strip()
        if spec.get('raison_requise'):
            refus = refus_raison_attente(raison_attente)
            if refus:
                return Response({'erreurs': {'raison_attente': refus}},
                                status=status.HTTP_400_BAD_REQUEST)
        if rappel_le:
            quand = _parse_rappel(
                rappel_le, (request.data.get('rappel_heure') or '').strip())
            if quand is None:
                return Response(
                    {'erreurs': {'rappel_le': (
                        '« Rappeler le » : date invalide (AAAA-MM-JJ '
                        'attendu, heure HH:MM optionnelle).')}},
                    status=status.HTTP_400_BAD_REQUEST)
            refus = _refus_date_passee(quand, 'Rappeler le')
            if refus:
                return Response({'erreurs': {'rappel_le': refus}},
                                status=status.HTTP_400_BAD_REQUEST)
        if reponse == REPONSE_NE_PLUS_CONTACTER:
            etape = repondre_ne_plus_contacter(
                etape, request.user, note=note, body=body)
        elif reponse == REPONSE_PLUS_TARD:
            etape = repondre_plus_tard(
                etape, request.user, quand, note=note, body=body)
        elif reponse == REPONSE_ATTENTE_ACCORD:
            # AGR520 — étiquette + la veille de « Plus tard » ; CIQ508 — la
            # raison typée (étiquette, historique, note du réveil daté).
            etape = repondre_attente_accord(
                etape, request.user, quand, raison=raison_attente,
                note=note, body=body)
        elif reponse == REPONSE_QUESTION_PRIX:
            etape = repondre_question_prix(
                etape, request.user, note=note, body=body)
        elif reponse == REPONSE_DEVIS_MODIFIE:
            etape = repondre_devis_modifie(
                etape, request.user, note=note, body=body)
        elif reponse in (REPONSE_DECISION_FAMILLE,
                         REPONSE_DECISION_PROPRIETAIRE):
            etape = repondre_decision_a_plusieurs(
                etape, request.user, reponse, note=note, body=body)
        elif reponse == REPONSE_PERDU:
            etape = repondre_perdu(
                etape, request.user, motif_perte, note=note, body=body)
        elif reponse == REPONSE_VISITE_ABANDONNEE:
            etape = repondre_visite_abandonnee(
                etape, request.user, note=note, body=body)
        elif reponse == REPONSE_JOINT_TELEPHONE:
            # SUIVI E16 — un APPEL abouti sur une touche message.
            etape = repondre_joint_telephone(
                etape, request.user, note=note, body=body)
        return self._reponse_fait(etape)

    @extend_schema(request=sd.corps('CrmRelanceFaitRequest', outcome=serializers.CharField(required=False), reponse=serializers.CharField(required=False), langue=serializers.CharField(required=False), note=serializers.CharField(required=False)), responses=RelanceEtapeSerializer)
    @action(detail=True, methods=['post'])
    def fait(self, request, pk=None):
        """Marque cette étape FAITE.

        Corps : ``{note?, outcome?, body?, rappel_le?, rappel_heure?}``.
        L'``outcome`` déclenche les règles d'arrêt de MRY9 (« joint » arrête
        la prise de contact) ; ``rappel_le`` reporte la touche suivante.

        CKP2 — ``outcome`` est OBLIGATOIRE sur une touche de canal ``appel``
        (400 ``{"erreurs": {"outcome": …}}``) : c'est l'issue qui programme le
        geste suivant du protocole. Facultatif sur WhatsApp / e-mail / visite.
        Toute issue autre que « joint »/« intéressé »/« refus » fait naître la
        touche suivante de la cadence — de même qu'un saut humain.

        CAD-A — ``reponse`` (clé de ``services.REPONSES_TOUCHE``, par exemple
        ``ne_plus_contacter``) remplace ``outcome`` : c'est la phrase du
        client, et le serveur en dérive l'issue ET la suite.

        CAD63 — ``langue`` (facultatif, ``fr``/``darija``) : la réponse « ne
        parle que darija » saisie SUR la touche pose ``Lead.langue_preferee``
        une fois pour toutes — seulement si la touche a bien été enregistrée
        (un refus 400 ne change rien). Une langue inconnue est refusée AVANT
        tout, en 400 ``{"erreurs": {"langue": …}}``."""
        from .cadence_messages import definir_langue_preferee, refus_langue_relance
        langue = (request.data.get('langue') or '').strip()
        if langue:
            refus = refus_langue_relance(langue)
            if refus:
                return Response({'erreurs': {'langue': refus}},
                                status=status.HTTP_400_BAD_REQUEST)
        reponse = (request.data.get('reponse') or '').strip()
        if reponse:
            resultat = self._repondre(request, reponse)
        else:
            resultat = self._marquer(request, RelanceEtape.Statut.FAIT)
        if langue and resultat.status_code < 400:
            # Relu par la MÊME portée que l'action (société + visibilité).
            definir_langue_preferee(self.get_object().lead, request.user,
                                    langue)
            resultat.data['lead_langue'] = langue
        if resultat.status_code < 400:
            # CAD178 — compteur BEST-EFFORT du geste « Fait », par famille
            # d'appareil (jamais bloquant, jamais compté sur un refus 400).
            from .mesure_cadence import enregistrer_geste_appareil
            enregistrer_geste_appareil(
                request.user.company, 'fait',
                request.META.get('HTTP_USER_AGENT', ''))
        return resultat

    @extend_schema(request=None, responses=RelanceEtapeSerializer)
    @action(detail=True, methods=['post'])
    def sauter(self, request, pk=None):
        """Marque cette étape de relance SAUTÉE (note optionnelle).

        CKP2 — sauter une touche n'éteint PAS la cadence : la touche suivante
        du protocole est matérialisée, exactement comme sur un « pas de
        réponse ». Sans cela, sauter le message d'identité supprimait les dix
        gestes qui suivent.

        COCKPIT-CONTRÔLE B4 — refusé sur une TÂCHE (400 ``{"erreurs":
        {"etape": …}}``, rien n'est écrit) : une tâche se traite ou se
        reporte, elle ne se saute pas."""
        return self._marquer(request, RelanceEtape.Statut.SAUTEE)

    @extend_schema(request=None, responses=RelanceEtapeSerializer)
    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """RLC1 — Annule une touche « Fait »/« Sautée » traitée par erreur.

        La touche redevient à faire À SON ÉCHÉANCE D'ORIGINE et les effets
        automatiques de son issue sont défaits tant qu'ils le sont encore
        (touches rouvertes par le retrait de l'arrêt de cadence, étape
        programmée supprimée, avance d'étape défaite) — le service
        ``annuler_touche_relance`` porte toute la règle.

        Refus MOTIVÉ en 400 ``{"erreurs": {champ: message}}`` (même forme que
        ``fait``) : passé 24 h, devis parti, dossier parqué au froid, lead
        signé/perdu, étape suivante déjà traitée. Écriture → garde
        ``IsResponsableOrAdmin`` par défaut de ``get_permissions`` (jamais
        listée parmi les lectures)."""
        etape = self.get_object()
        from .cadence_touche import AnnulationToucheRefusee, annuler_touche_relance
        try:
            etape = annuler_touche_relance(etape, request.user)
        except AnnulationToucheRefusee as refus:
            return Response({'erreurs': {refus.champ: refus.message}},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(etape).data)

    @extend_schema(parameters=[sd.P_CLE, sd.P_LANGUE], responses=sd.OBJ)
    @action(detail=True, methods=['get'])
    def message(self, request, pk=None):
        """MRY13 — Le message de CETTE touche, rendu côté serveur.

        Forme `relance_etape_message` (contrat MRY25). LECTURE PURE : rien
        n'est envoyé, rien n'est marqué — l'écran affiche une modale d'aperçu
        et c'est le clic humain qui ouvre WhatsApp (décision D5).

        CAD-A — ``?cle=`` (une de ``services.CLES_MESSAGE_REPONSE``) rend le
        texte de RÉPONSE convenu pour le client de cette touche (l'accusé
        « ne plus contacter », « je vous rappelle plus tard ») : même forme.
        Une autre clé est refusée en 400 nommant le champ ``cle``.

        CAD63 — ``?langue=fr|darija`` rend CE message dans la langue choisie
        à l'aperçu, sans toucher la fiche (le basculeur FR / Darija). Une
        autre valeur est refusée en 400 nommant le champ ``langue``."""
        etape = self.get_object()
        from .cadence_messages import message_pour_etape, refus_langue_relance
        from .cadence_reponses import CLES_MESSAGE_REPONSE
        cle = (request.query_params.get('cle') or '').strip()
        if cle and cle not in CLES_MESSAGE_REPONSE:
            # Levée, jamais un second `return` : la forme du contrat
            # `relance_etape_message` (lue sur les `return` de cette vue par
            # `check_api_shapes.py`) reste celle du rendu, sans `erreurs`.
            raise DRFValidationError({'erreurs': {'cle': (
                f'Texte de réponse inconnu : « {cle} ». Textes disponibles : '
                + ', '.join(CLES_MESSAGE_REPONSE) + '.')}})
        langue = (request.query_params.get('langue') or '').strip()
        if langue and refus_langue_relance(langue):
            raise DRFValidationError(
                {'erreurs': {'langue': refus_langue_relance(langue)}})
        return Response(message_pour_etape(
            etape, request=request, user=request.user, cle=cle or None,
            langue=langue or None))

    @extend_schema(request=sd.corps('CrmRelanceWhatsappRequest', langue=serializers.CharField(required=False)), responses=sd.OBJ)
    @action(detail=True, methods=['post'])
    @_geste_atomique
    def whatsapp(self, request, pk=None):
        """MRY13 — Le CLIC : même rendu, puis le clic est JOURNALISÉ.

        Le POST n'envoie RIEN (décision D5). RELANCE-WA (fondateur 08/09/2026) :
        ouvrir WhatsApp n'avance plus la touche — une activité « WhatsApp
        ouvert » entre dans l'historique, le premier contact est horodaté
        (MRY19) et la touche reste À FAIRE jusqu'à la réponse aux questions
        « Fait ». Refusé (400) si le numéro est inexploitable — prétendre
        avoir contacté quelqu'un qu'on ne peut pas joindre fausserait aussi
        bien la file que le KPI.

        CAD63 — ``langue`` (corps, facultatif) : la langue CHOISIE à l'aperçu,
        pour que le rendu vérifié ici soit celui qui vient d'être ouvert."""
        etape = self.get_object()
        from .cadence_messages import message_pour_etape, refus_langue_relance
        from .cadence_reperes import journaliser_whatsapp_ouvert
        from .leads_premier_contact import marquer_premier_contact
        langue = (request.data.get('langue') or '').strip()
        if langue and refus_langue_relance(langue):
            # Levée (même motif que `message`) : la forme versionnée du
            # contrat reste celle du rendu, sans `erreurs`.
            raise DRFValidationError(
                {'erreurs': {'langue': refus_langue_relance(langue)}})
        rendu = message_pour_etape(etape, request=request, user=request.user,
                                   langue=langue or None)
        if rendu.get('preuve_manquante'):
            # CAD70 — sans réalisation publiée, le message J4 se réduit à une
            # phrase orpheline : il n'est pas « ouvert ». Levée (même motif
            # que la langue) : la forme versionnée reste celle du rendu.
            from .cadence_messages import REFUS_PREUVE_MANQUANTE
            raise DRFValidationError(
                {'erreurs': {'preuve': REFUS_PREUVE_MANQUANTE}})
        if not rendu.get('wa_url'):
            return Response(
                {'detail': 'Numéro de téléphone invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        journaliser_whatsapp_ouvert(etape, request.user)
        marquer_premier_contact(etape.lead)

        def _audit():
            from apps.audit.models import AuditLog
            from apps.audit.recorder import record
            record(AuditLog.Action.WHATSAPP, instance=etape.lead,
                   detail=f'Message de relance ouvert (touche #{etape.pk})')
        # ACRM22 — AuditLog et mesure CAD178 en BEST-EFFORT (point de
        # sauvegarde propre) : leur panne n'annule pas le geste.
        _best_effort('AuditLog WhatsApp', _audit)
        # CAD178 — compteur BEST-EFFORT du geste « WhatsApp », par famille
        # d'appareil.
        from .mesure_cadence import enregistrer_geste_appareil
        _best_effort(
            'mesure CAD178 WhatsApp', enregistrer_geste_appareil,
            etape.company, 'whatsapp', request.META.get('HTTP_USER_AGENT', ''))
        rendu['etape'] = self.get_serializer(etape).data
        return Response(rendu)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=['post'], url_path='appel-compose')
    def appel_compose(self, request, pk=None):
        """CAD178 — compteur BEST-EFFORT du geste « Appeler ».

        Jusqu'ici, ce bouton cède la main au téléphone (``tel:``, CAD80) sans
        JAMAIS toucher le serveur — CAD86 note qu'aucun des 4 écrans de
        cadence n'a de trace d'usage mobile. Cette action n'écrit RIEN sur la
        touche ni sur le lead, ne journalise aucune activité chatter : elle
        compte seulement le geste, par famille d'appareil, pour
        `mesure_cadence`. Toujours 204, même si le comptage échoue en
        interne (mesure best-effort, jamais bloquante pour l'appel)."""
        etape = self.get_object()
        from .mesure_cadence import enregistrer_geste_appareil
        enregistrer_geste_appareil(
            etape.company, 'appeler', request.META.get('HTTP_USER_AGENT', ''))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=sd.corps('CrmRelanceLangueRequest', langue=serializers.CharField()), responses=RelanceEtapeSerializer)
    @action(detail=True, methods=['post'])
    def langue(self, request, pk=None):
        """CAD63 — enregistre la langue du CLIENT de cette touche, en un geste.

        Corps : ``{langue}`` (``fr`` | ``darija`` — le vocabulaire du champ
        ``Lead.langue_preferee``). C'est la confirmation de l'aperçu : la
        commerciale a basculé le message en darija au téléphone et coche
        « c'est sa langue » — plus besoin de quitter la touche pour ouvrir la
        fiche. Le changement est journalisé comme une édition de la fiche.

        Réponse : la touche, forme `relance_etape_v2` (``lead_langue`` à
        jour). Refus 400 ``{"erreurs": {"langue": …}}`` nommant le champ.
        Écriture → garde ``IsResponsableOrAdmin`` par défaut de
        ``get_permissions``."""
        etape = self.get_object()
        from .cadence_messages import definir_langue_preferee, refus_langue_relance
        langue = (request.data.get('langue') or '').strip()
        refus = (refus_langue_relance(langue) if langue else
                 '« Langue du client » : choisissez la langue à enregistrer.')
        if refus:
            return Response({'erreurs': {'langue': refus}},
                            status=status.HTTP_400_BAD_REQUEST)
        definir_langue_preferee(etape.lead, request.user, langue)
        return Response(self.get_serializer(etape).data)

    @extend_schema(request={'application/json': sd.corps('CrmPieceRecueRequest', type_piece=serializers.CharField(), note=serializers.CharField(required=False)), 'multipart/form-data': sd.corps('CrmPieceRecueMultipartRequest', type_piece=serializers.CharField(), note=serializers.CharField(required=False), fichier=serializers.FileField(required=False))}, responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='piece-recue',
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    @_geste_atomique
    def piece_recue(self, request, pk=None):
        """CAD101 — « pièce reçue » : le client a envoyé sa facture, son
        adresse ou sa localisation (sur WhatsApp, le plus souvent).

        Corps (multipart ou JSON) : ``type_piece`` (``facture`` | ``adresse``
        | ``localisation``, OBLIGATOIRE), ``fichier`` (facultatif — attaché à
        la fiche, magasin ``records.Attachment`` existant), ``note``
        (facultative). UN geste : la touche est close (issue « joint »), le
        document attaché, et l'étape « Préparer et envoyer le devis » posée.

        Réponse : la touche (forme `relance_etape_v2`) + ``prochaine_touche``
        (l'étape « préparer le devis »), comme le « Fait ». Refus 400
        ``{"erreurs": {champ: message}}`` nommant le champ. Jamais déclenché
        par un message ENTRANT : c'est un geste humain. Écriture → garde
        ``IsResponsableOrAdmin`` par défaut de ``get_permissions``."""
        etape = self.get_object()
        from .cadence_reponses import enregistrer_piece_recue, refus_piece_recue
        type_piece = (request.data.get('type_piece') or '').strip()
        refus = refus_piece_recue(etape, type_piece)
        if refus:
            champ, message = refus
            return Response({'erreurs': {champ: message}},
                            status=status.HTTP_400_BAD_REQUEST)
        attachment = None
        fichier = request.FILES.get('fichier')
        if fichier:
            from django.contrib.contenttypes.models import ContentType

            from apps.records.models import Attachment
            from apps.records.storage import store_attachment
            meta, err = store_attachment(fichier, company=etape.company)
            if err:
                return Response(
                    {'erreurs': {'fichier': f'« Pièce jointe » : {err}'}},
                    status=status.HTTP_400_BAD_REQUEST)
            # ACRM22 — supprimée du stockage si le geste échoue ensuite.
            request._acrm22_cles.append(meta.get('file_key'))
            attachment = Attachment.objects.create(
                company=etape.company,
                content_type=ContentType.objects.get(
                    app_label='crm', model='lead'),
                object_id=etape.lead_id, uploaded_by=request.user, **meta)
        etape, _etape_devis = enregistrer_piece_recue(
            etape, request.user, type_piece=type_piece,
            attachment=attachment,
            note=(request.data.get('note') or '').strip())
        # SUIVI I7 — ``prochaine_touche`` = la plus proche touche OUVERTE du
        # lead (d'ordinaire l'étape « préparer le devis » posée ici).
        return self._reponse_fait(etape)

    @extend_schema(request=sd.corps('CrmReporterRequest', mode=serializers.ChoiceField(choices=['decaler', 'veille'], required=False), due_at=serializers.DateTimeField(required=False), rappel_le=serializers.CharField(required=False), rappel_heure=serializers.CharField(required=False)), responses=RelanceEtapeSerializer)
    @action(detail=True, methods=['post'])
    @_geste_atomique
    def reporter(self, request, pk=None):
        """MRY10 — Reporte CETTE touche (et décale les suivantes du même
        delta). Corps : ``{due_at}`` (ISO) ou ``{rappel_le, rappel_heure?}``.

        Décaler la seule touche du jour serait faux : les suivantes se
        téléscoperaient avec elle.

        CAD26 — ``mode`` : ``decaler`` (défaut, le geste historique) ou
        ``veille`` (« Mettre en veille jusqu'au… ») — la cadence se tait
        jusqu'à la date et reprend au MÊME barreau ; au-delà d'un mois, elle
        bascule en réveil daté (``services.mettre_en_veille``). La réponse est
        la touche qui portera la reprise (forme `relance_etape_v2`)."""
        mode = (request.data.get('mode') or '').strip()
        if mode not in ('', 'decaler', 'veille'):
            return Response(
                {'erreurs': {'mode': (
                    f'Geste inconnu : « {mode} ». Choisir « decaler » '
                    '(décaler ce rappel) ou « veille » (mettre en veille '
                    'jusqu’au…).')}},
                status=status.HTTP_400_BAD_REQUEST)
        etape = self.get_object()
        if etape.statut != RelanceEtape.Statut.A_FAIRE:
            # SUIVI E8 — reporter une touche close déplaçait tout le reste
            # du plan (et son ancre) depuis une touche qui n'est plus la
            # prochaine.
            return Response(
                {'erreurs': {'etape': MESSAGE_ETAPE_DEJA_TRAITEE}},
                status=status.HTTP_400_BAD_REQUEST)
        brut = (request.data.get('due_at') or '').strip()
        quand = None
        if brut:
            from django.utils.dateparse import parse_datetime
            try:
                quand = parse_datetime(brut)
            except ValueError:
                quand = None
        elif request.data.get('rappel_le'):
            quand = _parse_rappel(
                (request.data.get('rappel_le') or '').strip(),
                (request.data.get('rappel_heure') or '').strip())
        if quand is None:
            return Response(
                {'due_at': 'Échéance invalide (datetime ISO attendu).'},
                status=status.HTTP_400_BAD_REQUEST)
        # CAD27 — une date de report dans le passé tirait tout le plan en
        # arrière : refusée, le champ fautif NOMMÉ (celui du corps reçu).
        refus = _refus_date_passee(quand, 'Reporter au')
        if refus:
            champ = 'due_at' if brut else 'rappel_le'
            return Response({'erreurs': {champ: refus}},
                            status=status.HTTP_400_BAD_REQUEST)
        # CAD178 — compteur BEST-EFFORT du geste « Reporter », par famille
        # d'appareil (les deux modes, decaler ET veille, comptent). ACRM22 —
        # dans son propre point de sauvegarde.
        from .mesure_cadence import enregistrer_geste_appareil
        _best_effort(
            'mesure CAD178 reporter', enregistrer_geste_appareil,
            etape.company, 'reporter', request.META.get('HTTP_USER_AGENT', ''))
        if mode == 'veille':
            from .cadence_reponses import mettre_en_veille
            reprise = mettre_en_veille(
                etape.lead, request.user, quand, etape=etape)
            if reprise is None:
                # Bascule sans réveil possible : la touche (arrêtée) est
                # rendue telle quelle, jamais une réponse vide.
                etape.refresh_from_db()
                reprise = etape
            return Response(self.get_serializer(reprise).data)
        from .cadence_plan import reporter_prochaine_touche
        etape = reporter_prochaine_touche(
            etape.lead, request.user, quand, etape=etape)
        return Response(self.get_serializer(etape).data)


@extend_schema_view(list=extend_schema(parameters=[sd.P_ARCHIVED_FLAG]))
class MessageTemplateViewSet(CompanyScopedModelViewSet):
    """Modèles de messages CRM (WhatsApp/SMS). Lecture tout rôle, écriture admin.

    La société est toujours posée côté serveur (TenantMixin). Un modèle archivé
    reste accessible en détail mais n'apparaît plus dans la liste par défaut
    (?archived=true pour les voir).
    """
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = MessageTemplate.objects.all()
    serializer_class = MessageTemplateSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'corps']
    ordering_fields = ['nom', 'date_creation']
    ordering = ['nom']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list':
            archived = self.request.query_params.get('archived')
            if archived not in ('1', 'true'):
                qs = qs.filter(archived=False)
        return qs

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'render_template']:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user,
        )

    @extend_schema(request=sd.corps('CrmMessageRenderRequest', lead_id=serializers.IntegerField(required=False), lien=serializers.CharField(required=False), prenom=serializers.CharField(required=False), ville=serializers.CharField(required=False)), responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='render',
            permission_classes=[IsAnyRole])
    def render_template(self, request, pk=None):
        """Applique les variables {prenom}/{ville}/{lien}/{lien_rdv} et
        retourne le texte.

        Corps : {prenom, ville, lien, lead_id} (tous optionnels). XSAL17 —
        ``lead_id`` (scopé société) résout {lien_rdv} en un lien de
        réservation réel ; sans lead_id (ou template sans le placeholder),
        aucun BookingLink n'est créé (no-op — le placeholder disparaît
        simplement s'il est présent sans lead_id fourni).
        """
        tmpl = self.get_object()
        prenom = request.data.get('prenom', '')
        ville = request.data.get('ville', '')
        lien = request.data.get('lien', '')
        lien_rdv = ''
        lead_id = request.data.get('lead_id')
        lead = None
        if lead_id:
            # ACRM8 — le lead est résolu dans la PORTÉE : un lead hors
            # portée (ou inexistant) → 400, aucun lien de réservation créé.
            from .selectors import leads_en_portee
            lead = (leads_en_portee(request.user).filter(pk=lead_id).first()
                    if str(lead_id).isdigit() else None)
            if lead is None:
                # LEVÉ, pas renvoyé : le contrat reste la forme du 200.
                raise DRFValidationError({'lead': ['Lead introuvable.']})
        if lead is not None and '{lien_rdv}' in (tmpl.corps or ''):
            from .visites_rdv import public_booking_url
            try:
                lien_rdv = public_booking_url(lead, request=request)
            except Exception:  # noqa: BLE001 — jamais bloquer l'aperçu
                lien_rdv = ''
        return Response({'texte': tmpl.render(
            prenom=prenom, ville=ville, lien=lien, lien_rdv=lien_rdv)})


def _message_ouvert_sur_touche(etape):
    """CAD45 — le message de CETTE touche a-t-il été ouvert depuis l'ERP ?

    Les boutons « Appeler » et « WhatsApp » sont rendus sur CHAQUE ligne quel
    que soit le canal : le geste est donc déjà libre, et la commerciale écrit
    parfois au lieu d'appeler. L'issue restait pourtant OBLIGATOIRE dès que le
    canal vaut « appel » — elle devait répondre « Joint / Non joint » à propos
    d'un appel qu'elle n'avait pas passé. C'est ce frottement-là qui gênait,
    pas une impossibilité d'agir.

    La preuve est celle que RLC3 écrit déjà : l'activité « WhatsApp ouvert »
    portant le préfixe de cette touche, posée par le clic humain — jamais une
    mémoire d'écran. Le préfixe vient de ``services`` (la même fonction que
    l'écriture), jamais d'un second littéral.

    Coût : une requête d'existence, et seulement quand la clôture arrive SANS
    issue sur un canal « appel » — le seul cas où la réponse sert.
    """
    from .models import LeadActivity
    from .cadence_reperes import prefixe_activite_message_ouvert
    return LeadActivity.objects.filter(
        company_id=etape.company_id, lead_id=etape.lead_id,
        kind=LeadActivity.Kind.WHATSAPP,
        body__startswith=prefixe_activite_message_ouvert(etape),
    ).exists()
