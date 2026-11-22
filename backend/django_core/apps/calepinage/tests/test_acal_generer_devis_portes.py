"""ACAL89 (C-ACAL-104/106/009) — les portes de « Générer le devis » du module.

* la COPIE d'un calepinage lié ne réutilise jamais le brouillon de
  l'original : un NOUVEAU devis lui est créé (porte PUB-10 : 500 avant) ;
* un double clic rend le MÊME devis (200, ``deduplique``), client seul compris ;
* un calepinage déjà lié à un devis non réutilisable (envoyé, ou brouillon
  d'une autre empreinte) répond 409 NOMMÉ ``{detail, devis, reference,
  revision_possible}`` sans créer de devis ni re-pointer le lien ;
* un lead agricole est refusé 409 ``{type_installation}`` ;
* la réponse porte ``avertissements`` / ``marques_manquantes`` (contrat
  ``calepinage_publication.json``).

Source réelle : ``build_devis_from_layout``, ``lier_devis``,
``devis_brouillon_pour_layout`` et ``devis_modifiabilite`` — aucun mock ;
catalogue semé comme les tests ventes (``seed_catalogue``).
"""
from __future__ import annotations

import copy
from decimal import Decimal
import json
from pathlib import Path

from django.test import SimpleTestCase, TransactionTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.variantes import dupliquer
from apps.crm.models import Client, Lead
from apps.ventes.horaire.conso import CODE_KWH_INCOHERENT, MESSAGE_KWH_INCOHERENT
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'calepinage_publication.json').read_text(encoding='utf-8'))
#: ACAL170 — la réponse de GÉNÉRER porte en plus la clé ``electrique``,
#: publiée par le contrat jumeau ``calepinage_publication_electrique.json``.
CONTRAT_ELECTRIQUE = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'calepinage_publication_electrique.json').read_text(encoding='utf-8'))

TOIT = {
    'areas': [{
        'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
        'obstacles': [],
        'roofType': 'flat',
        'pitch': 10,
        'azimuth': 180,
    }],
    'scenario': 'reseau',
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
}


#: ACAL983 — la liste committée des défauts non saisis (lue aussi par le test web).
DEFAUTS = json.loads(
    (Path(__file__).resolve().parent / 'fixtures' / 'defauts_annonces.json')
    .read_text(encoding='utf-8'))
PORTES_REJOUEES = {'generer_devis', 'pose', 'estimateur'}


def url_generer(pk):
    return f'{url_detail(pk)}generer-devis/'


class DefautsAnnoncesSansBaseTest(SimpleTestCase):
    """ACAL983 — la liste est complète, et l'allée du Terrain n'est jamais
    appliquée sans saisie (saisie : l'entraxe calculé est publié à côté)."""

    def test_chaque_defaut_a_sa_porte_et_sa_reponse(self):
        self.assertTrue(DEFAUTS['defauts'])
        for defaut in DEFAUTS['defauts']:
            self.assertIn(defaut['porte'], PORTES_REJOUEES, defaut['cle'])
            for cle in ('cle', 'valeur_origine', 'cas', 'reponse'):
                self.assertTrue(defaut[cle], f"{defaut['cle']} : « {cle} » vide")

    def test_allee_du_terrain_absente_sans_saisie_annoncee_si_saisie(self):
        from apps.calepinage.moteur_service import politique_du_sol

        from .test_api_pose import _terrain

        lignes = [d for d in DEFAUTS['defauts'] if d['porte'] == 'pose']
        self.assertEqual([d['cle'] for d in lignes], ['allee_terrain'])
        _politique, bloc = politique_du_sol(_terrain(), {'latitude_deg': 30.4})
        self.assertEqual(bloc['politique'], lignes[0]['reponse']['politique'])
        self.assertEqual(bloc['entraxe_applique_m'], bloc['entraxe_calcule_m'])
        _politique, saisie = politique_du_sol(_terrain(0.6), {'latitude_deg': 30.4})
        self.assertEqual(saisie['politique'], 'ALLEE_SAISIE')
        self.assertLess(saisie['entraxe_applique_m'], saisie['entraxe_calcule_m'])


class GenererDevisPortesTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue

        seed_catalogue(self.company)
        # ACAL922 — leads DIMENSIONNÉS (taille souhaitée) : aucune question.
        Lead.objects.filter(pk__in=(self.lead.pk, self.lead_2.pk)).update(
            taille_souhaitee_kwc=Decimal('5'))
        self.original = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL89-A')
        enregistrer_layout(self.original, copy.deepcopy(TOIT), user=self.user)

    def _generer(self, calepinage):
        return self.api.post(url_generer(calepinage.pk), {}, format='json')

    def test_copie_genere_nouveau_devis_sans_500(self):
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        # ACAL187 — source OUVERTE : la copie vise un autre lead.
        copie = dupliquer(self.original, user=self.user,
                          lead_id=self.lead_2.pk)
        # ACON11 — la production de la source ne suit pas une copie vers un
        # autre lead : la copie est re-simulée (ici, résultat reposé).
        self.assertNotIn('result', copie.roof_layout)
        enregistrer_layout(copie, copy.deepcopy(TOIT), user=self.user)

        reponse = self._generer(copie)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertNotEqual(reponse.data['devis'], premier.data['devis'])
        copie.refresh_from_db()
        self.original.refresh_from_db()
        self.assertEqual(copie.devis_id, reponse.data['devis'])
        self.assertEqual(self.original.devis_id, premier.data['devis'])

    def test_double_clic_dedup_meme_devis(self):
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        avant = Devis.objects.filter(company=self.company).count()
        second = self._generer(self.original)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertTrue(second.data['deduplique'])
        self.assertEqual(second.data['devis'], premier.data['devis'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)

    def test_montants_differents_du_brouillon_rendu_409(self):
        """ACON49 — un second POST dédupliqué qui demande une autre TVA ou
        une autre remise : 409 nommant le champ, brouillon inchangé ; sans
        montant, ou le même : 200 ``deduplique``."""
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        devis = Devis.objects.get(pk=premier.data['devis'])
        tva, remise = devis.taux_tva, devis.remise_globale
        url = url_generer(self.original.pk)
        for corps, champ in (({'taux_tva': 10}, 'taux_tva'),
                             ({'remise_globale': 5}, 'remise_globale')):
            with self.subTest(corps=corps):
                reponse = self.api.post(url, corps, format='json')
                self.assertEqual(reponse.status_code, 409, reponse.data)
                self.assertEqual(list(reponse.data), [champ])
                self.assertIn(devis.reference, reponse.data[champ])
        from apps.calepinage.services.devis import _pourcentage_lisible

        self.assertEqual(self.api.post(
            url, {'taux_tva': 10}, format='json').data['taux_tva'],
            f'Le devis {devis.reference} existe déjà à '
            f'{_pourcentage_lisible(tva)} % : changez la TVA depuis le devis.')
        for corps in ({}, {'taux_tva': str(tva)}):
            with self.subTest(corps=corps):
                reponse = self.api.post(url, corps, format='json')
                self.assertEqual(reponse.status_code, 200, reponse.data)
                self.assertTrue(reponse.data['deduplique'])
        devis.refresh_from_db()
        self.assertEqual((devis.taux_tva, devis.remise_globale),
                         (tva, remise))
        self.assertEqual(Devis.objects.filter(
            company=self.company).count(), 1)

    def test_montants_differents_brouillon_reutilisable_409(self):
        """ACON95 — la garde ACON49 sur le chemin « brouillon réutilisable
        NON lié » (``_brouillon_reutilisable``) : autre TVA ou autre remise ⇒
        409 nommant le champ, C non relié, D inchangé ; sans montant ⇒ 200
        ``deduplique`` et C relié à D."""
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        devis = Devis.objects.get(pk=premier.data['devis'])
        tva, remise = devis.taux_tva, devis.remise_globale
        Calepinage.objects.filter(pk=self.original.pk).update(devis=None)
        url = url_generer(self.original.pk)
        for corps, champ in (({'taux_tva': 10}, 'taux_tva'),
                             ({'remise_globale': 5}, 'remise_globale')):
            with self.subTest(corps=corps):
                reponse = self.api.post(url, corps, format='json')
                self.assertEqual(reponse.status_code, 409, reponse.data)
                self.assertEqual(list(reponse.data), [champ])
                self.original.refresh_from_db()
                self.assertIsNone(self.original.devis_id)
        devis.refresh_from_db()
        self.assertEqual((devis.taux_tva, devis.remise_globale),
                         (tva, remise))
        reponse = self.api.post(url, {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['deduplique'])
        self.assertEqual(reponse.data['devis'], devis.pk)
        self.original.refresh_from_db()
        self.assertEqual(self.original.devis_id, devis.pk)

    def test_client_seul_deux_clics_un_devis(self):
        client = Client.objects.create(company=self.company,
                                       nom='Client seul ACAL89')
        seul = Calepinage.objects.create(company=self.company,
                                         client=client, titre='QA-ACAL89-C')
        enregistrer_layout(seul, copy.deepcopy(TOIT), user=self.user)
        # ACAL922 — sans lead, la taille se CONFIRME au premier clic.
        premier = self.api.post(url_generer(seul.pk),
                                CONTRAT['corps_confirmer_taille'], format='json')
        self.assertEqual(premier.status_code, 201, premier.data)
        avant = Devis.objects.filter(company=self.company).count()
        second = self._generer(seul)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data['devis'], premier.data['devis'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)

    def test_lie_envoye_409_nomme_sans_nouveau_devis(self):
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        Devis.objects.filter(pk=premier.data['devis']).update(
            statut=Devis.Statut.ENVOYE)
        avant = Devis.objects.filter(company=self.company).count()

        reponse = self._generer(self.original)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(sorted(reponse.data),
                         sorted(CONTRAT['exemple_409_deja_rattache']))
        self.assertEqual(reponse.data['devis'], premier.data['devis'])
        self.assertIn(premier.data['reference'], reponse.data['detail'])
        self.assertIn('Resynchroniser le devis', reponse.data['detail'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        self.original.refresh_from_db()
        self.assertEqual(self.original.devis_id, premier.data['devis'])

    def test_lie_brouillon_autre_empreinte_409_sans_re_liaison(self):
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        autre = copy.deepcopy(TOIT)
        autre['result'] = dict(autre['result'], panels=10, kwc=5.5)
        autre['areas'][0]['azimuth'] = 170
        enregistrer_layout(self.original, autre, user=self.user)
        avant = Devis.objects.filter(company=self.company).count()

        reponse = self._generer(self.original)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['devis'], premier.data['devis'])
        self.assertIn('revision_possible', reponse.data)
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        self.original.refresh_from_db()
        self.assertEqual(self.original.devis_id, premier.data['devis'])

    def test_lead_ci_marche_du_lead_et_brouillon_d_un_autre_marche_409(self):
        """ACON90 (D-ACON-1) — « Générer le devis » sur un lead industriel :
        devis INDUSTRIEL ; un brouillon RÉSIDENTIEL de même empreinte lié à
        un calepinage d'un lead industriel : 409 ``{devis}`` sans nouveau
        devis ; ``from-layout`` : même refus, texte aussi sous ``detail``."""
        industriel = Lead.objects.create(company=self.company, nom='Usine',
                                         type_installation='industriel')
        c = Calepinage.objects.create(company=self.company,
                                      lead_id=industriel.pk, titre='ACON90-C')
        enregistrer_layout(c, copy.deepcopy(TOIT), user=self.user)
        reponse = self._generer(c)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(Devis.objects.get(pk=reponse.data['devis'])
                         .mode_installation, 'industriel')

        autre = Lead.objects.create(company=self.company, nom='Usine 2',
                                    type_installation='industriel')
        c2 = Calepinage.objects.create(company=self.company,
                                       lead_id=autre.pk, titre='ACON90-C2')
        enregistrer_layout(c2, copy.deepcopy(TOIT), user=self.user)
        c2.refresh_from_db()
        residentiel = Devis.objects.create(
            company=self.company, client=self.client_a, lead=autre,
            reference='DEV-ACON90-1', layout_hash=c2.layout_hash,
            mode_installation='residentiel')
        Calepinage.objects.filter(pk=c2.pk).update(devis=residentiel)
        avant = Devis.objects.filter(company=self.company).count()
        reponse = self._generer(c2)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('DEV-ACON90-1', str(reponse.data['devis']))
        self.assertIn('marché résidentiel', str(reponse.data['devis']))

        Calepinage.objects.filter(pk=c2.pk).update(devis=None)
        reponse = self.api.post(
            '/api/django/ventes/devis/from-layout/',
            {'layout': c2.roof_layout, 'lead': autre.pk}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['detail'], reponse.data['devis'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)

    def test_lead_agricole_409(self):
        agricole = Lead.objects.create(company=self.company,
                                       nom='Ferme Souss',
                                       type_installation='agricole')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=agricole.pk, titre='QA-ACAL89-AGR')
        enregistrer_layout(calepinage, copy.deepcopy(TOIT), user=self.user)
        avant = Devis.objects.filter(company=self.company).count()
        reponse = self._generer(calepinage)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data,
                         CONTRAT['exemple_409_lead_agricole'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        calepinage.refresh_from_db()
        self.assertIsNone(calepinage.devis_id)

    def test_kwh_contredit_par_les_factures_409_aux_deux_portes(self):
        # ADVS26 — 46 kWh/mois pour 10 000 MAD de facture : même refus
        # qu'``/atomic``, rien de créé (règle fondateur du 30/09/2026).
        Lead.objects.filter(pk=self.lead.pk).update(
            conso_mensuelle_kwh=Decimal('46'), facture_hiver=Decimal('10000'))
        reponses = (
            self.api.post('/api/django/ventes/devis/from-layout/',
                          {'layout': copy.deepcopy(TOIT), 'lead': self.lead.pk},
                          format='json'),
            self._generer(self.original))
        for reponse in reponses:
            self.assertEqual(reponse.status_code, 409, reponse.data)
            self.assertEqual(reponse.data['code'], CODE_KWH_INCOHERENT)
            self.assertEqual(reponse.data['detail'], MESSAGE_KWH_INCOHERENT)
        self.assertFalse(Devis.objects.filter(lead_id=self.lead.pk).exists())
        self.original.refresh_from_db()
        self.assertIsNone(self.original.devis_id)

    def test_kwh_coherent_les_deux_portes_creent(self):
        Lead.objects.filter(pk=self.lead.pk).update(
            conso_mensuelle_kwh=Decimal('650'), facture_hiver=Decimal('1200'))
        reponse = self.api.post(
            '/api/django/ventes/devis/from-layout/',
            {'layout': copy.deepcopy(TOIT), 'lead': self.lead.pk}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertIn(self._generer(self.original).status_code, (200, 201))

    def test_devis_genere_range_l_ombrage_servi(self):
        """ACON85 — les études du devis sont rafraîchies APRÈS le lien au
        calepinage : ``calepinage_du_devis`` trouve alors la conception et
        l'ombrage servi entre dans le bloc horaire (mutant : rafraîchir
        avant ``_lier`` ⇒ le dernier rafraîchissement voit un devis nu)."""
        from unittest import mock

        from apps.ventes import services as ventes_services

        vus = []
        reel = ventes_services.rafraichir_etudes_du_devis

        def espion(devis, *args, **kwargs):
            vus.append(Calepinage.objects.filter(devis_id=devis.pk).exists())
            return reel(devis, *args, **kwargs)

        with mock.patch.object(ventes_services, 'rafraichir_etudes_du_devis',
                               side_effect=espion):
            reponse = self._generer(self.original)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertTrue(vus)
        self.assertTrue(vus[-1], vus)

    def test_reponse_porte_avertissements(self):
        reponse = self._generer(self.original)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(sorted(reponse.data),
                         sorted(CONTRAT_ELECTRIQUE['exemple']))
        self.assertTrue(set(CONTRAT['exemple']) <= set(reponse.data))
        # REP-935 — la clé ``electrique`` sert aussi ``etat`` et ``points``.
        self.assertEqual(sorted(reponse.data['electrique']),
                         sorted(CONTRAT_ELECTRIQUE['exemple']['electrique']))
        self.assertEqual(
            sorted(CONTRAT_ELECTRIQUE['exemple_avec_manquantes']['electrique']),
            sorted(CONTRAT_ELECTRIQUE['exemple']['electrique']))
        self.assertIsInstance(reponse.data['avertissements'], list)
        self.assertIsInstance(reponse.data['marques_manquantes'], list)
        second = self._generer(self.original)
        self.assertEqual(sorted(second.data),
                         sorted(set(CONTRAT['exemple_deduplique'])
                                | {'electrique'}))

    def test_hypotheses_toit_non_confirmees_nommees(self):
        """ACAL426 — pan en pente sans source : deux avertissements nommés ;
        avec source : aucun ; toit plat : aucun ; jamais de blocage."""
        def doc(**champs):
            pan = {'id': 'A', 'label': 'A', 'roofType': 'pitched',
                   'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
                   'pitchDeg': 22, 'facingAzimuthDeg': 180, **champs}
            d = copy.deepcopy(TOIT)
            d['zones'] = [pan]
            return d

        from apps.calepinage.services.hypotheses_toit import (
            avertissements_hypotheses)

        self.assertEqual(avertissements_hypotheses(doc()), [
            "Pan « A » : la pente (22°) n'a jamais été confirmée — "
            "confirmez-la avant d'envoyer le devis.",
            "Pan « A » : la face (180°) n'a jamais été confirmée — "
            "confirmez-la avant d'envoyer le devis."])
        self.assertEqual(len(avertissements_hypotheses(
            doc(pitchSource={'mode': 'degres'}))), 1)
        self.assertEqual(avertissements_hypotheses(doc(
            pitchSource={'mode': 'degres'}, facingManual=True)), [])
        self.assertEqual(avertissements_hypotheses(doc(
            pitchSource={'mode': 'degres'},
            facingAzimuthSource='releve')), [])
        self.assertEqual(avertissements_hypotheses(
            doc(roofType='flat')), [])
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL426')
        enregistrer_layout(calepinage, doc(), user=self.user)
        reponse = self._generer(calepinage)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertTrue(any('la pente (22°)' in m
                            for m in reponse.data['avertissements']))
        self.assertTrue(any('la face (180°)' in m
                            for m in reponse.data['avertissements']))

    def test_module_substitue_409_sans_devis(self):
        """ACAL914 — 100 × 720 W dessinés (72,00 kWc) contre un catalogue à
        550 W : 409 ``module_substitue`` nommant les deux kWc, aucun devis
        (mutant : retirer l'appel de la garde ⇒ 201)."""
        doc = copy.deepcopy(TOIT)
        doc['zones'] = [{
            'id': 'A', 'label': 'A', 'roofType': 'flat',
            'vertices': [[0, 0], [30, 0], [30, 20], [0, 20]],
            'geometry': {'count': 100, 'kwc': 72.0, 'azimuthDeg': 180.0,
                         'tiltDeg': 10.0},
            'result': {'count': 100, 'kwc': 72.0}}]
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL914')
        enregistrer_layout(calepinage, doc, user=self.user)
        avant = Devis.objects.filter(company=self.company).count()
        reponse = self._generer(calepinage)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(sorted(reponse.data),
                         sorted(CONTRAT['exemple_409_module_substitue']))
        self.assertEqual(reponse.data['code'], 'module_substitue')
        self.assertEqual(reponse.data['kwc_dessine'], 72.0)
        self.assertNotEqual(reponse.data['kwc_compose'], 72.0)
        self.assertTrue(reponse.data['detail'].startswith(
            'Le dessin porte 72,00 kWc ; le catalogue compose '))
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        calepinage.refresh_from_db()
        self.assertIsNone(calepinage.devis_id)

    def test_acal922_sans_facture_ni_taille_question_puis_201(self):
        """ACAL922 — lead résidentiel sans facture ni taille souhaitée : 409
        ``confirmation_taille`` portant le kWc et le TTC du devis composé,
        aucun devis ; confirmé ⇒ 201 aux MÊMES chiffres (mutant : créer sans
        la garde ⇒ 201 d'emblée, échec)."""
        from core.electrique.types import fr

        nu = Lead.objects.create(company=self.company, nom='Villa sans facture')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=nu.pk, titre='QA-ACAL922')
        enregistrer_layout(calepinage, copy.deepcopy(TOIT), user=self.user)
        avant = Devis.objects.filter(company=self.company).count()
        question = self._generer(calepinage)
        self.assertEqual(question.status_code, 409, question.data)
        self.assertEqual(sorted(question.data),
                         sorted(CONTRAT['exemple_409_confirmation_taille']))
        self.assertEqual((question.data['code'], question.data['champ']),
                         ('confirmation_taille', 'confirmer_taille'))
        self.assertIn('facture', question.data['refus'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        calepinage.refresh_from_db()
        self.assertIsNone(calepinage.devis_id)

        reponse = self.api.post(url_generer(calepinage.pk),
                                CONTRAT['corps_confirmer_taille'], format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        devis = Devis.objects.get(pk=reponse.data['devis'])
        kwc = float(devis.etude_params['puissance_kwc'])
        ttc = Decimal(str(devis.total_ttc)).quantize(Decimal('0.01'))
        self.assertEqual(question.data['kwc'], kwc)
        self.assertEqual(question.data['total_ttc'], str(ttc))
        self.assertEqual(question.data['detail'], (
            'Aucune facture ni taille souhaitée sur le lead : le devis remplit '
            'le toit (%s kWc, %s MAD TTC). Confirmez, ou renseignez la facture '
            'du lead.' % (fr(kwc, 2),
                          f'{ttc:,.2f}'.replace(',', ' ').replace('.', ','))))

    def _cas_sans_facture(self):
        nu = Lead.objects.create(company=self.company, nom='Villa ACAL983')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=nu.pk, titre='QA-ACAL983-taille')
        enregistrer_layout(calepinage, copy.deepcopy(TOIT), user=self.user)
        return calepinage

    def _cas_module_720(self):
        doc = copy.deepcopy(TOIT)
        doc['zones'] = [{
            'id': 'A', 'label': 'A', 'roofType': 'flat',
            'vertices': [[0, 0], [30, 0], [30, 20], [0, 20]],
            'geometry': {'count': 100, 'kwc': 72.0, 'azimuthDeg': 180.0,
                         'tiltDeg': 10.0},
            'result': {'count': 100, 'kwc': 72.0}}]
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL983-module')
        enregistrer_layout(calepinage, doc, user=self.user)
        return calepinage

    def test_acal983_defauts_annonces_jamais_un_prix_sans_question(self):
        """ACAL983 — chaque défaut `generer_devis` de la liste committée rend
        sa question 409 nommée et AUCUN devis (mutant : retirer la garde de
        taille ⇒ 201, échec nommant la clé)."""
        cas = {'taille_sans_facture': self._cas_sans_facture,
               'module_absent_du_catalogue': self._cas_module_720}
        lignes = [d for d in DEFAUTS['defauts'] if d['porte'] == 'generer_devis']
        self.assertEqual(sorted(d['cle'] for d in lignes), sorted(cas))
        for defaut in lignes:
            calepinage = cas[defaut['cle']]()
            avant = Devis.objects.filter(company=self.company).count()
            reponse = self._generer(calepinage)
            attendu = defaut['reponse']
            self.assertEqual((reponse.status_code, reponse.data.get('code')),
                             (attendu['statut'], attendu['code']),
                             f"{defaut['cle']} : {defaut['valeur_origine']} a fixé un devis")
            self.assertEqual(Devis.objects.filter(company=self.company).count(),
                             avant, defaut['cle'])

    def test_acal968_champ_seul_coche_176_resynchro_comprise(self):
        """ACAL968 (D-ACAL-37) — zone 42 + champ au sol 176, seul le champ
        coché ⇒ 176 modules, sélection écrite au devis et relue par la
        resynchro SANS corps ⇒ 176 ; vide ou clé inconnue ⇒ 400 nommant
        ``surfaces_chiffrees``. Mutant : composer tout ⇒ 218 ⇒ rouge."""
        doc = {
            'scenario': 'reseau',
            'zones': [{'id': 'z1', 'label': 'Zone 1', 'roofType': 'flat',
                       'vertices': [[0, 0], [30, 0], [30, 20], [0, 20]],
                       'geometry': {'count': 42, 'kwc': 23.1, 'azimuthDeg': 180.0, 'tiltDeg': 10.0},
                       'result': {'count': 42, 'kwc': 23.1}}],
            'poseSurfaces': [{'id': 's1', 'kind': 'sol', 'label': 'Champ au sol 1', 'moduleWc': 550,
                              'contourM': [[0, 0], [40, 0], [40, 25], [0, 25]], 'areaM2': 1000,
                              'rowAzimuthDeg': 90, 'tiltDeg': 25,
                              'engine': {'modules': 176, 'tables': [], 'rowPitchM': 4.2}}]}
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL968')
        enregistrer_layout(calepinage, doc, user=self.user)
        url = url_generer(calepinage.pk)
        for mauvais in ([], ['inconnue'], 's1'):
            refus = self.api.post(url, {'surfaces_chiffrees': mauvais}, format='json')
            self.assertEqual(refus.status_code, 400, refus.data)
            self.assertEqual(sorted(refus.data), sorted(CONTRAT['exemple_400_surfaces_chiffrees']))
        reponse = self.api.post(url, CONTRAT['corps_surfaces_chiffrees'], format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        devis = Devis.objects.get(pk=reponse.data['devis'])

        def panneaux(devis):
            return sum(int(ligne.quantite) for ligne in devis.lignes.all()
                       if 'panneau' in (ligne.designation or '').lower())
        self.assertEqual(panneaux(devis), 176)
        self.assertEqual(devis.roof_layout['choixConception']['surfacesChiffrees'], ['s1'])
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.roof_layout['zones'][0]['geometry']['count'], 42)  # jamais réécrit
        sync = self.api.post(f'{url_detail(calepinage.pk)}sync-devis/', {}, format='json')
        self.assertEqual(sync.status_code, 200, sync.data)
        devis.refresh_from_db()
        self.assertEqual(panneaux(devis), 176)


class GenererDevisConcurrentTest(TransactionTestCase):
    """ACON46 — deux « Générer le devis » CONCURRENTS sur le même calepinage :
    le verrou de ligne les sérialise, UN devis sur le lead, la seconde rend la
    dédup (``cree`` faux). Deux fils, chacun sa connexion ; la première
    génération est ralentie DANS la création (jamais de barrière qui
    bloquerait sous le verrou)."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        from apps.roles.models import Role
        from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue
        from authentication.models import Company

        self.company = Company.objects.create(nom='ACON46 Co',
                                              slug='acon46-co')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = get_user_model().objects.create_user(
            username='acon46', password='x', company=self.company, role=role)
        self.lead = Lead.objects.create(company=self.company,
                                        nom='Toiture ACON46',
                                        taille_souhaitee_kwc=Decimal('5'))
        seed_catalogue(self.company)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACON46')
        enregistrer_layout(self.calepinage, copy.deepcopy(TOIT),
                           user=self.user)

    def test_deux_generations_concurrentes_un_seul_devis(self):
        import threading
        from unittest import mock

        from django.db import connection

        from apps.calepinage.services.devis import generer_devis
        from apps.ventes.services import build_devis_from_layout as vraie

        dans_la_creation = threading.Event()
        second_lance = threading.Event()
        resultats, erreurs = [], []

        def lente(*args, **kwargs):
            dans_la_creation.set()
            # La seconde génération est lancée PENDANT la création (poignée
            # de main, jamais une attente fixe).
            second_lance.wait(30)
            return vraie(*args, **kwargs)

        def generer(signal=None):
            try:
                if signal is not None:
                    signal.set()
                cal = Calepinage.objects.get(pk=self.calepinage.pk)
                resultats.append(generer_devis(cal, user=self.user,
                                               journal={}))
            except Exception as erreur:  # noqa: BLE001 — remonté par l'assertion
                erreurs.append(erreur)
            finally:
                connection.close()

        with mock.patch('apps.ventes.services.build_devis_from_layout',
                        side_effect=lente):
            premier = threading.Thread(target=generer)
            premier.start()
            self.assertTrue(dans_la_creation.wait(30))
            second = threading.Thread(target=generer,
                                      kwargs={'signal': second_lance})
            second.start()
            premier.join(60)
            second.join(60)

        self.assertEqual(erreurs, [])
        self.assertEqual(sorted(cree for _devis, cree in resultats),
                         [False, True])
        self.assertEqual(Devis.objects.filter(lead=self.lead).count(), 1)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.devis_id, resultats[0][0].pk)
