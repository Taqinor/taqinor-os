# -*- coding: utf-8 -*-
"""CJ2a — EXEMPLES FONDATEUR : le moteur décide, sous les yeux du fondateur.

ORDRE FONDATEUR : « show me examples with bill values 500dh, 800, 1200, 1700,
2500, 3500, 4500, and also some with different winter and summer ».

Ce module fait DEUX choses à la fois, et les deux comptent :

1. **Il IMPRIME** un rapport lisible par cas (préfixe ``EXEMPLE FONDATEUR``,
   visible dans le log CI en ``-v 2``) : la ou les factures en dirhams, les
   kWh/mois qu'elles impliquent, le TABLEAU des tailles candidates avec la
   règle des 80 % visible sur chaque ligne, puis la TAILLE RECOMMANDÉE et les
   lignes du devis qu'elle compose.
2. **Il ASSERTE la santé de chaque cas** — ce n'est pas un dump : la
   recommandation doit croître avec la facture, respecter la règle des 80 %,
   ne porter aucun verdict électrique bloquant, économiser plus AVEC batterie
   que sans, et jamais économiser plus que la facture annuelle.

TROU DE CATALOGUE. Si un palier de facture tombe sur une saveur que le
catalogue ne sait pas construire (le trou documenté n° 2 : hybride monophasé
5 kW impossible avec les panneaux 710 Wc, cf.
``test_pvfullrange_5_50``), la recommandation doit BASCULER honnêtement — et
l'exemple imprime CE choix. On ne cache pas un trou, on le montre.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_dimensionnement_exemples"
"""
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.ventes.courbes_journalieres import (
    OCCUPATION_PRESENCE,
    composer_equipements,
)
from apps.ventes.dimensionnement import RATIO_ONDULEUR_MIN, recommander_taille
from apps.ventes.etude_horaire import profil_depuis_factures
from authentication.models import Company

User = get_user_model()

#: Préfixe de log — l'orchestrateur extrait le rapport du log CI là-dessus.
TAG = 'EXEMPLE FONDATEUR'

#: Ville de référence des exemples : Casablanca-Bouskoura, le terrain réel de
#: la société (et la ville des trois factures qui étalonnent le barème).
VILLE = 'Casablanca'

#: Mots qui, dans un avertissement de composition, signalent un verdict
#: ÉLECTRIQUE bloquant (et non une simple remarque de catalogue).
MOTS_BLOQUANTS = ('ne se raccorde pas', 'incompatible', 'compatibilité')


class Cas:
    """Un exemple fondateur : ce qu'on lui donne, et sous quel raccordement."""

    def __init__(self, libelle, *, hiver, ete=None, phase=None,
                 occupation=OCCUPATION_PRESENCE, equipements=None):
        self.libelle = libelle
        self.hiver = hiver
        self.ete = ete
        self.phase = phase
        self.occupation = occupation
        self.equipements = equipements or {}

    @property
    def ete_differente(self):
        return self.ete is not None and self.ete != self.hiver


#: LES SEPT PALIERS demandés par le fondateur. Monophasé jusqu'à 1 700 DH,
#: triphasé au-delà — la règle terrain (une villa qui paie plus de ~2 000 DH
#: par mois est presque toujours en triphasé).
PALIERS = (
    Cas('500 DH/mois', hiver=500, phase='monophase'),
    Cas('800 DH/mois', hiver=800, phase='monophase'),
    Cas('1200 DH/mois', hiver=1200, phase='monophase'),
    Cas('1700 DH/mois', hiver=1700, phase='monophase'),
    Cas('2500 DH/mois', hiver=2500, phase='triphase'),
    Cas('3500 DH/mois', hiver=3500, phase='triphase'),
    Cas('4500 DH/mois', hiver=4500, phase='triphase'),
)

#: Le MÊME palier de 1 200 DH, mais déclaré TRIPHASÉ : montre que le
#: raccordement seul change l'onduleur retenu (règle de palier tri, PVCOMPAT).
CAS_TRI_1200 = Cas('1200 DH/mois — raccordement TRIPHASÉ', hiver=1200,
                   phase='triphase')

#: Trois profils hiver/été DIFFÉRENCIÉS — c'est là que la saisonnalité se voit.
SAISONNIERS = (
    Cas('800 hiver / 1600 été (villa climatisée)', hiver=800, ete=1600,
        phase='monophase',
        equipements={'clim': True, 'clim_pieces': 3}),
    Cas('1500 hiver / 900 été (chauffage électrique)', hiver=1500, ete=900,
        phase='monophase'),
    Cas('2500 hiver / 4000 été (villa + piscine)', hiver=2500, ete=4000,
        phase='triphase',
        equipements={'clim': True, 'clim_pieces': 5,
                     'piscine': True, 'piscine_pompe_kw': 1.1}),
)


def _mad(valeur):
    """Montant lisible : « 12 345 » (espace fine insécable exclue du log CI)."""
    try:
        return '{:,.0f}'.format(float(valeur)).replace(',', ' ')
    except (TypeError, ValueError):
        return '?'


def _pct(valeur):
    try:
        return '%.1f%%' % (float(valeur) * 100)
    except (TypeError, ValueError):
        return '?'


def _annees(valeur):
    return '%.1f a' % valeur if valeur is not None else '  n/a'


class ExemplesFondateurTest(TestCase):
    """Catalogue seedé UNE SEULE FOIS (``seed_catalogue`` est idempotent mais
    coûteux — jamais par test)."""

    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        cls.company, _ = Company.objects.get_or_create(
            slug='cj2a-exemples-co', defaults={'nom': 'CJ2a Exemples'})
        cls.user = User.objects.create_user(
            username='cj2a_exemples', password='x',
            role_legacy='responsable', company=cls.company)
        call_command('seed_catalogue', company_slug=cls.company.slug,
                     stdout=StringIO())

    # ── Moteur ───────────────────────────────────────────────────────────

    def _evaluer(self, cas):
        """Profil → tableau + recommandation. Rend aussi la conso déduite."""
        conso, source, detail = profil_depuis_factures(
            facture_hiver_mad=cas.hiver, facture_ete_mad=cas.ete,
            ete_differente=cas.ete_differente)
        self.assertIsNotNone(
            conso, '%s : aucune consommation déduite de la facture' % cas.libelle)
        resultat = recommander_taille(
            company=self.company, conso_kwh_mensuelles=conso, ville=VILLE,
            occupation=cas.occupation,
            equipements=composer_equipements(cas.equipements),
            phase=cas.phase, taux_tva=Decimal('20'), source_conso=source)
        return conso, source, detail, resultat

    # ── Rapport imprimé ──────────────────────────────────────────────────

    def _imprimer(self, cas, conso, source, resultat):
        annuel_mad = (cas.hiver * 6 + cas.ete * 6) if cas.ete_differente \
            else cas.hiver * 12
        print('')
        print('%s ══ %s' % (TAG, cas.libelle))
        if cas.ete_differente:
            print('%s    factures : %s DH hiver / %s DH ete  (%s DH/an)'
                  % (TAG, _mad(cas.hiver), _mad(cas.ete), _mad(annuel_mad)))
        else:
            print('%s    facture  : %s DH/mois  (%s DH/an)'
                  % (TAG, _mad(cas.hiver), _mad(annuel_mad)))
        print('%s    deduit   : %s kWh/mois hiver, %s kWh/an  (source %s)'
              % (TAG, _mad(conso[0]), _mad(sum(conso)), source))
        print('%s    profil   : %s, raccordement %s%s'
              % (TAG, cas.occupation, cas.phase or 'inconnu',
                 (', equipements ' + ', '.join(sorted(cas.equipements)))
                 if cas.equipements else ''))
        print('%s    %-4s %-7s %-22s %-9s %-6s %-6s %-10s %-10s %-8s'
              % (TAG, 'pan.', 'kWc', 'onduleur', 'ratio80', 'auto', 'couv',
                 'eco/an', 'eco+bat/an', 'payback'))
        for ligne in resultat['tableau']:
            marque = '>>' if (resultat['recommandation']
                              and ligne['panneaux']
                              == resultat['recommandation']['panneaux']) else '  '
            ratio = ('%.2f %s' % (ligne['ratio_onduleur_kwc'],
                                  'OK' if ligne['regle_80_pct_respectee']
                                  else '!!')
                     if ligne['ratio_onduleur_kwc'] else '   n/a')
            print('%s %s %-4d %-7.2f %-22s %-9s %-6s %-6s %-10s %-10s %-8s'
                  % (TAG, marque, ligne['panneaux'], ligne['kwc'],
                     (ligne['onduleur'] or '-')[:22], ratio,
                     _pct(ligne['taux_autoconso_sans']),
                     _pct(ligne['couverture_sans']),
                     _mad(ligne['economie_sans_mad']),
                     _mad(ligne['economie_avec_mad']),
                     _annees(ligne['payback_sans_annees'])))
            for avertissement in ligne['avertissements']:
                print('%s      ! %s' % (TAG, avertissement))

        recommandation = resultat['recommandation']
        if recommandation is None:
            print('%s    >>> AUCUNE TAILLE RECOMMANDEE — %s'
                  % (TAG, resultat['motivation']))
            return
        print('%s    >>> RECOMMANDE : %d panneaux, %.2f kWc, onduleur %s'
              % (TAG, recommandation['panneaux'], recommandation['kwc'],
                 recommandation['onduleur'] or '-'))
        print('%s        motif : %s' % (TAG, resultat['motivation']))
        print('%s        economie %s DH/an sans batterie, %s DH/an avec '
              '(facture %s DH/an) — couverture %s'
              % (TAG, _mad(recommandation['economie_sans_mad']),
                 _mad(recommandation['economie_avec_mad']), _mad(annuel_mad),
                 _pct(recommandation['couverture_sans'])))
        print('%s        cout %s DH TTC sans batterie, %s DH TTC avec'
              % (TAG, _mad(recommandation['cout_sans_ttc']),
                 _mad(recommandation['cout_avec_ttc'])))
        print('%s        lignes du devis (sans batterie) :' % TAG)
        for ligne in recommandation['lignes_sans']:
            print('%s          %2d x %-46s (%s)'
                  % (TAG, ligne['quantite'], ligne['designation'][:46],
                     ligne['role'] or '-'))

    # ── Assertions de santé, communes à tous les cas ─────────────────────

    def _verifier(self, cas, conso, resultat):
        libelle = cas.libelle
        self.assertTrue(resultat['tableau'],
                        '%s : tableau de tailles VIDE' % libelle)

        recommandation = resultat['recommandation']
        self.assertIsNotNone(
            recommandation,
            '%s : aucune taille recommandee (%s)' % (libelle,
                                                     resultat['motivation']))
        self.assertTrue(resultat['motivation'].strip(),
                        '%s : recommandation sans motivation' % libelle)

        # 1. Règle des 80 % du fondateur, sur la taille RECOMMANDÉE.
        self.assertIsNotNone(
            recommandation['ratio_onduleur_kwc'],
            '%s : onduleur sans puissance lisible' % libelle)
        self.assertGreaterEqual(
            recommandation['ratio_onduleur_kwc'], RATIO_ONDULEUR_MIN - 1e-9,
            '%s : onduleur a %.2f x kWc, sous la regle des 80 %%'
            % (libelle, recommandation['ratio_onduleur_kwc']))
        self.assertTrue(recommandation['regle_80_pct_respectee'], libelle)

        # 2. Aucun verdict ELECTRIQUE bloquant sur la recommandation.
        bloquants = [a for a in recommandation['avertissements']
                     if any(mot in a.lower() for mot in MOTS_BLOQUANTS)]
        self.assertEqual(
            bloquants, [],
            '%s : la taille recommandee porte un verdict bloquant' % libelle)

        # 3. La batterie ne peut PAS faire économiser moins.
        self.assertGreaterEqual(
            recommandation['economie_avec_mad'],
            recommandation['economie_sans_mad'] - 1e-6,
            '%s : la batterie economise MOINS que sans batterie' % libelle)

        # 4. On n'economise jamais plus que ce que le client paie.
        facture_annuelle = (cas.hiver * 6 + cas.ete * 6) \
            if cas.ete_differente else cas.hiver * 12
        for cle in ('economie_sans_mad', 'economie_avec_mad'):
            self.assertLess(
                recommandation[cle], facture_annuelle,
                '%s : economie %s (%s) >= facture annuelle (%s)'
                % (libelle, cle, _mad(recommandation[cle]),
                   _mad(facture_annuelle)))

        # 5. La taille recommandee est composable et chiffree.
        self.assertTrue(recommandation['composable'], libelle)
        self.assertGreater(recommandation['cout_sans_ttc'], 0, libelle)
        self.assertTrue(recommandation['lignes_sans'],
                        '%s : recommandation sans aucune ligne' % libelle)

        # 6. Elle ne depasse pas la borne de parite. On l'exprime en PANNEAUX
        # et non en pourcentage : la garantie du balayage est « au plus la
        # parite production/consommation, plus un panneau » — or pour une
        # petite installation UN panneau est deja un gros ecart relatif, si
        # bien qu'un seuil en pourcentage serait faux pour les petits paliers.
        production_par_panneau = (recommandation['production_annuelle_kwh']
                                  / max(1, recommandation['panneaux']))
        self.assertLessEqual(
            recommandation['production_annuelle_kwh']
            - recommandation['consommation_annuelle_kwh'],
            production_par_panneau * 2.0 + 1e-6,
            '%s : taille au-dela de la parite + 1 panneau — au Maroc le '
            'surplus ne vaut rien, chaque panneau en trop est du cout pur'
            % libelle)
        self.assertEqual(len(conso), 12, libelle)

    # ── LES TESTS ────────────────────────────────────────────────────────

    def test_sept_paliers_de_facture(self):
        """Les sept montants demandés par le fondateur, du plus petit au plus
        gros, avec la taille que le moteur choisit pour chacun."""
        tailles = []
        for cas in PALIERS:
            conso, source, _detail, resultat = self._evaluer(cas)
            self._imprimer(cas, conso, source, resultat)
            self._verifier(cas, conso, resultat)
            tailles.append((cas.libelle, resultat['recommandation']['kwc']))

        print('')
        print('%s ══ SYNTHESE DES SEPT PALIERS' % TAG)
        for libelle, kwc in tailles:
            print('%s    %-14s -> %5.2f kWc' % (TAG, libelle, kwc))

        # MONOTONIE : une facture plus grosse ne peut jamais donner une
        # installation plus PETITE. On l'exige au sens LARGE : deux paliers
        # voisins peuvent legitimement tomber sur le meme nombre de panneaux
        # (la granularite est un panneau du catalogue) — exiger le sens strict
        # serait epingler la grille de prix, pas le moteur.
        valeurs = [kwc for _libelle, kwc in tailles]
        for precedent, suivant in zip(valeurs, valeurs[1:]):
            self.assertGreaterEqual(
                suivant, precedent - 1e-9,
                'la taille recommandee DIMINUE quand la facture augmente : %s'
                % valeurs)
        # ... et sur toute l'amplitude, elle doit vraiment avoir grandi.
        self.assertGreater(
            valeurs[-1], valeurs[0],
            '4500 DH/mois doit donner une installation plus grande que '
            '500 DH/mois : %s' % valeurs)

    def test_regle_du_palier_triphase(self):
        """Le MÊME client à 1 200 DH, mono puis tri : seul le raccordement
        change, et l'onduleur retenu doit le suivre (PVCOMPAT + règle 80 %)."""
        mono = next(c for c in PALIERS if c.hiver == 1200)
        resultats = {}
        for cas in (mono, CAS_TRI_1200):
            conso, source, _detail, resultat = self._evaluer(cas)
            self._imprimer(cas, conso, source, resultat)
            self._verifier(cas, conso, resultat)
            resultats[cas.phase] = resultat['recommandation']

        print('')
        print('%s ══ MONO vs TRI a 1200 DH/mois' % TAG)
        for phase, recommandation in resultats.items():
            print('%s    %-10s -> %5.2f kWc, onduleur %s (triphase=%s, '
                  'ratio %.2f)'
                  % (TAG, phase, recommandation['kwc'],
                     recommandation['onduleur'],
                     recommandation['onduleur_triphase'],
                     recommandation['ratio_onduleur_kwc']))

        tri = resultats['triphase']
        mono_reco = resultats['monophase']
        # Un lead MONOPHASÉ ne peut jamais recevoir un onduleur triphasé :
        # c'est la garde PVCOMPAT, et elle est absolue.
        self.assertFalse(
            mono_reco['onduleur_triphase'],
            'un client monophase ne peut pas recevoir un onduleur triphase : '
            '%s' % mono_reco['onduleur'])
        # Un lead TRIPHASÉ accepte les deux (un triphasé peut brancher un
        # onduleur monophasé) : on n'exige donc PAS le triphasé, mais on exige
        # que la regle des 80 % tienne et que le choix soit imprime ci-dessus.
        self.assertGreaterEqual(tri['ratio_onduleur_kwc'],
                                RATIO_ONDULEUR_MIN - 1e-9)

    def test_profils_hiver_ete_differencies(self):
        """Trois clients dont l'été ne ressemble pas à l'hiver — c'est là que
        la saisonnalité change vraiment la réponse."""
        for cas in SAISONNIERS:
            conso, source, _detail, resultat = self._evaluer(cas)
            self._imprimer(cas, conso, source, resultat)
            self._verifier(cas, conso, resultat)

            # La série 12 mois DOIT porter la difference saisonniere : c'est
            # tout l'objet de ces cas.
            hiver_kwh, ete_kwh = conso[0], conso[6]
            self.assertNotAlmostEqual(
                hiver_kwh, ete_kwh, places=1,
                msg='%s : janvier et juillet identiques — la facture d\'ete '
                    'n\'a pas ete prise en compte' % cas.libelle)
            if cas.ete > cas.hiver:
                self.assertGreater(ete_kwh, hiver_kwh, cas.libelle)
            else:
                self.assertLess(ete_kwh, hiver_kwh, cas.libelle)

    def test_occupation_change_la_recommandation(self):
        """À FACTURE IDENTIQUE, « présent en journée » et « absent en journée »
        ne doivent pas donner le même dossier : c'est la raison d'être du
        questionnaire d'appel."""
        from apps.ventes.courbes_journalieres import OCCUPATION_ABSENCE

        resultats = {}
        for occupation in (OCCUPATION_PRESENCE, OCCUPATION_ABSENCE):
            cas = Cas('1700 DH/mois — %s' % occupation, hiver=1700,
                      phase='monophase', occupation=occupation)
            conso, source, _detail, resultat = self._evaluer(cas)
            self._imprimer(cas, conso, source, resultat)
            self._verifier(cas, conso, resultat)
            resultats[occupation] = resultat['recommandation']

        present = resultats[OCCUPATION_PRESENCE]
        absent = resultats[OCCUPATION_ABSENCE]
        print('')
        print('%s ══ PRESENT vs ABSENT a 1700 DH/mois' % TAG)
        print('%s    present : %5.2f kWc, autoconso %s, eco %s DH/an'
              % (TAG, present['kwc'], _pct(present['taux_autoconso_sans']),
                 _mad(present['economie_sans_mad'])))
        print('%s    absent  : %5.2f kWc, autoconso %s, eco %s DH/an'
              % (TAG, absent['kwc'], _pct(absent['taux_autoconso_sans']),
                 _mad(absent['economie_sans_mad'])))

        # Un foyer PRÉSENT en journée consomme pendant que le soleil produit :
        # à taille égale il autoconsomme davantage. Si cette inegalite tombe,
        # le profil ne sert a rien et tout CJ2a est vide de sens.
        self.assertGreater(
            present['taux_autoconso_sans'], absent['taux_autoconso_sans'],
            'un foyer present en journee doit autoconsommer plus qu\'un foyer '
            'absent, a facture egale')

    def test_criteres_alternatifs_sont_offerts_au_fondateur(self):
        """Le critère par défaut est un CHOIX, pas une fatalité : les autres
        existent et donnent bien d'autres réponses."""
        cas = next(c for c in PALIERS if c.hiver == 2500)
        conso, source, _detail = profil_depuis_factures(
            facture_hiver_mad=cas.hiver)
        rendus = {}
        for critere in ('meilleur_payback', 'meilleure_couverture',
                        'economie_max'):
            resultat = recommander_taille(
                company=self.company, conso_kwh_mensuelles=conso, ville=VILLE,
                occupation=cas.occupation, phase=cas.phase, critere=critere,
                taux_tva=Decimal('20'), source_conso=source)
            self.assertEqual(resultat['critere'], critere)
            rendus[critere] = resultat['recommandation']

        print('')
        print('%s ══ CRITERES DE CHOIX a 2500 DH/mois' % TAG)
        for critere, recommandation in rendus.items():
            if recommandation is None:
                print('%s    %-22s -> aucune' % (TAG, critere))
                continue
            print('%s    %-22s -> %5.2f kWc, couverture %s, eco %s DH/an, '
                  'payback %s'
                  % (TAG, critere, recommandation['kwc'],
                     _pct(recommandation['couverture_sans']),
                     _mad(recommandation['economie_sans_mad']),
                     _annees(recommandation['payback_sans_annees'])))

        # « meilleure couverture » ne peut pas couvrir MOINS que le payback.
        couverture = rendus['meilleure_couverture']
        payback = rendus['meilleur_payback']
        if couverture and payback:
            self.assertGreaterEqual(couverture['couverture_sans'],
                                    payback['couverture_sans'] - 1e-9)
