"""CAL32 — l'action ``layout`` d'une affaire écrit dans le MODULE Calepinage.

Ce que ce module VERROUILLE :

  1. **Un POST layout crée/alimente le calepinage de l'affaire ET son
     historique** (``apps.calepinage.services.enregistrer_layout``), et
     l'affaire pointe l'identifiant obtenu.
  2. **Le geste est IDEMPOTENT** : un second POST ne crée pas un second
     calepinage ; un renvoi à l'identique n'ajoute pas de version fantôme.
  3. **Une affaire déposée/close rend EXACTEMENT le 409 d'avant** — non
     régression mot pour mot (``selectors.raison_conception_figee``).
  4. **``calepinage_id`` est SERVI par l'API d'affaire, jamais ACCEPTÉ** : un
     PATCH qui le fournirait ne le change pas (l'identifiant est opaque —
     l'accepter laisserait pointer le document d'une autre société).
  5. **Une affaire sans lead ne casse rien** : la base refuse un calepinage
     sans lead ni client (CAL7), donc l'affaire écrit son ``roof_layout``
     seul, exactement comme avant CAL32.

Le modèle du module est lu par le REGISTRE (``apps.get_model``), jamais
importé : le même interdit que le code de production respecte.

Run :
    python manage.py test apps.ao.tests.test_layout_delegue -v2
"""
from django.apps import apps as registre
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import selectors
from apps.ao.models import AppelOffre
from apps.crm.models import Lead
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

LAYOUT = {'version': 2, 'outline': [[33.57, -7.58], [33.58, -7.58],
                                    [33.58, -7.57]],
          'zones': [{'id': 'z1', 'vertices': [[0, 0], [10, 0], [10, 6]]}]}
AUTRE_LAYOUT = {'version': 2, 'outline': [[34.01, -6.84], [34.02, -6.84],
                                          [34.02, -6.83]], 'zones': []}


def _calepinages():
    return registre.get_model('calepinage', 'Calepinage').objects


def _versions():
    return registre.get_model('calepinage', 'CalepinageVersion').objects


class BaseCal32(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CAL32 Co', slug='cal32-co')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='cal32_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(company=self.company,
                                        nom='Client CAL32')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-CAL32-1', objet='Délégation',
            lead_id=self.lead.pk)

    @property
    def url(self):
        return f'/api/django/ao/appels-offres/{self.ao.pk}/layout/'


class LePostAlimenteLeModule(BaseCal32):
    def test_il_cree_le_calepinage_de_l_affaire_et_le_pointe(self):
        reponse = self.api.post(self.url, LAYOUT, format='json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.ao.refresh_from_db()
        self.assertIsNotNone(self.ao.calepinage_id)
        calepinage = _calepinages().get(pk=self.ao.calepinage_id)
        self.assertEqual(calepinage.company_id, self.company.pk)
        self.assertEqual(calepinage.appel_offre_id, self.ao.pk)
        self.assertEqual(calepinage.roof_layout, LAYOUT)
        self.assertEqual(reponse.data['calepinage_id'], calepinage.pk)

    def test_l_historique_est_ecrit(self):
        self.api.post(self.url, LAYOUT, format='json')

        self.ao.refresh_from_db()
        self.assertEqual(
            _versions().filter(calepinage_id=self.ao.calepinage_id).count(), 1)

    def test_une_conception_modifiee_ajoute_une_version(self):
        self.api.post(self.url, LAYOUT, format='json')
        self.api.post(self.url, AUTRE_LAYOUT, format='json')

        self.ao.refresh_from_db()
        self.assertEqual(_calepinages().count(), 1)
        self.assertEqual(
            _versions().filter(calepinage_id=self.ao.calepinage_id).count(), 2)

    def test_un_renvoi_a_l_identique_ne_cree_pas_de_version_fantome(self):
        """Double-clic, renvoi réseau : l'historique ne se pollue pas."""
        self.api.post(self.url, LAYOUT, format='json')
        self.api.post(self.url, LAYOUT, format='json')

        self.ao.refresh_from_db()
        self.assertEqual(_calepinages().count(), 1)
        self.assertEqual(
            _versions().filter(calepinage_id=self.ao.calepinage_id).count(), 1)

    def test_l_enveloppe_layout_est_toujours_acceptee(self):
        """Parité avec le devis : ``{"layout": …}`` reste accepté."""
        reponse = self.api.post(self.url, {'layout': LAYOUT}, format='json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.ao.refresh_from_db()
        self.assertEqual(
            _calepinages().get(pk=self.ao.calepinage_id).roof_layout, LAYOUT)

    def test_le_roof_layout_de_l_affaire_reste_ecrit_en_miroir(self):
        """CAL30 l'a CONSERVÉ : le GET et le contexte le lisent encore."""
        self.api.post(self.url, LAYOUT, format='json')

        self.ao.refresh_from_db()
        self.assertEqual(self.ao.roof_layout, LAYOUT)
        lecture = self.api.get(self.url)
        self.assertEqual(lecture.data['roof_layout'], LAYOUT)
        self.assertEqual(lecture.data['calepinage_id'], self.ao.calepinage_id)

    def test_un_calepinage_deja_rattache_est_reutilise(self):
        deja = _calepinages().create(
            company=self.company, lead_id=self.lead.pk,
            appel_offre_id=self.ao.pk, titre='Posé avant')

        reponse = self.api.post(self.url, LAYOUT, format='json')

        self.assertEqual(reponse.data['calepinage_id'], deja.pk)
        self.assertEqual(_calepinages().count(), 1)


class LeRefus409EstInchange(BaseCal32):
    def test_le_motif_est_celui_du_selecteur_mot_pour_mot(self):
        # AOF13 — le statut d'un AO ne s'écrit pas par `save()` (le garde
        # de `AppelOffre.save` l'exige) : on FIGE la ligne par
        # `queryset.update()`, l'échappatoire documentée du garde, comme
        # le fait déjà `test_aud605_resultat_et_creer_devis._forcer_statut`.
        AppelOffre.objects.filter(pk=self.ao.pk).update(
            statut=AppelOffre.Statut.DEPOSE)
        self.ao.refresh_from_db()
        attendu = selectors.raison_conception_figee(self.ao)

        reponse = self.api.post(self.url, LAYOUT, format='json')

        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['detail'], attendu)

    def test_rien_n_est_ecrit_ni_cote_affaire_ni_cote_module(self):
        # AOF13 — le statut d'un AO ne s'écrit pas par `save()` (le garde
        # de `AppelOffre.save` l'exige) : on FIGE la ligne par
        # `queryset.update()`, l'échappatoire documentée du garde, comme
        # le fait déjà `test_aud605_resultat_et_creer_devis._forcer_statut`.
        AppelOffre.objects.filter(pk=self.ao.pk).update(
            statut=AppelOffre.Statut.DEPOSE)
        self.ao.refresh_from_db()

        self.api.post(self.url, LAYOUT, format='json')

        self.ao.refresh_from_db()
        self.assertIsNone(self.ao.roof_layout)
        self.assertIsNone(self.ao.calepinage_id)
        self.assertEqual(_calepinages().count(), 0)

    def test_le_get_reste_ouvert_sur_une_affaire_figee(self):
        """Lecture seule = LECTURE autorisée : seule l'écriture est fermée."""
        # AOF13 — le statut d'un AO ne s'écrit pas par `save()` (le garde
        # de `AppelOffre.save` l'exige) : on FIGE la ligne par
        # `queryset.update()`, l'échappatoire documentée du garde, comme
        # le fait déjà `test_aud605_resultat_et_creer_devis._forcer_statut`.
        AppelOffre.objects.filter(pk=self.ao.pk).update(
            statut=AppelOffre.Statut.DEPOSE)
        self.ao.refresh_from_db()

        self.assertEqual(self.api.get(self.url).status_code, 200)

    def test_un_layout_vide_reste_un_400(self):
        reponse = self.api.post(self.url, {}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertEqual(_calepinages().count(), 0)


class CalepinageIdEstServiJamaisAccepte(BaseCal32):
    URL_DETAIL = '/api/django/ao/appels-offres/'

    def test_le_serialiseur_le_sert(self):
        self.api.post(self.url, LAYOUT, format='json')
        self.ao.refresh_from_db()

        detail = self.api.get(f'{self.URL_DETAIL}{self.ao.pk}/')

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['calepinage_id'], self.ao.calepinage_id)

    def test_il_vaut_null_tant_qu_aucune_conception_n_existe(self):
        detail = self.api.get(f'{self.URL_DETAIL}{self.ao.pk}/')
        self.assertIsNone(detail.data['calepinage_id'])

    def test_un_patch_ne_peut_pas_le_poser(self):
        reponse = self.api.patch(f'{self.URL_DETAIL}{self.ao.pk}/',
                                 {'calepinage_id': 4242}, format='json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.ao.refresh_from_db()
        self.assertIsNone(self.ao.calepinage_id)


class UneAffaireSansLeadNeCassePas(BaseCal32):
    def test_elle_ecrit_son_roof_layout_seul(self):
        sans_lead = AppelOffre.objects.create(
            company=self.company, reference='AO-CAL32-2', objet='Sans lead')
        url = f'/api/django/ao/appels-offres/{sans_lead.pk}/layout/'

        reponse = self.api.post(url, LAYOUT, format='json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        sans_lead.refresh_from_db()
        self.assertEqual(sans_lead.roof_layout, LAYOUT)
        self.assertIsNone(sans_lead.calepinage_id)
        self.assertIsNone(reponse.data['calepinage_id'])
        self.assertEqual(_calepinages().count(), 0)

    def test_un_lead_orphelin_est_traite_comme_une_absence_de_lead(self):
        orpheline = AppelOffre.objects.create(
            company=self.company, reference='AO-CAL32-3', objet='Lead mort',
            lead_id=999999)
        url = f'/api/django/ao/appels-offres/{orpheline.pk}/layout/'

        reponse = self.api.post(url, LAYOUT, format='json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        orpheline.refresh_from_db()
        self.assertEqual(orpheline.roof_layout, LAYOUT)
        self.assertIsNone(orpheline.calepinage_id)


class LeMultiTenantTient(BaseCal32):
    def test_une_affaire_d_une_autre_societe_est_un_404(self):
        autre = Company.objects.create(nom='CAL32 Bis', slug='cal32-bis')
        etrangere = AppelOffre.objects.create(
            company=autre, reference='AO-X', objet='Ailleurs')

        reponse = self.api.post(
            f'/api/django/ao/appels-offres/{etrangere.pk}/layout/',
            LAYOUT, format='json')

        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(_calepinages().count(), 0)

    def test_le_calepinage_cree_porte_la_societe_de_l_appelant(self):
        self.api.post(self.url, LAYOUT, format='json')

        self.assertEqual(_calepinages().get().company_id, self.company.pk)
