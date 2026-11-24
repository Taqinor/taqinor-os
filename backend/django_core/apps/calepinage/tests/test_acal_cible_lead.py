"""ACAL194 (C-ACAL-004) — la cible d'un calepinage SANS devis vient du lead.

Ce qui est prouvé ici :

* un lead avec facture d'hiver et ville : ``cible`` = le MÊME nombre de
  panneaux que le devis automatique (``build_devis_auto``) pour ce lead,
  ``source: 'factures'`` — plus de bouchon CAL147 rendant ``None`` ;
* ``taille_souhaitee_kwc`` est SOUVERAINE (``source: 'lead'``) ;
* sans facture, le motif du moteur est NOMMÉ (``cible.refus`` et
  avertissement), jamais une puissance devinée ;
* un devis lié garde ``source: 'devis'`` ;
* lecture pure : deux GET rendent la même cible, rien n'est écrit.

Run :
    python manage.py test apps.calepinage.tests.test_acal_cible_lead -v2
"""
from decimal import Decimal

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail


def url_contexte(pk):
    return f'{url_detail(pk)}design-context/'


class CibleDuLeadTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        # Catalogue minimal (mêmes désignations que seed_catalogue).
        for nom, sku, prix in (
                ('Panneau Jinko 550W', 'A194-PAN', 1100),
                ('Onduleur réseau Huawei 5kW Monophasé', 'A194-ONDR', 14000),
                ('Onduleur hybride Deye 5kW Monophasé', 'A194-ONDH', 17000),
                ('Batterie Dyness 5 kWh', 'A194-BAT', 17000)):
            Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=100)

    def _lead(self, **extra):
        extra.setdefault('ville', 'Casablanca')
        extra.setdefault('email', 'cible194@example.com')
        return Lead.objects.create(company=self.company, nom='Cible',
                                   prenom='194', **extra)

    def _calepinage(self, lead, **extra):
        return Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, titre='Cible 194',
            **extra)

    def _contexte(self, calepinage):
        reponse = self.api.get(url_contexte(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_cible_du_lead_egale_la_taille_du_devis_auto(self):
        from apps.ventes.services import build_devis_auto, relancer

        lead = self._lead(facture_hiver=Decimal('1800'))
        # ACAL2012 — la conception rangée par l'écrivain unique, puis lue par l'atelier.
        relancer(lead, company=self.company, declencheur={'origine': 'manuel', 'champs': []})
        cible = self._contexte(self._calepinage(lead))['cible']
        self.assertIsNotNone(cible)
        self.assertEqual(cible['source'], 'factures')
        self.assertIsNone(cible['refus'])

        devis = build_devis_auto(lead=lead, user=self.user,
                                 company=self.company)
        # Même lecture que ``ventes/tests/test_devis_auto`` : la ligne
        # panneau du devis automatique.
        panneaux_devis = int(next(
            li for li in devis.lignes.all()
            if 'Panneau' in li.designation).quantite)
        self.assertGreater(panneaux_devis, 0)
        self.assertEqual(cible['panneaux'], panneaux_devis)
        self.assertEqual(cible['kwc'],
                         round(cible['panneaux'] * cible['panel_watt']
                               / 1000, 2))

    def test_taille_souhaitee_souveraine(self):
        lead = self._lead(facture_hiver=Decimal('1800'),
                          taille_souhaitee_kwc=Decimal('6.5'))
        ranger_conception(lead=lead, nb=10, watt=710)  # ACAL2012 — la conception rangée
        cible = self._contexte(self._calepinage(lead))['cible']
        self.assertEqual(cible['source'], 'lead')
        # plafond(6 500 / 710) = 10 — la conversion du devis automatique.
        self.assertEqual(cible['panneaux'], 10)
        self.assertEqual(cible['panel_watt'], 710)
        self.assertIsNone(cible['refus'])

    def test_sans_facture_le_motif_est_nomme(self):
        lead = self._lead()
        contexte = self._contexte(self._calepinage(lead))
        cible = contexte['cible']
        self.assertIsNotNone(cible)
        self.assertIsNone(cible['panneaux'])
        self.assertTrue(cible['refus'])
        # ACAL965 — le refus n'est servi qu'une fois : dans `cible.refus`, jamais répété dans `avertissements`.
        self.assertFalse([a for a in contexte['avertissements']
                          if 'Cible de puissance non calculée' in a or cible['refus'] in a])
        self.assertNotIn('Aucune cible de puissance connue : renseignez-la, '
                         'ou rattachez un devis.',
                         contexte['avertissements'])

    def test_devis_lie_ne_donne_plus_la_cible(self):
        # ACAL2012 — un devis lié n'est plus la source : la conception du lead l'est.
        lead = self._lead(facture_hiver=Decimal('1800'))
        ranger_conception(lead=lead, nb=12)
        client = Client.objects.create(company=self.company, nom='Client 194')
        devis = Devis.objects.create(company=self.company, client=client,
                                     lead=lead, reference='DEV-202610-1940')
        cible = self._contexte(self._calepinage(lead, devis=devis))['cible']
        self.assertEqual((cible['source'], cible['panneaux']), ('factures', 12))
        self.assertIsNone(cible['refus'])

    def test_lecture_pure_et_stable(self):
        from apps.ventes.models import ConceptionLead

        lead = self._lead(facture_hiver=Decimal('1800'))
        ranger_conception(lead=lead, nb=12)
        calepinage = self._calepinage(lead)
        avant = (calepinage.roof_layout, calepinage.updated_at)
        premiere = self._contexte(calepinage)['cible']
        seconde = self._contexte(calepinage)['cible']
        self.assertEqual(premiere, seconde)
        calepinage.refresh_from_db()
        self.assertEqual((calepinage.roof_layout, calepinage.updated_at),
                         avant)
        self.assertFalse(Devis.objects.filter(lead=lead).exists())
        self.assertEqual(ConceptionLead.objects.filter(lead=lead).count(), 1)


def _valeurs(nb, watt=550, onduleur=None, longueur=None):
    """La table §2 d'UNE option (contrat ``conception_lead.json``), valeurs posées."""
    def v(valeur, unite=None, source='moteur'):
        return {'valeur': valeur, 'unite': unite, 'source': source}
    onduleurs = [onduleur] if onduleur else []
    return {'nb_panneaux': v(nb, 'panneaux'), 'puissance_kwc': v(round(nb * watt / 1000, 2), 'kWc'),
            'module': v('Panneau Jinko %sW' % watt), 'onduleurs': v(onduleurs),
            'nombre_onduleurs': v(sum(o['quantite'] for o in onduleurs), 'onduleurs'),
            'chaines': v({'nombre': 1, 'longueurs': [longueur], 'longueur': longueur} if longueur else None),
            'ratio_dc_ac': v(None), 'production_annuelle': v(round(nb * watt * 1.6, 1), 'kWh/an')}


def ranger_conception(*, lead=None, calepinage=None, nb=10, etat='complet', refus=None, option='sans',
                      avec=None, **par_option):
    """ACAL2012 — une version COURANTE de la conception rangée par l'écrivain du modèle
    (``ConceptionLead.ranger``), valeurs posées : la fabrique des tests du calepinage."""
    from apps.ventes.models import ConceptionLead

    valeurs = {} if etat != 'complet' else {'sans': _valeurs(nb, **par_option)}
    if etat == 'complet' and avec is not None:
        valeurs['avec'] = _valeurs(avec, **par_option)
    porteur = ({'lead': lead} if lead is not None
               else {'calepinage_id': calepinage.pk, 'company': calepinage.company})
    return ConceptionLead.ranger(
        **porteur, etat=etat, refus=refus, marche='residentiel',
        option_retenue=option if etat == 'complet' else '', valeurs=valeurs, blocs={},
        entrees_utilisees={}, suppositions=[], empreinte='c' * 64, empreinte_pose='',
        niveau_regles=14, version_moteur='moteur-unique-1',
        declencheur={'raison': 'remplissage', 'champs': [], 'origine': 'remplissage'})


class CibleDeLaConceptionTest(BaseApiCalepinage):
    """ACAL2012 (C4-E5, D-ACAL-97) — la cible de l'atelier est la conception COURANTE :
    jamais celle d'un devis envoyé, la même avec ou sans devis, celle du porteur
    calepinage sans lead, un refus NOMMÉ sans conception possible. Lecture pure."""

    _lead, _calepinage, _contexte = CibleDuLeadTest._lead, CibleDuLeadTest._calepinage, CibleDuLeadTest._contexte

    def _cibles(self, calepinage):
        """``(cible du design-context, réponse de GET cible-factures/)``."""
        reponse = self.api.get(f'{url_detail(calepinage.pk)}cible-factures/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return self._contexte(calepinage)['cible'], reponse.data

    def test_devis_envoye_a_35_conception_a_48_la_cible_vaut_48(self):
        lead = self._lead(facture_hiver=Decimal('2400'))
        ranger_conception(lead=lead, nb=35)
        ranger_conception(lead=lead, nb=48)  # facture d'hiver modifiée : version 2, courante
        client = Client.objects.create(company=self.company, nom='Client 2012')
        devis = Devis.objects.create(company=self.company, client=client, lead=lead,
                                     reference='DEV-202611-2012', statut=Devis.Statut.ENVOYE)
        cible, factures = self._cibles(self._calepinage(lead, devis=devis))
        self.assertEqual((cible['panneaux'], cible['kwc'], cible['panel_watt']), (48, 26.4, 550))
        self.assertEqual((cible['source'], cible['option'], cible['refus']), ('factures', 'sans', None))
        self.assertEqual(factures, {'cible_factures': {'panneaux': 48, 'kwc': 26.4, 'module_wc': 550.0},
                                    'refus': ''})

    def test_sans_devis_la_conception_du_lead(self):
        lead = self._lead(facture_hiver=Decimal('2400'))
        ranger_conception(lead=lead, nb=20, avec=24, option='avec')
        cible, _factures = self._cibles(self._calepinage(lead))
        self.assertEqual((cible['panneaux'], cible['option'], cible['batterie']), (24, 'avec', True))

    def test_taille_souhaitee_dite_lead(self):
        lead = self._lead(taille_souhaitee_kwc=Decimal('6.5'))
        ranger_conception(lead=lead, nb=12)
        cible, factures = self._cibles(self._calepinage(lead))
        self.assertEqual((cible['source'], cible['panneaux']), ('lead', 12))
        self.assertIsNone(factures['cible_factures'])

    def test_sans_lead_la_conception_du_calepinage(self):
        client = Client.objects.create(company=self.company, nom='Client sans lead 2012')
        calepinage = Calepinage.objects.create(company=self.company, client=client, titre='Sans lead 2012')
        ranger_conception(calepinage=calepinage, nb=16)
        cible, _factures = self._cibles(calepinage)
        self.assertEqual((cible['panneaux'], cible['source']), (16, 'factures'))

    def test_conception_refusee_rend_le_refus_nomme(self):
        lead = self._lead()
        ranger_conception(lead=lead, etat='refus', refus={
            'code': 'refus_moteur', 'champ': 'facture_hiver',
            'message': 'Moteur unique : facture hiver du lead absente (ACAL2012).'})
        calepinage = self._calepinage(lead)
        cible, factures = self._cibles(calepinage)
        self.assertIsNone(cible['panneaux'])
        self.assertEqual(cible['refus'], 'Moteur unique : facture hiver du lead absente (ACAL2012).')
        self.assertEqual(factures, {'cible_factures': None, 'refus': cible['refus']})
        from apps.calepinage.services.devis import taille_non_dimensionnee
        self.assertEqual(taille_non_dimensionnee(calepinage), {'refus': cible['refus']})

    def test_conception_absente_refus_nomme_jamais_une_taille(self):
        lead = self._lead(facture_hiver=Decimal('1800'))
        cible, factures = self._cibles(self._calepinage(lead))
        self.assertIsNone(cible['panneaux'])
        self.assertIn('Conception du lead pas encore calculée', cible['refus'])
        self.assertIsNone(factures['cible_factures'])
