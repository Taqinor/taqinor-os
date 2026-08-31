"""NTMOB1 — tests du moteur offline-first généralisé (`apps.offlinesync`).

Couvre le critère d'acceptation du plan : une action CRM créée hors-ligne est
mise en file, puis appliquée UNE SEULE FOIS à la reconnexion — même si le flush
est rejoué deux fois. Plus : société posée serveur (jamais du corps), isolation
multi-société, op_type inconnu, refus journalisé et rejouable après correction,
plafond de lot, journal en lecture seule et scopé.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity

from . import registry, selectors
from .models import OfflineOperation
from .registry import OfflineOpError

User = get_user_model()

BATCH = '/api/django/offlinesync/operations/batch/'
JOURNAL = '/api/django/offlinesync/operations/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def op(client_op_id, op_type, payload):
    return {'client_op_id': client_op_id, 'op_type': op_type, 'payload': payload}


class OfflineSyncBatchTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ofs-a', 'Société A')
        self.co_b = make_company('ofs-b', 'Société B')
        self.user = make_user(self.co_a, 'ofs-resp-a')
        self.autre = make_user(self.co_b, 'ofs-resp-b')
        self.api = auth(self.user)
        self.lead = Lead.objects.create(company=self.co_a, nom='Alaoui')

    def notes(self, lead=None):
        return LeadActivity.objects.filter(
            lead=lead or self.lead, kind=LeadActivity.Kind.NOTE)

    # ── Critère d'acceptation NTMOB1 ────────────────────────────────────────
    def test_note_hors_ligne_appliquee_une_seule_fois_meme_rejouee(self):
        lot = {'ops': [op('cle-1', 'crm.lead.noter',
                          {'lead': self.lead.id, 'body': 'Client rappelé'})]}

        premier = self.api.post(BATCH, lot, format='json')
        self.assertEqual(premier.status_code, 200)
        self.assertEqual(premier.data['applied'], 1)
        self.assertEqual(premier.data['results'][0]['status'], 'applied')
        self.assertEqual(premier.data['results'][0]['module'], 'crm')

        # Rejeu EXACT du même lot (réponse perdue, onglet rechargé…).
        second = self.api.post(BATCH, lot, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['replayed'], 1)
        self.assertEqual(second.data['applied'], 0)
        self.assertEqual(second.data['results'][0]['status'], 'replayed')

        self.assertEqual(self.notes().count(), 1, 'un seul effet métier')
        self.assertEqual(OfflineOperation.objects.filter(
            company=self.co_a, client_op_id='cle-1').count(), 1)
        journal = OfflineOperation.objects.get(client_op_id='cle-1')
        self.assertEqual(journal.statut, OfflineOperation.Statut.APPLIQUEE)
        self.assertEqual(journal.module, 'crm')
        self.assertEqual(journal.user, self.user)
        self.assertIsNotNone(journal.date_traitement)

    def test_note_porte_l_utilisateur_acteur(self):
        self.api.post(BATCH, {'ops': [op('cle-acteur', 'crm.lead.noter',
                                         {'lead': self.lead.id, 'body': 'Hop'})]},
                      format='json')
        note = self.notes().get()
        self.assertEqual(note.user, self.user)
        self.assertEqual(note.body, 'Hop')

    def test_tag_pose_hors_ligne(self):
        resp = self.api.post(BATCH, {'ops': [op('cle-tag', 'crm.lead.tag',
                                                {'lead': self.lead.id,
                                                 'tag': 'chaud'})]},
                             format='json')
        self.assertEqual(resp.data['applied'], 1)
        self.lead.refresh_from_db()
        self.assertIn('chaud', self.lead.tags)

    # ── Multi-tenant ────────────────────────────────────────────────────────
    def test_lead_d_une_autre_societe_est_refuse(self):
        etranger = Lead.objects.create(company=self.co_b, nom='Bennani')
        resp = self.api.post(BATCH, {'ops': [op('cle-x', 'crm.lead.noter',
                                                {'lead': etranger.id,
                                                 'body': 'fuite ?'})]},
                             format='json')
        self.assertEqual(resp.data['errors'], 1)
        self.assertEqual(resp.data['results'][0]['status'], 'error')
        self.assertEqual(resp.data['results'][0]['error'], 'Lead inconnu.')
        self.assertEqual(self.notes(etranger).count(), 0)
        # …et le refus est JOURNALISÉ (rien ne disparaît en silence).
        journal = OfflineOperation.objects.get(client_op_id='cle-x')
        self.assertEqual(journal.statut, OfflineOperation.Statut.REJETEE)
        self.assertEqual(journal.company, self.co_a)

    def test_company_du_corps_est_ignoree(self):
        self.api.post(BATCH, {'company': self.co_b.id,
                              'ops': [op('cle-co', 'crm.lead.noter',
                                         {'lead': self.lead.id,
                                          'company': self.co_b.id,
                                          'body': 'Note'})]},
                      format='json')
        journal = OfflineOperation.objects.get(client_op_id='cle-co')
        self.assertEqual(journal.company, self.co_a)

    def test_meme_cle_dans_deux_societes_ne_collisionne_pas(self):
        lead_b = Lead.objects.create(company=self.co_b, nom='Bennani')
        self.api.post(BATCH, {'ops': [op('cle-partagee', 'crm.lead.noter',
                                         {'lead': self.lead.id, 'body': 'A'})]},
                      format='json')
        auth(self.autre).post(BATCH, {'ops': [op('cle-partagee', 'crm.lead.noter',
                                                 {'lead': lead_b.id, 'body': 'B'})]},
                              format='json')
        self.assertEqual(
            OfflineOperation.objects.filter(client_op_id='cle-partagee').count(), 2)
        self.assertEqual(self.notes().count(), 1)
        self.assertEqual(self.notes(lead_b).count(), 1)

    # ── Robustesse du lot ───────────────────────────────────────────────────
    def test_op_type_inconnu_refuse_sans_interrompre_le_lot(self):
        resp = self.api.post(BATCH, {'ops': [
            op('cle-inconnue', 'crm.lead.teleporter', {'lead': self.lead.id}),
            op('cle-ok', 'crm.lead.noter', {'lead': self.lead.id, 'body': 'Suite'}),
        ]}, format='json')
        self.assertEqual(resp.data['errors'], 1)
        self.assertEqual(resp.data['applied'], 1)
        self.assertIn('op_type inconnu', resp.data['results'][0]['error'])
        self.assertEqual(self.notes().count(), 1)
        # Un op_type inconnu n'invente pas de ligne de journal (rien n'a été tenté).
        self.assertFalse(
            OfflineOperation.objects.filter(client_op_id='cle-inconnue').exists())

    def test_op_refusee_est_rejouable_apres_correction(self):
        refus = self.api.post(BATCH, {'ops': [op('cle-corr', 'crm.lead.noter',
                                                 {'lead': self.lead.id,
                                                  'body': '   '})]},
                              format='json')
        self.assertEqual(refus.data['errors'], 1)
        journal = OfflineOperation.objects.get(client_op_id='cle-corr')
        self.assertEqual(journal.statut, OfflineOperation.Statut.REJETEE)
        self.assertTrue(journal.erreur)

        corrige = self.api.post(BATCH, {'ops': [op('cle-corr', 'crm.lead.noter',
                                                   {'lead': self.lead.id,
                                                    'body': 'Corrigée'})]},
                                format='json')
        self.assertEqual(corrige.data['applied'], 1)
        journal.refresh_from_db()
        self.assertEqual(journal.statut, OfflineOperation.Statut.APPLIQUEE)
        self.assertEqual(journal.erreur, '')
        self.assertEqual(self.notes().count(), 1)

    def test_client_op_id_manquant_refuse(self):
        resp = self.api.post(BATCH, {'ops': [
            {'op_type': 'crm.lead.noter', 'payload': {'lead': self.lead.id,
                                                      'body': 'x'}}]},
            format='json')
        self.assertEqual(resp.data['errors'], 1)
        self.assertEqual(self.notes().count(), 0)

    def test_ops_absent_ou_invalide_repond_400(self):
        self.assertEqual(self.api.post(BATCH, {}, format='json').status_code, 400)
        self.assertEqual(
            self.api.post(BATCH, {'ops': 'nope'}, format='json').status_code, 400)

    def test_lot_trop_grand_refuse(self):
        ops = [op(f'cle-{i}', 'crm.lead.noter',
                  {'lead': self.lead.id, 'body': 'x'}) for i in range(201)]
        resp = self.api.post(BATCH, {'ops': ops}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.notes().count(), 0)

    def test_horodatage_terminal_conserve(self):
        lot = {'ops': [dict(op('cle-h', 'crm.lead.noter',
                               {'lead': self.lead.id, 'body': 'x'}),
                            queued_at='2026-08-10T09:30:00Z')]}
        self.api.post(BATCH, lot, format='json')
        journal = OfflineOperation.objects.get(client_op_id='cle-h')
        self.assertIsNotNone(journal.date_creation)
        self.assertEqual(journal.date_creation.year, 2026)

    def test_anonyme_refuse(self):
        self.assertIn(APIClient().post(BATCH, {'ops': []},
                                       format='json').status_code, (401, 403))


class OfflineOperationJournalTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ofs-j-a', 'Société A')
        self.co_b = make_company('ofs-j-b', 'Société B')
        self.user = make_user(self.co_a, 'ofs-j-resp')
        self.api = auth(self.user)
        OfflineOperation.objects.create(
            company=self.co_a, module='crm', op_type='crm.lead.noter',
            client_op_id='j-a', statut=OfflineOperation.Statut.APPLIQUEE)
        OfflineOperation.objects.create(
            company=self.co_b, module='crm', op_type='crm.lead.noter',
            client_op_id='j-b', statut=OfflineOperation.Statut.REJETEE)

    def rows(self, resp):
        data = resp.data
        return data['results'] if isinstance(data, dict) and 'results' in data else data

    def test_journal_scope_societe(self):
        resp = self.api.get(JOURNAL)
        self.assertEqual(resp.status_code, 200)
        cles = {ligne['client_op_id'] for ligne in self.rows(resp)}
        self.assertEqual(cles, {'j-a'})

    def test_journal_filtre_par_statut(self):
        vide = self.rows(self.api.get(JOURNAL, {'statut': 'rejetee'}))
        self.assertEqual(len(vide), 0)
        plein = self.rows(self.api.get(JOURNAL, {'statut': 'appliquee'}))
        self.assertEqual(len(plein), 1)

    def test_journal_en_lecture_seule(self):
        resp = self.api.post(JOURNAL, {'module': 'crm', 'op_type': 'x',
                                       'client_op_id': 'z'}, format='json')
        self.assertIn(resp.status_code, (403, 405))


class RegistryTests(TestCase):
    def test_module_inconnu_refuse_a_l_enregistrement(self):
        from . import registry

        with self.assertRaises(ValueError):
            registry.register('marketing.campagne.creer', 'marketing', lambda *a: {})
        self.assertIn('crm.lead.noter', registry.registered_op_types())
        self.assertIn('crm', registry.modules_actifs())

    def test_resolveur_facultatif_et_valide(self):
        """NTMOB2 — un resolveur non appelable explose à l'ENREGISTREMENT
        (au démarrage), jamais au milieu d'un lot de synchro."""
        from . import registry

        with self.assertRaises(ValueError):
            registry.register('crm.lead.tag', 'crm', lambda *a: {},
                              resolveur='pas une fonction')
        # Les ops CRM réelles portent bien leur resolveur ; un op_type sans
        # resolveur reste sans garde (comportement NTMOB1).
        self.assertIsNotNone(registry.resolveur('crm.lead.tag'))
        self.assertIsNone(registry.resolveur('crm.lead.teleporter'))


class ConflitDetectionTests(TestCase):
    """NTMOB2 — comparaison de versions, fonction PURE (aucune base)."""

    class _Cible:
        def __init__(self, **champs):
            for k, v in champs.items():
                setattr(self, k, v)

    def test_sans_version_de_base_aucune_garde(self):
        from . import conflicts

        cible = self._Cible(date_modification='2026-08-31T10:00:00+00:00')
        self.assertIsNone(conflicts.detecter(cible, {'lead': 1}))

    def test_versions_identiques_pas_de_conflit(self):
        from . import conflicts

        cible = self._Cible(date_modification='2026-08-31T10:00:00+00:00')
        self.assertIsNone(conflicts.detecter(
            cible, {'base_version': '2026-08-31T10:00:00+00:00'}))

    def test_cible_modifiee_ailleurs_est_un_conflit(self):
        from . import conflicts

        cible = self._Cible(date_modification='2026-08-31T11:30:00+00:00')
        divergence = conflicts.detecter(
            cible, {'base_version': '2026-08-31T10:00:00+00:00'})
        self.assertEqual(divergence['champ'], 'date_modification')
        self.assertEqual(divergence['base'], '2026-08-31T10:00:00+00:00')
        self.assertEqual(divergence['serveur'], '2026-08-31T11:30:00+00:00')

    def test_troncature_des_microsecondes_n_invente_pas_de_conflit(self):
        """Un aller-retour JSON tronque les microsecondes : sans tolérance, un
        terminal parfaitement à jour aurait un faux conflit à CHAQUE op."""
        from . import conflicts

        cible = self._Cible(
            date_modification='2026-08-31T10:00:00.123456+00:00')
        self.assertIsNone(conflicts.detecter(
            cible, {'base_version': '2026-08-31T10:00:00.123Z'}))

    def test_compteur_de_version_entier_supporte(self):
        from . import conflicts

        self.assertIsNone(conflicts.detecter(
            self._Cible(version=7), {'base_version': 7}))
        self.assertEqual(
            conflicts.detecter(self._Cible(version=8),
                               {'base_version': 7})['champ'], 'version')

    def test_cible_sans_champ_de_version_n_invente_rien(self):
        from . import conflicts

        self.assertIsNone(conflicts.detecter(self._Cible(nom='x'),
                                             {'base_version': 'peu importe'}))
        self.assertIsNone(conflicts.detecter(None, {'base_version': 'x'}))


def _h_renommer(company, user, payload):
    """Op de test : renomme le lead par un ``save()`` COMPLET.

    Pourquoi une op dédiée et pas ``crm.lead.tag`` : ``poser_tag_lead``
    enregistre avec ``update_fields=['tags']``, or Django n'écrit alors PAS les
    champs ``auto_now`` — la version du lead ne bouge pas, donc aucune écriture
    concurrente n'est observable. Une modification ORDINAIRE du CRM (save
    complet) la fait bouger : c'est le scénario réel « le même enregistrement a
    été modifié par un autre acteur », et c'est celui qu'il faut éprouver."""
    from apps.crm import selectors as crm_selectors

    lead = crm_selectors.get_company_lead(company, payload.get('lead'))
    if lead is None:
        raise OfflineOpError('Lead inconnu.')
    nom = (payload.get('nom') or '').strip()
    if not nom:
        raise OfflineOpError('Nom vide.')
    lead.nom = nom
    lead.save()
    return {'lead': lead.id, 'nom': lead.nom}


def _resolveur_lead(company, payload):
    from apps.crm import selectors as crm_selectors

    return crm_selectors.get_company_lead(company, payload.get('lead'))


class ConflitSynchroTests(TestCase):
    """NTMOB2 — critère d'acceptation : deux terminaux modifient le MÊME
    enregistrement hors-ligne ; la reconnexion des deux produit EXACTEMENT un
    conflit visible, résolu explicitement — jamais un écrasement silencieux."""

    OP = 'crm.lead.renommer'

    def setUp(self):
        # Le registre est un état de PROCESSUS : on le restaure intégralement
        # en sortie (aucun autre module de test ne voit cette op).
        for cible in (registry._HANDLERS, registry._RESOLVEURS):
            correctif = patch.dict(cible, clear=False)
            correctif.start()
            self.addCleanup(correctif.stop)
        registry.register(self.OP, 'crm', _h_renommer,
                          resolveur=_resolveur_lead)

        self.company = make_company('ofs-c', 'Société Conflit')
        self.user_a = make_user(self.company, 'ofs-c-a')
        self.user_b = make_user(self.company, 'ofs-c-b')
        self.autre_co = make_company('ofs-c-x', 'Société X')
        self.etranger = make_user(self.autre_co, 'ofs-c-x-user')
        self.api_a = auth(self.user_a)
        self.api_b = auth(self.user_b)
        self.lead = Lead.objects.create(company=self.company, nom='Alaoui')
        # La version que les DEUX terminaux ont lue avant de partir en tournée.
        self.base = self.lead.date_modification.isoformat()

    def _renommer(self, api, cle, nom, base=None):
        payload = {'lead': self.lead.id, 'nom': nom}
        if base is not None:
            payload['base_version'] = base
        return api.post(BATCH, {'ops': [op(cle, self.OP, payload)]},
                        format='json')

    def conflits_ouverts(self):
        return selectors.conflits_ouverts(self.company).count()

    # ── Le conflit ──────────────────────────────────────────────────────────
    def test_deux_terminaux_hors_ligne_produisent_exactement_un_conflit(self):
        # Terminal A se reconnecte le premier : sa version EST la base → appliqué.
        premier = self._renommer(self.api_a, 'cle-a', 'Alaoui Karim', self.base)
        self.assertEqual(premier.data['applied'], 1)
        self.assertEqual(premier.data['conflicts'], 0)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.nom, 'Alaoui Karim')

        # Terminal B se reconnecte ensuite avec la MÊME base : le lead a bougé.
        second = self._renommer(self.api_b, 'cle-b', 'Alaoui Samir', self.base)
        self.assertEqual(second.data['conflicts'], 1)
        self.assertEqual(second.data['applied'], 0)
        self.assertEqual(second.data['errors'], 0)
        resultat = second.data['results'][0]
        self.assertEqual(resultat['status'], 'conflict')
        # Message présent AUSSI en `error` : un terminal antérieur à NTMOB2
        # garde l'op dans sa file au lieu de la perdre.
        self.assertTrue(resultat['error'])
        self.assertEqual(resultat['conflit']['base'], self.base)

        # RIEN n'a été écrasé.
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.nom, 'Alaoui Karim')

        journal = OfflineOperation.objects.get(client_op_id='cle-b')
        self.assertEqual(journal.statut, OfflineOperation.Statut.CONFLIT)
        self.assertEqual(journal.conflit['champ'], 'date_modification')
        self.assertEqual(journal.resolution, '')
        self.assertEqual(self.conflits_ouverts(), 1,
                         'exactement un conflit ouvert, visible')

    def test_sans_version_de_base_le_comportement_ntmob1_est_intact(self):
        """La garde est OPT-IN : un terminal qui n'envoie pas sa version
        continue d'appliquer, exactement comme avant NTMOB2."""
        self._renommer(self.api_a, 'cle-n1', 'Alaoui Karim', self.base)
        resp = self._renommer(self.api_b, 'cle-n2', 'Alaoui Samir')  # sans base
        self.assertEqual(resp.data['applied'], 1)
        self.assertEqual(resp.data['conflicts'], 0)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.nom, 'Alaoui Samir')

    def test_la_garde_couvre_aussi_les_ops_crm_reelles(self):
        """`crm.lead.noter` et `crm.lead.tag` déclarent leur resolveur : une
        note mise en file sur une version PÉRIMÉE du lead part en conflit au
        lieu de s'appliquer sur un dossier qu'on n'a pas relu."""
        self._renommer(self.api_a, 'cle-mv', 'Alaoui Karim', self.base)
        resp = self.api_b.post(BATCH, {'ops': [op(
            'cle-note-perimee', 'crm.lead.noter',
            {'lead': self.lead.id, 'body': 'Note', 'base_version': self.base})]},
            format='json')
        self.assertEqual(resp.data['conflicts'], 1)
        self.assertEqual(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE).count(), 0)

    def test_une_version_de_base_illisible_demande_un_arbitrage(self):
        """Dans le doute, on n'écrase pas : une base qu'on ne sait pas comparer
        au texte serveur est traitée comme différente."""
        resp = self._renommer(self.api_a, 'cle-illisible', 'Alaoui Karim',
                              'version-inconnue')
        self.assertEqual(resp.data['conflicts'], 1)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.nom, 'Alaoui')

    def test_une_op_en_conflit_n_est_pas_rejouee_a_l_identique(self):
        """Renvoyer le même lot ne « force » rien : l'op reste en conflit tant
        qu'un humain n'a pas tranché."""
        self._renommer(self.api_a, 'cle-r1', 'Alaoui Karim', self.base)
        self._renommer(self.api_b, 'cle-r2', 'Alaoui Samir', self.base)
        encore = self._renommer(self.api_b, 'cle-r2', 'Alaoui Samir', self.base)
        self.assertEqual(encore.data['conflicts'], 1)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.nom, 'Alaoui Karim')

    # ── L'arbitrage ─────────────────────────────────────────────────────────
    def _en_conflit(self):
        self._renommer(self.api_a, 'cle-base', 'Alaoui Karim', self.base)
        self._renommer(self.api_b, 'cle-conflit', 'Alaoui Samir', self.base)
        return OfflineOperation.objects.get(client_op_id='cle-conflit')

    def _resoudre(self, api, operation, corps):
        return api.post(f'{JOURNAL}{operation.id}/resoudre/', corps,
                        format='json')

    def test_garder_ma_version_applique_explicitement(self):
        operation = self._en_conflit()
        resp = self._resoudre(self.api_b, operation, {'choix': 'mienne'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['resultat']['status'], 'applied')
        operation.refresh_from_db()
        self.assertEqual(operation.statut, OfflineOperation.Statut.APPLIQUEE)
        self.assertEqual(operation.resolution, 'mienne')
        self.assertEqual(operation.resolu_par, self.user_b)
        self.assertIsNotNone(operation.date_resolution)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.nom, 'Alaoui Samir')
        # Le conflit n'est plus OUVERT (il a été tranché, il reste tracé).
        self.assertEqual(self.conflits_ouverts(), 0)

    def test_garder_la_version_du_serveur_n_applique_rien(self):
        operation = self._en_conflit()
        resp = self._resoudre(self.api_b, operation, {'choix': 'serveur'})
        self.assertEqual(resp.status_code, 200)
        operation.refresh_from_db()
        self.assertEqual(operation.statut, OfflineOperation.Statut.REJETEE)
        self.assertEqual(operation.resolution, 'serveur')
        self.assertIn('serveur', operation.erreur.lower())
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.nom, 'Alaoui Karim')
        self.assertEqual(self.conflits_ouverts(), 0)

    def test_fusion_manuelle_applique_le_corps_recompose(self):
        operation = self._en_conflit()
        resp = self._resoudre(self.api_b, operation, {
            'choix': 'fusion',
            'payload': {'lead': self.lead.id, 'nom': 'Alaoui Karim & Samir'}})
        self.assertEqual(resp.status_code, 200)
        operation.refresh_from_db()
        self.assertEqual(operation.resolution, 'fusion')
        self.assertEqual(operation.payload['nom'], 'Alaoui Karim & Samir')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.nom, 'Alaoui Karim & Samir')

    def test_fusion_sans_corps_refusee(self):
        operation = self._en_conflit()
        resp = self._resoudre(self.api_b, operation, {'choix': 'fusion'})
        self.assertEqual(resp.status_code, 400)
        operation.refresh_from_db()
        self.assertEqual(operation.statut, OfflineOperation.Statut.CONFLIT)

    def test_choix_inconnu_refuse(self):
        operation = self._en_conflit()
        resp = self._resoudre(self.api_b, operation, {'choix': 'ecraser-tout'})
        self.assertEqual(resp.status_code, 400)
        operation.refresh_from_db()
        self.assertEqual(operation.statut, OfflineOperation.Statut.CONFLIT)

    def test_une_op_hors_conflit_ne_s_arbitre_pas(self):
        self._renommer(self.api_a, 'cle-ok', 'Alaoui Karim', self.base)
        operation = OfflineOperation.objects.get(client_op_id='cle-ok')
        resp = self._resoudre(self.api_a, operation, {'choix': 'mienne'})
        self.assertEqual(resp.status_code, 400)

    # ── Multi-tenant + permissions ──────────────────────────────────────────
    def test_une_autre_societe_ne_voit_ni_n_arbitre_le_conflit(self):
        operation = self._en_conflit()
        resp = self._resoudre(auth(self.etranger), operation,
                              {'choix': 'mienne'})
        self.assertEqual(resp.status_code, 404)
        operation.refresh_from_db()
        self.assertEqual(operation.statut, OfflineOperation.Statut.CONFLIT)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.nom, 'Alaoui Karim')

    def test_arbitrage_refuse_a_un_anonyme(self):
        operation = self._en_conflit()
        resp = APIClient().post(f'{JOURNAL}{operation.id}/resoudre/',
                                {'choix': 'mienne'}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_le_journal_expose_le_conflit_filtrable(self):
        self._en_conflit()
        resp = self.api_a.get(JOURNAL, {'statut': 'conflit'})
        data = resp.data
        lignes = data['results'] if isinstance(data, dict) and 'results' in data else data
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['statut'], 'conflit')
        self.assertEqual(lignes[0]['conflit']['champ'], 'date_modification')
        self.assertEqual(lignes[0]['resolution'], '')
