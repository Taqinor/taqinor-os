"""AOF62 — actions de variante IDEMPOTENTES : retenir / comparer /
sensibilites / marches.

Ce que ces tests VERROUILLENT :

* un double-clic ou un rejeu réseau (même ``Idempotency-Key``) ne lance PAS un
  second calcul et ne bascule PAS deux fois la retenue ;
* la MÊME clé rejouée sur une AUTRE variante rend **409** — sans quoi la
  réponse mémorisée du premier appel ferait croire qu'on a retenu la seconde ;
* une variante ``PERIME`` ne peut pas devenir retenue (**409**) : son entrée a
  bougé depuis le calcul ;
* ``comparer`` compare N variantes EN UN APPEL ;
* la matrice de permissions tient (sans ``ao_gerer`` : 403 ; autre société :
  404).

Run :
    python manage.py test apps.ao.tests.test_actions_variante -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.models import (
    AppelOffre, BatimentAO, KitCalepinage, ToitureAO, VarianteCalepinage,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company
from core.idempotency import IdempotencyRecord

User = get_user_model()

RETENIR = '/api/django/ao/calepinage/variantes/%s/retenir/'
COMPARER = '/api/django/ao/calepinage/variantes/comparer/'
SENSIBILITES = '/api/django/ao/calepinage/variantes/%s/sensibilites/'
MARCHES = '/api/django/ao/calepinage/variantes/%s/marches/'

PARAMS = {
    'rive_laterale_m': 0.35,
    'rive_extremite_m': 0.35,
    'allee_min_m': 0.60,
    'degagements_par_provenance_m': {'MESURE': 0.30, 'DEVINE': 0.50},
    'kits_autorises': ['AO-TABLE-PORTRAIT'],
    'pas_recherche_m': 0.01,
}

PREUVE = {
    'total_retenu': 120, 'total_optimal': 120, 'methode': 'dp_exact_1cm',
    'optimal': True, 'pas_cm': 1, 'nb_optima': 3,
    'marge_troncon_min': 0.05, 'marge_bande_min': 0.12, 'controles': [],
}


class BaseActions(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='AOF62 Co', slug='aof62-co')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof62_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-62-1', objet='Actions')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='05H',
            contour_local_m=[[0, 0], [24, 0], [24, 14], [0, 14]],
            parametres_calepinage=dict(PARAMS))
        self.kit = KitCalepinage.objects.create(
            company=self.company, code='AO-TABLE-PORTRAIT',
            libelle='Table dos-à-dos portrait', modules_par_kit=2,
            pas_rangee_m=Decimal('1.134'), longueur_pente_m=Decimal('2.382'),
            faitage_m=Decimal('0.098'), puissance_module_w=625,
            inclinaison_deg=Decimal('15.00'))
        self.kit.appliquer_emprise()
        self.kit.save()

    def _variante(self, **kwargs):
        base = {
            'nom': 'Variante', 'params': dict(PARAMS), 'preuve': dict(PREUVE),
            'resultat': {'total_modules': 120, 'kwc': 75.0},
            'statut': VarianteCalepinage.Statut.CALCULEE,
        }
        base.update(kwargs)
        return VarianteCalepinage.objects.create(
            company=self.company, toiture=self.toiture, appel_offre=self.ao,
            **base)


class LaRetenueEstIdempotente(BaseActions):
    def test_double_clic_avec_la_meme_cle_ne_bascule_qu_une_fois(self):
        variante = self._variante()
        une = self.api.post(RETENIR % variante.pk, {}, format='json',
                            HTTP_IDEMPOTENCY_KEY='clic-1')
        deux = self.api.post(RETENIR % variante.pk, {}, format='json',
                             HTTP_IDEMPOTENCY_KEY='clic-1')
        self.assertEqual(une.status_code, 200, une.data)
        self.assertEqual(deux.status_code, 200, deux.data)
        self.assertEqual(deux.data['id'], une.data['id'])
        self.assertEqual(IdempotencyRecord.objects.count(), 1)
        variante.refresh_from_db()
        self.assertTrue(variante.est_retenue)
        self.assertEqual(
            VarianteCalepinage.objects.filter(est_retenue=True).count(), 1)

    def test_sans_cle_le_rejeu_reste_sans_effet(self):
        """Même sans en-tête, retenir deux fois ne casse pas l'unicité."""
        variante = self._variante()
        self.api.post(RETENIR % variante.pk, {}, format='json')
        deuxieme = self.api.post(RETENIR % variante.pk, {}, format='json')
        self.assertEqual(deuxieme.status_code, 200, deuxieme.data)
        self.assertEqual(
            VarianteCalepinage.objects.filter(est_retenue=True).count(), 1)

    def test_la_meme_cle_sur_une_autre_variante_rend_409(self):
        une = self._variante(nom='A')
        deux = self._variante(nom='B')
        self.api.post(RETENIR % une.pk, {}, format='json',
                      HTTP_IDEMPOTENCY_KEY='partagee')
        reponse = self.api.post(RETENIR % deux.pk, {}, format='json',
                                HTTP_IDEMPOTENCY_KEY='partagee')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        deux.refresh_from_db()
        self.assertFalse(deux.est_retenue)

    def test_une_variante_perimee_ne_peut_pas_etre_retenue(self):
        variante = self._variante(statut=VarianteCalepinage.Statut.PERIME)
        reponse = self.api.post(RETENIR % variante.pk, {}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('PÉRIMÉE', ' '.join(reponse.data['statut']))
        variante.refresh_from_db()
        self.assertFalse(variante.est_retenue)

    def test_retenir_bascule_l_ancienne_retenue(self):
        ancienne = self._variante(nom='Ancienne', est_retenue=True)
        nouvelle = self._variante(nom='Nouvelle')
        reponse = self.api.post(RETENIR % nouvelle.pk, {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        ancienne.refresh_from_db()
        nouvelle.refresh_from_db()
        self.assertFalse(ancienne.est_retenue)
        self.assertTrue(nouvelle.est_retenue)


class LaComparaison(BaseActions):
    def test_n_variantes_en_un_appel(self):
        une = self._variante(nom='A', resultat={'total_modules': 120,
                                                'kwc': 75.0})
        deux = self._variante(nom='B', resultat={'total_modules': 108,
                                                 'kwc': 67.5})
        trois = self._variante(nom='C', resultat={'total_modules': 96,
                                                  'kwc': 60.0})
        reponse = self.api.get(
            COMPARER, {'ids': '%s,%s,%s' % (une.pk, deux.pk, trois.pk)})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        lignes = reponse.data['lignes']
        self.assertEqual(len(lignes), 3)
        self.assertEqual([ligne['total_modules'] for ligne in lignes],
                         [120, 108, 96])
        self.assertEqual([ligne['delta_modules'] for ligne in lignes],
                         [0, -12, -24])
        self.assertEqual(reponse.data['reference_modules'], 120)

    def test_une_variante_d_une_autre_societe_est_introuvable(self):
        autre = Company.objects.create(nom='Autre 62', slug='autre-62')
        ao = AppelOffre.objects.create(company=autre, reference='AO-Z',
                                       objet='Ailleurs')
        batiment = BatimentAO.objects.create(company=autre, appel_offre=ao,
                                             code='Z')
        toiture = ToitureAO.objects.create(company=autre, batiment=batiment)
        etrangere = VarianteCalepinage.objects.create(
            company=autre, toiture=toiture, appel_offre=ao, nom='Étrangère')
        mienne = self._variante(nom='Mienne')
        reponse = self.api.get(
            COMPARER, {'ids': '%s,%s' % (mienne.pk, etrangere.pk)})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(len(reponse.data['lignes']), 1)
        self.assertEqual(reponse.data['introuvables'], [etrangere.pk])

    def test_identifiants_invalides_400_nomme(self):
        reponse = self.api.get(COMPARER, {'ids': 'abc'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('ids', reponse.data)

    def test_sans_identifiant_400_nomme(self):
        reponse = self.api.get(COMPARER, {'ids': ''})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('ids', reponse.data)


class LesSensibilites(BaseActions):
    def test_la_batterie_persiste_des_variantes_filles(self):
        variante = self._variante()
        reponse = self.api.post(SENSIBILITES % variante.pk, {},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertGreater(len(reponse.data['sensibilites']), 0)
        self.assertIn('plancher_modules', reponse.data)
        self.assertTrue(reponse.data['verdict'])
        filles = VarianteCalepinage.objects.filter(
            parent=variante, role=VarianteCalepinage.Role.SENSIBILITE)
        self.assertEqual(filles.count(), len(reponse.data['sensibilites']))

    def test_rejouer_ne_duplique_aucune_sensibilite(self):
        variante = self._variante()
        une = self.api.post(SENSIBILITES % variante.pk, {}, format='json')
        avant = VarianteCalepinage.objects.filter(
            parent=variante, role=VarianteCalepinage.Role.SENSIBILITE).count()
        deux = self.api.post(SENSIBILITES % variante.pk, {}, format='json')
        apres = VarianteCalepinage.objects.filter(
            parent=variante, role=VarianteCalepinage.Role.SENSIBILITE).count()
        self.assertEqual(une.status_code, 200)
        self.assertEqual(deux.status_code, 200)
        self.assertEqual(avant, apres)

    def test_la_meme_cle_rejoue_la_reponse_sans_recalculer(self):
        variante = self._variante()
        une = self.api.post(SENSIBILITES % variante.pk, {}, format='json',
                            HTTP_IDEMPOTENCY_KEY='batterie-1')
        deux = self.api.post(SENSIBILITES % variante.pk, {}, format='json',
                             HTTP_IDEMPOTENCY_KEY='batterie-1')
        self.assertEqual(une.status_code, 200, une.data)
        self.assertEqual(deux.status_code, 200, deux.data)
        self.assertEqual(deux.data['reference_modules'],
                         une.data['reference_modules'])
        self.assertEqual(IdempotencyRecord.objects.count(), 1)


class LesMarches(BaseActions):
    def _marche(self, parent, code, modules, attendu=None):
        return VarianteCalepinage.objects.create(
            company=self.company, toiture=self.toiture, appel_offre=self.ao,
            parent=parent, role=VarianteCalepinage.Role.MARCHE, nom=code,
            justification='marche %s' % code,
            resultat={'total_modules': modules, 'attendu': attendu})

    def test_l_echelle_publie_des_deltas_signes(self):
        variante = self._variante()
        self._marche(variante, 'F', 100, 100)
        self._marche(variante, 'G', 120, 120)
        reponse = self.api.get(MARCHES % variante.pk)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['depart'], 100)
        self.assertEqual(reponse.data['arrivee'], 120)
        self.assertEqual(reponse.data['gain_total'], 20)
        self.assertEqual([m['delta'] for m in reponse.data['marches']],
                         [0, 20])
        self.assertTrue(reponse.data['honnete'])
        self.assertIn('marches', reponse.data['recit'])

    def test_une_marche_qui_ne_redonne_pas_son_attendu_est_signalee(self):
        variante = self._variante()
        self._marche(variante, 'F', 100, 100)
        self._marche(variante, 'G', 120, 130)
        reponse = self.api.get(MARCHES % variante.pk)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(reponse.data['honnete'])
        self.assertTrue(reponse.data['motifs'])
        self.assertIn('attendu 130', reponse.data['motifs'][0])


class LaMatriceDePermissions(BaseActions):
    def _client(self, permissions, nom):
        role = Role.objects.create(company=self.company, nom=nom,
                                   permissions=list(permissions))
        user = User.objects.create_user(
            username='u_%s' % nom.lower(), password='x',
            company=self.company, role=role)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return client

    def test_lecture_seule_ne_peut_pas_retenir(self):
        variante = self._variante()
        client = self._client(['ao_voir'], 'Lecteur')
        marches = client.get(MARCHES % variante.pk)
        retenir = client.post(RETENIR % variante.pk, {}, format='json')
        self.assertEqual(marches.status_code, 200, marches.data)
        self.assertEqual(retenir.status_code, 403, retenir.data)

    def test_sans_permission_ao_tout_est_refuse(self):
        variante = self._variante()
        client = self._client(['stock_voir'], 'Etranger')
        self.assertEqual(client.get(MARCHES % variante.pk).status_code, 403)
        self.assertEqual(
            client.post(RETENIR % variante.pk, {}, format='json').status_code,
            403)

    def test_une_variante_d_une_autre_societe_rend_404(self):
        autre = Company.objects.create(nom='Autre 62b', slug='autre-62b')
        ao = AppelOffre.objects.create(company=autre, reference='AO-Y',
                                       objet='Ailleurs')
        batiment = BatimentAO.objects.create(company=autre, appel_offre=ao,
                                             code='Y')
        toiture = ToitureAO.objects.create(company=autre, batiment=batiment)
        etrangere = VarianteCalepinage.objects.create(
            company=autre, toiture=toiture, appel_offre=ao, nom='Étrangère')
        reponse = self.api.post(RETENIR % etrangere.pk, {}, format='json')
        self.assertEqual(reponse.status_code, 404)
