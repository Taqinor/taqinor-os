"""ZSAL3 — CRUD des équipes commerciales (Paramètres → CRM), distinct du
dashboard « Mes équipes » (tests_zsal3_equipes.py, qui couvre stats_equipe()).

Covers:
  - Lecture ouverte à tout rôle, écriture réservée au palier ADMIN
    (ACRM26 : une équipe pilote une portée — un responsable non admin ne
    s'y nomme plus).
  - Société forcée côté serveur (jamais acceptée du corps de la requête).
  - Isolation multi-tenant (une équipe d'une autre société n'apparaît jamais,
    n'est jamais modifiable/supprimable via l'API).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import EquipeCommerciale

User = get_user_model()


def make_company(slug='zsal3crud-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


class TestEquipeCommercialeCRUD(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other_company = make_company('zsal3crud-other')
        # ACRM26 — l'écriture des équipes est réservée au palier admin.
        self.resp = User.objects.create_user(
            username='zsal3cruresp', password='x', role_legacy='admin',
            company=self.company)
        self.commercial = User.objects.create_user(
            username='zsal3crucommercial', password='x', company=self.company)
        self.api = APIClient()

    def auth_as(self, user):
        token = AccessToken.for_user(user)
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_responsable_cree_une_equipe_societe_forcee(self):
        self.auth_as(self.resp)
        resp = self.api.post('/api/django/crm/equipes/', {
            'nom': 'Équipe Sud',
            'company': self.other_company.id,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        equipe = EquipeCommerciale.objects.get(id=resp.data['id'])
        self.assertEqual(equipe.company_id, self.company.id)

    def test_commercial_peut_lire_mais_pas_creer(self):
        EquipeCommerciale.objects.create(company=self.company, nom='Équipe Nord')
        self.auth_as(self.commercial)
        resp = self.api.get('/api/django/crm/equipes/')
        self.assertEqual(resp.status_code, 200)
        create_resp = self.api.post(
            '/api/django/crm/equipes/', {'nom': 'Tentative'}, format='json')
        self.assertEqual(create_resp.status_code, 403)

    def test_membres_et_nb_membres_reflete_la_composition(self):
        equipe = EquipeCommerciale.objects.create(
            company=self.company, nom='Équipe Ouest')
        equipe.membres.set([self.commercial])
        self.auth_as(self.resp)
        resp = self.api.get(f'/api/django/crm/equipes/{equipe.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_membres'], 1)
        self.assertIn(self.commercial.id, resp.data['membres'])

    def test_cross_company_404_sur_detail_update_delete(self):
        equipe_autre = EquipeCommerciale.objects.create(
            company=self.other_company, nom='Équipe Ailleurs')
        self.auth_as(self.resp)
        get_resp = self.api.get(f'/api/django/crm/equipes/{equipe_autre.id}/')
        self.assertEqual(get_resp.status_code, 404)
        patch_resp = self.api.patch(
            f'/api/django/crm/equipes/{equipe_autre.id}/',
            {'nom': 'Renommée'}, format='json')
        self.assertEqual(patch_resp.status_code, 404)
        del_resp = self.api.delete(f'/api/django/crm/equipes/{equipe_autre.id}/')
        self.assertEqual(del_resp.status_code, 404)
        equipe_autre.refresh_from_db()
        self.assertEqual(equipe_autre.nom, 'Équipe Ailleurs')

    def test_responsable_archive_une_equipe(self):
        equipe = EquipeCommerciale.objects.create(
            company=self.company, nom='Équipe À archiver')
        self.auth_as(self.resp)
        resp = self.api.patch(
            f'/api/django/crm/equipes/{equipe.id}/', {'actif': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        equipe.refresh_from_db()
        self.assertFalse(equipe.actif)


class TestEquipeStructurePersonnel(TestCase):
    """Fondateur 26/10/2026 — l'équipe est la source de « qui encadre qui » :
    son responsable devient le superviseur de ses membres, une personne
    n'appartient qu'à une équipe, et une seule équipe reçoit les leads."""

    URL = '/api/django/crm/equipes/'

    def setUp(self):
        self.company = make_company('structure-co')
        self.admin = User.objects.create_user(
            username='struct_admin', password='x', role_legacy='admin',
            company=self.company)
        self.chef = User.objects.create_user(
            username='struct_chef', password='x', company=self.company)
        self.m1 = User.objects.create_user(
            username='struct_m1', password='x', company=self.company)
        self.m2 = User.objects.create_user(
            username='struct_m2', password='x', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _creer(self, nom, membres, responsable=None, **extra):
        r = self.api.post(self.URL, {
            'nom': nom, 'membres': [u.id for u in membres],
            'responsable': responsable.id if responsable else None, **extra,
        }, format='json')
        return r

    def _sup(self, user):
        user.refresh_from_db()
        return user.supervisor_id

    def test_responsable_devient_superviseur_des_membres(self):
        r = self._creer('Casa', [self.m1, self.m2], self.chef)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self._sup(self.m1), self.chef.id)
        self.assertEqual(self._sup(self.m2), self.chef.id)
        self.assertIsNone(self._sup(self.chef))

    def test_membre_retire_ou_equipe_supprimee_libere_le_superviseur(self):
        r = self._creer('Casa', [self.m1, self.m2], self.chef)
        eid = r.data['id']
        r = self.api.patch(f'{self.URL}{eid}/', {'membres': [self.m2.id]},
                           format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(self._sup(self.m1))
        self.assertEqual(self._sup(self.m2), self.chef.id)
        self.assertEqual(self.api.delete(f'{self.URL}{eid}/').status_code, 204)
        self.assertIsNone(self._sup(self.m2))

    def test_une_personne_une_seule_equipe(self):
        self.assertEqual(self._creer('Casa', [self.m1], self.chef).status_code, 201)
        r = self._creer('Rabat', [self.m1])
        # api-fuzz-full 27/10 — refus d'ÉTAT (corps conforme) : 409, ENF11.
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('membres', r.data)

    def test_cycle_refuse(self):
        # m1 encadre déjà le chef : il ne peut pas devenir membre de son équipe.
        self.chef.supervisor = self.m1
        self.chef.save(update_fields=['supervisor'])
        r = self._creer('Casa', [self.m1], self.chef)
        self.assertEqual(r.status_code, 409, r.content)

    def test_une_seule_equipe_recoit_les_leads(self):
        a = self._creer('Casa', [self.m1], self.chef, recoit_leads=True)
        b = self._creer('Rabat', [self.m2], recoit_leads=True)
        self.assertEqual(b.status_code, 201, b.content)
        self.assertFalse(
            EquipeCommerciale.objects.get(pk=a.data['id']).recoit_leads)
        self.assertTrue(
            EquipeCommerciale.objects.get(pk=b.data['id']).recoit_leads)


class TestVisibiliteMembreEquipe(TestCase):
    """Fondateur 26/10/2026 — un Commercial (``records_scope_soi``) ne voit
    pas les leads de ses coéquipiers ; le responsable d'équipe les voit."""

    def test_membre_voit_les_siens_responsable_voit_l_equipe(self):
        from apps.crm.models import Lead
        from apps.crm.selectors import leads_visibles
        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            COMMERCIAL_PERMISSIONS, SCOPE_SELF, SCOPE_TEAM)

        self.assertIn(SCOPE_SELF, COMMERCIAL_PERMISSIONS)
        self.assertNotIn(SCOPE_TEAM, COMMERCIAL_PERMISSIONS)
        company = make_company('visibilite-co')
        role = Role.objects.create(
            company=company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS))
        chef = User.objects.create_user(
            username='vis_chef', password='x', company=company, role=role)
        a = User.objects.create_user(
            username='vis_a', password='x', company=company, role=role,
            supervisor=chef)
        b = User.objects.create_user(
            username='vis_b', password='x', company=company, role=role,
            supervisor=chef)
        la = Lead.objects.create(company=company, nom='A', owner=a)
        lb = Lead.objects.create(company=company, nom='B', owner=b)
        self.assertEqual(
            set(leads_visibles(a, company).values_list('id', flat=True)),
            {la.id})
        self.assertEqual(
            set(leads_visibles(chef, company).values_list('id', flat=True)),
            {la.id, lb.id})


class TestEquipeAnterieureEditable(TestCase):
    """Une équipe d'avant la règle « une seule équipe » dont un membre figure
    aussi ailleurs reste renommable ; seul un AJOUT est contrôlé."""

    def test_renommer_equipe_chevauchante_autorise(self):
        company = make_company('legacy-co')
        admin = User.objects.create_user(
            username='legacy_admin', password='x', role_legacy='admin',
            company=company)
        m = User.objects.create_user(
            username='legacy_m', password='x', company=company)
        e1 = EquipeCommerciale.objects.create(company=company, nom='Un')
        e2 = EquipeCommerciale.objects.create(company=company, nom='Deux')
        e1.membres.set([m])
        e2.membres.set([m])
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin)}')
        r = api.patch(f'/api/django/crm/equipes/{e1.id}/', {'nom': 'Un bis'},
                      format='json')
        self.assertEqual(r.status_code, 200, r.content)


def _cles(valeur):
    """Squelette de clés d'un JSON (listes : leur premier élément)."""
    if isinstance(valeur, dict):
        return {k: _cles(v) for k, v in valeur.items()}
    if isinstance(valeur, list):
        return [_cles(valeur[0])] if valeur else []
    return None


class TestDispatchLeads(TestCase):
    """Fondateur 27/10/2026 — file d'attribution du responsable d'équipe
    (contrat ``contract_samples/dispatch_leads.json``) et sa décision."""

    def setUp(self):
        from apps.crm.leads_attribution import default_responsable_for
        from apps.crm.models import Lead
        from apps.parametres.models import CompanyProfile
        self.company = make_company('dispatch-co')
        CompanyProfile.objects.create(company=self.company)
        mk = User.objects.create_user
        self.chef = mk(username='dsp_chef', password='x', company=self.company)
        self.m1 = mk(username='dsp_m1', password='x', company=self.company,
                     first_name='Sara')
        self.m2 = mk(username='dsp_m2', password='x', company=self.company)
        self.autre_chef = mk(username='dsp_chef2', password='x',
                             company=self.company)
        self.admin = mk(username='dsp_admin', password='x',
                        role_legacy='admin', company=self.company)
        self.equipe = EquipeCommerciale.objects.create(
            company=self.company, nom='Casa', responsable=self.chef,
            recoit_leads=True, confirmation_responsable=True)
        self.equipe.membres.set([self.m1, self.m2])
        self.autre = EquipeCommerciale.objects.create(
            company=self.company, nom='Rabat', responsable=self.autre_chef)
        self.lead = Lead.objects.create(
            company=self.company, nom='Tazi', prenom='Karim',
            ville='Casablanca', owner=default_responsable_for(self.company))
        self.api = APIClient()

    def auth_as(self, user):
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

    def _attribuer(self, user, owner, lead=None):
        self.auth_as(user)
        return self.api.post(
            f'/api/django/crm/dispatch/{(lead or self.lead).pk}/attribuer/',
            {'owner': owner.pk if owner else None}, format='json')

    def test_choix_fait_sur_la_fiche_jamais_defait_par_la_tache(self):
        # Revue Fable 27/10 : le responsable change le propriétaire depuis la
        # fiche du lead ; à l'échéance, la tâche ne le remet pas au proposé.
        import datetime
        from django.utils import timezone
        from apps.crm.dispatch import attribuer_echeances
        from apps.crm.models_clients import AttributionEnAttente
        self.lead.owner = self.m2
        self.lead.save(update_fields=['owner'])
        attribuer_echeances(timezone.now() + datetime.timedelta(days=30))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.owner_id, self.m2.pk)
        self.assertFalse(AttributionEnAttente.objects.filter(
            lead=self.lead).exists())

    def test_changement_de_responsable_rapatrie_la_file(self):
        # Revue Fable 27/10 : les leads en attente suivent le nouveau
        # responsable ; sans responsable, ils partent à leur proposition.
        from apps.crm.models_clients import AttributionEnAttente
        self.auth_as(self.admin)
        url = f'/api/django/crm/equipes/{self.equipe.pk}/'
        r = self.api.patch(url, {'responsable': self.autre_chef.pk},
                           format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.owner_id, self.autre_chef.pk)
        self.assertTrue(AttributionEnAttente.objects.filter(
            lead=self.lead).exists())
        avant = AttributionEnAttente.objects.get(lead=self.lead).echeance
        r = self.api.patch(url, {'responsable': None}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        # Échéance avancée (« maintenant ») : la tâche l'attribue à la minute.
        attente = AttributionEnAttente.objects.get(lead=self.lead)
        self.assertLess(attente.echeance, avant)

    def test_file_reservee_au_responsable_et_a_la_direction(self):
        from apps.roles.models import Role
        rh = Role.objects.create(company=self.company, nom='Admin RH',
                                 permissions=['users_voir'])
        u = User.objects.create_user(username='dsp_rh', password='x',
                                     company=self.company, role=rh)
        self.auth_as(u)
        r = self.api.get('/api/django/crm/dispatch/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['leads'], [])

    def test_file_respecte_le_contrat(self):
        import json
        import pathlib
        chemin = (pathlib.Path(__file__).resolve().parent
                  / 'contract_samples' / 'dispatch_leads.json')
        contrat = json.loads(chemin.read_text(encoding='utf-8'))
        self.auth_as(self.chef)
        r = self.api.get('/api/django/crm/dispatch/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(_cles(r.json()), _cles(contrat['exemple']))
        self.assertEqual(r.json()['en_attente'], 1)
        self.assertEqual(r.json()['leads'][0]['nom'], 'Karim Tazi')
        self.assertEqual(r.json()['equipe']['delai_minutes'], 5)

    def test_file_vide_pour_une_societe_sans_equipe(self):
        seul = User.objects.create_user(
            username='dsp_seul', password='x', company=make_company('dsp-vide'))
        self.auth_as(seul)
        r = self.api.get('/api/django/crm/dispatch/')
        self.assertEqual(r.json(), {'equipe': None, 'en_attente': 0,
                                    'leads': [], 'membres': [],
                                    'equipes_reglables': []})

    def test_responsable_confirme_la_proposition(self):
        from apps.crm.models import LeadActivity
        propose = self.lead.attribution_en_attente.proposee
        r = self._attribuer(self.chef, propose)
        self.assertEqual(r.status_code, 200, r.content)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.owner, propose)
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, body__endswith='(proposition confirmée)').exists())
        # Double clic : le lead n'attend plus → 409.
        self.assertEqual(self._attribuer(self.chef, propose).status_code, 409)

    def test_responsable_choisit_un_autre_membre(self):
        autre = ({self.m1, self.m2}
                 - {self.lead.attribution_en_attente.proposee}).pop()
        self.assertEqual(self._attribuer(self.chef, autre).status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.owner, autre)

    def test_membre_et_responsable_d_une_autre_equipe_refuses(self):
        self.assertEqual(self._attribuer(self.m1, self.m1).status_code, 403)
        self.assertEqual(
            self._attribuer(self.autre_chef, self.m1).status_code, 403)

    def test_admin_peut_attribuer(self):
        self.assertEqual(self._attribuer(self.admin, self.m2).status_code, 200)

    def test_owner_hors_equipe_400(self):
        r = self._attribuer(self.chef, self.autre_chef)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(self._attribuer(self.chef, None).status_code, 400)

    def test_lead_d_une_autre_societe_404(self):
        from apps.crm.models import Lead
        etranger = Lead.objects.create(
            company=make_company('dsp-autre'), nom='Etranger')
        self.assertEqual(
            self._attribuer(self.admin, self.m1, lead=etranger).status_code, 404)

    def test_regles_responsable_de_son_equipe_seulement(self):
        url = '/api/django/crm/regles-attribution/'
        self.auth_as(self.chef)
        r = self.api.post(url, {'equipe': self.equipe.pk, 'membre': self.m1.pk,
                                'villes': 'Casablanca', 'ordre': 1},
                          format='json')
        self.assertEqual(r.status_code, 201, r.content)
        regle = r.json()['id']
        r = self.api.post(url, {'equipe': self.autre.pk,
                                'membre': self.m1.pk}, format='json')
        self.assertIn(r.status_code, (403, 409), r.content)
        self.auth_as(self.autre_chef)
        self.assertEqual(self.api.patch(f'{url}{regle}/', {'ordre': 2},
                                        format='json').status_code, 403)
        self.assertEqual(self.api.delete(f'{url}{regle}/').status_code, 403)
        self.auth_as(self.m1)
        self.assertEqual(self.api.get(f'{url}?equipe={self.equipe.pk}')
                         .status_code, 200)
        self.assertEqual(self.api.post(url, {'equipe': self.equipe.pk,
                                             'membre': self.m1.pk},
                                       format='json').status_code, 403)

    def test_regle_membre_hors_equipe_409_et_societe_forcee(self):
        url = '/api/django/crm/regles-attribution/'
        self.auth_as(self.admin)
        r = self.api.post(url, {'equipe': self.equipe.pk,
                                'membre': self.autre_chef.pk}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        r = self.api.post(url, {'equipe': self.equipe.pk, 'membre': self.m2.pk,
                                'facture_min': '3000.00',
                                'facture_max': '1000.00'}, format='json')
        # api-fuzz-full 28/10 (ENF11) : max < min est une règle entre deux
        # champs, inexprimable au schéma — 409, même corps nommant le champ.
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('facture_max', r.json())
        r = self.api.post(url, {'equipe': self.equipe.pk, 'membre': self.m2.pk,
                                'types_installation': ['agricole'],
                                'sources': ['meta_ads'],
                                'company': make_company('dsp-x').pk},
                          format='json')
        self.assertEqual(r.status_code, 201, r.content)
        from apps.crm.models_clients import RegleAttribution
        self.assertEqual(RegleAttribution.objects.get(
            pk=r.json()['id']).company_id, self.company.pk)

    def test_regles_d_une_autre_societe_invisibles(self):
        from apps.crm.models_clients import RegleAttribution
        etrangere = make_company('dsp-etr')
        eq = EquipeCommerciale.objects.create(company=etrangere, nom='X')
        regle = RegleAttribution.objects.create(company=etrangere, equipe=eq)
        self.auth_as(self.admin)
        r = self.api.get('/api/django/crm/regles-attribution/')
        ids = [x['id'] for x in (r.json().get('results', r.json())
                                 if isinstance(r.json(), dict) else r.json())]
        self.assertNotIn(regle.pk, ids)
        self.assertEqual(self.api.patch(
            f'/api/django/crm/regles-attribution/{regle.pk}/', {'ordre': 3},
            format='json').status_code, 404)

    # ── Réglages par responsable / directeur commercial (fondateur, 28/10/2026)
    def _organigramme(self):
        from apps.roles.models import Departement
        mk = User.objects.create_user
        self.directeur = mk(username='dsp_dir', password='x',
                            company=self.company)
        self.autre_dir = mk(username='dsp_dir2', password='x',
                            company=self.company)
        commercial = Departement.objects.create(
            company=self.company, nom='Commercial', responsable=self.directeur)
        Departement.objects.create(
            company=self.company, nom='Technique', responsable=self.autre_dir)
        self.equipe.departement = commercial
        self.equipe.save(update_fields=['departement'])

    def _reglages(self, user, equipe, corps):
        self.auth_as(user)
        return self.api.patch(f'/api/django/crm/dispatch/reglages/{equipe.pk}/',
                              corps, format='json')

    def test_reglages_matrice_des_droits(self):
        self._organigramme()
        corps = {'delai_minutes': 7}
        for user, attendu in ((self.chef, 200), (self.directeur, 200),
                              (self.admin, 200), (self.autre_dir, 403),
                              (self.autre_chef, 403), (self.m1, 403)):
            r = self._reglages(user, self.equipe, corps)
            self.assertEqual(r.status_code, attendu, (user.username, r.content))
        etrangere = EquipeCommerciale.objects.create(
            company=make_company('dsp-regl-etr'), nom='Ailleurs')
        self.assertEqual(
            self._reglages(self.admin, etrangere, corps).status_code, 404)

    def test_reglages_ecrit_les_deux_champs_seuls(self):
        r = self._reglages(self.chef, self.equipe, {
            'confirmation_responsable': False, 'delai_minutes': 12,
            'nom': 'Pirate', 'recoit_leads': False})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json(), {'id': self.equipe.pk, 'nom': 'Casa',
                                    'confirmation_responsable': False,
                                    'delai_minutes': 12})
        self.equipe.refresh_from_db()
        self.assertEqual(self.equipe.nom, 'Casa')
        self.assertTrue(self.equipe.recoit_leads)
        self.assertFalse(self.equipe.confirmation_responsable)
        self.assertEqual(self.equipe.delai_attribution_minutes, 12)

    def test_reglages_types_json_stricts(self):
        for corps in ({'delai_minutes': 0}, {'delai_minutes': 481},
                      {'delai_minutes': '5'}, {'delai_minutes': True},
                      {'confirmation_responsable': 1},
                      {'confirmation_responsable': 'oui'}):
            r = self._reglages(self.chef, self.equipe, corps)
            self.assertEqual(r.status_code, 400, (corps, r.content))
            self.assertIn(next(iter(corps)), r.json())

    def test_couper_la_confirmation_ne_bloque_aucun_lead(self):
        # Les attentes déjà posées gardent leur échéance : la tâche les
        # attribue toujours à la proposition.
        import datetime
        from django.utils import timezone
        from apps.crm.dispatch import attribuer_echeances
        from apps.crm.models_clients import AttributionEnAttente
        propose = self.lead.attribution_en_attente.proposee
        r = self._reglages(self.chef, self.equipe,
                           {'confirmation_responsable': False})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(AttributionEnAttente.objects.filter(
            lead=self.lead).exists())
        self.assertEqual(
            attribuer_echeances(timezone.now() + datetime.timedelta(days=30)), 1)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.owner_id, propose.pk)

    def test_equipes_reglables_selon_le_role(self):
        self._organigramme()
        EquipeCommerciale.objects.create(
            company=self.company, nom='Archivée', responsable=self.chef,
            actif=False)

        def reglables(user):
            self.auth_as(user)
            r = self.api.get('/api/django/crm/dispatch/')
            self.assertEqual(r.status_code, 200, r.content)
            return [e['nom'] for e in r.json()['equipes_reglables']]

        self.assertEqual(reglables(self.chef), ['Casa'])
        self.assertEqual(reglables(self.directeur), ['Casa'])
        self.assertEqual(reglables(self.autre_chef), ['Rabat'])
        self.assertEqual(reglables(self.admin), ['Casa', 'Rabat'])
        self.assertEqual(reglables(self.autre_dir), [])
        self.assertEqual(reglables(self.m1), [])
        self.auth_as(self.chef)
        ligne = dict(self.api.get('/api/django/crm/dispatch/').json()
                     ['equipes_reglables'][0])
        membres = ligne.pop('membres')
        self.assertEqual(ligne, {'id': self.equipe.pk, 'nom': 'Casa',
                                 'confirmation_responsable': True,
                                 'delai_minutes': 5})
        # Membres ACTIFS servis pour l'éditeur de règles (un responsable au
        # rôle Commercial n'a pas accès à /crm/assignable-users/).
        self.assertEqual({m['id'] for m in membres}, {self.m1.pk, self.m2.pk})

    def test_file_vide_respecte_le_contrat(self):
        import json
        import pathlib
        chemin = (pathlib.Path(__file__).resolve().parent
                  / 'contract_samples' / 'dispatch_leads.json')
        contrat = json.loads(chemin.read_text(encoding='utf-8'))
        self.auth_as(self.m1)
        r = self.api.get('/api/django/crm/dispatch/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(_cles(r.json()), _cles(contrat['exemple_vide']))

    def test_regles_directeur_commercial_de_son_departement(self):
        self._organigramme()
        url = '/api/django/crm/regles-attribution/'
        self.auth_as(self.directeur)
        r = self.api.post(url, {'equipe': self.equipe.pk,
                                'membre': self.m1.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        regle = r.json()['id']
        self.assertEqual(self.api.patch(f'{url}{regle}/', {'ordre': 4},
                                        format='json').status_code, 200)
        self.auth_as(self.autre_dir)
        self.assertEqual(self.api.post(url, {'equipe': self.equipe.pk,
                                             'membre': self.m1.pk},
                                       format='json').status_code, 403)
        self.assertEqual(self.api.patch(f'{url}{regle}/', {'ordre': 2},
                                        format='json').status_code, 403)
        self.assertEqual(self.api.delete(f'{url}{regle}/').status_code, 403)
        self.auth_as(self.admin)
        self.assertEqual(self.api.delete(f'{url}{regle}/').status_code, 204)

    def test_regle_choix_multiples_api(self):
        url = '/api/django/crm/regles-attribution/'
        self.auth_as(self.chef)
        r = self.api.post(url, {
            'equipe': self.equipe.pk, 'membre': self.m1.pk,
            'types_installation': ['agricole', 'industriel', 'agricole'],
            'sources': ['meta_ads', 'site_web']}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['types_installation'],
                         ['agricole', 'industriel'])
        self.assertEqual(r.json()['sources'], ['meta_ads', 'site_web'])
        r = self.api.post(url, {'equipe': self.equipe.pk,
                                'membre': self.m1.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()['types_installation'], r.json()['sources']),
                         ([], []))
        for champ, valeur in (('types_installation', 'agricole'),
                              ('types_installation', ['inconnu']),
                              ('types_installation', [1]),
                              ('sources', {'a': 1}), ('sources', None),
                              ('sources', [''])):
            r = self.api.post(url, {'equipe': self.equipe.pk,
                                    'membre': self.m1.pk, champ: valeur},
                              format='json')
            self.assertEqual(r.status_code, 400, (champ, valeur, r.content))
            self.assertIn(champ, r.json())

    def test_equipe_expose_confirmation_et_delai(self):
        self.auth_as(self.admin)
        url = f'/api/django/crm/equipes/{self.autre.pk}/'
        r = self.api.patch(url, {'confirmation_responsable': True,
                                 'delai_attribution_minutes': 15},
                           format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['delai_attribution_minutes'], 15)
        self.assertEqual(self.api.patch(
            url, {'delai_attribution_minutes': 0}, format='json').status_code, 400)


class TestCockpitEquipe(TestCase):
    """Cockpit d'équipe du responsable (fondateur, 28/10/2026) — contrat
    ``contract_samples/cockpit_equipe.json`` ; objectifs fixés par les mêmes
    personnes (``dispatch.peut_regler``) pour les membres de leurs équipes."""

    URL = '/api/django/crm/cockpit-equipe/'
    OCT = {'periode': 'month', 'annee': 2026, 'mois': 10}

    def setUp(self):
        import datetime
        from decimal import Decimal
        from apps.crm import horaires
        from apps.crm.leads_attribution import default_responsable_for
        from apps.crm.models import (
            Appointment, Client, Lead, ObjectifCommercial, RelanceEtape)
        from apps.parametres.models import CompanyProfile
        from apps.roles.models import Departement
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis
        self.company = make_company('cockpit-co')
        CompanyProfile.objects.create(company=self.company)
        mk = User.objects.create_user
        self.chef = mk(username='ck_chef', password='x', company=self.company,
                       first_name='Meryem')
        self.m1 = mk(username='ck_m1', password='x', company=self.company,
                     first_name='Sara', poste='Chargée de clientèle')
        self.m2 = mk(username='ck_m2', password='x', company=self.company,
                     first_name='Amine')
        self.autre_chef = mk(username='ck_chef2', password='x',
                             company=self.company)
        self.m3 = mk(username='ck_m3', password='x', company=self.company)
        self.directeur = mk(username='ck_dir', password='x',
                            company=self.company)
        self.autre_dir = mk(username='ck_dir2', password='x',
                            company=self.company)
        self.admin = mk(username='ck_admin', password='x', role_legacy='admin',
                        company=self.company)
        commercial = Departement.objects.create(
            company=self.company, nom='Commercial', responsable=self.directeur)
        Departement.objects.create(
            company=self.company, nom='Technique', responsable=self.autre_dir)
        self.equipe = EquipeCommerciale.objects.create(
            company=self.company, nom='Casa', responsable=self.chef,
            departement=commercial, recoit_leads=True,
            confirmation_responsable=True)
        self.equipe.membres.set([self.m1, self.m2])
        self.autre = EquipeCommerciale.objects.create(
            company=self.company, nom='Rabat', responsable=self.autre_chef)
        self.autre.membres.set([self.m3])

        def a(jour, h, mi=0):
            return datetime.datetime(2026, 10, jour, h, mi,
                                     tzinfo=horaires.CASABLANCA)

        # m1 — 3 leads d'octobre : contacté en 2 min ouvrées, en 60 min,
        # jamais contacté (lundi 05 et mardi 06/10, en pleine fenêtre).
        self.leads = []
        for cree, contacte in ((a(5, 10), a(5, 10, 2)), (a(5, 11), a(5, 12)),
                               (a(6, 10), None)):
            lead = Lead.objects.create(company=self.company, nom='Lead',
                                       owner=self.m1)
            Lead.objects.filter(pk=lead.pk).update(
                date_creation=cree, first_contacted_at=contacte)
            self.leads.append(lead)
        self.obj_leads = ObjectifCommercial.objects.create(
            company=self.company, owner=self.m1, metric='nb_leads',
            cible=Decimal('4'), period_type='month', period_year=2026,
            period_month=10)
        Appointment.objects.create(
            company=self.company, lead=self.leads[0], created_by=self.m1,
            scheduled_at=a(7, 10), statut=Appointment.Statut.EFFECTUE)
        # Touche échue en janvier, jamais faite (ordre hors plan : aucune
        # collision avec une touche posée à la création du lead).
        RelanceEtape.objects.create(
            company=self.company, lead=self.leads[2], cadence='contact',
            ordre=99, libelle='Appel', due_date=datetime.date(2026, 1, 5),
            canal=RelanceEtape.Canal.APPEL)
        client = Client.objects.create(company=self.company, nom='Client')
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='CK-P',
            prix_vente=Decimal('1000'), quantite_stock=50)
        for ref, statut in (('DEV-CK-1', 'envoye'), ('DEV-CK-2', 'brouillon')):
            devis = Devis.objects.create(
                company=self.company, reference=ref, client=client,
                lead=self.leads[0], statut=statut, taux_tva=Decimal('20.00'),
                remise_globale=Decimal('0'), created_by=self.m1,
                date_envoi=a(8, 10) if statut == 'envoye' else None)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation='Panneau',
                quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
                remise=Decimal('0'))
            if statut == 'envoye':
                self.envoye = devis
        # Un lead en attente d'attribution (chez le responsable) : proposé au
        # moins chargé, m2.
        self.attente = Lead.objects.create(
            company=self.company, nom='Attente',
            owner=default_responsable_for(self.company))
        self.api = APIClient()

    def auth_as(self, user):
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

    def _get(self, user, **params):
        self.auth_as(user)
        return self.api.get(self.URL, params)

    def _contrat(self):
        import json
        import pathlib
        chemin = (pathlib.Path(__file__).resolve().parent
                  / 'contract_samples' / 'cockpit_equipe.json')
        return json.loads(chemin.read_text(encoding='utf-8'))

    def test_respecte_le_contrat(self):
        r = self._get(self.chef, **self.OCT)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(_cles(r.json()), _cles(self._contrat()['exemple']))
        r = self._get(self.m1)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json(), self._contrat()['exemple_vide'])

    def test_matrice_des_acces(self):
        for user, attendu in ((self.chef, 200), (self.directeur, 200),
                              (self.admin, 200), (self.autre_dir, 403),
                              (self.autre_chef, 403), (self.m1, 403)):
            r = self._get(user, equipe=self.equipe.pk)
            self.assertEqual(r.status_code, attendu, (user.username, r.content))
        etranger = User.objects.create_user(
            username='ck_etr', password='x', role_legacy='admin',
            company=make_company('cockpit-etr'))
        self.assertEqual(self._get(etranger, equipe=self.equipe.pk).status_code,
                         404)
        self.assertEqual(
            [e['nom'] for e in self._get(self.admin).json()['equipes_accessibles']],
            ['Casa', 'Rabat'])
        self.assertEqual(self._get(self.autre_chef).json()['equipe']['nom'],
                         'Rabat')
        for params, cle in (({'periode': 'semaine'}, 'periode'),
                            ({'mois': 13}, 'mois'), ({'annee': 'abc'}, 'annee'),
                            ({'trimestre': 5}, 'trimestre'),
                            ({'equipe': 'x'}, 'equipe')):
            r = self._get(self.chef, **params)
            self.assertEqual(r.status_code, 400, (params, r.content))
            self.assertIn(cle, r.json())

    def test_chiffres(self):
        from decimal import Decimal
        corps = self._get(self.chef, **self.OCT).json()
        self.assertEqual(corps['equipe'], {'id': self.equipe.pk, 'nom': 'Casa',
                                           'responsable': 'Meryem'})
        self.assertEqual(corps['periode']['debut'], '2026-10-01')
        self.assertEqual(corps['periode']['fin'], '2026-10-31')
        self.assertEqual(corps['periode']['libelle'], 'Octobre 2026')
        self.assertEqual([m['nom'] for m in corps['membres']], ['Amine', 'Sara'])
        sara = corps['membres'][1]
        self.assertEqual(sara['fonction'], 'Chargée de clientèle')
        self.assertEqual(sara['objectifs']['nb_leads'], {
            'objectif_id': self.obj_leads.pk, 'cible': 4.0, 'realise': 3.0,
            'pct': 75.0})
        self.assertEqual(sara['objectifs']['nb_contacts'], {
            'objectif_id': None, 'cible': None, 'realise': 2.0, 'pct': None})
        self.assertEqual(sara['objectifs']['nb_rdv']['realise'], 1.0)
        self.assertEqual(sara['objectifs']['nb_devis']['realise'], 1.0)
        # Même réalisé que crm/objectifs/<id>/attainment/.
        self.auth_as(self.admin)
        attainment = self.api.get(
            f'/api/django/crm/objectifs/{self.obj_leads.pk}/attainment/').data
        self.assertEqual(Decimal(str(attainment['realise'])), Decimal('3'))
        self.assertEqual(sara['suivi'], {
            'premier_contact_5min_pct': 33.3, 'premier_contact_mesures': 3,
            'relances_en_retard': 1, 'leads_non_contactes': 1,
            'leads_en_attente': 0})
        valeur = float(Decimal(str(self.envoye.total_ttc)))
        self.assertGreater(valeur, 0)
        self.assertEqual(sara['pipeline'], {
            'leads_ouverts': 3, 'devis_ouverts': 1,
            'valeur_devis_ouverts': valeur})
        amine = corps['membres'][0]
        self.assertEqual(amine['suivi']['leads_en_attente'], 1)
        self.assertIsNone(amine['suivi']['premier_contact_5min_pct'])
        totaux = corps['equipe_totaux']
        self.assertEqual(totaux['objectifs']['nb_leads'],
                         {'cible': 4.0, 'realise': 3.0, 'pct': 75.0})
        self.assertIsNone(totaux['objectifs']['ca_signe']['cible'])
        self.assertEqual(totaux['suivi']['leads_en_attente'], 1)
        self.assertEqual(totaux['suivi']['premier_contact_mesures'], 3)
        self.assertEqual(totaux['pipeline']['devis_ouverts'], 1)

    def test_objectifs_matrice_d_ecriture(self):
        url = '/api/django/crm/objectifs/'

        def corps(owner, metric='nb_contacts'):
            return {'owner': owner.pk if owner else None, 'metric': metric,
                    'period_type': 'month', 'period_year': 2026,
                    'period_month': 10, 'cible': '5'}

        self.auth_as(self.chef)
        r = self.api.post(url, corps(self.m1), format='json')
        self.assertEqual(r.status_code, 201, r.content)
        objectif = r.json()['id']
        self.assertEqual(self.api.post(url, corps(self.m3),
                                       format='json').status_code, 403)
        self.assertEqual(self.api.post(url, corps(None),
                                       format='json').status_code, 403)
        self.assertEqual(self.api.patch(f'{url}{objectif}/', {'cible': '8'},
                                        format='json').status_code, 200)
        self.assertEqual(self.api.patch(f'{url}{objectif}/', {'owner': self.m3.pk},
                                        format='json').status_code, 403)
        for user in (self.autre_chef, self.autre_dir, self.m1):
            self.auth_as(user)
            self.assertEqual(self.api.patch(f'{url}{objectif}/', {'cible': '9'},
                                            format='json').status_code, 403)
            self.assertEqual(self.api.delete(f'{url}{objectif}/').status_code, 403)
        self.auth_as(self.directeur)
        self.assertEqual(self.api.post(url, corps(self.m2),
                                       format='json').status_code, 201)
        self.auth_as(self.chef)
        self.assertEqual(self.api.delete(f'{url}{objectif}/').status_code, 204)
        self.auth_as(self.admin)
        self.assertEqual(self.api.post(url, corps(None),
                                       format='json').status_code, 201)
        # Unicité membre + métrique + période : 409 (le front PATCHe alors
        # l'``objectif_id`` servi par le cockpit). En DERNIER : selon la
        # version de DRF, le refus vient du validateur ou de la contrainte.
        self.auth_as(self.chef)
        self.assertEqual(self.api.post(url, corps(self.m2),
                                       format='json').status_code, 409)
