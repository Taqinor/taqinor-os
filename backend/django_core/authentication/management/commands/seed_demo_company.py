"""Seed a RICH demo tenant for sales demos & product evaluation (NTDMO1-5).

Extends the idea of ``seed_demo`` but builds a *distinct*, fuller company
(default slug ``taqinor-demo-full``, never colliding with ``taqinor-demo``) with
a 12-month living history: leads across the 6 STAGES.py stages (NTDMO2), quotes
covering the 3 market modes (NTDMO3), a chantier→facture→paiement chain with a
live aged balance (NTDMO4), and SAV/maintenance/stock movements (NTDMO5).

Idempotent — safe to run twice: the company is matched by slug
(``get_or_create``) and, once its 12-month history exists, a second run is a
no-op (stable counts).

Run:
  python manage.py seed_demo_company                      # slug taqinor-demo-full
  python manage.py seed_demo_company --slug ma-demo --force

Known logins (documented — DEBUG/demo only):
  demo_admin_full / DemoFull@2026!   (administrateur)
  demo_resp_full  / DemoFull@2026!   (responsable)

ERR88 guard: refused outside ``settings.DEBUG`` without ``--force`` (it creates
accounts with a KNOWN password).
"""
import random
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

DEMO_PASSWORD = 'DemoFull@2026!'
# Seed fixe → un reset (NTDMO6) reproduit le même nombre d'enregistrements.
RNG_SEED = 42


class Command(BaseCommand):
    help = ('Seed a rich 12-month demo tenant (idempotent). Distinct from '
            'seed_demo — creates its own company (default slug '
            'taqinor-demo-full) with leads/quotes/invoices/SAV history.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--slug', default='taqinor-demo-full',
            help='Slug de la société démo à créer/peupler '
                 '(défaut: taqinor-demo-full).')
        parser.add_argument(
            '--force', action='store_true',
            help='Autorise le seed hors DEBUG (crée des comptes à mot de passe '
                 'connu — à utiliser en connaissance de cause).')

    @transaction.atomic
    def handle(self, *args, **options):
        slug = options['slug']
        # ERR88 — même garde que seed_demo : comptes à mot de passe connu.
        if not settings.DEBUG and not options.get('force'):
            raise CommandError(
                "seed_demo_company est refusé hors DEBUG : il crée des comptes "
                "à mot de passe connu. Relancez avec --force si vous ciblez "
                "bien un environnement de démo.")

        rng = random.Random(RNG_SEED)
        company, admin, resp = self._ensure_company(slug)

        # Catalogue simulateur + pompage (idempotent, additif) — nécessaire aux
        # devis (NTDMO3) et aux mouvements de stock (NTDMO5).
        call_command('seed_catalogue', company_slug=slug, verbosity=0)

        # Garde d'idempotence : une fois l'historique 12 mois généré, no-op.
        if company.leads.exists() or company.devis.exists():
            self.stdout.write(self.style.WARNING(
                f'Demo company "{slug}" already populated — nothing to do.'))
            return

        self._generate_history(company, admin, resp, rng)

        self.stdout.write(self.style.SUCCESS(
            f'\nRich demo data seeded for "{company.nom}" (slug={slug}).\n'
            f'Logins:  demo_admin_full / {DEMO_PASSWORD}   (administrateur)\n'
            f'         demo_resp_full  / {DEMO_PASSWORD}   (responsable)'))

    # ── Company + profile + users + roles ──────────────────────────────────
    def _ensure_company(self, slug):
        from authentication.models import Company, CustomUser
        from apps.parametres.models import CompanyProfile

        company, _ = Company.objects.get_or_create(
            slug=slug, defaults={'nom': 'TAQINOR Démo (complet)'})
        # NTDMO8 — marque la société comme démo (idempotent).
        if not company.est_demo:
            company.est_demo = True
            company.save(update_fields=['est_demo'])

        profile = CompanyProfile.get(company)
        profile.nom = 'TAQINOR Démo (complet)'
        profile.adresse = '45 Boulevard Mohammed V, Casablanca'
        profile.email = 'demo-full@taqinor.local'
        profile.telephone = '+212 5 22 99 88 77'
        # Identité légale marocaine — placeholders réalistes.
        profile.ice = '002589631000045'
        profile.identifiant_fiscal = '48291057'
        profile.rc = '198453'
        profile.patente = '35201478'
        profile.save()

        admin, created_admin = CustomUser.objects.get_or_create(
            username='demo_admin_full',
            defaults={
                'email': 'demo_admin_full@taqinor.local',
                'role_legacy': CustomUser.ROLE_ADMIN,
                'company': company,
                'is_staff': True,
            })
        if created_admin:
            admin.set_password(DEMO_PASSWORD)
            admin.save()
        if not admin.is_protected:
            admin.is_protected = True
            admin.save(update_fields=['is_protected'])

        resp, created_resp = CustomUser.objects.get_or_create(
            username='demo_resp_full',
            defaults={
                'email': 'demo_resp_full@taqinor.local',
                'role_legacy': CustomUser.ROLE_RESPONSABLE,
                'company': company,
            })
        if created_resp:
            resp.set_password(DEMO_PASSWORD)
            resp.save()

        # Rôles système + types d'activité + niveaux de relance (idempotent).
        call_command('init_roles', verbosity=0)
        self._ensure_activity_scaffolding(company)
        return company, admin, resp

    def _ensure_activity_scaffolding(self, company):
        from apps.records.models import ActivityType
        from apps.ventes.models import FollowupLevel
        for nom, icone, ordre, delai in [
            ('Appel', '📞', 10, 0), ('Email', '✉️', 20, 0),
            ('Réunion', '👥', 30, 0), ('Relance', '📅', 40, 3),
            ('À faire', '✔️', 50, 0),
        ]:
            ActivityType.objects.get_or_create(
                company=company, nom=nom,
                defaults={'icone': icone, 'ordre': ordre,
                          'delai_defaut_jours': delai, 'est_systeme': True})
        for ordre, nom, delai in [
            (1, 'Rappel courtois', 7), (2, 'Relance', 15),
            (3, 'Relance ferme', 30),
        ]:
            FollowupLevel.objects.get_or_create(
                company=company, ordre=ordre,
                defaults={'nom': nom, 'delai_jours': delai})

    # ── 12-month history (extended by NTDMO2-5) ────────────────────────────
    def _generate_history(self, company, admin, resp, rng):
        """Génère l'historique vivant. Étendu par NTDMO2 (leads), NTDMO3
        (devis), NTDMO4 (chantiers/factures), NTDMO5 (SAV/stock)."""
        ctx = {'company': company, 'admin': admin, 'resp': resp, 'rng': rng}
        self._seed_leads(ctx)

    # ── NTDMO2 — leads répartis sur les 6 stages STAGES.py ─────────────────
    # Prénoms/noms/villes marocaines (Faker arrive en NTDMO17, hors de ce lot).
    _NOMS = ['Alaoui', 'Bennani', 'Tazi', 'Chraibi', 'Berrada', 'Idrissi',
             'El Amrani', 'Bouazza', 'Sekkat', 'Benjelloun', 'Fassi', 'Ouazzani',
             'Cherkaoui', 'Lahlou', 'Kettani', 'Bennis', 'Sqalli', 'Alami',
             'Mernissi', 'Belghiti', 'Tahiri', 'Naciri', 'Guerraoui', 'Filali']
    _PRENOMS = ['Karim', 'Salma', 'Omar', 'Fatima-Zahra', 'Youssef', 'Mehdi',
                'Sara', 'Hamid', 'Nadia', 'Rachid', 'Meryem', 'Anas', 'Imane',
                'Hicham', 'Loubna', 'Adil', 'Khadija', 'Yassine']
    _VILLES = ['Casablanca', 'Rabat', 'Marrakech', 'Tanger', 'Fès', 'Agadir',
               'Meknès', 'Oujda', 'Kénitra', 'Béni Mellal', 'Safi', 'El Jadida']
    _MOTIFS_PERTE = ['Prix trop élevé', 'Projet reporté', 'Concurrent choisi',
                     'Budget insuffisant', 'Sans suite']

    def _seed_leads(self, ctx):
        from apps.crm.models import Lead, MotifPerte
        # Clés de stage canoniques — chargées depuis STAGES.py (jamais en dur).
        from apps.crm.stages import (
            COLD, CONTACTED, FOLLOW_UP, NEW, QUOTE_SENT, SIGNED,
        )
        company, rng = ctx['company'], ctx['rng']
        now = timezone.now()

        motifs = [
            MotifPerte.objects.get_or_create(company=company, nom=nom)[0]
            for nom in self._MOTIFS_PERTE
        ]
        canaux = [c.value for c in Lead.Canal]
        priorites = [p.value for p in Lead.Priorite]
        types_inst = [t.value for t in Lead.TypeInstallation]

        # Distribution réaliste (entonnoir) : plus de NEW/CONTACTED récents,
        # moins de SIGNED anciens ; ~40 leads. (stage, count, âge_max_jours).
        plan = [
            (NEW, 12, 45), (CONTACTED, 10, 90), (QUOTE_SENT, 7, 150),
            (FOLLOW_UP, 5, 120), (SIGNED, 4, 300), (COLD, 4, 330),
        ]
        leads = []
        i = 0
        for stage, count, age_max in plan:
            for _ in range(count):
                nom = self._NOMS[i % len(self._NOMS)]
                prenom = self._PRENOMS[i % len(self._PRENOMS)]
                ville = rng.choice(self._VILLES)
                age = rng.randint(0, age_max)
                perdu = stage == COLD
                lead = Lead.objects.create(
                    company=company, nom=nom, prenom=prenom,
                    societe=(f'{nom} Énergie' if i % 3 == 0 else None),
                    telephone=f'+212 6 {rng.randint(10, 99)} '
                              f'{rng.randint(10, 99)} '
                              f'{rng.randint(10, 99)} {rng.randint(10, 99)}',
                    ville=ville, stage=stage, source=Lead.Source.OS_NATIVE,
                    canal=rng.choice(canaux), priorite=rng.choice(priorites),
                    type_installation=rng.choice(types_inst),
                    perdu=perdu,
                    motif_perte=(rng.choice(motifs).nom if perdu else None),
                )
                # date_creation est auto_now_add → réancrée par update().
                created = now - timedelta(days=age)
                Lead.objects.filter(pk=lead.pk).update(date_creation=created)
                # Quelques relances proches à venir (calendrier + alertes).
                if stage in (CONTACTED, FOLLOW_UP) and i % 2 == 0:
                    lead.relance_date = (
                        now + timedelta(days=rng.randint(1, 5))).date()
                    lead.save(update_fields=['relance_date'])
                leads.append(lead)
                i += 1
        ctx['leads'] = leads
