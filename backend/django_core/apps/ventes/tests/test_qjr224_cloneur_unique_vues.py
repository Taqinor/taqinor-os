# -*- coding: utf-8 -*-
"""QJR224 — ``/variante`` et ``/reviser`` clonent par ``cloner_lignes``.

TEST ROUGE D'ABORD : la garantie « un seul cloneur » de QJR116 n'était pas
valable dans tout le dépôt. Les DEUX chemins de copie au niveau VUE recopiaient
à la main leur liste de champs et divergeaient déjà de ``CHAMPS_CLONES`` en
oubliant ``lot`` — une variante (ou une révision) d'un devis à lots PERDAIT ses
lots.

Ce n'est PAS un appel direct de ``cloner_lignes`` en remplacement : les deux
vues ont leur propre mise à l'échelle de quantité. La copie des CHAMPS passe
par le cloneur ; l'ÉCHELLE reste à la vue (``remplacements``).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr224_cloneur_unique_vues -v 2
"""
from decimal import Decimal

from rest_framework.test import APIClient, APITestCase

from apps.ventes.domain.lignes import CHAMPS_CLONES
from apps.ventes.models import Devis, LotDevis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

LIGNES = [
    ('Onduleur réseau Huawei 10kW', '1', '11700'),
    ('Panneau mono 550W', '14', '1100'),
    ('Installation', '1', '4000'),
]


class _Base(APITestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.source = make_devis(
            self.company, self.user, self.client_obj, LIGNES,
            reference='DEV-QJR224-0001')
        self.lot = LotDevis.objects.create(
            company=self.company, devis=self.source, nom_lot='Villa A',
            adresse_site='Bouskoura', ordre=1)
        for ligne in self.source.lignes.all():
            ligne.lot = self.lot
            ligne.variante = 'avec' if ligne.designation.startswith(
                'Panneau') else ''
            ligne.optionnelle = ligne.designation == 'Installation'
            ligne.quantite_manuelle = ligne.designation.startswith('Panneau')
            ligne.prix_manuel = ligne.designation == 'Installation'
            ligne.save(update_fields=['lot', 'variante', 'optionnelle',
                                      'quantite_manuelle', 'prix_manuel'])
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _panneau(self, devis):
        return devis.lignes.get(designation='Panneau mono 550W')


class CheminVariante(_Base):

    def _variantes(self):
        resp = self.api.post(
            '/api/django/ventes/devis/%s/dupliquer-variante/' % self.source.id,
            {'variante_pct': 20}, format='json')
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))
        return [Devis.objects.get(pk=item['id']) for item in resp.data]

    def test_les_lots_sont_recrees_sur_chaque_variante(self):
        """LE ROUGE : la variante perdait ses lots."""
        for variante in self._variantes():
            with self.subTest(reference=variante.reference):
                lots = list(variante.lots.all())
                self.assertEqual(len(lots), 1, lots)
                self.assertEqual(lots[0].nom_lot, 'Villa A')
                self.assertNotEqual(lots[0].pk, self.lot.pk)
                for ligne in variante.lignes.all():
                    self.assertEqual(ligne.lot_id, lots[0].pk)

    def test_les_echelles_de_quantite_sont_inchangees(self):
        """Non-régression : 0,8 / 1,0 / 1,2 au centime, plancher compris."""
        source_qte = self._panneau(self.source).quantite
        quantites = sorted(self._panneau(v).quantite
                           for v in self._variantes())
        self.assertEqual(quantites, [
            (source_qte * Decimal('0.8')).quantize(Decimal('0.01')),
            source_qte,
            (source_qte * Decimal('1.2')).quantize(Decimal('0.01')),
        ])

    def test_quantite_manuelle_nest_pas_recopiee(self):
        """QJR84 conservé : la quantité vient d'être mise à l'échelle."""
        for variante in self._variantes():
            with self.subTest(reference=variante.reference):
                self.assertFalse(self._panneau(variante).quantite_manuelle)

    def test_les_autres_marqueurs_suivent(self):
        for variante in self._variantes():
            with self.subTest(reference=variante.reference):
                panneau = self._panneau(variante)
                self.assertEqual(panneau.variante, 'avec')
                pose = variante.lignes.get(designation='Installation')
                self.assertTrue(pose.optionnelle)
                self.assertTrue(pose.prix_manuel)


class CheminReviser(_Base):

    def _reviser(self):
        resp = self.api.post(
            '/api/django/ventes/devis/%s/reviser/' % self.source.id,
            {}, format='json')
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))
        return Devis.objects.get(pk=resp.data['id'])

    def test_les_lots_sont_recrees(self):
        """LE ROUGE : la révision perdait ses lots."""
        revision = self._reviser()
        lots = list(revision.lots.all())
        self.assertEqual(len(lots), 1, lots)
        self.assertEqual(lots[0].nom_lot, 'Villa A')
        self.assertNotEqual(lots[0].pk, self.lot.pk)

    def test_la_revision_repart_du_devis_tel_quel(self):
        """QJR84 : marqueurs D12 compris — c'est ce que CHAMPS_CLONES recopie."""
        revision = self._reviser()
        panneau = self._panneau(revision)
        self.assertEqual(panneau.quantite, self._panneau(self.source).quantite)
        self.assertTrue(panneau.quantite_manuelle)
        self.assertEqual(panneau.variante, 'avec')
        pose = revision.lignes.get(designation='Installation')
        self.assertTrue(pose.prix_manuel)
        self.assertTrue(pose.optionnelle)


class LeJeuDeChampsEstDERIVE(_Base):
    """La garde : un champ ajouté à ``CHAMPS_CLONES`` sans être cloné ROUGIT."""

    def test_chaque_champ_clone_arrive_sur_la_revision(self):
        revision = self._reviser_source()
        source_par_designation = {
            li.designation: li for li in self.source.lignes.all()}
        # ``lot`` est re-résolu (jumeau), ``produit``/``devis`` sont des FK
        # d'objet : on compare les autres champ par champ.
        a_part = {'lot'}
        for ligne in revision.lignes.all():
            origine = source_par_designation[ligne.designation]
            for champ in CHAMPS_CLONES:
                if champ in a_part:
                    continue
                with self.subTest(designation=ligne.designation, champ=champ):
                    self.assertEqual(getattr(ligne, champ),
                                     getattr(origine, champ))

    def _reviser_source(self):
        resp = self.api.post(
            '/api/django/ventes/devis/%s/reviser/' % self.source.id,
            {}, format='json')
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))
        return Devis.objects.get(pk=resp.data['id'])
