"""CIQ319 — acceptation entreprise côté serveur : raison sociale, qualité du
signataire et ICE enregistrés AVEC la signature ; ICE exigé en ligne pour un
devis commercial ou industriel (D-CIQ-11, contrat ``acceptation_entreprise.json``).

Chemin RÉEL : POST public ``/api/django/public/proposal/<token>/accept/`` ;
le PDF signé (WeasyPrint + MinIO) est neutralisé comme dans
``test_nplus1_acceptation_publique``. Aucun statut nouveau (règle #4).
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = json.loads(
    (Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'acceptation_entreprise.json').read_text(encoding='utf-8'))
ENTREPRISE = dict(CONTRAT['exemple']['entreprise'])


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class AcceptationEntreprise(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CIQ319 Co')
        self.seller = User.objects.create_user(
            username='ciq319_seller', password='x', role_legacy='commercial',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Hôtel Exemple', prenom='',
            email='ciq319@example.test', telephone='+212600000319')
        self.api = APIClient()
        self.n = 0

    def _devis(self, mode='commercial'):
        from apps.stock.models import Produit
        self.n += 10
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-C3{self.n:03d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.seller,
            mode_installation=mode)
        for i, (nom, qte) in enumerate((
                ('Panneau Canadien Solar 710W', '10'),
                ('Onduleur réseau Huawei 10kW Triphasé', '1'),
                ('Installation', '1'))):
            produit = Produit.objects.create(
                company=self.company, nom=nom, sku=f'C319-{self.n}-{i}',
                prix_vente=Decimal('1000'), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal('1000'),
                remise=Decimal('0'))
        return devis

    def _post(self, devis, entreprise=None):
        from apps.ventes.public.signature_views import empreinte_contenu
        link = ShareLink.for_devis(devis)
        # ADEV51 — le corps renvoie l'empreinte du contenu lu.
        corps = {'nom': 'Karim Exemple', 'consent_esign': True,
                 'empreinte_contenu': empreinte_contenu(devis)}
        if entreprise is not None:
            corps['entreprise'] = entreprise
        with patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
            return self.api.post(
                f'/api/django/public/proposal/{link.token}/accept/',
                corps, format='json')

    def test_ci_sans_ice_400_et_devis_non_accepte(self):
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode):
                devis = self._devis(mode)
                resp = self._post(devis, dict(ENTREPRISE, ice=''))
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(resp.data['champ'], 'entreprise.ice')
                devis.refresh_from_db()
                self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
                self.assertFalse(
                    DevisSignature.objects.filter(devis=devis).exists())

    def test_ci_etude_illisible_409_validation_requise_rien_ecrit(self):
        """C (revue du 24/10/2026) — REFUS FERMÉ : l'étude C&I ne se lit pas
        à l'acceptation ⇒ 409 ``validation_requise`` (message client), aucune
        signature, le devis reste « envoyé » — jamais un sceau C&I sans son
        étude en silence."""
        from apps.ventes.domain.cycle_vie import ETUDE_ILLISIBLE_REFUS
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode):
                devis = self._devis(mode)
                # Le refus fermé ne vaut que pour un devis qui PORTE une étude.
                Devis.objects.filter(pk=devis.pk).update(
                    etude_params={'etude_ci': {'statut': 'ok', 'kwc': 10}})
                with patch('apps.ventes.quote_engine.ci.synthese.synthese_ci',
                           side_effect=RuntimeError('moteur C&I en panne')):
                    resp = self._post(devis, ENTREPRISE)
                self.assertEqual(resp.status_code, 409, resp.data)
                self.assertEqual(resp.data, {
                    'detail': ETUDE_ILLISIBLE_REFUS,
                    'code': 'validation_requise'})
                devis.refresh_from_db()
                self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
                self.assertFalse(
                    DevisSignature.objects.filter(devis=devis).exists())

    def test_ci_sans_etude_s_accepte_sans_refus_ferme(self):
        """CI #1022 — un devis C&I composé à la main, SANS étude
        (``etude_params`` sans ``etude_ci``), s'accepte comme avant : aucun
        refus fermé, signature enregistrée, sceau sans chiffres d'étude."""
        devis = self._devis('commercial')
        with patch('apps.ventes.quote_engine.ci.synthese.synthese_ci',
                   side_effect=RuntimeError('moteur C&I en panne')):
            resp = self._post(devis, ENTREPRISE)
        self.assertEqual(resp.status_code, 200, resp.data)
        sig = DevisSignature.objects.get(devis=devis)
        self.assertTrue(sig.content_hash)
        self.assertFalse((sig.figures_scellees or {}).get('etude'))

    def test_ci_signature_porte_ses_chiffres_scelles(self):
        """C — la signature C&I stocke les chiffres de l'étude scellés."""
        devis = self._devis('commercial')
        resp = self._post(devis, ENTREPRISE)
        self.assertEqual(resp.status_code, 200, resp.data)
        sig = DevisSignature.objects.get(devis=devis)
        self.assertIn('etude', sig.figures_scellees)
        self.assertEqual(sig.verifier_contenu(),
                         (True, DevisSignature.CONTENT_HASH_V3))

    def test_ci_bloc_absent_nomme_le_premier_champ(self):
        resp = self._post(self._devis())
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['champ'], 'entreprise.raison_sociale')

    def test_ice_mal_forme_400(self):
        resp = self._post(self._devis(), dict(ENTREPRISE, ice='12AB'))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['champ'], 'entreprise.ice')

    def test_ci_trois_champs_signature_et_rendu(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('industriel')
        resp = self._post(devis, ENTREPRISE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], Devis.Statut.ACCEPTE)
        self.assertEqual(resp.data['entreprise'], ENTREPRISE)
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual(sig.raison_sociale, ENTREPRISE['raison_sociale'])
        self.assertEqual(sig.signataire_qualite,
                         ENTREPRISE['signataire_qualite'])
        self.assertEqual(sig.ice_declare, ENTREPRISE['ice'])
        devis.refresh_from_db()
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        attendu = CONTRAT['signature_entreprise']['exemple']
        self.assertEqual(set(data['signature_entreprise']), set(attendu))
        self.assertEqual(data['signature_entreprise']['ice'],
                         ENTREPRISE['ice'])
        self.assertEqual(data['signature_entreprise']['signataire_nom'],
                         'Karim Exemple')

    def test_texte_echappe_une_seule_fois(self):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, echapper_textes_client,
        )
        devis = self._devis()
        self._post(devis, dict(ENTREPRISE, raison_sociale='A & <B> SARL'))
        devis.refresh_from_db()
        rendu = echapper_textes_client(
            build_quote_data(devis, {'pdf_mode': 'full'}))
        self.assertEqual(rendu['signature_entreprise']['raison_sociale'],
                         'A &amp; &lt;B&gt; SARL')

    def test_ice_different_deja_present_divergence(self):
        """ADEV95 — un ICE différent de celui du Client n'est plus accepté en
        silence : 409 ``ice_divergent`` qui nomme les deux, rien n'est écrit."""
        from apps.ventes.domain.cycle_vie import divergence_ice
        self.client_obj.ice = '111111111111111'
        self.client_obj.save(update_fields=['ice'])
        devis = self._devis()
        resp = self._post(devis, ENTREPRISE)
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(set(resp.data), {'detail', 'code'})
        self.assertEqual(resp.data['code'], 'ice_divergent')
        self.assertIn('111111111111111', resp.data['detail'])
        self.assertIn(ENTREPRISE['ice'], resp.data['detail'])
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertFalse(DevisSignature.objects.filter(devis=devis).exists())
        self.client_obj.refresh_from_db()
        # Jamais écrasé.
        self.assertEqual(self.client_obj.ice, '111111111111111')
        self.assertTrue(divergence_ice(devis, ENTREPRISE['ice']))
        self.assertFalse(divergence_ice(devis, '111111111111111'))
        # Le même ICE que celui du Client passe.
        resp = self._post(devis, dict(ENTREPRISE, ice='111111111111111'))
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_cprs7_ice_compare_et_stocke_normalise(self):
        """CPRS7 — « 001-234… » et « 001234… » sont le même ICE : aucun
        faux 409, et la signature garde la forme canonique."""
        from apps.ventes.domain.cycle_vie import divergence_ice
        canon = ENTREPRISE['ice']
        tirets = '-'.join((canon[:3], canon[3:9], canon[9:]))
        self.client_obj.ice = tirets
        self.client_obj.save(update_fields=['ice'])
        devis = self._devis()
        self.assertFalse(divergence_ice(devis, canon))
        resp = self._post(devis, dict(ENTREPRISE, ice=f'ICE {tirets}'))
        self.assertEqual(resp.status_code, 200, resp.data)
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual(sig.ice_declare, canon)

    def test_signataire_b2b_exige_email_pouvoir_et_nom(self):
        """ADEV95 — lien public C&I : e-mail valide, attestation de pouvoir
        (booléen vrai) et nom = celui tapé pour signer ; 400 qui nomme le
        champ, rien n'est écrit."""
        cas = (
            (dict(ENTREPRISE, signataire_email=''), 'entreprise.signataire_email'),
            (dict(ENTREPRISE, signataire_email='pas-un-email'),
             'entreprise.signataire_email'),
            (dict(ENTREPRISE, pouvoir_engager=False), 'entreprise.pouvoir_engager'),
            (dict(ENTREPRISE, pouvoir_engager='true'), 'entreprise.pouvoir_engager'),
            (dict(ENTREPRISE, signataire_nom='Autre Personne'),
             'entreprise.signataire_nom'),
            ({k: v for k, v in ENTREPRISE.items() if k != 'signataire_nom'},
             'entreprise.signataire_nom'),
        )
        for corps, champ in cas:
            with self.subTest(champ=champ, corps=corps):
                devis = self._devis()
                resp = self._post(devis, corps)
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(resp.data['champ'], champ)
                self.assertFalse(
                    DevisSignature.objects.filter(devis=devis).exists())

    def test_signataire_b2b_enregistre_sur_la_signature(self):
        devis = self._devis('commercial')
        resp = self._post(devis, dict(ENTREPRISE, signataire_nom=' karim  exemple '))
        self.assertEqual(resp.status_code, 200, resp.data)
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual(sig.signataire_email, ENTREPRISE['signataire_email'])
        self.assertIs(sig.pouvoir_engager, True)
        self.assertEqual(sig.signataire_nom, 'Karim Exemple')

    def test_residentiel_inchange(self):
        devis = self._devis('residentiel')
        resp = self._post(devis)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['entreprise'])
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual((sig.raison_sociale, sig.ice_declare), ('', ''))
        # Un bloc envoyé hors C&I est IGNORÉ (ni erreur, ni écriture).
        devis2 = self._devis('residentiel')
        resp2 = self._post(devis2, dict(ENTREPRISE, ice='bad'))
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(
            DevisSignature.objects.get(devis=devis2).ice_declare, '')

    def test_double_envoi_idempotent(self):
        devis = self._devis()
        self.assertEqual(self._post(devis, ENTREPRISE).status_code, 200)
        autre = dict(ENTREPRISE, raison_sociale='Autre SARL')
        resp = self._post(devis, autre)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(DevisSignature.objects.filter(devis=devis).count(), 1)
        self.assertEqual(
            DevisSignature.objects.get(devis=devis).raison_sociale,
            ENTREPRISE['raison_sociale'])
        self.assertEqual(resp.data['entreprise'], ENTREPRISE)
