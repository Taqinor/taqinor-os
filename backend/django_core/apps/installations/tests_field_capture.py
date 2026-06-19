"""F9–F19 + F23 — module de capture/réconciliation terrain.

Couvre :
  * F9  — saisie n° de série (+ OCR swappable no-op = garde la saisie manuelle),
          flux vers le parc installé, série vide ne bloque jamais ;
  * F10 — annotation d'une photo (dessin + légende) ;
  * F11 — réconciliation matériel : prévu vs utilisé, justification requise sur
          variance, consommation réelle → mouvements de stock, prix internes ;
  * F12 — surface de revue des dépassements (seuil % Paramètres) ;
  * F13/F14 — mémo vocal stocké + transcription no-op (« Non transcrit ») ;
  * F15 — temps d'équipe (durée sur site / trajet) ;
  * F16 — réserves (punch-list) → ticket SAV / suivi ;
  * F17 — retour d'outillage (statut + emplacement) ;
  * F18 — sign-off des consignes de sécurité ;
  * F19 — compte-rendu PDF (client-facing, aucun prix d'achat) ;
  * F23 — code/QR d'intervention + résolution scan ;
  * isolation multi-société + le statut intervention ne touche jamais le
    chantier / STAGES.py.

Run :
    python manage.py test apps.installations.tests_field_capture -v2
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
from apps.stock.models import Produit, EmplacementStock
from apps.outillage.models import Outillage, KitOutillage, KitOutillageItem
from apps.installations.models import (
    Intervention, Installation, ComponentSerial, VoiceMemo,
)
from apps.installations.services import create_installation_from_devis
from apps.installations import field_capture, swappable

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug='cap-co', nom='Cap Co'):
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
        prix_vente=Decimal('100'), prix_achat=Decimal('60'),
        quantite_stock=stock)


def make_chantier(company, user, lines):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'cap-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-CAP-{company.id}-{n}', client=client,
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


_PNG_1x1 = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08'
    b'\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00'
    b'\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
# WebM/Matroska EBML header magic bytes (1A 45 DF A3) — mémo vocal valide.
_WEBM = b'\x1aE\xdf\xa3' + b'\x00' * 32


def png_file(name='photo.png'):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, _PNG_1x1, content_type='image/png')


def webm_file(name='memo.webm'):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, _WEBM, content_type='audio/webm')


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='cap_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.panneau = make_produit(self.company, 'Panneau 550W', stock=20)
        self.onduleur = make_produit(self.company, 'Onduleur 5kW', stock=10)
        self.inst = make_chantier(
            self.company, self.user, [(self.panneau, 12), (self.onduleur, 1)])
        self.interv = make_intervention(self.inst, self.company, self.user)
        self.url = f'/api/django/installations/interventions/{self.interv.id}'


# ── F9 — n° de série + OCR no-op + parc ──────────────────────────────────────
class TestSerials(_Base):
    def test_add_serial_manual(self):
        r = self.api.post(f'{self.url}/ajouter-serial/', {
            'produit': self.onduleur.id, 'designation': 'Onduleur 5kW',
            'numero_serie': 'SN-123'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['numero_serie'], 'SN-123')
        self.assertFalse(r.data['serie_ocr'])

    def test_empty_serial_never_blocks(self):
        # Série vide acceptée, et n'empêche jamais la complétion d'une étape.
        r = self.api.post(f'{self.url}/ajouter-serial/', {
            'produit': self.onduleur.id, 'numero_serie': ''}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['numero_serie'], '')

    def test_ocr_noop_keeps_manual_when_no_provider(self):
        # Aucun fournisseur configuré → extract_serial renvoie None (no-op).
        self.assertFalse(swappable.serial_ocr_active(self.company))
        self.assertIsNone(swappable.extract_serial(self.company, b'xxxx'))
        # Avec une photo de plaque mais sans n° → reste vide (pas d'OCR).
        r = self.api.post(f'{self.url}/ajouter-serial/', {
            'produit': self.onduleur.id, 'file': png_file('plaque.png')},
            format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['numero_serie'], '')
        self.assertFalse(r.data['serie_ocr'])
        self.assertIsNotNone(r.data['plaque_url'])

    def test_serials_flow_to_parc(self):
        from apps.sav.models import Equipement
        self.inst.statut = Installation.Statut.INSTALLE
        self.inst.date_pose_reelle = None
        self.inst.save(update_fields=['statut'])
        ComponentSerial.objects.create(
            company=self.company, intervention=self.interv,
            produit=self.onduleur, numero_serie='SN-9', created_by=self.user)
        n = field_capture.push_serials_to_parc(self.interv, self.user)
        self.assertEqual(n, 1)
        eq = Equipement.objects.get(installation=self.inst, numero_serie='SN-9')
        self.assertEqual(eq.produit_id, self.onduleur.id)
        # Idempotent : un second push ne recrée rien.
        self.assertEqual(
            field_capture.push_serials_to_parc(self.interv, self.user), 0)


# ── F10 — annotation de photo ────────────────────────────────────────────────
class TestPhotoAnnotation(_Base):
    def test_annotate_photo(self):
        with mock.patch('apps.records.storage.get_minio_client'):
            r = self.api.post(f'{self.url}/ajouter-photo/',
                              {'file': png_file(), 'slot': 'toiture_avant'},
                              format='multipart')
        att_id = r.data['id']
        r = self.api.post(f'{self.url}/annoter-photo/', {
            'photo': att_id, 'caption': 'Fissure', 'probleme': True,
            'drawing': [{'type': 'line', 'points': [0, 0, 1, 1]}]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['probleme'])
        self.assertEqual(r.data['caption'], 'Fissure')
        self.assertEqual(len(r.data['drawing']), 1)


# ── F11/F12 — réconciliation matériel consommé ───────────────────────────────
class TestConsommation(_Base):
    def test_lists_bom_as_prevu(self):
        r = self.api.get(f'{self.url}/consommation/')
        self.assertEqual(r.status_code, 200, r.data)
        desigs = {li['designation']: li for li in r.data['lignes']}
        self.assertEqual(Decimal(desigs['Panneau 550W']['quantite_prevue']), 12)

    def test_variance_requires_justification(self):
        cons = field_capture.ensure_consommation(self.interv)
        ligne = cons.lignes.get(designation='Panneau 550W')
        # Utilisé ≠ prévu, sans justification → validation refusée.
        self.api.post(f'{self.url}/modifier-ligne-consommation/', {
            'ligne': ligne.id, 'quantite_utilisee': '14'}, format='json')
        r = self.api.post(f'{self.url}/valider-consommation/', {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        # Avec justification → validation OK.
        self.api.post(f'{self.url}/modifier-ligne-consommation/', {
            'ligne': ligne.id, 'justification': 'Casse sur site'},
            format='json')
        r = self.api.post(f'{self.url}/valider-consommation/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_real_consumption_moves_stock(self):
        from apps.stock.models import MouvementStock
        cons = field_capture.ensure_consommation(self.interv)
        ligne = cons.lignes.get(designation='Panneau 550W')
        ligne.quantite_utilisee = Decimal('10')
        ligne.justification = 'Reste 2 panneaux'
        ligne.save()
        before = self.panneau.quantite_stock
        self.api.post(f'{self.url}/valider-consommation/', {}, format='json')
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, before - 10)
        self.assertTrue(MouvementStock.objects.filter(
            produit=self.panneau,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE).exists())

    def test_extra_unplanned_line(self):
        r = self.api.post(f'{self.url}/ajouter-ligne-consommation/', {
            'designation': 'Câble 6mm² (m)', 'quantite_utilisee': '25'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['hors_nomenclature'])

    def test_overage_review_threshold(self):
        cons = field_capture.ensure_consommation(self.interv)
        ligne = cons.lignes.get(designation='Panneau 550W')
        ligne.quantite_utilisee = Decimal('18')  # +50 % > seuil 10 %
        ligne.justification = 'Casse importante'
        ligne.save()
        field_capture.validate_consommation(cons, self.user)
        r = self.api.get(
            '/api/django/installations/interventions/overage-review/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['interventions']), 1)
        rows = r.data['interventions'][0]['overage']
        self.assertTrue(any(x['designation'] == 'Panneau 550W' for x in rows))

    def test_buy_price_never_in_consommation(self):
        r = self.api.get(f'{self.url}/consommation/')
        body = str(r.data)
        self.assertNotIn('prix_achat', body)
        self.assertNotIn('60', body.replace('600', ''))  # prix_achat = 60


# ── F13/F14 — mémo vocal + transcription no-op ───────────────────────────────
class TestVoiceMemo(_Base):
    def test_memo_noop_transcription(self):
        self.assertFalse(swappable.transcription_active(self.company))
        with mock.patch('apps.records.storage.get_minio_client'):
            r = self.api.post(f'{self.url}/ajouter-memo/',
                              {'file': webm_file(), 'cible': 'general'},
                              format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data['transcrit'])
        self.assertEqual(r.data['transcript'],
                         swappable.TRANSCRIPTION_NON_CONFIGUREE)
        self.assertIsNotNone(r.data['audio_url'])

    def test_transcript_editable(self):
        memo = VoiceMemo.objects.create(
            company=self.company, intervention=self.interv,
            transcript=swappable.TRANSCRIPTION_NON_CONFIGUREE)
        r = self.api.post(f'{self.url}/modifier-memo/', {
            'memo': memo.id, 'transcript': 'Onduleur OK'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['transcrit'])
        self.assertEqual(r.data['transcript'], 'Onduleur OK')

    def test_audio_format_rejected_for_image_endpoint(self):
        # Un fichier image n'est pas un audio valide → refusé en mémo.
        with mock.patch('apps.records.storage.get_minio_client'):
            r = self.api.post(f'{self.url}/ajouter-memo/',
                              {'file': png_file()}, format='multipart')
        self.assertEqual(r.status_code, 400)


# ── F15 — temps d'équipe ─────────────────────────────────────────────────────
class TestCrewTime(_Base):
    def test_crew_time_durations(self):
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        self.interv.depart_depot_le = now
        self.interv.arrivee_site_le = now + timedelta(minutes=30)
        self.interv.retour_depot_le = now + timedelta(minutes=270)
        self.interv.save()
        self.interv.equipe.add(self.user)
        t = field_capture.crew_time(self.interv)
        self.assertEqual(t['trajet_aller_min'], 30)
        self.assertEqual(t['duree_sur_site_min'], 240)
        jd = field_capture.labour_days_for_intervention(self.interv)
        self.assertEqual(jd, Decimal('0.50'))  # 240 min / 480 × 1 personne

    def test_push_labour_to_chantier(self):
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        self.interv.arrivee_site_le = now
        self.interv.retour_depot_le = now + timedelta(minutes=480)
        self.interv.save()
        self.interv.equipe.add(self.user)
        field_capture.push_labour_to_chantier(self.interv)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.labour_jours_reels, Decimal('1.0'))


# ── F16 — réserves ────────────────────────────────────────────────────────────
class TestReserves(_Base):
    def test_create_and_resolve(self):
        r = self.api.post(f'{self.url}/ajouter-reserve/', {
            'description': 'Câble manquant'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        rid = r.data['id']
        self.assertEqual(r.data['statut'], 'ouverte')
        r = self.api.post(f'{self.url}/resoudre-reserve/', {
            'reserve': rid, 'resolution': 'Câble posé'}, format='json')
        self.assertEqual(r.data['statut'], 'resolue')

    def test_reserve_spawns_ticket(self):
        from apps.sav.models import Ticket
        r = self.api.post(f'{self.url}/ajouter-reserve/', {
            'description': 'Réglage onduleur', 'creer_ticket': True},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNotNone(r.data['ticket'])
        self.assertTrue(Ticket.objects.filter(id=r.data['ticket']).exists())

    def test_reserve_spawns_followup_intervention(self):
        r = self.api.post(f'{self.url}/ajouter-reserve/', {
            'description': 'Revenir', 'creer_suivi': True}, format='json')
        self.assertIsNotNone(r.data['suivi_intervention'])


# ── F17 — retour d'outillage ─────────────────────────────────────────────────
class TestToolReturn(_Base):
    def _make_kit(self):
        depot = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt')
        outil = Outillage.objects.create(
            company=self.company, nom='Perceuse',
            statut=Outillage.Statut.EN_INTERVENTION)
        kit = KitOutillage.objects.create(
            company=self.company, nom='Kit pose', type_intervention='pose')
        KitOutillageItem.objects.create(company=self.company, kit=kit, outil=outil)
        # Lie le kit à la préparation.
        from apps.installations import field_services
        prep = field_services.ensure_preparation(self.interv)
        prep.kit = kit
        prep.save()
        field_services._sync_outils(prep)
        return depot, outil

    def test_confirm_updates_tool(self):
        depot, outil = self._make_kit()
        r = self.api.get(f'{self.url}/tool-return/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data), 1)
        line_id = r.data[0]['id']
        self.api.post(f'{self.url}/cocher-tool-return/', {
            'ligne': line_id, 'rendu': True, 'emplacement': depot.id},
            format='json')
        r = self.api.post(f'{self.url}/confirmer-tool-return/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['non_rendus'], [])
        outil.refresh_from_db()
        self.assertEqual(outil.statut, Outillage.Statut.DISPONIBLE)
        self.assertEqual(outil.emplacement_id, depot.id)

    def test_not_returned_flagged(self):
        depot, outil = self._make_kit()
        self.api.get(f'{self.url}/tool-return/')
        r = self.api.post(f'{self.url}/confirmer-tool-return/', {}, format='json')
        self.assertEqual(r.data['non_rendus'], ['Perceuse'])
        outil.refresh_from_db()
        self.assertEqual(outil.statut, Outillage.Statut.EN_INTERVENTION)


# ── F18 — consignes de sécurité ──────────────────────────────────────────────
class TestSafety(_Base):
    def test_signoff_flow(self):
        r = self.api.get(f'{self.url}/safety/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(len(r.data['items']) >= 2)
        cle = r.data['items'][0]['cle']
        r = self.api.post(f'{self.url}/cocher-safety/', {
            'cle': cle, 'coche': True}, format='json')
        item = next(i for i in r.data['items'] if i['cle'] == cle)
        self.assertTrue(item['coche'])
        self.assertEqual(item['coche_par_nom'], 'cap_resp')
        r = self.api.post(f'{self.url}/signer-safety/', {}, format='json')
        self.assertTrue(r.data['signe'])

    def test_default_slots_seeded(self):
        field_capture.seed_safety_slots(self.company)
        from apps.installations.models import SafetyChecklistSlot
        cles = set(SafetyChecklistSlot.objects.filter(
            company=self.company).values_list('cle', flat=True))
        self.assertIn('epi_portes', cles)
        self.assertIn('consignation_electrique', cles)


# ── F19 — compte-rendu PDF ───────────────────────────────────────────────────
class TestCompteRendu(_Base):
    def test_pdf_generated_no_buy_price(self):
        ComponentSerial.objects.create(
            company=self.company, intervention=self.interv,
            produit=self.onduleur, numero_serie='SN-PDF', created_by=self.user)
        r = self.api.get(f'{self.url}/compte-rendu/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content[:4] == b'%PDF')
        # Le prix d'achat ne doit jamais apparaître (sécurité, vérif payload).
        from apps.installations import intervention_pdf
        cons = intervention_pdf._consommation_payload(self.interv)
        self.assertFalse(any('prix_achat' in str(c) for c in cons))

    def test_compte_rendu_pushes_serials_to_parc(self):
        from apps.sav.models import Equipement
        ComponentSerial.objects.create(
            company=self.company, intervention=self.interv,
            produit=self.onduleur, numero_serie='SN-X', created_by=self.user)
        self.api.get(f'{self.url}/compte-rendu/')
        self.assertTrue(Equipement.objects.filter(
            installation=self.inst, numero_serie='SN-X').exists())


# ── F20 — contrôle qualité IA des photos (vision swappable no-op) ────────────
class TestPhotoQa(_Base):
    def test_photo_qa_noop_when_disabled(self):
        self.assertFalse(swappable.photo_qa_active(self.company))
        r = self.api.get(f'{self.url}/photo-qa/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['actif'])
        self.assertEqual(r.data['signalements'], [])

    def test_review_photos_never_raises(self):
        # No-op renvoie toujours [] sans fournisseur (jamais bloquant).
        self.assertEqual(swappable.review_photos(self.company, []), [])
        self.assertEqual(
            swappable.review_photos(self.company, [{'cle': 'x'}]), [])


# ── F23 — code/QR + résolution scan ──────────────────────────────────────────
class TestCode(_Base):
    def test_code_token(self):
        r = self.api.get(f'{self.url}/code/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['token'], f'INTERV:{self.interv.id}')
        self.assertIn('<svg', r.data['qr_svg'])

    def test_resolve_intervention_code(self):
        # Le résolveur N20 est gardé admin (comme PRODUIT/SYSTEME).
        admin = User.objects.create_user(
            username='cap_admin', password='x', role_legacy='admin',
            company=self.company)
        r = auth(admin).get('/api/django/stock/produits/resolve/',
                            {'code': f'INTERV:{self.interv.id}'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['type'], 'intervention')
        self.assertEqual(r.data['id'], self.interv.id)
        self.assertEqual(r.data['route'], '/interventions')


# ── Sécurité transversale : statut intervention ≠ chantier / STAGES ──────────
class TestStatutIsolation(_Base):
    def test_capture_never_touches_chantier_statut(self):
        before = self.inst.statut
        # Plusieurs captures + validations.
        self.api.post(f'{self.url}/ajouter-serial/', {
            'numero_serie': 'X'}, format='json')
        self.api.post(f'{self.url}/ajouter-reserve/', {
            'description': 'x'}, format='json')
        self.api.post(f'{self.url}/signer-safety/', {}, format='json')
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, before)


# ── Isolation multi-société ──────────────────────────────────────────────────
class TestTenantIsolation(_Base):
    def test_other_company_cannot_see_serials(self):
        other = make_company(slug='cap-co-2', nom='Cap Co 2')
        other_user = User.objects.create_user(
            username='other_resp', password='x', role_legacy='responsable',
            company=other)
        ComponentSerial.objects.create(
            company=self.company, intervention=self.interv, numero_serie='SECRET')
        r = auth(other_user).get(f'{self.url}/serials/')
        self.assertIn(r.status_code, (403, 404))
