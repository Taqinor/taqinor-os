"""Réglages de l'utilisateur et coupe-circuit de la société (reference/api.md §3.4, §4).

`reglages/` : réglages de `request.user` (sa `ReglagesRythme`, ou ses défauts tant qu'il n'a rien
écrit ; le premier `PATCH` la crée), heures des sollicitations DITES (`Preference`), fenêtre de la société, adresse du
raccourci Siri (réglage déclaré par TCH4), `est_admin` = `IsAdminRole`. Une route pas encore
construite lève `PasEncore` (501) ; le schéma OpenAPI de chacune est celui de son échantillon.
`reglages-societe/` est réservé à un administrateur (`IsAdminRole`, A18-M8) : le coupe-circuit de la
société (donnees.md §2.21, invariant 39) ; absent = actif, lire ne crée rien, un `PATCH` qui ne change pas
la valeur n'écrit rien (la trace `modifie_par`/`modifie_le` reste celle du dernier vrai changement).
"""
import datetime

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.taches.choix import ClePreference
from apps.taches.models.presence import ReglagesSociete
from apps.taches.moteur import sollicitations
from apps.taches.moteur.gabarits import format_heure
from apps.taches.selectors.rythme import preferences_de
from apps.taches.services import rythme as service
from apps.taches.views.base import PERMISSIONS, corps, forme_echantillon, reponses
from apps.taches.views.presence import HorsAssistant
from authentication.permissions import IsAdminRole

REGLAGES = forme_echantillon('reglages')
REGLAGES_SOCIETE = forme_echantillon('reglages_societe')
#: Jours cherchés pour la prochaine fenêtre ouverte de la société (un férié, un week-end).
FENETRE_HORIZON_JOURS = 7
#: Heures des sollicitations tant que rien n'est dit (reference/donnees.md §2.11).
SOLLICITATIONS_DEFAUT = {
    ClePreference.HEURE_MATIN: format_heure(sollicitations.HEURE_MATIN_DEFAUT),
    ClePreference.RELANCE_JOUR: format_heure(sollicitations.HEURE_RELANCE_DEFAUT),
    ClePreference.HEURE_SOIR: format_heure(sollicitations.HEURE_SOIR_DEFAUT),
    ClePreference.HEURE_LIMITE: format_heure(sollicitations.HEURE_LIMITE_DEFAUT),
    ClePreference.REVUE_SEMAINE: 'auto',
}
CHAMPS_DIRECTS = ('titres_notifications', 'titres_calendrier', 'titres_tuile', 'messages_sans_delai',
                  'rappel_avant_bloc_min', 'projet_arret_jours', 'familles_suggestions', 'suggestions_societe',
                  'erp_dans_journee', 'comprendre_mon_rythme', 'pauses_sollicitations')


def fenetre_societe(company, jour):
    """Heures de travail de la société `{"debut","fin"}` : la fenêtre des MESSAGES que
    `notifications.selectors.fenetre_notifications` applique (même canal, même source
    `crm.horaires`), lue le premier jour ouvert à partir de `jour` ; `None` si aucun en 7 jours."""
    from apps.crm import horaires  # module pur, lu comme le fait notifications.selectors
    from apps.notifications.selectors import CANAL_NOTIFICATIONS
    for decalage in range(FENETRE_HORIZON_JOURS):
        fenetre = horaires.fenetre_du_jour(jour + datetime.timedelta(days=decalage), company,
                                           canal=CANAL_NOTIFICATIONS)
        if fenetre is not None:
            return {'debut': format_heure(fenetre[0]), 'fin': format_heure(fenetre[1])}
    return None


def forme_reglages(request, reglages):
    """Le dict de `reglages.json` pour l'utilisateur de `request`."""
    user = request.user
    dites = {p.cle: p.valeur for p in preferences_de(user)}
    forme = {champ: getattr(reglages, champ) for champ in CHAMPS_DIRECTS}
    forme['titres_notifications_demande'] = reglages.titres_notifications_demande_le is not None
    forme['sollicitations'] = {cle: dites.get(cle, defaut) for cle, defaut in SOLLICITATIONS_DEFAUT.items()}
    forme['fenetre_societe'] = fenetre_societe(user.company, service.aujourdhui())
    forme['raccourci_siri_url'] = getattr(settings, 'TACHES_RACCOURCI_SIRI_URL', '') or None
    forme['est_admin'] = IsAdminRole().has_permission(request, None)
    return forme


class ReglagesHorsAssistant(HorsAssistant):
    """403 sous l'assistant (api.md §0) : le relais du Copilote ne lit ni ne change un réglage."""

    message = "L'assistant ne touche pas à tes réglages."


class ReglagesVue(APIView):
    """GET reglages/ · PATCH reglages/ (liste blanche) ; jamais servi au relais de l'assistant."""

    permission_classes = [*PERMISSIONS, ReglagesHorsAssistant]

    @extend_schema(responses=reponses(REGLAGES))
    def get(self, request):
        return Response(forme_reglages(request, service.reglages_ou_defauts(request.user)))

    @extend_schema(request=inline_serializer('TachesCorpsReglages', {
        'titres_notifications': serializers.BooleanField(required=False),
        'titres_calendrier': serializers.BooleanField(required=False),
        'titres_tuile': serializers.BooleanField(required=False),
        'messages_sans_delai': serializers.BooleanField(required=False),
        'rappel_avant_bloc_min': serializers.IntegerField(required=False, allow_null=True),
        'projet_arret_jours': serializers.IntegerField(required=False),
        'familles_suggestions': serializers.ListField(required=False, child=serializers.CharField()),
        'suggestions_societe': serializers.BooleanField(required=False),
        'erp_dans_journee': serializers.BooleanField(required=False),
        'comprendre_mon_rythme': serializers.BooleanField(required=False),
        'pauses_sollicitations': serializers.ListField(required=False, child=serializers.DictField()),
    }), responses=reponses(REGLAGES, erreurs=(400,)))
    def patch(self, request):
        est_admin = IsAdminRole().has_permission(request, self)
        try:
            reglages = service.modifier_reglages(request.user, request.data, est_admin=est_admin)
        except service.ErreursRythme as exc:
            return Response(exc.erreurs, status=status.HTTP_400_BAD_REQUEST)
        except service.ReserveAdministrateur:
            return Response({'suggestions_societe': [service.RESERVE_ADMIN]}, status=status.HTTP_403_FORBIDDEN)
        return Response(forme_reglages(request, reglages))


def maintenant():
    """L'instant de la trace du coupe-circuit (les tests le remplacent)."""
    return timezone.now()


def forme_reglages_societe(company):
    """Le dict de `reglages_societe.json` ; aucune ligne = actif, jamais modifié."""
    reglages = ReglagesSociete.objects.filter(company=company).first()
    if reglages is None:
        return {'balayage_actif': True, 'modifie_par': None, 'modifie_le': None}
    return {'balayage_actif': reglages.balayage_actif, 'modifie_par': reglages.modifie_par_id,
            'modifie_le': serializers.DateTimeField().to_representation(reglages.modifie_le)
            if reglages.modifie_le is not None else None}


def erreurs_reglages_societe(donnees):
    """Erreurs par champ du corps `{"balayage_actif": bool}` (seul champ, obligatoire), ou `{}`."""
    erreurs = {champ: [service.NON_MODIFIABLE] for champ in donnees if champ != 'balayage_actif'}
    if not isinstance(donnees.get('balayage_actif'), bool):
        erreurs['balayage_actif'] = [service.VALEUR_INCONNUE]
    return erreurs


def ecrire_balayage(company, user, valeur):
    """Pose `balayage_actif = valeur` pour la société et trace l'administrateur, seulement si la valeur
    change (absent = actif : rallumer une société jamais coupée ne crée rien)."""
    actuel = ReglagesSociete.objects.filter(company=company).values_list('balayage_actif', flat=True).first()
    if (True if actuel is None else actuel) == valeur:
        return
    instant = maintenant()
    reglages, _ = ReglagesSociete.objects.get_or_create(company=company)
    ReglagesSociete.objects.filter(pk=reglages.pk).update(
        balayage_actif=valeur, modifie_par=user, modifie_le=instant, updated_at=instant)


class ReglagesSocieteVue(APIView):
    """GET · PATCH reglages-societe/ `{"balayage_actif"}` — administrateur seulement."""

    permission_classes = [*PERMISSIONS, IsAdminRole, ReglagesHorsAssistant]

    @extend_schema(responses=reponses(REGLAGES_SOCIETE))
    def get(self, request):
        return Response(forme_reglages_societe(request.user.company))

    @extend_schema(request=corps('ReglagesSociete', {'balayage_actif': False}, requis=('balayage_actif',)),
                   responses=reponses(REGLAGES_SOCIETE, erreurs=(400,)))
    def patch(self, request):
        donnees = request.data if isinstance(request.data, dict) else {}
        erreurs = erreurs_reglages_societe(donnees)
        if erreurs:
            return Response(erreurs, status=status.HTTP_400_BAD_REQUEST)
        ecrire_balayage(request.user.company, request.user, donnees['balayage_actif'])
        return Response(forme_reglages_societe(request.user.company))
