"""API du dossier contractuel — portée, droits, refus, personnalisation,
formes servies (contract_samples/dossier_contractuel.json et
acte_contractuel.json).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.documents.tests.test_contrats_api"
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.documents.contrats import types as T
from apps.documents.models import ActeContractuel
from apps.documents.tests.test_contrats_dossier import (
    SIG, Vente, charger_echantillon, cles,
)
from apps.installations.models import Installation
from apps.roles.models import Role

User = get_user_model()
DOSSIER = '/api/django/documents/chantiers/{}/contrats/'
ACTE = '/api/django/documents/actes/{}/'


def api(user):
    a = APIClient()
    a.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return a


#: Clés servies au-delà de l'échantillon : aucune (la liste reste vide ; une
#: entrée ici serait un écart au contrat d'API à faire valider).
ECARTS_ADMIS = set()


class ApiContratsTests(TestCase):
    def setUp(self):
        self.v = Vente(self)
        self.api = api(self.v.user)

    def _detail(self, acte, **params):
        r = self.api.get(ACTE.format(acte.pk), params)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        return r.data

    def _patch(self, acte, surcharges, langue=None, client=None):
        corps = {'surcharges': surcharges}
        if langue:
            corps['langue'] = langue
        return (client or self.api).patch(ACTE.format(acte.pk), corps,
                                          format='json')

    # ── Portée et droits ────────────────────────────────────────────────

    def test_autre_societe_404(self):
        autre = Vente(self)
        for url in (DOSSIER.format(autre.chantier.pk),
                    ACTE.format(autre.acte(T.CONTRAT).pk),
                    ACTE.format(autre.acte(T.CONTRAT).pk) + 'pdf/'):
            with self.subTest(url=url):
                self.assertEqual(self.api.get(url).status_code, 404)
        r = self._patch(autre.acte(T.CONTRAT), {'titre': 'X'})
        self.assertEqual(r.status_code, 404)
        r = self.api.post(ACTE.format(autre.acte(T.CONTRAT).pk) + 'emettre/')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(autre.acte(T.CONTRAT).statut, T.BROUILLON)

    def test_role_lecture_seule_ne_peut_pas_ecrire(self):
        role = Role.objects.create(company=self.v.company, nom='Lecture',
                                   permissions=['installation_voir'])
        lecteur = User.objects.create_user(
            username=f'ctr-lect-{self.v.company.pk}', password='x',
            company=self.v.company, role=role)
        a = api(lecteur)
        acte = self.v.acte(T.CONTRAT)
        r = a.get(DOSSIER.format(self.v.chantier.pk))
        self.assertEqual(r.status_code, 200)
        # S11 : les peut_* disent la vérité — aucun geste proposé.
        gestes = ('peut_modifier', 'peut_emettre', 'peut_signer',
                  'peut_rouvrir')
        self.assertFalse(any(x[g] for x in r.data['actes'] for g in gestes))
        r = a.get(ACTE.format(acte.pk))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(any(r.data[g] for g in gestes))
        self.assertFalse(r.data['peut_enregistrer_modele'])
        moi = self._detail(acte)
        self.assertTrue(moi['peut_modifier'] and moi['peut_emettre'])
        self.assertFalse(moi['peut_enregistrer_modele'])
        self.assertEqual(self._patch(acte, {'titre': 'X'}, client=a)
                         .status_code, 403)
        for geste in ('emettre/', 'rouvrir/', 'modele/'):
            with self.subTest(geste=geste):
                self.assertEqual(
                    a.post(ACTE.format(acte.pk) + geste).status_code, 403)
        self.assertEqual(self.v.acte(T.CONTRAT).surcharges, {})

    def test_modele_reserve_au_directeur(self):
        from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
        acte = self.v.acte(T.CONTRAT)
        self.assertEqual(self.api.post(ACTE.format(acte.pk) + 'modele/')
                         .status_code, 403)
        role = Role.objects.create(company=self.v.company, nom='Directeur',
                                   est_systeme=True,
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        directeur = User.objects.create_user(
            username=f'ctr-dir-{self.v.company.pk}', password='x',
            company=self.v.company, role=role)
        self._patch(acte, {'societe': {'representant': 'Reda, gérant'}})
        self.assertTrue(api(directeur).get(ACTE.format(acte.pk)).data[
            'peut_enregistrer_modele'])
        r = api(directeur).post(ACTE.format(acte.pk) + 'modele/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('Modèle enregistré', r.data['detail'])
        livraison = self.v.acte(T.LIVRAISON, T.RESTE_A_REGLER)
        self.assertEqual(
            self._detail(livraison)['contenu']['societe']['representant'],
            'Reda, gérant')

    # ── Refus 409 / 400 ─────────────────────────────────────────────────

    def test_refus_400(self):
        acte = self.v.acte(T.CONTRAT)
        cas = (
            {'montants': {'total_ttc': '1.00'}},
            {'paiement': {'total_regle': '1.00'}},
            {'echeancier_textes': {'acompte': {'montant_ttc': '1.00'}}},
            {'articles': 'pas une liste'},
            {'garanties': [{'cle': 'x', 'duree_mois': 'longtemps'}]},
        )
        for surcharges in cas:
            with self.subTest(surcharges=surcharges):
                r = self._patch(acte, surcharges)
                self.assertEqual((r.status_code, r.data['code']),
                                 (400, T.CODE_CONTENU_INVALIDE))
        r = self._patch(acte, {'options': {'reserve_propriete': False}},
                        langue='ar')
        self.assertEqual((r.status_code, r.data['code']),
                         (400, T.CODE_CONTENU_INVALIDE))
        r = self.api.patch(ACTE.format(acte.pk), {'surcharges': 'x'},
                           format='json')
        self.assertEqual(r.status_code, 400)
        for url in (ACTE.format(acte.pk), ACTE.format(acte.pk) + 'pdf/'):
            with self.subTest(url=url):
                r = self.api.get(url, {'langue': 'xx'})
                self.assertEqual(r.status_code, 400)
        r = self.api.post(ACTE.format(acte.pk) + 'signer/',
                          {'signature_client': SIG}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.v.acte(T.CONTRAT).surcharges, {})

    # ── Personnalisation ────────────────────────────────────────────────

    def test_patch_fusion_et_remise_au_defaut(self):
        acte = self.v.acte(T.CONTRAT)
        r = self._patch(acte, {'conditions_particulieres': 'Accès terrasse.'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['contenu']['conditions_particulieres'],
                         'Accès terrasse.')
        self.assertEqual(r.data['sections_personnalisees'],
                         ['conditions_particulieres'])
        self.assertTrue(r.data['personnalise'])
        r = self._patch(acte, {'delais': {'date_limite': '2027-01-23',
                                          'detail': 'Pose comprise.'}})
        delais = r.data['contenu']['delais']
        self.assertEqual(delais['date_limite'], '2027-01-23')
        self.assertIn('23 janvier 2027', delais['resume'])
        self.assertEqual(r.data['contenu']['conditions_particulieres'],
                         'Accès terrasse.')
        articles = r.data['contenu']['articles']
        modifie = dict(articles[0], paragraphes=['Texte modifié.'])
        r = self._patch(acte, {'articles': [modifie]})
        self.assertEqual(r.data['contenu']['articles'][0]['paragraphes'],
                         ['Texte modifié.'])
        self.assertEqual(len(r.data['contenu']['articles']), len(articles))
        r = self._patch(acte, {'conditions_particulieres': None,
                               'garanties': [{'cle': '', 'designation': 'Toit',
                                              'duree_mois': 120}]})
        self.assertEqual(r.data['contenu']['conditions_particulieres'], '')
        self.assertEqual(r.data['contenu']['garanties'][0]['cle'], 'perso_1')
        self.assertNotIn('conditions_particulieres',
                         r.data['sections_personnalisees'])
        avert = r.data['avertissements']
        self.assertTrue(any('traduction arabe' in a for a in avert))

    def test_patch_arabe_ecrit_seulement_la_traduction(self):
        acte = self.v.acte(T.CONTRAT)
        r = self._patch(acte, {'conditions_particulieres': 'نص عربي'},
                        langue='ar')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['langue'], 'ar')
        self.assertEqual(r.data['contenu']['conditions_particulieres'],
                         'نص عربي')
        acte.refresh_from_db()
        self.assertEqual(acte.surcharges, {})
        self.assertEqual(acte.surcharges_ar,
                         {'conditions_particulieres': 'نص عربي'})
        fr = self._detail(acte)
        self.assertEqual(fr['contenu']['conditions_particulieres'], '')
        self.assertNotIn('options', self._detail(acte, langue='ar')[
            'sections_modifiables'])

    # ── S5 / S14 : corps envoyés par l'écran en arabe ───────────────────

    def test_arabe_delais_detail_seul_date_commune(self):
        acte = self.v.acte(T.CONTRAT)
        r = self._patch(acte, {'delais': {'date_limite': '2027-02-10'}})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(any('traduction arabe' in a
                             for a in r.data['avertissements']))
        r = self._patch(acte, {'delais': {'detail': 'يشمل كل شيء.'}},
                        langue='ar')
        self.assertEqual(r.status_code, 200, r.data)
        delais = r.data['contenu']['delais']
        self.assertEqual(delais['detail'], 'يشمل كل شيء.')
        self.assertEqual(delais['date_limite'], '2027-02-10')
        # Une date ou un résumé reçus en arabe ne changent rien.
        r = self._patch(acte, {'delais': {'detail': 'نص', 'resume': 'x',
                                          'date_limite': '2030-01-01'}},
                        langue='ar')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['contenu']['delais']['date_limite'],
                         '2027-02-10')
        self.assertNotEqual(r.data['contenu']['delais']['resume'], 'x')
        self.assertEqual(self._detail(acte)['contenu']['delais'][
            'date_limite'], '2027-02-10')

    def test_arabe_garanties_textes_seulement(self):
        acte = self.v.acte(T.CONTRAT)
        fr = self._detail(acte)['contenu']['garanties']
        lignes = [dict(g, duree_mois=36) if g['cle'] == 'installation' else g
                  for g in fr]
        r = self._patch(acte, {'garanties': lignes})
        self.assertEqual(r.status_code, 200, r.data)
        ar = self._detail(acte, langue='ar')['contenu']['garanties']
        self.assertEqual([(g['cle'], g['duree_mois']) for g in ar],
                         [(g['cle'], g['duree_mois'])
                          for g in r.data['contenu']['garanties']])
        corps = [{'cle': g['cle'], 'designation': g['designation'],
                  'garant': g['garant'], 'detail': g['detail']} for g in ar]
        corps[0] = dict(corps[0], designation='تسمية معدلة', duree_mois=1,
                        fin='2030-01-01')
        corps = corps[:-1] + [{'cle': 'inconnue', 'designation': 'زائد',
                               'garant': '', 'detail': ''}]
        r = self._patch(acte, {'garanties': corps}, langue='ar')
        self.assertEqual(r.status_code, 200, r.data)
        servi = r.data['contenu']['garanties']
        self.assertEqual([g['cle'] for g in servi], [g['cle'] for g in ar])
        self.assertEqual(servi[0]['designation'], 'تسمية معدلة')
        self.assertEqual(servi[0]['duree_mois'], ar[0]['duree_mois'])
        self.assertEqual(servi[-1]['designation'], ar[-1]['designation'])
        pose = [g for g in servi if g['cle'] == 'installation'][0]
        self.assertEqual(pose['duree_mois'], 36)
        r = self._patch(acte, {'garanties': [{'designation': 'بلا مفتاح'}]},
                        langue='ar')
        self.assertEqual((r.status_code, r.data['code']),
                         (400, T.CODE_CONTENU_INVALIDE))

    def test_paiement_modalites_seules_dans_les_deux_langues(self):
        acte = self.v.acte(T.CONTRAT)
        r = self._patch(acte, {'paiement': {'modalites': 'Par chèque.'}})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['contenu']['paiement']['modalites'],
                         'Par chèque.')
        self.assertIn('paiement', self._detail(acte, langue='ar')[
            'sections_modifiables'])
        r = self._patch(acte, {'paiement': {'modalites': 'بشيك.'}},
                        langue='ar')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['contenu']['paiement']['modalites'], 'بشيك.')
        self.assertEqual(self._detail(acte)['contenu']['paiement'][
            'modalites'], 'Par chèque.')
        r = self._patch(acte, {'paiement': {'engagement': 'Autre.'}})
        self.assertEqual((r.status_code, r.data['code']),
                         (400, T.CODE_CONTENU_INVALIDE))
        cloture = self.v.acte(T.CLOTURE)
        for langue, texte in (('fr', 'Bienvenue.'), ('ar', 'مرحبًا.')):
            with self.subTest(langue=langue):
                r = self._patch(cloture, {'conseils_intro': texte},
                                langue=langue)
                self.assertEqual(r.status_code, 200, r.data)
                self.assertEqual(r.data['contenu']['conseils_intro'], texte)

    # ── Formes servies = contrat d'API ──────────────────────────────────

    def test_formes_egales_aux_echantillons(self):
        self.v.payer(self.v.plan()['tranches'][0]['montant_ttc'],
                     jour=date(2026, 12, 2))
        dossier = charger_echantillon('dossier_contractuel.json')
        r = self.api.get(DOSSIER.format(self.v.chantier.pk))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(cles(r.json()), cles(dossier['exemple']))
        actes = charger_echantillon('acte_contractuel.json')
        paires = (
            ('exemple', T.CONTRAT, ''),
            ('exemple_pv_livraison_reste_a_regler', T.LIVRAISON,
             T.RESTE_A_REGLER),
            ('exemple_pv_livraison_tranche_reglee', T.LIVRAISON,
             T.TRANCHE_REGLEE),
            ('exemple_pv_reception', T.RECEPTION, ''),
            ('exemple_cloture_garanties', T.CLOTURE, ''),
        )
        for cle, type_acte, variante in paires:
            acte = self.v.acte(type_acte, variante)
            for langue in T.LANGUES:
                with self.subTest(acte=cle, langue=langue):
                    r = self.api.get(ACTE.format(acte.pk), {'langue': langue})
                    servi = cles(r.json())
                    attendu = cles(actes[cle])
                    self.assertEqual(servi - attendu, ECARTS_ADMIS)
                    self.assertEqual(attendu - servi, set())

    def test_dossier_prochaine_action_et_sans_devis(self):
        r = self.api.get(DOSSIER.format(self.v.chantier.pk))
        prochaine = r.data['prochaine_action']
        self.assertEqual(prochaine['type'], T.CONTRAT)
        self.assertEqual(len(r.data['actes']), 5)
        self.assertEqual([a['rang'] for a in r.data['actes']], [1, 2, 2, 3, 4])
        chantier = Installation.objects.create(
            company=self.v.company, reference='CHT-2026-11-9999')
        r = self.api.get(DOSSIER.format(chantier.pk))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['prix_ttc'])
        self.assertIsNone(r.data['prochaine_action'])
        self.assertEqual(ActeContractuel.objects.filter(
            chantier=chantier).count(), 5)
        self.assertFalse(any(a['peut_emettre'] for a in r.data['actes']))


@tag('pdf')
class ApiContratsPdfTests(TestCase):
    """Gestes qui rendent un PDF (WeasyPrint réel, GED de test) — palier
    « pdf »."""

    def setUp(self):
        self.v = Vente(self)
        self.api = api(self.v.user)

    def _patch(self, acte, surcharges, langue=None, client=None):
        corps = {'surcharges': surcharges}
        if langue:
            corps['langue'] = langue
        return (client or self.api).patch(ACTE.format(acte.pk), corps,
                                          format='json')

    def test_refus_409(self):
        acte = self.v.acte(T.CONTRAT)
        r = self.api.post(ACTE.format(acte.pk) + 'emettre/')
        self.assertEqual(r.status_code, 200, r.data)
        r = self._patch(acte, {'titre': 'X'})
        self.assertEqual((r.status_code, r.data['code']), (409, T.CODE_ACTE_FIGE))
        r = self.api.post(ACTE.format(acte.pk) + 'marquer-signe/',
                          {'signataire_nom': 'Youssef EXEMPLE',
                           'signe_le': '2099-01-01'}, format='json')
        self.assertEqual((r.status_code, r.data['code']),
                         (400, T.CODE_CONTENU_INVALIDE))  # date future
        r = self.api.post(ACTE.format(acte.pk) + 'marquer-signe/',
                          {'signataire_nom': 'Youssef EXEMPLE'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], T.SIGNE)
        self.assertEqual(r.data['mode_signature'], 'papier')
        r = self.api.post(ACTE.format(acte.pk) + 'signer/',
                          {'signature_client': SIG,
                           'signataire_nom': 'Youssef EXEMPLE'}, format='json')
        self.assertEqual((r.status_code, r.data['code']), (409, T.CODE_DEJA_SIGNE))
        cloture = self.v.acte(T.CLOTURE)
        r = self.api.post(ACTE.format(cloture.pk) + 'emettre/')
        self.assertEqual((r.status_code, r.data['code']),
                         (409, T.CODE_SOLDE_NON_REGLE))
        self.assertIn('restent dus', r.data['detail'])
        Installation.objects.filter(pk=self.v.chantier.pk).update(annule=True)
        r = self._patch(self.v.acte(T.RECEPTION), {'titre': 'X'})
        self.assertEqual((r.status_code, r.data['code']),
                         (409, T.CODE_CHANTIER_ANNULE))

    def test_pdf_inline(self):
        acte = self.v.acte(T.CONTRAT)
        for langue, suffixe in (('fr', ''), ('ar', '-ar')):
            with self.subTest(langue=langue):
                r = self.api.get(ACTE.format(acte.pk) + 'pdf/',
                                 {'langue': langue})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r['Content-Type'], 'application/pdf')
                self.assertEqual(
                    r['Content-Disposition'],
                    f'inline; filename="{acte.reference}{suffixe}.pdf"')
