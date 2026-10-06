# -*- coding: utf-8 -*-
"""AGR223 — Réviser V2, dupliquer, variante, gamme, renouveler : un devis
agricole recopie ses ENTRÉES et RECALCULE ses dérivées.

Test d'INTÉGRATION sur les cinq chemins RÉELS (``POST /dupliquer/``,
``/dupliquer-variante/``, ``/dupliquer-variante-gamme/``, ``/renouveler/``,
``/reviser/``) — aucun chemin de copie n'est simulé. Seul le RÉSEAU l'est
(PVGIS / TMY, patron AGR121) : aucun test ne touche Internet.

Ce qui est recopié : les lignes (dont ``tva_base_legale`` d'une ligne
exonérée), les ENTRÉES v2 (AGR122), ``saisies_economie_pompage``,
``attestation_usage_agricole`` et l'échéancier avec sa ``date_prevue``. Ce qui
est RECALCULÉ (AGR123) : les dérivées ``moteur_pompage`` — empreinte égale à
celle du source quand les lignes sont identiques, différente sinon. La lecture
``economie-pompage/`` d'une copie identique égale celle du source. Aucun
statut du source n'est touché (règle #4).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_agr223_copies_devis_agricole"
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.parametres.models import CompanyProfile
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.domain import pompage
from apps.ventes.domain.etude_schema import MOTEUR_POMPAGE, SCHEMA
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.tests._quote_engine_common import make_client
from authentication.models import Company

User = get_user_model()

SAISIES = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'economie_pompage.json').read_text(encoding='utf-8')
)['saisies_economie_pompage']['exemple']

_JOUR = ([0] * 6 + [100, 300, 500, 700, 850, 950, 1000, 950, 850, 700, 500,
                    300, 100] + [0] * 5)
PROFILS = [[g * (0.7 + 0.05 * i) for g in _JOUR] for i in range(12)]
COURBE = {'debits_m3h': [0, 12, 24, 30, 36, 39],
          'hmt_m': [91, 85, 70, 60, 43, 34]}
BASE_LEGALE = ("Exonération invoquée au titre de l'art. 91-I-C-6° du CGI "
               "(texte saisi, illustratif).")
ENTREES = {
    'mode_pompe': 'neuve', 'type_pompe': 'immergee', 'alim': 'tri',
    'besoin': {'mode': 'volume_declare', 'volume_m3_jour': 135},
    'hmt_entrees': {'saisie_m': 60},
    'localisation': {'ville': 'Taroudant', 'lat': 30.47, 'lon': -8.88},
    'saisies_economie_pompage': SAISIES,
    'attestation_usage_agricole': {'attestee': True, 'le': '2026-10-01',
                                   'signataire': 'Exploitant (illustratif)'},
}
ECHEANCIER = [
    {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 30},
    {'libelle': 'Matériel', 'type': 'materiel', 'pct_or_montant': 60},
    {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 10,
     'date_prevue': '2027-03-31'},
]
DERIVEES = tuple(cle for cle, regle in SCHEMA.items()
                 if regle['proprietaire'] == MOTEUR_POMPAGE)


class CopiesDevisAgricoleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='agr223-co', defaults={'nom': 'AGR223 Co'})[0]
        profil, _ = CompanyProfile.objects.get_or_create(company=cls.co)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            agricole_pump_hours=Decimal('7'))
        cls.pompe = cls._produit(
            'Pompe immergée OSP 30/8 7,5 CV 380V', '15000',
            role_pompage='pompe', type_pompe='immergee', alimentation='tri',
            pompe_kw=Decimal('5.5'), pompe_cv=Decimal('7.5'), tension_v=380,
            courbe_pompe=COURBE)
        cls.variateur = cls._produit(
            'VARIATEUR VEICHI SI23 5.5KW 380V', '6000',
            role_pompage='variateur_pompage', alimentation='tri',
            pompe_kw=Decimal('5.5'), tension_v=380)
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.variateur,
            type_fiche='variateur_pompage', ond_mppt_v_min=Decimal('250'),
            ond_mppt_v_max=Decimal('750'), ond_v_max_abs=Decimal('800'),
            ond_i_max_mppt_a=Decimal('20'), ond_phases=3,
            var_v_sortie_v=Decimal('380'))
        cls.panneau = cls._produit('Panneau 710W', '1100')
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        cls.client_obj = make_client(cls.co)

    @classmethod
    def _produit(cls, nom, prix, **kw):
        return Produit.objects.create(
            company=cls.co, nom=nom, prix_vente=Decimal(prix),
            prix_achat=Decimal('1'), **kw)

    def setUp(self):
        self.user = User.objects.create_user(
            username='agr223_user', password='x', role_legacy='responsable',
            company=self.co)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        for cible, valeur in (('profils_horaires_site', PROFILS),
                              ('temperatures_du_site', None)):
            patcher = mock.patch.object(pompage, cible, return_value=valeur)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.source = self._source()

    def _source(self):
        devis = Devis.objects.create(
            company=self.co, reference='DEV-202610-0230',
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user, mode_installation='agricole',
            etude_params=json.loads(json.dumps(ENTREES)),
            echeancier=json.loads(json.dumps(ECHEANCIER)))
        for ordre, (produit, qte, prix, taux, base) in enumerate((
                (self.pompe, 1, '15000', '0', BASE_LEGALE),
                (self.variateur, 1, '6000', '20', ''),
                (self.panneau, 10, '1100', '20', ''))):
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(prix),
                remise=Decimal('0'), taux_tva=Decimal(taux),
                tva_base_legale=base, ordre=ordre)
        pompage.rafraichir_etude_pompage_devis(devis)
        devis.refresh_from_db()
        return devis

    # ── les cinq chemins ────────────────────────────────────────────────────
    def _post(self, chemin, corps=None, statut_source=None):
        if statut_source:
            # Donnée de TEST : un source dans l'état que le chemin exige.
            Devis.objects.filter(pk=self.source.pk).update(
                statut=statut_source)
        rep = self.api.post('/api/django/ventes/devis/%s/%s/'
                            % (self.source.pk, chemin), corps or {},
                            format='json')
        self.assertEqual(rep.status_code, 201, rep.content[:500])
        return rep.json()

    def _copies_identiques(self):
        """(nom du chemin, copie) pour les chemins à lignes IDENTIQUES."""
        yield 'dupliquer', self._post('dupliquer')['id']
        variantes = self._post('dupliquer-variante', {'scales': [1.0]})
        yield 'variante', variantes[0]['id']
        yield 'gamme', self._post('dupliquer-variante-gamme',
                                  {'nom': 'Premium'})['gamme']['id']
        # Renouveler laisse le source intact (statut, is_active) ; réviser le
        # remplace — il passe donc en dernier. Prix catalogue = prix des
        # lignes : le renouvellement (prix COURANTS) ne change aucun montant.
        yield 'renouveler', self._post('renouveler',
                                       statut_source='expire')['id']
        yield 'reviser', self._post('reviser')['id']

    def test_les_cinq_chemins_recopient_entrees_et_recalculent(self):
        empreinte_source = (self.source.etude_params['provenance_pompage']
                            ['_empreinte'])
        economie_source = self._economie(self.source.pk)
        for chemin, copie_id in self._copies_identiques():
            with self.subTest(chemin=chemin):
                copie = Devis.objects.get(pk=copie_id)
                self.assertEqual(copie.statut, 'brouillon')
                etude = copie.etude_params
                for cle, valeur in ENTREES.items():
                    self.assertEqual(etude.get(cle), valeur, cle)
                self.assertEqual(copie.echeancier[2].get('date_prevue'),
                                 '2027-03-31')
                pompe = copie.lignes.get(produit=self.pompe)
                self.assertEqual(pompe.tva_base_legale, BASE_LEGALE)
                self.assertEqual(pompe.taux_tva, Decimal('0'))
                # Dérivées RECALCULÉES sur la copie, même empreinte.
                self.assertEqual(etude['pompe_kw'], 5.5)
                self.assertEqual(etude['champ_kwc'], 7.1)
                self.assertEqual(etude['provenance_pompage']['_empreinte'],
                                 empreinte_source)
                self.assertEqual(self._economie(copie_id), economie_source)

    def test_une_derivee_perimee_du_source_n_est_jamais_recopiee(self):
        """ROUGE AVANT AGR122/AGR123 : la copie héritait de la dérivée."""
        etude = dict(self.source.etude_params)
        etude.update({'m3_jour': 999.0, 'pompe_kw': 4.41})
        Devis.objects.filter(pk=self.source.pk).update(etude_params=etude)
        for chemin, copie_id in self._copies_identiques():
            with self.subTest(chemin=chemin):
                copie = Devis.objects.get(pk=copie_id).etude_params
                self.assertNotEqual(copie.get('m3_jour'), 999.0)
                self.assertEqual(copie['pompe_kw'], 5.5)

    def test_une_ligne_qui_change_change_l_empreinte(self):
        empreinte_source = (self.source.etude_params['provenance_pompage']
                            ['_empreinte'])
        variantes = self._post('dupliquer-variante', {'scales': [1.25]})
        copie = Devis.objects.get(pk=variantes[0]['id'])
        self.assertNotEqual(
            copie.etude_params['provenance_pompage']['_empreinte'],
            empreinte_source)
        panneaux = copie.lignes.get(produit=self.panneau).quantite
        self.assertEqual(copie.etude_params['champ']['nb_panneaux'],
                         int(panneaux))

    def test_le_source_reste_intact(self):
        avant = (self.source.statut, dict(self.source.etude_params))
        self._post('dupliquer')
        self._post('dupliquer-variante', {'scales': [1.0]})
        self.source.refresh_from_db()
        self.assertEqual(self.source.statut, avant[0])
        for cle in DERIVEES:
            self.assertEqual(self.source.etude_params.get(cle),
                             avant[1].get(cle), cle)

    def _economie(self, devis_id):
        rep = self.api.get(
            '/api/django/ventes/devis/%s/economie-pompage/' % devis_id)
        self.assertEqual(rep.status_code, 200, rep.content[:500])
        return rep.json()
