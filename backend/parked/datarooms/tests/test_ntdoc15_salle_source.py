"""NTDOC15 — Salle de données liée à un deal (Lead / Chantier / Contrat).

Couvre :
  * créer une salle depuis un Contrat la pré-nomme depuis le LIBELLÉ réel de
    l'objet (résolu par `contrats.selectors.contrat_card`) ;
  * le lien RETOUR est interrogeable (``?source_type=&source_id=``) — c'est ce
    qui permet à la fiche Contrat d'afficher ses salles ;
  * un objet d'une AUTRE société est introuvable (404), jamais un oracle ;
  * un type de source inconnu est refusé ;
  * aucun import cross-app de modèles : tout passe par les `selectors.py`.
"""
from django.test import TestCase

from apps.datarooms import selectors, services
from apps.datarooms.models import SalleDeDonnees

from ._base import auth, make_admin, make_company


class NtDoc15Base(TestCase):
    def setUp(self):
        self.co_a = make_company('ntdoc15-a', 'Ntdoc15 A')
        self.co_b = make_company('ntdoc15-b', 'Ntdoc15 B')
        self.admin_a = make_admin(self.co_a, 'ntdoc15-admin-a')
        self.api = auth(self.admin_a)
        self.contrat_a = self._contrat(self.co_a, 'CTR-2026-0001',
                                       'Maintenance annuelle')
        self.contrat_b = self._contrat(self.co_b, 'CTR-2026-0009',
                                       'Contrat voisin')

    def _contrat(self, company, reference, objet):
        from apps.contrats.models import Contrat
        return Contrat.objects.create(
            company=company, reference=reference, objet=objet)

    def _lead(self, company, nom):
        from apps.crm.models import Lead
        return Lead.objects.create(company=company, nom=nom)


class CarteSourceTests(NtDoc15Base):
    def test_carte_contrat_resolue_par_le_selecteur_cible(self):
        carte = services.carte_source(
            self.co_a, SalleDeDonnees.TypeSource.CONTRAT, self.contrat_a.pk)
        self.assertIsNotNone(carte)
        self.assertIn('CTR-2026-0001', carte['label'])
        self.assertIn('Maintenance annuelle', carte['label'])
        self.assertEqual(carte['url'], f'/contrats/{self.contrat_a.pk}')

    def test_carte_hors_societe_none(self):
        self.assertIsNone(services.carte_source(
            self.co_a, SalleDeDonnees.TypeSource.CONTRAT, self.contrat_b.pk))

    def test_type_inconnu_none(self):
        self.assertIsNone(services.carte_source(
            self.co_a, 'facture', self.contrat_a.pk))

    def test_carte_lead_resolue(self):
        lead = self._lead(self.co_a, 'Société Cliente')
        carte = services.carte_source(
            self.co_a, SalleDeDonnees.TypeSource.LEAD, lead.pk)
        self.assertIsNotNone(carte)
        self.assertIn('Société Cliente', carte['label'])


class CreationDepuisSourceTests(NtDoc15Base):
    def test_salle_pre_nommee_depuis_le_contrat(self):
        salle = services.creer_salle_depuis_source(
            company=self.co_a,
            source_type=SalleDeDonnees.TypeSource.CONTRAT,
            source_id=self.contrat_a.pk, created_by=self.admin_a)
        self.assertIn('CTR-2026-0001', salle.nom)
        self.assertEqual(salle.source_type, 'contrat')
        self.assertEqual(salle.source_id, self.contrat_a.pk)
        self.assertEqual(salle.company_id, self.co_a.pk)

    def test_nom_fourni_l_emporte(self):
        salle = services.creer_salle_depuis_source(
            company=self.co_a,
            source_type=SalleDeDonnees.TypeSource.CONTRAT,
            source_id=self.contrat_a.pk, nom='Data room juridique')
        self.assertEqual(salle.nom, 'Data room juridique')

    def test_source_hors_societe_refusee(self):
        with self.assertRaises(ValueError):
            services.creer_salle_depuis_source(
                company=self.co_a,
                source_type=SalleDeDonnees.TypeSource.CONTRAT,
                source_id=self.contrat_b.pk)


class ApiSourceTests(NtDoc15Base):
    def test_action_creer_depuis_source(self):
        reponse = self.api.post(
            '/api/django/datarooms/salles/creer-depuis-source/',
            {'source_type': 'contrat', 'source_id': self.contrat_a.pk},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertIn('CTR-2026-0001', reponse.data['nom'])
        self.assertIn('CTR-2026-0001', reponse.data['source_label'])
        self.assertEqual(reponse.data['source_url'],
                         f'/contrats/{self.contrat_a.pk}')

    def test_action_sur_objet_voisin_404(self):
        reponse = self.api.post(
            '/api/django/datarooms/salles/creer-depuis-source/',
            {'source_type': 'contrat', 'source_id': self.contrat_b.pk},
            format='json')
        self.assertEqual(reponse.status_code, 404, reponse.data)
        self.assertEqual(SalleDeDonnees.objects.count(), 0)

    def test_lien_retour_interrogeable(self):
        salle = services.creer_salle_depuis_source(
            company=self.co_a,
            source_type=SalleDeDonnees.TypeSource.CONTRAT,
            source_id=self.contrat_a.pk)
        services.creer_salle(company=self.co_a, nom='Salle sans source')
        reponse = self.api.get(
            f'/api/django/datarooms/salles/?source_type=contrat'
            f'&source_id={self.contrat_a.pk}')
        self.assertEqual(reponse.status_code, 200)
        resultats = reponse.data.get('results', reponse.data)
        self.assertEqual([r['id'] for r in resultats], [salle.pk])

    def test_selecteur_lien_retour(self):
        salle = services.creer_salle_depuis_source(
            company=self.co_a,
            source_type=SalleDeDonnees.TypeSource.CONTRAT,
            source_id=self.contrat_a.pk)
        trouvees = selectors.salles_pour_source(
            self.co_a, 'contrat', self.contrat_a.pk)
        self.assertEqual(list(trouvees), [salle])
        self.assertEqual(
            selectors.salles_pour_source(self.co_a, 'contrat', 0).count(), 0)
