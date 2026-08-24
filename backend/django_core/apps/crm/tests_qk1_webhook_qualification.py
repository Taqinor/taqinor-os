"""QK1 — Le webhook du site ne jette plus la qualification captée.

Couvre :
  - Un lead web atterrit avec facture/GPS/toiture/mode/distributeur/
    qualification remplis (aucune re-demande au prospect) ;
  - Les nouveaux champs additifs (distributeur, roof_age, ownership,
    project_timeline, financing_intent, futures_charges) ;
  - Le mapping mode marché → type_installation et langue → langue_preferee ;
  - La tolérance : valeurs invalides ignorées, jamais de crash ;
  - Le scoping société forcé côté serveur (jamais du payload).
"""

import json

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from .models import Lead

SECRET = 'test-secret-qk1'


def payload_site(**extra):
    """Charge utile de la forme émise par apps/web (capture-lead.ts)."""
    base = {
        'fullName': 'Youssef El Amrani',
        'phoneE164': '+212661000111',
        'whatsappOptIn': True,
        'city': 'Rabat',
        'roofType': 'villa',
        'billRange': '1500-3000',
        'consent': True,
        'qualified': True,
        'band': {'kwcLabel': '5 à 9 kWc', 'paybackLabel': '4 à 6 ans'},
        'page': '/devis/mon-toit',
    }
    base.update(extra)
    return base


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class WebhookQualificationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QK1 Co', slug='qk1-co')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_lead_web_atterrit_avec_toute_la_capture(self):
        """Facture exacte, GPS, contour, raccordement, mode, e-mail, langue,
        distributeur + qualification : tout est persisté en un seul POST."""
        res = self.post(payload_site(
            factureHiver='1850.50', factureEte='950', eteDifferente=True,
            billKwh='420',
            gpsLat='33.589', gpsLng='-7.603',
            roofPoint={'lat': 33.589, 'lng': -7.603},
            roofOutline=[[33.589, -7.603], [33.590, -7.603], [33.590, -7.604]],
            raccordement='triphase',
            marketMode='residentiel',
            email='youssef@example.ma',
            langue='fr',
            distributeur='lydec',
            roofAge='12',
            ownership='proprietaire',
            projectTimeline='immediat',
            financingIntent='cash',
            futuresCharges=['ve', 'clim'],
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        # Company forcée côté serveur.
        self.assertEqual(lead.company, self.company)
        # Facture / profil énergie
        self.assertEqual(str(lead.facture_hiver), '1850.50')
        self.assertEqual(str(lead.facture_ete), '950.00')
        self.assertTrue(lead.ete_differente)
        self.assertEqual(str(lead.bill_kwh), '420.00')
        # GPS + toiture
        self.assertEqual(str(lead.gps_lat), '33.589000')
        self.assertEqual(str(lead.gps_lng), '-7.603000')
        self.assertEqual(lead.roof_point, {'lat': 33.589, 'lng': -7.603})
        self.assertEqual(len(lead.roof_outline), 3)
        # Raccordement + mode + e-mail + langue
        self.assertEqual(lead.raccordement, 'triphase')
        self.assertEqual(lead.type_installation, 'residentiel')
        self.assertEqual(lead.email, 'youssef@example.ma')
        self.assertEqual(lead.langue_preferee, 'fr')
        # QK1 — qualification
        self.assertEqual(lead.distributeur, 'lydec')
        self.assertEqual(lead.roof_age, 12)
        self.assertEqual(lead.ownership, 'proprietaire')
        self.assertEqual(lead.project_timeline, 'immediat')
        self.assertEqual(lead.financing_intent, 'cash')
        self.assertEqual(lead.futures_charges, ['clim', 've'])

    def test_snake_case_et_alias_acceptes(self):
        res = self.post(payload_site(
            market_mode='industrial',      # alias EN → industriel
            language='ar',                 # arabe du site → darija (WhatsApp)
            utility='onee',                # alias 'utility' → distributeur
            roof_age=25,
            project_timeline='3_mois',
            financing_intent='credit',
            futures_charges={'pompe': True, 've': False, 'inconnu': True},
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.type_installation, 'industriel')
        self.assertEqual(lead.langue_preferee, 'darija')
        self.assertEqual(lead.distributeur, 'onee')
        self.assertEqual(lead.roof_age, 25)
        self.assertEqual(lead.project_timeline, '3_mois')
        self.assertEqual(lead.financing_intent, 'credit')
        # Dict → liste filtrée sur les clés autorisées et véridiques.
        self.assertEqual(lead.futures_charges, ['pompe'])

    def test_valeurs_invalides_ignorees_jamais_de_crash(self):
        res = self.post(payload_site(
            marketMode='fusion-nucleaire',
            langue='klingon',
            distributeur='edf',
            roofAge='-3',
            ownership='squatteur',
            projectTimeline='un-jour',
            financingIntent='troc',
            futuresCharges='pas-une-liste',
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.type_installation)
        self.assertIsNone(lead.langue_preferee)
        self.assertIsNone(lead.distributeur)
        self.assertIsNone(lead.roof_age)
        self.assertIsNone(lead.ownership)
        self.assertIsNone(lead.project_timeline)
        self.assertIsNone(lead.financing_intent)
        self.assertIsNone(lead.futures_charges)

    def test_champs_absents_comportement_inchange(self):
        res = self.post(payload_site())
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.distributeur)
        self.assertIsNone(lead.roof_age)
        self.assertIsNone(lead.ownership)
        self.assertIsNone(lead.project_timeline)
        self.assertIsNone(lead.financing_intent)
        self.assertIsNone(lead.futures_charges)

    def test_visiteur_revenant_complete_sans_ecraser(self):
        """Un second POST plus riche complète le lead existant (dedup) ;
        un POST plus pauvre n'efface pas la qualification déjà captée."""
        first = self.post(payload_site(ownership='proprietaire',
                                       financingIntent='cash'))
        self.assertEqual(first.status_code, 201)
        # Re-POST < 60 s : complète avec le timeline, sans perdre ownership.
        retry = self.post(payload_site(projectTimeline='immediat'))
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(Lead.objects.count(), 1)
        lead = Lead.objects.get()
        self.assertEqual(lead.ownership, 'proprietaire')
        self.assertEqual(lead.financing_intent, 'cash')
        self.assertEqual(lead.project_timeline, 'immediat')

    def test_company_jamais_lue_du_payload(self):
        autre = Company.objects.create(nom='Intrus', slug='intrus-qk1')
        res = self.post(payload_site(company=autre.pk, company_id=autre.pk))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        # Résolue côté serveur : première Company (setUp), jamais du corps.
        self.assertEqual(lead.company, self.company)

    # ── Bug fondateur 24/08 : tracé perdu (pin posé, puis dessiné, seul le pin
    # atterrissait en CRM). La cause était côté client (apps/web/src/scripts/
    # roofPro11/captureBoot.ts — un clic APRÈS la fermeture du contour effaçait
    # `vertices`/`closed` en silence). Ces tests couvrent la moitié BACKEND du
    # contrat : le contour, quand il arrive au webhook, est posé ; absent, il
    # ne touche rien ; invalide, il est ignoré proprement ; et un re-POST SANS
    # contour (visiteur revenant, session raccourcie...) n'efface JAMAIS un
    # contour déjà capté — même discipline que la garde GPS/attribution
    # first-touch déjà en place pour les autres champs additifs.
    def test_roof_outline_absent_ne_persiste_rien(self):
        """Aucun roofOutline dans le payload → lead.roof_outline reste None
        (le pin seul, lui, est bien posé)."""
        res = self.post(payload_site(
            roofPoint={'lat': 33.589, 'lng': -7.603}))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.roof_point, {'lat': 33.589, 'lng': -7.603})
        self.assertIsNone(lead.roof_outline)

    def test_roof_outline_invalide_ignore_proprement(self):
        """Un roofOutline malformé (pas une liste, ou < 3 points valides) est
        écarté silencieusement — jamais d'erreur 500, jamais de valeur
        aberrante persistée."""
        res = self.post(payload_site(
            roofPoint={'lat': 33.589, 'lng': -7.603},
            roofOutline='pas-une-liste'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.roof_outline)

        res2 = self.post(payload_site(
            phoneE164='+212661000222',
            roofPoint={'lat': 33.589, 'lng': -7.603},
            # Un seul point valide : sous le minimum de 3 sommets d'un polygone.
            roofOutline=[[33.589, -7.603]]))
        self.assertEqual(res2.status_code, 201, res2.content)
        lead2 = Lead.objects.get(pk=res2.json()['lead_id'])
        self.assertIsNone(lead2.roof_outline)

    def test_visiteur_revenant_sans_polygone_necrase_pas_lexistant(self):
        """Scénario du bug fondateur, côté serveur : un premier POST pose le
        contour tracé ; un second POST du même visiteur (dedup téléphone),
        SANS roofOutline cette fois (ex. un re-POST du pin seul après une
        manip qui l'a effacé côté client), ne doit JAMAIS écraser le contour
        déjà capté par du vide — même esprit que la garde GPS existante."""
        outline = [[33.589, -7.603], [33.590, -7.603], [33.590, -7.604]]
        first = self.post(payload_site(
            roofPoint={'lat': 33.589, 'lng': -7.603},
            roofOutline=outline))
        self.assertEqual(first.status_code, 201, first.content)
        lead_id = first.json()['lead_id']
        lead = Lead.objects.get(pk=lead_id)
        self.assertEqual(len(lead.roof_outline), 3)

        # Re-POST < 60 s (même téléphone) : SANS roofOutline cette fois.
        retry = self.post(payload_site(
            roofPoint={'lat': 33.589, 'lng': -7.603}))
        self.assertEqual(retry.status_code, 200, retry.content)
        self.assertEqual(Lead.objects.count(), 1)
        lead.refresh_from_db()
        # Le contour déjà capté survit — jamais écrasé par un payload plus pauvre.
        self.assertEqual(len(lead.roof_outline), 3)
        self.assertEqual(lead.roof_outline, outline)
