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
from decimal import Decimal

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
        self._seed_devis(ctx)
        self._seed_chantiers_factures(ctx)

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

    # ── NTDMO3 — devis couvrant les 3 modes marché + historique de statuts ──
    @staticmethod
    def _line_price(produit):
        """Prix unitaire robuste (certains produits OSP ont un prix vide)."""
        pv = getattr(produit, 'prix_vente', None)
        if pv and pv > 0:
            return pv
        return Decimal('1500.00')

    def _seed_clients_from_leads(self, ctx):
        """Crée des clients (dont certains liés à des leads) pour les devis."""
        from apps.crm.models import Client
        company, rng, leads = ctx['company'], ctx['rng'], ctx['leads']
        clients = []
        # Réutilise les leads les plus avancés (SIGNED/QUOTE_SENT/FOLLOW_UP).
        avances = [ld for ld in leads if not ld.perdu][:16]
        for idx, ld in enumerate(avances):
            entreprise = bool(ld.societe)
            clients.append(Client.objects.create(
                company=company, nom=ld.nom, prenom=ld.prenom,
                email=f'{ld.prenom}.{ld.nom}@demo.local'.lower().replace(' ', ''),
                telephone=ld.telephone, adresse=f'{ld.ville}',
                type_client=(Client.TypeClient.ENTREPRISE if entreprise
                             else Client.TypeClient.PARTICULIER),
                created_by=ctx['resp'],
            ))
        ctx['clients'] = clients
        _ = rng
        return clients

    def _seed_devis(self, ctx):
        from apps.ventes.models import Devis, LigneDevis
        from apps.ventes.utils.references import create_with_reference
        company, rng, resp = ctx['company'], ctx['rng'], ctx['resp']
        now = timezone.now()

        clients = self._seed_clients_from_leads(ctx)
        leads = [ld for ld in ctx['leads'] if not ld.perdu]
        produits = self._catalogue_index(company)

        # 25 devis : ~40 % acceptés (pipeline convaincant), reste réparti.
        S = Devis.Statut
        statuts = (
            [S.ACCEPTE] * 10 + [S.ENVOYE] * 5 + [S.BROUILLON] * 4
            + [S.REFUSE] * 3 + [S.EXPIRE] * 3)
        modes = ['residentiel', 'industriel', 'agricole']
        signed_resid_batt = 0
        devis_list = []
        for i, statut in enumerate(statuts):
            client = clients[i % len(clients)]
            lead = leads[i % len(leads)] if leads else None
            mode = modes[i % 3]
            avec_batterie = False
            etude = None
            if mode == 'residentiel':
                # ≥3 devis résidentiels signés « Avec batterie » (illustre A1-A3).
                if statut == S.ACCEPTE and signed_resid_batt < 3:
                    avec_batterie = True
                    signed_resid_batt += 1
                lignes = self._lignes_residentiel(produits, avec_batterie)
            elif mode == 'industriel':
                etude = {
                    'mode': 'industriel',
                    'taux_autoconsommation': rng.randint(55, 85),
                    'taux_couverture': rng.randint(40, 70),
                    'economies_annuelles': rng.randint(20000, 90000),
                    'payback_ans': round(rng.uniform(4.0, 7.5), 1),
                }
                lignes = self._lignes_industriel(produits)
            else:  # agricole (pompage)
                debit = rng.randint(8, 40)
                hmt = rng.randint(30, 90)
                etude = {
                    'mode': 'agricole',
                    'pompe_type': 'immergée',
                    'hmt_m': hmt, 'debit_m3h': debit,
                    'm3_jour': debit * 7,
                    'courbe_pompe': [
                        [0, hmt + 20], [debit / 2, hmt + 8], [debit, hmt]],
                }
                lignes = self._lignes_agricole(produits)

            def _make(reference, statut=statut, client=client, lead=lead,
                      etude=etude, lignes=lignes):
                validite = 30 if statut != S.EXPIRE else -20
                dv = Devis.objects.create(
                    company=company, reference=reference, client=client,
                    lead=lead, statut=statut, taux_tva=Decimal('20.00'),
                    remise_globale=Decimal('0'),
                    date_validite=(now.date() + timedelta(days=validite)),
                    etude_params=etude, created_by=resp)
                for produit, designation, qte, pu in lignes:
                    LigneDevis.objects.create(
                        devis=dv, produit=produit, designation=designation,
                        quantite=Decimal(str(qte)), prix_unitaire=pu,
                        remise=Decimal('0'))
                return dv

            devis = create_with_reference(Devis, 'DEV', company, _make)
            # Étale les dates sur 12 mois (≥8 mois couverts pour le dashboard).
            created = now - timedelta(days=15 + i * 14)
            Devis.objects.filter(pk=devis.pk).update(date_creation=created)
            devis_list.append(devis)
        ctx['devis'] = devis_list

    def _catalogue_index(self, company):
        from apps.stock.models import Produit
        produits = list(Produit.objects.filter(company=company))

        def find(*kws):
            for p in produits:
                low = p.nom.lower()
                if any(kw in low for kw in kws):
                    return p
            return produits[0] if produits else None
        return {
            'panneau': find('panneau'),
            'onduleur': find('onduleur', 'inverter'),
            'batterie': find('batterie', 'battery'),
            'pompe': find('pompe', 'pompage', 'osp'),
            'variateur': find('variateur', 'veichi', 'vfd'),
            'accessoire': find('câble', 'cable', 'accessoire', 'structure'),
        }

    def _lignes_residentiel(self, produits, avec_batterie):
        lignes = [
            (produits['panneau'], produits['panneau'].nom, 12,
             self._line_price(produits['panneau'])),
            (produits['onduleur'], produits['onduleur'].nom, 1,
             self._line_price(produits['onduleur'])),
        ]
        if avec_batterie and produits['batterie']:
            lignes.append((produits['batterie'], produits['batterie'].nom, 1,
                           self._line_price(produits['batterie'])))
        return lignes

    def _lignes_industriel(self, produits):
        return [
            (produits['panneau'], produits['panneau'].nom, 40,
             self._line_price(produits['panneau'])),
            (produits['onduleur'], produits['onduleur'].nom, 2,
             self._line_price(produits['onduleur'])),
        ]

    def _lignes_agricole(self, produits):
        pompe = produits['pompe'] or produits['panneau']
        var = produits['variateur'] or produits['onduleur']
        return [
            (pompe, f'Pompe solaire — {pompe.nom}', 1, self._line_price(pompe)),
            (var, f'Variateur — {var.nom}', 1, self._line_price(var)),
        ]

    # ── NTDMO4 — chaîne chantier→facture→paiement + balance âgée vivante ────
    @staticmethod
    def _devis_total_ttc(devis):
        from apps.ventes.models import LigneDevis
        total_ht = Decimal('0')
        for li in LigneDevis.objects.filter(devis=devis):
            total_ht += (li.quantite or 0) * (li.prix_unitaire or 0)
        return (total_ht * Decimal('1.2')).quantize(Decimal('0.01'))

    def _seed_chantiers_factures(self, ctx):
        from apps.ventes.models import Devis, Facture, LigneFacture, Paiement
        from apps.ventes.utils.references import create_with_reference
        from apps.installations import services as inst_services
        from apps.installations.models import Installation
        company, admin = ctx['company'], ctx['admin']
        now = timezone.now()
        today = now.date()

        acceptes = [d for d in ctx['devis'] if d.statut == Devis.Statut.ACCEPTE]
        # Décalages d'échéance dépassée → tranches d'ancienneté 0-30/31-60/
        # 61-90/90+ toutes peuplées (critère balance âgée).
        overdue_offsets = [15, 50, 75, 100]
        chantiers = []
        factures = []
        for j, devis in enumerate(acceptes):
            # Chantier via le service existant (jamais de duplication).
            chantier, _created = inst_services.create_installation_from_devis(
                devis, admin, company)
            if chantier is not None:
                pose = today - timedelta(days=60 + j * 12)
                updates = {'date_creation': now - timedelta(days=70 + j * 12),
                           'date_pose_reelle': pose}
                # ~la moitié des chantiers réceptionnés (Installation en aval).
                if j % 2 == 0:
                    updates['statut'] = Installation.Statut.RECEPTIONNE
                    updates['date_reception'] = pose + timedelta(days=5)
                Installation.objects.filter(pk=chantier.pk).update(**updates)
                chantiers.append(chantier)

            total = self._devis_total_ttc(devis)
            # Mix : payée à temps / en retard non payée / partiellement réglée.
            bucket = j % 4
            if bucket == 0:
                statut, echeance, paye = (
                    Facture.Statut.PAYEE, today - timedelta(days=20), total)
            elif bucket == 2:
                statut = Facture.Statut.EMISE
                echeance = today - timedelta(days=overdue_offsets[j % 4])
                paye = (total * Decimal('0.4')).quantize(Decimal('0.01'))
            else:
                statut = Facture.Statut.EMISE
                echeance = today - timedelta(days=overdue_offsets[j % 4])
                paye = Decimal('0')

            def _make_fac(reference, devis=devis, statut=statut,
                          echeance=echeance):
                fac = Facture.objects.create(
                    company=company, reference=reference, client=devis.client,
                    devis=devis, statut=statut, taux_tva=Decimal('20.00'),
                    date_echeance=echeance, created_by=admin)
                for li in devis.lignes.all():
                    LigneFacture.objects.create(
                        facture=fac, produit=li.produit,
                        designation=li.designation, quantite=li.quantite,
                        prix_unitaire=li.prix_unitaire, remise=li.remise)
                return fac

            facture = create_with_reference(Facture, 'FAC', company, _make_fac)
            emise = echeance - timedelta(days=30)
            Facture.objects.filter(pk=facture.pk).update(date_emission=emise)
            if paye > 0:
                Paiement.objects.create(
                    company=company, facture=facture, montant=paye,
                    date_paiement=emise + timedelta(days=3),
                    mode=Paiement.Mode.VIREMENT, created_by=admin,
                    statut=Paiement.Statut.ENCAISSE)
            factures.append(facture)
        ctx['chantiers'] = chantiers
        ctx['factures'] = factures
