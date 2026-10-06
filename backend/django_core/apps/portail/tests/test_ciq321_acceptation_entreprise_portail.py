"""CIQ321 — portail client : l'acceptation d'un devis commercial / industriel
exige aussi la raison sociale, la qualité du signataire et l'ICE (D-CIQ-11).

Même règle que la page publique (CIQ319), appliquée par le MÊME lecteur
(``apps.ventes.domain.cycle_vie.lire_entreprise_acceptation``) et le même
service ``accept_devis(..., entreprise=…)`` — jamais une seconde validation.
La liste ``mes-devis`` dit quand l'identité est requise
(``exige_identite_entreprise``, contrat ``mes_devis_liste.json``).

Corps et réponses lus dans les contrats COMMITTÉS :
``apps/ventes/contract_samples/acceptation_entreprise.json`` (``exemple_portail``)
et ``apps/portail/contract_samples/mes_devis_liste.json``.

Run :
    python manage.py test apps.portail.tests.test_ciq321_acceptation_entreprise_portail
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.ventes.models import Devis, DevisSignature
from authentication.models import CustomUser

from .test_ntprt10_mes_devis import (
    make_client, make_company, make_portal_user,
)

_APPS = Path(__file__).resolve().parents[2]
CONTRAT_ACCEPTATION = json.loads(
    (_APPS / 'ventes' / 'contract_samples' / 'acceptation_entreprise.json')
    .read_text(encoding='utf-8'))
CONTRAT_LISTE = json.loads(
    (_APPS / 'portail' / 'contract_samples' / 'mes_devis_liste.json')
    .read_text(encoding='utf-8'))
# ``option`` est retiré : ces devis de test sont mono-option (ADOC110 — un
# devis mono-option n'attend aucune option ; « sans » de l'exemple n'est pas
# une clé du portail).
CORPS = {k: v for k, v in CONTRAT_ACCEPTATION['exemple_portail']['corps']
         .items() if k != 'option'}
ENTREPRISE = dict(CORPS['entreprise'])


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class AcceptationEntreprisePortail(TestCase):

    def setUp(self):
        self.company = make_company('ciq321-co-a', 'CIQ321 Société A')
        self.client_a = make_client(self.company, 'Hôtel Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.user_a = make_portal_user(
            self.company, 'ciq321-portail-a',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_a.id)
        self.user_b = make_portal_user(
            self.company, 'ciq321-portail-b',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_b.id)
        self.api = APIClient()
        self.n = 0

    def _devis(self, mode, client=None):
        self.n += 10
        return Devis.objects.create(
            company=self.company, reference=f'DEV-CIQ321-{self.n:03d}',
            client=client or self.client_a, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), mode_installation=mode)

    def _post(self, devis, corps, user=None):
        self.api.force_authenticate(user=user or self.user_a)
        with patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
            return self.api.post(
                f'/api/django/portail/mes-devis/{devis.id}/accepter/',
                corps, format='json')

    def _corps(self, **entreprise):
        corps = {k: v for k, v in CORPS.items() if k != 'entreprise'}
        corps['entreprise'] = dict(ENTREPRISE, **entreprise)
        return corps

    # ── 400 qui nomme le champ ─────────────────────────────────────────────
    def test_industriel_sans_ice_400_nomme_le_champ(self):
        for mode in ('industriel', 'commercial'):
            with self.subTest(mode=mode):
                devis = self._devis(mode)
                res = self._post(devis, self._corps(ice=''))
                self.assertEqual(res.status_code, 400, res.data)
                self.assertEqual(res.data['champ'], 'entreprise.ice')
                self.assertEqual(
                    set(res.data),
                    set(CONTRAT_LISTE['acceptation']['reponses']
                        ['400_entreprise']))
                devis.refresh_from_db()
                self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
                self.assertFalse(
                    DevisSignature.objects.filter(devis=devis).exists())

    def test_bloc_absent_nomme_le_premier_champ(self):
        devis = self._devis('industriel')
        corps = {k: v for k, v in CORPS.items() if k != 'entreprise'}
        res = self._post(devis, corps)
        self.assertEqual(res.status_code, 400, res.data)
        self.assertEqual(res.data['champ'], 'entreprise.raison_sociale')

    def test_qualite_manquante_nommee(self):
        res = self._post(self._devis('industriel'),
                         self._corps(signataire_qualite='  '))
        self.assertEqual(res.status_code, 400, res.data)
        self.assertEqual(res.data['champ'], 'entreprise.signataire_qualite')

    def test_ice_mal_forme_400(self):
        res = self._post(self._devis('industriel'), self._corps(ice='12AB'))
        self.assertEqual(res.status_code, 400, res.data)
        self.assertEqual(res.data['champ'], 'entreprise.ice')

    # ── chemin heureux ─────────────────────────────────────────────────────
    def test_trois_champs_devis_accepte_signature_complete(self):
        devis = self._devis('industriel')
        res = self._post(devis, self._corps())
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['statut'], Devis.Statut.ACCEPTE)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual(sig.raison_sociale, ENTREPRISE['raison_sociale'])
        self.assertEqual(sig.signataire_qualite,
                         ENTREPRISE['signataire_qualite'])
        self.assertEqual(sig.ice_declare, ENTREPRISE['ice'])

    def test_double_envoi_idempotent(self):
        devis = self._devis('commercial')
        premier = self._post(devis, self._corps())
        second = self._post(devis, self._corps())
        self.assertEqual(premier.status_code, 200, premier.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(
            DevisSignature.objects.filter(devis=devis).count(), 1)

    # ── résidentiel inchangé ───────────────────────────────────────────────
    def test_residentiel_inchange_bloc_ignore(self):
        devis = self._devis('residentiel')
        res = self._post(devis, {'nom': 'Sami', 'consent_esign': True})
        self.assertEqual(res.status_code, 200, res.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)

    def test_residentiel_bloc_invalide_ignore(self):
        devis = self._devis('residentiel')
        res = self._post(devis, self._corps(ice='12AB'))
        self.assertEqual(res.status_code, 200, res.data)
        sig = DevisSignature.objects.filter(devis=devis).first()
        if sig is not None:
            self.assertEqual(sig.ice_declare, '')

    # ── cloisonnement ──────────────────────────────────────────────────────
    def test_devis_d_un_autre_client_404(self):
        devis = self._devis('industriel', client=self.client_b)
        res = self._post(devis, self._corps(), user=self.user_a)
        self.assertEqual(res.status_code, 404)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_devis_d_une_autre_societe_404(self):
        autre = make_company('ciq321-co-b', 'CIQ321 Société B')
        client_autre = make_client(autre, 'Gamma')
        devis = Devis.objects.create(
            company=autre, reference='DEV-CIQ321-B01', client=client_autre,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            mode_installation='industriel')
        res = self._post(devis, self._corps())
        self.assertEqual(res.status_code, 404)

    # ── la liste dit quand l'identité est requise ──────────────────────────
    def test_liste_porte_exige_identite_entreprise(self):
        industriel = self._devis('industriel')
        residentiel = self._devis('residentiel')
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get('/api/django/portail/mes-devis/')
        self.assertEqual(res.status_code, 200)
        lignes = {ligne['id']: ligne for ligne in res.data['results']}
        self.assertIs(lignes[industriel.id]['exige_identite_entreprise'], True)
        self.assertIs(
            lignes[residentiel.id]['exige_identite_entreprise'], False)
        # Mêmes clés que l'exemple COMMITTÉ du contrat.
        self.assertEqual(set(lignes[industriel.id]),
                         set(CONTRAT_LISTE['exemple']['results'][0]))
