# -*- coding: utf-8 -*-
"""L-2OPT — ``manage.py reparer_devis_deux_options``.

La commande soigne les devis DÉJÀ abîmés par l'ancienne resynchronisation 3D :
un devis né « Les deux (Sans + Avec) » dont l'onduleur RÉSEAU a été supprimé et
dont le scénario a été réécrit en mono « Avec batterie ». Ce que ces tests
verrouillent, et pourquoi :

1. **Le DRY-RUN est le défaut, et il n'écrit RIEN.** La détection est
   structurelle (aucun indice persisté de « né à deux options » n'a survécu au
   bug) : elle PEUT attraper un devis né mono. Un défaut qui écrit serait donc
   une seconde perte de données.
2. **``--apply`` répare pour de vrai** : ligne réseau recréée au PRIX CATALOGUE
   sans remise, scénario restauré, et le moteur PDF re-rend DEUX options.
3. **Idempotente** : relancée, elle ne trouve plus rien.
4. **Multi-tenant** : ``--company`` ne touche jamais l'autre société.
5. **Un devis né mono, sans calepinage, n'est JAMAIS touché.**

Run :
    DB_NAME=erp_ventes python manage.py test \\
        apps.ventes.tests.test_reparer_devis_deux_options -v 2
"""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import SCENARIO_AVEC_BATTERIE, SCENARIO_LES_DEUX

RESEAU = 'Onduleur réseau Huawei 5kW'
HYBRIDE = 'Onduleur hybride Deye 5kW'
BATTERIE = 'Batterie Dyness 5 kWh'
PANNEAU = 'Panneau Jinko 550W'

#: Le calepinage tel que la resynchro le range sur le devis — sa seule présence
#: prouve que le calepinage 3D est passé par là (c'est un des quatre critères).
LAYOUT = {'scenario': 'avec_batterie', 'panelWatt': 550,
          'result': {'panels': 8, 'kwc': 4.4}}


def make_company(slug):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class TestReparerDevisDeuxOptions(TestCase):
    """DEV-202608-0023 rejoué : hybride Deye 5 kW + batterie Dyness 5 kWh +
    8 panneaux, aucun onduleur réseau, scénario « Avec batterie », brouillon."""

    def setUp(self):
        self.company = make_company('rep2opt-co')
        self.autre = make_company('rep2opt-autre')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client L-2OPT')
        self.client_autre = Client.objects.create(
            company=self.autre, nom='Client autre société')
        self.produits = {}
        for prefixe, company in (('REP', self.company), ('REPA', self.autre)):
            for index, (nom, prix) in enumerate(
                    ((PANNEAU, '1100'), (RESEAU, '14000'),
                     (HYBRIDE, '17000'), (BATTERIE, '16000'))):
                produit = Produit.objects.create(
                    company=company, nom=nom,
                    sku='%s-%d' % (prefixe, index),
                    prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                    quantite_stock=100)
                self.produits[(company.slug, nom)] = produit
        self.compteur = 0

    def _devis(self, *, company=None, client=None, reseau=False,
               scenario=SCENARIO_AVEC_BATTERIE, layout=LAYOUT,
               statut=Devis.Statut.BROUILLON, groupe=False):
        company = company or self.company
        client = client or self.client_obj
        self.compteur += 1
        devis = Devis.objects.create(
            company=company, reference='DEV-REP-%03d' % self.compteur,
            client=client, statut=statut,
            etude_params=None if scenario is None else {'scenario': scenario},
            roof_layout=layout)
        ordre = 0
        lignes = [(PANNEAU, '1100', 8), (HYBRIDE, '17000', 1),
                  (BATTERIE, '16000', 1)]
        if reseau:
            lignes.append((RESEAU, '14000', 1))
        for nom, prix, quantite in lignes:
            ordre += 1
            devis.lignes.create(
                produit=self.produits[(company.slug, nom)], designation=nom,
                quantite=Decimal(str(quantite)),
                prix_unitaire=Decimal(prix), remise=Decimal('0'), ordre=ordre)
        if groupe:
            devis.lignes.create(
                produit=self.produits[(company.slug, PANNEAU)],
                designation=PANNEAU, quantite=Decimal('4'),
                prix_unitaire=Decimal('1100'), ordre=ordre + 1,
                groupe_index=1, groupe_label='Villa B')
        return devis

    def _run(self, *args):
        sortie = StringIO()
        call_command('reparer_devis_deux_options', *args, stdout=sortie)
        return sortie.getvalue()

    # ── (1) Le dry-run est le défaut et n'écrit rien ───────────────────────
    def test_dry_run_par_defaut_n_ecrit_rien(self):
        devis = self._devis()
        sortie = self._run()
        self.assertIn(devis.reference, sortie)
        self.assertIn('À RÉPARER', sortie)
        self.assertIn('DRY-RUN', sortie)
        # RIEN n'a bougé : ni ligne, ni scénario.
        self.assertFalse(devis.lignes.filter(designation=RESEAU).exists())
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'],
                         SCENARIO_AVEC_BATTERIE)

    # ── (2) --apply répare ─────────────────────────────────────────────────
    def test_apply_recree_la_ligne_reseau_au_prix_catalogue(self):
        devis = self._devis()
        sortie = self._run('--apply')
        self.assertIn('RÉPARÉ', sortie)
        ligne = devis.lignes.get(designation=RESEAU)
        self.assertEqual(ligne.produit_id,
                         self.produits[(self.company.slug, RESEAU)].id)
        self.assertEqual(ligne.prix_unitaire, Decimal('14000.00'))
        self.assertEqual(ligne.remise, Decimal('0.00'))
        self.assertEqual(int(ligne.quantite), 1)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], SCENARIO_LES_DEUX)
        # Règle #4 : aucun statut n'est touché.
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_apply_rend_deux_options_au_moteur(self):
        """La preuve par le moteur : c'est LUI que la page publique lit."""
        from apps.ventes.quote_engine.builder import build_quote_data

        devis = self._devis()
        self._run('--apply')
        devis.refresh_from_db()
        data = build_quote_data(devis)
        self.assertEqual(data['nb_options'], 2)
        self.assertEqual(data['scenario'], SCENARIO_LES_DEUX)
        self.assertTrue(data['sans_items'])

    # ── (3) Idempotence ────────────────────────────────────────────────────
    def test_relancee_elle_ne_trouve_plus_rien(self):
        devis = self._devis()
        self._run('--apply')
        sortie = self._run('--apply')
        self.assertIn('Aucun devis à réparer', sortie)
        self.assertEqual(
            devis.lignes.filter(designation=RESEAU).count(), 1)

    # ── (4) Multi-tenant ───────────────────────────────────────────────────
    def test_company_ne_repare_pas_l_autre_societe(self):
        ici = self._devis()
        ailleurs = self._devis(company=self.autre, client=self.client_autre)
        self._run('--apply', '--company', self.company.slug)
        self.assertTrue(ici.lignes.filter(designation=RESEAU).exists())
        self.assertFalse(ailleurs.lignes.filter(designation=RESEAU).exists())
        ailleurs.refresh_from_db()
        self.assertEqual(ailleurs.etude_params['scenario'],
                         SCENARIO_AVEC_BATTERIE)

    def test_societe_inconnue_refusee(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            self._run('--company', 'societe-qui-n-existe-pas')

    # ── (5) Ce qui ne doit JAMAIS être touché ──────────────────────────────
    def test_devis_ne_mono_sans_calepinage_jamais_touche(self):
        devis = self._devis(layout=None)
        sortie = self._run('--apply')
        self.assertIn('Aucun devis à réparer', sortie)
        self.assertFalse(devis.lignes.filter(designation=RESEAU).exists())
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'],
                         SCENARIO_AVEC_BATTERIE)

    def test_devis_deja_a_deux_onduleurs_ignore(self):
        devis = self._devis(reseau=True)
        self._run('--apply')
        self.assertEqual(
            devis.lignes.filter(designation=RESEAU).count(), 1)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'],
                         SCENARIO_AVEC_BATTERIE)

    def test_devis_non_brouillon_jamais_touche(self):
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        self._run('--apply')
        self.assertFalse(devis.lignes.filter(designation=RESEAU).exists())
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_devis_multi_villa_saute(self):
        devis = self._devis(groupe=True)
        self._run('--apply')
        self.assertFalse(devis.lignes.filter(designation=RESEAU).exists())

    def test_sans_reseau_tarife_le_devis_est_saute(self):
        Produit.objects.filter(
            pk=self.produits[(self.company.slug, RESEAU)].pk).update(
                is_archived=True)
        devis = self._devis()
        sortie = self._run('--apply')
        self.assertIn('SAUTÉ', sortie)
        self.assertIn('aucun onduleur réseau tarifé', sortie)
        self.assertFalse(devis.lignes.filter(designation=RESEAU).exists())
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'],
                         SCENARIO_AVEC_BATTERIE)

    # ── (6) --refs cible, et DIT pourquoi une référence est écartée ────────
    def test_refs_ne_repare_que_les_references_demandees(self):
        vise = self._devis()
        epargne = self._devis()
        self._run('--apply', '--refs', vise.reference)
        self.assertTrue(vise.lignes.filter(designation=RESEAU).exists())
        self.assertFalse(epargne.lignes.filter(designation=RESEAU).exists())

    def test_refs_explique_une_reference_non_concernee(self):
        devis = self._devis(reseau=True)
        sortie = self._run('--refs', devis.reference)
        self.assertIn('non concerné', sortie)
        self.assertIn('déjà un onduleur réseau', sortie)
