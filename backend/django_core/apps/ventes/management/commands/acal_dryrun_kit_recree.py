"""ACAL90 (C-ACAL-111, D-ACAL-22) — DRY-RUN : les devis ENVOYÉS où une
resynchronisation passée a RECRÉÉ une ligne de kit.

Avant ACAL90, « Resynchroniser le devis » recréait au prix catalogue toute
ligne de kit (transport, installation, structure…) que le commercial avait
supprimée à la main — y compris sur un devis ENVOYÉ, corrigé sur place. Le
marqueur ``etude_params.kit_retire`` protège les PROCHAINS gestes ; cette
commande liste, AVANT le merge, les envoyés déjà touchés pour la décision du
fondateur : référence / statut / classe / montant recréé / total TTC.

Détection : chaque trace « Corrigé après envoi — calepinage … » est comparée
à l'instantané de configuration pris JUSTE AVANT elle (QJR518,
``avant_correction``) ; une classe de kit absente de cet instantané et
présente dans les lignes ACTUELLES a été recréée par la resynchro.

LECTURE SEULE. ``--dry-run`` est le défaut ET le seul mode : aucun devis
n'est réécrit, aucun marqueur n'est posé rétroactivement.

    python manage.py acal_dryrun_kit_recree [--company <slug>]
"""
from decimal import Decimal

from django.core.management.base import BaseCommand


def _classes_du_contenu(contenu):
    from apps.ventes.domain.catalogue import classer_produit
    from apps.ventes.domain.composition import CLASSES_KIT_COMPLETABLES
    classes = set()
    for ligne in (contenu or {}).get('lignes') or ():
        if not isinstance(ligne, dict):
            continue
        classe = classer_produit(str(ligne.get('designation') or ''))
        if classe in CLASSES_KIT_COMPLETABLES:
            classes.add(classe)
    return classes


def kit_recree(devis):
    """``[(classe, designation, montant_ht)]`` des lignes de kit ACTUELLES
    absentes de l'instantané pris avant une correction « calepinage »
    après envoi. Aucune écriture."""
    from apps.ventes.domain.lignes import _classe_completable
    from apps.ventes.models import ConfigurationDevisSnapshot, DevisActivity

    corrections = (DevisActivity.objects
                   .filter(devis=devis, field='correction_apres_envoi',
                           body__icontains='calepinage')
                   .order_by('created_at'))
    absentes = set()
    for trace in corrections:
        avant = (ConfigurationDevisSnapshot.objects
                 .filter(devis=devis, date_creation__lte=trace.created_at)
                 .order_by('-date_creation', '-id').first())
        if avant is None:
            continue
        absentes |= ({c for c in (_classe_completable(li)
                                  for li in devis.lignes.all()) if c}
                     - _classes_du_contenu(avant.contenu))
    sortie = []
    for ligne in devis.lignes.all():
        classe = _classe_completable(ligne)
        if classe in absentes:
            montant = (Decimal(ligne.quantite or 0)
                       * Decimal(ligne.prix_unitaire or 0))
            sortie.append((classe, ligne.designation, montant))
    return sortie


class Command(BaseCommand):
    help = ('ACAL90 — liste (lecture seule) les devis envoyés où une '
            'resynchronisation a recréé une ligne de kit retirée.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', default=True,
            help="Défaut et seul mode : rien n'est jamais écrit.")
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')

    def handle(self, *args, **options):
        from apps.ventes.domain.argent import Vue, totaux
        from apps.ventes.models import Devis

        qs = (Devis.objects.filter(statut=Devis.Statut.ENVOYE)
              .select_related('company').prefetch_related('lignes__produit')
              .order_by('company_id', 'reference'))
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        self.stdout.write('DRY-RUN (lecture seule) — aucune écriture.')
        self.stdout.write(
            'société | référence | statut | classe | désignation | '
            'montant recréé HT | total TTC')
        nb = 0
        for devis in qs.iterator(chunk_size=200):
            recrees = kit_recree(devis)
            if not recrees:
                continue
            nb += 1
            try:
                ttc = totaux(devis, vue=Vue.NET).ttc
            except Exception:  # noqa: BLE001 — un total illisible est signalé
                ttc = '?'
            for classe, designation, montant in recrees:
                self.stdout.write(
                    f'  {devis.company.slug} | {devis.reference} | '
                    f'{devis.statut} | {classe} | {designation} | '
                    f'{montant} | {ttc}')
        self.stdout.write(f'Devis concernés : {nb}')
