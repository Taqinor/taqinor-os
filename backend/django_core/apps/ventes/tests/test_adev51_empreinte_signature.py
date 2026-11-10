"""ADEV51 (C-ADEV-018) — la signature engage l'empreinte du contenu VU.

``proposal_data`` sert ``empreinte_contenu`` (SHA-256 de
``modifiabilite.empreinte_visible``) ; la page la renvoie à ``/accept/`` ; si
le devis a été corrigé SUR PLACE entre la lecture et la signature (D-QJR5-1),
ou si l'empreinte manque, ``/accept/`` répond 409 ``empreinte_perimee`` et
n'écrit rien (sonde VA p12 : accept 200 au nouveau montant).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev51_empreinte_signature -v 2
"""
import json
import uuid
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisActivity, DevisSignature, LigneDevis, ShareLink

CONTRAT_ACCEPT = (Path(__file__).resolve().parent.parent
                  / 'contract_samples' / 'proposal_accept.json')


class EmpreinteSignatureTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='adev51', defaults={'nom': 'adev51'})
        client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV51',
            email='adev51@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ADEV51-0001',
            client=client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='ADEV51-P',
            prix_vente=Decimal('1100'), quantite_stock=50)
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation='Panneau 550W',
            quantite=Decimal('10'), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'))
        # Vocabulaire du classifieur d'options du moteur (réseau) : sans
        # onduleur, la lecture publique refuse le devis (404).
        onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Deye 8kW',
            sku='ADEV51-O', prix_vente=Decimal('14000'), quantite_stock=50)
        LigneDevis.objects.create(
            devis=self.devis, produit=onduleur,
            designation='Onduleur réseau Deye 8kW', quantite=Decimal('1'),
            prix_unitaire=Decimal('14000'), remise=Decimal('0'))
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis, token=str(uuid.uuid4()))
        self.api = APIClient()

    def _lire(self):
        with mock.patch('apps.ventes.public_views._notify_open'):
            resp = self.api.get(
                f'/api/django/public/proposal/{self.link.token}/data/')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return resp.json()

    def _signer(self, empreinte=None):
        corps = {'nom': 'M. Client', 'consent_esign': True}
        if empreinte is not None:
            corps['empreinte_contenu'] = empreinte
        with mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
            return self.api.post(
                f'/api/django/public/proposal/{self.link.token}/accept/',
                corps, format='json')

    def _assert_rien_ecrit(self, resp):
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data['code'], 'empreinte_perimee')
        attendu = json.loads(CONTRAT_ACCEPT.read_text(encoding='utf-8'))
        self.assertEqual(
            resp.data, attendu['reponses_409']['empreinte_perimee'])
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)
        self.assertFalse(
            DevisSignature.objects.filter(devis=self.devis).exists())

    def test_correction_entre_lecture_et_signature_409(self):
        lu = self._lire()
        e0 = lu['empreinte_contenu']
        # Correction SUR PLACE d'un envoyé (D-QJR5-1) : +1 sur une ligne.
        LigneDevis.objects.filter(pk=self.ligne.pk).update(
            quantite=Decimal('11'))
        self.assertNotEqual(self._lire()['empreinte_contenu'], e0)
        self._assert_rien_ecrit(self._signer(e0))
        # CLAUSE PERSISTANCE : relire après le 409 → toujours rien de signé.
        self.assertFalse(self._lire()['accepted'])

    def test_jalons_societe_changes_apres_lecture_409(self):
        """ASOC40 (C-ASOC-040, D-ASOC-1) — un envoyé SANS échéancier propre lit
        les jalons société : lu à 30 %, jalons passés à 40/50/10, signer avec
        l'empreinte lue ⇒ 409, devis envoyé, échéancier nul ; relu ⇒ 200."""
        from apps.parametres.models import CompanyProfile
        e1 = self._lire()['empreinte_contenu']
        profil = CompanyProfile.get(self.company)
        profil.payment_terms = {
            'residentiel': {'acompte': 40, 'materiel': 50, 'solde': 10}}
        profil.save(update_fields=['payment_terms'])
        e2 = self._lire()['empreinte_contenu']
        self.assertNotEqual(e2, e1)
        self._assert_rien_ecrit(self._signer(e1))
        self.assertFalse(self.devis.echeancier)
        resp = self._signer(e2)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_correction_commitee_entre_la_garde_et_le_verrou_409(self):
        """Course : la garde de la vue PASSE (contenu encore identique), puis
        le commercial corrige une ligne AVANT le verrou d'``accept_devis`` —
        l'empreinte re-comparée SOUS le verrou refuse : 409
        ``empreinte_perimee``, rien n'est écrit."""
        from apps.ventes.public import signature_views
        e0 = self._lire()['empreinte_contenu']
        vraie_garde = signature_views._refus_empreinte

        def garde_puis_correction(request, devis, link=None):
            refus = vraie_garde(request, devis, link)
            self.assertIsNone(refus)  # la voie rapide a bien laissé passer
            LigneDevis.objects.filter(pk=self.ligne.pk).update(
                quantite=Decimal('11'))
            return refus

        with mock.patch.object(signature_views, '_refus_empreinte',
                               side_effect=garde_puis_correction):
            self._assert_rien_ecrit(self._signer(e0))

    def test_empreinte_courante_200(self):
        lu = self._lire()
        resp = self._signer(lu['empreinte_contenu'])
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)

    def test_empreinte_absente_409(self):
        self._assert_rien_ecrit(self._signer())

    def test_empreinte_absente_de_la_lecture_quand_rien_n_est_signable(self):
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.ACCEPTE)
        self.assertNotIn('empreinte_contenu', self._lire())

    # ── ADVS25 — l'étude SAISIE entre dans l'empreinte et dans la trace ────

    def test_correction_etude_agricole_change_empreinte_et_trace(self):
        """ADVS25 (C-ADVS-044) — HMT d'un agricole envoyé corrigée : empreinte
        servie neuve, trace « corrigé après envoi : étude », signature à l'ancienne
        empreinte 409 (fixture de la sonde : PVGIS/TMY simulés, patron AGR123)."""
        from django.contrib.auth import get_user_model
        from apps.stock.models import FicheTechnique
        from apps.ventes.domain import pompage
        from apps.ventes.domain.etudes import rafraichir_etudes_du_devis
        co = self.company
        jour = [0] * 6 + [100, 300, 500, 700, 850, 950, 1000, 950, 850, 700, 500, 300, 100] + [0] * 5
        profils = [[g * (0.7 + 0.05 * i) for g in jour] for i in range(12)]

        def produit(nom, **kw):
            return Produit.objects.create(company=co, nom=nom, prix_vente=Decimal('1000'),
                                          prix_achat=Decimal('600'), **kw)
        pompe = produit('Pompe immergée OSP 30/8 7,5 CV 380V', role_pompage='pompe', type_pompe='immergee',
                        alimentation='tri', pompe_kw=Decimal('5.5'), pompe_cv=Decimal('7.5'), tension_v=380,
                        courbe_pompe={'debits_m3h': [0, 12, 24, 30, 36, 39], 'hmt_m': [91, 85, 70, 60, 43, 34]})
        variateur = produit('VARIATEUR VEICHI SI23 5.5KW 380V', role_pompage='variateur_pompage',
                            alimentation='tri', pompe_kw=Decimal('5.5'), tension_v=380)
        FicheTechnique.objects.create(
            company=co, produit=variateur, type_fiche='variateur_pompage', ond_mppt_v_min=Decimal('250'),
            ond_mppt_v_max=Decimal('750'), ond_v_max_abs=Decimal('800'), ond_i_max_mppt_a=Decimal('20'),
            ond_phases=3, var_v_sortie_v=Decimal('380'))
        panneau = produit('Panneau 710W')
        FicheTechnique.objects.create(
            company=co, produit=panneau, type_fiche='module', pmax_wc=Decimal('710'), vmp_v=Decimal('40'),
            voc_v=Decimal('48'), isc_a=Decimal('18'), imp_a=Decimal('17'))
        devis = Devis.objects.create(
            company=co, reference='DEV-ADVS25-0001', client=self.devis.client, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), mode_installation='agricole',
            etude_params={'mode_pompe': 'neuve', 'type_pompe': 'immergee', 'alim': 'tri',
                          'besoin': {'mode': 'volume_declare', 'volume_m3_jour': 135},
                          'hmt_entrees': {'saisie_m': 60},
                          'localisation': {'ville': 'Taroudant', 'lat': 30.47, 'lon': -8.88}})
        for ordre, (article, quantite) in enumerate(((pompe, 1), (variateur, 1), (panneau, 10))):
            LigneDevis.objects.create(devis=devis, produit=article, designation=article.nom,
                                      quantite=Decimal(quantite), prix_unitaire=Decimal('1000'),
                                      remise=Decimal('0'), ordre=ordre)
        api = APIClient()
        api.force_authenticate(get_user_model().objects.create_user(
            username='adev51-admin', password='x', role_legacy='admin', company=co))
        with mock.patch.object(pompage, 'profils_horaires_site', return_value=profils), \
                mock.patch.object(pompage, 'temperatures_du_site', return_value=None), \
                mock.patch('apps.ventes.public_views._notify_open'), \
                mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
            rafraichir_etudes_du_devis(devis)
            Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ENVOYE)
            lien = ShareLink.objects.create(company=co, devis=devis, token=str(uuid.uuid4()))
            donnees = f'/api/django/public/proposal/{lien.token}/data/'
            e1 = self.api.get(donnees).json()['empreinte_contenu']
            resp = api.patch(f'/api/django/ventes/devis/{devis.pk}/etude-params/',
                             {'hmt_entrees': {'saisie_m': 80}}, format='json')
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertNotEqual(self.api.get(donnees).json()['empreinte_contenu'], e1)
            signe = self.api.post(f'/api/django/public/proposal/{lien.token}/accept/',
                                  {'nom': 'M. Agri', 'consent_esign': True, 'empreinte_contenu': e1},
                                  format='json')
        self.assertEqual(signe.status_code, 409, signe.data)
        self.assertEqual(signe.data['code'], 'empreinte_perimee')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertTrue(devis.etude_params.get('resync_apres_envoi'))
        self.assertTrue(DevisActivity.objects.filter(
            devis=devis, field='correction_apres_envoi', new_value__contains='étude').exists())

    def _geste_sur_l_etude(self, **cles):
        """Un geste réel : instantané, écriture sous le propriétaire, fin de geste."""
        from apps.ventes.domain.etude_schema import ecrire
        from apps.ventes.domain.modifiabilite import (
            debut_de_geste_devis, empreinte_contenu_signable, fin_de_geste_devis)
        devis = Devis.objects.get(pk=self.devis.pk)
        avant = debut_de_geste_devis(devis)
        e1 = empreinte_contenu_signable(devis)
        ecrire(devis, **cles)
        trace = fin_de_geste_devis(devis, avant=avant)
        return e1, empreinte_contenu_signable(devis), trace

    def test_factures_reelles_corrigees_tracees_en_residentiel(self):
        """ADVS25 — résidentiel, ``factures_mensuelles_reelles`` : même effet."""
        e1, e2, trace = self._geste_sur_l_etude(factures_mensuelles_reelles=[900] * 12)
        self.assertNotEqual(e1, e2)
        self.assertIsNotNone(trace)
        self.devis.refresh_from_db()
        self.assertTrue(self.devis.etude_params.get('resync_apres_envoi'))

    def test_sortie_du_moteur_ou_attribution_ne_changent_rien(self):
        """ADVS25 — clé dérivée du moteur, attribution : ni empreinte ni trace."""
        from apps.ventes.domain.etude_schema import MOTEUR_HORAIRE
        for cles in ({'proprietaire': MOTEUR_HORAIRE, 'etude_horaire': {'kwh': 1}},
                     {'attribution': {'utm_source': 'facebook'}}):
            e1, e2, trace = self._geste_sur_l_etude(**cles)
            self.assertEqual(e1, e2, cles)
            self.assertIsNone(trace, cles)

    # ── ADEV96 — le sceau couvre les chiffres de l'étude C&I lue ───────────

    @staticmethod
    def _synthese_ci(**energie):
        synthese = {
            'segment': 'commercial', 'statut_etude': 'offre_ferme',
            'systeme': {'kwc': 55, 'production_kwh_an': 95425},
            'energie': {'taux_autoconso_pct': 72.8,
                        'taux_couverture_pct': 46.6},
            'argent': {'base': 'ht',
                       'economie_annee1': {'total_mad': 98933.48},
                       'indicateurs': {'retour_ans': 3, 'tri_pct': 39.8}},
            'hypotheses': [{'cle': 'autoconsommation'}, {'cle': 'tarif'}],
        }
        synthese['energie'].update(energie)
        return synthese

    def test_figures_etude_changent_l_empreinte(self):
        import hashlib
        from apps.ventes.domain.modifiabilite import empreinte_visible
        from apps.ventes.public.signature_views import empreinte_contenu
        base = empreinte_contenu(self.devis, self._synthese_ci())
        self.assertEqual(base,
                         empreinte_contenu(self.devis, self._synthese_ci()))
        self.assertNotEqual(base, empreinte_contenu(
            self.devis, self._synthese_ci(taux_autoconso_pct=80)))
        # Hors C&I (aucune synthèse) : l'empreinte d'avant, à l'octet.
        brut = json.dumps(empreinte_visible(self.devis), sort_keys=True,
                          ensure_ascii=False, default=str)
        self.assertEqual(empreinte_contenu(self.devis),
                         hashlib.sha256(brut.encode('utf-8')).hexdigest())

    def test_correction_de_l_etude_seule_409(self):
        """Une correction de l'étude SEULE (autoconsommation 72,8 → 80 %)
        entre la lecture et la signature ⇒ 409, rien n'est écrit."""
        from apps.ventes.public.signature_views import empreinte_contenu
        cible = 'apps.ventes.domain.modifiabilite.synthese_ci_lue'
        with mock.patch(cible, return_value=self._synthese_ci()):
            lue = empreinte_contenu(self.devis)
        with mock.patch(cible, return_value=self._synthese_ci(
                taux_autoconso_pct=80)):
            self._assert_rien_ecrit(self._signer(lue))
        with mock.patch(cible, return_value=self._synthese_ci()):
            resp = self._signer(lue)
        self.assertEqual(resp.status_code, 200, resp.data)
