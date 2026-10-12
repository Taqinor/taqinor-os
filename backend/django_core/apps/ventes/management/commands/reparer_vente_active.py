# -*- coding: utf-8 -*-
"""VNT47 (D-VNT-4, D-VNT-5) — une seule vente en vigueur par lead.

    # 1. Lister les leads à plus d'une vente en vigueur (lecture seule) :
    python manage.py reparer_vente_active --lister --societe 1
    python manage.py reparer_vente_active --lister --toutes-societes

    # 2. DRY-RUN (défaut) : diff avant/après, RIEN n'est écrit :
    python manage.py reparer_vente_active --lead 1594 --garder 388 \\
        --refaire-acompte 15000 --paiement-recu 15000 \\
        --paiement-date 2026-10-12 --paiement-mode virement \\
        --utilisateur <identifiant>

    # 3. Même ligne + --appliquer : écrit pour de vrai.

La logique vit dans ``apps/ventes/domain/reparation_vente.py`` : saisies de
paiement annulées (erreur de saisie), factures des autres ventes (et de la
vente gardée si l'acompte est refait) annulées PAR AVOIR, autres ventes
dés-acceptées puis archivées, acompte refait, émis et encaissé. Toujours borné
à la société du lead ; relancée après application, elle ne fait rien.
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "VNT47 — une seule vente en vigueur par lead : --lister les leads en "
        "double, puis --lead/--garder (DRY-RUN par défaut, --appliquer pour "
        "écrire)."
    )

    def add_arguments(self, parser):
        parser.add_argument('--lister', action='store_true',
                            help='Lister les leads à plus d\'une vente en '
                                 'vigueur (lecture seule).')
        parser.add_argument('--societe', default=None,
                            help='Société (id ou slug).')
        parser.add_argument('--toutes-societes', action='store_true',
                            help='--lister sur toutes les sociétés.')
        parser.add_argument('--lead', type=int, default=None)
        parser.add_argument('--garder', type=int, default=None,
                            help='Id du devis qui reste la vente en vigueur.')
        parser.add_argument('--refaire-acompte', '--acompte',
                            dest='acompte', default=None,
                            help="Acompte TTC (MAD) refait sur la vente "
                                 "gardée ; ses factures vivantes sont "
                                 "annulées par avoir.")
        parser.add_argument('--paiement-recu', default=None,
                            help='Montant réellement reçu (MAD) : les '
                                 'saisies existantes sont annulées comme '
                                 'erreurs de saisie.')
        parser.add_argument('--paiement-date', default=None,
                            help='Date du paiement reçu (AAAA-MM-JJ).')
        parser.add_argument('--paiement-mode', default='virement')
        parser.add_argument('--paiement-reference', default='')
        parser.add_argument('--utilisateur', default=None,
                            help='Identifiant de l\'auteur (chatter, avoirs).')
        parser.add_argument('--avoir-meme-si-envoyee', action='store_true',
                            help='Annuler par avoir même une facture déjà '
                                 'envoyée au client.')
        parser.add_argument('--appliquer', action='store_true',
                            help="Écrire réellement (sinon DRY-RUN).")

    def handle(self, *args, **options):
        from apps.ventes.domain.reparation_vente import ReparationRefusee
        try:
            if options['lister']:
                return self._lister(options)
            return self._reparer(options)
        except ReparationRefusee as exc:
            raise CommandError(f'Refusé : {exc.message}')

    # ── --lister ────────────────────────────────────────────────────────────
    def _lister(self, options):
        from apps.ventes.domain.reparation_vente import (
            leads_a_ventes_multiples)
        if not options['toutes_societes'] and not options['societe']:
            raise CommandError('--lister exige --societe <id|slug> ou '
                               '--toutes-societes.')
        societe = (None if options['toutes_societes']
                   else self._societe(options['societe']))
        leads = leads_a_ventes_multiples(societe)
        if not leads:
            self.stdout.write('Aucun lead à plus d\'une vente en vigueur.')
            return
        self.stdout.write(f'{len(leads)} lead(s) à plus d\'une vente en '
                          'vigueur :')
        for entree in leads:
            self._ecrire_lead(entree)

    def _ecrire_lead(self, entree):
        company = entree['company']
        self.stdout.write(
            f"\nLead {entree['lead_id']} — {entree['lead']} (société "
            f"{company.pk} {company.slug}) : {len(entree['ventes'])} ventes "
            'en vigueur')
        for v in entree['ventes']:
            self.stdout.write(
                f"  - {v['reference']} (id {v['id']}, V{v['version']}, "
                f"{v['ttc']} MAD TTC, acceptée le {v['date_acceptation']}) "
                f"chaîne : {' → '.join(v['chaine'])}")
            self.stdout.write(
                f"      factures : {'; '.join(v['factures']) or '—'} ; "
                f"BC : {', '.join(v['bons_commande']) or '—'}")
        self.stdout.write(
            f"  → python manage.py reparer_vente_active --lead "
            f"{entree['lead_id']} --garder <id> --utilisateur <identifiant>"
            ' [--refaire-acompte <MAD> --paiement-recu <MAD> '
            '--paiement-date AAAA-MM-JJ]')

    # ── réparation ──────────────────────────────────────────────────────────
    def _reparer(self, options):
        from apps.ventes.domain.reparation_vente import (
            montant_saisi, reparer_vente_active)
        if options['lead'] is None or options['garder'] is None:
            raise CommandError('Donnez --lister, ou --lead <id> --garder '
                               '<devis_id>.')
        self._verifier_societe(options)
        acompte = (montant_saisi(options['acompte'], 'Acompte')
                   if options['acompte'] else None)
        resultat = reparer_vente_active(
            lead_id=options['lead'], garder_id=options['garder'],
            user=self._utilisateur(options['utilisateur']),
            acompte=acompte, paiement=self._paiement(options),
            avoir_meme_si_envoyee=options['avoir_meme_si_envoyee'],
            appliquer=options['appliquer'])
        self._ecrire_resultat(resultat)

    def _ecrire_resultat(self, resultat):
        import difflib
        if resultat['statut'] == 'rien_a_faire':
            self.stdout.write(resultat['message'])
            return
        entete = ('DRY-RUN' if resultat['statut'] == 'dry_run'
                  else 'APPLIQUÉ')
        self.stdout.write(f'=== {entete} — étapes ===')
        for etape in resultat['etapes']:
            self.stdout.write(f'  {etape}')
        for titre, lignes in (('AVANT', resultat['avant']),
                              ('APRÈS', resultat['apres'])):
            self.stdout.write(f'=== {titre} ===')
            for ligne in lignes:
                self.stdout.write(f'  {ligne}')
        self.stdout.write('=== DIFF ===')
        for ligne in difflib.unified_diff(
                resultat['avant'], resultat['apres'], 'avant', 'après',
                lineterm='', n=0):
            self.stdout.write(ligne)
        self.stdout.write(resultat['message'])

    def _paiement(self, options):
        from apps.ventes.domain.reparation_vente import montant_saisi
        if not options['paiement_recu']:
            return None
        from apps.ventes.models import Paiement
        mode = options['paiement_mode']
        if mode not in Paiement.Mode.values:
            raise CommandError(f'Mode de paiement inconnu : {mode}.')
        try:
            jour = (date.fromisoformat(options['paiement_date'])
                    if options['paiement_date'] else date.today())
        except ValueError:
            raise CommandError('--paiement-date : format AAAA-MM-JJ.')
        return {'montant': montant_saisi(options['paiement_recu'],
                                         'Paiement reçu'),
                'date': jour, 'mode': mode,
                'reference': options['paiement_reference']}

    def _utilisateur(self, identifiant):
        if not identifiant:
            raise CommandError('--utilisateur <identifiant> est requis '
                               '(auteur des avoirs et du chatter).')
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.filter(username=identifiant).first()
        if user is None:
            raise CommandError(f'Utilisateur inconnu : {identifiant}.')
        return user

    def _verifier_societe(self, options):
        if not options['societe']:
            return
        from apps.ventes.models import Devis
        societe = self._societe(options['societe'])
        if not Devis.objects.filter(pk=options['garder'],
                                    lead_id=options['lead'],
                                    company=societe).exists():
            raise CommandError(
                f"Le lead {options['lead']} n'est pas dans la société "
                f'{societe.slug}.')

    def _societe(self, valeur):
        from authentication.models import Company
        societe = (Company.objects.filter(slug=valeur).first()
                   or (Company.objects.filter(pk=valeur).first()
                       if str(valeur).isdigit() else None))
        if societe is None:
            raise CommandError(f'Société inconnue : {valeur}')
        return societe
