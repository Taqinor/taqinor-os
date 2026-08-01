"""AOF166 — KPI AO + tableau de bord des marchés (supersede NTMAR27).

Quatre choses sont verrouillées ici, et ce sont exactement celles qui font
qu'un tableau de bord sert à quelque chose :

  1. **UN SEUL appel agrégé** sert le tableau (le front ne compose pas six
     requêtes) — et l'endpoint porte le NOM repris de NTMAR27,
     ``/api/django/ao/tableau-marches/``, pour qu'il n'existe jamais deux
     tableaux de bord d'AO concurrents.
  2. **Le taux de réussite est CALCULÉ** depuis ``ResultatAO``, jamais saisi :
     aucun champ « taux de réussite » n'existe sur aucun modèle AO, et le test
     le prouve par introspection.
  3. **Les cautions immobilisées remontent en montant** (le KPI propre de
     NTMAR27), et une caution restituée n'immobilise plus rien.
  4. **Aucun coût, aucune marge, aucun ``prix_achat``** ne sort du tableau ni
     des tuiles — c'est un écran ``ao_voir``, pas un écran directeur.

Run :
    python manage.py test apps.ao.tests.test_kpis_ao -v2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import kpis, selectors
from apps.ao.models import (
    AppelOffre, BatimentAO, CautionSoumission, EcheanceAO, ResultatAO,
    ToitureAO, VarianteCalepinage,
)
from apps.ao.platform import PLATFORM
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/tableau-marches/'


def _company(slug):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return co


class _Base(TestCase):
    def setUp(self):
        self.company = _company('aof166-co')
        self.autre = _company('aof166-autre')
        self.role = Role.objects.create(
            company=self.company, nom='Directeur AOF166',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof166', password='x', role_legacy='responsable',
            company=self.company, role=self.role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(self.user))
        self.aujourd_hui = timezone.now().date()

    def _ao(self, reference, statut, *, company=None, jours=None, **extra):
        return AppelOffre.objects.create(
            company=company or self.company, reference=reference,
            objet='Centrale PV', acheteur='Commune', statut=statut,
            date_limite=(self.aujourd_hui + timedelta(days=jours)
                         if jours is not None else None),
            **extra)


class LeTableauEstUnSeulAppelAgrege(_Base):
    def test_les_six_blocs_sont_presents(self):
        tableau = selectors.tableau_marches(self.company)
        for bloc in ('en_cours', 'echeances_dues', 'reussite', 'capacite',
                     'cautions', 'marches_en_execution'):
            self.assertIn(bloc, tableau, bloc)

    def test_l_endpoint_porte_le_nom_repris_de_ntmar27(self):
        self.assertEqual(reverse('ao-tableau-marches'), URL)

    def test_l_endpoint_rend_le_meme_objet_que_le_selector(self):
        self._ao('AO-1', AppelOffre.Statut.ETUDE, jours=3)
        reponse = self.api.get(URL)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['en_cours']['total'],
                         selectors.tableau_marches(
                             self.company)['en_cours']['total'])

    def test_un_seul_tableau_de_bord_ao_est_route(self):
        """Deux routes de tableau de bord AO = deux chiffres pour une question."""
        from apps.ao import urls as ao_urls

        noms = [getattr(p, 'name', '') for p in ao_urls.urlpatterns]
        tableaux = [n for n in noms if n and 'tableau' in n]
        self.assertEqual(tableaux, ['ao-tableau-marches'])


class LesAOEnCoursSontRangesParEcheanceDeRemise(_Base):
    def test_le_tri_suit_la_date_limite(self):
        self._ao('AO-LOIN', AppelOffre.Statut.ETUDE, jours=30)
        self._ao('AO-PROCHE', AppelOffre.Statut.CHIFFRAGE, jours=2)
        lignes = selectors.tableau_marches(
            self.company)['en_cours']['par_echeance']
        self.assertEqual([ligne['reference'] for ligne in lignes],
                         ['AO-PROCHE', 'AO-LOIN'])

    def test_les_remises_sous_7_jours_et_en_retard_sont_comptees(self):
        self._ao('AO-URGENT', AppelOffre.Statut.DOSSIER, jours=3)
        self._ao('AO-RETARD', AppelOffre.Statut.DOSSIER, jours=-2)
        self._ao('AO-CALME', AppelOffre.Statut.DOSSIER, jours=40)
        bloc = selectors.tableau_marches(self.company)['en_cours']
        self.assertEqual(bloc['total'], 3)
        self.assertEqual(bloc['sous_7_jours'], 1)
        self.assertEqual(bloc['en_retard'], 1)

    def test_un_ao_depose_n_est_plus_en_cours(self):
        self._ao('AO-DEPOSE', AppelOffre.Statut.DEPOSE, jours=1)
        self.assertEqual(
            selectors.tableau_marches(self.company)['en_cours']['total'], 0)

    def test_le_tableau_est_borne_a_la_societe(self):
        self._ao('AO-AUTRE', AppelOffre.Statut.ETUDE, company=self.autre,
                 jours=1)
        self.assertEqual(
            selectors.tableau_marches(self.company)['en_cours']['total'], 0)


class LeTauxDeReussiteEstCalculeJamaisSaisi(_Base):
    def _resultat(self, reference, issue):
        ao = self._ao(reference, AppelOffre.Statut.DEPOSE)
        return ResultatAO.objects.create(
            company=self.company, appel_offre=ao, issue=issue)

    def test_le_taux_se_derive_des_resultats(self):
        self._resultat('AO-G1', ResultatAO.Issue.GAGNE)
        self._resultat('AO-G2', ResultatAO.Issue.GAGNE)
        self._resultat('AO-P1', ResultatAO.Issue.PERDU)
        reussite = selectors.tableau_marches(self.company)['reussite']
        self.assertEqual(reussite['gagnes'], 2)
        self.assertEqual(reussite['perdus'], 1)
        self.assertEqual(reussite['taux_reussite_pct'], Decimal('66.67'))

    def test_sans_resultat_le_taux_vaut_zero_et_pas_none(self):
        reussite = selectors.tableau_marches(self.company)['reussite']
        self.assertEqual(reussite['taux_reussite_pct'], Decimal('0.00'))

    def test_aucun_modele_ao_ne_porte_un_champ_taux_de_reussite(self):
        """Un taux SAISISSABLE serait une opinion, pas une mesure."""
        for modele in (AppelOffre, ResultatAO):
            noms = {f.name for f in modele._meta.get_fields()}
            for interdit in ('taux_reussite', 'taux_reussite_pct'):
                self.assertNotIn(interdit, noms,
                                 '%s.%s' % (modele.__name__, interdit))


class LaCapaciteDemontreeSeCompareALEngagement(_Base):
    def _variante(self, modules, *, retenue=True):
        ao = self._ao('AO-CAP-%d' % modules, AppelOffre.Statut.ETUDE)
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=ao, code='A',
            engagement_modules=150)
        toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment, code_document='05H')
        return VarianteCalepinage.objects.create(
            company=self.company, toiture=toiture, appel_offre=ao,
            nom='V1', est_retenue=retenue,
            resultat={'total_modules': modules})

    def test_la_capacite_demontree_somme_les_variantes_retenues(self):
        self._variante(178)
        capacite = selectors.tableau_marches(self.company)['capacite']
        self.assertEqual(capacite['demontree_modules'], 178)
        self.assertEqual(capacite['engagee_modules'], 150)
        self.assertEqual(capacite['ecart_modules'], 28)
        self.assertEqual(capacite['toitures_prouvees'], 1)

    def test_une_variante_non_retenue_ne_demontre_rien(self):
        self._variante(178, retenue=False)
        capacite = selectors.tableau_marches(self.company)['capacite']
        self.assertEqual(capacite['demontree_modules'], 0)
        self.assertEqual(capacite['toitures_prouvees'], 0)


class LesCautionsImmobiliseesRemontentEnMontant(_Base):
    def _caution(self, montant, statut, *, date_echeance=None,
                 date_ouverture_plis=None):
        ao = self._ao('AO-CAU-%s' % montant, AppelOffre.Statut.DEPOSE,
                      date_ouverture_plis=date_ouverture_plis)
        return CautionSoumission.objects.create(
            company=self.company, appel_offre=ao,
            montant=Decimal(str(montant)), statut=statut,
            date_echeance=date_echeance)

    def test_le_montant_total_immobilise_remonte(self):
        self._caution(50000, CautionSoumission.Statut.CONSTITUEE)
        self._caution(30000, CautionSoumission.Statut.CONSTITUEE)
        cautions = selectors.tableau_marches(self.company)['cautions']
        self.assertEqual(cautions['montant_immobilise'], Decimal('80000.00'))
        self.assertEqual(cautions['nombre'], 2)

    def test_une_caution_restituee_n_immobilise_plus_rien(self):
        self._caution(50000, CautionSoumission.Statut.RESTITUEE)
        cautions = selectors.tableau_marches(self.company)['cautions']
        self.assertEqual(cautions['montant_immobilise'], Decimal('0.00'))
        self.assertEqual(cautions['nombre'], 0)

    def test_une_caution_expirant_avant_ouverture_est_signalee(self):
        self._caution(
            50000, CautionSoumission.Statut.CONSTITUEE,
            date_ouverture_plis=self.aujourd_hui + timedelta(days=20),
            date_echeance=self.aujourd_hui + timedelta(days=5))
        cautions = selectors.tableau_marches(self.company)['cautions']
        self.assertEqual(cautions['expirant_avant_ouverture'], 1)


class LesMarchesEnExecutionEtLesEcheances(_Base):
    def test_un_ao_gagne_compte_comme_marche_en_execution(self):
        self._ao('AO-GAGNE', AppelOffre.Statut.GAGNE,
                 montant_offre_ht=Decimal('1250000.00'))
        bloc = selectors.tableau_marches(self.company)['marches_en_execution']
        self.assertEqual(bloc['total'], 1)
        self.assertEqual(bloc['montant_offre_ht'], Decimal('1250000.00'))

    def test_un_ao_perdu_n_est_pas_en_execution(self):
        self._ao('AO-PERDU', AppelOffre.Statut.PERDU)
        self.assertEqual(
            selectors.tableau_marches(
                self.company)['marches_en_execution']['total'], 0)

    def test_les_echeances_dues_sont_comptees(self):
        ao = self._ao('AO-ECH', AppelOffre.Statut.DOSSIER)
        EcheanceAO.objects.create(
            company=self.company, appel_offre=ao, libelle='Remise des plis',
            date_echeance=self.aujourd_hui + timedelta(days=1),
            rappel_jours=7)
        self.assertEqual(
            selectors.tableau_marches(self.company)['echeances_dues'], 1)


class AucunChiffreDeCoutNeSortDuTableau(_Base):
    """Le tableau est un écran ``ao_voir`` : l'économie vit ailleurs (AOF2)."""

    def _cles(self, valeur, prefixe=''):
        cles = []
        if isinstance(valeur, dict):
            for k, v in valeur.items():
                cles.append('%s%s' % (prefixe, k))
                cles.extend(self._cles(v, prefixe))
        elif isinstance(valeur, (list, tuple)):
            for v in valeur:
                cles.extend(self._cles(v, prefixe))
        return cles

    def test_aucune_cle_de_cout_dans_le_tableau(self):
        self._ao('AO-CO', AppelOffre.Statut.GAGNE,
                 montant_offre_ht=Decimal('100.00'))
        cles = [c.lower() for c in self._cles(
            selectors.tableau_marches(self.company))]
        for interdit in kpis.CLES_INTERDITES:
            for cle in cles:
                self.assertNotIn(interdit, cle,
                                 'clé interdite dans le tableau : %s' % cle)

    def test_aucune_cle_de_cout_dans_les_tuiles_kpi(self):
        cles = [c.lower() for c in self._cles(kpis.kpi_ao(self.company))]
        for interdit in kpis.CLES_INTERDITES:
            for cle in cles:
                self.assertNotIn(interdit, cle, cle)

    def test_les_libelles_de_tuiles_ne_parlent_pas_de_marge(self):
        for tuile in kpis.kpi_ao(self.company):
            libelle = tuile['label'].lower()
            for interdit in ('marge', 'coût', 'bénéfice', 'revient'):
                self.assertNotIn(interdit, libelle, tuile['label'])


class LesTuilesKPISontConformesAuHubFedere(_Base):
    def test_chaque_tuile_porte_id_label_valeur(self):
        tuiles = kpis.kpi_ao(self.company)
        self.assertTrue(tuiles)
        for tuile in tuiles:
            for cle in ('id', 'label', 'valeur'):
                self.assertIn(cle, tuile, tuile)
            self.assertTrue(tuile['id'].startswith('ao_'), tuile['id'])

    def test_aucun_kpi_ne_double_un_autre_module(self):
        """Deux tuiles de même ``id`` = un doublon dans le hub fédéré."""
        ids = [t['id'] for t in kpis.kpi_ao(self.company)]
        self.assertEqual(len(ids), len(set(ids)))

    def test_les_tuiles_refletent_le_tableau(self):
        self._ao('AO-KPI', AppelOffre.Statut.ETUDE, jours=2)
        tuiles = {t['id']: t['valeur'] for t in kpis.kpi_ao(self.company)}
        tableau = selectors.tableau_marches(self.company)
        self.assertEqual(tuiles['ao_en_cours'], tableau['en_cours']['total'])
        self.assertEqual(tuiles['ao_cautions_immobilisees'],
                         tableau['cautions']['montant_immobilise'])


class LeProviderKPIEstReellementCable(SimpleTestCase):
    def test_le_manifeste_declare_le_provider(self):
        self.assertIn('apps.ao.kpis.kpi_ao', PLATFORM['kpi_providers'])

    def test_chaque_provider_declare_est_resoluble(self):
        """Règle d'honnêteté ARC41 : un dotted déclaré doit exister."""
        import importlib

        for dotted in PLATFORM['kpi_providers']:
            chemin, nom = dotted.rsplit('.', 1)
            self.assertTrue(callable(getattr(importlib.import_module(chemin),
                                             nom)), dotted)


class LEndpointEstGardeParAoVoir(_Base):
    def test_un_anonyme_est_refuse(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))

    def test_un_compte_sans_permission_ao_est_refuse(self):
        role = Role.objects.create(company=self.company, nom='Sans AO',
                                   permissions=[])
        user = User.objects.create_user(
            username='aof166-sansao', password='x', role_legacy='commercial',
            company=self.company, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(user))
        self.assertEqual(api.get(URL).status_code, 403)

    def test_un_compte_sans_societe_recoit_un_tableau_vide(self):
        user = User.objects.create_user(
            username='aof166-nocompany', password='x',
            role_legacy='responsable', company=None)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(user))
        reponse = api.get(URL)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['en_cours']['total'], 0)
