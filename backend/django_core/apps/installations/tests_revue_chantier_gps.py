"""
Nouveau fichier car : lanes parallèles file-disjointes de la revue chantier du 26/10/2026
(la lane GPS ne touche tests_xfsm23 / tests_ntmob9 que pour leurs assertions
devenues fausses).

Suivi GPS des techniciens — cadre loi 09-08 / délibération CNDP 17-2014 :
suivi AUTOMATIQUE pendant la session d'intervention (en route / sur site),
jamais caché, après un accusé de réception UNIQUE de la notice par le
technicien lui-même.

Couvre :
  * la porte de l'accusé de réception (403 avant, 201 après) et la notice
    servie au technicien (récépissé « non encore déclaré » si vide) ;
  * les gardes du ping (sans intervention 400, technicien étranger 403,
    membre d'équipe accepté, mauvais statut 409) ;
  * le lot hors-ligne (≤ 20, doublons ignorés) ;
  * la sortie de périmètre : SUR SITE seulement, une seule ouverte jusqu'à
    une ré-entrée, notification du responsable, rayon propre au chantier ;
  * la purge : les alertes survivent (position → NULL), la présence aussi ;
  * le calcul de présence + son endpoint (forme = contrat) ;
  * la carte live bornée en âge, le tracé du jour, « mes positions » ;
  * l'isolation société de chaque route neuve ; les champs du serializer ;
  * correctifs de revue : présence réservée (F1), lot rattrapé après un
    relevé live plus récent (F2), lot reçu après clôture (F3), présence datée
    du relevé (F4), retour arrière de 0132 (F5).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_revue_chantier_gps"
"""
import itertools
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.installations import gps_tracking_service
from apps.installations.models import (
    GeofenceAlert, GpsConsentRecord, Intervention, PositionTechnicien,
)
from apps.installations.services import create_installation_from_devis
from apps.ventes.models import Devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'

SITE_LAT, SITE_LNG = '33.573110', '-7.589843'
DEDANS = {'lat': '33.573150', 'lng': '-7.589800'}
DEHORS = {'lat': '33.62', 'lng': '-7.589843'}  # ~5 km au nord

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'rcgps-co-{n}', defaults={'nom': f'RCGPS Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'rcgps-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_intervention(company, responsable, technicien,
                      statut=Intervention.Statut.SUR_SITE):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'rcgps-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-RCGPS-{company.id}-{n}',
        client=client, lead=lead, statut=Devis.Statut.ACCEPTE,
        taux_tva=Decimal('20'), mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, responsable, company)
    inst.gps_lat = Decimal(SITE_LAT)
    inst.gps_lng = Decimal(SITE_LNG)
    inst.technicien_responsable = responsable
    inst.save(update_fields=['gps_lat', 'gps_lng', 'technicien_responsable'])
    return Intervention.objects.create(
        company=company, installation=inst, type_intervention='pose',
        created_by=responsable, technicien=technicien, statut=statut,
        date_prevue=date.today())


def consentement_accepte(company, technicien):
    gps_tracking_service.record_consent(company, technicien)
    gps_tracking_service.accepter_consentement(company, technicien)


def liste(resp):
    return resp.data.get('results', resp.data) if isinstance(
        resp.data, dict) else resp.data


class Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.responsable = make_user(self.company)
        self.technicien = make_user(self.company, role='normal')
        self.interv = make_intervention(
            self.company, self.responsable, self.technicien)
        self.api = auth(self.technicien)

    def ping(self, point, interv=None, api=None, **extra):
        corps = dict(point, intervention=(interv or self.interv).id, **extra)
        return (api or self.api).post(
            f'{BASE}/positions-techniciens/ping/', corps, format='json')


class AccuseReceptionTests(Base):
    """L'information préalable (loi 09-08 art. 5) ouvre le suivi."""

    def test_ping_refuse_tant_que_la_notice_nest_pas_acceptee(self):
        gps_tracking_service.record_consent(self.company, self.technicien)

        avant = self.ping(DEDANS)
        self.assertEqual(avant.status_code, 403, avant.content)
        self.assertIn('notice', str(avant.data['detail']))

        acc = self.api.post(
            f'{BASE}/gps-consentements/mon-consentement/accepter/', {},
            format='json')
        self.assertEqual(acc.status_code, 200, acc.content)
        self.assertEqual(acc.data['statut'], 'actif')
        self.assertIsNotNone(acc.data['accepte_le'])

        apres = self.ping(DEDANS)
        self.assertEqual(apres.status_code, 201, apres.content)

    def test_mon_consentement_sert_la_notice_complete(self):
        gps_tracking_service.record_consent(self.company, self.technicien)
        resp = self.api.get(f'{BASE}/gps-consentements/mon-consentement/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], 'a_accepter')
        self.assertTrue(resp.data['existe'])
        self.assertTrue(resp.data['actif'])
        self.assertIsNone(resp.data['accepte_le'])
        notice = resp.data['notice']
        for cle in ('version', 'texte', 'responsable', 'finalites', 'donnees',
                    'destinataires', 'retention_jours', 'droits',
                    'recepisse_cndp'):
            self.assertIn(cle, notice)
        self.assertEqual(notice['recepisse_cndp'], 'non encore déclaré')
        self.assertEqual(notice['retention_jours'], 30)
        # Forme = contrat partagé (PACT10).
        contrat = json.loads(
            (CONTRATS / 'gps_mon_consentement.json').read_text(encoding='utf-8'))
        self.assertEqual(set(resp.data), set(contrat['exemple']))
        self.assertEqual(set(notice), set(contrat['exemple']['notice']))

    def test_recepisse_saisi_est_servi(self):
        record = gps_tracking_service.record_consent(
            self.company, self.technicien)
        record.recepisse_cndp = 'D-GC-123/2026'
        record.save(update_fields=['recepisse_cndp'])
        resp = self.api.get(f'{BASE}/gps-consentements/mon-consentement/')
        self.assertEqual(resp.data['notice']['recepisse_cndp'], 'D-GC-123/2026')

    def test_sans_consentement_pose_absent_et_accepter_404(self):
        resp = self.api.get(f'{BASE}/gps-consentements/mon-consentement/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], 'absent')
        self.assertFalse(resp.data['existe'])
        acc = self.api.post(
            f'{BASE}/gps-consentements/mon-consentement/accepter/', {},
            format='json')
        self.assertEqual(acc.status_code, 404, acc.content)

    def test_acceptation_idempotente_garde_la_premiere_date(self):
        gps_tracking_service.record_consent(self.company, self.technicien)
        premier = gps_tracking_service.accepter_consentement(
            self.company, self.technicien, ip='10.0.0.7')
        second = gps_tracking_service.accepter_consentement(
            self.company, self.technicien, ip='10.0.0.8')
        self.assertEqual(premier.accepte_le, second.accepte_le)
        second.refresh_from_db()
        self.assertEqual(second.accepte_depuis_ip, '10.0.0.7')

    def test_ip_illisible_jamais_un_500(self):
        gps_tracking_service.record_consent(self.company, self.technicien)
        record = gps_tracking_service.accepter_consentement(
            self.company, self.technicien, ip='pas-une-ip')
        self.assertIsNone(record.accepte_depuis_ip)
        self.assertIsNotNone(record.accepte_le)

    def test_revoque_apres_acceptation_bloque_le_ping(self):
        consentement_accepte(self.company, self.technicien)
        gps_tracking_service.revoke_consent(self.company, self.technicien)
        self.assertEqual(self.ping(DEDANS).status_code, 403)
        resp = self.api.get(f'{BASE}/gps-consentements/mon-consentement/')
        self.assertEqual(resp.data['statut'], 'revoque')

    def test_le_responsable_voit_laccord_du_technicien(self):
        consentement_accepte(self.company, self.technicien)
        resp = auth(self.responsable).get(f'{BASE}/gps-consentements/')
        ligne = [r for r in liste(resp) if r['technicien'] == self.technicien.id][0]
        self.assertIsNotNone(ligne['accepte_le'])
        self.assertTrue(ligne['is_acknowledged'])
        self.assertEqual(ligne['statut'], 'actif')
        self.assertEqual(ligne['notice_version'], 'v1')

    def test_le_technicien_ne_lit_pas_les_consentements_des_autres(self):
        resp = self.api.get(f'{BASE}/gps-consentements/')
        self.assertEqual(resp.status_code, 403)


class GardesPingTests(Base):
    def setUp(self):
        super().setUp()
        consentement_accepte(self.company, self.technicien)

    def test_sans_intervention_400(self):
        resp = self.api.post(
            f'{BASE}/positions-techniciens/ping/', dict(DEDANS), format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('intervention', resp.data)

    def test_intervention_dun_autre_technicien_403(self):
        autre = make_user(self.company, role='normal')
        interv_autre = make_intervention(
            self.company, self.responsable, autre)
        resp = self.ping(DEDANS, interv=interv_autre)
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertFalse(PositionTechnicien.objects.exists())

    def test_membre_de_lequipe_accepte(self):
        equipier = make_user(self.company, role='normal')
        consentement_accepte(self.company, equipier)
        self.interv.equipe.add(equipier)
        resp = self.ping(DEDANS, api=auth(equipier))
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_statut_hors_session_409(self):
        for statut in (Intervention.Statut.PRETE, Intervention.Statut.TERMINEE,
                       Intervention.Statut.A_PREPARER):
            self.interv.statut = statut
            self.interv.save(update_fields=['statut'])
            resp = self.ping(DEDANS)
            self.assertEqual(resp.status_code, 409, (statut, resp.content))
        self.assertFalse(PositionTechnicien.objects.exists())

    def test_intervention_annulee_409(self):
        self.interv.annulee = True
        self.interv.save(update_fields=['annulee'])
        self.assertEqual(self.ping(DEDANS).status_code, 409)

    def test_intervention_dune_autre_societe_400(self):
        autre_co = make_company()
        resp_b = make_user(autre_co)
        interv_b = make_intervention(autre_co, resp_b, self.technicien)
        resp = self.ping(DEDANS, interv=interv_b)
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_captured_at_futur_refuse(self):
        futur = (timezone.now() + timedelta(hours=1)).isoformat()
        resp = self.ping(DEDANS, captured_at=futur)
        self.assertEqual(resp.status_code, 400, resp.content)


class LotHorsLigneTests(Base):
    def setUp(self):
        super().setUp()
        consentement_accepte(self.company, self.technicien)
        self.url = f'{BASE}/positions-techniciens/ping-lot/'

    def _point(self, minutes, point=DEDANS):
        return dict(point, accuracy_m=8,
                    captured_at=(timezone.now() - timedelta(minutes=minutes)).isoformat())

    def test_lot_enregistre_et_ignore_les_doublons(self):
        p1, p2 = self._point(10), self._point(5)
        resp = self.api.post(self.url, {
            'intervention': self.interv.id, 'positions': [p1, p2, dict(p2)],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['enregistrees'], 2)
        self.assertEqual(resp.data['doublons'], 1)

        # Le client renvoie le même lot après une coupure : rien de doublé.
        encore = self.api.post(self.url, {
            'intervention': self.interv.id, 'positions': [p1, p2],
        }, format='json')
        self.assertEqual(encore.status_code, 201, encore.content)
        self.assertEqual(encore.data['enregistrees'], 0)
        self.assertEqual(encore.data['doublons'], 2)
        self.assertEqual(
            PositionTechnicien.objects.filter(intervention=self.interv).count(), 2)

    def test_lot_trop_grand_400(self):
        points = [self._point(m) for m in range(1, 23)]
        resp = self.api.post(self.url, {
            'intervention': self.interv.id, 'positions': points}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_point_sans_heure_400(self):
        resp = self.api.post(self.url, {
            'intervention': self.interv.id, 'positions': [dict(DEDANS)]},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_lot_rattrape_apres_un_releve_live_plus_recent(self):
        """F2 — relevé live DEDANS à T, puis lot hors-ligne [T-10 dehors,
        T-5 dedans] : exactement une sortie puis une entrée, aucune sortie
        ouverte à la fin (la vraie sortie suivante est donc journalisée)."""
        self.assertEqual(self.ping(DEDANS).status_code, 201)
        resp = self.api.post(self.url, {
            'intervention': self.interv.id,
            'positions': [self._point(10, DEHORS), self._point(5, DEDANS)],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        types = list(GeofenceAlert.objects.filter(intervention=self.interv)
                     .order_by('created_at', 'id')
                     .values_list('type_franchissement', flat=True))
        self.assertEqual(types, ['sortie', 'entree'])
        self.assertFalse(gps_tracking_service._sortie_deja_ouverte(self.interv))
        sortie = self.ping(DEHORS)
        self.assertEqual(sortie.data['geofence_alert']['type_franchissement'], 'sortie')

    def _terminer(self, **champs):
        self.interv.statut = Intervention.Statut.TERMINEE
        for nom, valeur in champs.items():
            setattr(self.interv, nom, valeur)
        self.interv.save(update_fields=['statut', *champs])

    def test_lot_apres_cloture_accepte_si_releve_avant_la_fin(self):
        """F3 — le tampon relevé pendant la session, envoyé après « terminée »,
        est reçu ; un point postérieur au retour dépôt est refusé (409)."""
        self._terminer(retour_depot_le=timezone.now() - timedelta(minutes=30))
        resp = self.api.post(self.url, {
            'intervention': self.interv.id, 'positions': [self._point(60)]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['enregistrees'], 1)
        apres = self.api.post(self.url, {
            'intervention': self.interv.id,
            'positions': [self._point(45), self._point(10)]}, format='json')
        self.assertEqual(apres.status_code, 409, apres.content)
        self.assertEqual(
            PositionTechnicien.objects.filter(intervention=self.interv).count(), 1)
        # Le ping LIVE reste fermé sur une intervention close.
        self.assertEqual(self.ping(DEDANS).status_code, 409)

    def test_lot_apres_cloture_borne_par_la_date_realisee(self):
        self._terminer(date_realisee=timezone.localdate())
        resp = self.api.post(self.url, {
            'intervention': self.interv.id, 'positions': [self._point(5)]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_lot_apres_cloture_sans_fin_connue_409(self):
        self._terminer()
        resp = self.api.post(self.url, {
            'intervention': self.interv.id, 'positions': [self._point(5)]},
            format='json')
        self.assertEqual(resp.status_code, 409, resp.content)

    def test_lot_garde_le_consentement(self):
        autre = make_user(self.company, role='normal')
        self.interv.equipe.add(autre)
        resp = auth(autre).post(self.url, {
            'intervention': self.interv.id, 'positions': [self._point(3)]},
            format='json')
        self.assertEqual(resp.status_code, 403, resp.content)


class SortiePerimetreTests(Base):
    def setUp(self):
        super().setUp()
        consentement_accepte(self.company, self.technicien)

    def sorties(self):
        return GeofenceAlert.objects.filter(
            intervention=self.interv,
            type_franchissement=GeofenceAlert.TypeFranchissement.SORTIE)

    def test_en_route_loin_du_chantier_naleve_aucune_alerte(self):
        self.interv.statut = Intervention.Statut.EN_ROUTE
        self.interv.save(update_fields=['statut'])
        for _ in range(3):
            self.assertEqual(self.ping(DEHORS).status_code, 201)
        self.assertFalse(GeofenceAlert.objects.exists())
        # À l'arrivée, l'entrée est posée toute seule (NTMOB9 inchangé).
        resp = self.ping(DEDANS)
        self.assertEqual(resp.data['geofence_alert']['type_franchissement'], 'entree')

    def test_une_seule_sortie_ouverte_jusqua_la_reentree(self):
        self.ping(DEDANS)
        for _ in range(4):
            self.ping(DEHORS)
        self.assertEqual(self.sorties().count(), 1)
        self.ping(DEDANS)  # ré-entrée
        self.ping(DEHORS)
        self.ping(DEHORS)
        self.assertEqual(self.sorties().count(), 2)
        types = list(GeofenceAlert.objects.filter(intervention=self.interv)
                     .order_by('created_at', 'id')
                     .values_list('type_franchissement', flat=True))
        self.assertEqual(types, ['sortie', 'entree', 'sortie'])

    def test_sortie_acquittee_ne_rouvre_pas_avant_reentree(self):
        self.ping(DEHORS)
        self.sorties().update(acquittee=True)
        self.ping(DEHORS)
        self.assertEqual(self.sorties().count(), 1)

    def test_nouvelle_sortie_notifie_le_responsable(self):
        with mock.patch(
                'apps.notifications.services.notify_many') as notify_many:
            with self.captureOnCommitCallbacks(execute=True):
                self.ping(DEHORS)
            with self.captureOnCommitCallbacks(execute=True):
                self.ping(DEHORS)  # même sortie ouverte : pas de 2e alerte
        self.assertEqual(notify_many.call_count, 1)
        destinataires = notify_many.call_args.args[0]
        self.assertEqual([u.id for u in destinataires], [self.responsable.id])
        self.assertEqual(notify_many.call_args.kwargs['link'],
                         '/planification/suivi-gps')

    def test_rayon_propre_au_chantier(self):
        site = self.interv.installation
        site.geofence_rayon_m = 10000  # 10 km : le point à ~5 km est dedans
        site.save(update_fields=['geofence_rayon_m'])
        resp = self.ping(DEHORS)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertFalse(resp.data['hors_perimetre'])
        self.assertFalse(self.sorties().exists())


class PurgeEtPresenceTests(Base):
    def setUp(self):
        super().setUp()
        consentement_accepte(self.company, self.technicien)
        self.t0 = timezone.now() - timedelta(hours=6)

    def poser(self, point, minutes):
        return gps_tracking_service.enregistrer_position(
            self.company, self.technicien, float(point['lat']),
            float(point['lng']), intervention=self.interv,
            captured_at=self.t0 + timedelta(minutes=minutes))

    def test_presence_premiere_entree_derniere_sortie_duree(self):
        self.poser(DEHORS, 0)
        self.poser(DEDANS, 10)
        self.poser(DEDANS, 100)
        self.poser(DEDANS, 250)
        self.poser(DEHORS, 260)
        presence = gps_tracking_service.presence_intervention(self.interv)
        self.assertEqual(presence['premiere_entree'], self.t0 + timedelta(minutes=10))
        self.assertEqual(presence['derniere_sortie'], self.t0 + timedelta(minutes=250))
        self.assertEqual(presence['duree_sur_site_min'], 240)
        self.assertEqual(presence['nb_positions'], 5)
        self.assertEqual(presence['source_debut'], 'positions')
        self.assertEqual(presence['derniere_position']['captured_at'],
                         self.t0 + timedelta(minutes=260))

    def test_presence_sans_position_retombe_sur_le_pointage(self):
        self.interv.arrivee_site_le = self.t0
        self.interv.save(update_fields=['arrivee_site_le'])
        presence = gps_tracking_service.presence_intervention(self.interv)
        self.assertEqual(presence['premiere_entree'], self.t0)
        self.assertEqual(presence['source_debut'], 'pointage')
        self.assertIsNone(presence['duree_sur_site_min'])
        self.assertIsNone(presence['derniere_position'])

    def test_purge_garde_les_alertes_et_la_presence(self):
        ancien = timezone.now() - timedelta(days=40)
        for minutes, point in ((0, DEHORS), (10, DEDANS), (200, DEHORS)):
            gps_tracking_service.enregistrer_position(
                self.company, self.technicien, float(point['lat']),
                float(point['lng']), intervention=self.interv,
                captured_at=ancien + timedelta(minutes=minutes))
        self.assertEqual(GeofenceAlert.objects.filter(intervention=self.interv).count(), 3)

        from apps.installations.tasks import purger_positions_gps_task
        self.assertEqual(purger_positions_gps_task(), 3)

        self.assertFalse(PositionTechnicien.objects.exists())
        alertes = GeofenceAlert.objects.filter(intervention=self.interv)
        self.assertEqual(alertes.count(), 3)
        self.assertTrue(all(a.position_id is None for a in alertes))
        presence = gps_tracking_service.presence_intervention(self.interv)
        self.assertEqual(presence['source_debut'], 'alertes')
        # F4 — datée du RELEVÉ, pas de l'insertion de l'alerte (aujourd'hui).
        self.assertEqual(presence['premiere_entree'], ancien + timedelta(minutes=10))
        self.assertEqual(presence['derniere_sortie'], ancien + timedelta(minutes=200))
        self.assertEqual(presence['duree_sur_site_min'], 190)
        self.assertEqual(presence['nb_positions'], 0)

    def test_endpoint_presence_forme_du_contrat(self):
        self.poser(DEHORS, 0)
        self.poser(DEDANS, 5)
        self.poser(DEDANS, 65)
        resp = auth(self.responsable).get(
            f'{BASE}/interventions/{self.interv.id}/presence/')
        self.assertEqual(resp.status_code, 200, resp.content)
        contrat = json.loads(
            (CONTRATS / 'intervention_presence.json').read_text(encoding='utf-8'))
        self.assertEqual(set(resp.data), set(contrat['exemple']))
        self.assertEqual(set(resp.data['derniere_position']),
                         set(contrat['exemple']['derniere_position']))
        self.assertEqual(resp.data['duree_sur_site_min'], 60)
        self.assertEqual(resp.data['intervention'], self.interv.id)

    def test_endpoint_presence_vide_et_isolation(self):
        resp = auth(self.responsable).get(
            f'{BASE}/interventions/{self.interv.id}/presence/')
        self.assertEqual(resp.status_code, 200, resp.content)
        contrat = json.loads(
            (CONTRATS / 'intervention_presence.json').read_text(encoding='utf-8'))
        self.assertEqual(
            {k: v for k, v in resp.data.items() if k != 'intervention'},
            {k: v for k, v in contrat['exemple_vide'].items()
             if k != 'intervention'})
        autre_co = make_company()
        etranger = make_user(autre_co)
        resp = auth(etranger).get(
            f'{BASE}/interventions/{self.interv.id}/presence/')
        self.assertEqual(resp.status_code, 404, resp.content)
        resp = auth(etranger).get(f'{BASE}/interventions/99999999999/presence/')
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_presence_membre_sans_point_de_carte(self):
        """F1 — le technicien membre lit son temps sur site, jamais un point
        de carte ; le responsable garde la réponse complète."""
        self.poser(DEHORS, 0)
        self.poser(DEDANS, 5)
        self.poser(DEDANS, 65)
        url = f'{BASE}/interventions/{self.interv.id}/presence/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['duree_sur_site_min'], 60)
        self.assertIsNone(resp.data['derniere_position'])
        complet = auth(self.responsable).get(url)
        self.assertIsNotNone(complet.data['derniere_position'])

    def test_presence_collegue_non_membre_403(self):
        """F1 — portée « toute la société » d'un rôle sans marqueur d'équipe :
        un collègue ne lit pas la présence (ni la position) d'un autre."""
        self.poser(DEDANS, 5)
        collegue = make_user(self.company, role='normal')
        resp = auth(collegue).get(
            f'{BASE}/interventions/{self.interv.id}/presence/')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertNotIn('derniere_position', resp.data)


class LecturesTests(Base):
    def setUp(self):
        super().setUp()
        consentement_accepte(self.company, self.technicien)

    def test_carte_live_ecarte_les_positions_trop_vieilles(self):
        PositionTechnicien.objects.create(
            company=self.company, technicien=self.technicien,
            intervention=self.interv, lat=Decimal('33.5'), lng=Decimal('-7.6'),
            captured_at=timezone.now() - timedelta(minutes=30))
        api = auth(self.responsable)
        resp = api.get(f'{BASE}/positions-techniciens/carte-live/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data, [])
        resp = api.get(f'{BASE}/positions-techniciens/carte-live/?max_age_min=60')
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(
            api.get(f'{BASE}/positions-techniciens/carte-live/?max_age_min=abc').status_code,
            400)

    def test_carte_live_une_ligne_par_technicien_la_plus_recente(self):
        self.ping(DEHORS)
        derniere = self.ping(DEDANS)
        resp = auth(self.responsable).get(f'{BASE}/positions-techniciens/carte-live/')
        self.assertEqual([p['id'] for p in resp.data], [derniere.data['id']])

    def test_le_technicien_ne_voit_pas_la_carte_ni_les_positions_des_autres(self):
        self.ping(DEDANS)
        self.assertEqual(
            self.api.get(f'{BASE}/positions-techniciens/carte-live/').status_code, 403)
        self.assertEqual(
            self.api.get(f'{BASE}/positions-techniciens/').status_code, 403)

    def test_trace_du_jour_chronologique_non_pagine(self):
        # Instants ancrés à MIDI LOCAL du jour courant : un run CI autour de
        # minuit (Casablanca) ne doit pas faire glisser « now − 30 min » sur
        # la veille (rouge CI du 27/10/2026 : 0 != 3).
        midi = timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0)
        for m in (30, 20, 10):
            gps_tracking_service.enregistrer_position(
                self.company, self.technicien, 33.5731, -7.5898,
                intervention=self.interv,
                captured_at=midi - timedelta(minutes=m))
        jour = timezone.localdate(midi).isoformat()
        resp = auth(self.responsable).get(
            f'{BASE}/positions-techniciens/?technicien={self.technicien.id}&date={jour}')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsInstance(resp.data, list)
        instants = [p['captured_at'] for p in resp.data]
        self.assertEqual(len(instants), 3)
        self.assertEqual(instants, sorted(instants))

    def test_mes_positions_ne_rend_que_les_miennes(self):
        self.ping(DEDANS)
        collegue = make_user(self.company, role='normal')
        PositionTechnicien.objects.create(
            company=self.company, technicien=collegue, intervention=self.interv,
            lat=Decimal('33.5'), lng=Decimal('-7.6'))
        resp = self.api.get(f'{BASE}/positions-techniciens/mes-positions/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual({p['technicien'] for p in resp.data}, {self.technicien.id})
        self.assertEqual(len(resp.data), 1)
        hier = (timezone.localdate() - timedelta(days=1)).isoformat()
        resp = self.api.get(f'{BASE}/positions-techniciens/mes-positions/?date={hier}')
        self.assertEqual(resp.data, [])


class IsolationSocieteTests(TestCase):
    """Chaque route neuve reste dans la société de l'appelant."""

    def setUp(self):
        self.co_a, self.co_b = make_company(), make_company()
        self.resp_a, self.resp_b = make_user(self.co_a), make_user(self.co_b)
        self.tech_a = make_user(self.co_a, role='normal')
        self.tech_b = make_user(self.co_b, role='normal')
        consentement_accepte(self.co_a, self.tech_a)
        consentement_accepte(self.co_b, self.tech_b)
        self.interv_a = make_intervention(self.co_a, self.resp_a, self.tech_a)
        self.interv_b = make_intervention(self.co_b, self.resp_b, self.tech_b)
        for co, tech, interv in ((self.co_a, self.tech_a, self.interv_a),
                                 (self.co_b, self.tech_b, self.interv_b)):
            gps_tracking_service.enregistrer_position(
                co, tech, float(DEDANS['lat']), float(DEDANS['lng']),
                intervention=interv)

    def test_carte_live_et_trace(self):
        api = auth(self.resp_a)
        carte = api.get(f'{BASE}/positions-techniciens/carte-live/')
        self.assertEqual({p['technicien'] for p in carte.data}, {self.tech_a.id})
        jour = timezone.localdate().isoformat()
        trace = api.get(
            f'{BASE}/positions-techniciens/?technicien={self.tech_b.id}&date={jour}')
        self.assertEqual(trace.status_code, 200, trace.content)
        self.assertEqual(trace.data, [])

    def test_mes_positions_et_mon_consentement(self):
        api = auth(self.tech_a)
        mes = api.get(f'{BASE}/positions-techniciens/mes-positions/')
        self.assertEqual({p['technicien'] for p in mes.data}, {self.tech_a.id})
        mon = api.get(f'{BASE}/gps-consentements/mon-consentement/')
        self.assertEqual(mon.data['statut'], 'actif')
        self.assertEqual(
            GpsConsentRecord.objects.filter(technicien=self.tech_b).count(), 1)

    def test_ping_lot_sur_intervention_etrangere_400(self):
        resp = auth(self.tech_a).post(
            f'{BASE}/positions-techniciens/ping-lot/', {
                'intervention': self.interv_b.id,
                'positions': [dict(DEDANS, captured_at=timezone.now().isoformat())],
            }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_presence_etrangere_404(self):
        resp = auth(self.resp_a).get(
            f'{BASE}/interventions/{self.interv_b.id}/presence/')
        self.assertEqual(resp.status_code, 404)


class SerializerInterventionTests(Base):
    def test_champs_gps_sur_lintervention(self):
        api = auth(self.responsable)
        url = f'{BASE}/interventions/{self.interv.id}/'
        self.assertEqual(api.get(url).data['gps_consentement'], 'absent')
        self.assertTrue(api.get(url).data['gps_tracking_required'])

        gps_tracking_service.record_consent(self.company, self.technicien)
        self.assertEqual(api.get(url).data['gps_consentement'], 'a_accepter')
        gps_tracking_service.accepter_consentement(self.company, self.technicien)
        self.assertEqual(api.get(url).data['gps_consentement'], 'actif')
        gps_tracking_service.revoke_consent(self.company, self.technicien)
        self.assertEqual(api.get(url).data['gps_consentement'], 'revoque')

        self.interv.statut = Intervention.Statut.PRETE
        self.interv.save(update_fields=['statut'])
        self.assertFalse(api.get(url).data['gps_tracking_required'])

    def test_liste_sans_n_plus_1_sur_le_consentement(self):
        for _ in range(3):
            tech = make_user(self.company, role='normal')
            consentement_accepte(self.company, tech)
            make_intervention(self.company, self.responsable, tech)
        api = auth(self.responsable)
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            resp = api.get(f'{BASE}/interventions/')
        self.assertEqual(resp.status_code, 200, resp.content)
        lignes = liste(resp)
        self.assertGreaterEqual(len(lignes), 4)
        requetes_consentement = [
            q['sql'] for q in ctx.captured_queries
            if 'installations_gpsconsentrecord' in q['sql']]
        # UNE requête pour toute la page, quel que soit le nombre de lignes.
        self.assertEqual(len(requetes_consentement), 1, requetes_consentement)
        statuts = {r['technicien']: r['gps_consentement'] for r in lignes}
        self.assertEqual(statuts[self.technicien.id], 'absent')
        self.assertEqual(
            sorted(v for k, v in statuts.items() if k != self.technicien.id),
            ['actif', 'actif', 'actif'])


class Migration0132RetourArriereTests(Base):
    """F5 — le retour arrière de 0132 ne bute pas sur les alertes purgées."""

    def setUp(self):
        super().setUp()
        import importlib
        self.module = importlib.import_module(
            'apps.installations.migrations.0132_gps_consentement_geofence')

    def test_runpython_apres_alterfield_donc_defait_avant(self):
        from django.db import migrations
        ops = self.module.Migration.operations
        i_alter = next(i for i, op in enumerate(ops)
                       if isinstance(op, migrations.AlterField)
                       and op.name == 'position')
        i_run = next(i for i, op in enumerate(ops)
                     if isinstance(op, migrations.RunPython))
        self.assertGreater(i_run, i_alter)
        self.assertIs(ops[i_run].reverse_code,
                      self.module._supprimer_alertes_sans_position)

    def test_reverse_supprime_seulement_les_alertes_sans_position(self):
        from django.apps import apps as registre
        consentement_accepte(self.company, self.technicien)
        self.ping(DEHORS)
        self.ping(DEDANS)
        self.assertEqual(GeofenceAlert.objects.count(), 2)
        GeofenceAlert.objects.filter(
            type_franchissement=GeofenceAlert.TypeFranchissement.SORTIE,
        ).update(position=None)
        self.module._supprimer_alertes_sans_position(registre, None)
        self.assertEqual(
            list(GeofenceAlert.objects.values_list('type_franchissement', flat=True)),
            ['entree'])
