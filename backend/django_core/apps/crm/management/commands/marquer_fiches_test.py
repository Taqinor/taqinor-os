"""CADV63 — pose l'étiquette ``test`` sur les fiches internes / de test.

Deux populations, jamais des vrais prospects :
  * les leads qui PARTAGENT un numéro interne (au moins ``SEUIL_NUMERO_PARTAGE``
    fiches de la société sur le même ``phone_normalise``) ;
  * les « Signé » du site sans devis, sans activité (hors création) ni touche.

L'étiquette (``TAG_TEST``, CADV2) sort ces fiches des tuiles du funnel
(``q_lead_compte``). Réversible : retirer l'étiquette reste un geste manuel.

Dry-run PAR DÉFAUT (ids imprimés) ; ``--apply`` pose l'étiquette (et crée
l'entrée ``LeadTag`` de la société si elle manque) avec une note chatter.
Rejouable : une fiche déjà étiquetée n'est plus candidate.

    python manage.py marquer_fiches_test [--company <slug|id>] [--apply]
                                         [--ids 1,2,3]
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from apps.crm import stages
from apps.crm.activity import log_bulk_note
from apps.crm.fiche_funnel import poser_tag_lead
from apps.crm.leads_selectors import TAG_TEST
from apps.crm.management.commands.placer_anciens_leads import (
    _resoudre_company,
)
from apps.crm.models import Lead, LeadActivity, LeadTag
from apps.ventes.selectors import leads_ayant_recu_un_devis

#: Nombre de fiches de la société sur un même numéro à partir duquel le
#: numéro est un numéro interne (19 fiches du site sur un numéro en prod).
SEUIL_NUMERO_PARTAGE = 10


def _a_etiqueter(company):
    """Renvoie ``(partages, signes_vides)`` : deux listes de ``Lead`` non déjà
    étiquetés ``test``."""
    deja = {lead.pk for lead in Lead.objects.filter(company=company)
            .exclude(tags='') if TAG_TEST in
            [t.strip().lower() for t in (lead.tags or '').split(',')]}
    numeros = [
        ligne['phone_normalise'] for ligne in
        Lead.objects.filter(company=company).exclude(phone_normalise='')
        .values('phone_normalise').annotate(n=Count('pk'))
        .filter(n__gte=SEUIL_NUMERO_PARTAGE)]
    partages = list(Lead.objects.filter(
        company=company, phone_normalise__in=numeros).order_by('pk'))
    signes = list(Lead.objects.filter(
        company=company, stage=stages.SIGNED,
        source=Lead.Source.SITE_WEB).order_by('pk'))
    ids = [lead.pk for lead in signes]
    avec_devis = leads_ayant_recu_un_devis(company, ids)
    avec_activite = set(LeadActivity.objects.filter(
        company=company, lead_id__in=ids,
    ).exclude(kind=LeadActivity.Kind.CREATION)
        .values_list('lead_id', flat=True))
    avec_touche = set(Lead.objects.filter(
        company=company, pk__in=ids, relance_etapes__isnull=False,
    ).values_list('pk', flat=True))
    vides = [lead for lead in signes
             if lead.pk not in avec_devis | avec_activite | avec_touche]
    partages = [lead for lead in partages if lead.pk not in deja]
    vus = {lead.pk for lead in partages}
    vides = [lead for lead in vides
             if lead.pk not in deja and lead.pk not in vus]
    return partages, vides


class Command(BaseCommand):
    help = ('CADV63 — étiquette « test » les fiches à numéro partagé et les '
            '« Signé » du site vides (dry-run par défaut ; --apply, --ids).')

    def add_arguments(self, parser):
        parser.add_argument('--company', dest='company', default=None)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--ids', default='',
                            help='Ids de leads séparés par des virgules.')

    def handle(self, *args, **options):
        company = _resoudre_company(options.get('company'))
        try:
            ids = {int(i) for i in options['ids'].split(',') if i.strip()}
        except ValueError:
            raise CommandError('--ids : entiers séparés par des virgules.')
        partages, vides = _a_etiqueter(company)
        if ids:
            partages = [x for x in partages if x.pk in ids]
            vides = [x for x in vides if x.pk in ids]
        self.stdout.write(
            f'{len(partages)} fiche(s) à numéro partagé, '
            f'{len(vides)} « Signé » du site vide(s).')
        for motif, lot in (('numéro partagé', partages),
                           ('Signé du site vide', vides)):
            for lead in lot:
                self.stdout.write(f'  #{lead.pk} {lead.nom} ({motif})')
        if not options['apply']:
            self.stdout.write("Dry-run — rien n'est écrit (--apply).")
            return
        if partages or vides:
            LeadTag.objects.get_or_create(company=company, nom=TAG_TEST)
        for motif, lot in (('numéro partagé entre fiches', partages),
                           ('« Signé » du site sans devis ni activité', vides)):
            for lead in lot:
                poser_tag_lead(lead, None, TAG_TEST)
                log_bulk_note(
                    lead, None,
                    f'Fiche étiquetée « {TAG_TEST} » : {motif} (CADV63) — '
                    f'hors des chiffres du funnel.')
        self.stdout.write(self.style.SUCCESS(
            f'{len(partages) + len(vides)} fiche(s) étiquetée(s).'))
