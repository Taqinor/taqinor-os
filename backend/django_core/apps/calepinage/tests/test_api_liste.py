"""CAL16 — le viewset CRUD du pivot, ses filtres et ses refus.

Ce qui est prouvé ici :

* CHAQUE filtre (``?lead=`` ``?client=`` ``?statut=`` ``?depuis=`` ``?q=``)
  change RÉELLEMENT le jeu renvoyé — la leçon PV22 est qu'un ``?statut=``
  ignoré fait ouvrir le mauvais objet ;
* un filtre ILLISIBLE (statut inconnu, date invalide) est refusé 400 en
  NOMMANT le champ, jamais avalé en silence ;
* ``POST`` accepte lead, client, ou les deux s'ils sont COHÉRENTS (ACAL179),
  refuse un client incohérent et refuse aucun, avec un
  message français qui NOMME le champ fautif ;
* un ``company`` envoyé dans le corps est IGNORÉ (la société est celle de
  l'appelant, posée côté serveur) ;
* sans ``calepinage_voir`` la liste répond 403 ;
* un calepinage d'une AUTRE société est introuvable (404), jamais « interdit ».

Run :
    python manage.py test apps.calepinage.tests.test_api_liste -v2
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.agent.registry import LOT_COPILOTE, RISK_INTERNAL
from apps.calepinage.contrats_assistant import CONTRATS_ASSISTANT
from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.permissions import CAL_GERER, CAL_VOIR
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.crm.models import Client, Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    DIRECTEUR_PERMISSIONS,
    TECHNICIEN_PERMISSIONS,
    TECHNICIEN_RESP_PERMISSIONS,
)
from authentication.models import Company

User = get_user_model()

URL = '/api/django/calepinage/calepinages/'


def url_detail(pk):
    return f'{URL}{pk}/'


class BaseApiCalepinage(TestCase):
    """Deux sociétés, un porteur des droits, un technicien sans droit."""

    def setUp(self):
        self.company = Company.objects.create(nom='Calep Co',
                                              slug='calep-co-16')
        self.autre = Company.objects.create(nom='Voisine Co',
                                            slug='voisine-co-16')
        self.role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.role_autre = Role.objects.create(
            company=self.autre, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        # D-ACAL-106 — le Technicien LIT désormais un calepinage : le compte
        # « sans » garde ses droits, moins tout code ``calepinage_*``.
        self.role_sans = Role.objects.create(
            company=self.company, nom='Technicien sans calepinage',
            permissions=[c for c in TECHNICIEN_PERMISSIONS
                         if not c.startswith('calepinage_')])
        self.user = User.objects.create_user(
            username='cal_api', password='x', company=self.company,
            role=self.role)
        self.user_autre = User.objects.create_user(
            username='cal_api_voisin', password='x', company=self.autre,
            role=self.role_autre)
        self.user_sans = User.objects.create_user(
            username='cal_api_tech', password='x', company=self.company,
            role=self.role_sans)
        self.api = self._client(self.user)
        self.api_autre = self._client(self.user_autre)
        self.api_sans = self._client(self.user_sans)

        self.lead = Lead.objects.create(company=self.company,
                                        nom='Toiture Anfa')
        self.lead_2 = Lead.objects.create(company=self.company,
                                          nom='Toiture Maârif')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Bâtiment Atlas')

    @staticmethod
    def _client(user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    @staticmethod
    def _lignes(reponse):
        donnees = reponse.data
        if isinstance(donnees, dict) and 'results' in donnees:
            return donnees['results']
        return donnees


class FiltresListeTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.sur_lead = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk,
            titre='Villa Anfa', statut=Calepinage.Statut.BROUILLON)
        self.sur_lead_2 = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_2.pk,
            titre='Hangar Maârif', statut=Calepinage.Statut.VALIDE)
        # ACAL114 — « validé » est DÉRIVÉ de l'approbation (approuvée sur
        # l'empreinte courante), jamais lu dans la colonne ``statut``.
        Calepinage.objects.filter(pk=self.sur_lead_2.pk).update(
            layout_hash='a' * 64,
            approbation={'etat': 'approuve', 'empreinte_approuvee': 'a' * 64})
        self.sur_client = Calepinage.objects.create(
            company=self.company, client=self.client_a,
            titre='Usine Atlas', statut=Calepinage.Statut.BROUILLON)
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=999, titre='Chez la voisine')

    def _ids(self, **params):
        reponse = self.api.get(URL, params)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return {ligne['id'] for ligne in self._lignes(reponse)}

    def test_liste_bornee_societe(self):
        ids = self._ids()
        self.assertEqual(
            ids, {self.sur_lead.pk, self.sur_lead_2.pk, self.sur_client.pk})
        self.assertNotIn(self.etranger.pk, ids)

    def test_filtre_lead(self):
        self.assertEqual(self._ids(lead=self.lead.pk), {self.sur_lead.pk})

    def test_filtre_client(self):
        self.assertEqual(self._ids(client=self.client_a.pk),
                         {self.sur_client.pk})

    def test_filtre_statut(self):
        self.assertEqual(self._ids(statut=Calepinage.Statut.VALIDE),
                         {self.sur_lead_2.pk})

    def test_filtre_q_sur_le_titre(self):
        self.assertEqual(self._ids(q='anfa'), {self.sur_lead.pk})

    def test_filtre_depuis_vide_400(self):
        # api-fuzz-full 41773314544 : ``?depuis=`` (format publié : date) passait.
        reponse = self.api.get(URL, {'depuis': ''})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('depuis', reponse.data)

    def test_filtre_depuis(self):
        from datetime import timedelta

        demain = (self.sur_lead.created_at + timedelta(days=1)).date()
        self.assertEqual(self._ids(depuis=demain.isoformat()), set())
        hier = (self.sur_lead.created_at - timedelta(days=1)).date()
        self.assertEqual(len(self._ids(depuis=hier.isoformat())), 3)

    def test_statut_inconnu_refuse_en_nommant_le_champ(self):
        reponse = self.api.get(URL, {'statut': 'en_cours'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('statut', reponse.data)

    def test_date_illisible_refusee_en_nommant_le_champ(self):
        reponse = self.api.get(URL, {'depuis': 'la semaine dernière'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('depuis', reponse.data)

    def test_detail_d_une_autre_societe_est_introuvable(self):
        reponse = self.api.get(url_detail(self.etranger.pk))
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_de_lecture_403(self):
        reponse = self.api_sans.get(URL)
        self.assertEqual(reponse.status_code, 403)


class ResponsablesPossiblesTest(BaseApiCalepinage):
    """T4-X3-016 — le menu « Responsable » de Nouveau calepinage ne propose que
    des gens qui peuvent OUVRIR un calepinage (même prédicat que le serveur :
    ``calepinage_voir``, ``ScopedPermission``). Un compte sans ``calepinage_voir``
    reçoit 403 sur tout le module : lui confier un calepinage n'a pas de sens."""

    URL = '/api/django/crm/assignable-users/'

    def _usernames(self, **params):
        reponse = self.api.get(self.URL, params)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return {u['username'] for u in reponse.data}

    def test_filtre_par_permission_ecarte_qui_ne_peut_pas_ouvrir(self):
        # Sans filtre : tout le monde (comportement du sélecteur de leads, inchangé).
        self.assertIn('cal_api_tech', self._usernames())
        proposes = self._usernames(permission=CAL_VOIR)
        self.assertIn('cal_api', proposes)
        self.assertNotIn('cal_api_tech', proposes)
        self.assertNotIn('cal_api_voisin', proposes)
        # Ouvre bien ce qu'on lui offre : la liste lui répond 200.
        self.assertEqual(self.api_sans.get(URL).status_code, 403)

    def test_permission_inconnue_refusee_en_la_nommant(self):
        reponse = self.api.get(self.URL, {'permission': 'inventee'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('permission', reponse.data)


class ResponsableQuiOuvreTest(BaseApiCalepinage):
    """T4-X3-016 (suite) — D-ACAL-106/126 : un Technicien (``calepinage_voir`` +
    ``calepinage_releve``, sans ``calepinage_gerer``) ne lit que les calepinages
    de SES visites ; « responsable » ne lui ouvre rien. Le menu ne le propose
    donc que s'il a une visite sur le lead, et l'API refuse de lui confier un
    calepinage qu'il ne pourrait pas ouvrir. Aucun droit n'est changé."""

    MENU = '/api/django/crm/assignable-users/'

    def setUp(self):
        super().setUp()
        role_tech = Role.objects.create(
            company=self.company, nom='Technicien reel',
            permissions=list(TECHNICIEN_PERMISSIONS))
        self.tech = User.objects.create_user(
            username='cal_api_releve', password='x', company=self.company,
            role=role_tech)

    def _menu(self, **params):
        reponse = self.api.get(self.MENU, {'permission': CAL_VOIR, **params})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return {u['username'] for u in reponse.data}

    def _visite(self, technicien, lead=None):
        from apps.visites.models import VisiteTerrain

        return VisiteTerrain.objects.create(
            company=self.company, lead=lead or self.lead, commercial=technicien)

    def test_le_technicien_a_les_droits_de_lecture_et_ne_lit_que_par_le_releve(self):
        from apps.calepinage.selectors import lit_par_le_seul_releve

        self.assertIn(CAL_VOIR, TECHNICIEN_PERMISSIONS)
        self.assertTrue(lit_par_le_seul_releve(self.tech))

    def test_le_menu_ecarte_le_technicien_sans_lead_ou_sans_visite(self):
        proposes = self._menu()
        self.assertIn('cal_api', proposes)
        self.assertNotIn('cal_api_releve', proposes)
        # Un lead où il n'a AUCUNE visite : pas proposé non plus.
        self.assertNotIn('cal_api_releve', self._menu(lead=self.lead.pk))

    def test_le_menu_propose_le_technicien_qui_a_une_visite_sur_le_lead(self):
        self._visite(self.tech)
        self.assertIn('cal_api_releve', self._menu(lead=self.lead.pk))
        # Autre lead, ou sans lead : pas proposé.
        self.assertNotIn('cal_api_releve', self._menu(lead=self.lead_2.pk))
        self.assertNotIn('cal_api_releve', self._menu())

    def test_un_lead_d_une_autre_societe_est_ignore_comme_aucun_lead(self):
        self._visite(self.tech)
        lead_voisin = Lead.objects.create(company=self.autre, nom='Voisin')
        self.assertNotIn('cal_api_releve', self._menu(lead=lead_voisin.pk))
        self.assertNotIn('cal_api_releve', self._menu(lead='abc'))

    def test_creation_confiee_a_un_technicien_sans_visite_refusee_400(self):
        reponse = self.api.post(URL, {'lead': self.lead.pk,
                                      'responsable': self.tech.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('responsable', reponse.data)
        self.assertFalse(Calepinage.objects.filter(lead_id=self.lead.pk).exists())

    def test_creation_sur_client_sans_lead_confiee_a_un_technicien_refusee(self):
        reponse = self.api.post(URL, {'client': self.client_a.pk,
                                      'responsable': self.tech.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('responsable', reponse.data)

    def test_modification_confiee_a_un_technicien_sans_visite_refusee_409(self):
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa')
        reponse = self.api.patch(url_detail(calepinage.pk),
                                 {'responsable': self.tech.pk}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('responsable', reponse.data)
        calepinage.refresh_from_db()
        self.assertIsNone(calepinage.responsable)

    def test_le_technicien_de_la_visite_est_admis_et_ouvre_le_calepinage(self):
        self._visite(self.tech)
        reponse = self.api.post(URL, {'lead': self.lead.pk,
                                      'responsable': self.tech.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        ouvre = self._client(self.tech).get(url_detail(reponse.data['id']))
        self.assertEqual(ouvre.status_code, 200)

    def test_un_responsable_de_droit_complet_est_admis(self):
        reponse = self.api.post(URL, {'lead': self.lead.pk,
                                      'responsable': self.user.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)

    def test_renvoyer_le_responsable_deja_en_place_passe(self):
        # Un calepinage dont le responsable est DÉJÀ un Technicien (passif) : un
        # PATCH d'un autre champ qui renvoie ce même responsable n'est pas jugé.
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa',
            responsable=self.tech)
        reponse = self.api.patch(
            url_detail(calepinage.pk),
            {'titre': 'Villa Anfa', 'responsable': self.tech.pk}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def test_technicien_responsable_d_equipe_d_acal_126(self):
        # D-ACAL-126 : « Technicien responsable » lit les calepinages des visites
        # de son sous-arbre ; il est donc admis quand un technicien de SON équipe
        # a la visite — et refusé sans visite d'équipe sur le lead.
        resp = User.objects.create_user(
            username='cal_api_resp', password='x', company=self.company,
            role=Role.objects.create(
                company=self.company, nom='Technicien responsable',
                permissions=list(TECHNICIEN_RESP_PERMISSIONS)))
        User.objects.filter(pk=self.tech.pk).update(supervisor=resp)
        self.assertEqual(self.api.post(
            URL, {'lead': self.lead.pk, 'responsable': resp.pk},
            format='json').status_code, 400)
        self._visite(self.tech)
        reponse = self.api.post(URL, {'lead': self.lead.pk,
                                      'responsable': resp.pk}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(
            self._client(resp).get(url_detail(reponse.data['id'])).status_code, 200)

    def test_donnee_d_avant_lot_8_confiee_sans_visite_404_et_signalee(self):
        # Lot 8 (T4-X3-016) — la RÈGLE ne bouge pas (D-ACAL-106/126, choix 17) :
        # un calepinage déjà confié à un technicien sans visite sur le lead lui
        # reste introuvable ; la fiche de l'administrateur le dit.
        confie = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa',
            responsable=self.tech)
        api_tech = self._client(self.tech)
        self.assertEqual(api_tech.get(url_detail(confie.pk)).status_code, 404)
        self.assertNotIn(confie.pk, {ligne['id'] for ligne in self._lignes(
            api_tech.get(URL))})
        self.assertIs(self.api.get(url_detail(confie.pk)).data[
            'responsable_sans_acces'], True)
        # Une visite sur le lead : il l'ouvre, plus rien n'est signalé.
        self._visite(self.tech)
        self.assertEqual(api_tech.get(url_detail(confie.pk)).status_code, 200)
        self.assertIs(self.api.get(url_detail(confie.pk)).data[
            'responsable_sans_acces'], False)

    def test_detail_signale_le_seul_responsable_qui_ne_peut_pas_ouvrir(self):
        sans = Calepinage.objects.create(company=self.company, lead_id=self.lead.pk,
                                         titre='Sans responsable')
        directeur = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_2.pk, titre='Directeur',
            responsable=self.user)
        sans_lead = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Client seul',
            responsable=self.tech)
        for calepinage, attendu in ((sans, False), (directeur, False),
                                    (sans_lead, True)):
            detail = self.api.get(url_detail(calepinage.pk)).data
            self.assertIs(detail['responsable_sans_acces'], attendu,
                          calepinage.titre)


class CreationTest(BaseApiCalepinage):
    def test_creation_sur_lead(self):
        reponse = self.api.post(URL, {'lead': self.lead.pk,
                                      'titre': 'Villa Anfa'}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        calepinage = Calepinage.objects.get(pk=reponse.data['id'])
        self.assertEqual(calepinage.company_id, self.company.pk)
        self.assertEqual(calepinage.lead_id, self.lead.pk)
        self.assertEqual(calepinage.cree_par_id, self.user.pk)

    def test_creation_sur_client(self):
        reponse = self.api.post(URL, {'client': self.client_a.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(
            Calepinage.objects.get(pk=reponse.data['id']).client_id,
            self.client_a.pk)

    def test_les_deux_refuses_en_nommant_le_champ(self):
        """ACAL179 — lead ET client sont admis, mais un client INCOHÉRENT
        avec le lead (ici : le lead n'a pas ce client) est refusé en nommant
        ``client`` ; le client DU lead passe."""
        reponse = self.api.post(
            URL, {'lead': self.lead.pk, 'client': self.client_a.pk},
            format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('client', reponse.data)
        self.lead.client = self.client_a
        self.lead.save(update_fields=['client'])
        coherent = self.api.post(
            URL, {'lead': self.lead.pk, 'client': self.client_a.pk},
            format='json')
        self.assertEqual(coherent.status_code, 201, coherent.data)

    def test_aucun_des_deux_refuse_en_nommant_le_champ(self):
        reponse = self.api.post(URL, {'titre': 'Orphelin'}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('client', reponse.data)

    def test_lead_d_une_autre_societe_introuvable(self):
        lead_voisin = Lead.objects.create(company=self.autre, nom='Voisin')
        reponse = self.api.post(URL, {'lead': lead_voisin.pk}, format='json')
        # ENF11 — id bien formé qui ne désigne rien de la société : 404.
        self.assertEqual(reponse.status_code, 404)
        self.assertIn('lead', reponse.data)

    def test_lead_inexistant_404_comme_un_lead_etranger(self):
        reponse = self.api.post(URL, {'lead': 99999999}, format='json')
        self.assertEqual(reponse.status_code, 404)
        self.assertIn('lead', reponse.data)

    def test_patch_multipart_refuse_json_seul(self):
        # ENF11 — ``contraintes_site`` est un objet JSON : le PATCH n'accepte
        # que du JSON (un formulaire n'en porte que des chaînes).
        from apps.calepinage.models import Calepinage
        cal = Calepinage.objects.create(company=self.company,
                                        lead_id=self.lead.pk, titre='P')
        reponse = self.api.patch(f'{URL}{cal.pk}/',
                                 {'contraintes_site': 'pas du json'},
                                 format='multipart')
        self.assertEqual(reponse.status_code, 415, reponse.content)

    def test_client_d_une_autre_societe_refuse(self):
        client_voisin = Client.objects.create(company=self.autre,
                                              nom='Client voisin')
        reponse = self.api.post(URL, {'client': client_voisin.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 404)
        self.assertIn('client', reponse.data)

    def test_company_du_corps_est_ignoree(self):
        reponse = self.api.post(
            URL, {'lead': self.lead.pk, 'company': self.autre.pk},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(
            Calepinage.objects.get(pk=reponse.data['id']).company_id,
            self.company.pk)

    def test_sans_permission_d_ecriture_403(self):
        reponse = self.api_sans.post(URL, {'lead': self.lead.pk},
                                     format='json')
        self.assertEqual(reponse.status_code, 403)


# ═══════════════════════════════════════════════════════════════════════════
# Copilote vague 2 (lane CALA) — ce que l'assistant lit et écrit du calepinage.
# Les formes servies sont comparées aux échantillons COMMITTÉS
# (``contrats_assistant.CONTRATS_ASSISTANT``) : un renommage côté vue rougit ici.
# ═══════════════════════════════════════════════════════════════════════════

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
        from apps.calepinage.services.assistant import A_FAIRE, _premier_blocage

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
                self.assertEqual(_premier_blocage(signaux), attendu)
                self.assertIn(attendu, A_FAIRE)
        self.assertEqual(_premier_blocage(('devis_absent',), a_retenir=True),
                         'retenir')
        self.assertEqual(_premier_blocage(('sans_pose',), archive=True), 'rien')

    def test_lien_par_la_table_des_ecrans(self):
        from apps.calepinage.services.assistant import _lien_du_geste

        self.assertEqual(_lien_du_geste(14, 'corriger_electrique'),
                         '/calepinage/14?onglet=verdict-electrique')
        self.assertEqual(_lien_du_geste(12, 'publier'), '/calepinage/12')


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

    def test_avertissements_regroupes_comme_le_parcours_guide(self):
        # ACAL392 — la phrase « aucune norme » levée par trois postes
        # n'occupe plus les deux places : une ligne « (× 3) », puis la
        # suivante (rouge si le résumé recopie la liste brute).
        from unittest import mock

        norme = 'Aucune norme électrique sélectionnée : câbles non vérifiés.'
        resultat = {'avertissements': [norme, norme, norme,
                                       'Simulation périmée : relancez-la.']}
        with mock.patch('apps.calepinage.selectors.resultat_servi',
                        return_value=resultat):
            avertissements = self.api.get(url_assistant(
                'resume/', self.cal.pk)).data['avertissements']
        self.assertEqual(avertissements, [
            norme + ' (× 3)', 'Simulation périmée : relancez-la.'])

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


class ConfirmationTailleAssistantTest(SimpleTestCase):
    """Critique 22/11 (D6, ACAL922) — l'aperçu ANNONCE la question de taille
    (mot pour mot celle de ``generer-devis``) au lieu d'échouer ; la
    publication accepte ``confirmer_taille``, relayé tel quel."""

    def test_l_apercu_annonce_la_question_mot_pour_mot(self):
        from decimal import Decimal
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services import devis as service_devis
        from apps.calepinage.services.assistant import _question_de_taille

        devis = SimpleNamespace(etude_params={'puissance_kwc': 34.08},
                                total_ttc=Decimal('168800'))
        cree = {'deduplique': False}
        with mock.patch.object(service_devis, 'taille_non_dimensionnee',
                               return_value={'refus': 'Renseignez la facture.'}):
            question = _question_de_taille(object(), devis, 'genere', cree)
            self.assertIsNone(_question_de_taille(object(), devis, 'resynchronise', cree))
            self.assertIsNone(_question_de_taille(object(), devis, 'genere',
                                                  {'deduplique': True}))
        self.assertEqual(question, {
            'detail': 'Aucune facture ni taille souhaitée sur le lead : le devis remplit '
                      'le toit (34,08 kWc, 168 800,00 MAD TTC). Confirmez, ou renseignez '
                      'la facture du lead.',
            'refus': 'Renseignez la facture.'})
        with mock.patch.object(service_devis, 'taille_non_dimensionnee', return_value=None):
            self.assertIsNone(_question_de_taille(object(), devis, 'genere', cree))
        self.assertIn('confirmation_taille', echantillon(
            'calepinage_assistant_publier_apercu.json', 'exemple_generer'))

    def test_la_publication_accepte_la_confirmation(self):
        from apps.calepinage.agent_actions import PUBLIER_DEVIS
        from apps.calepinage.views.assistant import CHAMPS_PUBLIER

        self.assertIn('confirmer_taille', CHAMPS_PUBLIER)
        self.assertEqual(PUBLIER_DEVIS.inputs['properties']['confirmer_taille']['type'],
                         'boolean')
        self.assertNotIn('confirmer_taille', PUBLIER_DEVIS.inputs['required'])


class DevisExistantAssistantTest(SimpleTestCase):
    """CFIN2 (recette R2-22, patron ACAL922) — le lead a déjà un brouillon libre :
    l'aperçu ANNONCE ``devis_existant`` (référence, les deux choix) au lieu
    d'échouer ; la publication accepte le choix EXPLICITE relayé tel quel."""

    EXISTANT = json.loads((DOSSIER_CONTRATS / 'calepinage_publication.json').read_text(
        encoding='utf-8'))['exemple_409_devis_existant']

    def _apercu(self, choix_devis=None):
        from contextlib import nullcontext
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services import assistant as service
        from apps.calepinage.services.devis import DevisRefuse

        question = DevisRefuse(self.EXISTANT['detail'], champ='rattacher_devis', statut=409,
                               donnees=dict(self.EXISTANT))
        calepinage = SimpleNamespace(pk=16, roof_layout={})
        with mock.patch.object(service, '_refuser_avant_publication', return_value=None), \
                mock.patch.object(service, '_sans_affiche', side_effect=lambda c: c), \
                mock.patch.object(service, '_publier', side_effect=question) as ecriture, \
                mock.patch('django.db.transaction.atomic', return_value=nullcontext()), \
                mock.patch('apps.calepinage.services.presentation.reference_calepinage',
                           return_value='CAL-2611-0016'):
            reponse = service.apercu_publication(calepinage, user=None, choix_devis=choix_devis)
        return reponse, ecriture

    def test_l_apercu_annonce_le_devis_existant(self):
        reponse, _ecriture = self._apercu()
        self.assertEqual(sorted(reponse), sorted(echantillon(
            'calepinage_assistant_publier_apercu.json', 'exemple_generer_devis_existant')))
        self.assertEqual(reponse['a_faire'], 'choisir')
        self.assertIsNone(reponse['nouveau_total_ttc'])
        self.assertEqual(reponse['devis_existant'], {
            cle: self.EXISTANT[cle] for cle in ('detail', 'devis', 'reference', 'total_ttc')})
        for cle in ('exemple', 'exemple_generer', 'exemple_generer_confirmation_taille'):
            self.assertIn('devis_existant', echantillon(
                'calepinage_assistant_publier_apercu.json', cle), cle)

    def test_l_apercu_relaie_le_choix(self):
        choix = {'rattacher_devis': None, 'creer_autre_devis': True}
        _reponse, ecriture = self._apercu(choix)
        self.assertEqual(ecriture.call_args.kwargs.get('choix_devis'), choix)

    def test_publier_relaie_le_choix_au_pont_devis(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services import devis as service_devis
        from apps.calepinage.services.assistant import _publier, _question_de_taille

        brouillon = SimpleNamespace(pk=self.EXISTANT['devis'])
        with mock.patch.object(service_devis, '_devis_lie_actif', return_value=None), \
                mock.patch.object(service_devis, 'generer_devis',
                                  return_value=(brouillon, False)) as generer:
            geste, devis, details = _publier(
                object(), None, choix_devis={'rattacher_devis': brouillon.pk,
                                             'creer_autre_devis': False})
        self.assertEqual((geste, devis), ('genere', brouillon))
        self.assertEqual((generer.call_args.kwargs['rattacher_devis'],
                          generer.call_args.kwargs['creer_autre_devis']), (brouillon.pk, False))
        self.assertTrue(details['rattache'])
        # La garde de taille s'applique aussi au rattachement : la question est annoncée.
        with mock.patch.object(service_devis, 'taille_non_dimensionnee',
                               return_value={'refus': 'Renseignez la facture.'}):
            question = _question_de_taille(object(), SimpleNamespace(
                etude_params={'puissance_kwc': 5.0}, total_ttc=1), 'genere', details)
        self.assertIsNotNone(question)

    def test_vue_et_actions_declarent_le_choix(self):
        from types import SimpleNamespace

        from apps.calepinage.agent_actions import PUBLIER_APERCU, PUBLIER_DEVIS
        from apps.calepinage.views.assistant import CHAMPS_PUBLIER, choix_devis_existant

        for action in (PUBLIER_APERCU, PUBLIER_DEVIS):
            proprietes = action.inputs['properties']
            self.assertEqual(proprietes['rattacher_devis']['type'], 'integer', action.key)
            self.assertEqual(proprietes['creer_autre_devis']['type'], 'boolean', action.key)
            self.assertNotIn('rattacher_devis', action.inputs['required'])
        self.assertTrue({'rattacher_devis', 'creer_autre_devis'} <= set(CHAMPS_PUBLIER))
        lire = lambda **brut: choix_devis_existant(SimpleNamespace(query_params=brut))  # noqa: E731
        self.assertEqual(lire(), (None, None))
        self.assertEqual(lire(rattacher_devis='7'),
                         ({'rattacher_devis': 7, 'creer_autre_devis': False}, None))
        self.assertEqual(lire(creer_autre_devis='True'),
                         ({'rattacher_devis': None, 'creer_autre_devis': True}, None))
        for brut in ({'rattacher_devis': 'x'}, {'creer_autre_devis': 'oui'}):
            choix, refuse = lire(**brut)
            self.assertIsNone(choix)
            self.assertEqual((refuse.status_code, refuse.data['field']),
                             (400, next(iter(brut))))
        self.assertIn('corps_rattacher_devis', json.loads(
            (DOSSIER_CONTRATS / 'calepinage_assistant_publier_devis.json').read_text(encoding='utf-8')))


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

    def test_devis_envoye_exige_d_etre_nomme(self):
        """Revue 2B — la confirmation d'une correction d'un devis ENVOYÉ nomme
        ce devis : sans ``devis`` recopié de l'aperçu, ou avec un autre, 409."""
        from unittest import mock

        from apps.calepinage.services import assistant as service

        devis = self._lier('envoye')
        with mock.patch.object(service, '_refuser_avant_publication', return_value=devis), \
                mock.patch.object(service, '_publier') as ecriture:
            sans = self._poster({'ancien_total_ttc': '84500.00',
                                 'nouveau_total_ttc': '86900.00'})
            autre = self._poster({'ancien_total_ttc': '84500.00',
                                  'nouveau_total_ttc': '86900.00', 'devis': devis.pk + 1})
        self.assertEqual((sans.status_code, sans.data['code']), (409, 'devis_a_nommer'))
        self.assertIn(devis.reference, sans.data['detail'])
        self.assertEqual((autre.status_code, autre.data['code']), (409, 'devis_autre'))
        ecriture.assert_not_called()
        self.assertEqual(self._poster({'nouveau_total_ttc': '86900.00',
                                       'devis': 'x'}).status_code, 400)

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
                                    'nouveau_total_ttc': '86900.00', 'devis': devis.pk})
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['code'], 'apercu_perime')
        self.assertIn('87', reponse.data['detail'])

    def test_lead_sans_facture_apercu_annonce_puis_publication_confirmee(self):
        """Critique 22/11 (D6, ACAL922) — lead sans facture ni taille : l'aperçu
        rend 200 avec la question (plus de 409) ; publier sans la confirmation
        ⇒ 409 ``confirmation_taille``, aucun devis ; confirmée ⇒ généré."""
        import copy

        from apps.calepinage.services.layout import enregistrer_layout
        from apps.ventes.models import Devis
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue

        from .test_acal_generer_devis_portes import TOIT

        seed_catalogue(self.company)
        enregistrer_layout(self.cal, copy.deepcopy(TOIT), user=self.user)
        apercu = self.api.get(url_assistant('publier-devis/apercu/', self.cal.pk))
        self.assertEqual(apercu.status_code, 200, apercu.data)
        self.assertEqual(sorted(apercu.data), sorted(echantillon(
            'calepinage_assistant_publier_apercu.json', 'exemple_generer')))
        self.assertTrue(apercu.data['confirmation_taille']['detail'].startswith(
            'Aucune facture ni taille souhaitée sur le lead'))
        corps = {'nouveau_total_ttc': apercu.data['nouveau_total_ttc']}
        avant = Devis.objects.filter(company=self.company).count()
        refus = self._poster(corps)
        self.assertEqual((refus.status_code, refus.data.get('code')),
                         (409, 'confirmation_taille'), refus.data)
        self.assertEqual(Devis.objects.filter(company=self.company).count(), avant)
        reponse = self._poster({**corps, 'confirmer_taille': True})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['geste'], 'genere')
        self.assertEqual(self._poster({**corps, 'confirmer_taille': 'oui'}).status_code, 400)

    def test_actions_du_flux_en_deux_temps(self):
        from apps.calepinage.agent_actions import PUBLIER_APERCU, PUBLIER_DEVIS

        self.assertEqual((PUBLIER_APERCU.method, PUBLIER_APERCU.risk), ('GET', RISK_INTERNAL))
        self.assertEqual(PUBLIER_DEVIS.risk, 'outward')
        self.assertEqual(PUBLIER_DEVIS.required_permission, 'calepinage_gerer')
        self.assertEqual(PUBLIER_APERCU.required_permission, 'calepinage_gerer')
        self.assertEqual(set(PUBLIER_DEVIS.inputs['properties']),
                         {'id', 'ancien_total_ttc', 'nouveau_total_ttc', 'devis',
                          'confirmer_taille', 'rattacher_devis', 'creer_autre_devis'})
        self.assertEqual(PUBLIER_DEVIS.objets, {'id': 'calepinage', 'devis': 'devis',
                                                'rattacher_devis': 'devis'})
        self.assertIn('déjà envoyé au client', PUBLIER_DEVIS.label)

    def test_r2_22_brouillon_anterieur_annonce_puis_choix_relaye(self):
        """CFIN2 (R2-22) — le lead a un brouillon libre né AVANT ce calepinage :
        l'aperçu l'ANNONCE (200, ``a_faire: choisir``, rien d'écrit) ; publier
        sans réponse ⇒ 409 ``devis_existant`` ; « rattacher » relayé (aperçu
        puis publication) ⇒ le brouillon existant, aucun devis de plus."""
        import copy

        from django.utils import timezone

        from apps.calepinage.services.layout import enregistrer_layout
        from apps.ventes.models import Devis
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue

        from .test_acal_generer_devis_portes import TOIT

        seed_catalogue(self.company)
        ancien = Devis.objects.create(company=self.company, client=self.client_a,
                                      lead=self.lead, reference='DEV-CFIN2-0001')
        Calepinage.objects.filter(pk=self.cal.pk).update(created_at=timezone.now())
        enregistrer_layout(self.cal, copy.deepcopy(TOIT), user=self.user)
        avant = Devis.objects.filter(company=self.company).count()
        apercu = self.api.get(url_assistant('publier-devis/apercu/', self.cal.pk))
        self.assertEqual(apercu.status_code, 200, apercu.data)
        self.assertEqual(sorted(apercu.data), sorted(echantillon(
            'calepinage_assistant_publier_apercu.json', 'exemple_generer_devis_existant')))
        self.assertEqual((apercu.data['a_faire'], apercu.data['devis_existant']['devis']),
                         ('choisir', ancien.pk))
        self.assertEqual(Devis.objects.filter(company=self.company).count(), avant)
        sans = self._poster({'nouveau_total_ttc': '1.00', 'confirmer_taille': True})
        self.assertEqual((sans.status_code, sans.data.get('code')), (409, 'devis_existant'), sans.data)
        rattache = self.api.get(url_assistant('publier-devis/apercu/', self.cal.pk)
                                + f'?rattacher_devis={ancien.pk}')
        self.assertEqual((rattache.status_code, rattache.data['a_faire']), (200, 'publier'), rattache.data)
        reponse = self._poster({'nouveau_total_ttc': rattache.data['nouveau_total_ttc'],
                                'confirmer_taille': True, 'rattacher_devis': ancien.pk})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['devis'], ancien.pk)
        self.assertEqual(Devis.objects.filter(company=self.company).count(), avant)
        self.assertEqual(self.api.get(url_assistant('publier-devis/apercu/', self.cal.pk)
                                      + '?creer_autre_devis=oui').status_code, 400)


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
                                      client=self.client_a,
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

    def test_sans_panneau_designe_celui_du_devis_automatique_est_dit(self):
        from unittest import mock

        with mock.patch('apps.ventes.selectors_assistant.panneau_par_defaut_id',
                        return_value=self.panneau.pk):
            reponse = self._estimer(lead=self.lead_2.pk, origine='dicte', longueur_m='10',
                                    largeur_m='6', toit_plat='true')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['produit']['id'], self.panneau.pk)
        self.assertTrue(any(s.startswith('Panneau non précisé') and self.panneau.nom in s
                            for s in reponse.data['suppositions']), reponse.data['suppositions'])

    def test_sans_panneau_designe(self):
        from unittest import mock

        with mock.patch('apps.ventes.selectors_assistant.panneau_par_defaut_id',
                        return_value=None):
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
        # 400 : hors du schéma publié (inconnu, hors borne, hors énumération) ;
        # 409 : règles ENTRE paramètres, qu'un schéma ne sait pas dire.
        cas = (
            ({'origine': 'dicte', 'longueur_m': '10', 'largeur_m': '6', 'toit_plat': 'true',
              'company': '2'}, 'company', 400),
            ({'origine': 'visite', 'longueur_m': '10'}, 'longueur_m', 409),
            ({'origine': 'dicte', 'longueur_m': '900', 'largeur_m': '6', 'toit_plat': 'true'},
             'longueur_m', 400),
            ({'origine': 'dicte', 'longueur_m': '10', 'largeur_m': '6'}, 'pente_deg', 409),
            ({'origine': 'dicte', 'largeur_m': '6', 'toit_plat': 'true'}, 'longueur_m', 409),
            ({'origine': 'satellite'}, 'origine', 400),
        )
        for params, champ, statut in cas:
            with self.subTest(champ=champ):
                reponse = self._estimer(lead=self.lead_2.pk, **params)
                self.assertEqual(reponse.status_code, statut, reponse.data)
                self.assertEqual(reponse.data['field'], champ)

    def test_lead_d_une_autre_societe_introuvable(self):
        reponse = self._dicte(api=self.api_autre, toit_plat='true')
        self.assertEqual(reponse.status_code, 404, reponse.data)


class BriefCalepinageTest(BaseAssistantCalepinage):
    """CALA11 — ``selectors.brief_calepinage`` : le bloc du point du matin."""

    def test_forme_du_bloc_et_lignes_de_la_file(self):
        import datetime

        from apps.calepinage.selectors import LIGNES_BRIEF, brief_calepinage

        for rang in range(LIGNES_BRIEF + 2):
            Calepinage.objects.create(company=self.company, titre=f'Brief {rang}',
                                      client=self.client_a,
                                      responsable=self.user, cree_par=self.user)
        bloc = brief_calepinage(self.user, datetime.date.today())
        self.assertEqual(set(bloc), {'total', 'lignes'})
        self.assertEqual(len(bloc['lignes']), LIGNES_BRIEF)
        self.assertGreaterEqual(bloc['total'], LIGNES_BRIEF + 2)
        ligne_contrat = echantillon('calepinage_assistant_a_traiter.json')['lignes'][0]
        for ligne in bloc['lignes']:
            self.assertEqual(set(ligne), set(ligne_contrat))

    def test_fenetre_de_30_jours_depuis_aujourdhui(self):
        import datetime

        from apps.calepinage.selectors import brief_calepinage

        bien_plus_tard = datetime.date.today() + datetime.timedelta(days=60)
        self.assertEqual(brief_calepinage(self.user, bien_plus_tard)['lignes'], [])

    def test_absent_sans_droit_de_lecture(self):
        from apps.calepinage.selectors import brief_calepinage

        sans = Role.objects.create(company=self.company, nom='SansCalepinage', permissions=[])
        compte = User.objects.create_user(username='cala_sans', password='x',
                                          company=self.company, role=sans)
        self.assertIsNone(brief_calepinage(compte))


def _garde_de_la_route(action):
    """Le code de permission que la ROUTE de ``action`` exige pour SA méthode :
    la garde de l'``@action`` (``code``), ou ``read_permission`` /
    ``write_permission`` d'une vue ``ScopedPermission`` — résolu par l'URLconf
    réelle, jamais lu comme un texte."""
    import re

    from django.urls import resolve

    chemin = re.sub(r'\{[a-z_]+\}', '1', action.endpoint)
    vue = resolve(chemin).func
    methode = action.method.lower()
    classe = getattr(vue, 'cls', None) or getattr(vue, 'view_class', None)
    nom_action = (getattr(vue, 'actions', None) or {}).get(methode)
    if nom_action:
        gardes = getattr(classe, nom_action).kwargs.get('permission_classes') or ()
        codes = {getattr(garde, 'code', None) for garde in gardes}
        return codes - {None}
    return {classe.read_permission if methode == 'get' else classe.write_permission}


class ContenanceTraceToitPlatTest(SimpleTestCase):
    """ACAL1923 — origine « trace » : un pan plat qui porte la valeur du
    curseur (22) se lit pente 0, comme un pan plat à 0 (calcul pur)."""

    def _lignes(self, valeur):
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services import contenance

        pan = {'id': 'z1', 'label': 'Pan 1', 'roofType': 'flat', 'pitchDeg': valeur,
               'vertices': [[0, 0], [1, 0], [1, 1]]}
        sortie = {'traduction': SimpleNamespace(politique=SimpleNamespace(code='ANTI_OMBRAGE'),
                                                regle_retrait='r', regle_allee='a'),
                  'resultat': SimpleNamespace(modules=10, optimal=True)}
        with mock.patch('apps.calepinage.villa_service.calepiner_pan_traduit',
                        return_value=sortie):
            lignes, _regles = contenance._zones_du_trace(
                SimpleNamespace(roof_layout={'zones': [pan]}), None, {}, 710)
        return lignes

    def test_pan_plat_a_22_rend_la_meme_ligne_qu_a_0(self):
        a_22, a_0 = self._lignes(22.0), self._lignes(0.0)
        self.assertEqual(a_22, a_0)
        self.assertEqual(a_22[0]['pente_deg'], 0.0)


class ManifesteEtPermissionsTest(SimpleTestCase):
    """CALA12 — toutes les actions ``calepinage.*`` : la permission du catalogue
    est la garde de la route (assertion LOCALE de la parité FND14), une
    écriture exige ``calepinage_gerer``, une lecture ``calepinage_voir`` ;
    le manifeste nomme le module et chaque clé y est attribuée (ARC33)."""

    def test_permission_du_catalogue_egale_garde_de_la_route(self):
        from apps.calepinage.agent_actions import ACTIONS

        for action in ACTIONS:
            with self.subTest(action=action.key):
                self.assertIn(action.required_permission, _garde_de_la_route(action))

    def test_ecritures_et_lectures(self):
        from apps.calepinage.agent_actions import ACTIONS

        for action in ACTIONS:
            with self.subTest(action=action.key):
                # L'aperçu de la publication joue le chemin de l'écriture
                # (verrous compris, transaction annulée) : garde de l'écriture.
                lecture = (action.method == 'GET'
                           and action.key != 'calepinage.publier_apercu')
                attendu = 'calepinage_voir' if lecture else 'calepinage_gerer'
                self.assertEqual(action.required_permission, attendu)
                if action.risk == 'outward':
                    self.assertTrue(action.confirm_summary)
                    self.assertTrue(action.objets)

    def test_les_cles_attendues_et_rien_d_autre(self):
        from apps.calepinage.agent_actions import ACTIONS

        self.assertEqual({a.key for a in ACTIONS}, {
            'calepinage.du_lead', 'calepinage.resume', 'calepinage.variantes_comparer',
            'calepinage.simulation_suivre', 'calepinage.simuler', 'calepinage.preparer',
            'calepinage.publier_apercu', 'calepinage.publier_devis', 'calepinage.retenir',
            'calepinage.a_traiter', 'calepinage.contenance'})
        interdites = {'calepinage.approuver', 'calepinage.pack_technique'}
        self.assertEqual({a.key for a in ACTIONS} & interdites, set())

    def test_le_manifeste_attribue_les_cles_au_module(self):
        from apps.agent import registry
        from apps.calepinage.agent_actions import ACTIONS

        registry.autodiscover_from_platform_manifests()
        attribuees = registry._DISCOVERED.get('apps.calepinage.agent_actions', set())
        self.assertEqual({a.key for a in ACTIONS} - attribuees, set())

    def test_chaque_route_neuve_a_son_contrat_cite(self):
        from apps.calepinage.agent_actions import ACTIONS

        neuves = [a for a in ACTIONS if any(
            segment in a.endpoint for segment in ('resume/', 'du-lead/', 'a-traiter/',
                                                  'contenance/', 'preparer/', 'publier-devis/'))]
        self.assertEqual(len(neuves), 7)
        self.assertEqual(len(CONTRATS_ASSISTANT), 7)
