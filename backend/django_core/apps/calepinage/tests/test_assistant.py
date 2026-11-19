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
