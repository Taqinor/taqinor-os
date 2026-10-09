"""APRF23 — « Ma file » : ``devis_expirant_bientot`` ne lit que les devis
ENVOYÉS de la portée qui expirent avant la limite (filtre SQL de
``ventes.selectors.devis_envoyes_expirant``, date effective ACRM29, totaux
préchargés) ; +40 leads / +12 devis non concernés n'ajoutent aucune requête,
et la sortie est celle d'avant (oracle recopié ci-dessous).

Test-du-test : retirer le filtre de statut SQL ⇒ le SELECT devis ne le porte
plus (test_select_porte_le_statut) ; revenir au ``prefetch_related('devis')``
⇒ requêtes croissantes (test_requetes_plates).
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from authentication.models import Company
from core.dates import aujourd_hui_local
from apps.crm import selectors
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


def _ancien(company, today, dans_jours=7):
    """Oracle : l'algorithme d'avant APRF23 (tous les devis, filtres Python)."""
    from apps.ventes.selectors import date_validite_effective
    limite = today + datetime.timedelta(days=dans_jours)
    out = []
    for lead in Lead.objects.filter(company=company, is_archived=False):
        for devis in lead.devis.all():
            if devis.statut != 'envoye':
                continue
            exp = date_validite_effective(devis)
            if exp is None or exp > limite:
                continue
            out.append({
                'devis_id': devis.id, 'reference': devis.reference,
                'lead_id': lead.id,
                'lead_nom': f'{lead.nom} {lead.prenom or ""}'.strip(),
                'date_expiration': exp, 'total_ttc': str(devis.total_ttc)})
    out.sort(key=lambda d: (d['date_expiration'], d['reference']))
    return out


class MaFileExpirantTests(TestCase):

    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ADMIN_PERMISSIONS
        self.company = Company.objects.create(
            nom='APRF23 Solaire', slug='aprf23-file')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Administrateur',
            defaults={'permissions': ADMIN_PERMISSIONS, 'est_systeme': True})
        self.user = User.objects.create_user(
            username='aprf23-admin', password='x', company=self.company,
            role=role, role_legacy='admin')
        self.client_c = Client.objects.create(
            company=self.company, nom='Client', prenom='23')
        self.today = aujourd_hui_local()
        self.n = 0

    def _devis(self, lead, statut, validite=None, cree_il_y_a=None):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-APRF23-{self.n:04d}',
            client=self.client_c, lead=lead, statut=statut,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user, date_validite=validite)
        if cree_il_y_a is not None:
            Devis.objects.filter(pk=devis.pk).update(
                date_creation=timezone.now()
                - datetime.timedelta(days=cree_il_y_a))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku=f'APRF23-{self.n}',
            prix_vente=Decimal('1000'), quantite_stock=10)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau',
            quantite=Decimal('2'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        return devis

    def _lead(self, nom='Lead'):
        return Lead.objects.create(company=self.company, nom=nom,
                                   owner=self.user)

    def _jeu_concerne(self):
        a = self._lead('Alpha')
        self._devis(a, 'envoye', validite=self.today + datetime.timedelta(
            days=3))
        b = self._lead('Beta')
        # sans date_validite : création il y a 40 j ⇒ échéance effective
        # passée (validité par défaut) — ACRM29.
        self._devis(b, 'envoye', cree_il_y_a=40)

    def _bruit(self):
        for i in range(40):
            self._lead(f'Bruit {i}')
        leads = list(Lead.objects.filter(company=self.company)[:12])
        for i, lead in enumerate(leads):
            statut = ('brouillon', 'accepte', 'refuse')[i % 3]
            self._devis(lead, statut, validite=self.today)
        # envoyés mais lointains : non concernés
        self._devis(leads[0], 'envoye', validite=self.today
                    + datetime.timedelta(days=60))

    def _requetes(self):
        with CaptureQueriesContext(connection) as ctx:
            res = selectors.devis_expirant_bientot(
                self.company, self.user, today=self.today)
        return len(ctx.captured_queries), res, ctx.captured_queries

    def test_requetes_plates(self):
        self._jeu_concerne()
        self._requetes()  # échauffement (profil société créé au 1er accès)
        avant, res_avant, _ = self._requetes()
        self._bruit()
        apres, res_apres, _ = self._requetes()
        self.assertEqual(apres, avant)
        self.assertEqual(len(res_avant), 2)
        self.assertEqual(res_apres, res_avant)

    def test_meme_sortie_qu_avant(self):
        self._jeu_concerne()
        self._bruit()
        _, res, _ = self._requetes()
        self.assertEqual(res, _ancien(self.company, self.today))

    def test_select_porte_le_statut(self):
        self._jeu_concerne()
        _, _, requetes = self._requetes()
        sql_devis = [q['sql'] for q in requetes
                     if 'FROM "ventes_devis"' in q['sql']]
        self.assertTrue(sql_devis)
        self.assertIn('"ventes_devis"."statut" =', sql_devis[0])

    def test_ma_file_items(self):
        self._jeu_concerne()
        items = selectors.ma_file_commercial_items(
            self.company, self.user, today=self.today)
        self.assertEqual(
            sum(1 for i in items if i['kind'] == 'devis_expire'), 2)
