"""AG1 — Tests de l'endpoint GET /api/django/agent/actions/.

Couvre :
- auth requise (401/403 sans token) ;
- l'endpoint renvoie seulement les actions que le caller peut exécuter ;
- aucun débordement inter-société : deux utilisateurs de sociétés distinctes
  avec le même nom de permission voient leur catalogue filtré par LEUR rôle,
  sans fuite de l'autre société.
"""
from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

User = get_user_model()
URL = '/api/django/agent/actions/'


def _auth(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


class AgentActionsEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Co A', slug='co-a')
        self.sales_role = Role.objects.create(
            company=self.company, nom='Vendeur',
            permissions=['ventes_creer', 'ventes_pdf', 'crm_voir'])
        self.sales = User.objects.create_user(
            username='vendeur_a', password='x', role=self.sales_role,
            company=self.company)
        self.readonly_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['crm_voir'])
        self.readonly = User.objects.create_user(
            username='ro_a', password='x', role=self.readonly_role,
            company=self.company)

    def test_requires_authentication(self):
        resp = APIClient().get(URL)
        self.assertIn(resp.status_code, (401, 403))

    def test_returns_only_permitted_actions(self):
        resp = _auth(self.sales).get(URL)
        self.assertEqual(resp.status_code, 200)
        keys = {a['key'] for a in resp.data['actions']}
        self.assertEqual(resp.data['count'], len(resp.data['actions']))
        self.assertIn('ventes.devis.creer_auto', keys)
        self.assertIn('ventes.devis.generer_pdf', keys)
        self.assertNotIn('stock.produit.delete', keys)

    def test_catalogue_suit_l_interrupteur_du_copilote(self):
        """COP-G1 — ``ASSISTANT_COPILOTE`` : l'endpoint ne sert le lot
        ``copilote`` qu'aux comptes pour qui il est allumé (ici un
        commercial : éteint par défaut, allumé par ``tous``) et ``lot`` figure
        dans chaque action servie."""
        from apps.agent.registry import (
            AgentAction, register, unregister)
        for cle, lot in (('tmp.vw.copilote', 'copilote'),
                         ('tmp.vw.herite', 'herite')):
            register(AgentAction(key=cle, label=cle, description='d',
                                 endpoint='/x/', lot=lot))
            self.addCleanup(unregister, cle)
        for reglage, attendu in (('admins', {'tmp.vw.herite'}),
                                 ('aucun', {'tmp.vw.herite'}),
                                 ('tous', {'tmp.vw.copilote'})):
            with self.settings(ASSISTANT_COPILOTE=reglage):
                resp = _auth(self.sales).get(URL)
            servies = {a['key']: a['lot'] for a in resp.data['actions']
                       if a['key'].startswith('tmp.vw.')}
            self.assertEqual(set(servies), attendu, reglage)
            self.assertTrue(all(servies.values()), reglage)

    def test_readonly_user_gets_limited_catalogue(self):
        resp = _auth(self.readonly).get(URL)
        self.assertEqual(resp.status_code, 200)
        keys = {a['key'] for a in resp.data['actions']}
        self.assertIn('crm.lead.list', keys)
        self.assertNotIn('ventes.devis.creer_auto', keys)
        self.assertNotIn('ventes.devis.generer_pdf', keys)

    def test_action_metadata_present(self):
        resp = _auth(self.sales).get(URL)
        action = next(a for a in resp.data['actions']
                      if a['key'] == 'ventes.devis.generer_pdf')
        for fld in ('key', 'label', 'description', 'inputs', 'endpoint',
                    'method', 'required_permission', 'risk', 'confirm_summary',
                    'carte', 'lot', 'objets'):
            self.assertIn(fld, action)
        self.assertEqual(action['risk'], 'internal')


class CrossTenantNoLeakageTest(TestCase):
    """Deux sociétés distinctes : le filtre est par rôle/permission, et un rôle
    n'existe que dans SA société, donc le catalogue ne fuit pas d'une société à
    l'autre."""

    def setUp(self):
        self.co_a = Company.objects.create(nom='Tenant A', slug='tenant-a')
        self.co_b = Company.objects.create(nom='Tenant B', slug='tenant-b')
        # Société A : un vendeur avec ventes_creer.
        self.role_a = Role.objects.create(
            company=self.co_a, nom='Vendeur A', permissions=['ventes_creer'])
        self.user_a = User.objects.create_user(
            username='u_a', password='x', role=self.role_a, company=self.co_a)
        # Société B : un utilisateur lecture seule (crm_voir uniquement).
        self.role_b = Role.objects.create(
            company=self.co_b, nom='Lecture B', permissions=['crm_voir'])
        self.user_b = User.objects.create_user(
            username='u_b', password='x', role=self.role_b, company=self.co_b)

    def test_each_tenant_sees_own_permission_set(self):
        keys_a = {a['key'] for a in _auth(self.user_a).get(URL).data['actions']}
        keys_b = {a['key'] for a in _auth(self.user_b).get(URL).data['actions']}
        # A peut créer un devis ; B (lecture seule autre société) non.
        self.assertIn('ventes.devis.creer_auto', keys_a)
        self.assertNotIn('ventes.devis.creer_auto', keys_b)
        # B voit les leads (crm_voir) ; A n'a pas crm_voir → ne le voit pas.
        self.assertIn('crm.lead.list', keys_b)
        self.assertNotIn('crm.lead.list', keys_a)


# ── AIC6 — journal de l'assistant des commerciaux (contrat AIC1) ─────────────
import json  # noqa: E402 — bloc AIC6 ajoute en fin de module
from pathlib import Path  # noqa: E402

from django.test import override_settings  # noqa: E402

from apps.agent import services as agent_services  # noqa: E402
from apps.agent.models import AssistantEvent  # noqa: E402
from apps.agent.views import ACTION_PREUVE_EVENEMENT  # noqa: E402

URL_EVENEMENTS = '/api/django/agent/evenements/'
SECRET_AIC6 = 'secret-de-test-aic6'
CONTRAT_EVENEMENT = json.loads(
    (Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'assistant_evenement.json').read_text(encoding='utf-8'))


def _corps_signe(user, **surcharge):
    corps = dict(CONTRAT_EVENEMENT['exemple_corps'], **surcharge)
    corps['preuve'] = agent_services.calculer_preuve_confirmation(
        secret=SECRET_AIC6, action_key=ACTION_PREUVE_EVENEMENT,
        company_id=user.company_id, user_id=user.pk, inputs=dict(corps),
        object_id=None)
    return corps


@override_settings(AGENT_HMAC_SECRET=SECRET_AIC6)
class AssistantEvenementTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='AIC6 Co', slug='aic6-co')
        self.autre = Company.objects.create(nom='AIC6 Autre', slug='aic6-autre')
        self.vendeur = User.objects.create_user(
            username='aic6_vendeur', password='x', role_legacy='normal',
            company=self.co)
        self.collegue = User.objects.create_user(
            username='aic6_collegue', password='x', role_legacy='normal',
            company=self.co)
        self.admin = User.objects.create_user(
            username='aic6_admin', password='x', role_legacy='admin',
            company=self.co)
        self.admin_autre = User.objects.create_user(
            username='aic6_admin_b', password='x', role_legacy='admin',
            company=self.autre)

    def test_evenement_cree_par_relais_avec_preuve_sinon_403(self):
        sans_preuve = dict(CONTRAT_EVENEMENT['exemple_corps'], preuve='0' * 64)
        resp = _auth(self.vendeur).post(URL_EVENEMENTS, sans_preuve, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(AssistantEvent.objects.exists())

        resp = _auth(self.vendeur).post(
            URL_EVENEMENTS, _corps_signe(self.vendeur), format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        # La reponse porte EXACTEMENT les cles du contrat.
        self.assertEqual(set(resp.data), set(CONTRAT_EVENEMENT['exemple']))
        ev = AssistantEvent.objects.get(pk=resp.data['id'])
        # company/user poses cote serveur ; lead 12 hors societe => null.
        self.assertEqual((ev.company, ev.user), (self.co, self.vendeur))
        self.assertIsNone(ev.lead_id)
        self.assertEqual(ev.tokens, {
            'cache_read': 1800, 'cache_write': 300, 'input': 420, 'output': 96})
        self.assertEqual(ev.outils_appeles, ['crm.lead.note'])
        self.assertEqual(ev.note, 0)

    def test_erreur_avec_request_id_et_tampon_borne(self):
        """COP-G5 — ``erreur`` porte ``request_id`` et ``diagnostic`` ; le
        tampon est BORNÉ (15 requêtes, 10 erreurs, chaînes tronquées, route sans
        chaîne de requête) et tout champ inconnu est écarté."""
        requete = dict(
            CONTRAT_EVENEMENT['exemple_erreur_avec_tampon']['diagnostic']['requetes'][0],
            route='/api/django/crm/leads/12/?telephone=0612345678#x' + 'a' * 400,
            corps={'secret': 'x'})
        erreur = dict(CONTRAT_EVENEMENT['exemple_erreur_avec_tampon'])
        erreur['inconnu'] = 'ecarte'
        erreur['message'] = 'm' * 900
        erreur['diagnostic'] = dict(
            erreur['diagnostic'], requetes=[dict(requete) for _ in range(20)],
            erreurs=[{'genre': 'script', 'message': 'appelle 0612345678',
                      'il_y_a_s': 3, 'pile': 'x'}] * 14,
            cookie='ecarte')
        resp = _auth(self.vendeur).post(
            URL_EVENEMENTS, _corps_signe(self.vendeur, erreur=erreur),
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        stocke = AssistantEvent.objects.get(pk=resp.data['id']).erreur
        self.assertEqual(set(stocke), {
            'status', 'outil', 'message', 'request_id', 'diagnostic'})
        self.assertEqual(len(stocke['message']), 300)
        self.assertEqual(stocke['request_id'], erreur['request_id'])
        diag = stocke['diagnostic']
        self.assertEqual(set(diag), {'version', 'ecran', 'navigateur',
                                     'en_ligne', 'requetes', 'erreurs'})
        self.assertEqual((len(diag['requetes']), len(diag['erreurs'])), (15, 10))
        self.assertEqual(set(diag['requetes'][0]), {
            'methode', 'route', 'statut', 'duree_ms', 'request_id', 'code',
            'il_y_a_s'})
        self.assertEqual(diag['requetes'][0]['route'], '/api/django/crm/leads/12/')
        self.assertEqual(diag['erreurs'][0]['message'], 'appelle [tel]')
        self.assertEqual(set(diag['erreurs'][0]), {'genre', 'message', 'il_y_a_s'})

    def test_outils_du_relais_et_tokens_complets_acceptes(self):
        """COP-G5 (couture avec le relais) — ``outils_appeles`` porte aussi les
        outils propres au relais (hors registre) et ``tokens`` les quatre clés."""
        outils = ['crm.lead.note', 'sql_db_query', 'sql_db_schema', 'report_gap']
        tokens = {'input': 10, 'output': 20, 'cache_read': 30, 'cache_write': 40}
        resp = _auth(self.vendeur).post(
            URL_EVENEMENTS,
            _corps_signe(self.vendeur, outils_appeles=outils, tokens=tokens),
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ev = AssistantEvent.objects.get(pk=resp.data['id'])
        self.assertEqual((ev.outils_appeles, ev.tokens), (outils, tokens))

    def test_erreur_aux_types_faux_refusee_400(self):
        for erreur in ({'status': '409'}, {'status': True},
                       {'outil': 3}, {'request_id': ['x']},
                       {'diagnostic': []}, ['liste']):
            resp = _auth(self.vendeur).post(
                URL_EVENEMENTS, _corps_signe(self.vendeur, erreur=erreur),
                format='json')
            self.assertEqual(resp.status_code, 400, erreur)
        self.assertFalse(AssistantEvent.objects.exists())

    def test_erreur_simple_du_contrat_reste_acceptee(self):
        erreur = CONTRAT_EVENEMENT['exemple_erreur_outil']
        resp = _auth(self.vendeur).post(
            URL_EVENEMENTS, _corps_signe(self.vendeur, erreur=erreur),
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(AssistantEvent.objects.get(pk=resp.data['id']).erreur, erreur)

    def test_preuve_dun_autre_utilisateur_refusee(self):
        corps = _corps_signe(self.collegue)
        resp = _auth(self.vendeur).post(URL_EVENEMENTS, corps, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_note_par_auteur_seul(self):
        ev = AssistantEvent.objects.create(
            company=self.co, user=self.vendeur, question='q ?')
        url = f'{URL_EVENEMENTS}{ev.pk}/note/'
        ecriture = CONTRAT_EVENEMENT['ecriture_commercial']
        resp = _auth(self.collegue).patch(url, ecriture['exemple_corps'], format='json')
        self.assertEqual(resp.status_code, 404)
        resp = _auth(self.vendeur).patch(
            url, dict(ecriture['exemple_corps'], question='pirate', intention='bug'),
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(set(resp.data), set(ecriture['exemple']))
        ev.refresh_from_db()
        self.assertEqual((ev.note, ev.commentaire),
                         (-1, "Il n'a pas trouvé le devis signé."))
        self.assertEqual((ev.question, ev.intention), ('q ?', 'donnee'))
        resp = _auth(self.vendeur).patch(url, {'note': 5}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_liste_scopee_societe(self):
        AssistantEvent.objects.create(company=self.co, user=self.vendeur, question='a')
        AssistantEvent.objects.create(company=self.autre, question='b')
        self.assertEqual(_auth(self.vendeur).get(URL_EVENEMENTS).status_code, 403)
        resp = _auth(self.admin).get(URL_EVENEMENTS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([e['question'] for e in resp.data['results']], ['a'])
        resp = _auth(self.admin_autre).get(URL_EVENEMENTS)
        self.assertEqual([e['question'] for e in resp.data['results']], ['b'])


# ── AIC11 — export anonymisé pour le tri nocturne (contrat AIC2) ─────────────
import re  # noqa: E402

CONTRAT_EXPORT = json.loads(
    (Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'assistant_export.json').read_text(encoding='utf-8'))
# Jeton de remplacement de chaque règle, LU du contrat (aucune seconde copie).
JETONS = {
    regle: re.search(r'`(\[\w+\])`', texte).group(1)
    for regle, texte in CONTRAT_EXPORT['anonymisation'].items()
    if regle in ('telephones', 'emails', 'noms', 'suites_de_chiffres')
}


class AnonymiserTexteTests(TestCase):
    def test_regles_du_contrat_dans_lordre(self):
        self.assertEqual(set(JETONS), {'telephones', 'emails', 'noms',
                                       'suites_de_chiffres'})
        cas = {
            'telephones': ['0612345678', '06 12 34 56 78', '+212 6 12 34 56 78',
                           '06.12.34.56.78', '06-12-34-56-78', '00212612345678'],
            'emails': ['ahmed@x.ma', 'a.b+c@exemple.co.uk'],
            'noms': ['Ahmed', 'BÉNALI', 'benali'],
            'suites_de_chiffres': ['123456', '9876543'],
        }
        for regle, valeurs in cas.items():
            for valeur in valeurs:
                with self.subTest(regle=regle, valeur=valeur):
                    sortie = agent_services.anonymiser_texte(
                        f'avant {valeur} apres', ['Ahmed', 'Benali'])
                    self.assertEqual(sortie, f'avant {JETONS[regle]} apres')
        # Ni un mot qui CONTIENT le nom, ni un nombre court.
        self.assertEqual(agent_services.anonymiser_texte(
            'Ahmedou paie 12 345 DH', ['Ahmed']), 'Ahmedou paie 12 345 DH')


class BornerErreurEvenementTests(SimpleTestCase):
    """COP-G5 — ``borner_erreur`` / ``borner_diagnostic`` (fonctions pures)."""

    def test_non_objet_donne_none(self):
        for valeur in (None, 'x', [], 3):
            self.assertIsNone(agent_services.borner_erreur(valeur))
            self.assertIsNone(agent_services.borner_diagnostic(valeur))

    def test_diagnostic_du_contrat_traverse_a_l_identique(self):
        diag = CONTRAT_EVENEMENT['exemple_erreur_avec_tampon']['diagnostic']
        self.assertEqual(agent_services.borner_diagnostic(diag), diag)

    def test_bornes_chaines_et_champs_inconnus(self):
        sortie = agent_services.borner_diagnostic({
            'version': 'v' * 100, 'navigateur': 'Chrome', 'en_ligne': 'oui',
            'requetes': [{'methode': 'post', 'route': '/x/?a=1', 'statut': True,
                          'duree_ms': 12.5, 'corps': 'secret'}, 'pas un objet'],
            'erreurs': 'pas une liste', 'inconnu': 1})
        self.assertEqual(len(sortie['version']), 40)
        self.assertIsNone(sortie['en_ligne'])
        self.assertEqual(sortie['erreurs'], [])
        self.assertEqual(sortie['requetes'], [{
            'methode': 'POST', 'route': '/x/', 'statut': None, 'duree_ms': None,
            'request_id': '', 'code': '', 'il_y_a_s': None}])
        self.assertNotIn('inconnu', sortie)

    def test_erreur_sans_request_id_ni_tampon_reste_a_trois_cles(self):
        self.assertEqual(
            agent_services.borner_erreur({'status': 502, 'outil': 'o', 'message': 'm'}),
            {'status': 502, 'outil': 'o', 'message': 'm'})


@override_settings(AGENT_HMAC_SECRET=SECRET_AIC6)
class AssistantExportTests(TestCase):
    URL = URL_EVENEMENTS + 'export/'

    def setUp(self):
        from apps.crm.models import Lead

        self.co = Company.objects.create(nom='AIC11 Co', slug='aic11-co')
        self.autre = Company.objects.create(nom='AIC11 Autre', slug='aic11-autre')
        self.admin = User.objects.create_user(
            username='aic11_admin', password='x', role_legacy='admin', company=self.co)
        self.vendeur = User.objects.create_user(
            username='aic11_vendeur', password='x', role_legacy='normal', company=self.co)
        lead = Lead.objects.create(company=self.co, nom='Benali', prenom='Ahmed')
        self.manque = AssistantEvent.objects.create(
            company=self.co, user=self.vendeur, intention='manque', lead_id=lead.pk,
            question='Envoie le devis à Ahmed Benali 0612345678 ahmed@x.ma',
            commentaire='Rappeler BENALI au 06 12 34 56 78')
        AssistantEvent.objects.create(company=self.co, user=self.vendeur,
                                      intention='donnee', question='Combien ?')
        AssistantEvent.objects.create(company=self.co, user=self.vendeur,
                                      intention='hors_champ', question='Météo ?')
        AssistantEvent.objects.create(company=self.autre, intention='bug',
                                      question='Autre société 0699999999')

    def test_export_garde_trois_cles_d_erreur_sans_le_tampon(self):
        """COP-G5 — le tampon technique et le request_id d'un événement ne
        partent pas dans l'export (le tri nocturne dépose des lignes au dépôt)."""
        AssistantEvent.objects.create(
            company=self.co, user=self.vendeur, intention='bug', question='Bug',
            erreur=CONTRAT_EVENEMENT['exemple_erreur_avec_tampon'])
        resp = _auth(self.admin).get(self.URL)
        bug = next(e for e in resp.data['evenements'] if e['intention'] == 'bug')
        self.assertEqual(set(bug['erreur']), {'status', 'outil', 'message'})

    def test_export_anonymise_sans_tel_ni_nom_ni_email(self):
        resp = _auth(self.admin).get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(set(resp.data), set(CONTRAT_EXPORT['exemple']))
        lignes = resp.data['evenements']
        self.assertEqual(len(lignes), 3)  # société de l'admin seulement
        self.assertEqual(set(lignes[0]), set(CONTRAT_EXPORT['exemple']['evenements'][0]))
        manque = next(e for e in lignes if e['intention'] == 'manque')
        self.assertEqual(manque['question_anonymisee'],
                         'Envoie le devis à [client] [tel] [email]')
        self.assertEqual(manque['commentaire_anonymise'], 'Rappeler [client] au [tel]')
        self.assertEqual(manque['id_hache'], agent_services.hacher_identifiant(
            self.manque.pk, SECRET_AIC6))
        self.assertEqual(manque['utilisateur_hache'], agent_services.hacher_identifiant(
            self.vendeur.pk, SECRET_AIC6))
        brut = json.dumps(resp.data, default=str)
        for interdit in ('0612345678', 'Benali', 'ahmed@x.ma', 'AIC11 Co', '0699999999'):
            self.assertNotIn(interdit, brut)
        for cle in CONTRAT_EXPORT['anonymisation']['jamais_exportes']:
            self.assertNotIn(cle, lignes[0])
        self.assertEqual(resp.data['totaux']['non_supportes'], 2)
        self.assertEqual(resp.data['totaux']['par_intention']['donnee'], 1)

    def test_export_admin_seul(self):
        self.assertEqual(_auth(self.vendeur).get(self.URL).status_code, 404)
        with override_settings(AGENT_HMAC_SECRET=''):
            self.assertEqual(_auth(self.admin).get(self.URL).status_code, 403)


# ── AIC12 — mesure : coût, taux de non-supporté, repli (contrat AIC2) ────────
CONTRAT_STATS = json.loads(
    (Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'assistant_stats.json').read_text(encoding='utf-8'))


class AssistantStatsTests(TestCase):
    URL = URL_EVENEMENTS + 'stats/'

    def setUp(self):
        self.co = Company.objects.create(nom='AIC12 Co', slug='aic12-co')
        self.admin = User.objects.create_user(
            username='aic12_admin', password='x', role_legacy='admin', company=self.co)
        self.vendeur = User.objects.create_user(
            username='aic12_vendeur', password='x', role_legacy='normal', company=self.co)
        self.collegue = User.objects.create_user(
            username='aic12_collegue', password='x', role_legacy='normal', company=self.co)
        AssistantEvent.objects.create(
            company=self.co, user=self.vendeur, question='Combien ?', modele='claude-sonnet-5-5',
            tokens={'input': 1_000_000, 'output': 100_000, 'cache_read': 2_000_000})
        AssistantEvent.objects.create(
            company=self.co, user=self.vendeur, intention='manque', modele='claude-haiku-5-5',
            question='Envoie-le sur WhatsApp au 0612345678',
            tokens={'input': 2_000_000, 'output': 0, 'cache_read': 0})
        AssistantEvent.objects.create(
            company=self.co, user=self.collegue, intention='hors_champ', repli=True,
            modele='llama-3.3-70b-versatile', question='Météo ?', tokens={'input': 500_000})

    def test_prix_nommes_alignes_sur_le_contrat(self):
        prix = {k: v for k, v in CONTRAT_STATS['prix_mtok'].items()
                if k not in ('releve_le', 'unite')}
        self.assertEqual(agent_services.PRIX_MTOK_USD, prix)
        self.assertEqual(agent_services.PRIX_MTOK_RELEVE_LE,
                         CONTRAT_STATS['prix_mtok']['releve_le'])

    def test_stats_cout_taux_et_repli(self):
        resp = _auth(self.admin).get(self.URL, {'semaines': 1})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(set(resp.data), set(CONTRAT_STATS['exemple']))
        # Sonnet : 2 + 1 + 2 000 000 × 0,10 / 1e6 = 3,20 ; Haiku : 0,20 ; Groq : 0.
        self.assertEqual(resp.data['cout_estime_usd'], 3.40)
        self.assertEqual(resp.data['questions'], 3)
        self.assertEqual(resp.data['commerciaux_actifs'], 2)
        self.assertEqual(resp.data['questions_par_commercial_semaine'], 1.5)
        self.assertEqual(resp.data['taux_non_supporte'], round(2 / 3, 4))
        self.assertEqual(resp.data['part_repli'], round(1 / 3, 4))
        self.assertEqual(resp.data['par_intention']['manque'], 1)
        self.assertEqual(resp.data['manques_recents'], [
            {'question_anonymisee': 'Envoie-le sur WhatsApp au [tel]', 'vu_n_fois': 1}])

    def test_cout_compte_les_ecritures_de_cache(self):
        """COP-G5 — ``cache_write`` a son prix NOMMÉ (2 × l'entrée, écriture
        d'une heure) : 1 M de tokens écrits en cache = 4 USD sur Sonnet 5.5."""
        AssistantEvent.objects.create(
            company=self.co, user=self.vendeur, modele='claude-sonnet-5-5',
            question='Manuel ?', tokens={'cache_write': 1_000_000})
        resp = _auth(self.admin).get(self.URL, {'semaines': 1})
        self.assertEqual(resp.data['cout_estime_usd'], 7.40)
        self.assertEqual(agent_services.cout_estime_usd(
            'claude-sonnet-5-5', {'cache_write': 500_000}), 2.0)
        self.assertEqual(agent_services.cout_estime_usd('inconnu', {'cache_write': 5}), 0.0)

    def test_stats_admin_seul(self):
        self.assertEqual(_auth(self.vendeur).get(self.URL).status_code, 403)
        self.assertEqual(_auth(self.admin).get(self.URL, {'semaines': 'x'}).status_code, 400)

    def test_bornes_et_corps_publies_tels_qu_appliques(self):
        """api-fuzz-full 28/10 (ENF11) — ``semaines`` publié 1..52 (``-17739``
        était « conforme » puis refusé) ; le PATCH de note publie ``note``
        obligatoire (un ``{}`` était « conforme » puis refusé 400)."""
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator
        doc = SchemaGenerator(patterns=[path(
            'api/django/agent/', include('apps.agent.urls'))]).get_schema(
            request=None, public=True)
        stats = doc['paths']['/api/django/agent/evenements/stats/']['get']
        semaines = next(p for p in stats['parameters']
                        if p['name'] == 'semaines')['schema']
        self.assertEqual((semaines['minimum'], semaines['maximum']), (1, 52))
        note = doc['paths']['/api/django/agent/evenements/{id}/note/']['patch']
        self.assertTrue(note['requestBody'].get('required'))
        self.assertIn('"required": ["note"]', json.dumps(note['requestBody']))
        # api-fuzz-full 29/10 : `commentaire` publie le motif sans NUL.
        from core.champs_stricts import MOTIF_SANS_NUL
        self.assertEqual(doc['components']['schemas']['PatchedNoteEvenementRequest'][
            'properties']['commentaire']['pattern'], MOTIF_SANS_NUL)
        for brut in ('0', '53', '-17739'):
            resp = _auth(self.admin).get(self.URL, {'semaines': brut})
            self.assertEqual(resp.status_code, 400, brut)


# ── COP-G4 — libellés des objets nommés dans l'aperçu d'une proposition ──────
URL_LIBELLES = '/api/django/agent/libelles/'
CONTRAT_LIBELLES = json.loads(
    (Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'assistant_libelles.json').read_text(encoding='utf-8'))


class LibellesObjetsTest(TestCase):
    """``GET agent/libelles/`` : le libellé en clair des objets désignés par
    une action ; un objet inconnu, d'une autre société ou hors portée est
    ABSENT (jamais une erreur) ; aucun prix d'achat."""

    def setUp(self):
        from decimal import Decimal

        from django.utils import timezone

        from apps.crm.models import Client, Lead, RelanceEtape
        from apps.ventes.models import Devis, Facture, LigneDevis, LigneFacture

        self.co = Company.objects.create(nom='Lib Co', slug='lib-co')
        self.autre = Company.objects.create(nom='Lib Autre', slug='lib-autre')
        # Rôle restreint à SES enregistrements (SCOPE_SELF des commerciaux).
        role = Role.objects.create(
            company=self.co, nom='Commercial',
            permissions=['crm_voir', 'ventes_voir', 'records_scope_soi'])
        self.moi = User.objects.create_user(
            username='lib_moi', password='x', role=role, company=self.co)
        self.collegue = User.objects.create_user(
            username='lib_col', password='x', role=role, company=self.co)
        self.client_moi = Client.objects.create(
            company=self.co, nom='Benali', prenom='Aziz')
        self.lead = Lead.objects.create(
            company=self.co, nom='Benali', prenom='Aziz', ville='Casablanca',
            owner=self.moi, client=self.client_moi,
            telephone='0612345678', email='aziz@example.com')
        self.lead_collegue = Lead.objects.create(
            company=self.co, nom='Alami', prenom='Sara', owner=self.collegue)
        self.lead_autre = Lead.objects.create(
            company=self.autre, nom='Etranger', prenom='Zed')
        horaire = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        self.touche = RelanceEtape.objects.create(
            company=self.co, lead=self.lead, cadence='contact', ordre=1,
            canal=RelanceEtape.Canal.WHATSAPP, libelle='Relance J+1',
            due_at=horaire, due_date=horaire.date())
        self.touche_collegue = RelanceEtape.objects.create(
            company=self.co, lead=self.lead_collegue, cadence='contact',
            ordre=1, canal=RelanceEtape.Canal.APPEL, libelle='Appel',
            due_at=horaire, due_date=horaire.date())
        self.devis = Devis.objects.create(
            company=self.co, reference='DEV-202611-0045',
            client=self.client_moi, lead=self.lead, created_by=self.moi,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20.00'))
        LigneDevis.objects.create(
            devis=self.devis, designation='Kit', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'))
        self.devis_collegue = Devis.objects.create(
            company=self.co, reference='DEV-202611-0046',
            client=Client.objects.create(company=self.co, nom='Autre'),
            lead=self.lead_collegue, created_by=self.collegue,
            taux_tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.co, reference='FAC-202611-0012',
            client=self.client_moi, devis=self.devis, created_by=self.moi,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, designation='Kit', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))

    def _get(self, user, **params):
        return _auth(user).get(URL_LIBELLES, params)

    @staticmethod
    def _blanc(texte):
        """Espaces fines / insécables -> espace simple (comparaison au contrat)."""
        return ' '.join(texte.replace(' ', ' ').replace('\xa0', ' ').split())

    def test_libelles_au_format_du_contrat(self):
        resp = self._get(self.moi, lead=self.lead.pk, devis=self.devis.pk,
                         touche=self.touche.pk, facture=self.facture.pk,
                         client=self.client_moi.pk)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(set(resp.data), set(CONTRAT_LIBELLES['exemple']))
        corps = {k: self._blanc(v) for k, v in resp.data.items()}
        self.assertEqual(corps['lead'], 'Aziz Benali — Casablanca')
        self.assertEqual(corps['client'], 'Benali Aziz')
        self.assertEqual(
            corps['devis'], 'DEV-202611-0045 — Benali — 1 200,00 MAD TTC (envoyé)')
        self.assertEqual(
            corps['facture'],
            'FAC-202611-0012 — Benali — 1 200,00 MAD TTC, reste dû 1 200,00')
        self.assertEqual(
            corps['touche'],
            'Aziz Benali — Relance J+1 (WhatsApp, prévue le '
            f'{self.touche.due_date:%d/%m/%Y})')

    def test_objet_inconnu_autre_societe_ou_hors_portee_est_absent(self):
        resp = self._get(
            self.moi, lead=self.lead_collegue.pk, touche=self.touche_collegue.pk,
            devis=self.devis_collegue.pk, client=999999)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, CONTRAT_LIBELLES['exemple_hors_portee'])
        resp = self._get(self.moi, lead=self.lead_autre.pk)
        self.assertEqual((resp.status_code, resp.data), (200, {}))

    def test_chacun_voit_ce_que_voit_sa_portee(self):
        resp = self._get(self.collegue, lead=self.lead.pk,
                         devis=self.devis_collegue.pk)
        self.assertNotIn('lead', resp.data)
        self.assertIn('devis', resp.data)

    def test_aucune_donnee_personnelle_ni_prix_achat(self):
        resp = self._get(self.moi, lead=self.lead.pk, devis=self.devis.pk,
                         facture=self.facture.pk)
        texte = json.dumps(resp.data, ensure_ascii=False).lower()
        for interdit in ('0612345678', 'aziz@example.com', 'prix_achat', 'marge'):
            self.assertNotIn(interdit, texte)

    def test_parametres_invalides_400_et_sans_parametre_vide(self):
        for brut in ('abc', '-3', '1.5', '99999999999'):
            self.assertEqual(self._get(self.moi, lead=brut).status_code, 400, brut)
        repete = f'?lead={self.lead.pk}&lead={self.lead.pk}'
        self.assertEqual(_auth(self.moi).get(URL_LIBELLES + repete).status_code, 400)
        resp = self._get(self.moi)
        self.assertEqual((resp.status_code, resp.data), (200, {}))

    def test_authentification_requise(self):
        self.assertIn(APIClient().get(URL_LIBELLES).status_code, (401, 403))
