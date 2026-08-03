"""AOF173 — la BIBLIOTHÈQUE de l'écran AO répond vraiment.

Constat de production (03/08/2026) : l'écran Bibliothèque appelait
``/api/django/ao/bibliotheque/`` — une route qui n'a JAMAIS été enregistrée.
Les quatre catégories de l'écran sont en réalité quatre ressources : kits
(``kits-calepinage``) et jeux de paramètres (``presets-calepinage``) existaient
déjà ; les gabarits de pack et les textes normalisés étaient sans route.

Ce module vérifie la réalité SERVEUR, pas une forme supposée par le front :
les deux nouvelles ressources répondent, sont scopées par société, et
``dossiers-impactes`` applique la MÊME règle d'inclusion que le rendu du
mémoire (aucune estimation).

Run :
    python manage.py test apps.ao.tests.test_bibliotheque_ao -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.models import AppelOffre, ModelePack, SectionMemoire
from apps.ao.permissions import AO_GERER, AO_VOIR
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/ao/'


class BaseBibliotheque(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF173 Co',
                                              slug='aof173-co')
        role = Role.objects.create(company=self.company, nom='Chargé AO',
                                   permissions=[AO_VOIR, AO_GERER])
        self.user = User.objects.create_user(
            username='aof173', password='x', company=self.company, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')


class TestRessourcesDeBibliotheque(BaseBibliotheque):
    def test_les_gabarits_de_pack_sont_listables(self):
        ModelePack.objects.create(
            company=self.company, code='PACK-AO', libelle='Pack solaire AO',
            description='Neuf pièces, 00 → 08.')
        reponse = self.api.get(f'{BASE}modeles-pack/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['count'], 1)
        ligne = reponse.data['results'][0]
        # La FORME réelle : ``code``/``libelle``/``description`` — jamais un
        # ``nom`` que le serveur n'a jamais produit.
        self.assertEqual(ligne['code'], 'PACK-AO')
        self.assertEqual(ligne['libelle'], 'Pack solaire AO')
        self.assertIn('actif', ligne)

    def test_les_textes_normalises_sont_listables_et_modifiables(self):
        section = SectionMemoire.objects.create(
            company=self.company, code='RESERVE', titre='Clause de réserve',
            corps='Texte initial.')
        reponse = self.api.get(f'{BASE}sections-memoire/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        ligne = reponse.data['results'][0]
        self.assertEqual(ligne['titre'], 'Clause de réserve')
        self.assertEqual(ligne['corps'], 'Texte initial.')

        # AOF173 — modifier un texte PARTAGÉ est un PATCH sur le MÊME id :
        # aucune duplication silencieuse.
        patch = self.api.patch(f'{BASE}sections-memoire/{section.pk}/',
                               {'corps': 'Texte révisé.'}, format='json')
        self.assertEqual(patch.status_code, 200, patch.data)
        section.refresh_from_db()
        self.assertEqual(section.corps, 'Texte révisé.')
        self.assertEqual(
            SectionMemoire.objects.filter(company=self.company).count(), 1)

    def test_le_filtre_actif_est_celui_du_serveur(self):
        SectionMemoire.objects.create(
            company=self.company, code='A', titre='Active', actif=True)
        SectionMemoire.objects.create(
            company=self.company, code='I', titre='Retirée', actif=False)
        reponse = self.api.get(f'{BASE}sections-memoire/', {'actif': 'true'})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual([r['code'] for r in reponse.data['results']], ['A'])

    def test_une_autre_societe_ne_voit_rien(self):
        autre = Company.objects.create(nom='AOF173 X', slug='aof173-x')
        SectionMemoire.objects.create(
            company=autre, code='X', titre='Texte de l’autre société')
        ModelePack.objects.create(company=autre, code='X', libelle='Pack X')
        self.assertEqual(
            self.api.get(f'{BASE}sections-memoire/').data['count'], 0)
        self.assertEqual(
            self.api.get(f'{BASE}modeles-pack/').data['count'], 0)


class TestDossiersImpactes(BaseBibliotheque):
    """La liste affichée AVANT toute modification doit être VRAIE."""

    def setUp(self):
        super().setUp()
        self.ao_a = AppelOffre.objects.create(
            company=self.company, reference='AO-173-A', objet='Toiture A')
        self.ao_b = AppelOffre.objects.create(
            company=self.company, reference='AO-173-B', objet='Toiture B')

    def _impactes(self, section):
        reponse = self.api.get(
            f'{BASE}sections-memoire/{section.pk}/dossiers-impactes/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_une_section_sans_condition_est_reprise_par_tous_les_dossiers(self):
        section = SectionMemoire.objects.create(
            company=self.company, code='INTRO', titre='Présentation')
        references = {d['reference'] for d in self._impactes(section)}
        self.assertEqual(references, {'AO-173-A', 'AO-173-B'})

    def test_une_section_inactive_n_impacte_aucun_dossier(self):
        section = SectionMemoire.objects.create(
            company=self.company, code='OLD', titre='Retirée', actif=False)
        self.assertEqual(self._impactes(section), [])

    def test_une_condition_non_satisfaite_exclut_le_dossier(self):
        """La règle est celle du RENDU, pas une approximation d'écran."""
        section = SectionMemoire.objects.create(
            company=self.company, code='BATT', titre='Stockage',
            conditions_inclusion={'equipements.batterie.designation':
                                  'Batterie X'})
        self.assertEqual(self._impactes(section), [])

    def test_les_dossiers_d_une_autre_societe_ne_sont_jamais_comptes(self):
        autre = Company.objects.create(nom='AOF173 Y', slug='aof173-y')
        AppelOffre.objects.create(
            company=autre, reference='AO-173-Y', objet='Ailleurs')
        section = SectionMemoire.objects.create(
            company=self.company, code='INTRO', titre='Présentation')
        references = {d['reference'] for d in self._impactes(section)}
        self.assertNotIn('AO-173-Y', references)
