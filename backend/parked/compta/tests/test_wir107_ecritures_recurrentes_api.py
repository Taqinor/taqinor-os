"""Tests WIR107 — REST des sous-ensembles comptables avancés.

Le cockpit de clôture (NTFIN26-34) était déjà exposé mais sans écran ; les
modèles d'écriture / écritures récurrentes (XACC8) n'avaient AUCUNE route.
Ce module couvre la nouvelle surface REST qui rend les deux écrans possibles :

* ``/compta/modeles-ecriture/`` + ``/lignes-modele-ecriture/`` +
  ``/abonnements-ecriture/`` : CRUD company-scopé, ``company`` posée côté
  serveur (jamais lue du corps), isolation multi-société ;
* ``modeles-ecriture/<id>/generer/`` : matérialise UNE écriture en BROUILLON,
  avec les montants saisis (clefs JSON en STRING correctement reclées) ;
* ``abonnements-ecriture/generer-dues/`` : rejoue le service planifié et reste
  IDEMPOTENT par période (rejouer ne crée pas de doublon) ;
* ``instances-cloture/`` expose ``periode_libelle`` (l'écran de clôture nomme
  l'instance autrement que par un ID brut).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    AbonnementEcriture, EcritureComptable, InstanceCloture,
    LigneModeleEcriture, ModeleEcriture, PeriodeComptable,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _BaseWir107(TestCase):
    def setUp(self):
        self.co = make_company('wir107', 'WIR107 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.resp = make_user(self.co, 'wir107-resp')
        self.api = auth(self.resp)

    def _journal(self):
        from apps.compta.models import Journal
        return Journal.objects.filter(company=self.co).first()

    def _modele(self, libelle='Loyer', montants=('1200', '1200')):
        modele = ModeleEcriture.objects.create(
            company=self.co, libelle=libelle, journal=self._journal())
        LigneModeleEcriture.objects.create(
            company=self.co, modele=modele,
            compte=services.get_compte(self.co, '6111'), sens='debit',
            montant_defaut=Decimal(montants[0]), ordre=1)
        LigneModeleEcriture.objects.create(
            company=self.co, modele=modele,
            compte=services.get_compte(self.co, '4411'), sens='credit',
            montant_defaut=Decimal(montants[1]), ordre=2)
        return modele


class ModeleEcritureApiTests(_BaseWir107):
    def test_create_pose_company_serveur(self):
        autre = make_company('wir107-b', 'Autre')
        resp = self.api.post('/api/django/compta/modeles-ecriture/', {
            'libelle': 'Dotation', 'journal': self._journal().id,
            'company': autre.id,  # ignoré : la société vient du serveur
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        modele = ModeleEcriture.objects.get(pk=resp.data['id'])
        self.assertEqual(modele.company_id, self.co.id)

    def test_liste_isolee_par_societe(self):
        self._modele()
        autre = make_company('wir107-c', 'Autre C')
        services.seed_plan_comptable(autre)
        services.seed_journaux(autre)
        etranger = make_user(autre, 'wir107-etranger')
        resp = auth(etranger).get('/api/django/compta/modeles-ecriture/')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)

    def test_lignes_serialisees_avec_le_modele(self):
        modele = self._modele()
        resp = self.api.get(f'/api/django/compta/modeles-ecriture/{modele.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data['lignes']), 2)
        self.assertEqual(resp.data['lignes'][0]['compte_numero'], '6111')

    def test_generer_cree_une_ecriture_en_brouillon(self):
        modele = self._modele()
        resp = self.api.post(
            f'/api/django/compta/modeles-ecriture/{modele.id}/generer/',
            {'date_ecriture': '2026-03-31'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ecriture = EcritureComptable.objects.get(pk=resp.data['ecriture_id'])
        self.assertEqual(ecriture.statut, EcritureComptable.Statut.BROUILLON)
        self.assertEqual(ecriture.company_id, self.co.id)
        self.assertEqual(ecriture.lignes.count(), 2)

    def test_generer_respecte_les_montants_saisis_clefs_json(self):
        """JSON n'a pas de clef entière : ``{"12": 900}`` doit être honoré.

        Sans le reclé en int, le montant saisi était silencieusement remplacé
        par le montant par défaut du modèle — l'écran aurait menti.
        """
        modele = self._modele()
        lignes = list(modele.lignes.order_by('ordre'))
        resp = self.api.post(
            f'/api/django/compta/modeles-ecriture/{modele.id}/generer/',
            {'date_ecriture': '2026-03-31',
             'montants': {str(lignes[0].id): '900', str(lignes[1].id): '900'}},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ecriture = EcritureComptable.objects.get(pk=resp.data['ecriture_id'])
        total_debit = sum(lig.debit for lig in ecriture.lignes.all())
        self.assertEqual(total_debit, Decimal('900.00'))

    def test_generer_montant_invalide_refuse(self):
        modele = self._modele()
        ligne = modele.lignes.order_by('ordre').first()
        resp = self.api.post(
            f'/api/django/compta/modeles-ecriture/{modele.id}/generer/',
            {'date_ecriture': '2026-03-31',
             'montants': {str(ligne.id): 'beaucoup'}}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_generer_refuse_role_normal(self):
        modele = self._modele()
        simple = make_user(self.co, 'wir107-normal', role='normal')
        resp = auth(simple).post(
            f'/api/django/compta/modeles-ecriture/{modele.id}/generer/',
            {'date_ecriture': '2026-03-31'}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_filtre_actif(self):
        self._modele('Actif')
        inactif = self._modele('Inactif')
        inactif.actif = False
        inactif.save(update_fields=['actif'])
        resp = self.api.get('/api/django/compta/modeles-ecriture/?actif=true')
        results = resp.data.get('results', resp.data)
        self.assertEqual([r['libelle'] for r in results], ['Actif'])


class LigneModeleEcritureApiTests(_BaseWir107):
    def test_filtre_par_modele(self):
        a = self._modele('A')
        self._modele('B')
        resp = self.api.get(
            f'/api/django/compta/lignes-modele-ecriture/?modele={a.id}')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r['modele'] == a.id for r in results))

    def test_refuse_modele_autre_societe(self):
        autre = make_company('wir107-d', 'Autre D')
        services.seed_plan_comptable(autre)
        services.seed_journaux(autre)
        from apps.compta.models import Journal
        modele_etranger = ModeleEcriture.objects.create(
            company=autre, libelle='Étranger',
            journal=Journal.objects.filter(company=autre).first())
        resp = self.api.post('/api/django/compta/lignes-modele-ecriture/', {
            'modele': modele_etranger.id,
            'compte': services.get_compte(self.co, '6111').id,
            'sens': 'debit', 'montant_defaut': '10',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)


class AbonnementEcritureApiTests(_BaseWir107):
    def test_create_pose_company_serveur(self):
        modele = self._modele()
        resp = self.api.post('/api/django/compta/abonnements-ecriture/', {
            'modele': modele.id, 'libelle': 'Loyer mensuel',
            'frequence': 'mensuelle', 'prochaine_echeance': '2026-01-31',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ab = AbonnementEcriture.objects.get(pk=resp.data['id'])
        self.assertEqual(ab.company_id, self.co.id)
        self.assertEqual(resp.data['modele_libelle'], 'Loyer')

    def test_date_fin_avant_echeance_refusee(self):
        modele = self._modele()
        resp = self.api.post('/api/django/compta/abonnements-ecriture/', {
            'modele': modele.id, 'frequence': 'mensuelle',
            'prochaine_echeance': '2026-06-30', 'date_fin': '2026-01-31',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('date_fin', resp.data)

    def test_generer_dues_est_idempotent_par_periode(self):
        modele = self._modele()
        AbonnementEcriture.objects.create(
            company=self.co, modele=modele, libelle='Loyer',
            frequence=AbonnementEcriture.Frequence.MENSUELLE,
            prochaine_echeance=date(2026, 1, 31))
        url = '/api/django/compta/abonnements-ecriture/generer-dues/'
        premier = self.api.post(url, {'jusqua': '2026-01-31'}, format='json')
        self.assertEqual(premier.status_code, 200, premier.content)
        self.assertEqual(len(premier.data['generees']), 1)
        cree = EcritureComptable.objects.filter(
            company=self.co, source_type='abonnement').count()
        self.assertEqual(cree, 1)

        # Rejouer sur la MÊME période ne doit rien créer de plus : l'échéance
        # a avancé, donc plus rien n'est dû au 31/01.
        second = self.api.post(url, {'jusqua': '2026-01-31'}, format='json')
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(len(second.data['generees']), 0)
        self.assertEqual(EcritureComptable.objects.filter(
            company=self.co, source_type='abonnement').count(), 1)

    def test_generer_dues_refuse_role_normal(self):
        simple = make_user(self.co, 'wir107-normal-2', role='normal')
        resp = auth(simple).post(
            '/api/django/compta/abonnements-ecriture/generer-dues/',
            {}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_generer_dues_ignore_les_autres_societes(self):
        autre = make_company('wir107-e', 'Autre E')
        services.seed_plan_comptable(autre)
        services.seed_journaux(autre)
        from apps.compta.models import Journal
        modele_autre = ModeleEcriture.objects.create(
            company=autre, libelle='Étranger',
            journal=Journal.objects.filter(company=autre).first())
        LigneModeleEcriture.objects.create(
            company=autre, modele=modele_autre,
            compte=services.get_compte(autre, '6111'), sens='debit',
            montant_defaut=Decimal('50'), ordre=1)
        LigneModeleEcriture.objects.create(
            company=autre, modele=modele_autre,
            compte=services.get_compte(autre, '4411'), sens='credit',
            montant_defaut=Decimal('50'), ordre=2)
        AbonnementEcriture.objects.create(
            company=autre, modele=modele_autre,
            frequence=AbonnementEcriture.Frequence.MENSUELLE,
            prochaine_echeance=date(2026, 1, 31))

        resp = self.api.post(
            '/api/django/compta/abonnements-ecriture/generer-dues/',
            {'jusqua': '2026-01-31'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data['generees']), 0)
        self.assertEqual(EcritureComptable.objects.filter(
            company=autre, source_type='abonnement').count(), 0)


class InstanceClotureLibelleTests(_BaseWir107):
    def test_periode_libelle_expose(self):
        """WIR107 — l'écran de clôture affiche un libellé, pas un ID brut."""
        periode = PeriodeComptable.objects.create(
            company=self.co, type_periode=PeriodeComptable.Type.MOIS,
            libelle='Janvier 2026', date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31))
        modele = services.seed_modele_cloture_mensuel(self.co)
        instance = services.instancier_cloture(periode, modele)
        self.assertIsInstance(instance, InstanceCloture)

        resp = self.api.get(
            f'/api/django/compta/instances-cloture/?periode={periode.id}')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['periode_libelle'], 'Janvier 2026')
        self.assertTrue(results[0]['taches'])
