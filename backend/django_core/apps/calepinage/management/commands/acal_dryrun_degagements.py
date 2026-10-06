"""ACAL256 (C-ACAL-033) — DRY-RUN : le compte moteur avec les réglages de
dégagement de la société, à côté du compte actuel.

Le drapeau ``USE_MOTEUR_CALEPINAGE`` levé, chaque pan d'un devis passe par
``services/traduction.entree_depuis_layout`` avec la section ``degagements``
de sa société (retrait de rive, allée technique, dégagement par type) et
l'allée propre au document. Avant toute activation (décision du fondateur,
D-ACAL-17), cette commande liste, devis par devis :

    société | référence | statut | compte actuel → compte avec réglages

« Compte actuel » = l'entrée villa d'aujourd'hui (``traduire=False``) ;
« avec réglages » = l'entrée traduite (``traduire=True``). Seuls les devis
dont la société a réglé ses dégagements (ou dont le document porte son allée)
peuvent changer.

LECTURE SEULE : aucun devis, aucun calepinage, aucun envoyé n'est réécrit.

    python manage.py acal_dryrun_degagements [--company <slug>] [--tous]
"""
from __future__ import annotations

from django.apps import apps as registre
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('ACAL256 — liste (lecture seule) le compte moteur actuel et le '
            'compte avec les réglages de dégagement de la société.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', default=True,
            help="Défaut et seul mode : rien n'est jamais écrit.")
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')
        parser.add_argument(
            '--tous', action='store_true', default=False,
            help='Lister aussi les devis dont le compte ne change pas.')

    def handle(self, *args, **options):
        from apps.ventes.services import compte_moteur_du_layout

        Devis = registre.get_model('ventes', 'Devis')
        qs = (Devis.objects.exclude(roof_layout__isnull=True)
              .select_related('company')
              .order_by('company_id', 'reference'))
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        ecrire = self.stdout.write
        ecrire('DRY-RUN ACAL256 (lecture seule) — aucune écriture.')
        ecrire('société | référence | statut | compte actuel → compte avec '
               'réglages')
        nb = 0
        for devis in qs.iterator(chunk_size=200):
            layout = devis.roof_layout
            if not isinstance(layout, dict) or not layout:
                continue
            try:
                actuel = compte_moteur_du_layout(
                    layout, company=devis.company, devis=devis,
                    traduire=False)
                regle = compte_moteur_du_layout(
                    layout, company=devis.company, devis=devis,
                    traduire=True)
            except Exception as exc:  # noqa: BLE001 — signalé, jamais fatal
                ecrire(f'  {devis.reference} : illisible ({exc})')
                continue
            avant = actuel['modules'] if actuel else None
            apres = regle['modules'] if regle else None
            if avant == apres and not options.get('tous'):
                continue
            nb += 1
            slug = getattr(devis.company, 'slug', '') or ''
            ecrire(f'  {slug} | {devis.reference} | {devis.statut} | '
                   f'{avant} → {apres}')
        ecrire(f'Devis listés : {nb}')
