"""NTDMO21/31 — résumé « Ce que vous avez accompli ce mois-ci » (société démo).

Widget du Dashboard réservé aux sociétés de DÉMONSTRATION (``Company.est_demo``) :
une phrase qui aide un commercial TAQINOR à raconter une histoire cohérente en
rendez-vous. AUCUNE nouvelle agrégation : on réutilise les sélecteurs existants
(``ventes.selectors.devis_envoyes_periode``, ``installations.selectors.
chantiers_receptionnes``, ``reporting.metriques_ca.ca_ht`` = LE CA HT net
d'avoirs du reporting).

NTDMO31 — le résumé est pré-calculé chaque nuit (tâche ``reporting.
recalcul_nocturne_onboarding``) et SERVI DEPUIS LE CACHE : ``resume_pour_societe``
ne recalcule jamais qu'en cas de défaut de cache (première demande du mois,
purge Redis), puis remet en cache.
"""
import logging
from datetime import date
from decimal import Decimal

from django.core.cache import cache

logger = logging.getLogger(__name__)

#: 26 h : couvre la fenêtre entre deux passages nocturnes (un raté n'éteint pas
#: le widget), sans jamais servir un résumé d'un mois révolu (la clé porte le
#: mois).
TTL_SECONDES = 26 * 3600

_STATUTS_CA = ['emise', 'en_retard', 'payee']


def cle_cache(company_id, today):
    return f'reporting:demo_resume:{company_id}:{today:%Y%m}'


def _debut_fin_mois(today):
    debut = today.replace(day=1)
    if debut.month == 12:
        suivant = date(debut.year + 1, 1, 1)
    else:
        suivant = date(debut.year, debut.month + 1, 1)
    return debut, date.fromordinal(suivant.toordinal() - 1)


def _montant(valeur):
    entier = int(Decimal(str(valeur)).quantize(Decimal('1')))
    return f'{entier:,}'.replace(',', ' ')


def phrase(nb_devis, nb_chantiers, ca_ht):
    return (f'{nb_devis} devis envoyés, {nb_chantiers} chantiers réceptionnés, '
            f'{_montant(ca_ht)} MAD facturés ce mois — données de démonstration')


def calculer_resume(company, today=None):
    """Calcule (sans cache) le résumé du mois courant d'UNE société."""
    from apps.installations.selectors import chantiers_receptionnes
    from apps.reporting.metriques_ca import ca_ht
    from apps.ventes.selectors import devis_envoyes_periode

    today = today or date.today()
    debut, fin = _debut_fin_mois(today)
    nb_devis = devis_envoyes_periode(
        company, date_debut=debut, date_fin=fin).count()
    nb_chantiers = len(chantiers_receptionnes(
        company, date_debut=debut, date_fin=fin))
    ca = ca_ht(company, period=(debut, fin),
               filters={'statut__in': _STATUTS_CA})
    return {
        'mois': f'{today:%Y-%m}',
        'devis_envoyes': nb_devis,
        'chantiers_receptionnes': nb_chantiers,
        'ca_facture_ht': float(ca),
        'phrase': phrase(nb_devis, nb_chantiers, ca),
    }


def precalculer(company, today=None):
    """Calcule ET met en cache le résumé d'une société démo."""
    today = today or date.today()
    resume = calculer_resume(company, today)
    cache.set(cle_cache(company.id, today), resume, TTL_SECONDES)
    return resume


def resume_pour_societe(company, today=None):
    """Résumé servi par l'endpoint : cache d'abord (NTDMO31), calcul seulement
    sur défaut de cache. ``None`` pour une société qui n'est PAS démo."""
    if company is None or not getattr(company, 'est_demo', False):
        return None
    today = today or date.today()
    resume = cache.get(cle_cache(company.id, today))
    if resume is None:
        resume = precalculer(company, today)
    return resume


def precalculer_societes_demo(today=None):
    """Tâche nocturne : pré-calcule le résumé de chaque société démo.
    Une société en échec n'interrompt jamais les suivantes."""
    from authentication.models import Company

    n = 0
    for company in Company.objects.filter(est_demo=True):
        try:
            precalculer(company, today)
            n += 1
        except Exception:  # pragma: no cover - défensif
            logger.warning('demo_resume : échec société %s ignoré',
                           company.id, exc_info=True)
    return n
