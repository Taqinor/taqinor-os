"""CAL231 — le contexte de conception NEUTRE, conforme à son contrat.

Ce qui est prouvé ici :

* les sept clés de ``contract_samples/calepinage_design_context.json`` sont
  TOUJOURS présentes, dans les DEUX états du serveur (avec devis / sans rien) ;
* un calepinage SANS devis ni facture rend ``cible: null`` — jamais une
  puissance inventée — et le dit dans ``avertissements`` ;
* la cible d'un calepinage AVEC devis est celle de l'atelier devis (même
  sélecteur ``apps.ventes.selectors.contexte_conception_devis``), marquée
  ``source: "devis"`` ;
* ``geometrie.source`` vaut ``calepinage`` / ``lead`` / ``none`` selon ce qui
  a réellement été posé, et rien n'est deviné quand tout manque ;
* la raison de lecture seule du serveur VENTES est reprise MOT POUR MOT ;
* un calepinage d'une AUTRE société est introuvable (404).

Run :
    python manage.py test apps.calepinage.tests.test_design_context -v2
"""
import json
import unittest
import pathlib
from unittest import mock

from apps.calepinage.models import Calepinage
from apps.calepinage.tests._m0_en_attente import affirmer_non_servies, sans
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_design_context.json').read_text(encoding='utf-8'))

#: ACAL5 (forme_serveur ``partielle``) a posé ces clés avant leurs moitiés
#: back : chaque tâche nommée sert sa clé et retire son entrée ; la table
#: vide, ``forme_serveur`` redevient ``complete``.
# ACAL178 (calepinage.lead_supprime) est livrée : sa clé est servie.
# ACAL250 (geometrie.contour_utilisable / source_repere) est livrée.
EN_ATTENTE = {}
#: H3 — la taille tirée des factures, sortie du design-context (lue à part : ``GET cible-factures/``).
CONTRAT_CIBLE = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_cible_factures.json').read_text(encoding='utf-8'))
EXEMPLE_SERVI = sans(CONTRAT['exemple'], EN_ATTENTE)

LAYOUT = {'schema_version': 2, 'result': {'panels': 12, 'kwc': 8.64},
          'pin': {'lat': 33.5731, 'lng': -7.5898},
          'outline': [[33.5731, -7.5898], [33.5732, -7.5898]]}


#: Un contour qui ENTOURE l'épingle du lead (33.5731, -7.5898).
CONTOUR_AUTOUR_DU_REPERE = [[33.5730, -7.5899], [33.5732, -7.5899],
                            [33.5732, -7.5897], [33.5730, -7.5897]]


def url_contexte(pk):
    return f'{url_detail(pk)}design-context/'


class ContexteConceptionTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.client_lie = Client.objects.create(company=self.company,
                                                nom='Bâtiment Atlas 231')
        self.lead_lie = Lead.objects.create(
            company=self.company, nom='Toiture Anfa 231', ville='Casablanca',
            roof_point={'lat': 33.5731, 'lng': -7.5898})
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference='DEV-202609-2311')
        self.avec_devis = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, devis=self.devis,
            titre='Villa Anfa', roof_layout=LAYOUT, layout_hash='a' * 64)
        self.nu = Calepinage.objects.create(
            company=self.company, client=self.client_lie,
            titre='Calepinage sans titre')
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=5, titre='Chez la voisine')

    def _contexte(self, calepinage, api=None):
        reponse = (api or self.api).get(url_contexte(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_sept_cles_toujours_presentes(self):
        attendues = set(EXEMPLE_SERVI)
        for calepinage in (self.avec_devis, self.nu):
            contexte = self._contexte(calepinage)
            affirmer_non_servies(self, contexte, EN_ATTENTE)
            self.assertEqual(set(contexte), attendues)

    def test_sous_blocs_conformes(self):
        contexte = self._contexte(self.avec_devis)
        affirmer_non_servies(self, contexte, EN_ATTENTE)
        for bloc in ('calepinage', 'geometrie', 'carte'):
            self.assertEqual(set(contexte[bloc]),
                             set(EXEMPLE_SERVI[bloc]), bloc)

    def test_cible_factures_lue_a_part_bornee_societe(self):
        # H3 — ``GET cible-factures/`` : la forme du contrat, ``null`` sans facture, 404 hors société ;
        # le design-context ne la porte plus (elle coûtait ~1,9 s à chaque ouverture).
        url = f'{url_detail(self.nu.pk)}cible-factures/'
        reponse = self.api.get(url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data, CONTRAT_CIBLE['exemple_vide'])
        self.assertEqual(self.api.get(f'{url_detail(self.etranger.pk)}cible-factures/').status_code, 404)
        self.assertNotIn('cible_factures', self._contexte(self.nu))

    def test_acal1500_lead_commercial_cible_de_sa_conception_calculee(self):
        """ACAL1500 réaligné par la relecture E5 B1 — un lead commercial AVEC
        facture et sans conception rangée : la première lecture met UN calcul en
        file et sert EXACTEMENT ``exemple_en_cours`` du contrat (jamais une
        impasse, jamais 0 panneau) ; une seconde lecture n'en remet pas ; le
        calcul fait par le VRAI moteur (la tâche que ferait le worker), la cible
        est la taille de la conception rangée ; un calepinage sans lead sert
        ``exemple_vide``. Mutants : porte sans file ⇒ refus « absente » ; cible
        hors conception ⇒ autre taille."""
        from django.core.cache import cache

        from apps.ventes import tarif_ci, tasks
        from apps.ventes.domain import etude_ci
        from apps.ventes.models import ConceptionLead
        from apps.ventes.tests import test_ciq120_devis_auto_ci as ci_fab
        from authentication.models import Company

        cache.clear()
        self.addCleanup(cache.clear)
        fab = type('CatalogueCI', (), {})
        with mock.patch.object(Company.objects, 'get_or_create', return_value=(self.company, False)):
            ci_fab._Base.setUpTestData.__func__(fab)  # le catalogue C&I des tests du moteur, sur CETTE société
        lead = Lead.objects.create(company=self.company, nom='Boulangerie 1500', type_installation='commercial',
                                   facture_hiver=1200, ville='Casablanca', categorie_commerciale='bureau',
                                   tension_raccordement='bt', raccordement='triphase', type_toiture='bac_acier')
        calepinage = Calepinage.objects.create(company=self.company, lead_id=lead.pk, titre='Boulangerie')
        url = f'{url_detail(calepinage.pk)}cible-factures/'
        with mock.patch.object(tasks.task_relancer_conception, 'apply_async') as en_file:  # jamais le courtier
            premiere, seconde = self.api.get(url), self.api.get(url)
        self.assertEqual(premiere.status_code, 200, premiere.data)
        self.assertEqual(premiere.data, CONTRAT_CIBLE['exemple_en_cours'])
        self.assertEqual(seconde.data, CONTRAT_CIBLE['exemple_en_cours'])
        self.assertEqual(en_file.call_count, 1)  # dédupliqué : une seule tâche pour ce lead
        self.assertFalse(ConceptionLead.objects.filter(lead=lead).exists())  # rien calculé dans la requête

        with mock.patch.object(etude_ci, 'lire_production', side_effect=ci_fab._production_casablanca), \
                mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=ci_fab._tarif_grille):
            rendu = tasks.task_relancer_conception(**en_file.call_args.kwargs['kwargs'])
        self.assertEqual(rendu, {'version': 1, 'ecrite': True})
        version = ConceptionLead.objects.get(lead=lead, courante=True)
        self.assertEqual(version.etat, 'complet', version.refus)
        valeurs = version.valeurs[version.option_retenue]
        panneaux, kwc = valeurs['nb_panneaux']['valeur'], valeurs['puissance_kwc']['valeur']
        self.assertGreater(panneaux, 0)
        reponse = self.api.get(url)
        self.assertEqual(sorted(reponse.data), sorted(CONTRAT_CIBLE['exemple']))
        self.assertEqual(reponse.data, {
            'cible_factures': {'panneaux': panneaux, 'kwc': kwc, 'module_wc': float(round(kwc * 1000 / panneaux)),
                               'version': version.version, 'raison': (version.declencheur or {}).get('raison') or None},
            'refus': '', 'calcul_en_cours': False})
        sans_lead = self.api.get(f'{url_detail(self.nu.pk)}cible-factures/')
        self.assertEqual(sans_lead.data, CONTRAT_CIBLE['exemple_vide'])

    def test_sans_devis_ni_facture_la_cible_est_nulle(self):
        contexte = self._contexte(self.nu)
        self.assertIsNone(contexte['cible'])
        self.assertTrue(any('cible' in m for m in contexte['avertissements']))

    def test_sans_geometrie_la_source_est_none(self):
        contexte = self._contexte(self.nu)
        self.assertEqual(contexte['geometrie']['source'], 'none')
        self.assertIsNone(contexte['geometrie']['pin'])
        self.assertEqual(contexte['geometrie']['outline'], [])

    def test_avec_layout_la_source_est_le_calepinage(self):
        contexte = self._contexte(self.avec_devis)
        self.assertEqual(contexte['geometrie']['source'], 'calepinage')
        self.assertEqual(contexte['geometrie']['roof_layout'], LAYOUT)

    def test_sans_layout_mais_avec_epingle_la_source_est_le_lead(self):
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk,
            titre='Repli lead')
        contexte = self._contexte(calepinage)
        self.assertEqual(contexte['geometrie']['source'], 'lead')
        self.assertEqual(contexte['geometrie']['pin'],
                         {'lat': 33.5731, 'lng': -7.5898})

    def test_cible_avec_devis_lie_vient_de_la_conception(self):
        # ACAL2012 — le devis lié n'est plus la source de la cible : la conception du lead l'est.
        from .test_acal_cible_lead import ranger_conception

        ranger_conception(lead=self.lead_lie, nb=14)
        contexte = self._contexte(self.avec_devis)
        self.assertEqual((contexte['cible']['source'], contexte['cible']['panneaux']), ('factures', 14))

    def test_raison_lecture_seule_reprise_mot_pour_mot(self):
        phrase = 'Devis accepté : la conception ne se modifie plus.'
        faux_contexte = {
            'cible': None, 'geometrie': {'contour_client': []},
            'raison_lecture_seule': phrase, 'avertissements': [],
        }
        with mock.patch('apps.ventes.selectors.contexte_conception_devis',
                        return_value=faux_contexte):
            contexte = self._contexte(self.avec_devis)
        self.assertEqual(contexte['raison_lecture_seule'], phrase)
        self.assertFalse(contexte['modifiable'])

    def test_layout_sans_geometrie_retombe_sur_le_trace_du_client(self):
        """Le tracé du client ne se perd pas derrière un layout sans géométrie.

        C'est le cas RÉEL d'un calepinage né d'un devis automatique (son
        ``roof_layout`` ne porte que ``result``/``panelWatt``) ou d'un premier
        enregistrement fait avant qu'un pan n'ait été dessiné : ``outline``
        valait ``[]`` et l'atelier n'avait AUCUN pan à ouvrir, alors que le
        contour du client était là. Miroir du repli déjà posé côté ventes.
        """
        contour = CONTOUR_AUTOUR_DU_REPERE
        self.lead_lie.roof_outline = contour
        self.lead_lie.save(update_fields=['roof_outline'])
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk,
            titre='Repris du devis automatique',
            roof_layout={'version': 2, 'outline': [],
                         'result': {'kwc': 4.4}, 'panelWatt': 550})
        geometrie = self._contexte(calepinage)['geometrie']
        self.assertEqual(geometrie['outline'], contour)
        self.assertEqual(geometrie['pin'], {'lat': 33.5731, 'lng': -7.5898})
        self.assertEqual(geometrie['contour_client'], contour)

    def test_layout_deja_dessine_garde_son_contour(self):
        """Le repli ci-dessus ne touche JAMAIS un calepinage déjà dessiné."""
        contour_client = [[33.5731, -7.5898], [33.5732, -7.5898],
                          [33.5732, -7.5897]]
        self.lead_lie.roof_outline = contour_client
        self.lead_lie.save(update_fields=['roof_outline'])
        dessine = [[33.6, -7.6], [33.61, -7.6], [33.61, -7.59]]
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, titre='Dessiné',
            roof_layout={'version': 2, 'outline': dessine,
                         'zones': [{'id': 'z1', 'vertices': dessine}]})
        geometrie = self._contexte(calepinage)['geometrie']
        self.assertEqual(geometrie['outline'], dessine)
        self.assertEqual(geometrie['contour_client'], contour_client)

    def test_zones_sans_sommets_ne_comptent_pas_pour_une_geometrie(self):
        """Un premier enregistrement AVANT tout dessin garde le tracé client.

        Constat production (20/09/2026) : ``/calepinage/<id>`` restait figé
        (« Devis chargé — tracez le contour du toit », zéro pan, zéro requête
        de rendement) là où ``/ventes/devis/<id>/design`` ouvrait le toit du
        MÊME lead. Le sérialiseur de l'atelier émet TOUJOURS une zone (il
        projette la zone par défaut) : « Enregistrer » avant tout dessin écrit
        ``{outline: [], zones: [{vertices: []}]}``. L'ancien test (« ``zones``
        présent ? ») lisait ce layout comme un calepinage déjà dessiné et
        jetait le contour du client.
        """
        contour = CONTOUR_AUTOUR_DU_REPERE
        self.lead_lie.roof_outline = contour
        self.lead_lie.save(update_fields=['roof_outline'])
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk,
            titre='Enregistré avant tout dessin',
            roof_layout={'version': 2, 'pin': None, 'outline': [],
                         'zones': [{'id': 'z1', 'label': 'Zone 1',
                                    'vertices': []}],
                         'activeAreaId': 'z1'})
        geometrie = self._contexte(calepinage)['geometrie']
        self.assertEqual(geometrie['outline'], contour)
        self.assertEqual(geometrie['pin'], {'lat': 33.5731, 'lng': -7.5898})
        self.assertEqual(geometrie['contour_client'], contour)

    def test_adresse_du_client_servie_comme_en_mode_devis(self):
        """L'atelier pré-remplit sa barre d'adresse : le serveur la fournit."""
        self.lead_lie.adresse = 'Cour Golf, 17000 Nouaceur'
        self.lead_lie.save(update_fields=['adresse'])
        bloc = self._contexte(self.avec_devis)['calepinage']
        self.assertEqual(bloc['client_adresse'], 'Cour Golf, 17000 Nouaceur')
        self.assertEqual(bloc['client_ville'], 'Casablanca')

    def test_adresse_inconnue_vaut_une_chaine_vide(self):
        """Jamais une clé absente, jamais une adresse inventée."""
        bloc = self._contexte(self.nu)['calepinage']
        self.assertEqual(bloc['client_adresse'], '')
        self.assertEqual(bloc['client_ville'], '')

    def test_relecture_m1_site_de_repli_dit_ce_que_fera_le_calcul(self):
        """Relecture M1 — un calepinage d'un CLIENT sans lead dont l'adresse
        nomme une ville : le serveur sert la ville qu'il prendra (le bandeau
        l'imprime) ; rien de résoluble ⇒ ``None`` (le calcul est refusé) ;
        un lead avec repère ⇒ sa position GPS."""
        self.assertIsNone(self._contexte(self.nu)['calepinage']['site_de_repli'])
        self.client_lie.adresse = '12 rue des Fleurs, Casablanca'
        self.client_lie.save(update_fields=['adresse'])
        self.assertEqual(self._contexte(self.nu)['calepinage']['site_de_repli'],
                         'Casablanca (ville de référence)')
        self.client_lie.adresse = "Route d'El Jadida, Casablanca"
        self.client_lie.save(update_fields=['adresse'])
        self.assertIsNone(self._contexte(self.nu)['calepinage']['site_de_repli'])
        self.assertEqual(
            self._contexte(self.avec_devis)['calepinage']['site_de_repli'],
            'la position GPS de la fiche')

    def test_t4_x2_005_point_de_repli_meme_lieu_que_la_simulation(self):
        """T4-X2-005 — le POINT du repli (l'atelier y cale le pas entre
        rangées) est celui que la simulation prend : ``point_du_site`` sur un
        document sans épingle ; ``None`` exactement quand le libellé l'est."""
        from apps.calepinage.services.site import point_du_site
        self.assertIsNone(self._contexte(self.nu)['calepinage']['site_de_repli_point'])
        self.client_lie.adresse = '12 rue des Fleurs, Casablanca'
        self.client_lie.save(update_fields=['adresse'])
        point = self._contexte(self.nu)['calepinage']['site_de_repli_point']
        lat, lon, reference = point_du_site({}, lambda: {'adresse': '12 rue des Fleurs, Casablanca'})
        self.assertEqual(point, {'lat': lat, 'lon': lon, 'libelle': reference['libelle']})
        self.assertEqual(point['libelle'], 'Casablanca (ville de référence)')
        bloc = self._contexte(self.avec_devis)['calepinage']
        self.assertEqual(bloc['site_de_repli_point']['libelle'], bloc['site_de_repli'])

    def _lead_gps_hors_contour(self):
        """ACAL250 — roof_point A DANS R, GPS corrigé B HORS de R."""
        self.lead_lie.roof_outline = CONTOUR_AUTOUR_DU_REPERE
        self.lead_lie.gps_lat, self.lead_lie.gps_lng = 33.6, -7.7
        self.lead_lie.save(update_fields=['roof_outline', 'gps_lat',
                                          'gps_lng'])

    def test_contour_inutilisable_ni_graine_ni_zone(self):
        """ACAL250 — le drapeau est publié ; R reste un calque, jamais une
        graine éditable, et le pin est le GPS corrigé B."""
        self._lead_gps_hors_contour()
        sans_layout = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, titre='Lead')
        layout_vide = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, titre='Vide',
            roof_layout={'version': 2, 'outline': [],
                         'zones': [{'id': 'z1', 'vertices': []}]})
        for calepinage in (sans_layout, layout_vide):
            geometrie = self._contexte(calepinage)['geometrie']
            self.assertFalse(geometrie['contour_utilisable'])
            self.assertEqual(geometrie['source_repere'], 'gps')
            self.assertEqual(geometrie['outline'], [])
            self.assertEqual(geometrie['contour_client'],
                             CONTOUR_AUTOUR_DU_REPERE)
            self.assertEqual(geometrie['pin'], {'lat': 33.6, 'lng': -7.7})

    def test_contour_inutilisable_cote_devis(self):
        """ACAL250 — le contexte de conception DEVIS dit la même chose."""
        from apps.ventes.selectors import contexte_conception_devis

        self._lead_gps_hors_contour()
        devis = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference='DEV-202609-2312')
        geometrie = contexte_conception_devis(devis, self.company)['geometrie']
        self.assertFalse(geometrie['contour_utilisable'])
        self.assertEqual(geometrie['source_repere'], 'gps')
        self.assertEqual(geometrie['outline'], [])
        self.assertEqual(geometrie['contour_client'], CONTOUR_AUTOUR_DU_REPERE)

    def test_contour_utilisable_ensemence_le_pan(self):
        self.lead_lie.roof_outline = CONTOUR_AUTOUR_DU_REPERE
        self.lead_lie.save(update_fields=['roof_outline'])
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, titre='Lead')
        geometrie = self._contexte(calepinage)['geometrie']
        self.assertTrue(geometrie['contour_utilisable'])
        self.assertEqual(geometrie['source_repere'], 'roof_point')
        self.assertEqual(geometrie['outline'], CONTOUR_AUTOUR_DU_REPERE)

    def test_trois_portes_meme_reponse(self):
        """ACAL282 — roof-config, contexte devis et design-context calepinage
        lisent la clé carte par UNE fonction (ventes.selectors.config_carte)."""
        from apps.ventes.selectors import contexte_conception_devis

        attendu = {'available': True, 'maptilerKey': 'k', 'mapboxToken': None}
        env = {'PUBLIC_MAPTILER_KEY': 'k', 'PUBLIC_MAPBOX_TOKEN': ''}
        with mock.patch.dict('os.environ', env):
            roof = self.api.get('/api/django/ventes/roof-config/')
            self.assertEqual(roof.status_code, 200)
            portes = [
                roof.data,
                contexte_conception_devis(self.devis, self.company)['carte'],
                self._contexte(self.avec_devis)['carte'],
            ]
        for carte in portes:
            self.assertEqual(dict(carte), attendu)
        with mock.patch.dict('os.environ', {'PUBLIC_MAPTILER_KEY': ''}):
            self.assertFalse(self._contexte(self.nu)['carte']['available'])

    def test_devis_porte_par_une_variante_sert_la_variante(self):
        """ACON80 (D-ACON-2) — ``?devis=<B>`` d'un devis porté par une
        VARIANTE de ce calepinage : le contexte sert la variante et SON
        document ; sans le paramètre (ou un devis étranger) : inchangé."""
        from apps.calepinage.models import CalepinageVariante
        from apps.calepinage.selectors import ombrage_servi
        from apps.ventes.selectors import contexte_conception_devis

        b = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference='DEV-202609-2312')
        document_v = dict(LAYOUT, result={'panels': 8, 'kwc': 5.76})
        v = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.avec_devis,
            nom=f'Devis {b.reference}', roof_layout=document_v, devis=b)

        contexte = self.api.get(
            url_contexte(self.avec_devis.pk), {'devis': b.pk}).data
        self.assertEqual(contexte['variante'],
                         {'id': v.pk, 'nom': v.nom, 'devis': b.pk})
        self.assertEqual(contexte['geometrie']['roof_layout'], document_v)
        self.assertEqual(contexte['calepinage']['devis_lie']['id'], b.pk)
        self.assertEqual(set(contexte), set(CONTRAT['exemple_variante']))
        # ACAL993 — le chiffrage lit le devis ET le document de la variante.
        with mock.patch('apps.ventes.services.chiffrer_conception',
                        return_value={}) as porte:
            self.api.get(url_contexte(self.avec_devis.pk), {'devis': b.pk})
        servie = porte.call_args.kwargs['calepinage']
        self.assertEqual((servie.devis_id, servie.roof_layout),
                         (b.pk, document_v))
        # Sans paramètre, ou un devis qui n'est pas porté ici : inchangé.
        for params in ({}, {'devis': self.devis.pk}, {'devis': 'x'}):
            with self.subTest(params=params):
                servi = self.api.get(url_contexte(self.avec_devis.pk),
                                     params).data
                self.assertIsNone(servi['variante'])
                self.assertEqual(servi['geometrie']['roof_layout'], LAYOUT)
        # Le contexte devis de B dessine le document de V ; C1 intact.
        self.assertEqual(contexte_conception_devis(b, self.company)
                         ['geometrie']['roof_layout'], document_v)
        self.avec_devis.refresh_from_db()
        self.assertEqual(self.avec_devis.roof_layout, LAYOUT)
        # Sans simulation de V : aucun ombrage d'une autre conception.
        self.assertIsNone(ombrage_servi(b.pk, self.company))

    def test_facture_mensuelle_du_lead_servie(self):
        # ACAL776 — 900 MAD en hiver et en été ⇒ 900,0 ; sans facture ⇒ null.
        Lead.objects.filter(pk=self.lead_lie.pk).update(
            facture_hiver=900, ete_differente=False)
        servi = self._contexte(self.avec_devis)['consommation_lead']
        self.assertEqual(servi, {'facture_mensuelle_mad': 900.0,
                                 'source': 'lead', 'motif': ''})
        sans_lead = self._contexte(self.nu)['consommation_lead']
        self.assertIsNone(sans_lead['facture_mensuelle_mad'])
        self.assertTrue(sans_lead['motif'])

    def test_acal993_chiffrage_lu_par_la_porte_de_ventes(self):
        """ACAL993 — lead à facture 900 MAD/mois, sans devis : ``chiffrage`` =
        ``chiffrer_conception`` de ce calepinage ; sans lead : ``non_servi`` et
        son motif. Mutant : renvoyer ``None`` ⇒ rouge."""
        from apps.ventes.services import chiffrer_conception

        Lead.objects.filter(pk=self.lead_lie.pk).update(facture_hiver=900, ete_differente=False)
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, titre='ACAL993',
            roof_layout=LAYOUT, layout_hash='b' * 64)
        # ADEV153 — le chiffrage LIT la conception rangée du lead (aucun noyau) : ici 6 047 kWh/an rangés.
        rangee = {'etat': 'complet', 'marche': 'residentiel', 'option_retenue': 'sans', 'niveau_regles': 15,
                  'entrees_utilisees': {'facture_hiver': {'valeur': 900, 'source': 'lead'}},
                  'valeurs': {'sans': {
                      'puissance_kwc': {'valeur': 4.4}, 'production_annuelle': {'valeur': 6047.0, 'source': 'pose'},
                      'economies_annuelles': {'valeur': 5100.0}, 'autoconsommation': {'valeur': 0.62},
                      'couverture': {'valeur': 0.55}}}}
        with mock.patch('apps.ventes.conception.service.conception_ou_calcul', return_value=(rangee, False)):
            servi = self._contexte(calepinage)['chiffrage']
            attendu = chiffrer_conception(calepinage=calepinage, company=self.company)
        self.assertEqual(set(servi), set(CONTRAT['exemple']['chiffrage']))
        self.assertEqual(servi['production_annuelle_kwh']['valeur'],
                         attendu['production_annuelle_kwh']['valeur'])
        self.assertEqual(servi['production_annuelle_kwh']['valeur'], 6047.0)
        self.assertEqual(servi['couverture_pct']['valeur'], 55.0)
        sans_lead = self._contexte(self.nu)['chiffrage']
        self.assertEqual({sans_lead[c]['etat'] for c in ('kwc', 'production_annuelle_kwh')}, {'non_servi'})
        self.assertEqual(sans_lead['omissions'], CONTRAT['exemple_vide']['chiffrage']['omissions'])

    def test_r2_15_toiture_declaree_du_lead_servie(self):
        """R2-15 / R2-01 — le lead en tuiles, 25°, sud-ouest, ombrage partiel :
        ``toiture_lead`` le redit ; ``mode_pose`` est celui du DOCUMENT (CIQ112) ;
        sans lead, tous les champs sont nuls."""
        Lead.objects.filter(pk=self.lead_lie.pk).update(
            type_toiture='tuiles', inclinaison_deg=25, orientation='sud_ouest',
            ombrage='partiel', ombrage_notes=' palmier ')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, titre='R2-15',
            roof_layout={'modePoseDeclare': 'toiture_inclinee'})
        servi = self._contexte(calepinage)['toiture_lead']
        self.assertEqual(set(servi), set(CONTRAT['exemple']['toiture_lead']))
        self.assertEqual((servi['type_toiture'], servi['inclinaison_deg'], servi['orientation'],
                          servi['ombrage'], servi['ombrage_notes'], servi['mode_pose']),
                         ('Tuiles', 25.0, 'Sud-Ouest', 'Partiel', 'palmier', 'toiture_inclinee'))
        self.assertIsNone(servi['surface_toiture_m2'])
        self.assertEqual(set(self._contexte(self.nu)['toiture_lead'].values()), {None})

    def test_t4_u3_012_pompage_du_lead_servi_en_preremplissage(self):
        """T4-U3-012 — le lead dit HMT 80 m (déclarée), débit souhaité 20 m³/h,
        niveau statique 40 m (mesuré en visite), débit du forage 25 m³/h (essai) :
        ``prefill_lead.pompage`` les sert sous les clés du panneau Pompage, chacune
        avec SA provenance telle que la fiche la garde. Sans lead : ``null`` ; un
        lead d'une autre société n'est jamais lu."""
        from decimal import Decimal

        Lead.objects.filter(pk=self.lead_lie.pk).update(
            pompe_hmt_m=Decimal('80'), pompe_hmt_source='declaree',
            pompe_debit_m3h=Decimal('20'), niveau_statique_m=Decimal('40'),
            niveau_statique_source='mesure_visite', debit_forage_m3h=Decimal('25'),
            debit_forage_source='essai')
        servi = self._contexte(self.avec_devis)['prefill_lead']
        self.assertEqual(set(servi), set(CONTRAT['exemple']['prefill_lead']))
        self.assertEqual(servi['lead'], self.lead_lie.pk)
        pompage = servi['pompage']
        self.assertEqual(set(pompage), set(CONTRAT['exemple']['prefill_lead']['pompage']))
        self.assertEqual(pompage['hmt_saisie'], {
            'valeur': 80.0, 'origine': 'declaree', 'origine_libelle': 'Déclarée'})
        self.assertEqual(pompage['niveau_statique_m'], {
            'valeur': 40.0, 'origine': 'mesure_visite',
            'origine_libelle': 'Mesuré en visite'})
        self.assertEqual(pompage['debit_exploitation_m3h'], {
            'valeur': 25.0, 'origine': 'essai', 'origine_libelle': 'Essai de pompage'})
        self.assertEqual(pompage['debit_souhaite_m3h'], {
            'valeur': 20.0, 'origine': None, 'origine_libelle': None})
        self.assertIsNone(self._contexte(self.nu)['prefill_lead'])
        lead_voisin = Lead.objects.create(
            company=self.autre, nom='Voisin', pompe_hmt_m=Decimal('99'))
        piege = Calepinage.objects.create(
            company=self.company, lead_id=lead_voisin.pk, titre='Lead voisin')
        self.assertIsNone(self._contexte(piege)['prefill_lead'])

    def test_autre_societe_introuvable(self):
        reponse = self.api.get(url_contexte(self.etranger.pk))
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_403(self):
        reponse = self.api_sans.get(url_contexte(self.avec_devis.pk))
        self.assertEqual(reponse.status_code, 403)


class ToitureDuLeadTest(unittest.TestCase):
    """R2-15 / R2-01 — le bloc ``toiture_lead``, sans base (lead non enregistré)."""

    @staticmethod
    def servi(lead, roof_layout=None, lead_id=7):
        from apps.calepinage.views.toiture_lead import toiture_du_lead

        calepinage = mock.Mock(lead_id=lead_id, roof_layout=roof_layout)
        return toiture_du_lead(object(), calepinage, lire_lead=lambda company, pk: lead)

    def test_ce_que_le_lead_declare_tel_quel(self):
        lead = Lead(type_surface='toiture', type_toiture='tuiles', orientation='sud_ouest',
                    ombrage='partiel', ombrage_notes='palmier', inclinaison_deg='25.00',
                    surface_toiture_m2='60.00', nb_etages=2, roof_age=15, structure_pref='acier')
        servi = self.servi(lead, {'modePoseDeclare': 'toiture_inclinee'})
        self.assertEqual(set(servi), set(CONTRAT['exemple']['toiture_lead']))
        self.assertEqual(servi, {
            'type_surface': 'Toiture', 'type_toiture': 'Tuiles', 'orientation': 'Sud-Ouest',
            'ombrage': 'Partiel', 'structure_pref': 'Acier', 'surface_toiture_m2': 60.0,
            'inclinaison_deg': 25.0, 'nb_etages': 2.0, 'roof_age': 15.0,
            'ombrage_notes': 'palmier', 'mode_pose': 'toiture_inclinee'})

    def test_rien_de_declare_tout_est_nul(self):
        # Un lead muet, puis aucun lead : chaque champ vaut None (jamais deviné).
        for lead in (Lead(), None):
            with self.subTest(lead=lead):
                self.assertEqual(set(self.servi(lead).values()), {None})

    def test_mode_pose_relu_du_document_jamais_recalcule(self):
        # Le lead dit « tuiles » mais le document ne porte aucun mode : None
        # (le serveur ne l'applique pas, l'atelier non plus).
        self.assertIsNone(self.servi(Lead(type_toiture='tuiles'), {'zones': []})['mode_pose'])
        self.assertIsNone(self.servi(None, {'modePoseDeclare': ''})['mode_pose'])


class CibleFacturesTest(unittest.TestCase):
    """Maquette Panneaux — ``cible_factures`` : la cible du garde R2-17, telle quelle, sans base."""

    @staticmethod
    def servi(cible):
        from apps.calepinage.views.toiture_lead import cible_factures

        return cible_factures(mock.Mock(), lire_cible=lambda calepinage: cible)

    def test_taille_tiree_des_factures_servie_telle_quelle(self):
        servi = self.servi({'panneaux': 12, 'panel_watt': 580, 'kwc': 6.96, 'source': 'factures',
                            'refus': None, 'motif_code': None, 'version': 3, 'raison': 'Recalculé le 25/11'})
        self.assertEqual(set(servi), set(CONTRAT_CIBLE['exemple']['cible_factures']))
        self.assertNotIn('cible_factures', CONTRAT['exemple'])  # H3 : hors du démarrage de l'atelier
        # Lane E9 — la version et la raison de la conception voyagent avec ses chiffres.
        self.assertEqual(servi, {'panneaux': 12, 'kwc': 6.96, 'module_wc': 580.0, 'version': 3,
                                 'raison': 'Recalculé le 25/11'})

    def test_aucune_cible_des_factures_vaut_none(self):
        # Sans lead, taille souhaitée du lead, refus (sans facture, C&I…) : jamais une taille devinée.
        for cible in (None, {'panneaux': 10, 'panel_watt': 580, 'kwc': 5.8, 'source': 'lead'},
                      {'panneaux': None, 'kwc': None, 'source': 'factures', 'refus': 'Aucune facture.'}):
            with self.subTest(cible=cible):
                self.assertIsNone(self.servi(cible))

    # R6-N4 — lead R5A-4 : facture 900 MAD ET taille souhaitée 6 kWc. La taille souhaitée est souveraine (« lead »),
    # aucune taille ne vient des factures, mais ce n'est PAS parce que la facture manque — la phrase le dit.
    def test_taille_souhaitee_dite_et_non_une_facture_absente(self):
        from decimal import Decimal

        from apps.calepinage.views.toiture_lead import cible_factures_et_refus

        cible = {'panneaux': 9, 'panel_watt': 710, 'kwc': 6.39, 'source': 'lead', 'refus': None, 'motif_code': None}

        def refus_pour(souhait, cible=cible):
            lead = mock.Mock(taille_souhaitee_kwc=souhait)
            return cible_factures_et_refus(mock.Mock(), lire_cible=lambda calepinage: cible,
                                           lire_lead=lambda company, pk: lead)

        servi, refus = refus_pour(Decimal('6'))
        self.assertIsNone(servi)
        # Le SOUHAIT tel qu'il est sur la fiche (rond : « 6 kWc », jamais « 6,00 »),
        # la pose calculée nommée « conception ».
        self.assertEqual(refus, 'La taille de ce lead vient de la taille souhaitée sur sa fiche '
                                '(6 kWc ; conception : 9 panneaux · 6,39 kWc), pas de ses factures.')
        self.assertNotIn('Aucune taille', refus)
        self.assertIn('(6,5 kWc ; conception', refus_pour(Decimal('6.5'))[1])
        # Souhait illisible : jamais inventé — seule la conception, nommée comme telle.
        self.assertIn('(conception : 9 panneaux · 6,39 kWc)', refus_pour(None)[1])
        un = dict(cible, panneaux=1, kwc=None)
        self.assertIn('(6 kWc ; conception : 1 panneau)', refus_pour(Decimal('6'), un)[1])

    def test_les_autres_refus_et_la_cible_des_factures_ne_changent_pas(self):
        from apps.calepinage.views.toiture_lead import cible_factures_et_refus

        refus = {'panneaux': None, 'source': 'factures', 'refus': 'Aucune facture.'}
        self.assertEqual(cible_factures_et_refus(mock.Mock(), lire_cible=lambda c: refus), (None, 'Aucune facture.'))
        self.assertEqual(cible_factures_et_refus(mock.Mock(), lire_cible=lambda c: None), (None, ''))
        sans_lead = {'panneaux': 16, 'source': 'conception', 'refus': None}
        self.assertEqual(cible_factures_et_refus(mock.Mock(), lire_cible=lambda c: sans_lead), (None, ''))
        factures = {'panneaux': 12, 'panel_watt': 580, 'kwc': 6.96, 'source': 'factures', 'refus': None}
        servi, texte = cible_factures_et_refus(mock.Mock(), lire_cible=lambda c: factures)
        self.assertEqual((servi['panneaux'], texte), (12, ''))


class FactureMensuelleDuLeadTest(unittest.TestCase):
    """ACAL776 — la facture mensuelle moyenne du lead, sans base."""

    @staticmethod
    def lead(hiver, ete=None, differente=False):
        return mock.Mock(facture_hiver=hiver, facture_ete=ete,
                         ete_differente=differente, conso_mensuelle_kwh=None)

    def servi(self, lead, lead_id=7):
        from apps.calepinage.services.consommation import (
            facture_mensuelle_du_lead,
        )
        return facture_mensuelle_du_lead(
            object(), lead_id, lire_lead=lambda company, pk: lead)

    def test_900_en_hiver_et_en_ete_sert_900(self):
        servi = self.servi(self.lead(900))
        self.assertEqual(servi, {'facture_mensuelle_mad': 900.0,
                                 'source': 'lead', 'motif': ''})

    def test_la_moyenne_est_annuel_divise_par_douze(self):
        # hiver 1200 / été 600 : la moyenne des douze mois interpolés.
        servi = self.servi(self.lead(1200, 600, True))
        self.assertIsNotNone(servi['facture_mensuelle_mad'])
        self.assertLess(servi['facture_mensuelle_mad'], 1200.0)
        self.assertGreater(servi['facture_mensuelle_mad'], 600.0)

    def test_sans_facture_null_avec_motif(self):
        servi = self.servi(self.lead(None))
        self.assertIsNone(servi['facture_mensuelle_mad'])
        self.assertIsNone(servi['source'])
        self.assertIn('facture', servi['motif'])

    def test_sans_lead_ou_autre_societe_null_avec_motif(self):
        for lead_id, lead in ((None, None), (7, None)):
            with self.subTest(lead_id=lead_id):
                servi = self.servi(lead, lead_id)
                self.assertIsNone(servi['facture_mensuelle_mad'])
                self.assertIn('lead', servi['motif'])
