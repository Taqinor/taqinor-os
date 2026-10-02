"""ERR-QJR570 (D-QJR5-4) — la PROVENANCE d'une ligne (composée par le moteur /
ajoutée à la main) survit à l'enregistrement.

Une recomposition (Auto-remplir / Appliquer cette taille / Recalculer)
remplace les lignes posées par le moteur et garde celles que le vendeur a
ajoutées à la main. Sans marqueur PERSISTANT, un produit ajouté à la main,
enregistré puis rouvert, était pris pour une ligne composée et remplacé.
``LigneDevis.ligne_composee`` : True (moteur) / False (main) / None (inconnue).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_err_qjr570_ligne_composee"
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit
from apps.ventes.domain.lignes import CHAMPS_CLONES, CHAMPS_LIGNE
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

COMPO_URL = '/api/django/ventes/devis/composition/'

#: Le kit minimal qui compose (même catalogue que STKCAT7).
CATALOGUE = [
    ('Panneau Canadien Solar 710W', '1450'),
    ('Onduleur réseau Huawei 5kW Monophasé', '14000'),
    ('Onduleur hybride Deye 5kW Monophasé', '17000'),
    ('Structures acier', '500'),
    ('Structures aluminium', '850'),
    ('Socles', '80'),
    ('Transport', '1000'),
]


class _Base(TestCase):

    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = ProduitFactory(company=self.company)
        self.devis = DevisFactory(company=self.company)


class ReplaceLinesPersisteLaProvenance(_Base):

    def _ligne(self, **extra):
        corps = {'produit': self.produit.id, 'quantite': '1',
                 'prix_unitaire': '1000'}
        corps.update(extra)
        return corps

    def _replace(self, lignes):
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            {'lignes': lignes}, format='json')

    def test_true_false_none_persistent(self):
        r = self._replace([
            self._ligne(ordre=0, ligne_composee=True),
            self._ligne(ordre=1, ligne_composee=False),
            self._ligne(ordre=2),                       # absente ⇒ None
            self._ligne(ordre=3, ligne_composee=None),
        ])
        self.assertEqual(r.status_code, 200, r.content)
        valeurs = list(self.devis.lignes.order_by('ordre')
                       .values_list('ligne_composee', flat=True))
        self.assertEqual(valeurs, [True, False, None, None])

    def test_la_lecture_sert_la_provenance(self):
        r = self._replace([self._ligne(ordre=0, ligne_composee=False)])
        self.assertEqual(r.status_code, 200, r.content)
        lu = self.api.get(f'/api/django/ventes/devis/{self.devis.id}/')
        self.assertEqual(lu.status_code, 200, lu.content)
        self.assertIs(lu.data['lignes'][0]['ligne_composee'], False)

    def test_une_chaine_false_n_est_pas_lue_comme_composee(self):
        r = self._replace([self._ligne(ordre=0, ligne_composee='false')])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIs(self.devis.lignes.get().ligne_composee, False)

    def test_une_section_reste_sans_provenance(self):
        r = self._replace([
            {'type_ligne': 'section', 'designation': 'Stockage', 'ordre': 0,
             'ligne_composee': None},
            self._ligne(ordre=1, ligne_composee=True),
        ])
        self.assertEqual(r.status_code, 200, r.content)
        section = self.devis.lignes.get(type_ligne='section')
        self.assertIsNone(section.ligne_composee)


class LaCopieReprendLaProvenance(_Base):

    def test_le_champ_est_dans_les_jeux_de_champs(self):
        self.assertIn('ligne_composee', CHAMPS_LIGNE)
        self.assertIn('ligne_composee', CHAMPS_CLONES)

    def test_cloner_devis_copie_le_champ(self):
        from apps.ventes.domain.creation import cloner_devis
        from apps.ventes.domain.lignes import creer_ligne

        for ordre, provenance in enumerate((True, False, None)):
            creer_ligne(
                self.devis, produit=self.produit, designation='L%d' % ordre,
                quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
                remise=Decimal('0'), ordre=ordre, ligne_composee=provenance)
        copie = cloner_devis(self.devis, user=self.user)
        self.assertEqual(
            list(copie.lignes.order_by('ordre')
                 .values_list('ligne_composee', flat=True)),
            [True, False, None])

    def test_le_modele_de_devis_capture_le_champ(self):
        from apps.ventes.domain.creation import save_devis_as_preset
        from apps.ventes.domain.lignes import creer_ligne

        creer_ligne(
            self.devis, produit=self.produit, designation='Ajout main',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), ordre=0, ligne_composee=False)
        preset = save_devis_as_preset(self.devis, 'Provenance')
        self.assertIs(preset.lignes_snapshot[0]['ligne_composee'], False)


class LeMoteurPoseTrue(_Base):

    def test_ecrire_lignes_d_une_composition_pose_true(self):
        from apps.ventes.domain.pipeline import ecrire_lignes

        spec = SimpleNamespace(
            produit=self.produit, designation=self.produit.nom,
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            variante='')
        ecrire_lignes(self.devis, [spec], company=self.company)
        self.assertIs(self.devis.lignes.get().ligne_composee, True)

    def test_ecrire_lignes_d_un_dict_ecran_garde_sa_provenance(self):
        from apps.ventes.domain.pipeline import ecrire_lignes

        ecrire_lignes(self.devis, [{
            'produit': self.produit.id, 'quantite': '1',
            'prix_unitaire': '1000', 'ligne_composee': False,
        }], company=self.company)
        self.assertIs(self.devis.lignes.get().ligne_composee, False)

    def test_le_dry_run_de_composition_rend_true(self):
        for nom, prix in CATALOGUE:
            Produit.objects.create(
                company=self.company, nom=nom, prix_vente=Decimal(prix),
                prix_achat=Decimal('1'), quantite_stock=1000)
        r = self.api.post(COMPO_URL, {
            'kwc': 5, 'panel_watt': 710, 'scenario': 'sans',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['lignes'])
        for ligne in r.data['lignes']:
            self.assertIs(ligne['ligne_composee'], True, ligne)
