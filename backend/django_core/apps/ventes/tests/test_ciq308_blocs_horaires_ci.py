"""CIQ308 — Proposition C&I : les blocs du moteur horaire RÉSIDENTIEL
(courbe du jour, jours types, estimation de consommation…) ne sortent plus ;
seuls ceux du moteur C&I passent.

Deux étages :
  * ``construire_courbes_ci`` (PUR, ``SimpleTestCase``) sur la sortie du
    moteur C&I du contrat partagé ``etude_ci_preview.json`` ;
  * la charge utile RÉELLE (client Django) d'un commercial et d'un
    industriel, avec et sans sortie du moteur C&I, et d'un résidentiel.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq308_blocs_horaires_ci"
"""
import copy
import json
import uuid
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.test import Client as DjangoClient, SimpleTestCase

from apps.ventes import courbes_journalieres as cj
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.tests.test_ciq210_branchement import _BaseDevis

ETUDE_CI = json.loads(
    (Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'etude_ci_preview.json').read_text(encoding='utf-8'))

#: Les clés du moteur horaire RÉSIDENTIEL, absentes en C&I sauf si le moteur
#: C&I les sert (contrat ``proposal_data.json`` › ``notes_ciq4``).
CLES_RESIDENTIELLES = ('jours_types', 'estimation_conso', 'tranche_tarifaire',
                       'profils_comparatifs', 'batterie_regime',
                       'balayage_stockage', 'dimensionnement_options',
                       'production_par_option')
CLES_BATTERIE = ('couverture_batterie', 'paliers_batterie')


def _data(**surcharges_etude_ci):
    etude_ci = copy.deepcopy(ETUDE_CI['exemple'])
    etude_ci.update(surcharges_etude_ci)
    return {'mode_installation': 'commercial', 'etude': {'etude_ci': etude_ci}}


class CourbesCiPuresTest(SimpleTestCase):

    def test_source_moteur_ci_et_formes_normalisees(self):
        bloc = cj.construire_courbes_ci(_data())
        self.assertEqual(bloc['source'], cj.SOURCE_MOTEUR_CI)
        self.assertIn('production', bloc)
        for saison, serie in bloc['production'].items():
            self.assertEqual(len(serie['forme']), 24)
            self.assertAlmostEqual(sum(serie['forme']), 1.0, places=6)
            self.assertEqual(serie['source'], cj.SOURCE_MOTEUR_CI)
            self.assertGreater(serie['pic_kw'], 0)
        # Jamais l'occupation ni les équipements d'un logement.
        for cle in ('occupation', 'occupation_source', 'equipements',
                    'options', 'batterie_kwh'):
            self.assertNotIn(cle, bloc)

    def test_niveau_de_production_egal_a_la_matrice_du_moteur(self):
        """kWh/jour d'été = moyenne pondérée (nb_jours) de autoconso +
        surplus des mois d'été de ``bilan.horaire`` — aucun autre modèle."""
        horaire = ETUDE_CI['exemple']['bilan']['horaire']
        ete = [e for e in horaire if e['mois'] in (6, 7, 8)]
        if not ete:
            self.skipTest('contrat sans mois d\'été')
        jours = sum(e['nb_jours'] for e in ete)
        attendu = sum(sum(e['autoconso_kwh']) + sum(e['surplus_kwh'])
                      for e in ete for _ in range(e['nb_jours'])) / jours
        bloc = cj.construire_courbes_ci(_data())
        self.assertAlmostEqual(bloc['production']['ete']['kwh_jour'],
                               round(attendu, 1), places=1)

    def test_heure_legale_via_decalage_maroc(self):
        base = cj.construire_courbes_ci(_data())['production']['ete']['forme']
        with mock.patch('apps.parametres.pvgis_profils.decalage_maroc_h',
                        return_value=1):
            decale = cj.construire_courbes_ci(
                _data())['production']['ete']['forme']
        self.assertEqual(decale[1:] + decale[:1], base)

    def test_profil_type_etiquete_estimation(self):
        profil = copy.deepcopy(ETUDE_CI['exemple']['profil_charge'])
        profil['methode'] = 'archetype'
        bloc = cj.construire_courbes_ci(_data(profil_charge=profil))
        self.assertTrue(bloc['profil_suppose'])
        self.assertEqual(bloc['etiquette_profil'], cj.ETIQUETTE_PROFIL_TYPE)
        declare = cj.construire_courbes_ci(_data())
        self.assertNotIn('etiquette_profil', declare)

    def test_sans_sortie_moteur_none(self):
        self.assertIsNone(cj.construire_courbes_ci(
            {'mode_installation': 'industriel', 'etude': {}}))
        self.assertIsNone(cj.construire_courbes_ci(_data(bilan={},
                                                         profil_charge={})))


class BlocsHorairesCiChargeUtileTest(_BaseDevis):

    def _payload(self, devis):
        token = str(uuid.uuid4())
        ShareLink.objects.create(company=self.co, devis=devis, token=token)
        reponse = DjangoClient().get(
            f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse.json()

    def _sans_moteur(self, ref, mode):
        devis = Devis.objects.create(
            company=self.co, reference=ref, client=self.client_obj,
            statut='envoye', taux_tva=Decimal('20'), mode_installation=mode,
            etude_params={'occupation_jour': 'presence_jour'})
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau 710W',
            quantite=Decimal('70'), prix_unitaire=Decimal('1272.73'),
            remise=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, produit=self.ond, designation='Onduleur 50 kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('40000'),
            remise=Decimal('0'))
        return devis

    def test_sans_sortie_moteur_aucun_bloc_residentiel(self):
        for ref, mode in (('DEV-CIQ308-0010', 'commercial'),
                          ('DEV-CIQ308-0020', 'industriel')):
            with self.subTest(mode=mode):
                p = self._payload(self._sans_moteur(ref, mode))
                self.assertNotIn('courbes_journalieres', p)
                for cle in CLES_RESIDENTIELLES + CLES_BATTERIE:
                    self.assertNotIn(cle, p)

    def test_avec_sortie_moteur_courbe_moteur_ci(self):
        for ref, mode, tension in (('DEV-CIQ308-0030', 'commercial', 'bt'),
                                   ('DEV-CIQ308-0040', 'industriel', 'mt')):
            with self.subTest(mode=mode):
                devis = self._devis(ref, mode=mode, tension=tension)
                self.assertIn('etude_ci', devis.etude_params)
                p = self._payload(devis)
                courbes = p['courbes_journalieres']
                self.assertEqual(courbes['source'], 'moteur_ci')
                self.assertNotIn('occupation', courbes)
                for cle in CLES_RESIDENTIELLES + CLES_BATTERIE:
                    self.assertNotIn(cle, p)

    def test_residentiel_inchange(self):
        devis = Devis.objects.create(
            company=self.co, reference='DEV-CIQ308-0050',
            client=self.client_obj, statut='envoye', taux_tva=Decimal('20'),
            mode_installation='residentiel', etude_params={})
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau 710W',
            quantite=Decimal('10'), prix_unitaire=Decimal('1272.73'),
            remise=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, produit=self.ond, designation='Onduleur réseau 8kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('14000'),
            remise=Decimal('0'))
        with mock.patch.object(
                cj, 'construire_courbes_ci',
                side_effect=AssertionError('chemin C&I appelé')) as ci:
            p = self._payload(devis)
        ci.assert_not_called()
        courbes = p.get('courbes_journalieres')
        if courbes is not None:
            self.assertNotEqual(courbes.get('source'), 'moteur_ci')
