"""AOF146 — contrôleur de cohérence croisée : une PORTE, pas un rapport.

Ce qui est prouvé ici — **les trois défauts RÉELS de la session** :

1. **bordereau frère périmé** — deux bordereaux du même AO à des montants
   différents (5 219 280 vs 4 999 920) ;
2. **« LISEZ-MOI » figé** — une pièce produite sous une empreinte antérieure
   reste dans le pack alors que le dossier a bougé ;
3. **en-tête contredit par son propre addendum** — le montant de l'en-tête
   n'est plus celui du bordereau.

Plus : la transition ``pret_a_deposer`` est REFUSÉE en CITANT le code de règle
fautif, et une règle non branchée ne rend jamais un vert silencieux.

Run :
    python manage.py test apps.ao.tests.test_aof_coherence -v2
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from apps.ao import controles, services
from apps.ao.fabrique import coherence
from apps.ao.models import (
    AppelOffre, BatimentAO, BordereauPrix, ControleCoherence, DossierAO,
    EquipementAO, LigneBordereau, ObstacleAO, PieceDossierAO, ToitureAO,
    VarianteCalepinage,
)
from authentication.models import Company

CLAUSE = 'Marché à prix unitaires — quantités prévisionnelles.'


class TestRegistre(SimpleTestCase):
    def test_les_invariants_sont_enregistres(self):
        for code in ('AO_MONTANT_UNIQUE', 'AO_MONTANT_ENTETE',
                     'AO_LETTRES_RECALCULEES', 'AO_TOTAL_LIGNES',
                     'AO_NUMEROTATION_BORDEREAU', 'AO_CLAUSE_RESERVE',
                     'AO_QUANTITES_PLANCHES', 'AO_KWC_COHERENT',
                     'AO_REFERENCE_PRODUIT_UNIQUE', 'AO_PLANCHES_CITEES',
                     'AO_FICHES_ANNEXES', 'AO_ARTEFACT_PERIME',
                     'AO_PIECES_OBLIGATOIRES', 'AO_OBSTACLES_NON_MESURES',
                     'AO_COTES_A_CONFIRMER', 'AO_SANITISATION'):
            self.assertIn(code, controles.REGLES, code)

    def test_une_regle_qui_leve_ne_rend_jamais_un_vert(self):
        @controles.regle('AO_TEST_EXPLOSIF', 'Règle qui lève')
        def _explose(ctx):
            raise RuntimeError('boum')

        try:
            resultats = controles.executer_regles(
                {}, codes={'AO_TEST_EXPLOSIF'})
        finally:
            controles.REGLES.pop('AO_TEST_EXPLOSIF', None)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]['code_regle'], 'AO_REGLE_EN_ERREUR')
        self.assertIn("n'a PAS été vérifié", resultats[0]['message'])


class BaseCoherence(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF146 Co',
                                              slug='aof146-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-146-1', objet='Cohérence')
        self.dossier = services.creer_dossier_ao(self.company, self.ao)
        self.bordereau = self._bordereau('A', '4166600.00')

    def _bordereau(self, indice, montant_ht):
        bordereau = BordereauPrix.objects.create(
            company=self.company, appel_offre=self.ao,
            indice_revision=indice, clause_reserve=CLAUSE)
        LigneBordereau.objects.create(
            company=self.company, bordereau=bordereau, numero=1,
            designation='Fourniture et pose', unite='Ens',
            quantite=Decimal('1'), prix_unitaire=Decimal(montant_ht))
        return bordereau

    def _passe(self):
        return coherence.passer_controle(self.dossier)

    def _codes(self, passe):
        return {item['code_regle'] for item in passe['bloquants']}


class TestDefautReelBordereauFrere(BaseCoherence):
    """Défaut n°1 : un bordereau FRÈRE périmé traîne dans le dépôt."""

    def test_un_seul_bordereau_est_propre(self):
        self.assertNotIn('AO_MONTANT_UNIQUE', self._codes(self._passe()))

    def test_deux_bordereaux_divergents_sont_bloquants(self):
        self._bordereau('B', '4349400.00')  # 5 219 280 TTC
        passe = self._passe()
        self.assertIn('AO_MONTANT_UNIQUE', self._codes(passe))
        message = next(item['message'] for item in passe['bloquants']
                       if item['code_regle'] == 'AO_MONTANT_UNIQUE')
        self.assertIn('4999920.00', message)
        self.assertIn('5219280.00', message)
        self.assertIn('fichiers frères périmés', message)

    def test_deux_bordereaux_au_meme_montant_ne_bloquent_pas(self):
        self._bordereau('B', '4166600.00')
        self.assertNotIn('AO_MONTANT_UNIQUE', self._codes(self._passe()))


class TestDefautReelEnteteContredite(BaseCoherence):
    """Défaut n°3 : l'en-tête contredit son propre addendum."""

    def test_un_entete_divergent_est_bloquant(self):
        self.ao.montant_offre_ttc = Decimal('5219280.00')
        self.ao.save(update_fields=['montant_offre_ttc'])
        passe = self._passe()
        self.assertIn('AO_MONTANT_ENTETE', self._codes(passe))
        message = next(item['message'] for item in passe['bloquants']
                       if item['code_regle'] == 'AO_MONTANT_ENTETE')
        self.assertIn('5219280.00', message)
        self.assertIn('4999920.00', message)

    def test_un_entete_aligne_ne_bloque_pas(self):
        self.ao.montant_offre_ttc = Decimal('4999920.00')
        self.ao.montant_offre_ht = Decimal('4166600.00')
        self.ao.save(update_fields=['montant_offre_ttc', 'montant_offre_ht'])
        self.assertNotIn('AO_MONTANT_ENTETE', self._codes(self._passe()))


class TestDefautReelArtefactFige(BaseCoherence):
    """Défaut n°2 : le « LISEZ-MOI » figé resté dans le dépôt."""

    def test_une_piece_a_l_empreinte_courante_est_propre(self):
        empreinte = coherence.empreinte_dossier(self.dossier)
        PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, code='00',
            libelle='LISEZ-MOI', presente=True, empreinte_source=empreinte)
        self.assertNotIn('AO_ARTEFACT_PERIME', self._codes(self._passe()))

    def test_une_piece_a_l_empreinte_perimee_est_bloquante(self):
        PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, code='00',
            libelle='LISEZ-MOI', presente=True,
            empreinte_source='0' * 64)
        passe = self._passe()
        self.assertIn('AO_ARTEFACT_PERIME', self._codes(passe))
        message = next(item['message'] for item in passe['bloquants']
                       if item['code_regle'] == 'AO_ARTEFACT_PERIME')
        self.assertIn('LISEZ-MOI', message)
        self.assertIn('PÉRIMÉ', message)

    def test_l_empreinte_bouge_quand_le_bordereau_bouge(self):
        avant = coherence.empreinte_dossier(self.dossier)
        LigneBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, numero=2,
            designation='Ajout', unite='U', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000.00'))
        self.assertNotEqual(coherence.empreinte_dossier(self.dossier), avant)

    def test_une_piece_sans_empreinte_n_est_pas_declaree_perimee(self):
        PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, code='00',
            libelle='Fournie à la main', presente=True)
        self.assertNotIn('AO_ARTEFACT_PERIME', self._codes(self._passe()))


class TestAutresInvariants(BaseCoherence):
    def test_numerotation_trouee_et_pu_nul(self):
        LigneBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, numero=5,
            designation='Trou', unite='U', quantite=Decimal('1'),
            prix_unitaire=Decimal('0.00'))
        passe = self._passe()
        messages = ' '.join(item['message'] for item in passe['bloquants'])
        self.assertIn('Numérotation du bordereau interrompue', messages)
        self.assertIn('prix unitaire NUL', messages)

    def test_unite_manquante(self):
        LigneBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, numero=2,
            designation='Sans unité', unite='', quantite=Decimal('1'),
            prix_unitaire=Decimal('10.00'))
        messages = ' '.join(item['message']
                            for item in self._passe()['bloquants'])
        self.assertIn('unité non renseignée', messages)

    def test_deux_references_actives_du_meme_role(self):
        services.engager_equipement(
            self.ao, role=EquipementAO.Role.BATTERIE, designation='BOS-G')
        services.engager_equipement(
            self.ao, role=EquipementAO.Role.BATTERIE,
            designation='BOS-B Pro-A3')
        passe = self._passe()
        self.assertIn('AO_REFERENCE_PRODUIT_UNIQUE', self._codes(passe))
        message = next(item['message'] for item in passe['bloquants']
                       if item['code_regle'] == 'AO_REFERENCE_PRODUIT_UNIQUE')
        self.assertIn('bascule', message)

    def test_quantite_bordereau_contre_engagement_des_planches(self):
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment, code_document='05')
        variante = VarianteCalepinage.objects.create(
            company=self.company, toiture=toiture, appel_offre=self.ao,
            nom='Retenue', est_retenue=True,
            resultat={'total_modules': 314})
        LigneBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, numero=2,
            designation='Modules', unite='U', quantite=Decimal('264'),
            prix_unitaire=Decimal('2950.00'),
            quantite_source=LigneBordereau.QuantiteSource.CALEPINAGE,
            variante=variante)
        passe = self._passe()
        self.assertIn('AO_QUANTITES_PLANCHES', self._codes(passe))
        message = next(item['message'] for item in passe['bloquants']
                       if item['code_regle'] == 'AO_QUANTITES_PLANCHES')
        self.assertIn('264', message)
        self.assertIn('314', message)

    def test_obstacle_non_mesure_encore_actif(self):
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment, code_document='05')
        ObstacleAO.objects.create(
            company=self.company, toiture=toiture, repere='D',
            nature=ObstacleAO.Nature.SOUCHE,
            provenance=ObstacleAO.Provenance.DEVINE)
        self.assertIn('AO_OBSTACLES_NON_MESURES', self._codes(self._passe()))

    def test_la_sanitisation_non_branchee_avertit_au_lieu_de_verdir(self):
        passe = self._passe()
        codes = {item['code_regle'] for item in passe['avertissements']}
        self.assertIn('AO_SANITISATION', codes)
        message = next(item['message'] for item in passe['avertissements']
                       if item['code_regle'] == 'AO_SANITISATION')
        self.assertIn("n'a donc PAS été vérifié", message)

    def test_aucun_champ_ne_stocke_un_montant_en_lettres(self):
        self.assertNotIn('AO_LETTRES_RECALCULEES', self._codes(self._passe()))


class TestPersistanceDeLaPasse(BaseCoherence):
    def test_la_passe_persiste_ses_lignes_avec_l_empreinte(self):
        passe = self._passe()
        lignes = ControleCoherence.objects.filter(dossier=self.dossier)
        self.assertEqual(lignes.count(), len(passe['resultats']))
        self.assertTrue(all(ligne.empreinte == passe['empreinte']
                            for ligne in lignes))

    def test_une_nouvelle_passe_remplace_la_precedente(self):
        self._bordereau('B', '4349400.00')
        premiere = self._passe()
        self.assertIn('AO_MONTANT_UNIQUE', self._codes(premiere))
        BordereauPrix.objects.filter(indice_revision='B').delete()
        seconde = self._passe()
        self.assertNotIn('AO_MONTANT_UNIQUE', self._codes(seconde))
        self.assertFalse(ControleCoherence.objects.filter(
            dossier=self.dossier, code_regle='AO_MONTANT_UNIQUE').exists())


class TestPorteDeDepot(BaseCoherence):
    def _amener_au_controle(self):
        PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, code='04',
            libelle='Bordereau', presente=True)
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.EN_CONSTITUTION)
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.CONTROLE)

    def test_la_transition_est_refusee_en_citant_le_code_de_regle(self):
        self._bordereau('B', '4349400.00')
        self._amener_au_controle()
        with self.assertRaises(ValidationError) as ctx:
            services.changer_statut_dossier(
                self.dossier, DossierAO.Statut.PRET_A_DEPOSER)
        motifs = ' '.join(ctx.exception.message_dict['controles'])
        self.assertIn('AO_MONTANT_UNIQUE', motifs)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.statut, DossierAO.Statut.CONTROLE)

    def test_un_dossier_coherent_franchit_la_porte(self):
        self._amener_au_controle()
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.PRET_A_DEPOSER)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.statut,
                         DossierAO.Statut.PRET_A_DEPOSER)

    def test_un_avertissement_ne_ferme_pas_la_porte(self):
        services.engager_equipement(
            self.ao, role=EquipementAO.Role.MODULE, designation='Module')
        self._amener_au_controle()
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.PRET_A_DEPOSER)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.statut,
                         DossierAO.Statut.PRET_A_DEPOSER)
