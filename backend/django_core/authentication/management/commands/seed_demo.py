"""
Seed realistic demo data so no screen is empty on first launch.

Idempotent — safe to run twice (skips if the demo company already has data).

Run:
  docker compose exec django_core python manage.py seed_demo

Creates:
  - Company "TAQINOR Démo" + CompanyProfile
  - Users  : demo_admin / Demo@2026!  (admin)
             demo_resp  / Demo@2026!  (responsable)
  - 3 catégories, 2 fournisseurs, 8 produits (dont 2 sous le seuil d'alerte)
  - 5 clients
  - 5 devis répartis sur les statuts (brouillon, envoyé, accepté, refusé, expiré)
  - 1 bon de commande confirmé (depuis le devis accepté) + 1 en attente
  - 2 factures (1 émise, 1 payée)
  - Mouvements de stock d'entrée initiale
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Seed demo company with realistic data (idempotent).'

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company, CustomUser
        from apps.parametres.models import CompanyProfile
        from apps.stock.models import (
            Categorie, Fournisseur, Produit, MouvementStock,
        )
        from apps.crm.models import Client
        from apps.ventes.models import (
            Devis, LigneDevis, BonCommande, Facture, LigneFacture,
        )

        company, created = Company.objects.get_or_create(
            slug='taqinor-demo',
            defaults={'nom': 'TAQINOR Démo'},
        )
        if not created and company.produits.exists():
            self.stdout.write(self.style.WARNING(
                'Demo company already seeded — nothing to do.'
            ))
            return

        profile = CompanyProfile.get(company)
        profile.nom = 'TAQINOR Démo'
        profile.adresse = '12 Boulevard Zerktouni, Casablanca'
        profile.email = 'demo@taqinor.local'
        profile.telephone = '+212 5 22 00 00 00'
        profile.save()

        # ── Users ──────────────────────────────────────────────────────
        admin, was_created = CustomUser.objects.get_or_create(
            username='demo_admin',
            defaults={
                'email': 'demo_admin@taqinor.local',
                'role_legacy': CustomUser.ROLE_ADMIN,
                'company': company,
                'is_staff': True,
            },
        )
        if was_created:
            admin.set_password('Demo@2026!')
            admin.save()

        resp, was_created = CustomUser.objects.get_or_create(
            username='demo_resp',
            defaults={
                'email': 'demo_resp@taqinor.local',
                'role_legacy': CustomUser.ROLE_RESPONSABLE,
                'company': company,
            },
        )
        if was_created:
            resp.set_password('Demo@2026!')
            resp.save()

        # Create per-company system roles and attach them to the users
        call_command('init_roles')

        # ── Stock ──────────────────────────────────────────────────────
        cat_panneaux = Categorie.objects.create(
            company=company, nom='Panneaux solaires',
            description='Modules photovoltaïques')
        cat_onduleurs = Categorie.objects.create(
            company=company, nom='Onduleurs',
            description='Onduleurs et micro-onduleurs')
        cat_access = Categorie.objects.create(
            company=company, nom='Accessoires',
            description='Câblage, fixations, connectique')

        f_sunpro = Fournisseur.objects.create(
            company=company, nom='SunPro Maroc',
            contact_personne='Hassan Benjelloun',
            email='contact@sunpro.ma', telephone='+212 5 22 11 22 33',
            adresse='Zone industrielle Ain Sebaâ, Casablanca')
        f_electra = Fournisseur.objects.create(
            company=company, nom='Electra Distribution',
            contact_personne='Nadia El Fassi',
            email='ventes@electra.ma', telephone='+212 5 37 44 55 66',
            adresse='Quartier industriel, Salé')

        produits_data = [
            # nom, sku, cat, fournisseur, achat, vente, stock, seuil, tva
            ('Panneau mono 450W', 'PAN-450M', cat_panneaux, f_sunpro,
             '1450.00', '1890.00', 120, 20, '20.00'),
            ('Panneau mono 550W', 'PAN-550M', cat_panneaux, f_sunpro,
             '1780.00', '2290.00', 85, 15, '20.00'),
            ('Panneau poly 330W', 'PAN-330P', cat_panneaux, f_sunpro,
             '980.00', '1290.00', 8, 10, '20.00'),          # sous le seuil
            ('Onduleur hybride 5kW', 'OND-5KH', cat_onduleurs, f_electra,
             '8900.00', '11500.00', 25, 5, '20.00'),
            ('Onduleur réseau 10kW', 'OND-10KR', cat_onduleurs, f_electra,
             '14500.00', '18900.00', 12, 3, '20.00'),
            ('Micro-onduleur 800W', 'OND-800M', cat_onduleurs, f_electra,
             '1100.00', '1490.00', 2, 6, '20.00'),           # sous le seuil
            ('Câble solaire 6mm² (100m)', 'CAB-6MM', cat_access, f_electra,
             '850.00', '1190.00', 40, 10, '20.00'),
            ('Kit fixation toiture', 'FIX-KIT', cat_access, f_sunpro,
             '320.00', '450.00', 65, 15, '20.00'),
        ]
        produits = {}
        for nom, sku, cat, four, achat, vente, stock, seuil, tva in produits_data:
            p = Produit.objects.create(
                company=company, nom=nom, sku=sku,
                categorie=cat, fournisseur=four,
                prix_achat=Decimal(achat), prix_vente=Decimal(vente),
                quantite_stock=stock, seuil_alerte=seuil, tva=Decimal(tva),
            )
            produits[sku] = p
            MouvementStock.objects.create(
                produit=p,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                quantite=stock, quantite_avant=0, quantite_apres=stock,
                reference='SEED-INIT',
                note='Stock initial (données de démonstration)',
                created_by=admin,
            )

        # ── Clients ────────────────────────────────────────────────────
        clients_data = [
            ('Alaoui', 'Karim', 'k.alaoui@gmail.com', '+212 6 61 11 22 33',
             'Hay Riad, Rabat'),
            ('Bennani', 'Salma', 's.bennani@menara.ma', '+212 6 62 22 33 44',
             'Maarif, Casablanca'),
            ('Tazi', 'Omar', 'omar.tazi@outlook.com', '+212 6 63 33 44 55',
             'Guéliz, Marrakech'),
            ('Chraibi', 'Fatima-Zahra', 'fz.chraibi@gmail.com',
             '+212 6 64 44 55 66', 'Centre-ville, Tanger'),
            ('Berrada', 'Youssef', 'y.berrada@yahoo.fr', '+212 6 65 55 66 77',
             'Agdal, Rabat'),
        ]
        clients = []
        for nom, prenom, email, tel, adresse in clients_data:
            clients.append(Client.objects.create(
                company=company, nom=nom, prenom=prenom, email=email,
                telephone=tel, adresse=adresse,
            ))

        # ── Devis (un par statut) ──────────────────────────────────────
        today = timezone.now().date()

        def make_devis(ref, client, statut, lignes, validite_days=30):
            devis = Devis.objects.create(
                company=company, reference=ref, client=client, statut=statut,
                taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
                date_validite=today + timedelta(days=validite_days),
                created_by=resp,
            )
            for sku, qte in lignes:
                p = produits[sku]
                LigneDevis.objects.create(
                    devis=devis, produit=p, designation=p.nom,
                    quantite=Decimal(qte), prix_unitaire=p.prix_vente,
                    remise=Decimal('0'),
                )
            return devis

        make_devis('DEV-DEMO-0001', clients[0], Devis.Statut.BROUILLON,
                   [('PAN-450M', '12'), ('OND-5KH', '1'), ('FIX-KIT', '3')])
        make_devis('DEV-DEMO-0002', clients[1], Devis.Statut.ENVOYE,
                   [('PAN-550M', '20'), ('OND-10KR', '1'), ('CAB-6MM', '2')])
        devis_accepte = make_devis(
            'DEV-DEMO-0003', clients[2], Devis.Statut.ACCEPTE,
            [('PAN-450M', '8'), ('OND-5KH', '1'), ('FIX-KIT', '2')])
        make_devis('DEV-DEMO-0004', clients[3], Devis.Statut.REFUSE,
                   [('PAN-330P', '6'), ('OND-800M', '6')])
        make_devis('DEV-DEMO-0005', clients[4], Devis.Statut.EXPIRE,
                   [('PAN-550M', '10'), ('CAB-6MM', '1')], validite_days=-15)

        # ── Bons de commande ───────────────────────────────────────────
        bc_confirme = BonCommande.objects.create(
            company=company, reference='BC-DEMO-0001',
            devis=devis_accepte, client=devis_accepte.client,
            statut=BonCommande.Statut.CONFIRME,
            date_livraison_prevue=today + timedelta(days=10),
        )
        BonCommande.objects.create(
            company=company, reference='BC-DEMO-0002',
            client=clients[1],
            statut=BonCommande.Statut.EN_ATTENTE,
            date_livraison_prevue=today + timedelta(days=21),
        )

        # ── Factures ───────────────────────────────────────────────────
        def make_facture(ref, client, statut, lignes, bc=None, echeance=30):
            facture = Facture.objects.create(
                company=company, reference=ref, client=client, statut=statut,
                bon_commande=bc, taux_tva=Decimal('20.00'),
                date_echeance=today + timedelta(days=echeance),
                created_by=resp,
            )
            for sku, qte in lignes:
                p = produits[sku]
                LigneFacture.objects.create(
                    facture=facture, produit=p, designation=p.nom,
                    quantite=Decimal(qte), prix_unitaire=p.prix_vente,
                    remise=Decimal('0'),
                )
            return facture

        make_facture('FAC-DEMO-0001', devis_accepte.client,
                     Facture.Statut.EMISE,
                     [('PAN-450M', '8'), ('OND-5KH', '1'), ('FIX-KIT', '2')],
                     bc=bc_confirme)
        make_facture('FAC-DEMO-0002', clients[0], Facture.Statut.PAYEE,
                     [('CAB-6MM', '3'), ('FIX-KIT', '5')], echeance=-5)

        self.stdout.write(self.style.SUCCESS(
            '\nDemo data seeded for "TAQINOR Démo".\n'
            'Logins:  demo_admin / Demo@2026!   (administrateur)\n'
            '         demo_resp  / Demo@2026!   (responsable)'
        ))
