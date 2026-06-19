"""
F5–F8 — module d'exécution terrain (interventions).

Couvre :
  * F5 — liste de préparation : matériel issu de la nomenclature gelée du
    chantier + outils du kit ; cases « chargé » ; pourcentage de complétion ;
    confirmation « Tout est chargé » requise pour quitter « À préparer » ;
    drapeau « manquant » dérivé du disponible (réservation de stock) + bon de
    commande brouillon ;
  * F6 — départ-dépôt / check-in GPS (horodatage + coordonnées) / retour, et
    distance-au-site ;
  * F7 — photos par créneau de shot list via le stockage objet générique,
    galerie avant/pendant/après ;
  * F8 — interdiction de passer à « Terminée » tant qu'un créneau obligatoire
    n'a pas de photo, et déblocage une fois la photo présente ;
  * shot list configurable (Paramètres) + isolation multi-société.

Run :
    python manage.py test apps.installations.tests_field_execution -v2
"""
import itertools
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import Produit
from apps.outillage.models import Outillage, KitOutillage, KitOutillageItem
from apps.installations.models import Intervention, ShotListSlot
from apps.installations.services import create_installation_from_devis
from apps.installations import field_services

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug='field-co', nom='Field Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom, stock):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=nom, sku=f'SKU-{company.id}-{n}',
        prix_vente=Decimal('100'), quantite_stock=stock)


def make_chantier(company, user, lines, gps=('33.5', '-7.5')):
    """Crée un chantier depuis un devis accepté avec une nomenclature."""
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'field-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel',
        gps_lat=Decimal(gps[0]), gps_lng=Decimal(gps[1]))
    devis = Devis.objects.create(
        company=company, reference=f'DEV-FIELD-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    for produit, qte in lines:
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal(str(qte)), prix_unitaire=Decimal('100'))
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


def make_intervention(inst, company, user, type_interv='pose'):
    return Intervention.objects.create(
        company=company, installation=inst, type_intervention=type_interv,
        created_by=user)


# Image PNG 1×1 minimale, valide pour store_attachment (magic bytes \x89PNG).
_PNG_1x1 = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08'
    b'\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00'
    b'\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')


def png_file(name='photo.png'):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, _PNG_1x1, content_type='image/png')


class TestPreparation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='field_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.panneau = make_produit(self.company, 'Panneau 550W', stock=20)
        self.onduleur = make_produit(self.company, 'Onduleur 5kW', stock=10)
        self.inst = make_chantier(
            self.company, self.user,
            [(self.panneau, 12), (self.onduleur, 1)])
        self.interv = make_intervention(self.inst, self.company, self.user)
        self.url = f'/api/django/installations/interventions/{self.interv.id}'

    def test_preparation_lists_material_from_bom(self):
        r = self.api.get(f'{self.url}/preparation/')
        self.assertEqual(r.status_code, 200, r.data)
        desigs = {li['designation']: li for li in r.data['materiel']}
        self.assertIn('Panneau 550W', desigs)
        self.assertEqual(desigs['Panneau 550W']['quantite_requise'], 12)
        self.assertEqual(desigs['Onduleur 5kW']['quantite_requise'], 1)
        # Aucun manque : le disponible couvre la nomenclature.
        self.assertEqual(r.data['nb_manques'], 0)
        self.assertIsNotNone(r.data['completion'])

    def test_completion_and_confirm_flow(self):
        prep = field_services.ensure_preparation(self.interv)
        # Au départ rien n'est chargé → 0 %.
        self.assertEqual(field_services.preparation_completion(prep), 0)
        # Cocher chaque ligne matériel.
        for li in prep.materiel.all():
            r = self.api.post(f'{self.url}/cocher-materiel/',
                              {'ligne': li.id, 'charge': True}, format='json')
            self.assertEqual(r.status_code, 200, r.data)
        r = self.api.get(f'{self.url}/preparation/')
        self.assertEqual(r.data['completion'], 100)
        # Confirmer « Tout est chargé ».
        r = self.api.post(f'{self.url}/confirmer-charge/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['tout_charge'])

    def test_cannot_leave_a_preparer_without_confirmation(self):
        # Sans confirmation, passer à « Prête » est refusé (F5).
        r = self.api.patch(f'{self.url}/', {'statut': 'prete'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('statut', r.data)
        # Confirmer puis réessayer → autorisé.
        prep = field_services.ensure_preparation(self.interv)
        for li in prep.materiel.all():
            li.charge = True
            li.save(update_fields=['charge'])
        field_services.confirm_charge(prep, self.user)
        r = self.api.patch(f'{self.url}/', {'statut': 'prete'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.interv.refresh_from_db()
        self.assertEqual(self.interv.statut, 'prete')

    def test_uncheck_drops_confirmation(self):
        prep = field_services.ensure_preparation(self.interv)
        for li in prep.materiel.all():
            li.charge = True
            li.save(update_fields=['charge'])
        field_services.confirm_charge(prep, self.user)
        # Décocher une ligne retire la confirmation.
        li = prep.materiel.first()
        r = self.api.post(f'{self.url}/cocher-materiel/',
                          {'ligne': li.id, 'charge': False}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        prep.refresh_from_db()
        self.assertFalse(prep.tout_charge)

    def test_manquant_flag_and_draft_order(self):
        # Produit dont la nomenclature dépasse le stock disponible.
        rare = make_produit(self.company, 'Câble rare', stock=2)
        inst = make_chantier(self.company, self.user, [(rare, 9)])
        interv = make_intervention(inst, self.company, self.user)
        url = f'/api/django/installations/interventions/{interv.id}'
        r = self.api.get(f'{url}/preparation/')
        ligne = next(li for li in r.data['materiel']
                     if li['designation'] == 'Câble rare')
        self.assertTrue(ligne['manquant'])
        self.assertEqual(ligne['quantite_manquante'], 7)  # 9 requis − 2 dispo
        self.assertEqual(r.data['nb_manques'], 1)
        # Le manque peut générer un bon de commande fournisseur brouillon.
        from apps.stock.models import Fournisseur
        f = Fournisseur.objects.create(company=self.company, nom='Grossiste')
        rare.fournisseur = f
        rare.save(update_fields=['fournisseur'])
        r = self.api.post(f'{url}/commander-manques/',
                          {'fournisseur': f.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['nb_lignes'], 1)


class TestKitTools(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='field_kit', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.panneau = make_produit(self.company, 'Panneau', stock=50)
        self.inst = make_chantier(self.company, self.user, [(self.panneau, 4)])
        self.interv = make_intervention(self.inst, self.company, self.user)
        self.url = f'/api/django/installations/interventions/{self.interv.id}'
        # Kit avec deux outils, visant le type « pose ».
        self.kit = KitOutillage.objects.create(
            company=self.company, nom='Kit pose', type_intervention='pose')
        self.perceuse = Outillage.objects.create(
            company=self.company, nom='Perceuse')
        self.echelle = Outillage.objects.create(
            company=self.company, nom='Échelle')
        KitOutillageItem.objects.create(
            company=self.company, kit=self.kit, outil=self.perceuse, ordre=0)
        KitOutillageItem.objects.create(
            company=self.company, kit=self.kit, outil=self.echelle, ordre=1)

    def test_kit_autoselected_by_type_and_lists_tools(self):
        r = self.api.get(f'{self.url}/preparation/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['kit'], self.kit.id)
        outils = {o['libelle'] for o in r.data['outils']}
        self.assertEqual(outils, {'Perceuse', 'Échelle'})

    def test_check_tool_and_completion(self):
        prep = field_services.ensure_preparation(self.interv)
        outil_ligne = prep.outils.first()
        r = self.api.post(f'{self.url}/cocher-outil/',
                          {'ligne': outil_ligne.id, 'coche': True},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        checked = next(o for o in r.data['outils']
                       if o['id'] == outil_ligne.id)
        self.assertTrue(checked['coche'])

    def test_choisir_kit_resyncs_tools(self):
        # Changer pour un kit vide retire les outils.
        autre = KitOutillage.objects.create(
            company=self.company, nom='Kit vide')
        r = self.api.post(f'{self.url}/choisir-kit/',
                          {'kit': autre.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['kit'], autre.id)
        self.assertEqual(len(r.data['outils']), 0)


class TestCheckinGPS(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='field_gps', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        p = make_produit(self.company, 'Panneau', stock=10)
        # Chantier à Casablanca (≈ 33.5731, -7.5898).
        self.inst = make_chantier(
            self.company, self.user, [(p, 1)], gps=('33.5731', '-7.5898'))
        self.interv = make_intervention(self.inst, self.company, self.user)
        self.url = f'/api/django/installations/interventions/{self.interv.id}'

    def test_depart_checkin_retour_stamps(self):
        r = self.api.post(f'{self.url}/depart-depot/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNotNone(r.data['depart_depot_le'])
        # Check-in proche du site → distance faible.
        r = self.api.post(f'{self.url}/checkin/',
                          {'lat': '33.5735', 'lng': '-7.5900'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNotNone(r.data['arrivee_site_le'])
        self.assertIsNotNone(r.data['distance_site_km'])
        self.assertLess(r.data['distance_site_km'], 1.0)  # < 1 km
        r = self.api.post(f'{self.url}/retour/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNotNone(r.data['retour_depot_le'])

    def test_distance_none_without_coords(self):
        self.assertIsNone(field_services.distance_to_site(self.interv))
        self.assertIsNone(field_services.haversine_km(None, None, 1, 1))

    def test_haversine_known_distance(self):
        # Casablanca → Rabat ≈ 86 km (tolérance large).
        d = field_services.haversine_km(33.5731, -7.5898, 34.0209, -6.8416)
        self.assertGreater(d, 70)
        self.assertLess(d, 100)


@mock.patch('apps.records.storage.get_minio_client')
class TestPhotosAndRequiredEnforcement(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='field_photo', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        p = make_produit(self.company, 'Panneau', stock=10)
        self.inst = make_chantier(self.company, self.user, [(p, 1)])
        self.interv = make_intervention(self.inst, self.company, self.user)
        self.url = f'/api/django/installations/interventions/{self.interv.id}'
        field_services.seed_shotlist_slots(self.company)
        # Confirme la préparation pour pouvoir avancer le statut (F5 déjà géré) :
        # coche toutes les lignes (matériel + outils) avant de confirmer.
        prep = field_services.ensure_preparation(self.interv)
        for li in prep.materiel.all():
            li.charge = True
            li.save(update_fields=['charge'])
        for li in prep.outils.all():
            li.coche = True
            li.save(update_fields=['coche'])
        field_services.confirm_charge(prep, self.user)

    def _upload(self, slot):
        return self.api.post(
            f'{self.url}/ajouter-photo/',
            {'file': png_file(), 'slot': slot}, format='multipart')

    def test_shotlist_seeded_with_obligatoires(self, _minio):
        slots = ShotListSlot.objects.filter(company=self.company)
        self.assertTrue(slots.exists())
        self.assertTrue(slots.filter(obligatoire=True).exists())

    def test_photo_upload_groups_by_phase(self, minio):
        r = self._upload('toiture_avant')
        self.assertEqual(r.status_code, 201, r.data)
        r = self.api.get(f'{self.url}/photos/')
        self.assertEqual(r.status_code, 200, r.data)
        avant = r.data['groupes']['avant']
        toiture = next(s for s in avant if s['cle'] == 'toiture_avant')
        self.assertEqual(len(toiture['photos']), 1)

    def test_cannot_terminate_until_required_photos_present(self, minio):
        # Sans photo obligatoire, passer à « Terminée » est refusé (F8).
        # On amène d'abord l'intervention jusqu'à « Sur site ».
        for st in ('prete', 'en_route', 'sur_site'):
            r = self.api.patch(f'{self.url}/', {'statut': st}, format='json')
            self.assertEqual(r.status_code, 200, (st, r.data))
        r = self.api.patch(f'{self.url}/', {'statut': 'terminee'},
                           format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('statut', r.data)
        # La checklist des manquants liste les créneaux obligatoires.
        r = self.api.get(f'{self.url}/photos/')
        manquants = {m['cle'] for m in r.data['obligatoires_manquants']}
        oblig = set(ShotListSlot.objects.filter(
            company=self.company, obligatoire=True).values_list('cle', flat=True))
        self.assertEqual(manquants, oblig)

    def test_terminate_unblocks_after_all_required_photos(self, minio):
        oblig = list(ShotListSlot.objects.filter(
            company=self.company, obligatoire=True, actif=True))
        for slot in oblig:
            self.assertEqual(self._upload(slot.cle).status_code, 201)
        for st in ('prete', 'en_route', 'sur_site', 'terminee'):
            r = self.api.patch(f'{self.url}/', {'statut': st}, format='json')
            self.assertEqual(r.status_code, 200, (st, r.data))
        self.interv.refresh_from_db()
        self.assertEqual(self.interv.statut, 'terminee')

    def test_missing_required_helper(self, minio):
        self.assertTrue(field_services.missing_required_shots(self.interv))
        for slot in ShotListSlot.objects.filter(
                company=self.company, obligatoire=True, actif=True):
            self._upload(slot.cle)
        self.assertFalse(field_services.missing_required_shots(self.interv))


class TestTenantIsolation(TestCase):
    def test_company_b_cannot_touch_company_a_intervention(self):
        a = make_company('field-a', 'A')
        b = make_company('field-b', 'B')
        ua = User.objects.create_user(
            username='fa', password='x', role_legacy='responsable', company=a)
        ub = User.objects.create_user(
            username='fb', password='x', role_legacy='responsable', company=b)
        p = make_produit(a, 'Panneau A', stock=5)
        inst = make_chantier(a, ua, [(p, 2)])
        interv = make_intervention(inst, a, ua)
        url = f'/api/django/installations/interventions/{interv.id}'
        # B ne voit pas l'intervention de A.
        r = auth(ub).get(f'{url}/preparation/')
        self.assertEqual(r.status_code, 404)
        # A la voit.
        r = auth(ua).get(f'{url}/preparation/')
        self.assertEqual(r.status_code, 200, r.data)

    def test_shotlist_seeding_is_per_company_and_idempotent(self):
        a = make_company('field-c', 'C')
        field_services.seed_shotlist_slots(a)
        n1 = ShotListSlot.objects.filter(company=a).count()
        field_services.seed_shotlist_slots(a)  # idempotent
        self.assertEqual(ShotListSlot.objects.filter(company=a).count(), n1)
        self.assertGreater(n1, 0)


class TestStatutNeverTouchesChantier(TestCase):
    """Invariant F3 préservé : avancer/garder le statut intervention ne change
    JAMAIS le statut du chantier (machine à états séparée)."""
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='field_inv', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        p = make_produit(self.company, 'Panneau', stock=10)
        self.inst = make_chantier(self.company, self.user, [(p, 1)])
        self.interv = make_intervention(self.inst, self.company, self.user)

    def test_confirm_and_advance_keeps_chantier_statut(self):
        before = self.inst.statut
        prep = field_services.ensure_preparation(self.interv)
        for li in prep.materiel.all():
            li.charge = True
            li.save(update_fields=['charge'])
        field_services.confirm_charge(prep, self.user)
        url = f'/api/django/installations/interventions/{self.interv.id}/'
        r = self.api.patch(url, {'statut': 'prete'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, before)
