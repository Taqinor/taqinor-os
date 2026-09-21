"""VAO11 — dédoublonnage à DEUX niveaux : le cœur de fiabilité du groupe.

Ce qui est vérifié :
  * rejouer deux fois la même collecte ne crée AUCUN doublon (niveau 1) ;
  * un avis RECTIFIÉ, qui ressort avec un NOUVEL identifiant de portail, met
    à jour l'existant au lieu de dupliquer (niveau 2) ;
  * un même avis saisi à la main puis collecté automatiquement FUSIONNE ;
  * deux avis du même acheteur, même date, mais de références différentes
    restent DEUX avis (garde anti-sur-fusion : sur le portail, un acheteur
    publie couramment plusieurs lots qui ferment le même jour) ;
  * la normalisation (casse, accents, espaces) est testée ;
  * un statut décidé par un humain n'est jamais écrasé par une re-collecte.
"""
import datetime as dt

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.veille_ao.hashing import (
    empreinte_avis, empreinte_pour_avis, normaliser_date, normaliser_texte,
)
from apps.veille_ao.models import AvisMarche, SourceVeille, StatutAvis, TypeSource
from apps.veille_ao.services import (
    calculer_empreinte, enregistrer_avis, trouver_avis_existant,
)
from authentication.models import Company

LIMITE = timezone.make_aware(dt.datetime(2026, 9, 30, 10, 0))


class NormalisationTests(SimpleTestCase):
    def test_casse_accents_espaces(self):
        self.assertEqual(
            normaliser_texte('  COMMUNE   DE  FIGUIG '),
            'commune de figuig')
        self.assertEqual(normaliser_texte('Préfecture'), 'prefecture')

    def test_valeur_vide(self):
        self.assertEqual(normaliser_texte(''), '')
        self.assertEqual(normaliser_texte(None), '')

    def test_normalisation_de_date(self):
        self.assertEqual(normaliser_date(None), '')
        self.assertEqual(normaliser_date(''), '')
        self.assertEqual(normaliser_date(LIMITE), LIMITE.isoformat())


class EmpreinteTests(SimpleTestCase):
    def test_empreinte_deterministe(self):
        a = empreinte_avis('AO 12/2026', 'Commune de Figuig', LIMITE)
        b = empreinte_avis('AO 12/2026', 'Commune de Figuig', LIMITE)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)

    def test_empreinte_insensible_a_la_casse_et_aux_accents(self):
        self.assertEqual(
            empreinte_avis('ao 12/2026', 'commune de figuig', LIMITE),
            empreinte_avis('AO  12/2026', 'Commune de FIGUIG', LIMITE))

    def test_empreintes_differentes_sur_reference_differente(self):
        self.assertNotEqual(
            empreinte_avis('AO 12/2026', 'Commune', LIMITE),
            empreinte_avis('AO 13/2026', 'Commune', LIMITE))

    def test_empreintes_differentes_sur_date_differente(self):
        self.assertNotEqual(
            empreinte_avis('AO 12/2026', 'Commune', LIMITE),
            empreinte_avis('AO 12/2026', 'Commune',
                           LIMITE + dt.timedelta(days=1)))

    def test_avis_sans_matiere_n_a_pas_d_empreinte(self):
        """Une empreinte de vide serait un aimant à faux doublons."""
        self.assertEqual(empreinte_avis('', '', None), '')

    def test_date_limite_absente_reste_empreignable(self):
        self.assertNotEqual(empreinte_avis('AO 12/2026', 'Commune', None), '')


class BaseDedoublonnage(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Dedoublonnage')
        cls.portail = SourceVeille.objects.create(
            company=cls.company, code='pmmp', libelle='Portail',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test', actif=True)
        cls.manuelle = SourceVeille.objects.create(
            company=cls.company, code='manuel', libelle='Saisie manuelle',
            type_source=TypeSource.SAISIE_MANUELLE, actif=True)

    def _donnees(self, **kwargs):
        donnees = {
            'ref_consultation': '918273',
            'org_acronyme': 'C123',
            'reference_avis': 'AO 12/2026',
            'objet': 'Pompage solaire pour abreuvement du cheptel',
            'acheteur': 'Commune de Figuig',
            'date_limite_remise': LIMITE,
        }
        donnees.update(kwargs)
        return donnees


class Niveau1IdentitePortailTests(BaseDedoublonnage):
    def test_collecte_rejouee_ne_cree_aucun_doublon(self):
        avis, cree, _ = enregistrer_avis(
            self.company, self.portail, self._donnees())
        self.assertTrue(cree)

        meme, recree, niveau = enregistrer_avis(
            self.company, self.portail, self._donnees())

        self.assertFalse(recree)
        self.assertEqual(niveau, 1)
        self.assertEqual(meme.pk, avis.pk)
        self.assertEqual(
            AvisMarche.objects.filter(company=self.company).count(), 1)

    def test_deux_identifiants_de_portail_distincts_font_deux_avis(self):
        enregistrer_avis(self.company, self.portail, self._donnees())
        enregistrer_avis(self.company, self.portail, self._donnees(
            ref_consultation='918274', reference_avis='AO 13/2026'))
        self.assertEqual(
            AvisMarche.objects.filter(company=self.company).count(), 2)

    def test_trouver_avis_existant_rend_le_niveau(self):
        enregistrer_avis(self.company, self.portail, self._donnees())
        _, niveau = trouver_avis_existant(
            self.company, self.portail, self._donnees())
        self.assertEqual(niveau, 1)

    def test_avis_inconnu_rend_niveau_zero(self):
        existant, niveau = trouver_avis_existant(
            self.company, self.portail, self._donnees())
        self.assertIsNone(existant)
        self.assertEqual(niveau, 0)


class Niveau2EmpreinteTests(BaseDedoublonnage):
    def test_avis_rectifie_met_a_jour_sans_dupliquer(self):
        """Un avis rectifié ressort avec un NOUVEL identifiant de portail :
        le niveau 1 le croirait neuf, le niveau 2 le reconnaît."""
        avis, _, _ = enregistrer_avis(
            self.company, self.portail, self._donnees())

        rectifie, cree, niveau = enregistrer_avis(
            self.company, self.portail,
            self._donnees(ref_consultation='999999',
                          objet='Pompage solaire — objet rectifié'))

        self.assertFalse(cree)
        self.assertEqual(niveau, 2)
        self.assertEqual(rectifie.pk, avis.pk)
        self.assertEqual(
            AvisMarche.objects.filter(company=self.company).count(), 1)
        self.assertEqual(rectifie.objet,
                         'Pompage solaire — objet rectifié')
        self.assertEqual(rectifie.ref_consultation, '999999')

    def test_rectification_journalisee_sur_l_avis(self):
        """Une fusion silencieuse est un bug qu'on ne peut plus expliquer."""
        enregistrer_avis(self.company, self.portail, self._donnees())
        rectifie, _, _ = enregistrer_avis(
            self.company, self.portail,
            self._donnees(ref_consultation='999999', objet='Objet corrigé'))

        rectifie.refresh_from_db()
        historique = rectifie.donnees_brutes.get('rectifications')
        self.assertEqual(len(historique), 1)
        self.assertEqual(historique[0]['niveau_dedoublonnage'], 2)
        self.assertIn('objet', historique[0]['changements'])

    def test_saisie_manuelle_puis_collecte_fusionnent(self):
        """Le filet de niveau 2 traverse les SOURCES à dessein."""
        manuel, cree, _ = enregistrer_avis(
            self.company, self.manuelle,
            {'reference_avis': 'AO 12/2026',
             'objet': 'Pompage solaire (signalé par un partenaire)',
             'acheteur': 'Commune de Figuig',
             'date_limite_remise': LIMITE})
        self.assertTrue(cree)

        collecte, recree, niveau = enregistrer_avis(
            self.company, self.portail, self._donnees())

        self.assertFalse(recree)
        self.assertEqual(niveau, 2)
        self.assertEqual(collecte.pk, manuel.pk)
        self.assertEqual(
            AvisMarche.objects.filter(company=self.company).count(), 1)
        # L'identité de portail est acquise par la fusion.
        self.assertEqual(collecte.ref_consultation, '918273')

    def test_meme_acheteur_meme_date_mais_references_differentes_ne_fusionnent_pas(self):
        """Garde ANTI-SUR-FUSION : un acheteur publie couramment plusieurs
        lots qui ferment le même jour — les fusionner perdrait des avis."""
        enregistrer_avis(
            self.company, self.manuelle,
            {'reference_avis': 'AO 12/2026 lot 1',
             'objet': 'Lot 1', 'acheteur': 'Commune de Figuig',
             'date_limite_remise': LIMITE})
        enregistrer_avis(
            self.company, self.manuelle,
            {'reference_avis': 'AO 12/2026 lot 2',
             'objet': 'Lot 2', 'acheteur': 'Commune de Figuig',
             'date_limite_remise': LIMITE})
        self.assertEqual(
            AvisMarche.objects.filter(company=self.company).count(), 2)

    def test_empreinte_ecrite_a_la_creation(self):
        avis, _, _ = enregistrer_avis(
            self.company, self.portail, self._donnees())
        self.assertNotEqual(avis.empreinte, '')
        self.assertEqual(avis.empreinte,
                         calculer_empreinte(self._donnees()))
        self.assertEqual(avis.empreinte, empreinte_pour_avis(avis))

    def test_normalisation_appliquee_au_dedoublonnage(self):
        enregistrer_avis(
            self.company, self.manuelle,
            {'reference_avis': 'AO 12/2026', 'objet': 'Objet',
             'acheteur': 'Commune de Figuig',
             'date_limite_remise': LIMITE})
        _, cree, niveau = enregistrer_avis(
            self.company, self.manuelle,
            {'reference_avis': '  ao   12/2026 ', 'objet': 'Objet',
             'acheteur': 'COMMUNE DE FIGUIG',
             'date_limite_remise': LIMITE})
        self.assertFalse(cree)
        self.assertEqual(niveau, 2)
        self.assertEqual(
            AvisMarche.objects.filter(company=self.company).count(), 1)


class ArbitrageHumainPreserveTests(BaseDedoublonnage):
    def test_une_recollecte_n_ecrase_jamais_le_statut(self):
        """Un avis que l'utilisateur a retenu ne redevient pas « nouveau »."""
        avis, _, _ = enregistrer_avis(
            self.company, self.portail, self._donnees())
        avis.statut = StatutAvis.RETENU
        avis.save(update_fields=['statut'])

        enregistrer_avis(self.company, self.portail,
                         self._donnees(objet='Objet mis à jour'))

        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.RETENU)
        self.assertEqual(avis.objet, 'Objet mis à jour')

    def test_une_recollecte_n_efface_pas_le_lien_vers_l_appel_offre(self):
        avis, _, _ = enregistrer_avis(
            self.company, self.portail, self._donnees())
        avis.statut = StatutAvis.CONVERTI
        avis.appel_offre_id = 4242
        avis.save(update_fields=['statut', 'appel_offre_id'])

        enregistrer_avis(self.company, self.portail, self._donnees())

        avis.refresh_from_db()
        self.assertEqual(avis.appel_offre_id, 4242)
        self.assertEqual(avis.statut, StatutAvis.CONVERTI)


class IsolationParSocieteTests(BaseDedoublonnage):
    def test_le_dedoublonnage_ne_traverse_jamais_les_societes(self):
        autre = Company.objects.create(nom='Autre Dedoublonnage')
        source_autre = SourceVeille.objects.create(
            company=autre, code='pmmp', libelle='Portail',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test', actif=True)

        enregistrer_avis(self.company, self.portail, self._donnees())
        _, cree, _ = enregistrer_avis(autre, source_autre, self._donnees())

        self.assertTrue(cree)
        self.assertEqual(
            AvisMarche.objects.filter(company=self.company).count(), 1)
        self.assertEqual(AvisMarche.objects.filter(company=autre).count(), 1)
