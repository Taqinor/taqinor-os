"""Copilote vague 2 (lane CALA) — ce que l'assistant lit et écrit du calepinage.

Nouveau fichier car : aucune suite de l'assistant n'existe dans cette app
(modules neufs ``agent_actions.py``, ``views/assistant.py``,
``services/assistant.py``, ``services/contenance.py``,
``selectors_libelles.py``).

Les formes servies sont comparées aux échantillons COMMITTÉS
(``contrats_assistant.CONTRATS_ASSISTANT``) : un renommage côté vue rougit
ici, pas chez la carte.

Run :
    python manage.py test apps.calepinage.tests.test_assistant -v2
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, override_settings

from apps.agent.registry import LOT_COPILOTE, RISK_INTERNAL
from apps.calepinage.contrats_assistant import CONTRATS_ASSISTANT
from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.permissions import CAL_GERER, CAL_VOIR
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.roles.models import Role

from .test_api_liste import URL, BaseApiCalepinage

User = get_user_model()

DOSSIER_CONTRATS = Path(__file__).resolve().parent.parent / 'contract_samples'


def echantillon(nom, cle='exemple'):
    """L'exemple ``cle`` du contrat ``nom`` (un des CONTRATS_ASSISTANT)."""
    assert nom in CONTRATS_ASSISTANT, nom
    return json.loads((DOSSIER_CONTRATS / nom).read_text(encoding='utf-8'))[cle]


class BaseAssistantCalepinage(BaseApiCalepinage):
    """Un calepinage sur le lead, une variante, un compte restreint « U »."""

    def setUp(self):
        super().setUp()
        self.lead.prenom = 'Karim'
        self.lead.nom = 'Alami'
        self.lead.save(update_fields=['prenom', 'nom'])
        self.cal = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Toit Anfa',
            responsable=self.user, cree_par=self.user)
        self.variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.cal, nom='Paysage')
        role = Role.objects.create(company=self.company, nom='ConcepteurCALA',
                                   permissions=[CAL_VOIR, CAL_GERER])
        self.u = User.objects.create_user(
            username='cala_u', password='x', company=self.company, role=role)
        self.api_u = self._client(self.u)

    def restreindre(self):
        enregistrer_parametres(self.company, {
            'presets': {'vue_restreinte_au_responsable': True}})


class LibellesTest(BaseAssistantCalepinage):
    """CALA1 — ``libelles_calepinage`` : la vue de l'utilisateur, rien d'autre."""

    def _libelles(self, user, **ids):
        from apps.calepinage.selectors_libelles import libelles_calepinage

        return libelles_calepinage(user, **ids)

    def test_reference_puis_nom_du_lead(self):
        sortie = self._libelles(self.user, calepinage=self.cal.pk,
                                variante=self.variante.pk)
        self.assertTrue(sortie['calepinage'].startswith('CAL-'))
        self.assertTrue(sortie['calepinage'].endswith('— Karim Alami'))
        self.assertTrue(sortie['variante'].startswith('« Paysage » (CAL-'))

    def test_autre_societe_ne_voit_rien(self):
        self.assertEqual(self._libelles(self.user_autre, calepinage=self.cal.pk,
                                        variante=self.variante.pk), {})

    def test_identifiant_inconnu_absent(self):
        self.assertEqual(self._libelles(self.user, calepinage=999999,
                                        variante=999999), {})

    def test_vue_restreinte_au_responsable(self):
        self.restreindre()
        self.assertEqual(self._libelles(self.u, calepinage=self.cal.pk,
                                        variante=self.variante.pk), {})
        self.assertIn('calepinage', self._libelles(self.user,
                                                   calepinage=self.cal.pk))

    def test_dispatch_de_l_agent(self):
        from apps.agent.libelles import libelles_objets

        sortie = libelles_objets(self.user, {'calepinage': self.cal.pk,
                                             'variante': self.variante.pk})
        self.assertEqual(set(sortie), {'calepinage', 'variante'})


def _cles(objet):
    """Les clés de tous les niveaux d'un objet JSON (listes traversées)."""
    if isinstance(objet, dict):
        return set(objet) | set().union(*(_cles(v) for v in objet.values()))
    if isinstance(objet, list):
        return set().union(*(_cles(v) for v in objet)) if objet else set()
    return set()


def url_assistant(suffixe, pk=None):
    """``/api/django/calepinage/calepinages/[<pk>/]<suffixe>``."""
    return f'{URL}{pk}/{suffixe}' if pk is not None else f'{URL}{suffixe}'


class PremierBlocageTest(BaseAssistantCalepinage):
    """CALA2 — LA règle ``a_faire``, écrite une fois (ensemble fermé)."""

    def test_ordre_des_gestes(self):
        from apps.calepinage.services.assistant import A_FAIRE, premier_blocage

        cas = (
            ((), 'rien'),
            (('devis_desynchronise',), 'publier'),
            (('bloquant_electrique', 'devis_absent', 'approbation_attendue'),
             'corriger_electrique'),
            (('visite_non_reprise', 'sans_pose'), 'reprendre_visite'),
            (('sans_pose', 'simulation_jamais'), 'dessiner'),
            (('simulation_perimee', 'devis_absent'), 'simuler'),
            (('approbation_perimee', 'devis_absent'), 'faire_approuver'),
        )
        for signaux, attendu in cas:
            with self.subTest(signaux=signaux):
                self.assertEqual(premier_blocage(signaux), attendu)
                self.assertIn(attendu, A_FAIRE)
        self.assertEqual(premier_blocage(('devis_absent',), a_retenir=True),
                         'retenir')
        self.assertEqual(premier_blocage(('sans_pose',), archive=True), 'rien')

    def test_lien_par_la_table_des_ecrans(self):
        from apps.calepinage.services.assistant import lien_du_geste

        self.assertEqual(lien_du_geste(14, 'corriger_electrique'),
                         '/calepinage/14?onglet=verdict-electrique')
        self.assertEqual(lien_du_geste(12, 'publier'), '/calepinage/12')


class ResumeCompactTest(BaseAssistantCalepinage):
    """CALA2 — ``GET calepinages/<pk>/resume/`` : la forme du contrat."""

    def test_forme_exacte_du_contrat(self):
        reponse = self.api.get(url_assistant('resume/', self.cal.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        attendu = echantillon('calepinage_assistant_resume.json')
        self.assertEqual(set(reponse.data), set(attendu))
        for bloc in ('conception', 'simulation', 'production', 'approbation',
                     'visite', 'electrique'):
            self.assertEqual(set(reponse.data[bloc]), set(attendu[bloc]), bloc)
        self.assertEqual(reponse.data['production']['portee'],
                         'etude_technique_interne')
        self.assertEqual(reponse.data['simulation']['etat'], 'jamais')
        self.assertIsNone(reponse.data['production']['p90_kwh'])
        self.assertEqual(reponse.data['a_faire'], 'dessiner')
        self.assertLessEqual(len(json.dumps(reponse.data, ensure_ascii=False)), 1500)

    def test_aucune_cle_interdite(self):
        reponse = self.api.get(url_assistant('resume/', self.cal.pk))
        interdites = {'prix', 'prix_achat', 'marge', 'roof_layout', 'maptilerKey',
                      'telephone', 'nom_client', 'cascade', 'serie'}
        self.assertEqual(_cles(reponse.data) & interdites, set())

    def test_le_contrat_tient_en_1500_caracteres(self):
        for cle in ('exemple', 'exemple_borne_haute'):
            texte = json.dumps(echantillon('calepinage_assistant_resume.json', cle),
                               ensure_ascii=False, separators=(',', ':'))
            self.assertLessEqual(len(texte), 1500, cle)

    def test_borne_haute_masque_le_p90(self):
        from apps.calepinage.services.assistant import _bloc_production

        resultat = {'simule': True, 'simulation_perimee': False, 'pertes': [],
                    'production': {'total': {
                        'p50_kwh': 11200, 'p90_kwh': 10100, 'complete': False,
                        'mention': 'borne haute — 2 pertes non renseignées'}}}
        _simulation, production, _pertes, signaux = _bloc_production(resultat)
        self.assertIsNone(production['p90_kwh'])
        self.assertEqual(production['p50_kwh'], 11200)
        self.assertEqual(signaux, [])
        resultat['production']['total'].update(complete=True, mention='')
        self.assertEqual(_bloc_production(resultat)[1]['p90_kwh'], 10100)

    def test_autre_societe_et_vue_restreinte_404(self):
        url = url_assistant('resume/', self.cal.pk)
        self.assertEqual(self.api_autre.get(url).status_code, 404)
        self.restreindre()
        self.assertEqual(self.api_u.get(url).status_code, 404)

    def test_variante_validee(self):
        url = url_assistant('resume/', self.cal.pk)
        self.assertEqual(self.api.get(url, {'variante': 'x'}).status_code, 400)
        self.assertEqual(self.api.get(url, {'variante': '999999'}).status_code, 404)
        reponse = self.api.get(url, {'variante': str(self.variante.pk)})
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['code'], 'variante_sans_conception')


class DuLeadTest(BaseAssistantCalepinage):
    """CALA3 — ``GET calepinages/du-lead/?lead=`` : l'ouvert, résumé."""

    def test_forme_exacte_avec_calepinage(self):
        reponse = self.api.get(url_assistant('du-lead/'), {'lead': self.lead.pk})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        attendu = echantillon('calepinage_assistant_du_lead.json')
        self.assertEqual(set(reponse.data), set(attendu))
        self.assertEqual(set(reponse.data['visite']), set(attendu['visite']))
        self.assertEqual(reponse.data['calepinage']['calepinage'], self.cal.pk)
        self.assertEqual(set(reponse.data['calepinage']),
                         set(echantillon('calepinage_assistant_resume.json')))
        self.assertEqual(reponse.data['a_faire'], reponse.data['calepinage']['a_faire'])

    def test_sans_calepinage_le_geste_est_creer(self):
        reponse = self.api.get(url_assistant('du-lead/'), {'lead': self.lead_2.pk})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIsNone(reponse.data['calepinage'])
        self.assertEqual(reponse.data['a_faire'], 'creer')
        self.assertEqual(reponse.data['lien'], f'/crm/leads/{self.lead_2.pk}')
        self.assertEqual(set(reponse.data),
                         set(echantillon('calepinage_assistant_du_lead.json',
                                         'exemple_sans_calepinage')))

    def test_parametre_lead_obligatoire(self):
        for valeur in (None, '', 'abc', '-3', '0'):
            with self.subTest(lead=valeur):
                params = {} if valeur is None else {'lead': valeur}
                reponse = self.api.get(url_assistant('du-lead/'), params)
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertEqual(reponse.data['code'], 'lead_invalide')

    def test_lead_d_une_autre_societe_introuvable(self):
        reponse = self.api_autre.get(url_assistant('du-lead/'), {'lead': self.lead.pk})
        self.assertEqual(reponse.status_code, 404, reponse.data)

    def test_ouvert_hors_vue_jamais_nomme(self):
        self.restreindre()
        reponse = self.api_u.get(url_assistant('du-lead/'), {'lead': self.lead.pk})
        # Le lead peut aussi être hors de la portée CRM de U (404) : dans les
        # deux cas, le calepinage de K n'est jamais servi ni nommé.
        self.assertIn(reponse.status_code, (200, 404), reponse.data)
        if reponse.status_code == 200:
            self.assertIsNone(reponse.data['calepinage'])
            self.assertEqual(reponse.data['a_faire'], 'rien')


#: Entrées qu'aucune action de l'assistant ne déclare jamais.
ENTREES_INTERDITES = {'company', 'forcer', 'remplacer', 'derogation_electrique',
                      'taux_tva', 'remise_globale', 'titre'}


class ActionsDeclareesTest(SimpleTestCase):
    """CALA4 — les actions ``calepinage.*`` : lot, garde, entrées, carte."""

    def _actions(self):
        from apps.calepinage import agent_actions

        return {a.key: a for a in agent_actions.ACTIONS}

    def test_lecture_internes_et_gardees_par_calepinage_voir(self):
        actions = self._actions()
        for cle in ('calepinage.du_lead', 'calepinage.resume',
                    'calepinage.variantes_comparer', 'calepinage.simulation_suivre'):
            with self.subTest(action=cle):
                action = actions[cle]
                self.assertEqual(action.method, 'GET')
                self.assertEqual(action.risk, RISK_INTERNAL)
                self.assertEqual(action.required_permission, 'calepinage_voir')
        self.assertEqual(actions['calepinage.du_lead'].carte, 'fiche_calepinage')
        self.assertEqual(actions['calepinage.resume'].carte, 'fiche_calepinage')

    def test_lot_copilote_entrees_et_quatre_sections(self):
        for cle, action in self._actions().items():
            with self.subTest(action=cle):
                self.assertTrue(cle.startswith('calepinage.'))
                self.assertEqual(action.lot, LOT_COPILOTE)
                self.assertTrue(action.as_dict()['natif_seul'])
                proprietes = set((action.inputs or {}).get('properties') or {})
                self.assertEqual(proprietes & ENTREES_INTERDITES, set())
                self.assertFalse(any(p.startswith(('override_', 'derogation'))
                                     for p in proprietes))
                for section in ('Sert à', 'Ne pas utiliser pour', 'Exemple', 'Résultat'):
                    self.assertIn(section, action.description)

    def test_register_actions_idempotent(self):
        from apps.agent import registry
        from apps.calepinage.agent_actions import register_actions

        avant = len(registry.all_actions())
        register_actions()
        register_actions()
        self.assertEqual(len(registry.all_actions()), avant)
        for cle in self._actions():
            self.assertIn(cle, {a.key for a in registry.all_actions()})


@override_settings(ASSISTANT_COPILOTE='tous')
class ActionsServiesTest(BaseAssistantCalepinage):
    """CALA4 — servies copilote allumé, cachées module calepinage éteint (ARC33)."""

    def _cles(self, user):
        from apps.agent import registry

        return {a.key for a in registry.for_user(user)}

    def test_servies_au_porteur_du_droit(self):
        self.assertIn('calepinage.du_lead', self._cles(self.user))

    def test_module_eteint_les_cache(self):
        from core.models import ModuleToggle

        ModuleToggle.objects.create(company=self.company, module='calepinage',
                                    actif=False)
        self.assertNotIn('calepinage.du_lead', self._cles(self.user))

    @override_settings(ASSISTANT_COPILOTE='aucun')
    def test_copilote_eteint_les_cache(self):
        self.assertNotIn('calepinage.du_lead', self._cles(self.user))


class SimulerTest(BaseAssistantCalepinage):
    """CALA5 — ``calepinage.simuler`` : écriture silencieuse, jamais ``forcer``."""

    def test_contrat_de_l_action(self):
        from apps.calepinage.agent_actions import SIMULER

        self.assertEqual((SIMULER.method, SIMULER.risk, SIMULER.required_permission),
                         ('POST', RISK_INTERNAL, 'calepinage_gerer'))
        self.assertEqual(set(SIMULER.inputs['properties']), {'id', 'variante_id'})
        self.assertFalse(SIMULER.lecture)
        self.assertEqual(SIMULER.endpoint, f'{URL}{{id}}/simuler/')

    def test_le_refus_nomme_est_relaye_tel_quel(self):
        """Le corps que le relais envoie (sans ``forcer``) sur un calepinage non
        dessiné : un 409 qui NOMME ce qui manque, jamais un 500."""
        reponse = self.api.post(url_assistant('simuler/', self.cal.pk), {},
                                format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertTrue(set(reponse.data))


class PreparerTest(BaseAssistantCalepinage):
    """CALA6 — ``POST calepinages/preparer/ {lead}`` : un geste, jamais deux ouverts."""

    def _preparer(self, api, corps):
        return api.post(url_assistant('preparer/'), corps, format='json')

    def test_cree_puis_retrouve_le_meme(self):
        premier = self._preparer(self.api, {'lead': self.lead_2.pk})
        self.assertEqual(premier.status_code, 201, premier.data)
        self.assertEqual(set(premier.data),
                         set(echantillon('calepinage_assistant_preparer.json')))
        self.assertTrue(premier.data['cree'])
        self.assertEqual(premier.data['ecran'], 'calepinage')
        self.assertEqual(premier.data['reprise_visite'], 'aucune_visite_validee')
        self.assertTrue(premier.data['chemin'].startswith(
            f"/calepinage/{premier.data['calepinage']}"))
        second = self._preparer(self.api, {'lead': self.lead_2.pk})
        self.assertEqual(second.status_code, 200, second.data)
        self.assertFalse(second.data['cree'])
        self.assertEqual(second.data['calepinage'], premier.data['calepinage'])
        self.assertEqual(Calepinage.objects.filter(
            company=self.company, lead_id=self.lead_2.pk, archive_le__isnull=True).count(), 1)

    def test_l_ouvert_existant_est_rendu(self):
        reponse = self._preparer(self.api, {'lead': self.lead.pk})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['calepinage'], self.cal.pk)

    def test_aucun_autre_champ(self):
        for corps in ({'lead': self.lead.pk, 'remplacer': True},
                      {'lead': self.lead.pk, 'titre': 'Karim'}):
            with self.subTest(corps=corps):
                reponse = self._preparer(self.api, corps)
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertEqual(reponse.data['code'], 'champ_refuse')
        self.assertEqual(self._preparer(self.api, {'lead': 'x'}).status_code, 400)

    def test_autre_societe_introuvable(self):
        reponse = self._preparer(self.api_autre, {'lead': self.lead_2.pk})
        self.assertEqual(reponse.status_code, 404, reponse.data)
        self.assertFalse(Calepinage.objects.filter(lead_id=self.lead_2.pk).exists())

    def test_ouvert_hors_vue_refuse_sans_le_nommer(self):
        self.restreindre()
        reponse = self._preparer(self.api_u, {'lead': self.lead.pk})
        self.assertIn(reponse.status_code, (404, 409), reponse.data)
        if reponse.status_code == 409:
            self.assertEqual(reponse.data['code'], 'calepinage_hors_vue')
            self.assertNotIn('calepinage', reponse.data)


class PublierDevisTest(BaseAssistantCalepinage):
    """CALA7 — aperçu puis publication ; envoyé permis APRÈS confirmation des
    deux totaux (D-W2-Q1), figé refusé, jamais un champ de plus."""

    def _lier(self, statut):
        from apps.ventes.models import Devis

        devis = Devis.objects.create(company=self.company, lead=self.lead,
                                     client=self.client_a, statut=statut,
                                     reference=f'DEV-CALA7-{statut}')
        Calepinage.objects.filter(pk=self.cal.pk).update(devis=devis)
        return devis

    def _poster(self, corps):
        return self.api.post(url_assistant('publier-devis/', self.cal.pk), corps,
                             format='json')

    def test_aucun_autre_champ_que_les_deux_totaux(self):
        reponse = self._poster({'nouveau_total_ttc': '86900.00',
                                'derogation_electrique': {'motif': 'x'}})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertEqual((reponse.data['field'], reponse.data['code']),
                         ('derogation_electrique', 'champ_refuse'))
        self.assertEqual(set(reponse.data), set(echantillon(
            'calepinage_assistant_publier_devis.json', 'exemple_400_champ_refuse')))
        for corps in ({}, {'nouveau_total_ttc': 86900}, {'taux_tva': 10}):
            with self.subTest(corps=corps):
                self.assertEqual(self._poster(corps).status_code, 400)

    def test_devis_fige_refuse_aux_deux_temps(self):
        devis = self._lier('accepte')
        apercu = self.api.get(url_assistant('publier-devis/apercu/', self.cal.pk))
        self.assertEqual(apercu.status_code, 409, apercu.data)
        self.assertEqual(apercu.data['code'], 'devis_fige')
        reponse = self._poster({'ancien_total_ttc': '0.00', 'nouveau_total_ttc': '0.00'})
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['code'], 'devis_fige')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')

    def test_sans_conception_l_apercu_n_ecrit_rien(self):
        from apps.ventes.models import Devis

        avant = Devis.objects.filter(company=self.company).count()
        reponse = self.api.get(url_assistant('publier-devis/apercu/', self.cal.pk))
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(Devis.objects.filter(company=self.company).count(), avant)
        self.cal.refresh_from_db()
        self.assertIsNone(self.cal.devis_id)

    def test_apercu_perime_n_ecrit_rien(self):
        """Le recalcul ne rend pas les totaux vus : la transaction est annulée."""
        from unittest import mock

        from apps.calepinage.services import assistant as service

        devis = self._lier('envoye')
        with mock.patch.object(service, '_refuser_avant_publication', return_value=devis), \
                mock.patch.object(service, '_publier',
                                  return_value=('resynchronise', devis, {})), \
                mock.patch.object(service, '_total_ttc', side_effect=['84500.00', '87300.00']):
            reponse = self._poster({'ancien_total_ttc': '84500.00',
                                    'nouveau_total_ttc': '86900.00'})
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['code'], 'apercu_perime')
        self.assertIn('87', reponse.data['detail'])

    def test_actions_du_flux_en_deux_temps(self):
        from apps.calepinage.agent_actions import PUBLIER_APERCU, PUBLIER_DEVIS

        self.assertEqual((PUBLIER_APERCU.method, PUBLIER_APERCU.risk), ('GET', RISK_INTERNAL))
        self.assertEqual(PUBLIER_DEVIS.risk, 'outward')
        self.assertEqual(PUBLIER_DEVIS.required_permission, 'calepinage_gerer')
        self.assertEqual(set(PUBLIER_DEVIS.inputs['properties']),
                         {'id', 'ancien_total_ttc', 'nouveau_total_ttc'})
        self.assertEqual(PUBLIER_DEVIS.objets, {'id': 'calepinage'})


class RetenirTest(BaseAssistantCalepinage):
    """CALA8 — ``calepinage.retenir`` sur la route existante, confirmé."""

    def test_contrat_de_l_action(self):
        from apps.calepinage.agent_actions import RETENIR

        self.assertEqual((RETENIR.method, RETENIR.risk, RETENIR.required_permission),
                         ('POST', 'outward', 'calepinage_gerer'))
        self.assertEqual(RETENIR.endpoint, f'{URL}{{id}}/variantes/{{variante_id}}/retenir/')
        self.assertEqual(RETENIR.objets, {'id': 'calepinage', 'variante_id': 'variante'})
        self.assertIn('périmée', RETENIR.label)

    def test_variante_sans_conception_refusee_sans_bascule(self):
        reponse = self.api.post(
            url_assistant(f'variantes/{self.variante.pk}/retenir/', self.cal.pk),
            {}, format='json')
        self.assertIn(reponse.status_code, (400, 409), reponse.data)
        self.variante.refresh_from_db()
        self.assertFalse(self.variante.retenue)


class ATraiterTest(BaseAssistantCalepinage):
    """CALA9 — ``GET calepinages/a-traiter/`` et ``selectors.calepinages_a_traiter``."""

    def test_forme_et_signaux_fermes(self):
        from apps.calepinage.services.assistant import A_FAIRE, SIGNAUX

        reponse = self.api.get(url_assistant('a-traiter/'))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        attendu = echantillon('calepinage_assistant_a_traiter.json')
        self.assertEqual(set(reponse.data), set(attendu))
        self.assertEqual(reponse.data['limite'], 10)
        lignes = reponse.data['lignes']
        self.assertEqual([ligne['calepinage'] for ligne in lignes], [self.cal.pk])
        self.assertEqual(set(lignes[0]), set(attendu['lignes'][0]))
        self.assertIn('sans_pose', lignes[0]['signaux'])
        self.assertTrue(set(lignes[0]['signaux']) <= set(SIGNAUX))
        self.assertIn(lignes[0]['a_faire'], A_FAIRE)
        self.assertTrue(lignes[0]['evalue'])

    def test_limite_bornee(self):
        for valeur in ('0', '21', 'x', '-1'):
            with self.subTest(limite=valeur):
                reponse = self.api.get(url_assistant('a-traiter/'), {'limite': valeur})
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertEqual(reponse.data['code'], 'limite_invalide')

    def test_couteux_bornes_aux_premiers_candidats(self):
        from apps.calepinage.services import assistant as service

        for rang in range(service.COUTEUX_MAX + 2):
            Calepinage.objects.create(company=self.company, titre=f'Toit {rang}',
                                      responsable=self.user, cree_par=self.user)
        sortie = service.file_a_traiter(self.user, limite=20)
        evalues = [ligne['evalue'] for ligne in sortie['lignes']]
        self.assertEqual(evalues.count(True), service.COUTEUX_MAX)
        self.assertEqual(sortie['total'], len(sortie['lignes']))

    def test_portee_societe_et_vue_restreinte(self):
        self.assertEqual(self.api_autre.get(url_assistant('a-traiter/')).data['lignes'], [])
        self.restreindre()
        self.assertEqual(self.api_u.get(url_assistant('a-traiter/')).data['lignes'], [])

    def test_le_selecteur_public_rend_la_meme_forme(self):
        from apps.calepinage.selectors import calepinages_a_traiter

        self.assertEqual(set(calepinages_a_traiter(self.user, limite=5)),
                         {'total', 'limite', 'lignes'})


class ContenanceTest(BaseAssistantCalepinage):
    """CALA10 — l'ESTIMATION avant dessin (D-W2-Q3) : étiquetée, jamais écrite."""

    def setUp(self):
        super().setUp()
        self.panneau = self._panneau('Panneau 710', longueur_mm=2384,
                                     largeur_mm=1303, pmax_wc=710)

    def _panneau(self, nom, **fiche):
        from decimal import Decimal

        from apps.stock.models import FicheTechnique, Produit

        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'CALA10-{nom}',
            prix_achat=Decimal('900'), prix_vente=Decimal('1500'), quantite_stock=1)
        FicheTechnique.objects.create(company=self.company, produit=produit,
                                      type_fiche='module', **fiche)
        return produit

    def _estimer(self, api=None, **params):
        return (api or self.api).get(url_assistant('contenance/'), params)

    def _dicte(self, **extra):
        return self._estimer(lead=self.lead_2.pk, origine='dicte', longueur_m='10',
                             largeur_m='6', produit=str(self.panneau.pk), **extra)

    def test_dimensions_dictees_forme_du_contrat_sans_ecriture(self):
        from apps.calepinage.models import CalepinageVersion

        avant = (Calepinage.objects.count(), CalepinageVersion.objects.count())
        reponse = self._dicte(toit_plat='true')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        attendu = echantillon('calepinage_assistant_contenance.json', 'exemple_dicte')
        self.assertEqual(set(reponse.data), set(attendu))
        self.assertEqual(set(reponse.data['zones'][0]), set(attendu['zones'][0]))
        self.assertEqual(set(reponse.data['produit']), set(attendu['produit']))
        zone = reponse.data['zones'][0]
        self.assertEqual(zone['politique'], 'anti_ombrage')
        self.assertLessEqual(zone['modules_min'], zone['modules_max'])
        self.assertTrue(reponse.data['libelle'].startswith('Estimation sur dimensions dictées'))
        self.assertEqual(reponse.data['a_faire'], 'preparer_calepinage')
        self.assertEqual(_cles(reponse.data) & {'prix', 'prix_achat', 'p50_kwh', 'production'},
                         set())
        self.assertEqual((Calepinage.objects.count(), CalepinageVersion.objects.count()), avant)

    def test_toit_plat_espace_les_rangees(self):
        plat = self._dicte(toit_plat='true').data['total']['modules_max']
        en_pente = self._dicte(pente_deg='15').data['total']['modules_max']
        self.assertLess(plat, en_pente)

    def test_fiche_incomplete_refusee_en_la_nommant(self):
        incomplet = self._panneau('Panneau sans cotes', pmax_wc=710)
        reponse = self._estimer(lead=self.lead_2.pk, origine='dicte', longueur_m='10',
                                largeur_m='6', toit_plat='true', produit=str(incomplet.pk))
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['code'], 'fiche_incomplete')

    def test_sans_panneau_designe(self):
        reponse = self._estimer(lead=self.lead_2.pk, origine='dicte', longueur_m='10',
                                largeur_m='6', toit_plat='true')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['code'], 'panneau_non_designe')

    def test_visite_non_validee_et_aucun_trace(self):
        visite = self._estimer(lead=self.lead_2.pk, origine='visite', produit=str(self.panneau.pk))
        self.assertEqual(visite.status_code, 409, visite.data)
        self.assertEqual(set(visite.data), set(echantillon(
            'calepinage_assistant_contenance.json', 'exemple_409_sans_visite')))
        self.assertEqual(visite.data['code'], 'visite_non_validee')
        trace = self._estimer(lead=self.lead_2.pk, origine='trace', produit=str(self.panneau.pk))
        self.assertEqual(trace.status_code, 409, trace.data)
        self.assertEqual(trace.data['code'], 'aucun_trace')

    def test_parametres_refuses_en_les_nommant(self):
        cas = (
            ({'origine': 'dicte', 'longueur_m': '10', 'largeur_m': '6', 'toit_plat': 'true',
              'company': '2'}, 'company'),
            ({'origine': 'visite', 'longueur_m': '10'}, 'longueur_m'),
            ({'origine': 'dicte', 'longueur_m': '900', 'largeur_m': '6', 'toit_plat': 'true'},
             'longueur_m'),
            ({'origine': 'dicte', 'longueur_m': '10', 'largeur_m': '6'}, 'pente_deg'),
            ({'origine': 'satellite'}, 'origine'),
        )
        for params, champ in cas:
            with self.subTest(champ=champ):
                reponse = self._estimer(lead=self.lead_2.pk, **params)
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertEqual(reponse.data['field'], champ)

    def test_lead_d_une_autre_societe_introuvable(self):
        reponse = self._dicte(api=self.api_autre, toit_plat='true')
        self.assertEqual(reponse.status_code, 404, reponse.data)
