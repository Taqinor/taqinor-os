"""Tests COMPTA6 — Dossier de contrôle CGNC prêt à valider (fiduciaire).

Couvre le constructeur de dossier (``construire_dossier_cgnc``), les contrôles
de cohérence (``controles_coherence_cgnc``), le barème de référence
(``plan_cgnc_reference``) et la commande de gestion ``compta_cgnc_dossier``.
On vérifie : la structure du dossier, la couverture du barème, la synthèse par
sévérité, la CAPTURE d'incohérences volontairement injectées (classe déclarée ≠
classe du numéro, sens incohérent, compte désactivé encore mouvementé,
complétude du mapping), l'isolation multi-société et les deux formats de la
commande. Aucun appel externe, aucune écriture de données de contrôle.
"""
import json
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import CompteComptable, Journal


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CgncDossierServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('acme-cgnc', 'Acme Solaire')
        self.plan = services.seed_plan_comptable(self.company)
        services.seed_journaux(self.company)

    def test_reference_cgnc_groupe_par_classe(self):
        ref = services.plan_cgnc_reference()
        # Le barème couvre au moins les classes 1 à 7.
        for classe in (1, 2, 3, 4, 5, 6, 7):
            self.assertIn(classe, ref)
            self.assertTrue(ref[classe]['comptes'])
            self.assertEqual(ref[classe]['libelle'], services.CGNC_CLASSES[classe])
        # Comptes triés par numéro dans chaque classe.
        c3 = [c['numero'] for c in ref[3]['comptes']]
        self.assertEqual(c3, sorted(c3))

    def test_dossier_structure_et_synthese(self):
        dossier = services.construire_dossier_cgnc(self.company)
        self.assertEqual(
            set(dossier),
            {'synthese', 'plan_comptable', 'reference_cgnc',
             'controles', 'a_valider_fiduciaire'})
        synthese = dossier['synthese']
        self.assertEqual(synthese['company'], 'Acme Solaire')
        self.assertEqual(synthese['company_slug'], 'acme-cgnc')
        self.assertGreater(synthese['nb_comptes'], 0)
        # Un plan fraîchement semé couvre 100 % du barème de référence.
        self.assertEqual(
            synthese['reference_cgnc_couverte'],
            synthese['reference_cgnc_totale'])
        self.assertTrue(synthese['pret_a_transmettre'])
        # L'étape fiduciaire humaine est explicitement listée.
        self.assertTrue(dossier['a_valider_fiduciaire'])
        self.assertTrue(any(
            'LÉGALE' in item for item in dossier['a_valider_fiduciaire']))

    def test_plan_seme_ne_produit_aucune_anomalie_bloquante(self):
        anomalies = services.controles_coherence_cgnc(self.company)
        bloquants = [a for a in anomalies if a['severite'] == 'bloquant']
        self.assertEqual(bloquants, [])

    def test_capture_classe_incoherente(self):
        # Compte dont le numéro dit « classe 6 » mais dont le champ classe = 7.
        CompteComptable.objects.create(
            company=self.company, plan=self.plan,
            numero='6999', intitule='Charge mal classée', classe=7)
        anomalies = services.controles_coherence_cgnc(self.company)
        codes = {a['code'] for a in anomalies}
        self.assertIn('classe_incoherente', codes)
        incoherence = next(
            a for a in anomalies if a['code'] == 'classe_incoherente')
        self.assertEqual(incoherence['severite'], 'bloquant')
        self.assertIn('6999', incoherence['comptes'])
        # Cette anomalie bloquante fait basculer l'état du dossier.
        dossier = services.construire_dossier_cgnc(self.company)
        self.assertFalse(dossier['synthese']['pret_a_transmettre'])
        self.assertGreaterEqual(
            dossier['synthese']['anomalies_par_severite']['bloquant'], 1)

    def test_capture_sens_incoherent(self):
        # Compte de classe 6 (charge) mais déclaré « produit ».
        CompteComptable.objects.create(
            company=self.company, plan=self.plan,
            numero='6998', intitule='Charge au mauvais sens', classe=6,
            sens='produit')
        anomalies = services.controles_coherence_cgnc(self.company)
        sens = [a for a in anomalies if a['code'] == 'sens_incoherent']
        self.assertTrue(sens)
        self.assertEqual(sens[0]['severite'], 'avertissement')

    def test_capture_compte_manquant_au_barème(self):
        # Supprimer un compte usuel du barème → info « compte_ref_manquant ».
        CompteComptable.objects.filter(
            company=self.company, numero='7111').delete()
        anomalies = services.controles_coherence_cgnc(self.company)
        manquants = [a for a in anomalies if a['code'] == 'compte_ref_manquant']
        self.assertTrue(manquants)
        self.assertEqual(manquants[0]['severite'], 'info')
        self.assertIn('7111', manquants[0]['comptes'])
        dossier = services.construire_dossier_cgnc(self.company)
        self.assertLess(
            dossier['synthese']['reference_cgnc_couverte'],
            dossier['synthese']['reference_cgnc_totale'])

    def test_capture_compte_inactif_encore_mouvemente(self):
        journal = services._journal(
            self.company, Journal.Type.OPERATIONS_DIVERSES)
        c6 = services.get_compte(self.company, '6111')
        c5 = services.get_compte(self.company, '5141')
        services.creer_ecriture(
            self.company, journal, date(2026, 3, 1), 'Achat',
            [{'compte': c6, 'debit': Decimal('100'), 'credit': Decimal('0')},
             {'compte': c5, 'debit': Decimal('0'), 'credit': Decimal('100')}])
        # Désactiver un compte pourtant mouvementé.
        c6.actif = False
        c6.save(update_fields=['actif'])
        anomalies = services.controles_coherence_cgnc(self.company)
        orphelins = [
            a for a in anomalies if a['code'] == 'compte_reference_absent']
        self.assertTrue(orphelins)
        self.assertIn('6111', orphelins[0]['comptes'])

    def test_isolation_multi_societe(self):
        autre = make_company('beta-cgnc', 'Beta SARL')
        services.seed_plan_comptable(autre)
        # Anomalie injectée chez Acme uniquement.
        CompteComptable.objects.create(
            company=self.company, plan=self.plan,
            numero='6997', intitule='X', classe=8)
        anomalies_autre = services.controles_coherence_cgnc(autre)
        self.assertEqual(
            [a for a in anomalies_autre if '6997' in a.get('comptes', [])], [])


class CgncDossierCommandTests(TestCase):
    def setUp(self):
        self.company = make_company('cmd-cgnc', 'Command Co')
        services.seed_plan_comptable(self.company)

    def test_commande_exige_company_ou_all(self):
        with self.assertRaises(CommandError):
            call_command('compta_cgnc_dossier')

    def test_commande_slug_inconnu(self):
        with self.assertRaises(CommandError):
            call_command('compta_cgnc_dossier', company='inexistant')

    def test_commande_texte(self):
        out = StringIO()
        call_command(
            'compta_cgnc_dossier', company='cmd-cgnc', format='text',
            stdout=out)
        texte = out.getvalue()
        self.assertIn('DOSSIER DE CONTRÔLE CGNC', texte)
        self.assertIn('Command Co', texte)
        self.assertIn('À VALIDER PAR LE FIDUCIAIRE', texte)
        self.assertIn('PLAN COMPTABLE PAR CLASSE', texte)

    def test_commande_json(self):
        out = StringIO()
        call_command(
            'compta_cgnc_dossier', company='cmd-cgnc', format='json',
            stdout=out)
        data = json.loads(out.getvalue())
        self.assertIn('synthese', data)
        self.assertIn('plan_comptable', data)
        self.assertIn('a_valider_fiduciaire', data)
        self.assertEqual(data['synthese']['company_slug'], 'cmd-cgnc')

    def test_commande_all_json_liste(self):
        make_company('cmd-cgnc-2', 'Autre Co')
        services.seed_plan_comptable(Company.objects.get(slug='cmd-cgnc-2'))
        out = StringIO()
        call_command(
            'compta_cgnc_dossier', all=True, format='json', stdout=out)
        data = json.loads(out.getvalue())
        self.assertIsInstance(data, list)
        slugs = {d['synthese']['company_slug'] for d in data}
        self.assertIn('cmd-cgnc', slugs)
        self.assertIn('cmd-cgnc-2', slugs)
