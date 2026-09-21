"""Tests NTDOC7 — Parapheur électronique du dirigeant (signature en masse).

Critère d'acceptation :
- le dirigeant voit EN UNE LISTE tout ce qui l'attend (contrats dont la
  signature interne manque + étapes d'approbation qui lui sont assignées) ;
- il signe plusieurs contrats EN UNE ACTION ;
- un item signé entre-temps par un tiers est RAPPORTÉ sans faire échouer le
  lot (jamais tout-ou-rien).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors, services
from apps.contrats.models import (
    Contrat, EtapeApprobation, PartieContrat, SignatureContrat,
)

User = get_user_model()

BASE = '/api/django/contrats/contrats/'
PARAPHEUR = BASE + 'parapheur/'
SIGNER_LOT = BASE + 'parapheur/signer-lot/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ParapheurTestsBase(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc7', 'Parapheur')
        self.dirigeant = User.objects.create_user(
            username='ntdoc7-dirigeant', password='x', company=self.co,
            role_legacy='admin')
        self.api = auth(self.dirigeant)

    def make_contrat(self, objet, *, statut=Contrat.Statut.EN_APPROBATION,
                     date_fin=None, company=None):
        """Contrat à DEUX parties (garde « ≥2 parties » de la machine d'états)."""
        company = company or self.co
        contrat = Contrat.objects.create(
            company=company, objet=objet, statut=statut, date_fin=date_fin)
        for rang, type_partie in enumerate(['client', 'prestataire']):
            PartieContrat.objects.create(
                company=company, contrat=contrat, type_partie=type_partie,
                nom=f'{objet} — partie {rang}', ordre=rang)
        return contrat

    def signer_cote_client(self, contrat, nom='Client SARL'):
        return services.signer_contrat(
            contrat, signataire_nom=nom,
            role_signataire=SignatureContrat.RoleSignataire.CLIENT)


class FileDuParapheurTests(ParapheurTestsBase):
    """La file unifiée « ce qui m'attend »."""

    def test_contrat_en_approbation_non_signe_est_dans_la_file(self):
        contrat = self.make_contrat('Maintenance', date_fin=date(2030, 1, 1))
        items = selectors.items_parapheur(self.dirigeant)
        self.assertEqual(
            [(i['type'], i['contrat']) for i in items],
            [('signature', contrat.id)])

    def test_contrat_deja_signe_en_interne_sort_de_la_file(self):
        contrat = self.make_contrat('Déjà paraphé')
        services.signer_contrat(
            contrat, signataire_nom='Le dirigeant',
            role_signataire=SignatureContrat.RoleSignataire.PRESTATAIRE)
        self.assertEqual(selectors.items_parapheur(self.dirigeant), [])

    def test_contrat_en_brouillon_hors_file(self):
        """Un contrat pas encore parvenu au stade signable n'attend personne."""
        self.make_contrat('Brouillon', statut=Contrat.Statut.BROUILLON)
        self.assertEqual(selectors.items_parapheur(self.dirigeant), [])

    def test_etape_assignee_est_dans_la_file(self):
        contrat = self.make_contrat('Avec workflow')
        etape = EtapeApprobation.objects.create(
            company=self.co, contrat=contrat, niveau=1,
            assigne_a=self.dirigeant)
        items = selectors.items_parapheur(self.dirigeant)
        types = {i['type'] for i in items}
        self.assertEqual(types, {'signature', 'approbation'})
        approbation = [i for i in items if i['type'] == 'approbation'][0]
        self.assertEqual(approbation['etape'], etape.id)
        self.assertEqual(approbation['niveau'], 1)

    def test_etape_non_assignee_jamais_dans_la_file(self):
        """L'existant (assigne_a NULL) ne remonte JAMAIS : comportement inchangé."""
        contrat = self.make_contrat('Workflow anonyme')
        EtapeApprobation.objects.create(
            company=self.co, contrat=contrat, niveau=1)
        items = selectors.items_parapheur(self.dirigeant)
        self.assertEqual([i['type'] for i in items], ['signature'])

    def test_etape_deja_decidee_hors_file(self):
        contrat = self.make_contrat('Workflow clos')
        EtapeApprobation.objects.create(
            company=self.co, contrat=contrat, niveau=1,
            assigne_a=self.dirigeant,
            statut=EtapeApprobation.Statut.APPROUVE)
        items = selectors.items_parapheur(self.dirigeant)
        self.assertEqual([i['type'] for i in items], ['signature'])

    def test_tri_par_echeance_la_plus_proche_dabord_sans_date_en_dernier(self):
        tard = self.make_contrat('Tard', date_fin=date(2031, 6, 1))
        tot = self.make_contrat('Tôt', date_fin=date(2030, 1, 1))
        sans = self.make_contrat('Sans échéance')
        items = selectors.items_parapheur(self.dirigeant)
        self.assertEqual(
            [i['contrat'] for i in items], [tot.id, tard.id, sans.id])

    def test_endpoint_parapheur_rend_la_file(self):
        contrat = self.make_contrat('Via API')
        resp = self.api.get(PARAPHEUR)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['contrat'], contrat.id)


class IsolationSocieteTests(ParapheurTestsBase):
    """Le parapheur ne fuit JAMAIS d'une société à l'autre."""

    def setUp(self):
        super().setUp()
        self.autre_co = make_company('ntdoc7-autre', 'Autre société')
        self.autre_user = User.objects.create_user(
            username='ntdoc7-autre-user', password='x', company=self.autre_co,
            role_legacy='admin')

    def test_contrat_dune_autre_societe_absent(self):
        self.make_contrat('Contrat voisin', company=self.autre_co)
        self.assertEqual(selectors.items_parapheur(self.dirigeant), [])

    def test_etape_assignee_depuis_une_autre_societe_absente(self):
        """Même assignée nommément, une étape d'une autre société n'apparaît pas."""
        contrat_voisin = self.make_contrat(
            'Voisin avec étape', company=self.autre_co)
        EtapeApprobation.objects.create(
            company=self.autre_co, contrat=contrat_voisin, niveau=1,
            assigne_a=self.dirigeant)
        self.assertEqual(selectors.items_parapheur(self.dirigeant), [])

    def test_signer_lot_ignore_un_contrat_dune_autre_societe(self):
        voisin = self.make_contrat('Cible interdite', company=self.autre_co)
        rapport = services.signer_lot_parapheur(
            self.dirigeant, [voisin.id], signataire_nom='Le dirigeant')
        self.assertEqual(rapport['nb_signes'], 0)
        self.assertEqual(rapport['nb_echecs'], 1)
        self.assertIn('introuvable', rapport['resultats'][0]['detail'].lower())
        self.assertFalse(
            SignatureContrat.objects.filter(contrat=voisin).exists())


class SignerLotTests(ParapheurTestsBase):
    """La signature en masse — jamais tout-ou-rien."""

    def test_signe_cinq_contrats_en_une_action(self):
        contrats = [self.make_contrat(f'Lot {n}') for n in range(5)]
        resp = self.api.post(
            SIGNER_LOT,
            {'contrats': [c.id for c in contrats],
             'signataire_nom': 'Reda K.'},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_signes'], 5)
        self.assertEqual(resp.data['nb_echecs'], 0)
        self.assertEqual(
            SignatureContrat.objects.filter(
                company=self.co,
                role_signataire=SignatureContrat.RoleSignataire.PRESTATAIRE,
            ).count(), 5)

    def test_item_signe_entre_temps_rapporte_sans_bloquer_le_lot(self):
        a = self.make_contrat('A')
        conflit = self.make_contrat('Conflit')
        b = self.make_contrat('B')
        # Un TIERS signe le contrat « conflit » juste avant la validation.
        services.signer_contrat(
            conflit, signataire_nom='Un associé',
            role_signataire=SignatureContrat.RoleSignataire.PRESTATAIRE)

        resp = self.api.post(
            SIGNER_LOT,
            {'contrats': [a.id, conflit.id, b.id],
             'signataire_nom': 'Reda K.'},
            format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_signes'], 2)
        self.assertEqual(resp.data['nb_echecs'], 1)
        par_contrat = {r['contrat']: r for r in resp.data['resultats']}
        self.assertTrue(par_contrat[a.id]['ok'])
        self.assertTrue(par_contrat[b.id]['ok'])
        self.assertFalse(par_contrat[conflit.id]['ok'])
        # Les deux autres sont bel et bien signés en base (aucun rollback).
        for contrat in (a, b):
            self.assertTrue(
                SignatureContrat.objects.filter(
                    contrat=contrat,
                    role_signataire=(
                        SignatureContrat.RoleSignataire.PRESTATAIRE),
                ).exists())

    def test_bascule_signe_quand_le_client_avait_deja_signe(self):
        contrat = self.make_contrat('Client déjà signé')
        self.signer_cote_client(contrat)
        rapport = services.signer_lot_parapheur(
            self.dirigeant, [contrat.id], signataire_nom='Reda K.')
        contrat.refresh_from_db()
        self.assertTrue(rapport['resultats'][0]['contrat_signe'])
        self.assertIn(
            contrat.statut, {Contrat.Statut.SIGNE, Contrat.Statut.ACTIF})

    def test_lot_vide_refuse_en_400(self):
        resp = self.api.post(
            SIGNER_LOT, {'contrats': [], 'signataire_nom': 'Reda K.'},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_nom_vide_refuse_en_400(self):
        contrat = self.make_contrat('Sans nom')
        resp = self.api.post(
            SIGNER_LOT,
            {'contrats': [contrat.id], 'signataire_nom': '   '},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_doublon_dans_la_selection_ne_produit_quun_seul_essai(self):
        contrat = self.make_contrat('Coché deux fois')
        rapport = services.signer_lot_parapheur(
            self.dirigeant, [contrat.id, contrat.id],
            signataire_nom='Reda K.')
        self.assertEqual(rapport['nb_signes'], 1)
        self.assertEqual(rapport['nb_echecs'], 0)
        self.assertEqual(len(rapport['resultats']), 1)

    def test_preuves_posees_cote_serveur(self):
        contrat = self.make_contrat('Preuves')
        self.api.post(
            SIGNER_LOT,
            {'contrats': [contrat.id], 'signataire_nom': 'Reda K.'},
            format='json', HTTP_USER_AGENT='pytest-agent')
        signature = SignatureContrat.objects.get(contrat=contrat)
        self.assertEqual(signature.signataire_id, self.dirigeant.id)
        self.assertEqual(signature.company_id, self.co.id)
        self.assertEqual(signature.user_agent, 'pytest-agent')


class AssignerEtapeTests(ParapheurTestsBase):
    """L'assignation nominative d'une étape — n'approuve jamais rien."""

    def setUp(self):
        super().setUp()
        self.contrat = self.make_contrat('Workflow')
        self.etape = EtapeApprobation.objects.create(
            company=self.co, contrat=self.contrat, niveau=1)

    def test_assigner_fait_entrer_letape_dans_le_parapheur(self):
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/assigner-etape/',
            {'etape': self.etape.id, 'assigne_a': self.dirigeant.id},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.assigne_a_id, self.dirigeant.id)
        # Le statut de l'étape n'a PAS bougé : assigner ne décide rien.
        self.assertEqual(
            self.etape.statut, EtapeApprobation.Statut.EN_ATTENTE)
        etapes = [
            i for i in selectors.items_parapheur(self.dirigeant)
            if i['type'] == 'approbation']
        self.assertEqual([i['etape'] for i in etapes], [self.etape.id])

    def test_desassigner_sort_letape_du_parapheur(self):
        self.etape.assigne_a = self.dirigeant
        self.etape.save(update_fields=['assigne_a'])
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/assigner-etape/',
            {'etape': self.etape.id, 'assigne_a': None}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.etape.refresh_from_db()
        self.assertIsNone(self.etape.assigne_a_id)
        self.assertEqual(
            [i for i in selectors.items_parapheur(self.dirigeant)
             if i['type'] == 'approbation'], [])

    def test_etape_deja_decidee_refusee_en_400(self):
        self.etape.statut = EtapeApprobation.Statut.APPROUVE
        self.etape.save(update_fields=['statut'])
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/assigner-etape/',
            {'etape': self.etape.id, 'assigne_a': self.dirigeant.id},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_etape_dun_autre_contrat_en_404(self):
        autre = self.make_contrat('Autre contrat')
        resp = self.api.post(
            f'{BASE}{autre.id}/assigner-etape/',
            {'etape': self.etape.id, 'assigne_a': self.dirigeant.id},
            format='json')
        self.assertEqual(resp.status_code, 404)

    def test_utilisateur_dune_autre_societe_en_404(self):
        autre_co = make_company('ntdoc7-assign-autre', 'Assign autre')
        etranger = User.objects.create_user(
            username='ntdoc7-etranger', password='x', company=autre_co,
            role_legacy='admin')
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/assigner-etape/',
            {'etape': self.etape.id, 'assigne_a': etranger.id},
            format='json')
        self.assertEqual(resp.status_code, 404)
        self.etape.refresh_from_db()
        self.assertIsNone(self.etape.assigne_a_id)
