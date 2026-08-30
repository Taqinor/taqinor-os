# -*- coding: utf-8 -*-
"""QJR221 — la complétion PVHEAL hérite du GAMME du devis.

TEST ROUGE D'ABORD : ``domain/composition._completer_kit_residentiel`` appelait
``pipeline.composer(IntentionComposition(...))`` SANS ``gamme_nom_devis``, donc
``carte_marques_composition(company, None)`` résolvait la carte de marques PAR
DÉFAUT de la société — pendant que la moitié CHIRURGICALE de la même resynchro
(``_pick_product(..., gamme=gamme_nom(devis))``) utilisait la VRAIE gamme du
devis. Un devis Premium d'une société à ``deux_gammes=True`` se faisait donc
compléter avec les marques de l'AUTRE gamme.

Ne mord que sur ``deux_gammes=True`` : le chemin mono-gamme est byte-identique,
et c'est épinglé ici.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr221_pvheal_gamme -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain import composition as _composition
from apps.ventes.domain.catalogue import carte_marques_composition
from apps.ventes.models import Devis, ParametresGammes
from apps.ventes.tests.test_pv18_sync_layout import make_company

User = get_user_model()

MARQUE_ESSENTIELLE = 'AlphaSteel'
MARQUE_PREMIUM = 'OmegaSteel'


class _Base(TestCase):

    DEUX_GAMMES = True

    def setUp(self):
        self.company = make_company('qjr221-co-%s' % int(self.DEUX_GAMMES))
        self.user = User.objects.create_user(
            username='qjr221user-%s' % int(self.DEUX_GAMMES), password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR221')
        ParametresGammes.objects.update_or_create(
            company=self.company,
            defaults={
                'deux_gammes': self.DEUX_GAMMES,
                'nom_essentielle': ParametresGammes.SLOT_ESSENTIELLE,
                'nom_premium': ParametresGammes.SLOT_PREMIUM,
                'marques': {
                    ParametresGammes.SLOT_ESSENTIELLE: {
                        'structure_acier': MARQUE_ESSENTIELLE},
                    ParametresGammes.SLOT_PREMIUM: {
                        'structure_acier': MARQUE_PREMIUM},
                },
            })
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W',
            sku='QJR221-PAN', prix_vente=Decimal('1100'),
            prix_achat=Decimal('1'), quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 5kW',
            sku='QJR221-ONDR', prix_vente=Decimal('14000'),
            prix_achat=Decimal('1'), quantite_stock=100)

    def _devis(self, gamme):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR221-%s' % (gamme or 'X'),
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user, taux_tva=Decimal('20'),
            etude_params={'gamme': {'nom': gamme}} if gamme else None)
        devis.lignes.create(
            produit=self.panneau, designation=self.panneau.nom,
            quantite=Decimal('12'), prix_unitaire=self.panneau.prix_vente,
            remise=Decimal('0'), ordre=1)
        devis.lignes.create(
            produit=self.onduleur, designation=self.onduleur.nom,
            quantite=Decimal('1'), prix_unitaire=self.onduleur.prix_vente,
            remise=Decimal('0'), ordre=2)
        return devis

    def _intention_de_completion(self, devis):
        """La ``IntentionComposition`` que la complétion construit VRAIMENT.

        On espionne ``composer`` (importé dans le namespace du module) : ce qui
        nous intéresse est ce que la complétion DEMANDE, pas ce que le
        catalogue rend."""
        vues = []
        vrai = _composition.composer

        def _espion(intention):
            vues.append(intention)
            return []

        _composition.composer = _espion
        self.addCleanup(setattr, _composition, 'composer', vrai)
        _composition._completer_kit_residentiel(
            devis, kwc=6.6, watt=550, nb_panneaux=12,
            avec_batterie=False, avertissements=[])
        self.assertTrue(vues, 'la complétion n\'a composé aucune vue')
        return vues[0]


class SocieteADeuxGammes(_Base):
    """LE ROUGE : la complétion partait sans gamme."""

    DEUX_GAMMES = True

    def test_l_intention_porte_la_gamme_du_devis(self):
        intention = self._intention_de_completion(self._devis('Premium'))
        self.assertEqual(intention.gamme_nom_devis, 'Premium')

    def test_la_carte_de_marques_diverge_vraiment(self):
        """La preuve que le défaut mordait : sans gamme, la carte est l'AUTRE."""
        self.assertEqual(
            carte_marques_composition(self.company, 'Premium'),
            {'structure_acier': MARQUE_PREMIUM})
        self.assertEqual(
            carte_marques_composition(self.company, None),
            {'structure_acier': MARQUE_ESSENTIELLE})

    def test_un_devis_essentielle_garde_sa_carte(self):
        intention = self._intention_de_completion(self._devis('Essentielle'))
        self.assertEqual(intention.gamme_nom_devis, 'Essentielle')
        self.assertEqual(
            carte_marques_composition(self.company, intention.gamme_nom_devis),
            {'structure_acier': MARQUE_ESSENTIELLE})

    def test_un_devis_sans_gamme_retombe_sur_essentielle(self):
        intention = self._intention_de_completion(self._devis(None))
        self.assertEqual(intention.gamme_nom_devis, '')
        self.assertEqual(
            carte_marques_composition(self.company, ''),
            {'structure_acier': MARQUE_ESSENTIELLE})


class SocieteMonoGamme(_Base):
    """Non-régression : le chemin mono-gamme est byte-identique."""

    DEUX_GAMMES = False

    def test_la_carte_est_la_meme_avec_ou_sans_gamme(self):
        devis = self._devis('Premium')
        intention = self._intention_de_completion(devis)
        self.assertEqual(intention.gamme_nom_devis, 'Premium')
        self.assertEqual(
            carte_marques_composition(self.company, 'Premium'),
            carte_marques_composition(self.company, None))
