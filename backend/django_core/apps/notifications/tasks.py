"""NTI18N37 — rappel Beat de fin d'année : saisie des fêtes mobiles N+1.

Le calcul hégirien précis nécessite une observation lunaire locale — jamais
calculé algorithmiquement (principe déjà en place dans ``rh/holidays.py``) :
les 4 fêtes mobiles (Aïd el-Fitr, Aïd el-Adha, 1er Moharram, Aïd el-Mawlid)
restent une saisie MANUELLE, via l'assistant NTI18N33
(``apps.parametres.fetes_mobiles`` — app FONDATION exemptée de la frontière
cross-app CLAUDE.md). Le risque réel : une société oublie de les saisir avant
la fin de l'année, et le calendrier RH/projet de janvier calcule des jours
ouvrés faux sans que personne ne s'en aperçoive.

Ce module ajoute le RAPPEL : en novembre-décembre, une fois par jour tant que
les 4 fêtes de l'année N+1 ne sont pas toutes saisies
(``Holiday.recurrent_annuel=False``, NTI18N14), l'administrateur RH de
chaque société est notifié via ``notifications.services.notify()`` — jamais
un second canal. Idempotent PAR CONSTRUCTION (pas d'état/marqueur à gérer) :
l'état est recalculé chaque jour depuis ``Holiday`` via
``fetes_mobiles_saisies()`` (NTI18N33) ; le rappel s'arrête de lui-même dès
que la saisie est complète, et repart si une fête saisie était supprimée par
erreur.
"""
import logging

from celery import shared_task
from django.utils import timezone

from .models import EventType
from .services import notify

logger = logging.getLogger(__name__)

# Fenêtre d'activation : le rappel ne fait rien hors novembre-décembre, même
# appelé manuellement (le beat ne le déclenche déjà que sur cette fenêtre —
# voir erp_agentique/celery.py — mais la garde est répétée ici pour rester
# correcte indépendamment du réglage du scheduler).
MOIS_ACTIFS = (11, 12)


def _societes_actives():
    """Toutes les sociétés actives. Vide si erreur (best-effort)."""
    try:
        from authentication.models import Company
        return list(Company.objects.filter(actif=True))
    except Exception:  # pragma: no cover - défensif
        logger.warning(
            'rappel_fetes_mobiles: chargement des sociétés impossible',
            exc_info=True)
        return []


def _admins_rh(company):
    """Porteurs de la permission ``rh_voir`` de la société ; repli sur les
    managers (même politique que ``sweeps._managers``) si aucun n'est
    identifiable — jamais un prénom en dur, la responsabilité par défaut est
    la société (règle fondateur)."""
    try:
        from authentication.models import CustomUser
        candidats = [
            u for u in CustomUser.objects.filter(
                company=company, is_active=True)
            if u.has_erp_permission('rh_voir')
        ]
    except Exception:  # pragma: no cover - défensif
        candidats = []
    if candidats:
        return candidats
    from .sweeps import _managers
    return _managers(company)


def _fetes_manquantes(company, annee):
    """Clés (parmi ``FETES_MOBILES_CLES``) encore SANS date saisie pour
    ``annee``, via l'assistant NTI18N33 — jamais une requête ``Holiday``
    réinventée ici."""
    from apps.parametres.fetes_mobiles import fetes_mobiles_saisies
    saisies = fetes_mobiles_saisies(company, annee)
    return [cle for cle, valeur in saisies.items() if not valeur]


@shared_task(name='notifications.rappel_fetes_mobiles')
def rappel_fetes_mobiles(now=None):
    """Notifie chaque société active dont les fêtes mobiles de l'année N+1
    ne sont pas toutes saisies (novembre-décembre uniquement). Best-effort
    par société ; renvoie le nombre de sociétés notifiées."""
    moment = now or timezone.now()
    if moment.month not in MOIS_ACTIFS:
        return 0

    from apps.parametres.fetes_mobiles import FETES_MOBILES_LIBELLES
    annee_suivante = moment.year + 1
    notifiees = 0
    for company in _societes_actives():
        try:
            manquantes = _fetes_manquantes(company, annee_suivante)
        except Exception:  # pragma: no cover - défensif
            logger.warning(
                'rappel_fetes_mobiles: société %s échouée',
                getattr(company, 'pk', None), exc_info=True)
            continue
        if not manquantes:
            continue
        try:
            libelles = ', '.join(FETES_MOBILES_LIBELLES[cle] for cle in manquantes)
            title = f'Fêtes mobiles {annee_suivante} à saisir'
            body = (
                f'{len(manquantes)} fête(s) mobile(s) de {annee_suivante} '
                f'restent à saisir : {libelles}. Sans cette saisie, le '
                'calendrier RH/projet de janvier calculera des jours ouvrés '
                'incorrects.')
            for admin in _admins_rh(company):
                notify(admin, EventType.FETES_MOBILES_A_SAISIR, title,
                       body=body, company=company)
            notifiees += 1
        except Exception:  # pragma: no cover - défensif
            logger.warning(
                'rappel_fetes_mobiles: notification société %s échouée',
                getattr(company, 'pk', None), exc_info=True)
    logger.info(
        'rappel_fetes_mobiles: %s société(s) notifiée(s) pour %s',
        notifiees, annee_suivante)
    return notifiees
