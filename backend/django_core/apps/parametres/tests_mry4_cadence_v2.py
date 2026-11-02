"""MRY4 — Gabarit de cadence v2 : trois cadences, minutes, gabarit de message.

Ce que ce fichier verrouille :
  * la migration 0081 étiquette `generique` TOUTES les lignes existantes — un
    défaut `contact` les aurait fait se percuter avec le protocole de rappel
    sur la nouvelle clé d'unicité `(company, cadence, ordre)` ;
  * les trois cadences nommées seedent 11 / 10 / 2 barreaux, avec les délais
    EXACTS du Protocole de rappel v3 (6 appels maximum, jamais 7) ;
  * `seed_defaults` garde sa signature ET son effet historique (5 barreaux
    neutres) — il ne devient pas silencieusement autre chose ;
  * l'idempotence ne réécrit jamais un barreau personnalisé ;
  * l'API filtre par `?cadence=` et refuse un `delai_minutes` ≥ 1440.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.parametres.models_relance import (
    CADENCE_APRES_DEVIS_DEFAUT, CADENCE_CONTACT_DEFAUT,
    CADENCE_RELANCE_DEFAUT, CADENCE_REVEIL_DEFAUT, Cadence,
    CadenceRelanceEtape, CanalRelance,
)

User = get_user_model()

CADENCE_URL = '/api/django/parametres/cadence-relance/'


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ProtocoleV3Tests(TestCase):
    """Les délais viennent du Protocole de rappel v3 — pas d'une estimation."""

    def test_six_appels_maximum_sur_la_cadence_contact(self):
        appels = [e for e in CADENCE_CONTACT_DEFAUT
                  if e['canal'] == CanalRelance.APPEL]
        self.assertEqual(len(appels), 6)

    def test_cinq_whatsapp_sur_la_cadence_contact(self):
        messages = [e for e in CADENCE_CONTACT_DEFAUT
                    if e['canal'] == CanalRelance.WHATSAPP]
        self.assertEqual(len(messages), 5)

    def test_la_cadence_contact_tient_en_quatorze_jours(self):
        self.assertEqual(
            max(e['delai_jours'] for e in CADENCE_CONTACT_DEFAUT), 14)

    def test_la_deuxieme_touche_tombe_trois_minutes_apres(self):
        """« Rappelé dans les cinq minutes » : un délai en JOURS ne pouvait
        pas l'exprimer — c'est la raison d'être de `delai_minutes`."""
        touche = CADENCE_CONTACT_DEFAUT[1]
        self.assertEqual(touche['delai_jours'], 0)
        self.assertEqual(touche['delai_minutes'], 3)
        self.assertEqual(touche['canal'], CanalRelance.APPEL)

    def test_une_seule_touche_est_autorisee_le_dimanche(self):
        dimanche = [e for e in CADENCE_CONTACT_DEFAUT if e['dimanche_ok']]
        self.assertEqual(len(dimanche), 1)
        self.assertEqual(dimanche[0]['template_cle'], 'appel_dimanche')

    def test_apres_devis_porte_la_touche_dimanche_famille(self):
        cles = {e['template_cle'] for e in CADENCE_APRES_DEVIS_DEFAUT}
        self.assertIn('dimanche_famille', cles)

    def test_reveil_est_j30_puis_j60(self):
        self.assertEqual([e['delai_jours'] for e in CADENCE_REVEIL_DEFAUT],
                         [30, 60])


class SeedCadenceTests(TestCase):
    def test_seed_des_trois_cadences(self):
        company = _company('mry4-seed')
        self.assertEqual(
            CadenceRelanceEtape.seed_cadence(company, Cadence.CONTACT),
            len(CADENCE_CONTACT_DEFAUT))
        self.assertEqual(
            CadenceRelanceEtape.seed_cadence(company, Cadence.APRES_DEVIS),
            len(CADENCE_APRES_DEVIS_DEFAUT))
        self.assertEqual(
            CadenceRelanceEtape.seed_cadence(company, Cadence.REVEIL),
            len(CADENCE_REVEIL_DEFAUT))

    def test_seed_defaults_reste_les_cinq_barreaux_neutres(self):
        """Bug CI #77 — `seed_defaults` ne devient pas autre chose en douce."""
        company = _company('mry4-neutre')
        cree = CadenceRelanceEtape.seed_defaults(company)
        self.assertEqual(cree, len(CADENCE_RELANCE_DEFAUT))
        lignes = CadenceRelanceEtape.objects.filter(company=company)
        self.assertEqual(lignes.count(), 5)
        self.assertEqual(
            set(lignes.values_list('cadence', flat=True)), {'generique'})
        self.assertEqual(
            list(lignes.order_by('ordre')
                 .values_list('delai_jours', flat=True)),
            [2, 5, 10, 20, 35])

    def test_seed_est_idempotent_par_cadence(self):
        company = _company('mry4-idem')
        CadenceRelanceEtape.seed_cadence(company, Cadence.CONTACT)
        self.assertEqual(
            CadenceRelanceEtape.seed_cadence(company, Cadence.CONTACT), 0)
        self.assertEqual(
            CadenceRelanceEtape.objects.filter(
                company=company, cadence=Cadence.CONTACT).count(),
            len(CADENCE_CONTACT_DEFAUT))

    def test_seed_ne_reecrit_jamais_un_barreau_personnalise(self):
        company = _company('mry4-perso')
        CadenceRelanceEtape.seed_cadence(company, Cadence.CONTACT)
        etape = CadenceRelanceEtape.objects.get(
            company=company, cadence=Cadence.CONTACT, ordre=2)
        etape.delai_minutes = 42
        etape.save(update_fields=['delai_minutes'])
        CadenceRelanceEtape.seed_cadence(company, Cadence.CONTACT)
        etape.refresh_from_db()
        self.assertEqual(etape.delai_minutes, 42)

    def test_le_meme_ordre_coexiste_dans_deux_cadences(self):
        """C'est exactement ce que l'ancienne unicité (company, ordre)
        interdisait."""
        company = _company('mry4-ordre')
        CadenceRelanceEtape.seed_cadence(company, Cadence.CONTACT)
        CadenceRelanceEtape.seed_cadence(company, Cadence.REVEIL)
        self.assertEqual(
            CadenceRelanceEtape.objects.filter(
                company=company, ordre=1).count(), 2)

    def test_cadence_pour_seede_a_la_volee_la_bonne_cadence(self):
        company = _company('mry4-lazy')
        barreaux = CadenceRelanceEtape.cadence_pour(company, Cadence.REVEIL)
        self.assertEqual(len(barreaux), len(CADENCE_REVEIL_DEFAUT))
        # Aucune autre cadence n'a été seedée au passage.
        self.assertEqual(
            CadenceRelanceEtape.objects.filter(
                company=company).exclude(cadence=Cadence.REVEIL).count(), 0)

    def test_cadence_pour_ignore_les_barreaux_inactifs(self):
        company = _company('mry4-inactif')
        CadenceRelanceEtape.seed_cadence(company, Cadence.CONTACT)
        CadenceRelanceEtape.objects.filter(
            company=company, cadence=Cadence.CONTACT, ordre=1
        ).update(actif=False)
        self.assertEqual(
            len(CadenceRelanceEtape.cadence_pour(company, Cadence.CONTACT)),
            len(CADENCE_CONTACT_DEFAUT) - 1)

    def test_isolation_entre_societes(self):
        une = _company('mry4-t1')
        autre = _company('mry4-t2')
        CadenceRelanceEtape.seed_cadence(une, Cadence.CONTACT)
        self.assertEqual(
            CadenceRelanceEtape.objects.filter(company=autre).count(), 0)

    def test_heure_cible_seedee_sur_les_touches_qui_en_ont_une(self):
        company = _company('mry4-heure')
        CadenceRelanceEtape.seed_cadence(company, Cadence.CONTACT)
        etape = CadenceRelanceEtape.objects.get(
            company=company, cadence=Cadence.CONTACT, ordre=4)
        self.assertEqual(etape.heure_cible, datetime.time(10, 30))
        sans_heure = CadenceRelanceEtape.objects.get(
            company=company, cadence=Cadence.CONTACT, ordre=1)
        self.assertIsNone(sans_heure.heure_cible)


class MigrationEtiquetteGeneriqueTests(TestCase):
    """L'opération de données de la migration 0081, exécutée telle quelle.

    On appelle la VRAIE fonction `etiqueter_generique` avec un registre
    d'applications simulé — jamais un `MigrationExecutor` qui dé-migrerait la
    base de test partagée sous les autres suites. Ce qu'elle garantit : les
    barreaux qui existaient AVANT deviennent `generique`. Sans elle, ils
    héritaient du défaut `contact` et se percutaient avec le protocole de
    rappel sur la clé `(company, cadence, ordre)`.
    """

    class _RegistreSimule:
        @staticmethod
        def get_model(app_label, model_name):
            assert (app_label, model_name) == (
                'parametres', 'CadenceRelanceEtape')
            return CadenceRelanceEtape

    def test_les_lignes_existantes_deviennent_generique(self):
        from importlib import import_module

        # Nom de module commençant par un chiffre : seul `import_module`
        # peut le charger (un `import` littéral serait une erreur de syntaxe).
        module = import_module(
            'apps.parametres.migrations.0081_cadence_relance_v2')
        company = _company('mry4-mig')
        # Une ligne posée AVANT la migration : le défaut du modèle est
        # `contact`, la migration doit la ramener à `generique`.
        etape = CadenceRelanceEtape.objects.create(
            company=company, ordre=1, delai_jours=2, canal='appel',
            libelle='Premier rappel', actif=True)
        self.assertEqual(etape.cadence, Cadence.CONTACT)
        module.etiqueter_generique(self._RegistreSimule, None)
        etape.refresh_from_db()
        self.assertEqual(etape.cadence, Cadence.GENERIQUE)


class CadenceApiTests(TestCase):
    def setUp(self):
        self.company = _company('mry4-api')
        self.admin = User.objects.create_user(
            username='mry4-admin', password='pw', role_legacy='admin',
            company=self.company)
        self.api = _auth(self.admin)
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.CONTACT)
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.REVEIL)

    def _rows(self, resp):
        return (resp.data['results']
                if isinstance(resp.data, dict) and 'results' in resp.data
                else resp.data)

    def test_filtre_par_cadence(self):
        resp = self.api.get(CADENCE_URL, {'cadence': 'reveil'})
        self.assertEqual(resp.status_code, 200)
        rows = self._rows(resp)
        self.assertEqual(len(rows), len(CADENCE_REVEIL_DEFAUT))
        self.assertEqual({r['cadence'] for r in rows}, {'reveil'})

    def test_sans_filtre_toutes_les_cadences_sortent(self):
        rows = self._rows(self.api.get(CADENCE_URL))
        self.assertEqual(
            len(rows),
            len(CADENCE_CONTACT_DEFAUT) + len(CADENCE_REVEIL_DEFAUT))

    def test_les_nouveaux_champs_sont_exposes(self):
        rows = self._rows(self.api.get(CADENCE_URL, {'cadence': 'contact'}))
        ligne = next(r for r in rows if r['ordre'] == 2)
        for champ in ('cadence', 'delai_minutes', 'heure_cible',
                      'template_cle', 'dimanche_ok'):
            self.assertIn(champ, ligne)
        self.assertEqual(ligne['delai_minutes'], 3)

    def test_delai_minutes_au_dela_de_24h_est_refuse(self):
        etape = CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.CONTACT).first()
        resp = self.api.patch(f'{CADENCE_URL}{etape.id}/',
                              {'delai_minutes': 1440}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('delai_minutes', resp.data)

    def test_heure_cible_reste_optionnelle(self):
        etape = CadenceRelanceEtape.objects.get(
            company=self.company, cadence=Cadence.CONTACT, ordre=4)
        resp = self.api.patch(f'{CADENCE_URL}{etape.id}/',
                              {'heure_cible': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        self.assertIsNone(etape.heure_cible)

    def test_company_forcee_cote_serveur(self):
        autre = _company('mry4-api-autre')
        resp = self.api.post(CADENCE_URL, {
            'cadence': 'contact', 'ordre': 99, 'delai_jours': 1,
            'canal': 'appel', 'libelle': 'Test', 'company': autre.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cree = CadenceRelanceEtape.objects.get(ordre=99)
        self.assertEqual(cree.company_id, self.company.pk)


class CadenceEditeurMry28Tests(TestCase):
    """MRY28 (défaut MAJEUR) — sur une société EXISTANTE (qui a déjà utilisé
    `contact`/`reveil`, comme n'importe quel tenant réel), les onglets
    « Après devis » et « Réveil » de l'éditeur de Paramètres → CRM
    affichaient « Aucune étape pour cette cadence. » sans aucun moyen d'en
    sortir tant que personne n'avait initialisé cette cadence sur un lead
    (seul ``CadenceRelanceEtape.cadence_pour`` seedait, jamais l'éditeur).
    """

    def setUp(self):
        self.company = _company('mry28-editeur')
        self.admin = User.objects.create_user(
            username='mry28-admin', password='pw', role_legacy='admin',
            company=self.company)
        self.api = _auth(self.admin)
        # La société a déjà de l'activité sur D'AUTRES cadences — le bug
        # n'était pas « société toute neuve », mais « cadence jamais
        # touchée », même sur un tenant actif de longue date.
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.CONTACT)

    def _rows(self, resp):
        return (resp.data['results']
                if isinstance(resp.data, dict) and 'results' in resp.data
                else resp.data)

    def test_get_cadence_apres_devis_seede_a_la_lecture(self):
        self.assertFalse(
            CadenceRelanceEtape.objects.filter(
                company=self.company, cadence=Cadence.APRES_DEVIS).exists())
        resp = self.api.get(CADENCE_URL, {'cadence': 'apres_devis'})
        self.assertEqual(resp.status_code, 200)
        rows = self._rows(resp)
        self.assertEqual(len(rows), len(CADENCE_APRES_DEVIS_DEFAUT))
        self.assertEqual({r['cadence'] for r in rows}, {'apres_devis'})

    def test_get_cadence_apres_devis_reste_idempotent(self):
        premier = self._rows(
            self.api.get(CADENCE_URL, {'cadence': 'apres_devis'}))
        second = self._rows(
            self.api.get(CADENCE_URL, {'cadence': 'apres_devis'}))
        self.assertEqual(len(premier), len(CADENCE_APRES_DEVIS_DEFAUT))
        self.assertEqual(len(second), len(CADENCE_APRES_DEVIS_DEFAUT))
        self.assertEqual(
            CadenceRelanceEtape.objects.filter(
                company=self.company, cadence=Cadence.APRES_DEVIS).count(),
            len(CADENCE_APRES_DEVIS_DEFAUT))

    def test_cadence_inconnue_est_refusee(self):
        resp = self.api.get(CADENCE_URL, {'cadence': 'bidon'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('cadence', resp.data)
        # Rien n'a été seedé sous le nom invalide.
        self.assertFalse(
            CadenceRelanceEtape.objects.filter(
                company=self.company, cadence='bidon').exists())

    def test_post_sur_apres_devis_force_aussi_la_company(self):
        """La création reste ouverte sur cette cadence, et la société vient
        TOUJOURS du serveur — jamais du corps de la requête."""
        autre = _company('mry28-editeur-autre')
        resp = self.api.post(CADENCE_URL, {
            'cadence': 'apres_devis', 'ordre': 42, 'delai_jours': 1,
            'canal': 'appel', 'libelle': 'Test MRY28', 'company': autre.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cree = CadenceRelanceEtape.objects.get(
            company=self.company, cadence='apres_devis', ordre=42)
        self.assertEqual(cree.company_id, self.company.pk)
        self.assertFalse(
            CadenceRelanceEtape.objects.filter(company=autre).exists())
