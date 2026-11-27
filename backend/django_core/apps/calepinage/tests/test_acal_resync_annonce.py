"""ACAL38 (D-ACAL-1, C-ACAL-109) — « Resynchroniser le devis » depuis le module
annonce ENFIN ``layout_finalise``, UNE fois, sans rien réécrire du calepinage.

Catalogue tarifé réel, HTTP réel ; l'abonné crm (note au chatter du lead) est
le VRAI récepteur ; seul un compteur d'émissions est branché sur le signal.

Run :
    python manage.py test apps.calepinage.tests.test_acal_resync_annonce -v2
"""
import copy
from decimal import Decimal

from django.test import SimpleTestCase

from core import events

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.layout import enregistrer_layout

from .test_api_liste import BaseApiCalepinage, url_detail

TOIT = {
    'areas': [{'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
               'obstacles': [], 'roofType': 'flat', 'pitch': 10,
               'azimuth': 180}],
    'scenario': 'reseau',
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
}


def _materiel(apercu):
    """Les écarts de MATÉRIEL de l'aperçu (round 4 : le toit plat de ``TOIT`` sans tables y ajoute
    aussi la phrase des 20° supposés, champ ``geometry.tiltDeg``, la même qu'à la génération)."""
    return [e for e in apercu['ecarts'] if e['champ'] != 'geometry.tiltDeg']


class ResyncAnnonceTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue
        seed_catalogue(self.company)
        # ACAL922 — lead DIMENSIONNÉ : « Générer » ne pose pas la question.
        self.lead.taille_souhaitee_kwc = Decimal('5')
        self.lead.save(update_fields=['taille_souhaitee_kwc'])
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL38')
        enregistrer_layout(self.calepinage, copy.deepcopy(TOIT),
                           user=self.user)
        self.base = url_detail(self.calepinage.pk)
        reponse = self.api.post(f'{self.base}generer-devis/', {},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.emissions = []

        def compter(sender, devis=None, **kwargs):
            self.emissions.append(getattr(devis, 'pk', None))
        self._compteur = compter
        events.layout_finalise.connect(compter, weak=False,
                                       dispatch_uid='acal38_compteur')

    def tearDown(self):
        events.layout_finalise.disconnect(dispatch_uid='acal38_compteur')
        super().tearDown()

    def test_resync_module_emet_layout_finalise_une_fois_sans_version(self):
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 14
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        self.calepinage.refresh_from_db()
        document_avant = copy.deepcopy(self.calepinage.roof_layout)
        versions_avant = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()

        reponse = self.api.post(f'{self.base}sync-devis/', {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

        self.assertEqual(len(self.emissions), 1)
        self.assertEqual(self.emissions[0], self.calepinage.devis_id)
        self.calepinage.refresh_from_db()
        # Aucune version déposée par la resynchro, aucun document réécrit.
        self.assertEqual(CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count(), versions_avant)
        self.assertEqual(self.calepinage.roof_layout, document_avant)
        self.assertNotIn('_pans_geometry', self.calepinage.roof_layout)

    # ── ACAL1320 (D-ACAL-73 = corriger_dire) — l'aperçu de « Resynchroniser le devis » ──
    def _etat_ecrit(self):
        """Tout ce qu'une resynchronisation écrirait : le devis (toutes ses colonnes : statut,
        empreinte, échéancier, cache PDF, clauses, ``updated_at``), ses lignes, son journal, ses
        instantanés, ses liens de partage, le chatter du lead et le calepinage."""
        from apps.crm.models import LeadActivity
        from apps.ventes.models import ConfigurationDevisSnapshot, Devis, DevisActivity, LigneDevis, ShareLink

        pk = Calepinage.objects.get(pk=self.calepinage.pk).devis_id
        return {
            'devis': list(Devis.objects.filter(pk=pk).values()),
            'lignes': list(LigneDevis.objects.filter(devis_id=pk).order_by('pk').values()),
            'journal': list(DevisActivity.objects.filter(devis_id=pk).order_by('pk').values_list('pk', flat=True)),
            'instantanes': ConfigurationDevisSnapshot.objects.filter(devis_id=pk).count(),
            'liens': list(ShareLink.objects.filter(devis_id=pk).order_by('pk').values()),
            'chatter': LeadActivity.objects.filter(lead_id=self.lead.pk).count(),
            'calepinage': list(Calepinage.objects.filter(pk=self.calepinage.pk).values()),
        }

    def _apercu_resync(self, client=None, **params):
        reponse = (client or self.api).get(f'{self.base}apercu-resync/', params)
        return reponse

    def test_acal1320_apercu_dit_ce_qui_change_et_n_ecrit_rien(self):
        """Devis ENVOYÉ, pose 12 → 14 panneaux : l'aperçu dit la ligne de panneaux qui change, les
        totaux avant → après et que le devis reçu par le client sera corrigé ; RIEN n'est écrit
        (devis, lignes, journal, note, instantané, liens, chatter, calepinage, annonce, rappels
        ``on_commit``). Puis la resynchronisation réelle écrit EXACTEMENT ce que l'aperçu annonçait."""
        import json
        import pathlib

        from apps.ventes.models import Devis

        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 14
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        self.calepinage.refresh_from_db()
        Devis.objects.filter(pk=self.calepinage.devis_id).update(statut='envoye')
        from apps.calepinage.services.devis_resync_apercu import apercu_resynchronisation

        avant = self._etat_ecrit()
        reponse = self._apercu_resync()
        self.assertEqual(reponse.status_code, 200, reponse.data)
        with self.captureOnCommitCallbacks(execute=False) as rappels:  # le service seul, hors requête HTTP
            direct = apercu_resynchronisation(Calepinage.objects.get(pk=self.calepinage.pk), user=self.user)
        self.assertEqual(rappels, [])  # ceux du geste joué sont abandonnés avec son point de sauvegarde
        self.assertEqual(direct, reponse.data)
        self.assertEqual(self.emissions, [])
        self.assertEqual(self._etat_ecrit(), avant)
        contrat = json.loads((pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
                              / 'calepinage_apercu_resync.json').read_text(encoding='utf-8'))
        self.assertEqual(set(reponse.data), set(contrat['exemple']))
        apercu = reponse.data
        self.assertEqual((apercu['inchange'], apercu['statut'], apercu['corrige_apres_envoi']),
                         (False, 'envoye', True))
        panneaux = [c for c in apercu['changements'] if c['designation_apres'].startswith('Panneau')]
        self.assertEqual([c['quantite_apres'] for c in panneaux], ['14.00'], apercu)  # la pose : 14 panneaux
        self.assertNotEqual(panneaux[0]['quantite_avant'], '14.00')
        self.assertEqual(set(panneaux[0]), set(contrat['exemple']['changements'][0]))
        self.assertNotEqual(apercu['totaux']['avant']['ttc'], apercu['totaux']['apres']['ttc'])

        reel = self.api.post(f'{self.base}sync-devis/', {}, format='json')
        self.assertEqual(reel.status_code, 200, reel.data)
        devis = Devis.objects.get(pk=self.calepinage.devis_id)
        self.assertEqual(str(devis.total_ttc.quantize(Decimal('0.01'))), apercu['totaux']['apres']['ttc'])
        self.assertEqual(reel.data['avertissements'], apercu['avertissements'])
        self.assertEqual(devis.statut, 'envoye')  # corrigé sur place, statut lu jamais écrit (règle #4)
        self.assertTrue(devis.activites.filter(field='correction_apres_envoi').exists())

    def test_acal1320_rien_a_changer_ne_dit_rien_et_n_ecrit_rien(self):
        avant = self._etat_ecrit()
        reponse = self._apercu_resync()
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['inchange'], reponse.data)
        self.assertEqual((reponse.data['ajouts'], reponse.data['retraits'], reponse.data['changements']), ([], [], []))
        self.assertFalse(reponse.data['corrige_apres_envoi'])
        self.assertEqual(self._etat_ecrit(), avant)

    def test_acal1320_devis_accepte_refuse_comme_la_resynchro_sans_rien_ouvrir(self):
        """Un devis ACCEPTÉ : l'aperçu rend le MÊME 409 que la resynchronisation (``revision_possible``)
        — la règle de modifiabilité n'est pas élargie ; rien n'est écrit. 404 hors société."""
        from apps.ventes.models import Devis

        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 14
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        self.calepinage.refresh_from_db()
        Devis.objects.filter(pk=self.calepinage.devis_id).update(statut='accepte')
        avant = self._etat_ecrit()
        apercu = self._apercu_resync()
        reel = self.api.post(f'{self.base}sync-devis/', {}, format='json')
        self.assertEqual((apercu.status_code, reel.status_code), (409, 409), apercu.data)
        self.assertEqual(apercu.data, reel.data)
        self.assertTrue(apercu.data['revision_possible'])
        self.assertEqual(self._etat_ecrit()['lignes'], avant['lignes'])
        etranger = Calepinage.objects.create(company=self.autre, lead_id=self.lead.pk, titre='Autre')
        self.assertEqual(self.api.get(f'{url_detail(etranger.pk)}apercu-resync/').status_code, 404)

    def test_acal1320_sans_lecture_des_devis_ni_reference_ni_montant(self):
        """D-ACAL-106 — un compte qui gère le calepinage sans lire les devis : mêmes clés, aucune
        référence, aucun montant, aucun total ; la désignation et la quantité restent."""
        import json

        from django.contrib.auth import get_user_model

        from apps.roles.models import Role
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
        from apps.ventes.models import Devis

        role = Role.objects.create(company=self.company, nom='A1320 sans devis',
                                   permissions=list(TECHNICIEN_PERMISSIONS) + ['calepinage_gerer'])
        compte = get_user_model().objects.create_user(username='a1320', password='x', company=self.company, role=role)
        from apps.visites.models import VisiteTerrain

        VisiteTerrain.objects.create(company=self.company, lead=self.lead, commercial=compte)  # portée du lead
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 14
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        self.calepinage.refresh_from_db()
        reference = Devis.objects.get(pk=self.calepinage.devis_id).reference
        lecteur = self._apercu_resync()
        cache = self._apercu_resync(self._client(compte))
        self.assertEqual((lecteur.status_code, cache.status_code), (200, 200), cache.data)
        self.assertEqual(set(cache.data), set(lecteur.data))
        self.assertIsNone(cache.data['totaux'])
        self.assertNotIn(reference, json.dumps(cache.data, default=str))
        for ligne in cache.data['changements']:
            self.assertIsNone(ligne['total_ht_apres'])
            self.assertIsNone(ligne['prix_unitaire_avant'])
        self.assertEqual([c['quantite_apres'] for c in cache.data['changements']],
                         [c['quantite_apres'] for c in lecteur.data['changements']])

    def test_revue_sans_lecture_des_devis_aucun_montant_dans_les_avertissements(self):
        """Revue du 26/11 (D-ACAL-106/165) — la phrase du forfait au prix saisi (« barème du stock : …
        MAD HT », ``lignes.avertissement_forfait_verrouille``) n'arrive JAMAIS avec son montant à un compte
        qui gère le calepinage sans lire les devis : ni par l'aperçu, ni par la réponse de ``sync-devis`` ;
        le lecteur des devis la reçoit entière. La phrase vient de la VRAIE fonction de ventes."""
        from unittest import mock

        from django.contrib.auth import get_user_model

        from apps.roles.models import Role
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
        from apps.ventes.domain.lignes import avertissement_forfait_verrouille
        from apps.visites.models import VisiteTerrain

        role = Role.objects.create(company=self.company, nom='Revue sans devis',
                                   permissions=list(TECHNICIEN_PERMISSIONS) + ['calepinage_gerer'])
        compte = get_user_model().objects.create_user(username='revue-165', password='x', company=self.company,
                                                      role=role)
        VisiteTerrain.objects.create(company=self.company, lead=self.lead, commercial=compte)
        phrase = avertissement_forfait_verrouille('Pose', 14, '4 200,00')
        reel = {'inchange': False, 'panneaux': 14, 'kwc': 7.7, 'scenario': 'reseau', 'batterie': False,
                'lignes_modifiees': 1, 'lignes_ajoutees': 0, 'avertissements': [phrase]}
        apercu = {'inchange': False, 'statut': 'brouillon', 'reference': 'DEV-X', 'corrige_apres_envoi': False,
                  'ajouts': [], 'retraits': [], 'changements': [], 'totaux': None, 'avertissements': [phrase],
                  'panneaux': 14, 'kwc': 7.7, 'scenario': 'reseau', 'batterie': False}
        technicien = self._client(compte)
        with mock.patch('apps.calepinage.views.calepinages.resynchroniser_devis', return_value=dict(reel)), \
                mock.patch('apps.ventes.services.apercu_de_resynchronisation', return_value=dict(apercu)):
            for client, attendu in ((technicien, False), (self.api, True)):
                for reponse in (client.post(f'{self.base}sync-devis/', {}, format='json'),
                                client.get(f'{self.base}apercu-resync/')):
                    self.assertEqual(reponse.status_code, 200, reponse.data)
                    texte = ' '.join(reponse.data['avertissements'])
                    self.assertEqual(('4 200,00 MAD HT' in texte), attendu, texte)
                    self.assertIn('« Pose » : prix saisi à la main', texte)

    # ── Lane E6e, item 3 (T4-X5-010) — le devis né de l'atelier et l'onduleur désigné ──
    def _designer(self, nom, **saisie):
        from apps.calepinage.services.electrique import CLE_ENTREE
        from apps.stock.models import Produit

        produit = Produit.objects.get(company=self.company, nom=nom)
        self.calepinage.refresh_from_db()
        resultat = dict(self.calepinage.resultat or {},
                        **{CLE_ENTREE: {'onduleur_produit': produit.pk, **saisie}})
        Calepinage.objects.filter(pk=self.calepinage.pk).update(resultat=resultat)
        self.calepinage.refresh_from_db()
        return produit

    def test_e6e_devis_genere_porte_l_onduleur_du_scenario_pas_le_designe(self):
        """ÉTABLIT ce que fait « Générer le devis » d'un onduleur HYBRIDE désigné sur une pose
        « réseau » : le devis chiffre l'onduleur RÉSEAU du catalogue. Le fondateur n'a pas
        tranché la règle : ce test fige le constat, il ne l'invente pas."""
        from apps.ventes.models import Devis

        Devis.objects.filter(pk=self.calepinage.devis_id).update(is_active=False)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=None)
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 10  # une autre pose : aucun brouillon à la même empreinte
        self.calepinage.refresh_from_db()
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        self._designer('Onduleur hybride Deye 5kW Monophasé')
        reponse = self.api.post(f'{self.base}generer-devis/', {'creer_autre_devis': True}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        devis = Devis.objects.get(pk=Calepinage.objects.get(pk=self.calepinage.pk).devis_id)
        onduleurs = [li.designation for li in devis.lignes.all() if 'nduleur' in li.designation]
        self.assertEqual(onduleurs, ['Onduleur réseau Huawei 5kW Monophasé'], onduleurs)

    def test_e9_apercu_avant_generer_dit_le_materiel_porte_et_l_ecart(self):
        """Lane E9 (T4-X5-010) — AVANT « Générer le devis », ``apercu-devis/`` dit le module et
        l'onduleur que le devis portera (dry-run de LA composition : RIEN d'écrit) et, l'onduleur
        hybride désigné à l'étape Électrique n'étant pas celui-là, UNE phrase qui le dit et pourquoi.
        Ce que l'aperçu annonce est exactement ce que la génération écrit ensuite. 404 hors société."""
        import json
        import pathlib

        from apps.ventes.models import Devis

        Devis.objects.filter(pk=self.calepinage.devis_id).update(is_active=False)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=None)
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 10
        self.calepinage.refresh_from_db()
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        self._designer('Onduleur hybride Deye 5kW Monophasé')
        devis_avant, resultat_avant = Devis.objects.count(), copy.deepcopy(self.calepinage.resultat)
        reponse = self.api.get(f'{self.base}apercu-devis/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        contrat = json.loads((pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
                              / 'calepinage_apercu_devis.json').read_text(encoding='utf-8'))
        self.assertEqual(set(reponse.data), set(contrat['exemple']))
        self.assertEqual(set(reponse.data['options'][0]), set(contrat['exemple']['options'][0]))
        self.assertEqual([o['onduleur'] for o in reponse.data['options']], ['Onduleur réseau Huawei 5kW Monophasé'])
        self.assertEqual([e['champ'] for e in _materiel(reponse.data)], ['onduleur_produit'])
        self.assertIn('« Onduleur hybride Deye 5kW Monophasé »', reponse.data['ecarts'][0]['message'])
        # D-ACAL-148 (relecture, point 4) — la phrase est celle de la décision (ici : aucun nombre
        # d'onduleurs accepté ni établi par un schéma sans fiche) ; l'onduleur porté est lu dans ``options``.
        self.assertIn('le devis garde l’onduleur de la conception du lead', reponse.data['ecarts'][0]['message'])
        self.assertIsNone(reponse.data['refus'])
        self.assertNotIn('prix', json.dumps(reponse.data))
        self.calepinage.refresh_from_db()
        self.assertEqual((Devis.objects.count(), self.calepinage.resultat), (devis_avant, resultat_avant))
        genere = self.api.post(f'{self.base}generer-devis/', {'creer_autre_devis': True}, format='json')
        self.assertEqual(genere.status_code, 201, genere.data)
        devis = Devis.objects.get(pk=Calepinage.objects.get(pk=self.calepinage.pk).devis_id)
        lignes = [li.designation for li in devis.lignes.all()]
        self.assertIn(reponse.data['options'][0]['onduleur'], lignes)
        self.assertIn(reponse.data['options'][0]['module'], lignes)
        etranger = Calepinage.objects.create(company=self.autre, lead_id=self.lead.pk, titre='Autre')
        self.assertEqual(self.api.get(f'{url_detail(etranger.pk)}apercu-devis/').status_code, 404)

    def _nouvelle_pose(self, panneaux=10):
        """Le devis du setUp mis de côté et une AUTRE pose : « Générer » composerait un devis neuf."""
        from apps.ventes.models import Devis

        Devis.objects.filter(pk=self.calepinage.devis_id).update(is_active=False)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=None)
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = panneaux
        self.calepinage.refresh_from_db()
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        self.calepinage.refresh_from_db()

    def test_e9b_apercu_a_blanc_ne_cree_aucun_reglage(self):
        """Lane E9b — l'aperçu est un calcul À BLANC : une société SANS ``CompanyProfile`` ni
        ``TariffSettings`` n'en gagne aucun (``reglages_lus_sans_creer``), aucune écriture parmi
        les requêtes de l'appel. Mutant « aperçu hors du contexte » ⇒ INSERT ⇒ rouge."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.calepinage.services.devis_apercu import apercu_materiel_du_devis
        from apps.parametres.models import CompanyProfile
        from apps.parametres.models_tariff import TariffSettings

        self._nouvelle_pose()
        CompanyProfile.objects.filter(company=self.company).delete()
        TariffSettings.objects.filter(company=self.company).delete()
        with CaptureQueriesContext(connection) as requetes:
            rendu = apercu_materiel_du_devis(self.calepinage)
        self.assertTrue(rendu['options'], rendu)
        ecritures = [q['sql'] for q in requetes.captured_queries
                     if q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(ecritures, [])
        self.assertFalse(CompanyProfile.objects.filter(company=self.company).exists())
        self.assertFalse(TariffSettings.objects.filter(company=self.company).exists())

    def test_e9b_apercu_suit_le_brouillon_que_le_bouton_ouvrirait(self):
        """Lane E9b — « Générer » RENDRAIT le brouillon de même empreinte (lié, ou réutilisable :
        ``devis._brouillon_rendu``) au lieu d'en composer un : l'aperçu lit SES lignes et le dit
        (``source: brouillon_existant`` + sa référence). Mutant « recomposer » ⇒ la ligne
        retouchée du brouillon n'est pas lue ⇒ rouge."""
        from apps.ventes.models import Devis

        self.calepinage.refresh_from_db()  # le lien posé par « Générer » du setUp
        devis = Devis.objects.get(pk=self.calepinage.devis_id)
        ligne = next(li for li in devis.lignes.all() if 'nduleur' in li.designation)
        type(ligne).objects.filter(pk=ligne.pk).update(designation='Onduleur du brouillon retouché')
        for lie in (True, False):  # lié au calepinage, puis réutilisable (même empreinte, délié)
            with self.subTest(lie=lie):
                if not lie:
                    Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=None)
                reponse = self.api.get(f'{self.base}apercu-devis/')
                self.assertEqual(reponse.status_code, 200, reponse.data)
                self.assertEqual((reponse.data['source'], reponse.data['reference']),
                                 ('brouillon_existant', devis.reference))
                self.assertEqual([o['onduleur'] for o in reponse.data['options']], ['Onduleur du brouillon retouché'])
        # Une autre pose : la composition neuve, sans référence.
        self._nouvelle_pose(panneaux=9)
        neuve = self.api.get(f'{self.base}apercu-devis/')
        self.assertEqual((neuve.data['source'], neuve.data['reference']), ('composition', None))

    def test_lot8_apercu_et_generation_meme_onduleur_autour_des_paliers(self):
        """Lot 8 (aperçu ≠ devis, 26/11) — autour des paliers 20 / 25 / 30 kW, triphasé et monophasé,
        dont le cas signalé (34 × 715 W triphasé) : l'onduleur que l'aperçu nomme est la ligne onduleur
        du devis que « Générer » écrit ensuite (mêmes entrées : layout, société, lead ; la génération
        n'ajoute que TVA / remise, que l'écran n'envoie pas)."""
        from apps.stock.models import Produit
        from apps.ventes.models import Devis

        for nom, prix in (('Panneau Jinko 715W', 1400), ('Onduleur réseau Huawei 20kW Triphasé', 30000),
                          ('Onduleur réseau Huawei 25kW Triphasé', 35000),
                          ('Onduleur réseau Huawei 30kW Triphasé', 40000)):
            Produit.objects.create(company=self.company, nom=nom, sku=f'L8-{nom[-14:]}-{self.company.pk}',
                                   prix_vente=Decimal(prix), prix_achat=Decimal('1'), quantite_stock=100)
        for phase, panneaux in (('triphase', 28), ('triphase', 34), ('triphase', 35), ('triphase', 42),
                                ('monophase', 7)):
            with self.subTest(phase=phase, panneaux=panneaux):
                self.lead.raccordement = phase
                self.lead.save(update_fields=['raccordement'])
                calepinage = Calepinage.objects.create(company=self.company, lead_id=self.lead.pk,
                                                       titre=f'L8 {phase} {panneaux}')
                toit = copy.deepcopy(TOIT)
                toit['result'] = {'panels': panneaux, 'kwc': round(panneaux * 0.715, 3),
                                  'annualKwh': 1600 * panneaux, 'savings': 1200 * panneaux}
                enregistrer_layout(calepinage, toit, user=self.user)
                base = url_detail(calepinage.pk)
                apercu = self.api.get(f'{base}apercu-devis/')
                self.assertEqual(apercu.status_code, 200, apercu.data)
                self.assertIsNone(apercu.data['refus'], apercu.data)
                genere = self.api.post(f'{base}generer-devis/', {'creer_autre_devis': True, 'confirmer_taille': True},
                                       format='json')
                self.assertEqual(genere.status_code, 201, genere.data)
                lignes = Devis.objects.get(pk=genere.data['devis']).lignes.all()
                onduleurs = sorted(li.designation for li in lignes if str(li.role_devis or '').startswith('onduleur_'))
                self.assertEqual(sorted(o['onduleur'] for o in apercu.data['options']), onduleurs, apercu.data)

    def test_lot8_apercu_dit_le_brouillon_libre_que_generer_rattacherait(self):
        """Lot 8 — le lead a un brouillon LIBRE né avant ce calepinage : « Générer » ne compose pas, il
        demande (409 ``devis_existant``) ; rattaché, ce brouillon GARDE son onduleur (PV18). L'aperçu le
        dit (``ecarts`` champ ``rattacher_devis``, référence et onduleur du brouillon) au lieu de
        présenter la composition comme LE devis. Mutant « aperçu sans cette branche » ⇒ rouge."""
        from datetime import timedelta

        from apps.ventes.models import Devis

        self.calepinage.refresh_from_db()
        libre = Devis.objects.get(pk=self.calepinage.devis_id)
        ligne = next(li for li in libre.lignes.all() if str(li.role_devis or '').startswith('onduleur_'))
        type(ligne).objects.filter(pk=ligne.pk).update(designation='Onduleur du brouillon libre')
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=None)
        self.calepinage.refresh_from_db()
        Devis.objects.filter(pk=libre.pk).update(date_creation=self.calepinage.created_at - timedelta(days=1))
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 10  # une autre pose : le brouillon n'est pas « rendu »
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        reponse = self.api.get(f'{self.base}apercu-devis/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['source'], 'composition')
        phrase = next((e['message'] for e in reponse.data['ecarts'] if e['champ'] == 'rattacher_devis'), None)
        self.assertIsNotNone(phrase, reponse.data)
        self.assertIn(libre.reference, phrase)
        self.assertIn('« Onduleur du brouillon libre »', phrase)
        question = self.api.post(f'{self.base}generer-devis/', {'confirmer_taille': True}, format='json')
        self.assertEqual((question.status_code, question.data.get('code')), (409, 'devis_existant'), question.data)
        rattache = self.api.post(f'{self.base}generer-devis/', {'rattacher_devis': libre.pk, 'confirmer_taille': True},
                                 format='json')
        self.assertEqual(rattache.status_code, 200, rattache.data)
        onduleurs = [li.designation for li in Devis.objects.get(pk=libre.pk).lignes.all()
                     if str(li.role_devis or '').startswith('onduleur_')]
        self.assertEqual(onduleurs, ['Onduleur du brouillon libre'])
        # Sans brouillon libre (créer un autre devis tranché ailleurs) : aucune phrase de rattachement.
        Devis.objects.filter(pk=libre.pk).update(is_active=False)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=None)
        sans = self.api.get(f'{self.base}apercu-devis/')
        self.assertNotIn('rattacher_devis', [e['champ'] for e in sans.data['ecarts']])

    def test_lot8_b1_lie_non_reutilisable_jamais_la_phrase_du_brouillon_libre(self):
        """Lot 8 (B1) — le lead a un brouillon manuel D1 né avant ce calepinage, la première
        génération a lié D2 (setUp), le toit change : « Générer » répond « déjà rattaché à D2 »
        (409), jamais la question sur D1. L'aperçu dit CE refus, sans phrase sur D1."""
        from datetime import timedelta

        from apps.ventes.models import Devis

        self.calepinage.refresh_from_db()
        d2 = Devis.objects.get(pk=self.calepinage.devis_id)
        d1 = Devis.objects.create(company=self.company, client=d2.client, lead=self.lead, reference='DEV-L8B1-0001')
        Devis.objects.filter(pk=d1.pk).update(date_creation=self.calepinage.created_at - timedelta(days=1))
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 10
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        apercu = self.api.get(f'{self.base}apercu-devis/')
        self.assertEqual(apercu.status_code, 200, apercu.data)
        self.assertNotIn('DEV-L8B1-0001', str(apercu.data))
        self.assertEqual((apercu.data['options'], apercu.data['ecarts']), ([], []))
        genere = self.api.post(f'{self.base}generer-devis/', {'confirmer_taille': True}, format='json')
        self.assertEqual(genere.status_code, 409, genere.data)
        self.assertEqual(apercu.data['refus'], str(genere.data['detail']))
        self.assertIn(d2.reference, apercu.data['refus'])

    def test_lot8_b2_onduleur_du_brouillon_libre_sans_role_fige(self):
        """Lot 8 (B2) — brouillon libre dont la ligne onduleur n'a pas de rôle figé : le rôle est
        résolu (produit, puis mots-clés) et l'onduleur nommé ; sans onduleur établi, la phrase ne
        dit rien de l'onduleur (jamais « aucun »)."""
        from datetime import timedelta

        from apps.ventes.models import Devis

        self.calepinage.refresh_from_db()
        libre = Devis.objects.get(pk=self.calepinage.devis_id)
        ligne = next(li for li in libre.lignes.all() if str(li.role_devis or '').startswith('onduleur_'))
        type(ligne).objects.filter(pk=ligne.pk).update(role_devis=None, produit=None,
                                                       designation='Onduleur réseau Huawei 20 kW')
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=None)
        self.calepinage.refresh_from_db()
        Devis.objects.filter(pk=libre.pk).update(date_creation=self.calepinage.created_at - timedelta(days=1))
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 10
        enregistrer_layout(self.calepinage, modifie, user=self.user)

        def phrase():
            reponse = self.api.get(f'{self.base}apercu-devis/')
            self.assertEqual(reponse.status_code, 200, reponse.data)
            return next(e['message'] for e in reponse.data['ecarts'] if e['champ'] == 'rattacher_devis')
        self.assertIn('(onduleur « Onduleur réseau Huawei 20 kW »)', phrase())
        type(ligne).objects.filter(pk=ligne.pk).delete()
        sans = phrase()
        self.assertIn(libre.reference, sans)
        self.assertNotIn('onduleur', sans)
        self.assertNotIn('aucun', sans)

    def test_lot8_d_acal_106_technicien_ne_lit_aucun_devis_dans_l_apercu(self):
        """Lot 8 (D-ACAL-106 « toujours aucun devis ni aucun prix ») — un Technicien (sa visite, sans
        aucun code ``ventes_*``) lit l'aperçu sans qu'aucun devis y soit NOMMÉ, dans les trois cas :
        brouillon rendu, devis lié non réutilisable, brouillon libre antérieur. Le Directeur reçoit la
        réponse complète, identique à l'appel direct du service. Mutant « vue sans lit_les_devis » ⇒ rouge."""
        from datetime import timedelta

        from django.contrib.auth import get_user_model

        from apps.calepinage.services.devis_apercu import (
            MESSAGE_BROUILLON_LIBRE_CAVIARDE, MESSAGE_DEJA_RATTACHE_CAVIARDE, MESSAGE_DEVIS_EXISTANT_CAVIARDE,
            apercu_materiel_du_devis,
        )
        from apps.roles.models import Role
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
        from apps.ventes.models import Devis
        from apps.visites.models import VisiteTerrain

        role = Role.objects.create(company=self.company, nom='L8 Technicien', permissions=list(TECHNICIEN_PERMISSIONS))
        tech = get_user_model().objects.create_user(username='l8-tech', password='x', company=self.company, role=role)
        VisiteTerrain.objects.create(company=self.company, lead=self.lead, commercial=tech)
        api_tech = self._client(tech)
        self.calepinage.refresh_from_db()
        devis = Devis.objects.get(pk=self.calepinage.devis_id)

        def lire():
            directeur = self.api.get(f'{self.base}apercu-devis/')
            technicien = api_tech.get(f'{self.base}apercu-devis/')
            self.assertEqual((directeur.status_code, technicien.status_code), (200, 200), technicien.data)
            self.calepinage.refresh_from_db()
            self.assertEqual(directeur.data, apercu_materiel_du_devis(self.calepinage))  # lecteur : inchangé
            self.assertEqual(set(technicien.data), set(directeur.data))
            self.assertIsNone(technicien.data['reference'])
            self.assertNotIn(devis.reference, str(technicien.data))
            return directeur.data, technicien.data

        # 1. Brouillon rendu (lié, même empreinte).
        directeur, technicien = lire()
        self.assertEqual(directeur['reference'], devis.reference)
        self.assertEqual((technicien['options'], technicien['refus']), ([], MESSAGE_DEVIS_EXISTANT_CAVIARDE))
        # 2. Lié, non réutilisable (le toit a changé).
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 10
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        directeur, technicien = lire()
        self.assertIn(devis.reference, directeur['refus'])
        self.assertEqual(technicien['refus'], MESSAGE_DEJA_RATTACHE_CAVIARDE)
        # 3. Brouillon libre antérieur (délié, antidaté).
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=None)
        self.calepinage.refresh_from_db()
        Devis.objects.filter(pk=devis.pk).update(date_creation=self.calepinage.created_at - timedelta(days=1))
        directeur, technicien = lire()
        self.assertEqual(technicien['options'], directeur['options'])  # la composition du calepinage reste
        phrase = next(e['message'] for e in technicien['ecarts'] if e['champ'] == 'rattacher_devis')
        self.assertEqual(phrase, MESSAGE_BROUILLON_LIBRE_CAVIARDE)

    def test_e9b_apercu_compose_les_surfaces_cochees_comme_la_generation(self):
        """Lane E9b — ``?surfaces=`` (les cases cochées que « Générer » enverra) passe par LA même
        fonction (``devis._layout_des_surfaces``) : clé inconnue ⇒ le refus nommé de la génération ;
        seul le champ coché ⇒ l'onduleur que la génération écrit pour ce champ."""
        doc = {
            'scenario': 'reseau',
            'zones': [{'id': 'z1', 'label': 'Zone 1', 'roofType': 'flat',
                       'vertices': [[0, 0], [30, 0], [30, 20], [0, 20]],
                       'geometry': {'count': 42, 'kwc': 23.1, 'azimuthDeg': 180.0, 'tiltDeg': 10.0},
                       'result': {'count': 42, 'kwc': 23.1}}],
            'poseSurfaces': [{'id': 's1', 'kind': 'sol', 'label': 'Champ au sol 1', 'moduleWc': 550,
                              'contourM': [[0, 0], [40, 0], [40, 25], [0, 25]], 'areaM2': 1000,
                              'rowAzimuthDeg': 90, 'tiltDeg': 25,
                              'engine': {'modules': 176, 'tables': [], 'rowPitchM': 4.2}}]}
        from apps.ventes.models import Devis

        calepinage = Calepinage.objects.create(company=self.company, lead_id=self.lead.pk, titre='E9b surfaces')
        enregistrer_layout(calepinage, doc, user=self.user)
        base = url_detail(calepinage.pk)
        inconnue = self.api.get(f'{base}apercu-devis/', {'surfaces': 'inconnue'})
        self.assertEqual(inconnue.status_code, 200, inconnue.data)
        self.assertTrue(str(inconnue.data['refus']).startswith('Cochez au moins une surface'), inconnue.data)
        champ = self.api.get(f'{base}apercu-devis/', {'surfaces': 's1'})
        genere = self.api.post(f'{base}generer-devis/', {'surfaces_chiffrees': ['s1'], 'creer_autre_devis': True},
                               format='json')
        self.assertEqual(genere.status_code, 201, genere.data)
        lignes = [li.designation for li in Devis.objects.get(pk=genere.data['devis']).lignes.all()]
        self.assertIn(champ.data['options'][0]['onduleur'], lignes)

    def test_e6e_resynchro_refusee_pour_un_onduleur_non_designe_dit_l_issue(self):
        """Le refus de « Resynchroniser » qui juge l'onduleur du DEVIS alors qu'un autre est
        désigné à l'étape Électrique le dit, nomme les deux et propose le geste qui existe :
        désigner à l'étape Électrique l'onduleur du devis. Rien n'est écrit."""
        from unittest import mock

        from apps.ventes.services import SyncLayoutError

        self._designer('Onduleur hybride Deye 5kW Monophasé')
        refus = SyncLayoutError("7 panneaux « P » sont incompatibles avec « Onduleur réseau Huawei 5kW "
                                "Monophasé » : Isc. — le devis n'a pas été modifié.", revision_possible=False,
                                code='couple_incompatible')
        with mock.patch('apps.ventes.services.resynchroniser_conception', side_effect=refus):
            reponse = self.api.post(f'{self.base}sync-devis/', {}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        # T4-X7-007 — plus de « désignez l'onduleur du devis » (geste qui ne lève pas ce refus) :
        # les gestes qui le lèvent sont nommés.
        self.assertTrue(str(reponse.data['detail']).endswith(
            " L'étape Électrique juge l'onduleur désigné « Onduleur hybride Deye 5kW Monophasé » ; ce devis "
            "porte « Onduleur réseau Huawei 5kW Monophasé », c'est lui que ce refus juge : désigner un "
            "onduleur à l'étape Électrique ne le change pas. Pour lever ce refus, choisissez un autre module "
            "à l'étape Électrique (Matériel électrique), ou remplacez « Onduleur réseau Huawei 5kW "
            "Monophasé » dans le devis, puis resynchronisez."), reponse.data)
        self.assertNotIn('désignez « Onduleur réseau Huawei', reponse.data['detail'])
        self.assertEqual(self.emissions, [])

    def test_t4_x7_007_refus_d_etat_ne_propose_pas_de_changer_de_module(self):
        """T4-X7-007 — un refus qui n'est pas celui du couple (ici un refus d'état) garde
        l'onduleur jugé nommé, sans « choisissez un autre module »."""
        from unittest import mock

        from apps.ventes.services import SyncLayoutError

        self._designer('Onduleur hybride Deye 5kW Monophasé')
        with mock.patch('apps.ventes.services.resynchroniser_conception',
                        side_effect=SyncLayoutError('Devis accepté.', revision_possible=True)):
            reponse = self.api.post(f'{self.base}sync-devis/', {}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('c\'est lui que ce refus juge', reponse.data['detail'])
        self.assertNotIn('autre module', reponse.data['detail'])

    def test_e6e_resynchro_refusee_onduleur_designe_inchangee(self):
        """Le devis porte l'onduleur désigné : le refus reste celui du serveur, mot pour mot."""
        from unittest import mock

        from apps.ventes.services import SyncLayoutError

        self._designer('Onduleur réseau Huawei 5kW Monophasé')
        with mock.patch('apps.ventes.services.resynchroniser_conception',
                        side_effect=SyncLayoutError('Refus du serveur.', revision_possible=False)):
            reponse = self.api.post(f'{self.base}sync-devis/', {}, format='json')
        self.assertEqual((reponse.status_code, str(reponse.data['detail'])), (409, 'Refus du serveur.'))

    # ── D-ACAL-148 (fondateur, 26/11/2026) — le devis chiffre l'onduleur désigné ──
    def _apercu_puis_generation(self):
        from apps.ventes.models import Devis

        apercu = self.api.get(f'{self.base}apercu-devis/')
        self.assertEqual(apercu.status_code, 200, apercu.data)
        genere = self.api.post(f'{self.base}generer-devis/', {'creer_autre_devis': True}, format='json')
        self.assertEqual(genere.status_code, 201, genere.data)
        lignes = Devis.objects.get(pk=genere.data['devis']).lignes.all()
        onduleurs = {(li.variante or None): (li.designation, li.role_devis) for li in lignes
                     if str(li.role_devis or '').startswith('onduleur_')}
        return apercu.data, genere.data, onduleurs

    def test_d_acal_148_onduleur_reseau_designe_et_tarife_est_au_devis(self):
        from apps.stock.models import Produit

        for kw, prix in ((6, 15000), (8, 16000)):  # sans désignation, le catalogue prendrait le 6 kW
            Produit.objects.create(company=self.company, nom=f'Onduleur réseau Growatt {kw}kW Monophasé',
                                   sku=f'A148-G{kw}-{self.company.pk}', prix_vente=Decimal(prix),
                                   prix_achat=Decimal('1'), quantite_stock=5)
        self._nouvelle_pose()
        self._designer('Onduleur réseau Growatt 8kW Monophasé', nombre_onduleurs=1)
        apercu, _genere, onduleurs = self._apercu_puis_generation()
        self.assertEqual([o['onduleur'] for o in apercu['options']], ['Onduleur réseau Growatt 8kW Monophasé'])
        self.assertEqual(_materiel(apercu), [])
        self.assertEqual(onduleurs, {None: ('Onduleur réseau Growatt 8kW Monophasé', 'onduleur_reseau')})

    def test_d_acal_148_sans_prix_le_repli_est_dit_a_l_apercu_et_a_la_generation(self):
        from apps.stock.models import Produit

        Produit.objects.create(company=self.company, nom='Onduleur réseau Growatt 3kW Monophasé',
                               sku=f'A148-G3-{self.company.pk}', prix_vente=Decimal('0'),
                               prix_achat=Decimal('1'), quantite_stock=5)
        self._nouvelle_pose()
        self._designer('Onduleur réseau Growatt 3kW Monophasé', nombre_onduleurs=1)
        apercu, genere, onduleurs = self._apercu_puis_generation()
        self.assertEqual([o['onduleur'] for o in apercu['options']], ['Onduleur réseau Huawei 5kW Monophasé'])
        self.assertEqual([e['champ'] for e in _materiel(apercu)], ['onduleur_produit'])
        self.assertIn('pas de prix de vente', apercu['ecarts'][0]['message'])
        self.assertTrue(any('pas de prix de vente' in m for m in genere['avertissements']), genere)
        self.assertEqual(onduleurs, {None: ('Onduleur réseau Huawei 5kW Monophasé', 'onduleur_reseau')})

    def test_d_acal_148_sans_nombre_ni_schema_le_repli_est_dit(self):
        """Relecture, point 1 — aucun nombre accepté et un schéma sans fiche (aucun nombre établi) :
        le devis garde le choix du catalogue et le dit, jamais ⌈kWc ÷ kW⌉."""
        from apps.stock.models import Produit

        Produit.objects.create(company=self.company, nom='Onduleur réseau Growatt 8kW Monophasé',
                               sku=f'A148-N8-{self.company.pk}', prix_vente=Decimal('16000'),
                               prix_achat=Decimal('1'), quantite_stock=5)
        self._nouvelle_pose()  # sans désignation, le catalogue prend le 8 kW (≥ 80 % de 6,6 kWc)
        self._designer('Onduleur réseau Huawei 5kW Monophasé')
        apercu, genere, onduleurs = self._apercu_puis_generation()
        self.assertIn('ni établi par le schéma', apercu['ecarts'][0]['message'])
        self.assertTrue(any('ni établi par le schéma' in m for m in genere['avertissements']), genere)
        self.assertEqual(onduleurs, {None: ('Onduleur réseau Growatt 8kW Monophasé', 'onduleur_reseau')})

    def test_d_acal_159_hybride_sur_pose_sans_batterie_le_devis_passe_avec_batterie(self):
        """D-ACAL-159 (fondateur, 26/11/2026) — l'hybride désigné ET une batterie (celle que la
        composition pose) ; la phrase est dite à la génération."""
        from apps.ventes.models import Devis

        self._nouvelle_pose()
        self._designer('Onduleur hybride Deye 5kW Monophasé', nombre_onduleurs=1)
        apercu, genere, onduleurs = self._apercu_puis_generation()
        phrase = ('Le devis passe en « avec batterie » : l’onduleur désigné « Onduleur hybride Deye 5kW '
                  'Monophasé » est un hybride.')
        self.assertIn(phrase, genere['avertissements'], genere)
        self.assertEqual(_materiel(apercu), [{'champ': 'onduleur_produit', 'message': phrase}])  # même phrase
        # ``TOIT`` est un toit plat sans tables : la phrase des 20° supposés (D-ACAL-168) y est VRAIE, seule à côté.
        self.assertEqual([e['champ'] for e in apercu['ecarts']], ['onduleur_produit', 'geometry.tiltDeg'])
        self.assertEqual([o['onduleur'] for o in apercu['options']], ['Onduleur hybride Deye 5kW Monophasé'])
        self.assertEqual(onduleurs, {None: ('Onduleur hybride Deye 5kW Monophasé', 'onduleur_hybride')})
        self.assertTrue(Devis.objects.get(pk=genere['devis']).lignes.filter(role_devis='batterie').exists())

    def test_d_acal_148_deux_options_l_hybride_designe_va_a_l_option_avec(self):
        from apps.ventes.models import Devis

        Devis.objects.filter(pk=self.calepinage.devis_id).update(is_active=False)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=None)
        self.calepinage.refresh_from_db()
        enregistrer_layout(self.calepinage, dict(copy.deepcopy(TOIT), scenario='les_deux'), user=self.user)
        self.calepinage.refresh_from_db()
        self._designer('Onduleur hybride Deye 5kW Monophasé', nombre_onduleurs=1)
        apercu, _genere, onduleurs = self._apercu_puis_generation()
        self.assertEqual({o['option']: o['onduleur'] for o in apercu['options']},
                         {'sans': 'Onduleur réseau Huawei 5kW Monophasé',
                          'avec': 'Onduleur hybride Deye 5kW Monophasé'})
        self.assertEqual(_materiel(apercu), [])
        self.assertEqual(onduleurs['avec'], ('Onduleur hybride Deye 5kW Monophasé', 'onduleur_hybride'))
        self.assertEqual(onduleurs['sans'], ('Onduleur réseau Huawei 5kW Monophasé', 'onduleur_reseau'))

    # ── D-ACAL-148 / 159 (relecture, A) — « Resynchroniser » ne défait pas une désignation ──
    def _resynchroniser(self, corps=None):
        from apps.ventes.models import Devis

        reponse = self.api.post(f'{self.base}sync-devis/', corps or {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.calepinage.refresh_from_db()
        lignes = Devis.objects.get(pk=self.calepinage.devis_id).lignes.all()
        onduleurs = sorted((li.designation, int(li.quantite)) for li in lignes
                           if str(li.role_devis or '').startswith('onduleur_') or 'nduleur' in li.designation)
        return reponse.data, onduleurs, [li for li in lignes if li.role_devis == 'batterie']

    def _growatt_8(self):
        from apps.stock.models import Produit

        Produit.objects.create(company=self.company, nom='Onduleur réseau Growatt 8kW Monophasé',
                               sku=f'A148R-G8-{self.company.pk}', prix_vente=Decimal('16000'),
                               prix_achat=Decimal('1'), quantite_stock=5)

    def test_a_la_resynchro_garde_l_onduleur_designe(self):
        self._growatt_8()  # le catalogue prendrait le 8 kW
        self._nouvelle_pose()
        self._designer('Onduleur réseau Huawei 5kW Monophasé', nombre_onduleurs=1)
        self._apercu_puis_generation()
        _data, onduleurs, _batteries = self._resynchroniser()
        self.assertEqual(onduleurs, [('Onduleur réseau Huawei 5kW Monophasé', 1)])

    def test_a_la_resynchro_suit_une_designation_changee_et_le_dit(self):
        self._growatt_8()
        self._nouvelle_pose()
        self._designer('Onduleur réseau Huawei 5kW Monophasé', nombre_onduleurs=1)
        self._apercu_puis_generation()
        self._designer('Onduleur réseau Growatt 8kW Monophasé', nombre_onduleurs=1)
        data, onduleurs, _b = self._resynchroniser()
        self.assertEqual(onduleurs, [('Onduleur réseau Growatt 8kW Monophasé', 1)])
        self.assertIn('La désignation de l’onduleur a changé à l’étape Électrique : « Onduleur réseau Growatt '
                      '8kW Monophasé » remplace « Onduleur réseau Huawei 5kW Monophasé ».', data['avertissements'])

    def test_a_designation_retiree_la_resynchro_reprend_le_catalogue_et_le_dit(self):
        from apps.calepinage.services.electrique import CLE_ENTREE

        self._growatt_8()
        self._nouvelle_pose()
        self._designer('Onduleur réseau Huawei 5kW Monophasé', nombre_onduleurs=1)
        self._apercu_puis_generation()
        self.calepinage.refresh_from_db()
        Calepinage.objects.filter(pk=self.calepinage.pk).update(resultat={
            **(self.calepinage.resultat or {}), CLE_ENTREE: {}})
        data, onduleurs, _b = self._resynchroniser()
        self.assertEqual(onduleurs, [('Onduleur réseau Growatt 8kW Monophasé', 1)])
        self.assertTrue(any('n’est plus désigné à l’étape Électrique' in m for m in data['avertissements']), data)

    def test_a_d_acal_159_la_resynchro_garde_l_hybride_et_la_batterie(self):
        self._nouvelle_pose()
        self._designer('Onduleur hybride Deye 5kW Monophasé', nombre_onduleurs=1)
        self._apercu_puis_generation()
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 11  # le toit bouge : la resynchro écrit vraiment
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        _data, onduleurs, batteries = self._resynchroniser()
        self.assertEqual(onduleurs, [('Onduleur hybride Deye 5kW Monophasé', 1)])
        self.assertTrue(batteries)

    def test_a_brouillon_ne_sans_designation_suit_une_designation_ajoutee(self):
        """Né sous la règle (marqueur ``{}`` posé même sans désignation) : une désignation AJOUTÉE
        ensuite est appliquée à la resynchro et dite."""
        from apps.ventes.models import Devis

        self._growatt_8()
        self._nouvelle_pose()
        self._apercu_puis_generation()  # aucun onduleur désigné : le catalogue (8 kW)
        self.calepinage.refresh_from_db()
        self.assertEqual(Devis.objects.get(pk=self.calepinage.devis_id).roof_layout['_designations'], {})
        self._designer('Onduleur réseau Huawei 5kW Monophasé', nombre_onduleurs=1)
        data, onduleurs, _b = self._resynchroniser()
        self.assertEqual(onduleurs, [('Onduleur réseau Huawei 5kW Monophasé', 1)])
        self.assertIn('L’onduleur suit la désignation de l’étape Électrique : « Onduleur réseau Huawei 5kW '
                      'Monophasé » remplace « Onduleur réseau Growatt 8kW Monophasé ».', data['avertissements'])

    def _sans_marqueur_ou_envoye(self, *, envoye, marqueur=None, apercu=None, corps=None):
        """``marqueur`` (défaut : vrai pour un envoyé, faux pour un brouillon) — le devis est-il né
        sous la règle ? ``apercu`` : une liste où ranger l'aperçu lu AVANT la resynchronisation ;
        ``corps`` : le corps de ``sync-devis`` (``{'apercu_confirme': True}`` = la carte confirmée)."""
        from apps.ventes.models import Devis

        self._growatt_8()
        self._nouvelle_pose()
        self._apercu_puis_generation()
        self.calepinage.refresh_from_db()
        devis = Devis.objects.get(pk=self.calepinage.devis_id)
        if envoye:
            Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        if not (envoye if marqueur is None else marqueur):  # un devis créé AVANT la règle : aucun marqueur
            Devis.objects.filter(pk=devis.pk).update(roof_layout={
                k: v for k, v in devis.roof_layout.items() if k != '_designations'})
        self._designer('Onduleur réseau Huawei 5kW Monophasé', nombre_onduleurs=1)
        if apercu is not None:
            lu = self._apercu_resync()
            self.assertEqual(lu.status_code, 200, lu.data)
            apercu.append(lu.data)
            if corps and corps.get('apercu_confirme'):  # la carte renvoie le jeton de SON aperçu
                corps = dict(corps, jeton_apercu=lu.data['jeton'])
        return self._resynchroniser(corps)

    def test_a_brouillon_cree_avant_la_regle_ne_suit_pas_la_designation_et_le_dit(self):
        data, onduleurs, _b = self._sans_marqueur_ou_envoye(envoye=False)
        self.assertEqual(onduleurs, [('Onduleur réseau Growatt 8kW Monophasé', 1)])
        self.assertTrue(data['inchange'], data)  # aucune écriture de plus : le court-circuit d'hier
        self.assertIn('Le calepinage désigne un onduleur à l’étape Électrique : ce devis, créé avant que le '
                      'devis suive la désignation, ne la suit pas ; un nouveau devis généré depuis le calepinage '
                      'la suivra.', data['avertissements'])

    def test_acal1320_devis_envoye_ne_sous_la_regle_suit_la_designation_annoncee_avant(self):
        """D-ACAL-73 (corriger_dire) — un ENVOYÉ né sous la règle (marqueur) reçoit l'onduleur désigné
        à la resynchronisation confirmée, comme un brouillon ; l'aperçu l'a dit AVANT, montants
        compris, et le devis reçu par le client est corrigé sur place (trace posée). Remplace le
        refus « révisez-le (V2) » posé faute d'aperçu."""
        from apps.ventes.models import Devis

        lus = []
        data, onduleurs, _b = self._sans_marqueur_ou_envoye(envoye=True, apercu=lus,
                                                            corps={'apercu_confirme': True})
        self.assertEqual(onduleurs, [('Onduleur réseau Huawei 5kW Monophasé', 1)])
        self.assertFalse(any('révisez-le (V2)' in m for m in data['avertissements']), data)
        apercu = lus[0]
        self.assertEqual((apercu['statut'], apercu['corrige_apres_envoi']), ('envoye', True))
        onduleur = next(c for c in apercu['changements'] if c['designation_avant'] != c['designation_apres'])
        self.assertEqual((onduleur['designation_avant'], onduleur['designation_apres']),
                         ('Onduleur réseau Growatt 8kW Monophasé', 'Onduleur réseau Huawei 5kW Monophasé'))
        self.assertIsNotNone(onduleur['prix_unitaire_apres'])
        self.assertNotEqual(onduleur['total_ht_avant'], onduleur['total_ht_apres'])
        self.assertEqual(apercu['avertissements'], data['avertissements'])  # mêmes phrases, avant et pendant
        devis = Devis.objects.get(pk=self.calepinage.devis_id)
        self.assertEqual(devis.statut, 'envoye')
        self.assertTrue(devis.activites.filter(field='correction_apres_envoi').exists())

    def test_revue_envoye_sans_la_carte_ne_recoit_pas_la_designation_et_le_dit(self):
        """Revue du 26/11 (D-ACAL-73 « le dire AVANT ») — un envoyé né sous la règle, resynchronisé SANS
        la confirmation de l'aperçu (``sync-devis`` sans ``apercu_confirme``, ou ``sync-layout`` /
        POST layout du devis : ``ecrire_conception_du_devis``) : la désignation n'est pas appliquée,
        une phrase dit d'utiliser « Resynchroniser le devis ». Mutant « drapeau ignoré » ⇒ rouge."""
        from apps.ventes.domain.creation_calepinage import MSG_RESYNC_ENVOYE_SANS_APERCU
        from apps.ventes.domain.resynchronisation import ecrire_conception_du_devis
        from apps.ventes.models import Devis

        phrase = MSG_RESYNC_ENVOYE_SANS_APERCU % 'un onduleur'
        data, onduleurs, _b = self._sans_marqueur_ou_envoye(envoye=True)
        self.assertEqual(onduleurs, [('Onduleur réseau Growatt 8kW Monophasé', 1)])
        self.assertIn(phrase, data['avertissements'])
        # Le jumeau de la route devis (sync-layout / POST layout) ne passe jamais le drapeau.
        self.calepinage.refresh_from_db()
        devis = Devis.objects.get(pk=self.calepinage.devis_id)
        rendu = ecrire_conception_du_devis(devis, copy.deepcopy(self.calepinage.roof_layout), self.user)
        devis.refresh_from_db()
        self.assertEqual(sorted(li.designation for li in devis.lignes.all() if 'nduleur' in li.designation),
                         ['Onduleur réseau Growatt 8kW Monophasé'])
        self.assertIn(phrase, rendu['avertissements'])
        # Avec la carte confirmée (son jeton) : appliquée, et la correction tracée.
        jeton = self._apercu_resync().data['jeton']
        data, onduleurs, _b = self._resynchroniser({'apercu_confirme': True, 'jeton_apercu': jeton})
        self.assertEqual(onduleurs, [('Onduleur réseau Huawei 5kW Monophasé', 1)])
        self.assertTrue(Devis.objects.get(pk=devis.pk).activites.filter(field='correction_apres_envoi').exists())

    def test_revue_confirmation_liee_a_l_apercu_409_si_les_entrees_ont_change(self):
        """Revue du 26/11 — la confirmation renvoie le jeton de l'aperçu : sans jeton ⇒ 400 nommant
        ``jeton_apercu`` ; la conception change entre l'aperçu et la confirmation (autre onglet,
        re-simulation, retouche) ⇒ 409 ``apercu_perime`` et RIEN n'est écrit ; un nouvel aperçu rend un
        nouveau jeton, qui passe. Mutant « jeton non vérifié » ⇒ rouge."""
        from apps.calepinage.services.devis import CODE_APERCU_PERIME
        from apps.ventes.models import Devis

        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 14
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        Devis.objects.filter(pk=self.calepinage.devis_id).update(statut='envoye')
        premier = self._apercu_resync().data
        sans_jeton = self.api.post(f'{self.base}sync-devis/', {'apercu_confirme': True}, format='json')
        self.assertEqual(sans_jeton.status_code, 400, sans_jeton.data)
        self.assertIn('jeton_apercu', sans_jeton.data)
        autre = copy.deepcopy(modifie)
        autre['result']['panels'] = 13  # la conception bouge APRÈS l'aperçu
        self.calepinage.refresh_from_db()
        enregistrer_layout(self.calepinage, autre, user=self.user)
        avant = self._etat_ecrit()
        perime = self.api.post(f'{self.base}sync-devis/', {'apercu_confirme': True, 'jeton_apercu': premier['jeton']},
                               format='json')
        self.assertEqual(perime.status_code, 409, perime.data)
        self.assertEqual(perime.data['code'], CODE_APERCU_PERIME)
        self.assertEqual(self._etat_ecrit()['lignes'], avant['lignes'])
        self.assertEqual(self._etat_ecrit()['journal'], avant['journal'])
        second = self._apercu_resync().data
        self.assertNotEqual(second['jeton'], premier['jeton'])
        ok = self.api.post(f'{self.base}sync-devis/', {'apercu_confirme': True, 'jeton_apercu': second['jeton']},
                           format='json')
        self.assertEqual(ok.status_code, 200, ok.data)

    def test_acal1320_devis_envoye_cree_avant_la_regle_ne_suit_pas_et_le_dit(self):
        data, onduleurs, _b = self._sans_marqueur_ou_envoye(envoye=True, marqueur=False)
        self.assertEqual(onduleurs, [('Onduleur réseau Growatt 8kW Monophasé', 1)])
        self.assertIn('Le calepinage désigne un onduleur à l’étape Électrique : ce devis, créé avant que le '
                      'devis suive la désignation, ne la suit pas ; un nouveau devis généré depuis le calepinage '
                      'la suivra.', data['avertissements'])

    def test_a_onduleur_change_a_la_main_garde_et_dit_une_fois(self):
        from apps.stock.models import Produit
        from apps.ventes.models import Devis

        self._growatt_8()
        self._nouvelle_pose()
        self._designer('Onduleur réseau Huawei 5kW Monophasé', nombre_onduleurs=1)
        self._apercu_puis_generation()
        self.calepinage.refresh_from_db()
        devis = Devis.objects.get(pk=self.calepinage.devis_id)
        growatt = Produit.objects.get(company=self.company, nom='Onduleur réseau Growatt 8kW Monophasé')
        ligne = next(li for li in devis.lignes.all() if str(li.role_devis or '').startswith('onduleur_'))
        type(ligne).objects.filter(pk=ligne.pk).update(produit=growatt, designation=growatt.nom)
        for _tour, attendue in ((1, True), (2, False)):
            data, onduleurs, _b = self._resynchroniser()
            self.assertEqual(onduleurs, [('Onduleur réseau Growatt 8kW Monophasé', 1)])
            self.assertEqual(any('a été posé à la main' in m for m in data['avertissements']), attendue, data)

    def test_round_4_la_phrase_des_20_degres_est_la_meme_a_l_apercu_et_a_la_generation(self):
        from apps.ventes.domain.geometrie import SUPPOSITION_INCLINAISON_TOIT_PLAT

        self._nouvelle_pose()
        apercu, genere, _o = self._apercu_puis_generation()
        phrase = SUPPOSITION_INCLINAISON_TOIT_PLAT['message']
        self.assertIn({'champ': 'geometry.tiltDeg', 'message': phrase}, apercu['ecarts'])
        self.assertIn(phrase, genere['avertissements'])

    # ── Relecture round 4, point 6 — chaque phrase vraie dans son état ──
    def test_6_d_onduleur_plus_chiffrable_la_phrase_dit_la_raison_et_la_reprise(self):
        from apps.stock.models import Produit

        self._growatt_8()
        self._nouvelle_pose()
        self._designer('Onduleur réseau Huawei 5kW Monophasé', nombre_onduleurs=1)
        self._apercu_puis_generation()
        Produit.objects.filter(company=self.company, nom='Onduleur réseau Huawei 5kW Monophasé').update(prix_vente=0)
        data, onduleurs, _b = self._resynchroniser()
        self.assertEqual(onduleurs, [('Onduleur réseau Growatt 8kW Monophasé', 1)])
        self.assertTrue(any('n’est plus chiffrable : il n’a pas de prix de vente au catalogue ; la resynchronisation '
                            'reprend le choix du catalogue' in m for m in data['avertissements']), data)
        self.assertFalse(any('conception du lead' in m or 'n’est plus désigné' in m for m in data['avertissements']))

    def test_6_e_la_bascule_n_est_dite_qu_au_moment_ou_elle_a_lieu(self):
        self._nouvelle_pose()
        self._designer('Onduleur hybride Deye 5kW Monophasé', nombre_onduleurs=1)
        _apercu, genere, _o = self._apercu_puis_generation()
        self.assertTrue(any('Le devis passe en « avec batterie »' in m for m in genere['avertissements']))
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 11
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        data, _o, batteries = self._resynchroniser()
        self.assertTrue(batteries)
        self.assertFalse(any('Le devis passe en « avec batterie »' in m for m in data['avertissements']), data)

    # ── Lot 8, relecture finale — un devis né « avec batterie » par l'hybride désigné ne la perd pas ──
    HYBRIDE = 'Onduleur hybride Deye 5kW Monophasé'

    def _ne_d_acal_159(self):
        """« Générer » sur une pose « sans » avec l'hybride désigné : le devis né « avec batterie »,
        et son état (onduleurs, batteries, panneaux) relu de la base."""
        from apps.ventes.models import Devis

        self._nouvelle_pose()
        self._designer(self.HYBRIDE, nombre_onduleurs=1)
        _apercu, genere, _o = self._apercu_puis_generation()
        devis = Devis.objects.get(pk=genere['devis'])
        etat = self._etat(devis)
        self.assertEqual((etat['onduleurs'], etat['panneaux']), ([self.HYBRIDE], 10))
        self.assertTrue(etat['batteries'])
        return devis, etat

    def _etat(self, devis):
        from apps.ventes.services import _is_panel

        lignes = list(type(devis).objects.get(pk=devis.pk).lignes.all())
        return {'onduleurs': sorted(li.designation for li in lignes if 'nduleur' in li.designation),
                'batteries': sorted((li.designation, int(li.quantite)) for li in lignes if li.role_devis == 'batterie'),
                'panneaux': sum(int(li.quantite) for li in lignes if _is_panel(li.designation or ''))}

    def _toit_de(self, panneaux):
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = panneaux
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        self.calepinage.refresh_from_db()

    def test_relecture_finale_devis_envoye_ne_d_acal_159_garde_hybride_et_batterie(self):
        """Pose « sans », hybride désigné → devis « avec batterie » → ENVOYÉ → le toit gagne un panneau →
        « Resynchroniser le devis » : le panneau suit le toit, l'hybride et la batterie (même quantité)
        restent, et la phrase dit ce qui s'est passé. Mutant « sans option_batterie_gardee » ⇒ la batterie
        est retirée et l'hybride permuté en réseau ⇒ rouge."""
        from apps.ventes.domain.creation_calepinage import MSG_RESYNC_ENVOYE_SANS_APERCU, MSG_RESYNC_OPTION_GARDEE
        from apps.ventes.models import Devis

        devis, avant = self._ne_d_acal_159()
        Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        self._toit_de(11)
        data, _o, _b = self._resynchroniser()
        apres = self._etat(devis)
        self.assertEqual(apres, dict(avant, panneaux=11))
        self.assertEqual((data['scenario'], data['batterie']), ('avec_batterie', True), data)
        self.assertIn(MSG_RESYNC_OPTION_GARDEE % self.HYBRIDE, data['avertissements'])
        self.assertIn(MSG_RESYNC_ENVOYE_SANS_APERCU % 'un onduleur', data['avertissements'])  # sans la carte

    def test_revue_envoye_ne_d_acal_159_carte_confirmee_garde_l_option_et_l_apercu_le_montre(self):
        """Cas 4 de la règle combinée — le même devis envoyé né « avec batterie » par l'hybride désigné ;
        le vendeur a seulement bougé un panneau (désignation INCHANGÉE) et confirme la carte : l'aperçu
        ne montre AUCUN changement d'onduleur ni de batterie (seule la ligne de panneaux), et la
        resynchronisation confirmée (désignations appliquées, D-ACAL-159 : l'hybride garde « avec ») écrit
        exactement cela. Mutant « l'envoyé confirmé bascule en sans » ⇒ batterie retirée ⇒ rouge."""
        from apps.ventes.models import Devis

        devis, avant = self._ne_d_acal_159()
        Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        self._toit_de(11)
        lu = self._apercu_resync()
        self.assertEqual(lu.status_code, 200, lu.data)
        apercu = lu.data
        self.assertEqual(apercu['retraits'], [], apercu)
        self.assertFalse([c for c in apercu['changements'] if c['designation_avant'] != c['designation_apres']], apercu)
        self.assertFalse([c for c in apercu['changements'] if 'nduleur' in c['designation_apres']
                          or 'atterie' in c['designation_apres']], apercu)
        data, _o, _b = self._resynchroniser({'apercu_confirme': True, 'jeton_apercu': apercu['jeton']})
        self.assertEqual(self._etat(devis), dict(avant, panneaux=11))
        self.assertEqual((data['scenario'], data['batterie']), ('avec_batterie', True), data)
        self.assertEqual(data['avertissements'], apercu['avertissements'])  # la carte a dit ce qui est écrit

    def test_relecture_finale_brouillon_libre_rattache_garde_hybride_et_batterie(self):
        """Le brouillon né « avec batterie » par l'hybride désigné, devenu LIBRE (plus lié, né avant le
        calepinage), rattaché à « Générer » (``_rattacher_au_brouillon``, sans désignations) : il garde
        l'hybride et la batterie, ses panneaux suivent le toit."""
        from datetime import timedelta

        from apps.ventes.domain.creation_calepinage import MSG_RESYNC_OPTION_GARDEE
        from apps.ventes.models import Devis

        devis, avant = self._ne_d_acal_159()
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=None)
        self.calepinage.refresh_from_db()
        Devis.objects.filter(pk=devis.pk).update(date_creation=self.calepinage.created_at - timedelta(days=1))
        self._toit_de(11)
        rattache = self.api.post(f'{self.base}generer-devis/', {'rattacher_devis': devis.pk, 'confirmer_taille': True},
                                 format='json')
        self.assertEqual(rattache.status_code, 200, rattache.data)
        self.assertEqual(self._etat(devis), dict(avant, panneaux=11))
        self.assertIn(MSG_RESYNC_OPTION_GARDEE % self.HYBRIDE, rattache.data['avertissements'])

    def test_relecture_finale_devis_envoye_sans_marqueur_inchange(self):
        """Le même devis SANS le marqueur (créé avant la règle) : la resynchro d'hier, à l'identique —
        la pose « sans » retire la batterie au prix catalogue, aucune phrase d'option gardée."""
        from apps.ventes.domain.creation_calepinage import CLE_DESIGNATIONS, MSG_RESYNC_OPTION_GARDEE
        from apps.ventes.models import Devis

        devis, _avant = self._ne_d_acal_159()
        Devis.objects.filter(pk=devis.pk).update(statut='envoye', roof_layout={
            k: v for k, v in devis.roof_layout.items() if k != CLE_DESIGNATIONS})
        self._toit_de(11)
        data, _o, batteries = self._resynchroniser()
        self.assertEqual(batteries, [])
        self.assertFalse(any(m == MSG_RESYNC_OPTION_GARDEE % self.HYBRIDE for m in data['avertissements']), data)

    def test_relecture_finale_miroir_reseau_designe_sur_pose_avec_rien_ne_bascule(self):
        """Miroir — un onduleur RÉSEAU désigné sur une pose « avec batterie » n'est pas chiffré (repli) :
        le devis naît hybride + batterie ; envoyé puis resynchronisé, il ne perd rien et n'ajoute aucun
        onduleur réseau ni seconde batterie."""
        from apps.ventes.models import Devis

        Devis.objects.filter(pk=self.calepinage.devis_id).update(is_active=False)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=None)
        self.calepinage.refresh_from_db()

        def pose_avec(panneaux):
            avec = dict(copy.deepcopy(TOIT), scenario='avec_batterie')
            avec['result']['panels'] = panneaux
            self.calepinage.refresh_from_db()
            enregistrer_layout(self.calepinage, avec, user=self.user)
            self.calepinage.refresh_from_db()

        pose_avec(10)
        self._designer('Onduleur réseau Huawei 5kW Monophasé', nombre_onduleurs=1)
        _apercu, genere, _o = self._apercu_puis_generation()
        devis = Devis.objects.get(pk=genere['devis'])
        avant = self._etat(devis)
        self.assertTrue(avant['batteries'])
        self.assertEqual(len(avant['onduleurs']), 1, avant)
        self.assertIn('hybride', avant['onduleurs'][0].lower())
        Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        pose_avec(11)
        self._resynchroniser()
        self.assertEqual(self._etat(devis), dict(avant, panneaux=11))

    def test_6_b_batterie_sur_devis_redevenu_sans_une_seule_phrase_vraie(self):
        from apps.stock.models import Produit

        batterie = Produit.objects.get(company=self.company, nom='Batterie Dyness 5 kWh')
        self._nouvelle_pose()
        self._designer('Onduleur hybride Deye 5kW Monophasé', nombre_onduleurs=1,
                       batterie={'produit': batterie.pk, 'packs': 1})
        self._apercu_puis_generation()
        self._designer('Onduleur réseau Huawei 5kW Monophasé', nombre_onduleurs=1,
                       batterie={'produit': batterie.pk, 'packs': 1})  # plus d'hybride : la pose « sans » reste
        data, _o, _b = self._resynchroniser()
        self.assertTrue(any('n’est pas mise au devis' in m for m in data['avertissements']), data)
        self.assertFalse(any('reprend le choix automatique' in m for m in data['avertissements']), data)

    # ── D-ACAL-164 (B) — la batterie désignée à l'étape Électrique ──
    def test_b_batterie_designee_generation_apercu_et_resynchro(self):
        from apps.stock.models import Produit

        Produit.objects.create(company=self.company, nom='Batterie Lithium 7 kWh', sku=f'A164C-{self.company.pk}',
                               prix_vente=Decimal('21000'), prix_achat=Decimal('1'), quantite_stock=5)
        batterie = Produit.objects.get(company=self.company, nom='Batterie Lithium 7 kWh')
        self._nouvelle_pose()
        self._designer('Onduleur hybride Deye 5kW Monophasé', nombre_onduleurs=1,
                       batterie={'produit': batterie.pk, 'packs': 2})
        apercu, genere, onduleurs = self._apercu_puis_generation()
        self.assertEqual(onduleurs, {None: ('Onduleur hybride Deye 5kW Monophasé', 'onduleur_hybride')})
        # Chiffrée ; point 4 — seule phrase : les 2 packs désignés face à la règle automatique (1), la même
        # à l'aperçu et à la génération.
        phrase = next(e['message'] for e in apercu['ecarts'] if e['champ'] == 'batterie.produit')
        self.assertIn('est vendue à 2 pack(s)', phrase)
        self.assertIn(phrase, genere['avertissements'])
        _data, _ond, batteries = self._resynchroniser()
        self.assertEqual([(b.designation, int(b.quantite)) for b in batteries], [('Batterie Lithium 7 kWh', 2)])
        self._designer('Onduleur hybride Deye 5kW Monophasé', nombre_onduleurs=1,
                       batterie={'produit': batterie.pk, 'packs': 3})
        data, _ond, batteries = self._resynchroniser()
        self.assertEqual([(b.designation, int(b.quantite)) for b in batteries], [('Batterie Lithium 7 kWh', 3)])
        self.assertTrue(any('La batterie suit la désignation' in m for m in data['avertissements']), data)

    def test_b_batterie_designee_sans_hybride_sur_pose_sans_dite_a_l_apercu_et_a_la_generation(self):
        from apps.stock.models import Produit

        batterie = Produit.objects.get(company=self.company, nom='Batterie Dyness 5 kWh')
        self._nouvelle_pose()
        self._designer('Onduleur réseau Huawei 5kW Monophasé', nombre_onduleurs=1,
                       batterie={'produit': batterie.pk, 'packs': 1})
        apercu, genere, _onduleurs = self._apercu_puis_generation()
        phrase = next(e['message'] for e in apercu['ecarts'] if e['champ'] == 'batterie.produit')
        self.assertIn('n’est pas mise au devis', phrase)
        self.assertIn(phrase, genere['avertissements'])  # la même phrase


class ApercuBrouillonLibreSansBaseTest(SimpleTestCase):
    """Lot 8 (B2) — sans base : le rôle d'une ligne de brouillon et la phrase R2-22."""

    def test_d_acal_148_point_4_chaque_issue_dit_sa_raison(self):
        """Relecture, point 4 — jamais « la désignation n'y entre pas » pour l'onduleur : la phrase de
        la décision (la même que la génération, produite par la VRAIE fonction de ventes), rien
        quand il est posé, et une raison vraie quand l'imposé n'est pas posé."""
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services import devis_apercu as service
        from apps.ventes.domain.creation_calepinage import decision_onduleur_designe, repli_onduleur_designe

        nom = 'Onduleur hybride Deye 5kW'
        bascule = decision_onduleur_designe(produit_id=9, nom=nom, etat='tarife', famille='onduleur_hybride',
                                            famille_au_nom='onduleur_hybride', scenario='sans',
                                            hors_reseau=False, nombre=1)
        repli = repli_onduleur_designe(nom, 'sans_prix')
        impose = dict(bascule, message=None)
        porte = [{'option': None, 'onduleur': nom, 'onduleur_produit': 9, 'module': None, 'module_produit': None}]
        autre = [dict(porte[0], onduleur='Onduleur réseau Huawei 5kW', onduleur_produit=3)]
        calepinage = SimpleNamespace(company=None)
        with (mock.patch('apps.calepinage.services.electrique.entree_stockee', return_value={'onduleur_produit': 9}),
              mock.patch('apps.calepinage.services.devis_retenu.conception_du_calepinage', return_value={}),
              mock.patch('apps.stock.selectors.get_produit_scoped', return_value=SimpleNamespace(nom=nom))):
            self.assertEqual(service._ecarts(calepinage, porte, bascule),
                             [{'champ': 'onduleur_produit', 'message': bascule['message']}])
            self.assertEqual(service._ecarts(calepinage, autre, repli),
                             [{'champ': 'onduleur_produit', 'message': repli['message']}])
            self.assertEqual(service._ecarts(calepinage, porte, impose), [])
            non_pose = service._ecarts(calepinage, autre, impose)
        self.assertIn(service.RAISON_IMPOSE_NON_POSE, non_pose[0]['message'])
        # Round 4, point 6 a — le brouillon rendu : la raison vraie selon qu'il est né sous la règle.
        with (mock.patch('apps.calepinage.services.electrique.entree_stockee', return_value={'onduleur_produit': 9}),
              mock.patch('apps.calepinage.services.devis_retenu.conception_du_calepinage', return_value={}),
              mock.patch('apps.stock.selectors.get_produit_scoped', return_value=SimpleNamespace(nom=nom))):
            for sous, attendue in ((True, service.RAISON_BROUILLON_SOUS_LA_REGLE),
                                   (False, service.RAISON_BROUILLON_AVANT_LA_REGLE)):
                message = service._ecarts(calepinage, autre, None, brouillon=True, sous_la_regle=sous)[0]['message']
                self.assertIn(attendue, message)
                self.assertNotIn('ne vaut que pour un devis neuf', message)
        self.assertNotIn(service.RAISON_PAR_DEFAUT, non_pose[0]['message'])

    def test_role_fige_puis_mots_cles_et_aucun_onduleur(self):
        from types import SimpleNamespace

        from apps.calepinage.services.devis_apercu import _role_de_ligne

        def ligne(role, designation, produit=None):
            return SimpleNamespace(role_devis=role, designation=designation, produit=produit)
        self.assertEqual(_role_de_ligne(ligne('onduleur_hybride', 'Désignation libre')), 'onduleur_hybride')
        produit = SimpleNamespace(role_devis='onduleur_reseau')
        self.assertEqual(_role_de_ligne(ligne(None, 'Désignation libre', produit)), 'onduleur_reseau')
        self.assertEqual(_role_de_ligne(ligne(None, 'Onduleur réseau Huawei 20 kW')), 'onduleur_reseau')
        self.assertEqual(_role_de_ligne(ligne('', 'Onduleur hybride Deye 5kW Monophasé')), 'onduleur_hybride')
        self.assertFalse(str(_role_de_ligne(ligne(None, 'Pompe immergée 4 pouces')) or '').startswith('onduleur_'))

    def test_phrase_ne_dit_jamais_aucun_onduleur(self):
        from apps.calepinage.services.devis_apercu import _phrase_brouillon_libre

        avec = _phrase_brouillon_libre('DEV-1', ['Onduleur réseau Huawei 20 kW', None])
        self.assertIn('(onduleur « Onduleur réseau Huawei 20 kW »)', avec)
        sans = _phrase_brouillon_libre('DEV-1', [None])
        self.assertIn('DEV-1', sans)
        self.assertNotIn('onduleur', sans)
        self.assertNotIn('aucun', sans)

    def test_d_acal_106_caviardage_trois_cas_avec_et_sans_droit(self):
        """Lot 8 (D-ACAL-106) — brouillon rendu, devis lié du refus, brouillon libre : avec le droit de
        lire les devis la réponse est l'OBJET même du calcul complet ; sans, aucune référence, aucun
        statut, aucun onduleur lu sur un devis — la composition et les désignations du calepinage restent."""
        from unittest import mock

        from apps.calepinage.services import devis_apercu as service
        from apps.calepinage.services.devis import ISSUE_BROUILLON_LIBRE, ISSUE_DEJA_RATTACHE, ISSUE_RENDU

        option = {'option': None, 'libelle': 'Devis', 'module': 'Module 715 Wc', 'onduleur': 'Onduleur A'}
        designe = {'champ': 'onduleur_produit', 'message': 'L’onduleur désigné (« Onduleur A ») : raison.'}
        libre = {'champ': 'rattacher_devis', 'message': service._phrase_brouillon_libre('DEV-1', ['Onduleur du devis'])}
        cas = {
            ISSUE_RENDU: {'options': [dict(option, onduleur='Onduleur du devis')], 'ecarts': [designe],
                          'refus': None, 'source': 'brouillon_existant', 'reference': 'DEV-1'},
            ISSUE_DEJA_RATTACHE: {'options': [], 'ecarts': [], 'source': None, 'reference': None,
                                  'refus': 'Ce calepinage est déjà rattaché au devis DEV-1 (Envoyé) : utilisez …'},
            ISSUE_BROUILLON_LIBRE: {'options': [option], 'ecarts': [designe, libre], 'refus': None,
                                    'source': 'composition', 'reference': None},
        }
        for issue, complet in cas.items():
            with self.subTest(issue=issue), \
                    mock.patch.object(service, '_apercu_complet', return_value=(complet, issue)):
                self.assertIs(service.apercu_materiel_du_devis(object()), complet)
                cache = service.apercu_materiel_du_devis(object(), lit_les_devis=False)
                self.assertEqual(set(cache), set(complet))
                self.assertIsNone(cache['reference'])
                for nomme in ('DEV-1', 'Onduleur du devis', 'Envoyé'):
                    self.assertNotIn(nomme, str(cache))
        cache = service._caviarder(cas[ISSUE_BROUILLON_LIBRE], ISSUE_BROUILLON_LIBRE)
        self.assertEqual(cache['options'], [option])
        self.assertIn(designe, cache['ecarts'])

    def test_d_acal_106_lit_les_devis_suit_la_garde_des_devis(self):
        """``ventes.selectors_assistant.lit_les_devis`` = ``LectureVentes`` de ``DevisViewSet`` : le
        Technicien (aucun code ``ventes_*``) ne lit pas, le Commercial et le Directeur lisent."""
        from types import SimpleNamespace

        from apps.roles.permissions_registre import (
            COMMERCIAL_PERMISSIONS, DIRECTEUR_PERMISSIONS, TECHNICIEN_PERMISSIONS,
        )
        from apps.ventes.selectors_assistant import lit_les_devis

        def compte(permissions):
            return SimpleNamespace(is_authenticated=True, is_superuser=False, is_admin_role=False,
                                   portee='interne', role_id=1, role=SimpleNamespace(permissions=list(permissions)))
        self.assertFalse(lit_les_devis(compte(TECHNICIEN_PERMISSIONS)))
        self.assertTrue(lit_les_devis(compte(COMMERCIAL_PERMISSIONS)))
        self.assertTrue(lit_les_devis(compte(DIRECTEUR_PERMISSIONS)))
        self.assertFalse(lit_les_devis(None))


class ApercuResyncSansBaseTest(SimpleTestCase):
    """ACAL1320 — sans base : le caviardage D-ACAL-106 de l'aperçu de resynchronisation."""

    def test_caviardage_retire_reference_montants_et_totaux_garde_la_pose(self):
        import json
        import pathlib

        from apps.calepinage.services.devis_resync_apercu import _caviarder

        contrat = json.loads((pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
                              / 'calepinage_apercu_resync.json').read_text(encoding='utf-8'))
        complet = contrat['exemple']
        cache = _caviarder(complet)
        self.assertEqual(set(cache), set(complet))
        self.assertEqual((cache['reference'], cache['totaux']), (None, None))
        self.assertEqual(cache['statut'], complet['statut'])  # le vendeur doit savoir qu'il corrige un envoyé
        for ligne, origine in zip(cache['changements'], complet['changements']):
            self.assertEqual(set(ligne), set(origine))
            self.assertEqual((ligne['designation_apres'], ligne['quantite_apres']),
                             (origine['designation_apres'], origine['quantite_apres']))
            self.assertEqual({ligne[c] for c in ligne if c.startswith(('prix_', 'total_'))}, {None})
        # La forme caviardée est celle que le contrat publie pour ce cas.
        attendu = contrat['exemple_sans_lecture_devis']
        self.assertEqual(set(cache), set(attendu))
        self.assertEqual(set(cache['changements'][0]), set(attendu['changements'][0]))
        self.assertIsNot(cache, complet)
        self.assertEqual(complet['reference'], 'DEV-202611-0001')  # l'entrée n'est pas modifiée
        # Revue du 26/11 (D-ACAL-165) — l'avertissement au montant de vente (vraie fonction de ventes).
        from apps.ventes.domain.lignes import avertissement_forfait_verrouille
        chiffre = dict(complet, avertissements=[avertissement_forfait_verrouille('Pose', 14, '4 200,00')])
        self.assertNotIn('MAD', ' '.join(_caviarder(chiffre)['avertissements']))
