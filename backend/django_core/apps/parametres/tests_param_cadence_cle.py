"""PARAM-CADENCE — la chaîne après l'appel et la visite passent dans Paramètres.

Décision fondateur du 25/09/2026 : « cette cadence doit être dans Paramètres,
pour qu'une autre société ou nous puissions tout y changer ». Ce que ce
fichier verrouille, côté GABARIT :

* deux cadences de plus, ``apres_contact`` (6 barreaux) et ``visite``
  (4 barreaux), seedées EXACTEMENT comme le contrat
  ``contract_samples/cadence_relance_v2.json`` (``exemple_apres_contact``,
  ``exemple_visite``) — idempotent, jamais une réécriture ;
* chaque barreau porte une CLÉ stable, unique par (société, cadence) quand
  elle est posée, en LECTURE SEULE dans l'API ;
* ``barreau_par_cle`` : le barreau actif (ou inactif sur demande), seedé à la
  volée sur une cadence vide, ``None`` s'il a été supprimé ;
* un barreau à clé ne change pas de cadence (400 nommé) ; sa suppression est
  permise (le moteur retombe sur le défaut).

Côté moteur (lecture par clé, repli, multi-société, jamais un plan qu'on
démarre) : ``apps/crm/tests_param_cadence_moteur.py``.
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.parametres.models_relance import (
    CADENCE_APRES_CONTACT_DEFAUT, CADENCE_VISITE_DEFAUT, CADENCES_DEFAUT,
    CADENCES_MOTEUR, Cadence, CadenceRelanceEtape, barreau_par_defaut,
)

User = get_user_model()

CADENCE_URL = '/api/django/parametres/cadence-relance/'
CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'cadence_relance_v2.json').read_text(encoding='utf-8'))
CHAMPS_GABARIT = ('cadence', 'ordre', 'delai_jours', 'delai_minutes',
                  'heure_cible', 'canal', 'libelle', 'template_cle', 'actif',
                  'dimanche_ok', 'samedi_ok', 'cle')


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def _forme(barreau):
    """Le barreau comme le contrat le montre (sans l'id)."""
    return {
        'cadence': barreau.cadence, 'ordre': barreau.ordre,
        'delai_jours': barreau.delai_jours,
        'delai_minutes': barreau.delai_minutes,
        'heure_cible': barreau.heure_cible, 'canal': barreau.canal,
        'libelle': barreau.libelle, 'template_cle': barreau.template_cle,
        'actif': barreau.actif, 'dimanche_ok': barreau.dimanche_ok,
        'samedi_ok': barreau.samedi_ok, 'cle': barreau.cle,
    }


def _attendu(exemple):
    return [{champ: ligne[champ] for champ in CHAMPS_GABARIT}
            for ligne in CONTRAT[exemple]]


class SeedConformeAuContratTests(TestCase):

    def setUp(self):
        self.company = _company('pcad-seed')

    def _barreaux(self, cadence):
        return list(CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=cadence).order_by('ordre'))

    def test_apres_contact_est_exactement_l_exemple_du_contrat(self):
        crees = CadenceRelanceEtape.seed_cadence(
            self.company, Cadence.APRES_CONTACT)
        self.assertEqual(crees, 6)
        self.assertEqual([_forme(b) for b in self._barreaux(
            Cadence.APRES_CONTACT)], _attendu('exemple_apres_contact'))

    def test_visite_est_exactement_l_exemple_du_contrat(self):
        crees = CadenceRelanceEtape.seed_cadence(self.company, Cadence.VISITE)
        self.assertEqual(crees, 4)
        self.assertEqual([_forme(b) for b in self._barreaux(
            Cadence.VISITE)], _attendu('exemple_visite'))

    def test_le_seed_est_idempotent_et_ne_reecrit_rien(self):
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.APRES_CONTACT)
        devis = CadenceRelanceEtape.objects.get(
            company=self.company, cadence=Cadence.APRES_CONTACT, cle='devis')
        devis.libelle = 'Faire le devis'
        devis.delai_jours = 2
        devis.save()

        self.assertEqual(CadenceRelanceEtape.seed_cadence(
            self.company, Cadence.APRES_CONTACT), 0)
        devis.refresh_from_db()
        self.assertEqual((devis.libelle, devis.delai_jours),
                         ('Faire le devis', 2))
        self.assertEqual(len(self._barreaux(Cadence.APRES_CONTACT)), 6)

    def test_un_barreau_deplace_n_est_jamais_reseede(self):
        """La société a déplacé « devis » au rang 9 et supprimé le rang 1 :
        le seed ne recrée pas un second « devis » (la contrainte d'unicité
        l'interdirait) — ni ne plante."""
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.APRES_CONTACT)
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.APRES_CONTACT,
            cle='devis').update(ordre=9)

        CadenceRelanceEtape.seed_cadence(self.company, Cadence.APRES_CONTACT)

        self.assertEqual(CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.APRES_CONTACT,
            cle='devis').count(), 1)

    def test_les_defauts_sont_ceux_du_moteur(self):
        self.assertIs(CADENCES_DEFAUT[Cadence.APRES_CONTACT],
                      CADENCE_APRES_CONTACT_DEFAUT)
        self.assertIs(CADENCES_DEFAUT[Cadence.VISITE], CADENCE_VISITE_DEFAUT)
        self.assertEqual(barreau_par_defaut(Cadence.VISITE, 'confirmation')
                         ['template_cle'], 'visite_confirmation')
        self.assertIsNone(barreau_par_defaut(Cadence.VISITE, 'devis'))
        self.assertEqual(set(CADENCES_MOTEUR),
                         {Cadence.APRES_CONTACT, Cadence.VISITE})


class BarreauParCleTests(TestCase):

    def setUp(self):
        self.company = _company('pcad-cle')

    def test_une_cadence_vide_est_seedee_a_la_volee(self):
        barreau = CadenceRelanceEtape.barreau_par_cle(
            self.company, Cadence.VISITE, 'debrief')
        self.assertIsNotNone(barreau)
        self.assertEqual(barreau.libelle,
                         'Débrief visite — rappeler le client')
        self.assertEqual(CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.VISITE).count(), 4)

    def test_inactif_rend_none_sauf_sur_demande(self):
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.APRES_CONTACT)
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.APRES_CONTACT,
            cle='dernier_appel').update(actif=False)

        self.assertIsNone(CadenceRelanceEtape.barreau_par_cle(
            self.company, Cadence.APRES_CONTACT, 'dernier_appel'))
        inactif = CadenceRelanceEtape.barreau_par_cle(
            self.company, Cadence.APRES_CONTACT, 'dernier_appel',
            inactif_ok=True)
        self.assertIsNotNone(inactif)
        self.assertFalse(inactif.actif)

    def test_supprime_rend_none_sans_reseeder(self):
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.VISITE)
        CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.VISITE,
            cle='debrief').delete()

        self.assertIsNone(CadenceRelanceEtape.barreau_par_cle(
            self.company, Cadence.VISITE, 'debrief', inactif_ok=True))
        self.assertEqual(CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.VISITE).count(), 3)

    def test_une_societe_ne_lit_jamais_le_barreau_d_une_autre(self):
        autre = _company('pcad-cle-autre')
        CadenceRelanceEtape.seed_cadence(autre, Cadence.VISITE)
        CadenceRelanceEtape.objects.filter(
            company=autre, cadence=Cadence.VISITE, cle='debrief').update(
                libelle='Débrief maison')

        barreau = CadenceRelanceEtape.barreau_par_cle(
            self.company, Cadence.VISITE, 'debrief')
        self.assertEqual(barreau.company_id, self.company.pk)
        self.assertEqual(barreau.libelle,
                         'Débrief visite — rappeler le client')


class UniciteDeLaCleTests(TestCase):

    def setUp(self):
        self.company = _company('pcad-uniq')
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.VISITE)

    def _barreau(self, company, cle, ordre):
        return CadenceRelanceEtape.objects.create(
            company=company, cadence=Cadence.VISITE, ordre=ordre,
            delai_jours=1, canal='appel', libelle='Doublon', cle=cle)

    def test_une_cle_deja_posee_ne_se_double_pas(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._barreau(self.company, 'debrief', 50)

    def test_la_meme_cle_vit_dans_une_autre_societe(self):
        autre = _company('pcad-uniq-autre')
        self.assertIsNotNone(self._barreau(autre, 'debrief', 50).pk)

    def test_les_barreaux_sans_cle_ne_sont_pas_contraints(self):
        self._barreau(self.company, '', 50)
        self._barreau(self.company, '', 51)
        self.assertEqual(CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.VISITE, cle='').count(), 2)


class ApiTests(TestCase):

    def setUp(self):
        self.company = _company('pcad-api')
        self.admin = User.objects.create_user(
            username='pcad-admin', password='pw', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _rows(self, resp):
        return (resp.data['results']
                if isinstance(resp.data, dict) and 'results' in resp.data
                else resp.data)

    def _barreau(self, cadence, cle):
        return CadenceRelanceEtape.objects.get(
            company=self.company, cadence=cadence, cle=cle)

    def test_la_liste_seede_et_sert_la_cle(self):
        resp = self.api.get(CADENCE_URL, {'cadence': 'apres_contact'})
        self.assertEqual(resp.status_code, 200, resp.data)
        lignes = self._rows(resp)
        self.assertEqual([r['cle'] for r in lignes],
                         [e['cle'] for e in CADENCE_APRES_CONTACT_DEFAUT])
        self.assertEqual(set(lignes[0]),
                         set(CONTRAT['exemple_apres_contact'][0]))

        resp = self.api.get(CADENCE_URL, {'cadence': 'visite'})
        self.assertEqual(len(self._rows(resp)), 4)

    def test_patch_change_libelle_delai_canal_heure(self):
        self.api.get(CADENCE_URL, {'cadence': 'apres_contact'})
        devis = self._barreau(Cadence.APRES_CONTACT, 'devis')

        resp = self.api.patch(f'{CADENCE_URL}{devis.pk}/', {
            'libelle': 'Faire le devis', 'delai_jours': 2,
            'canal': 'whatsapp', 'heure_cible': '10:15'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual((devis.libelle, devis.delai_jours, devis.canal,
                          devis.heure_cible.strftime('%H:%M'), devis.cle),
                         ('Faire le devis', 2, 'whatsapp', '10:15', 'devis'))

    def test_la_cle_n_est_jamais_modifiable_par_l_ecran(self):
        self.api.get(CADENCE_URL, {'cadence': 'visite'})
        debrief = self._barreau(Cadence.VISITE, 'debrief')

        resp = self.api.patch(f'{CADENCE_URL}{debrief.pk}/',
                              {'cle': 'autre_chose'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        debrief.refresh_from_db()
        self.assertEqual(debrief.cle, 'debrief')

    def test_un_ajout_a_la_main_n_a_pas_de_cle(self):
        resp = self.api.post(CADENCE_URL, {
            'cadence': 'visite', 'delai_jours': 3, 'canal': 'appel',
            'libelle': 'Rappel maison', 'cle': 'debrief'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['cle'], '')

    def test_un_barreau_a_cle_ne_change_pas_de_cadence(self):
        self.api.get(CADENCE_URL, {'cadence': 'visite'})
        debrief = self._barreau(Cadence.VISITE, 'debrief')

        resp = self.api.patch(f'{CADENCE_URL}{debrief.pk}/',
                              {'cadence': 'contact'}, format='json')

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('cadence', resp.data)
        debrief.refresh_from_db()
        self.assertEqual(debrief.cadence, Cadence.VISITE)

    def test_un_barreau_a_cle_peut_etre_supprime(self):
        self.api.get(CADENCE_URL, {'cadence': 'visite'})
        debrief = self._barreau(Cadence.VISITE, 'debrief')

        resp = self.api.delete(f'{CADENCE_URL}{debrief.pk}/')

        self.assertEqual(resp.status_code, 204)
        self.assertIsNone(CadenceRelanceEtape.barreau_par_cle(
            self.company, Cadence.VISITE, 'debrief', inactif_ok=True))
