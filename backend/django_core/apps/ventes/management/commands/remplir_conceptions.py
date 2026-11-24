"""ADEV141 (D-ACAL-97) — remplir les conceptions des leads existants, LISTE D'ABORD.

Sans option, la commande LISTE (règle du 21/11 : une réparation de données ne
se fait qu'après la liste montrée) : pour chaque lead, société par société,
son marché, l'option que le moteur retiendrait, ou son refus nommé — calculé
par le moteur unique (``conception/moteur.py::calculer_conception``, aucune
écriture ; le tout dans une transaction annulée d'office). Rien n'est écrit.

``--appliquer`` range la conception de chaque lead situé (ville ou GPS : un
lead sans lieu reste un refus listé, jamais rangé) par l'écrivain unique
(``conception/service.py::relancer``, origine ``remplissage``) : une empreinte
égale n'écrit rien, donc une seconde exécution ne change rien. Aucun devis
n'est lu en écriture : le moteur ne lit aucun devis, ``relancer`` n'en écrit
aucun. Un lead d'une société n'est jamais lu pour une autre (la société est
celle du lead, filtrée à la requête).

Un lead qui a déjà une version courante n'est pas recalculé (relecture E3 M2 :
une version née d'une pose serait refaite sans son toit). ``--appliquer`` exige
``--company`` ; la liste ouvre un point de sauvegarde par lead.

    python manage.py remplir_conceptions [--company <id>] [--appliquer]   (--appliquer : --company requis)
"""
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)

DECLENCHEUR = {'origine': 'remplissage', 'champs': []}


def _leads(company):
    """Les leads vivants de ``company`` (référence par chaîne : aucun import
    du modèle du CRM)."""
    from django.apps import apps
    return apps.get_model('crm', 'Lead').objects.filter(company=company).order_by('pk')


def _leads_deja_ranges(company):
    """Les leads de ``company`` qui ont déjà une version courante."""
    from apps.ventes.models import ConceptionLead
    return set(ConceptionLead.objects.filter(company=company, courante=True, lead__isnull=False)
               .values_list('lead_id', flat=True))


def _ligne(lead, resultat):
    if resultat.etat == 'refus':
        refus = resultat.refus or {}
        return f'  lead #{lead.pk} [{resultat.marche}] REFUS {refus.get("code")} ({refus.get("champ")}) : ' \
               f'{refus.get("message")}'
    return f'  lead #{lead.pk} [{resultat.marche}] option retenue : {resultat.option_retenue}'


class Command(BaseCommand):
    help = ("Liste (par défaut) ou range (--appliquer) la conception du moteur unique de chaque lead "
            "existant, société par société. Aucun devis n'est modifié.")

    def add_arguments(self, parser):
        parser.add_argument('--company', type=int, default=None)
        parser.add_argument('--appliquer', action='store_true')

    def handle(self, *args, **opts):
        from authentication.models import Company

        if opts['appliquer'] and not opts['company']:
            # Relecture E3 M2 — une écriture se fait société par société, nommée.
            raise CommandError('--appliquer exige --company <id> : une société à la fois.')
        societes = Company.objects.order_by('pk')
        if opts['company']:
            societes = societes.filter(pk=opts['company'])
        for company in societes:
            self.stdout.write(f'Société #{company.pk} {company.nom}')
            if opts['appliquer']:
                self._appliquer(company)
            else:
                self._lister(company)

    def _lister(self, company):
        from apps.ventes.conception.moteur import calculer_conception

        completes = refus = erreurs = 0
        with transaction.atomic():
            for lead in _leads(company).iterator():
                try:
                    with transaction.atomic():  # relecture E3 M2 : une erreur de base reste à ce lead
                        resultat = calculer_conception(lead, company)
                except Exception as exc:  # noqa: BLE001 — lead illisible signalé (D-ENF22-BLE001)
                    logger.warning('remplir_conceptions : lead #%s illisible', lead.pk, exc_info=True)
                    erreurs += 1
                    self.stdout.write(f'  lead #{lead.pk} : calcul impossible ({type(exc).__name__})')
                    continue
                completes += resultat.etat != 'refus'
                refus += resultat.etat == 'refus'
                self.stdout.write(_ligne(lead, resultat))
            transaction.set_rollback(True)  # garantie : la liste n'écrit rien
        self.stdout.write(f'  LISTE : {completes} conception(s) complète(s), {refus} refus, {erreurs} erreur(s) '
                          '— rien n\'est écrit ; relancer avec --appliquer pour ranger.')

    def _appliquer(self, company):
        from apps.ventes.conception.moteur import refus_localisation
        from apps.ventes.conception.service import relancer

        ecrites = inchangees = sans_lieu = erreurs = 0
        deja = _leads_deja_ranges(company)
        for lead in _leads(company).iterator():
            if refus_localisation(lead) is not None:  # listé comme refus : rien à ranger sans lieu
                sans_lieu += 1
                continue
            if lead.pk in deja:
                # Relecture E3 M2 — un REMPLISSAGE, pas un rafraîchissement : une
                # version courante (peut-être née d'une pose) n'est pas refaite
                # sans son toit ; le filet de la lecture la tient à jour.
                inchangees += 1
                continue
            try:
                relance = relancer(lead, company=company, declencheur=dict(DECLENCHEUR))
            except Exception as exc:  # noqa: BLE001 — un lead en échec n'arrête pas le remplissage (D-ENF22-BLE001)
                logger.warning('remplir_conceptions : lead #%s non rangé', lead.pk, exc_info=True)
                erreurs += 1
                self.stdout.write(f'  lead #{lead.pk} : non rangé ({type(exc).__name__})')
                continue
            ecrites += relance.ecrite
            inchangees += not relance.ecrite
        self.stdout.write(f'  APPLIQUÉ : {ecrites} version(s) rangée(s), {inchangees} inchangée(s), '
                          f'{sans_lieu} sans ville ni GPS (non rangés), {erreurs} erreur(s).')
