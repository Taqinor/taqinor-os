"""SPL2 — golden de SCÉNARIO de la surface `crm/services` (capture seule).

L'empreinte AST (SPL1, `tests_services_split_golden`) prouve que les corps
sont identiques ; elle ne prouve pas que les VALEURS rendues, les lignes
écrites et les chatters le sont (un nom résolu vers un autre objet après
déplacement, un import d'en-tête manquant exécuté à froid, un texte
client-visible modifié lui échappent). Ce scénario exécute, de bout en bout et
sans mock (hors transport de notification et horloge), les fonctions de la
chaîne de scission et compare un instantané JSON normalisé.

Règles :
* chaque fonction est résolue PAR NOM via la table de destination du golden
  SPL1 (jamais `services.X`) : ce fichier n'est donc JAMAIS édité pendant la
  chaîne de scission ;
* horloge gelée (`testkit.time.frozen`) à 2026-09-21 10:00 Africa/Casablanca ;
* ids -> ordinaux, datetimes -> ISO local ;
* recapture (réservée à une tâche qui change VOLONTAIREMENT une valeur
  client-visible) : `UPDATE_GOLDEN=1`.
"""
import datetime
import decimal
import importlib
import json
import os
import pathlib
import re
import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import models as dj_models
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.tests_services_split_golden import (
    _chemin_module, charger_golden)
from apps.parametres.models import CompanyProfile
from apps.parametres.models_messages import (
    MESSAGE_TEMPLATE_DEFAULTS, MessageTemplate)
from apps.parametres.models_relance import (
    CADENCES_DEFAUT, CadenceRelanceEtape)

User = get_user_model()

_GOLDEN = (pathlib.Path(__file__).resolve().parent
           / 'golden' / 'services_split_scenario.json')
GEL = datetime.datetime(2026, 9, 21, 10, 0, tzinfo=horaires.CASABLANCA)

Q_SOURCE_EAU = "d'où_vient_l'eau_de_votre_exploitation_?"
Q_ENERGIE_POMPE = 'votre_pompe_actuelle_fonctionne_avec_quelle_énergie_?'
Q_SURFACE_HA = 'combien_d\'hectares_irriguez-vous_?'
Q_DEPENSE = 'combien_dépensez-vous_en_carburant_pour_la_pompe_par_mois_?'

#: ids bruts dans les textes rendus (« #63 », « lead=32 », « /leads/32/ ») :
#: la séquence Postgres n'est pas déterministe d'un run à l'autre.
_MASQUE_IDS = re.compile(r'(#|lead=|/leads?/|/devis/|/clients?/)\d+')

#: Champs volatils ou purement techniques exclus de l'instantané.
_EXCLUS = frozenset({'id', 'password', 'last_login'})


def _fonction(nom):
    """La fonction `nom`, résolue par la table de destination du golden SPL1
    (module cible s'il existe, sinon `services`)."""
    cible = charger_golden()['noms'][nom]['cible']
    module = cible if _chemin_module(cible).exists() else 'services'
    return getattr(importlib.import_module(f'apps.crm.{module}'), nom)


class _Normaliseur:
    """ids -> ordinaux (par modèle, dans l'ordre de première rencontre)."""

    def __init__(self):
        self.ordinaux = {}

    def ordinal(self, modele, pk):
        table = self.ordinaux.setdefault(modele, {})
        return table.setdefault(pk, len(table) + 1)

    def valeur(self, v):
        if isinstance(v, dj_models.Model):
            return f'<{v._meta.label}#{self.ordinal(v._meta.label, v.pk)}>'
        if isinstance(v, datetime.datetime):
            if timezone.is_aware(v):
                v = v.astimezone(horaires.CASABLANCA)
            return v.isoformat()
        if isinstance(v, (datetime.date, datetime.time)):
            return v.isoformat()
        if isinstance(v, decimal.Decimal):
            return str(v)
        if isinstance(v, uuid.UUID):
            return '<uuid>'
        if isinstance(v, dict):
            return {str(k): ('<id>' if isinstance(x, int)
                             and not isinstance(x, bool)
                             and (str(k) in ('id', 'pk', 'lead')
                                  or str(k).endswith('_id'))
                             else self.valeur(x))
                    for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
        if isinstance(v, (list, tuple, set, frozenset)):
            seq = [self.valeur(x) for x in v]
            return sorted(seq, key=json.dumps) if isinstance(
                v, (set, frozenset)) else seq
        if isinstance(v, str):
            return _MASQUE_IDS.sub(r'<id>', v)
        if isinstance(v, (int, float, bool)) or v is None:
            return v
        return f'<{type(v).__name__}> {v!r}'

    def ligne(self, obj, exclus=()):
        out = {}
        for f in obj._meta.concrete_fields:
            if f.name in _EXCLUS or f.name in exclus:
                continue
            brut = getattr(obj, f.attname)
            if f.is_relation and brut is not None:
                out[f.name] = f'<{f.related_model._meta.label}#' \
                              f'{self.ordinal(f.related_model._meta.label, brut)}>'
            else:
                out[f.name] = self.valeur(brut)
        return out


class ScenarioServicesGoldenTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.n = _Normaliseur()
        self.etapes = {}
        self.vus_activites = set()
        self.company = Company.objects.create(
            nom='SPL2 Solaire', slug='spl2-golden')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        for cle, corps in sorted(MESSAGE_TEMPLATE_DEFAULTS.items()):
            MessageTemplate.objects.get_or_create(
                company=self.company, cle=cle, defaults={'corps_fr': corps})
        self.resp = User.objects.create_user(
            username='spl2-resp', password='x', role_legacy='responsable',
            company=self.company, first_name='Meryem')
        self.comm = User.objects.create_user(
            username='spl2-comm', password='x', company=self.company,
            first_name='Hamza')

    # ----------------------------------------------------------------- aides
    def _lead(self, nom, tel, **kw):
        defaults = dict(company=self.company, nom=nom, prenom='Test',
                        stage=stages.NEW, owner=self.resp, telephone=tel,
                        ville='Casablanca')
        defaults.update(kw)
        return Lead.objects.create(**defaults)

    def _etat(self):
        leads = [self.n.ligne(x) for x in Lead.objects.filter(
            company=self.company).order_by('id')]
        etapes = [self.n.ligne(x) for x in RelanceEtape.objects.filter(
            company=self.company).order_by('id')]
        return {'leads': leads, 'relance_etapes': etapes}

    def _nouvelles_activites(self):
        out = []
        for a in LeadActivity.objects.filter(
                lead__company=self.company).order_by('id'):
            if a.pk in self.vus_activites:
                continue
            self.vus_activites.add(a.pk)
            out.append({
                'lead': self.n.valeur(a.lead), 'kind': a.kind,
                'user': a.user.username if a.user_id else None,
                'outcome': a.outcome, 'body': self.n.valeur(a.body)})
        return out

    def _jouer(self, cle, nom, *args, **kwargs):
        """Appelle la fonction `nom` (résolue par nom) et consigne sa valeur
        de retour normalisée, les activités créées et l'état."""
        fn = _fonction(nom)
        try:
            retour = self.n.valeur(fn(*args, **kwargs))
            erreur = None
        except Exception as exc:  # noqa: BLE001 — l'exception EST la valeur
            retour = None
            erreur = f'{type(exc).__name__}: {exc}'
        self.etapes[cle] = {
            'fonction': nom, 'retour': retour, 'erreur': erreur,
            'activites': self._nouvelles_activites(), 'etat': self._etat()}
        return retour

    def _touches(self, lead):
        return list(RelanceEtape.objects.filter(
            lead=lead).order_by('id'))

    @staticmethod
    def _formulaire_residentiel(phone):
        return [
            {'name': 'full_name', 'values': ['Karima Benjelloun']},
            {'name': 'phone_number', 'values': [phone]},
            {'name': 'email', 'values': ['karima@example.test']},
            {'name': 'city', 'values': ['casablanca']},
            {'name': 'quelle_est_votre_facture_délectricité_?',
             'values': ['1500_dh']},
            {'name': 'quand_souhaitez-vous_commencer_?',
             'values': ['dès_que_possible']},
        ]

    @staticmethod
    def _formulaire_agricole(phone):
        return [
            {'name': 'full_name', 'values': ['Fellah Testeur']},
            {'name': 'phone_number', 'values': [phone]},
            {'name': 'city', 'values': ['taroudant']},
            {'name': Q_SOURCE_EAU, 'values': ['un_forage']},
            {'name': Q_ENERGIE_POMPE, 'values': ['butane_(gaz)']},
            {'name': Q_SURFACE_HA, 'values': ['4_ha']},
            {'name': Q_DEPENSE, 'values': ['3000_dh']},
        ]

    # -------------------------------------------------------------- scénario
    def _derouler(self):
        creer = 'create_lead_from_meta_lead_ads'
        resid = self._jouer(
            'meta_residentiel', creer, company=self.company,
            leadgen_id='SPL2-1001',
            field_data=self._formulaire_residentiel('+212661002001'),
            form_id='FORM-RESID', ad_id='AD1', adgroup_id='ADG1',
            created_time=GEL - datetime.timedelta(hours=2),
            origine='Meta Lead Ads (golden)')
        self._jouer(
            'meta_agricole', creer, company=self.company,
            leadgen_id='SPL2-1002',
            field_data=self._formulaire_agricole('+212661002002'),
            form_id='FORM-AGRI-1', origine='Meta Lead Ads (golden)')
        lead_a = Lead.objects.get(external_id='SPL2-1001')
        lead_agri = Lead.objects.get(external_id='SPL2-1002')
        self.assertTrue(resid)

        # Cadence + messages de chaque touche, en fr ET en darija.
        self._jouer('cadence_A', 'demarrer_cadence_contact', lead_a,
                    user=self.resp, origine='golden')
        for i, touche in enumerate(self._touches(lead_a)):
            for langue in ('fr', 'darija'):
                self._jouer(f'message_A_{i}_{langue}', 'message_pour_etape',
                            touche, user=self.resp, langue=langue)

        # Branche A : non joint -> report -> annulation.
        touches = self._touches(lead_a)
        self._jouer('marquer_non_joint', 'marquer_etape_relance',
                    touches[0], self.resp, 'fait', note='Pas de réponse',
                    outcome='non_joint')
        self._jouer('reporter_prochaine_touche', 'reporter_prochaine_touche',
                    lead_a, self.resp, GEL + datetime.timedelta(days=5))
        self._jouer('annuler_touche', 'annuler_touche_relance',
                    RelanceEtape.objects.get(pk=touches[0].pk), self.resp)

        # Branches B (joint) et C (intéressé).
        for cle, tel, outcome in (('B', '+212661002003', 'joint'),
                                  ('C', '+212661002004', 'interesse')):
            lead = self._lead(f'Branche{cle}', tel)
            self._jouer(f'cadence_{cle}', 'demarrer_cadence_contact', lead,
                        user=self.resp, origine='golden')
            touche = self._touches(lead)[0]
            self._jouer(f'marquer_{outcome}', 'marquer_etape_relance',
                        touche, self.resp, 'fait', note=f'Issue {outcome}',
                        outcome=outcome)

        # Réponses : plus tard, question prix, ne plus contacter.
        for cle, tel, fonction, extra in (
                ('plus_tard', '+212661002005', 'repondre_plus_tard',
                 (GEL + datetime.timedelta(days=21),)),
                ('question_prix', '+212661002006', 'repondre_question_prix',
                 ()),
                ('ne_plus_contacter', '+212661002007',
                 'repondre_ne_plus_contacter', ())):
            lead = self._lead(f'Reponse {cle}', tel)
            self._jouer(f'cadence_{cle}', 'demarrer_cadence_contact', lead,
                        user=self.resp, origine='golden')
            touche = self._touches(lead)[0]
            self._jouer(cle, fonction, touche, self.resp, *extra,
                        note='golden')

        # Visite : planifiée puis retour.
        self._jouer('visite_planifiee', 'appliquer_visite_planifiee',
                    lead_a, self.resp, datetime.date(2026, 9, 28), 'Hamza')
        self._jouer('retour_visite', 'appliquer_retour_visite', lead_a,
                    self.resp, {'notes': 'Toiture accessible, 12 panneaux.'},
                    auteur='Hamza')

        # Agricole : mesures du point d'eau, rappel FDA, playbooks.
        self._jouer(
            'mesures_point_eau', 'appliquer_mesures_point_eau', lead_agri,
            {'point_eau': {'niveau_statique_m': 42, 'debit_mesure_m3h': 11},
             'administratif': {'compteur_eau': True}}, self.resp)
        lead_agri.refresh_from_db()
        lead_agri.stage = stages.CONTACTED
        lead_agri.dossier_subvention = Lead.DossierSubvention.ACCORDE
        lead_agri.dossier_subvention_le = datetime.date(2026, 9, 15)
        lead_agri.save()
        self._jouer('rappel_subvention', 'poser_rappel_subvention',
                    lead_agri, self.resp)
        self._jouer('playbooks_pompe', 'rattraper_playbooks_pompe', lead_agri)

        # Action en masse, fusion, client.
        leads = [self._lead('Bulk1', '+212661002008'),
                 self._lead('Bulk2', '+212661002009')]
        self._jouer('bulk_set_stage', 'apply_bulk_action',
                    company=self.company, user=self.resp,
                    lead_ids=[x.pk for x in leads], op='set_stage',
                    params={'stage': stages.QUOTE_SENT})
        absorbe = self._lead('Doublon', '+212661002010')
        survivant = self._lead('Survivant', '+212661002011')
        self._jouer('merge_leads', 'merge_leads', survivant,
                    [absorbe], self.resp)
        survivant.refresh_from_db()
        self._jouer('resolve_client', 'resolve_client_for_lead', survivant)
        self._jouer('placer_anciens_leads', 'placer_anciens_leads',
                    self.company, self.resp, apply=False)

        # Notification (seul transport mocké) + score + devis ouvert.
        with mock.patch('apps.notifications.services.notify_many') as envoi:
            self._jouer('notify_new_lead', 'notify_new_lead', lead_a)
        self.etapes['notify_new_lead']['transport'] = self.n.valeur(
            [(c.args, c.kwargs) for c in envoi.call_args_list])
        self._jouer('recompute_lead_score', 'recompute_lead_score', lead_a)
        self._jouer('noter_devis_ouvert', 'noter_devis_ouvert',
                    'DEV-2026-0001', lead_a)
        return {'version': 1, 'etapes': self.etapes}

    def test_scenario_identique_au_golden(self):
        instantane = self._derouler()
        # Passage par JSON : ce qui est comparé est ce qui est écrit.
        instantane = json.loads(json.dumps(
            instantane, ensure_ascii=False, sort_keys=True))
        if os.environ.get('UPDATE_GOLDEN') == '1':
            _GOLDEN.parent.mkdir(parents=True, exist_ok=True)
            with open(_GOLDEN, 'w', encoding='utf-8') as f:
                json.dump(instantane, f, indent=1, ensure_ascii=False,
                          sort_keys=True)
                f.write('\n')
        with open(_GOLDEN, encoding='utf-8') as f:
            golden = json.load(f)
        self.assertEqual(sorted(instantane['etapes']),
                         sorted(golden['etapes']))
        for cle in sorted(golden['etapes']):
            with self.subTest(etape=cle):
                self.assertEqual(instantane['etapes'][cle],
                                 golden['etapes'][cle])

    def test_toutes_les_fonctions_de_la_liste_sont_appelees(self):
        instantane = self._derouler()
        appelees = {e['fonction'] for e in instantane['etapes'].values()}
        self.assertEqual(appelees, set(FONCTIONS))


FONCTIONS = (
    'create_lead_from_meta_lead_ads', 'demarrer_cadence_contact',
    'message_pour_etape', 'marquer_etape_relance',
    'reporter_prochaine_touche', 'repondre_plus_tard',
    'repondre_question_prix', 'repondre_ne_plus_contacter',
    'annuler_touche_relance', 'appliquer_visite_planifiee',
    'appliquer_retour_visite', 'appliquer_mesures_point_eau',
    'poser_rappel_subvention', 'rattraper_playbooks_pompe',
    'apply_bulk_action', 'merge_leads', 'resolve_client_for_lead',
    'placer_anciens_leads', 'notify_new_lead', 'recompute_lead_score',
    'noter_devis_ouvert')
