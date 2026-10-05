"""AGR217 (contrat AGR200) — capacité TVA : chaque ligne exonérée porte sa
base légale, la note multi-taux la cite, l'attestation d'usage agricole est
enregistrée. AUCUN taux par défaut ne change (avis écrit du fiscaliste
attendu, AGRM8) : on ne livre que la CAPACITÉ.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_agr217_tva_base_legale"
"""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.domain.lignes import CHAMPS_CLONES, CHAMPS_LIGNE
from apps.ventes.quote_engine.builder import tva_note_des_lignes
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'devis_replace_lines_entete.json').read_text(encoding='utf-8'))
BASE = ("exonérée art. 91-I-C-6° CGI — matériel utilisé dans le secteur "
        "agricole")


def _l(taux, designation='Article', base=''):
    return SimpleNamespace(taux_tva=None if taux is None else Decimal(taux),
                           designation=designation, produit=None,
                           tva_base_legale=base)


class NoteTvaPureTests(SimpleTestCase):
    def test_sans_zero_identique_a_l_octet(self):
        self.assertEqual(
            tva_note_des_lignes([_l('20'), _l('20')], Decimal('20')),
            "TVA 20 % appliquée sur l'ensemble des équipements et travaux.")
        self.assertEqual(
            tva_note_des_lignes([_l('10', 'Panneau 710W'), _l('20')],
                                Decimal('20')),
            "TVA : 10% panneaux photovoltaïques · "
            "20% autres équipements et prestations")
        self.assertEqual(
            tva_note_des_lignes([_l('14'), _l('20')], Decimal('20')),
            "TVA appliquée ligne par ligne : 14 % / 20 % — taux indiqué "
            "dans le tableau")

    def test_devis_global_a_zero_sans_taux_de_ligne_inchange(self):
        self.assertEqual(
            tva_note_des_lignes([_l(None)], Decimal('0')),
            "TVA 0 % appliquée sur l'ensemble des équipements et travaux.")

    def test_zero_cite_la_base_legale(self):
        note = tva_note_des_lignes(
            [_l('0', 'Pompe', BASE), _l('10', 'Panneau 710W'), _l('20')],
            Decimal('20'))
        self.assertEqual(
            note, "TVA appliquée ligne par ligne : 0 % / 10 % / 20 % — "
                  "exonération : " + BASE)

    def test_une_mention_par_base_distincte(self):
        note = tva_note_des_lignes(
            [_l('0', 'Pompe', 'base A'), _l('0', 'Variateur', 'base A'),
             _l('0', 'Câble', 'base B'), _l('20')], Decimal('20'))
        self.assertEqual(
            note, "TVA appliquée ligne par ligne : 0 % / 20 % — "
                  "exonération : base A ; exonération : base B")
        self.assertEqual(note.count('base A'), 1)


#: Le devis de test ne porte aucun onduleur : le format à options ('full')
#: est refusé par la règle dure du builder. Les clés vérifiées ici (note TVA,
#: attestation) ne dépendent pas du format — on rend donc la page unique.
_ONEPAGE = {'pdf_mode': 'onepage'}


class _Base(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = ProduitFactory(company=self.company)
        self.devis = DevisFactory(company=self.company)

    def _ligne(self, **extra):
        corps = {'produit': self.produit.id, 'quantite': '1',
                 'prix_unitaire': '1000'}
        corps.update(extra)
        return corps

    def _replace(self, lignes, **extra):
        corps = {'lignes': lignes}
        corps.update(extra)
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            corps, format='json')


class ReplaceLinesTests(_Base):
    def test_zero_sans_base_refuse_400_nomme_le_champ(self):
        avant = self.devis.lignes.count()
        r = self._replace([self._ligne(taux_tva='20.00'),
                           self._ligne(taux_tva='0.00', ordre=1)])
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.data['champ'], 'lignes[1].tva_base_legale')
        self.assertIn('base légale', str(r.data['detail']))
        self.assertEqual(self.devis.lignes.count(), avant)

    def test_zero_avec_base_conserve_a_l_aller_retour(self):
        r = self._replace([self._ligne(taux_tva='0.00',
                                       tva_base_legale=BASE),
                           self._ligne(taux_tva='20.00', ordre=1)])
        self.assertEqual(r.status_code, 200, r.content)
        lu = self.api.get(f'/api/django/ventes/devis/{self.devis.id}/')
        self.assertEqual(lu.status_code, 200, lu.content)
        bases = [li['tva_base_legale'] for li in
                 sorted(lu.data['lignes'], key=lambda li: li['ordre'])]
        self.assertEqual(bases, [BASE, ''])

    def test_ligne_sans_taux_jamais_refusee(self):
        r = self._replace([self._ligne()])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.devis.lignes.get().tva_base_legale, '')

    def test_corps_agricole_du_contrat_accepte(self):
        lignes = [dict(li, produit=self.produit.id)
                  for li in CONTRAT['corps_agricole']['lignes']]
        r = self._replace(lignes)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(
            self.devis.lignes.get(ordre=0).tva_base_legale,
            CONTRAT['corps_agricole']['lignes'][0]['tva_base_legale'])

    def test_note_du_rendu_cite_la_base(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        r = self._replace([self._ligne(taux_tva='0.00', tva_base_legale=BASE),
                           self._ligne(taux_tva='20.00', ordre=1)])
        self.assertEqual(r.status_code, 200, r.content)
        self.devis.refresh_from_db()
        data = build_quote_data(self.devis, _ONEPAGE)
        self.assertIn('exonération : ' + BASE, data['tva_note'])


class LigneViewSetTests(_Base):
    def test_serialiseur_refuse_zero_sans_base(self):
        from apps.ventes.serializers import LigneDevisSerializer
        ser = LigneDevisSerializer(data={
            'devis': self.devis.id, 'produit': self.produit.id,
            'designation': 'Pompe', 'quantite': '1',
            'prix_unitaire': '1000', 'taux_tva': '0.00'})
        self.assertFalse(ser.is_valid())
        self.assertIn('tva_base_legale', ser.errors)

    def test_serialiseur_accepte_zero_avec_base(self):
        from apps.ventes.serializers import LigneDevisSerializer
        ser = LigneDevisSerializer(data={
            'devis': self.devis.id, 'produit': self.produit.id,
            'designation': 'Pompe', 'quantite': '1',
            'prix_unitaire': '1000', 'taux_tva': '0.00',
            'tva_base_legale': BASE})
        self.assertTrue(ser.is_valid(), ser.errors)


class CopieTests(_Base):
    def test_le_champ_est_dans_les_jeux_de_champs(self):
        self.assertIn('tva_base_legale', CHAMPS_LIGNE)
        self.assertIn('tva_base_legale', CHAMPS_CLONES)

    def test_dupliquer_et_cloner_conservent_la_base(self):
        from apps.ventes.domain.creation import cloner_devis
        from apps.ventes.domain.lignes import cloner_lignes, creer_ligne

        creer_ligne(self.devis, produit=self.produit, designation='Pompe',
                    quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
                    remise=Decimal('0'), taux_tva=Decimal('0'), ordre=0,
                    tva_base_legale=BASE)
        copie = cloner_devis(self.devis, user=self.user)
        self.assertEqual(copie.lignes.get().tva_base_legale, BASE)
        cible = DevisFactory(company=self.company)
        cloner_lignes(self.devis, cible)
        self.assertEqual(cible.lignes.get().tva_base_legale, BASE)


class AttestationTests(_Base):
    def test_schema_declare_l_attestation(self):
        from apps.ventes.domain.etude_schema import SCHEMA, valider
        self.assertIn('attestation_usage_agricole', SCHEMA)
        self.assertEqual(valider({'attestation_usage_agricole': (
            CONTRAT['corps_agricole']['etude_params']
            ['attestation_usage_agricole'])}), [])

    def test_build_quote_data_expose_l_attestation(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        self.devis.etude_params = {
            'attestation_usage_agricole': {
                'attestee': True, 'le': '2026-10-02',
                'signataire': 'Exploitant'}}
        self.devis.save(update_fields=['etude_params'])
        data = build_quote_data(self.devis, _ONEPAGE)
        self.assertEqual(data['attestation_usage_agricole'],
                         {'attestee': True, 'le': '2026-10-02',
                          'signataire': 'Exploitant'})

    def test_sans_attestation_cle_absente(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(self.devis, _ONEPAGE)
        self.assertNotIn('attestation_usage_agricole', data)
