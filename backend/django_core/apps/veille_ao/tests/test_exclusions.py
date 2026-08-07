"""VAO10 — « Ignorer » doit APPRENDRE, et jamais filtrer en silence.

Ce qui est vérifié :
  * une règle active écarte automatiquement les avis suivants ;
  * l'avis auto-ignoré AFFICHE la règle qui l'a filtré (jamais un filtrage
    muet) ;
  * désactiver une règle fait RÉAPPARAÎTRE les avis suivants ;
  * le compteur d'application monte, et de façon atomique ;
  * proposer une règle depuis un avis ne la CRÉE jamais en douce ;
  * tout reste scopé société.
"""
from django.test import TestCase

from apps.veille_ao.models import (
    AvisMarche, CategorieAvis, PorteeExclusion, RegleExclusion, SourceVeille,
    StatutAvis, TypeSource,
)
from apps.veille_ao.services import (
    appliquer_regles_exclusion, avis_ignores_par, proposer_regle_pour_avis,
    regle_correspondante, regle_mord, regles_actives,
)
from authentication.models import Company


class BaseExclusion(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Exclusion')
        cls.source = SourceVeille.objects.create(
            company=cls.company, code='src', libelle='Source',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test', actif=True)

    def _avis(self, **kwargs):
        params = {
            'company': self.company,
            'source': self.source,
            'objet': 'Travaux de voirie et assainissement',
            'acheteur': 'Commune de Bruit',
            'region': 'Oriental',
            'categorie': CategorieAvis.TRAVAUX,
        }
        params.update(kwargs)
        return AvisMarche.objects.create(**params)

    def _regle(self, **kwargs):
        params = {
            'company': self.company,
            'portee': PorteeExclusion.ACHETEUR,
            'valeur': 'Commune de Bruit',
            'motif': 'Acheteur hors périmètre solaire',
            'actif': True,
        }
        params.update(kwargs)
        return RegleExclusion.objects.create(**params)


class CorrespondanceTests(BaseExclusion):
    def test_portee_acheteur(self):
        self.assertTrue(regle_mord(self._regle(), self._avis()))

    def test_portee_libelle_sur_un_mot_de_l_objet(self):
        regle = self._regle(portee=PorteeExclusion.LIBELLE, valeur='voirie')
        self.assertTrue(regle_mord(regle, self._avis()))

    def test_portee_region(self):
        regle = self._regle(portee=PorteeExclusion.REGION, valeur='Oriental')
        self.assertTrue(regle_mord(regle, self._avis()))

    def test_portee_categorie_est_comparee_a_l_identique(self):
        regle = self._regle(portee=PorteeExclusion.CATEGORIE,
                            valeur=CategorieAvis.TRAVAUX)
        self.assertTrue(regle_mord(regle, self._avis()))
        partielle = self._regle(portee=PorteeExclusion.CATEGORIE,
                                valeur='trav')
        self.assertFalse(regle_mord(partielle, self._avis()))

    def test_comparaison_insensible_a_la_casse_et_aux_accents(self):
        regle = self._regle(valeur='COMMUNE DE BRUIT')
        self.assertTrue(regle_mord(regle, self._avis()))
        accentuee = self._regle(portee=PorteeExclusion.REGION,
                                valeur='oriental')
        self.assertTrue(regle_mord(accentuee, self._avis()))

    def test_regle_qui_ne_mord_pas(self):
        regle = self._regle(valeur='Ministère de la Santé')
        self.assertFalse(regle_mord(regle, self._avis()))

    def test_valeur_vide_ne_mord_jamais_tout(self):
        """Une règle vide écarterait TOUS les avis — interdit."""
        regle = self._regle(valeur='')
        self.assertFalse(regle_mord(regle, self._avis()))


class ApplicationAutomatiqueTests(BaseExclusion):
    def test_avis_capte_est_marque_ignore(self):
        regle = self._regle()
        avis = self._avis()
        appliquee = appliquer_regles_exclusion(avis)
        self.assertEqual(appliquee, regle)
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.IGNORE)

    def test_avis_auto_ignore_affiche_sa_regle(self):
        """Jamais un filtrage muet : l'avis porte la règle qui l'a filtré."""
        regle = self._regle()
        avis = self._avis()
        appliquer_regles_exclusion(avis)
        avis.refresh_from_db()
        self.assertEqual(avis.regle_exclusion_id, regle.pk)
        self.assertEqual(avis.regle_exclusion.motif,
                         'Acheteur hors périmètre solaire')

    def test_avis_non_capte_reste_nouveau_et_sans_regle(self):
        self._regle(valeur='Un autre acheteur')
        avis = self._avis()
        self.assertIsNone(appliquer_regles_exclusion(avis))
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.NOUVEAU)
        self.assertIsNone(avis.regle_exclusion_id)

    def test_regle_desactivee_fait_reapparaitre_les_avis_suivants(self):
        regle = self._regle()
        appliquer_regles_exclusion(self._avis())

        regle.actif = False
        regle.save(update_fields=['actif'])

        avis_suivant = self._avis(objet='Autre avis du même acheteur')
        self.assertIsNone(appliquer_regles_exclusion(avis_suivant))
        avis_suivant.refresh_from_db()
        self.assertEqual(avis_suivant.statut, StatutAvis.NOUVEAU)

    def test_compteur_application_monte(self):
        regle = self._regle()
        appliquer_regles_exclusion(self._avis())
        appliquer_regles_exclusion(self._avis(objet='Deuxième avis'))
        regle.refresh_from_db()
        self.assertEqual(regle.compteur_application, 2)

    def test_compteur_inchange_quand_la_regle_ne_mord_pas(self):
        regle = self._regle(valeur='Aucun rapport')
        appliquer_regles_exclusion(self._avis())
        regle.refresh_from_db()
        self.assertEqual(regle.compteur_application, 0)

    def test_avis_ignores_par_regle(self):
        regle = self._regle()
        appliquer_regles_exclusion(self._avis())
        appliquer_regles_exclusion(self._avis(objet='Deuxième avis'))
        self.assertEqual(avis_ignores_par(regle).count(), 2)

    def test_premiere_regle_qui_mord_est_celle_appliquee(self):
        premiere = self._regle(portee=PorteeExclusion.ACHETEUR,
                               valeur='Commune de Bruit')
        self._regle(portee=PorteeExclusion.LIBELLE, valeur='voirie')
        avis = self._avis()
        self.assertEqual(
            regle_correspondante(avis, [premiere]), premiere)
        self.assertIsNotNone(appliquer_regles_exclusion(avis))


class PropositionSansCreationTests(BaseExclusion):
    """« Ignorer un avis PROPOSE la règle, sans jamais la créer en douce. »"""

    def test_proposition_ne_cree_aucune_regle(self):
        avis = self._avis()
        avant = RegleExclusion.objects.filter(company=self.company).count()
        proposition = proposer_regle_pour_avis(avis)
        apres = RegleExclusion.objects.filter(company=self.company).count()
        self.assertEqual(avant, apres)
        self.assertEqual(proposition['valeur'], 'Commune de Bruit')
        self.assertEqual(proposition['portee'], PorteeExclusion.ACHETEUR)
        self.assertFalse(proposition['existe_deja'])

    def test_proposition_signale_une_regle_deja_presente(self):
        regle = self._regle()
        proposition = proposer_regle_pour_avis(self._avis())
        self.assertTrue(proposition['existe_deja'])
        self.assertEqual(proposition['regle_existante_id'], regle.pk)
        self.assertTrue(proposition['regle_existante_active'])

    def test_proposition_signale_une_regle_desactivee(self):
        """L'écran doit proposer de RÉACTIVER, pas de créer une jumelle."""
        self._regle(actif=False)
        proposition = proposer_regle_pour_avis(self._avis())
        self.assertTrue(proposition['existe_deja'])
        self.assertFalse(proposition['regle_existante_active'])

    def test_proposition_sur_une_autre_portee(self):
        proposition = proposer_regle_pour_avis(
            self._avis(), portee=PorteeExclusion.REGION)
        self.assertEqual(proposition['valeur'], 'Oriental')
        self.assertIn('Oriental', proposition['motif_suggere'])

    def test_motif_suggere_vide_si_le_champ_est_vide(self):
        proposition = proposer_regle_pour_avis(
            self._avis(region=''), portee=PorteeExclusion.REGION)
        self.assertEqual(proposition['valeur'], '')
        self.assertEqual(proposition['motif_suggere'], '')


class IsolationParSocieteTests(BaseExclusion):
    def test_une_regle_d_une_autre_societe_ne_mord_jamais(self):
        autre = Company.objects.create(nom='Autre Exclusion')
        RegleExclusion.objects.create(
            company=autre, portee=PorteeExclusion.ACHETEUR,
            valeur='Commune de Bruit', motif='Règle du voisin', actif=True)
        avis = self._avis()
        self.assertEqual(regles_actives(self.company), [])
        self.assertIsNone(appliquer_regles_exclusion(avis))
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.NOUVEAU)
