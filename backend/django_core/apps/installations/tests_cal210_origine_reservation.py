"""CAL210 — trace la réservation de stock jusqu'au calepinage qui l'a
dimensionnée.

Couvre :
  * une réservation posée pour un chantier dont le devis a un calepinage
    RETENU porte ``origine_calepinage_id`` — sans aucune nouvelle mécanique de
    réservation (comportement quantitatif inchangé, patron
    ``tests_reservation.py``) ;
  * un chantier sans calepinage garde ``origine_calepinage_id = None``
    (comportement historique) ;
  * ré-amorcer (``seed_reservations`` rejoué) reste idempotent et backfill
    l'origine sur une réservation existante sans la retoucher une fois posée.

Run :
    python manage.py test apps.installations.tests_cal210_origine_reservation -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.variantes import bascule_autorisee
from apps.crm.models import Client, Lead
from apps.installations.services import (
    create_installation_from_devis, seed_reservations,
)
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    return Company.objects.create(nom=f'CAL210 Co {n}', slug=f'cal210-co-{n}')


def make_produit(company, stock=20):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=f'Panneau {n}', sku=f'SKU-CAL210-{n}',
        prix_vente=Decimal('100'), quantite_stock=stock)


def make_devis_with_lines(company, lines):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='CAL210',
        email=f'cal210-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='CAL210', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-CAL210-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    for produit, qte in lines:
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal(str(qte)), prix_unitaire=Decimal('100'))
    return client, devis


class TestOrigineReservation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='cal210_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.panneau = make_produit(self.company)

    def test_reservation_sans_calepinage_garde_origine_none(self):
        client_obj, devis = make_devis_with_lines(
            self.company, [(self.panneau, 6)])
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        resa = inst.reservations.get(produit=self.panneau)
        self.assertIsNone(resa.origine_calepinage_id)
        # Comportement quantitatif strictement inchangé.
        self.assertEqual(resa.quantite, 6)
        self.assertTrue(resa.active and not resa.consomme)

    def test_reservation_cite_le_calepinage_retenu(self):
        client_obj, devis = make_devis_with_lines(
            self.company, [(self.panneau, 8)])
        calepinage = Calepinage.objects.create(
            company=self.company, client=client_obj, devis=devis)
        with bascule_autorisee():
            CalepinageVariante.objects.create(
                company=self.company, calepinage=calepinage, nom='V1',
                retenue=True,
                resultat={'pose': {'kwc': 5.76, 'total_modules': 8}})

        inst, _ = create_installation_from_devis(devis, self.user, self.company)

        resa = inst.reservations.get(produit=self.panneau)
        self.assertEqual(resa.origine_calepinage_id, calepinage.id)
        # La quantité réservée reste celle du BOM — aucune double mécanique.
        self.assertEqual(resa.quantite, 8)

    def test_reamorcage_est_idempotent_et_backfill_l_origine(self):
        client_obj, devis = make_devis_with_lines(
            self.company, [(self.panneau, 3)])
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        resa = inst.reservations.get(produit=self.panneau)
        self.assertIsNone(resa.origine_calepinage_id)

        # Un calepinage retenu apparaît APRÈS coup (conception faite plus
        # tard) : le prochain réamorçage backfill l'origine sans dupliquer ni
        # changer la quantité.
        calepinage = Calepinage.objects.create(
            company=self.company, client=client_obj, devis=devis)
        with bascule_autorisee():
            CalepinageVariante.objects.create(
                company=self.company, calepinage=calepinage, nom='V1',
                retenue=True,
                resultat={'pose': {'kwc': 2.16, 'total_modules': 3}})
        seed_reservations(inst)
        seed_reservations(inst)

        self.assertEqual(
            inst.reservations.filter(produit=self.panneau).count(), 1)
        resa.refresh_from_db()
        self.assertEqual(resa.origine_calepinage_id, calepinage.id)
        self.assertEqual(resa.quantite, 3)
