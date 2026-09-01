"""QJR58 — la colonne ``Devis.overrides`` et son endpoint dédié.

CE QUE CES TESTS TIENNENT :

1. **INDÉPENDANCE PAR CHEMIN** — poser A ne touche PAS B, bit à bit.
2. **PROVENANCE** — chaque chemin posé porte ``{pose_le, pose_par, origine}``.
3. **L'ÉCRITURE NE FAIT PAS AVANCER ``updated_at`` ET NE GÈLE PAS
   ``prix_par_kwc``** — les deux effets de bord de ``Devis.save`` sont FAUX
   pour une pose d'override, et le second est WRITE-ONCE (donc définitif).
4. **``regenerer`` SUPPRIME** (DELETE ``?chemin=``) et ne remplace jamais.
5. **La forme rendue est celle du contrat PACT10** ``devis_overrides.json``.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_overrides_endpoint -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import Devis, LigneDevis
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'devis_overrides.json')


class _OverridesBase(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.produit = ProduitFactory(company=self.company)
        self.devis = DevisFactory(company=self.company,
                                  etude_params={'puissance_kwc': 6.0})
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('10'),
            prix_unitaire=Decimal('1000.00'), remise=Decimal('0'))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.url = f'/api/django/ventes/devis/{self.devis.id}/overrides/'


class FormeDuContratTests(_OverridesBase):

    def test_le_get_rend_les_trois_blocs_du_contrat(self):
        resp = self.api.get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        attendus = set(json.loads(CONTRAT.read_text(encoding='utf-8'))
                       ['exemple'])
        self.assertEqual(set(resp.data), attendus)

    def test_un_devis_vierge_rend_un_registre_vide(self):
        resp = self.api.get(self.url)
        self.assertEqual(resp.data['overrides'], {})
        self.assertEqual(resp.data['lignes'], {})

    def test_isolation_multi_societe(self):
        autre = DevisFactory(company=CompanyFactory())
        resp = self.api.get(
            f'/api/django/ventes/devis/{autre.id}/overrides/')
        self.assertEqual(resp.status_code, 404)


class PatchFusionTests(_OverridesBase):

    def test_poser_un_chemin_ne_touche_pas_les_autres(self):
        r1 = self.api.patch(self.url,
                            {'tarif.distributeur': {'valeur': 'ONEE',
                                                    'origine': 'import'}},
                            format='json')
        self.assertEqual(r1.status_code, 200, r1.data)
        avant = dict(r1.data['overrides']['tarif.distributeur'])

        r2 = self.api.patch(self.url, {'taille.nb_panneaux': 14},
                            format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(set(r2.data['overrides']),
                         {'tarif.distributeur', 'taille.nb_panneaux'})
        self.assertEqual(r2.data['overrides']['tarif.distributeur'], avant)

    def test_la_provenance_est_ecrite(self):
        resp = self.api.patch(self.url, {'taille.nb_panneaux': 14},
                              format='json')
        entree = resp.data['overrides']['taille.nb_panneaux']
        self.assertEqual(set(entree),
                         {'valeur', 'pose_le', 'pose_par', 'origine'})
        self.assertEqual(entree['valeur'], 14)
        self.assertEqual(entree['origine'], 'manuel')
        self.assertEqual(entree['pose_par'],
                         self.user.email or self.user.username)
        self.assertTrue(entree['pose_le'])

    def test_un_champ_derive_est_refuse_en_400(self):
        resp = self.api.patch(self.url, {'prix_ttc': 120000}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('prix_ttc', resp.data)

    def test_un_chemin_inconnu_est_refuse_en_400(self):
        resp = self.api.patch(self.url, {'taille.inventee': 1}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_une_cle_indexee_par_position_est_refusee_en_400(self):
        resp = self.api.patch(self.url, {'lignes[3].prix_manuel': True},
                              format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_l_effectif_reflete_l_override(self):
        self.api.patch(self.url, {'scenario': 'Les deux (Sans + Avec)'},
                       format='json')
        resp = self.api.get(self.url)
        bloc = resp.data['effectif']['scenario']
        self.assertEqual(bloc['manuel'], 'Les deux (Sans + Avec)')
        self.assertEqual(bloc['effectif'], 'Les deux (Sans + Avec)')
        self.assertEqual(bloc['source'], 'manuel')


class EcritureChirurgicaleTests(_OverridesBase):
    """UN UPDATE d'une seule colonne — pas un ``Devis.save``."""

    def test_updated_at_ne_bouge_pas(self):
        self.devis.refresh_from_db()
        avant = self.devis.updated_at
        self.api.patch(self.url, {'taille.nb_panneaux': 14}, format='json')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.updated_at, avant)

    def test_le_gel_prix_par_kwc_n_est_pas_declenche(self):
        self.devis.refresh_from_db()
        self.assertIsNone(self.devis.prix_par_kwc)
        self.api.patch(self.url, {'taille.nb_panneaux': 14}, format='json')
        self.devis.refresh_from_db()
        self.assertIsNone(
            self.devis.prix_par_kwc,
            "poser une ENTRÉE ne doit pas figer, write-once et pour "
            'toujours, un prix par kWc que ce geste ne concerne pas')

    def test_aucune_ligne_aucun_statut_ne_bouge(self):
        avant_lignes = list(
            self.devis.lignes.values_list('id', 'quantite', 'prix_unitaire'))
        avant_statut = self.devis.statut
        self.api.patch(self.url, {'taille.nb_panneaux': 14}, format='json')
        self.devis.refresh_from_db()
        self.assertEqual(
            list(self.devis.lignes.values_list('id', 'quantite',
                                               'prix_unitaire')),
            avant_lignes)
        self.assertEqual(self.devis.statut, avant_statut)

    def test_la_colonne_est_bien_persistee(self):
        self.api.patch(self.url, {'taille.nb_panneaux': 14}, format='json')
        self.assertEqual(
            Devis.objects.get(pk=self.devis.pk)
            .overrides['taille.nb_panneaux']['valeur'], 14)


class RegenererTests(_OverridesBase):

    def test_delete_supprime_le_chemin_et_lui_seul(self):
        self.api.patch(self.url,
                       {'taille.nb_panneaux': 14, 'scenario': 'Sans batterie'},
                       format='json')
        resp = self.api.delete(self.url + '?chemin=taille.nb_panneaux')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data['overrides']), {'scenario'})

    def test_delete_ne_repose_aucune_valeur_calculee(self):
        self.api.patch(self.url, {'taille.nb_panneaux': 14}, format='json')
        self.api.delete(self.url + '?chemin=taille.nb_panneaux')
        registre = Devis.objects.get(pk=self.devis.pk).overrides or {}
        self.assertNotIn('taille.nb_panneaux', registre)

    def test_delete_sans_chemin_est_refuse(self):
        resp = self.api.delete(self.url)
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_delete_d_un_chemin_inconnu_est_refuse(self):
        resp = self.api.delete(self.url + '?chemin=taille.inventee')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_delete_d_un_chemin_non_pose_est_idempotent(self):
        resp = self.api.delete(self.url + '?chemin=scenario')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['overrides'], {})
