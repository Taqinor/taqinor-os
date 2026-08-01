"""AOF120 — bordereau v2 : sections, TVA, quantités TRAÇABLES, totaux serveur.

Ce qui est prouvé ici :

* les totaux sont RECALCULÉS côté serveur (sous-total HT → remise → total HT →
  TVA par taux → total TTC) et jamais des colonnes recopiées ;
* la clause de réserve est OBLIGATOIRE sur un marché à prix unitaires ;
* une quantité annoncée « issue du calepinage » DOIT citer la variante qui l'a
  produite — c'est ce qui rend vérifiable en machine « quantités du bordereau =
  engagements des planches » ;
* la migration est ADDITIVE : les tables ``compta_*`` d'ODX11 ne sont pas
  renommées ;
* **aucun second modèle de ligne de bordereau n'existe** (NTMAR22 superseded).

Run :
    python manage.py test apps.ao.tests.test_bordereau_v2 -v2
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from apps.ao import services
from apps.ao.models import (
    AppelOffre, BatimentAO, BordereauPrix, LigneBordereau, SectionBordereau,
    ToitureAO, VarianteCalepinage,
)
from apps.ao.serializers import BordereauPrixSerializer, LigneBordereauSerializer
from authentication.models import Company

CLAUSE = (
    "Marché à prix unitaires : les quantités portées au présent bordereau "
    "sont des quantités prévisionnelles ; le règlement s'effectue sur les "
    "quantités réellement exécutées."
)


class TestAucunSecondModeleDeLigne(SimpleTestCase):
    """NTMAR22 est SUPERSEDED : ``LigneBordereau`` est ÉTENDU, pas doublé."""

    def test_pas_de_modele_lignebordereauprix(self):
        from django.apps import apps as django_apps

        noms = {m.__name__ for m in django_apps.get_app_config('ao').get_models()}
        self.assertNotIn('LigneBordereauPrix', noms)

    def test_un_seul_modele_de_ligne_de_bordereau(self):
        from django.apps import apps as django_apps

        lignes = sorted(
            m.__name__ for m in django_apps.get_app_config('ao').get_models()
            if 'LigneBordereau' in m.__name__)
        self.assertEqual(lignes, ['LigneBordereau'])

    def test_les_tables_odx11_ne_bougent_pas(self):
        self.assertEqual(BordereauPrix._meta.db_table, 'compta_bordereauprix')
        self.assertEqual(LigneBordereau._meta.db_table,
                         'compta_lignebordereau')


class BaseBordereau(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF120 Co',
                                              slug='aof120-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-120-1', objet='Bordereau')
        self.bordereau = BordereauPrix.objects.create(
            company=self.company, appel_offre=self.ao,
            clause_reserve=CLAUSE)

    def _section(self, numero, libelle, **kwargs):
        return SectionBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, numero=numero,
            libelle=libelle, **kwargs)

    def _ligne(self, numero, quantite, pu, **kwargs):
        base = {'designation': f'Poste {numero}'}
        base.update(kwargs)
        return LigneBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, numero=numero,
            quantite=Decimal(quantite), prix_unitaire=Decimal(pu), **base)


class TestTotauxServeur(BaseBordereau):
    def test_sous_total_et_total_sans_remise(self):
        self._ligne(1, '314', '2950.00')
        self._ligne(2, '2', '78000.00')
        attendu = Decimal('314') * Decimal('2950') + Decimal('156000')
        self.assertEqual(self.bordereau.sous_total_ht,
                         attendu.quantize(Decimal('0.01')))
        self.assertEqual(self.bordereau.total_ht,
                         attendu.quantize(Decimal('0.01')))

    def test_la_remise_de_ligne_entre_dans_le_montant(self):
        ligne = self._ligne(1, '100', '1000.00', remise_pct=Decimal('10.00'))
        self.assertEqual(ligne.montant_ht, Decimal('90000.00'))

    def test_la_remise_globale_est_deduite_du_sous_total(self):
        self._ligne(1, '100', '1000.00')
        self.bordereau.remise_globale_pct = Decimal('5.00')
        self.bordereau.save(update_fields=['remise_globale_pct'])
        self.assertEqual(self.bordereau.sous_total_ht, Decimal('100000.00'))
        self.assertEqual(self.bordereau.montant_remise_globale,
                         Decimal('5000.00'))
        self.assertEqual(self.bordereau.total_ht, Decimal('95000.00'))

    def test_deux_taux_de_tva_donnent_deux_paniers(self):
        self._ligne(1, '100', '1000.00',
                    taux_tva=Decimal('10.00'))
        self._ligne(2, '100', '1000.00',
                    taux_tva=Decimal('20.00'))
        panier = self.bordereau.tva_par_taux
        self.assertEqual(panier[Decimal('10.00')], Decimal('10000.00'))
        self.assertEqual(panier[Decimal('20.00')], Decimal('20000.00'))
        self.assertEqual(self.bordereau.total_tva, Decimal('30000.00'))
        self.assertEqual(self.bordereau.total_ttc, Decimal('230000.00'))

    def test_le_taux_du_bordereau_sert_de_repli(self):
        ligne = self._ligne(1, '10', '100.00')
        self.assertIsNone(ligne.taux_tva)
        self.assertEqual(ligne.taux_tva_effectif, Decimal('20.00'))

    def test_la_remise_globale_est_repartie_au_prorata_sur_la_tva(self):
        self._ligne(1, '100', '1000.00', taux_tva=Decimal('10.00'))
        self.bordereau.remise_globale_pct = Decimal('10.00')
        self.bordereau.save(update_fields=['remise_globale_pct'])
        self.assertEqual(self.bordereau.total_ht, Decimal('90000.00'))
        self.assertEqual(self.bordereau.total_tva, Decimal('9000.00'))
        self.assertEqual(self.bordereau.total_ttc, Decimal('99000.00'))

    def test_aucun_total_n_est_une_colonne(self):
        noms = {f.name for f in BordereauPrix._meta.get_fields()}
        for interdit in ('total_ht', 'total_ttc', 'total_tva',
                         'sous_total_ht'):
            self.assertNotIn(interdit, noms)

    def test_le_service_publie_la_chaine_complete(self):
        self._ligne(1, '100', '1000.00')
        totaux = services.totaux_bordereau(self.bordereau)
        self.assertEqual(
            set(totaux),
            {'sous_total_ht', 'remise_globale_pct', 'montant_remise_globale',
             'total_ht', 'tva_par_taux', 'total_tva', 'total_ttc'})


class TestSectionsDuBordereau(BaseBordereau):
    def test_les_quatre_sections_reelles(self):
        for code in ('A', 'B', 'C'):
            batiment = BatimentAO.objects.create(
                company=self.company, appel_offre=self.ao, code=code)
            self._section(code, f'Bâtiment {code}', batiment=batiment)
        self._section('D', 'Prestations communes')
        self.assertEqual(self.bordereau.sections.count(), 4)

    def test_le_total_d_une_section_ne_compte_que_ses_lignes(self):
        section_a = self._section('A', 'Bâtiment A')
        self._section('B', 'Bâtiment B')
        self._ligne(1, '10', '100.00', section=section_a)
        self._ligne(2, '10', '100.00')
        self.assertEqual(section_a.total_ht, Decimal('1000.00'))
        self.assertEqual(self.bordereau.sous_total_ht, Decimal('2000.00'))


class TestClauseDeReserve(BaseBordereau):
    def test_un_marche_a_prix_unitaires_sans_clause_est_refuse(self):
        self.bordereau.clause_reserve = ''
        with self.assertRaises(ValidationError) as ctx:
            self.bordereau.clean()
        self.assertIn('clause de réserve',
                      ' '.join(ctx.exception.message_dict['clause_reserve']))

    def test_le_serializer_refuse_aussi(self):
        # `intitule` distinct de celui du bordereau du setUp : sans lui, la
        # contrainte d'unicité (appel_offre, intitule, indice_revision) —
        # ajoutée par YDATA — répond AVANT la validation métier, et le test
        # ne prouverait plus rien sur la clause de réserve.
        serializer = BordereauPrixSerializer(data={
            'appel_offre': self.ao.id, 'intitule': 'Bordereau bis',
            'marche_prix_unitaires': True, 'clause_reserve': '   '})
        self.assertFalse(serializer.is_valid())
        self.assertIn('clause_reserve', serializer.errors)

    def test_un_marche_a_prix_global_n_exige_rien(self):
        self.bordereau.marche_prix_unitaires = False
        self.bordereau.clause_reserve = ''
        self.assertEqual(self.bordereau.raisons_de_non_conformite(), [])


class TestTracabiliteDesQuantites(BaseBordereau):
    def setUp(self):
        super().setUp()
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment, code_document='05H')
        self.variante = VarianteCalepinage.objects.create(
            company=self.company, toiture=toiture, appel_offre=self.ao,
            nom='Retenue', est_retenue=True,
            resultat={'total_modules': 314})

    def test_une_quantite_de_calepinage_cite_sa_variante(self):
        ligne = self._ligne(
            1, '314', '2950.00',
            quantite_source=LigneBordereau.QuantiteSource.CALEPINAGE,
            variante=self.variante)
        self.assertEqual(ligne.raisons_de_non_tracabilite(), [])
        self.assertEqual(ligne.variante.total_modules, 314)

    def test_une_quantite_de_calepinage_sans_variante_est_signalee(self):
        ligne = self._ligne(
            1, '314', '2950.00',
            quantite_source=LigneBordereau.QuantiteSource.CALEPINAGE)
        raisons = ligne.raisons_de_non_tracabilite()
        self.assertEqual(len(raisons), 1)
        self.assertIn('AUCUNE variante', raisons[0])

    def test_le_serializer_refuse_une_quantite_de_calepinage_orpheline(self):
        serializer = LigneBordereauSerializer(data={
            'bordereau': self.bordereau.id, 'numero': 1,
            'designation': 'Modules', 'quantite': '314',
            'prix_unitaire': '2950.00', 'quantite_source': 'calepinage'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('variante', serializer.errors)

    def test_une_quantite_manuelle_n_exige_pas_de_variante(self):
        ligne = self._ligne(1, '1', '120000.00',
                            designation='Génie civil')
        self.assertEqual(ligne.quantite_source, 'manuelle')
        self.assertEqual(ligne.raisons_de_non_tracabilite(), [])

    def test_le_verrou_de_quantite_existe(self):
        ligne = self._ligne(1, '10', '100.00', quantite_verrouillee=True)
        self.assertTrue(ligne.quantite_verrouillee)

    def test_le_controle_agrege_les_deux_familles_de_motifs(self):
        self.bordereau.clause_reserve = ''
        self.bordereau.save(update_fields=['clause_reserve'])
        self._ligne(1, '314', '2950.00',
                    quantite_source=LigneBordereau.QuantiteSource.CALEPINAGE)
        raisons = services.raisons_bordereau_non_remettable(self.bordereau)
        self.assertEqual(len(raisons), 2)
