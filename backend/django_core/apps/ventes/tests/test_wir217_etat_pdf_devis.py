"""WIR217 — l'échec DÉFINITIF d'une génération de PDF de devis est consigné,
lisible, et le sondage du frontend peut enfin s'arrêter.

Le constat : ``task_generate_devis_pdf`` retentait 3 fois puis mourait en
silence. Le sondage de ``DevisList`` ne lisait que ``fichier_pdf`` : il tournait
donc INDÉFINIMENT, en répétant son toast « toujours en cours », et
l'utilisateur n'apprenait jamais qu'il n'y aurait pas de PDF.

Ce module vérifie :
  1. la tâche ne consigne RIEN tant qu'un retry reste (échec transitoire) ;
  2. elle consigne l'échec quand les retries sont épuisés (patron EXPORT_JOB) ;
  3. un rendu réussi — comme une nouvelle demande — PURGE l'échec ;
  4. ``GET /ventes/devis/<id>/etat-pdf/`` rend les trois états, et le PDF prêt
     l'emporte sur un échec plus ancien ;
  5. la réponse a EXACTEMENT la forme de l'exemple de contrat committé
     (``contract_samples/devis_etat_pdf.json``, PACT10) — le même fichier que
     le test frontend importe, donc les deux moitiés ne peuvent plus diverger ;
  6. l'état d'une AUTRE société n'est jamais lisible (404 + garde en profondeur).
"""
import json
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes import tasks as ventes_tasks
from apps.ventes.models import Devis

User = get_user_model()
ECHANTILLON = (Path(__file__).resolve().parent.parent
               / 'contract_samples' / 'devis_etat_pdf.json')


def _contrat(variante='exemple'):
    return json.loads(ECHANTILLON.read_text(encoding='utf-8'))[variante]


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='WIR217 Co')
        self.user = User.objects.create_user(
            username='wir217-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='WIR217',
            telephone='+212600021701')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_obj,
            reference='DEV-WIR217-1')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def url(self, devis=None):
        return f'/api/django/ventes/devis/{(devis or self.devis).pk}/etat-pdf/'


class ConsignationEchecTests(_Base):
    def test_rien_de_consigne_tant_qu_un_retry_reste(self):
        ventes_tasks.consigner_echec_pdf_devis  # présent
        cle = ventes_tasks.pdf_job_cache_key(self.devis.pk)
        self.assertIsNone(cache.get(cle))
        # Un échec TRANSITOIRE est encore « en cours » pour l'utilisateur.
        resp = self.api.get(self.url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'en_cours')

    def test_echec_definitif_consigne_avec_la_societe(self):
        ventes_tasks.consigner_echec_pdf_devis(
            self.devis.pk, ValueError("Aucun onduleur."))
        job = cache.get(ventes_tasks.pdf_job_cache_key(self.devis.pk))
        self.assertEqual(job['status'], 'error')
        self.assertEqual(job['company_id'], self.company.id)
        self.assertIn('onduleur', job['error'])
        self.assertTrue(job['at'])

    def test_un_rendu_reussi_purge_l_echec(self):
        ventes_tasks.consigner_echec_pdf_devis(self.devis.pk, 'boum')
        ventes_tasks.oublier_echec_pdf_devis(self.devis.pk)
        self.assertIsNone(
            cache.get(ventes_tasks.pdf_job_cache_key(self.devis.pk)))

    def test_relancer_la_generation_efface_l_echec(self):
        ventes_tasks.consigner_echec_pdf_devis(self.devis.pk, 'boum')
        with patch('apps.ventes.tasks.task_generate_devis_pdf.delay') as delay:
            delay.return_value.id = 'tache-1'
            resp = self.api.post(
                f'/api/django/ventes/devis/{self.devis.pk}/generer-pdf/',
                {}, format='json')
        self.assertEqual(resp.status_code, 202, resp.data)
        # R1-02/R1-03 — la clé du job désigne désormais la NOUVELLE demande
        # (en cours) : l'échec consigné n'y est plus.
        job = cache.get(ventes_tasks.pdf_job_cache_key(self.devis.pk))
        self.assertEqual(job['status'], 'pending')
        self.assertEqual(job['demande'], resp.data['demande'])
        self.assertEqual(self.api.get(self.url()).data['statut'], 'en_cours')


class StatutPurTests(SimpleTestCase):
    """R1-02/R1-03 — la décision « prêt / en cours / échec », sans base."""

    MAINTENANT = datetime(2026, 11, 22, 3, 0, tzinfo=dt_timezone.utc)

    def _demande(self, statut, minutes=1, erreur=None):
        return {'demande': 'd1', 'status': statut, 'error': erreur,
                'at': (self.MAINTENANT - timedelta(minutes=minutes)).isoformat()}

    def test_un_ancien_fichier_ne_fait_pas_dire_pret_a_une_demande_en_cours(self):
        statut, erreur, _ = ventes_tasks.statut_pdf_devis(
            {}, self._demande('pending'), True, self.MAINTENANT)
        self.assertEqual((statut, erreur), ('en_cours', None))

    def test_demande_rendue_pret(self):
        self.assertEqual(ventes_tasks.statut_pdf_devis(
            {}, self._demande('done'), True, self.MAINTENANT)[0], 'pret')

    def test_echec_de_la_demande_l_emporte_sur_un_ancien_fichier(self):
        statut, erreur, _ = ventes_tasks.statut_pdf_devis(
            {}, self._demande('error', erreur='boum'), True, self.MAINTENANT)
        self.assertEqual((statut, erreur), ('echec', 'boum'))

    def test_demande_jamais_close_se_dit_en_echec_passe_le_delai(self):
        minutes = ventes_tasks.PDF_DEMANDE_DELAI_MAX_S // 60 + 1
        statut, erreur, _ = ventes_tasks.statut_pdf_devis(
            {}, self._demande('pending', minutes=minutes), True,
            self.MAINTENANT)
        self.assertEqual(statut, 'echec')
        self.assertEqual(erreur, ventes_tasks.MSG_DEMANDE_SANS_REPONSE)

    def test_sans_demande_suivie_comportement_wir217(self):
        f = ventes_tasks.statut_pdf_devis
        self.assertEqual(f({}, {}, True, self.MAINTENANT)[0], 'pret')
        self.assertEqual(f({}, {}, False, self.MAINTENANT)[0], 'en_cours')
        self.assertEqual(f({'status': 'error', 'error': 'x'}, {}, False,
                           self.MAINTENANT)[:2], ('echec', 'x'))
        self.assertEqual(f({'status': 'error', 'error': 'x'}, {}, True,
                           self.MAINTENANT)[0], 'pret')


class DemandePdfTests(_Base):
    """R1-02/R1-03 — le fichier remis est celui des options DEMANDÉES."""

    COMPLET = {'pdf_mode': 'full', 'include_etude': True}
    UNE_PAGE = {'pdf_mode': 'onepage'}

    def setUp(self):
        super().setUp()
        # Un ANCIEN rendu « complet » existe déjà (c'est le cas de R1).
        from apps.ventes.quote_engine import clean_pdf_options
        self.devis.fichier_pdf = 'devis/1/DEV-WIR217-1.pdf'
        self.devis.pdf_render_meta = {
            'empreinte': 'e-complet', 'options': clean_pdf_options(self.COMPLET)}
        self.devis.save(update_fields=['fichier_pdf', 'pdf_render_meta'])

    def _demander(self, options):
        with patch('apps.ventes.tasks.task_generate_devis_pdf.delay') as delay:
            delay.return_value.id = 'tache'
            resp = self.api.post(
                f'/api/django/ventes/devis/{self.devis.pk}/generer-pdf/',
                options, format='json')
        self.assertEqual(resp.status_code, 202, resp.data)
        self.assertEqual(delay.call_args.kwargs['demande'], resp.data['demande'])
        return resp.data['demande']

    def _etat(self, demande=None):
        suffixe = f'?demande={demande}' if demande else ''
        return self.api.get(self.url() + suffixe).data

    def _options_servies(self, demande):
        with patch('apps.ventes.quote_engine.cle_pdf_a_jour',
                   return_value='devis/1/DEV-WIR217-1.pdf') as cle, \
                patch('apps.ventes.utils.pdf.download_pdf',
                      return_value=b'%PDF-1.4 r1'):
            resp = self.api.get(
                f'/api/django/ventes/devis/{self.devis.pk}/telecharger-pdf/'
                f'?demande={demande}')
        self.assertEqual(resp.status_code, 200)
        return cle.call_args.args[1]

    def test_une_page_demandee_pas_pret_tant_que_non_rendue_puis_servie(self):
        demande = self._demander(self.UNE_PAGE)
        for etat in (self._etat(demande), self._etat()):
            self.assertEqual(etat['statut'], 'en_cours')
            self.assertFalse(etat['fichier_pdf'])
        ventes_tasks._terminer_demande(self.devis.pk, demande)
        self.assertEqual(self._etat(demande)['statut'], 'pret')
        self.assertEqual(self._options_servies(demande)['pdf_mode'], 'onepage')

    def test_deux_formats_coup_sur_coup_chacun_recoit_le_sien(self):
        complet = self._demander(self.COMPLET)
        une_page = self._demander(self.UNE_PAGE)
        # La SECONDE finit d'abord : la première reste en cours.
        ventes_tasks._terminer_demande(self.devis.pk, une_page)
        self.assertEqual(self._etat(complet)['statut'], 'en_cours')
        self.assertEqual(self._etat(une_page)['statut'], 'pret')
        ventes_tasks._terminer_demande(self.devis.pk, complet)
        servi = self._options_servies(complet)
        self.assertEqual((servi['pdf_mode'], servi['include_etude']),
                         ('full', True))
        self.assertEqual(self._options_servies(une_page)['pdf_mode'],
                         'onepage')

    def test_echec_d_une_demande_ne_touche_pas_l_autre(self):
        premiere = self._demander(self.COMPLET)
        seconde = self._demander(self.UNE_PAGE)
        ventes_tasks.consigner_echec_pdf_devis(
            self.devis.pk, 'boum', demande=premiere)
        self.assertEqual(self._etat(premiere)['statut'], 'echec')
        self.assertEqual(self._etat(premiere)['erreur'], 'boum')
        self.assertEqual(self._etat(seconde)['statut'], 'en_cours')
        # Une tâche d'avant le correctif (sans demande) n'écrase pas non plus
        # la dernière demande en cours.
        ventes_tasks.consigner_echec_pdf_devis(self.devis.pk, 'ancienne')
        self.assertEqual(self._etat()['statut'], 'en_cours')

    def test_rendu_impossible_jamais_l_ancien_format_a_la_place(self):
        demande = self._demander(self.UNE_PAGE)
        ventes_tasks._terminer_demande(self.devis.pk, demande)
        with patch('apps.ventes.quote_engine.cle_pdf_a_jour',
                   side_effect=RuntimeError('moteur indisponible')), \
                patch('apps.ventes.utils.pdf.download_pdf',
                      return_value=b'%PDF-1.4 ancien') as lecture:
            resp = self.api.get(
                f'/api/django/ventes/devis/{self.devis.pk}/telecharger-pdf/'
                f'?demande={demande}')
        self.assertEqual(resp.status_code, 409)
        lecture.assert_not_called()

    def test_la_tache_clot_sa_demande_au_saut_d_idempotence(self):
        demande = self._demander(self.UNE_PAGE)
        with patch('apps.ventes.tasks._idempotent_cached_key',
                   return_value='devis/1/DEV-WIR217-1.pdf'):
            resultat = ventes_tasks.task_generate_devis_pdf.apply(
                args=[self.devis.pk, self.UNE_PAGE],
                kwargs={'demande': demande})
        self.assertTrue(resultat.successful(), resultat.traceback)
        self.assertEqual(self._etat(demande)['statut'], 'pret')

    def test_aucun_statut_ecrit(self):
        statut = self.devis.statut
        demande = self._demander(self.UNE_PAGE)
        ventes_tasks._terminer_demande(self.devis.pk, demande)
        self._options_servies(demande)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, statut)


class EtatPdfEndpointTests(_Base):
    def test_en_cours_par_defaut(self):
        resp = self.api.get(self.url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'en_cours')
        self.assertFalse(resp.data['fichier_pdf'])
        self.assertIsNone(resp.data['erreur'])
        self.assertIsNone(resp.data['date'])

    def test_echec_expose_le_message_du_serveur(self):
        ventes_tasks.consigner_echec_pdf_devis(
            self.devis.pk, "Aucune option de ce devis ne porte d'onduleur")
        resp = self.api.get(self.url())
        self.assertEqual(resp.data['statut'], 'echec')
        self.assertIn('onduleur', resp.data['erreur'])
        self.assertTrue(resp.data['date'])

    def test_pdf_pret_l_emporte_sur_un_echec_plus_ancien(self):
        ventes_tasks.consigner_echec_pdf_devis(self.devis.pk, 'ancien')
        self.devis.fichier_pdf = 'devis/1/DEV-WIR217-1.pdf'
        self.devis.save(update_fields=['fichier_pdf'])
        resp = self.api.get(self.url())
        self.assertEqual(resp.data['statut'], 'pret')
        self.assertTrue(resp.data['fichier_pdf'])
        self.assertIsNone(resp.data['erreur'])

    # ── PACT10 — la forme EXACTE de l'exemple committé ───────────────────────
    def test_forme_identique_a_l_exemple_de_contrat(self):
        ventes_tasks.consigner_echec_pdf_devis(self.devis.pk, 'boum')
        resp = self.api.get(self.url())
        self.assertEqual(
            sorted(resp.data.keys()), sorted(_contrat().keys()))
        self.assertEqual(resp.data['statut'], _contrat()['statut'])

    def test_les_trois_variantes_du_contrat_ont_la_meme_forme(self):
        reference = sorted(_contrat().keys())
        for variante in ('exemple', 'exemple_pret', 'exemple_en_cours'):
            self.assertEqual(
                sorted(_contrat(variante).keys()), reference, variante)

    def test_etat_pret_identique_a_la_variante_du_contrat(self):
        self.devis.fichier_pdf = 'devis/1/DEV-WIR217-1.pdf'
        self.devis.save(update_fields=['fichier_pdf'])
        resp = self.api.get(self.url())
        attendu = _contrat('exemple_pret')
        self.assertEqual(resp.data['statut'], attendu['statut'])
        self.assertEqual(resp.data['fichier_pdf'], attendu['fichier_pdf'])
        self.assertEqual(resp.data['erreur'], attendu['erreur'])


class IsolationTests(_Base):
    def test_devis_d_une_autre_societe_404(self):
        autre = Company.objects.create(nom='WIR217 Autre')
        autre_user = User.objects.create_user(
            username='wir217-autre', password='x', role_legacy='responsable',
            company=autre)
        api = APIClient()
        api.force_authenticate(autre_user)
        self.assertEqual(api.get(self.url()).status_code, 404)

    def test_un_job_d_une_autre_societe_est_ignore(self):
        # Défense en profondeur : même si une clé venait à porter une société
        # étrangère, l'endpoint ne la relaie JAMAIS.
        cache.set(ventes_tasks.pdf_job_cache_key(self.devis.pk), {
            'company_id': self.company.id + 9999,
            'status': 'error', 'error': 'fuite', 'at': '2026-01-01T00:00:00Z',
        }, 60)
        resp = self.api.get(self.url())
        self.assertEqual(resp.data['statut'], 'en_cours')
        self.assertIsNone(resp.data['erreur'])
