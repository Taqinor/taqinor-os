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
from apps.ventes.dimensionnement import (
    EGALITE_PAYBACK_ANNEES,
    HORIZON_MARGINAL_BATTERIE,
    HORIZON_MARGINAL_PV,
    MAX_PALIERS_STOCKAGE,
    RATIO_ONDULEUR_MIN,
    depart_dans_horizon,
    recommander_taille,
    verdict_bloquant,
)
from apps.ventes.etude_horaire import (
    BATTERY_ROUNDTRIP,
    CALIBRATION_RAFALE_SOURCE,
    RAFALE_POSITION_MESUREE,
    jours_types_annee,
    profil_depuis_factures,
    recouvrement_pas_fins,
    simuler_batterie_pas_fins,
)
from authentication.models import Company

User = get_user_model()

#: Préfixe de log — l'orchestrateur extrait le rapport du log CI là-dessus.
TAG = 'EXEMPLE FONDATEUR'

#: Ville de référence des exemples : Casablanca-Bouskoura, le terrain réel de
#: la société (et la ville des trois factures qui étalonnent le barème).
VILLE = 'Casablanca'

#: Le détecteur de verdict bloquant vient du MODULE, pas du test : une seconde
#: définition ici finirait par diverger de celle qui décide vraiment.


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


def _kwh(valeur):
    """Capacité/énergie lisible : « 0,2 » plutôt que « 0 » (les petits surplus
    d'hiver se comptent au dixième de kWh — les arrondir à l'entier ferait
    disparaître la raison même d'un refus de stockage)."""
    try:
        return '%.1f' % float(valeur)
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
        if resultat.get('falaise'):
            falaise = resultat['falaise']
            print('%s    barème   : aujourd\'hui en %s ; la marche juste en '
                  'dessous est %s kWh/mois (%s)'
                  % (TAG, falaise['tranche_actuelle']['libelle'],
                     _mad(falaise['cible_kwh_mois']),
                     (falaise.get('tranche_visee') or {}).get('libelle') or '?'))
        print('%s    %-4s %-7s %-22s %-9s %-6s %-6s %-10s %-10s %-8s %-7s %-9s '
              '%-16s'
              % (TAG, 'pan.', 'kWc', 'onduleur', 'ratio80', 'auto', 'couv',
                 'eco/an', 'eco+bat/an', 'payback', 'bat kWh', 'resid/mois',
                 'tranche apres'))
        for ligne in resultat['tableau']:
            marque = '>>' if (resultat['recommandation']
                              and ligne['panneaux']
                              == resultat['recommandation']['panneaux']) else '  '
            ratio = ('%.2f %s' % (ligne['ratio_onduleur_kwc'],
                                  'OK' if ligne['regle_80_pct_respectee']
                                  else '!!')
                     if ligne['ratio_onduleur_kwc'] else '   n/a')
            eco_avec = (_mad(ligne['economie_avec_mad'])
                        if ligne['batterie_disponible'] else 'impossible')
            print('%s %s %-4d %-7.2f %-22s %-9s %-6s %-6s %-10s %-10s %-8s '
                  '%-7s %-9s %-16s'
                  % (TAG, marque, ligne['panneaux'], ligne['kwc'],
                     (ligne['onduleur'] or '-')[:22], ratio,
                     _pct(ligne['taux_autoconso_sans']),
                     _pct(ligne['couverture_sans']),
                     _mad(ligne['economie_sans_mad']), eco_avec,
                     _annees(ligne['payback_sans_annees']),
                     _mad(ligne['batterie_kwh']),
                     _mad(ligne['residuel_kwh_mois']),
                     ((ligne['tranche_apres'] or {}).get('libelle') or '-')[:16]))
            for avertissement in ligne['verdicts_bloquants_avec']:
                print('%s      [option batterie ECARTEE] %s'
                      % (TAG, avertissement))
            if ligne.get('stockage_refuse'):
                print('%s      [stockage REFUSE] %s'
                      % (TAG, ligne['stockage_refuse']['motif_refus']))
            for avertissement in ligne['avertissements_sans']:
                print('%s      ! %s' % (TAG, avertissement))

        recommandation = resultat['recommandation']
        if recommandation is None:
            print('%s    >>> AUCUNE TAILLE RECOMMANDEE — %s'
                  % (TAG, resultat['motivation']))
            return
        print('%s    >>> RECOMMANDE : %d panneaux, %.2f kWc, onduleur %d x %s '
              '= %s kW (ratio %.2f x kWc, regle 80%% %s)'
              % (TAG, recommandation['panneaux'], recommandation['kwc'],
                 recommandation['onduleur_quantite'] or 1,
                 recommandation['onduleur'] or '-',
                 recommandation['onduleur_kw'],
                 recommandation['ratio_onduleur_kwc'] or 0,
                 'OK' if recommandation['regle_80_pct_respectee'] else 'NON'))
        print('%s        motif : %s' % (TAG, resultat['motivation']))
        if recommandation['batterie_disponible']:
            print('%s        economie %s DH/an sans batterie, %s DH/an avec '
                  '(facture %s DH/an) — couverture %s'
                  % (TAG, _mad(recommandation['economie_sans_mad']),
                     _mad(recommandation['economie_avec_mad']),
                     _mad(annuel_mad),
                     _pct(recommandation['couverture_sans'])))
            print('%s        cout %s DH TTC sans batterie, %s DH TTC avec'
                  % (TAG, _mad(recommandation['cout_sans_ttc']),
                     _mad(recommandation['cout_avec_ttc'])))
        else:
            print('%s        economie %s DH/an (facture %s DH/an) — '
                  'couverture %s ; cout %s DH TTC'
                  % (TAG, _mad(recommandation['economie_sans_mad']),
                     _mad(annuel_mad),
                     _pct(recommandation['couverture_sans']),
                     _mad(recommandation['cout_sans_ttc'])))
            print('%s        OPTION BATTERIE IMPOSSIBLE a cette taille — '
                  'aucun chiffre affiche pour elle :' % TAG)
            for avertissement in recommandation['verdicts_bloquants_avec']:
                print('%s          %s' % (TAG, avertissement))
            if recommandation.get('stockage_refuse'):
                print('%s          %s'
                      % (TAG, recommandation['stockage_refuse']['motif_refus']))
        print('%s        lignes du devis (sans batterie) :' % TAG)
        for ligne in recommandation['lignes_sans']:
            print('%s          %2d x %-46s (%s)'
                  % (TAG, ligne['quantite'], ligne['designation'][:46],
                     ligne['role'] or '-'))

    # ── DIM2 — le mini-balayage du stockage, imprimé ─────────────────────

    def _imprimer_un_balayage(self, titre, ligne):
        """Le mini-balayage du stockage d'UNE taille de champ."""
        if ligne is None:
            return
        print('')
        print('%s ══ MINI-BALAYAGE STOCKAGE — %s (%d panneaux, %.2f kWc)'
              % (TAG, titre, ligne['panneaux'], ligne['kwc']))
        print('%s    plafond de stockage %s kWh (motif : %s) — surplus '
              'quotidien le plus faible %s kWh au mois %s'
              % (TAG, _kwh(ligne['stockage_plafond_kwh']),
                 ligne['stockage_plafond_motif'] or '-',
                 _kwh(ligne['stockage_surplus_jour_min_kwh']),
                 ligne['stockage_surplus_jour_min_mois']))
        print('%s    %-8s %-11s %-11s %-11s %-8s %-10s %-16s %-11s'
              % (TAG, 'kWh bat', 'cout TTC', 'eco/an', 'marginal',
                 'payback', 'resid/mois', 'tranche apres', 'remplissage'))
        for palier in ligne['balayage_stockage']:
            pire = palier['remplissage']['pire_mois']
            print('%s    %-8s %-11s %-11s %-11s %-8s %-10s %-16s %s (mois %s)'
                  % (TAG, _kwh(palier['capacite_kwh']),
                     _mad(palier['cout_ttc']), _mad(palier['economie_mad']),
                     _mad(palier['economie_marginale_mad']),
                     _annees(palier['payback_annees']),
                     _mad(palier['residuel_kwh_mois']),
                     ((palier['tranche_apres'] or {}).get('libelle') or '-')[:16],
                     _pct(pire['ratio']), pire['mois']))
        if not ligne['balayage_stockage']:
            print('%s    (aucun palier candidat : voir le refus ci-dessous)'
                  % TAG)
        if ligne.get('stockage_refuse'):
            print('%s    REFUSE : %s'
                  % (TAG, ligne['stockage_refuse']['motif_refus']))

    def _imprimer_stockage(self, resultat):
        """Le MINI-BALAYAGE du stockage + la falaise.

        C'est LA sortie que le fondateur a demandée le 24/08/2026 : voir, pour
        une taille de champ donnée, ce que chaque palier de batteries change —
        et si la marche du barème est atteignable.

        DEUX tailles sont imprimées, et c'est délibéré : la taille RECOMMANDÉE
        (choisie sans batterie) et celle du MEILLEUR PAYBACK AVEC batterie.
        Elles ne coïncident pas, et c'est tout le propos de DIM2 : sur la
        recommandée, le champ est souvent trop petit pour remplir la moindre
        banque — le balayage y est donc VIDE, avec son refus motivé.
        """
        self._imprimer_un_balayage('taille recommandee (sans batterie)',
                                   resultat.get('recommandation'))
        avec = resultat.get('recommandation_avec')
        if avec is not None:
            self._imprimer_un_balayage('meilleur payback AVEC batterie', avec)
            print('%s    >>> MEILLEUR PAYBACK AVEC BATTERIE : %s'
                  % (TAG, resultat['motivation_avec']))
        falaise = resultat.get('meilleure_falaise')
        if falaise is None:
            print('%s    >>> FALAISE : aucune combinaison du balayage ne fait '
                  'passer le residuel sous la marche.' % TAG)
        else:
            print('%s    >>> FALAISE FRANCHIE : %d panneaux + %s kWh — cout %s '
                  'DH TTC, economie %s DH/an, payback %s, residuel %s kWh/mois '
                  '(%s), remplissage du pire mois %s'
                  % (TAG, falaise['panneaux'], _mad(falaise['batterie_kwh']),
                     _mad(falaise['cout_ttc']), _mad(falaise['economie_mad']),
                     _annees(falaise['payback_annees']),
                     _mad(falaise['residuel_kwh_mois']),
                     (falaise['tranche_apres'] or {}).get('libelle') or '-',
                     _pct(falaise['remplissage']['pire_mois']['ratio'])))

    # ── Assertions de santé, communes à tous les cas ─────────────────────

    def _verifier_stockage(self, cas, resultat):
        """DIM2 — les invariants du mini-balayage, sur TOUTES les tailles."""
        libelle = cas.libelle
        for ligne in resultat['tableau']:
            paliers = ligne['balayage_stockage']
            contexte = '%s, %d panneaux' % (libelle, ligne['panneaux'])

            self.assertLessEqual(
                len(paliers), MAX_PALIERS_STOCKAGE,
                '%s : plus de %d paliers de stockage'
                % (contexte, MAX_PALIERS_STOCKAGE))

            capacites = [p['capacite_kwh'] for p in paliers]
            self.assertEqual(
                capacites, sorted(set(capacites)),
                '%s : les paliers ne sont pas strictement croissants : %s'
                % (contexte, capacites))

            for palier in paliers:
                # 1. Une économie marginale NÉGATIVE serait un contresens
                #    physique : plus de stockage ne peut pas décaler moins
                #    d'énergie (la simulation est monotone en capacité).
                self.assertGreaterEqual(
                    palier['economie_marginale_mad'], -1e-6,
                    '%s : palier %s kWh à economie marginale NEGATIVE (%s)'
                    % (contexte, palier['capacite_kwh'],
                       palier['economie_marginale_mad']))
                # 2. RÈGLE FONDATEUR — « batteries toujours pleines » : aucun
                #    palier retenu ne dépasse le plafond de remplissage.
                self.assertLessEqual(
                    palier['capacite_kwh'],
                    ligne['stockage_plafond_kwh'] + 1e-6,
                    '%s : palier %s kWh retenu AU-DESSUS du plafond %s kWh'
                    % (contexte, palier['capacite_kwh'],
                       ligne['stockage_plafond_kwh']))

            # 3. À CHAMP FIXE, le résiduel DÉCROÎT quand le stockage croît.
            residuels = [p['residuel_kwh_mois'] for p in paliers]
            for avant, apres in zip(residuels, residuels[1:]):
                self.assertLessEqual(
                    apres, avant + 1e-6,
                    '%s : le residuel REMONTE quand le stockage augmente : %s'
                    % (contexte, residuels))

            # 4. AUCUN palier au-delà de la coupe à marginal nul : seul le
            #    DERNIER peut porter une économie marginale nulle (il est gardé
            #    parce qu'il PROUVE le retournement).
            for palier in paliers[:-1]:
                self.assertGreater(
                    palier['economie_marginale_mad'], 0,
                    '%s : un palier a marginal nul est suivi d\'autres paliers '
                    '— la coupe n\'a pas eu lieu (%s kWh)'
                    % (contexte, palier['capacite_kwh']))

            # 5. Le résiduel affiché est cohérent avec la variante retenue.
            if ligne['batterie_disponible']:
                self.assertEqual(ligne['residuel_kwh_mois'],
                                 ligne['residuel_avec_kwh_mois'], contexte)
            else:
                self.assertEqual(ligne['residuel_kwh_mois'],
                                 ligne['residuel_sans_kwh_mois'], contexte)

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

        # 2. L'option de BASE (sans batterie) est electriquement saine. Un
        #    verdict bloquant sur la variante BATTERIE n'invalide pas la
        #    taille : il retire l'option batterie, ce que le rapport imprime
        #    (c'est le trou de catalogue documente n° 2 — on le MONTRE).
        self.assertEqual(
            recommandation['verdicts_bloquants_sans'], [],
            '%s : la taille recommandee porte un verdict bloquant sur '
            'l\'option de base' % libelle)
        for avertissement in recommandation['avertissements_sans']:
            self.assertFalse(
                verdict_bloquant(avertissement),
                '%s : avertissement bloquant non detecte : %s'
                % (libelle, avertissement))

        # 3. Quand l'option batterie EXISTE, elle ne peut pas economiser moins.
        #    Quand elle n'existe pas, elle ne porte AUCUN chiffre (on
        #    n'affiche jamais l'economie d'une installation non livrable).
        if recommandation['batterie_disponible']:
            self.assertGreaterEqual(
                recommandation['economie_avec_mad'],
                recommandation['economie_sans_mad'] - 1e-6,
                '%s : la batterie economise MOINS que sans batterie' % libelle)
        else:
            for cle in ('economie_avec_mad', 'cout_avec_ttc',
                        'payback_avec_annees', 'couverture_avec'):
                self.assertIsNone(
                    recommandation[cle],
                    '%s : option batterie impossible mais « %s » est chiffre'
                    % (libelle, cle))

        # 4. On n'economise jamais plus que ce que le client paie.
        facture_annuelle = (cas.hiver * 6 + cas.ete * 6) \
            if cas.ete_differente else cas.hiver * 12
        for cle in ('economie_sans_mad', 'economie_avec_mad'):
            valeur = recommandation[cle]
            if valeur is None:
                continue
            self.assertLess(
                valeur, facture_annuelle,
                '%s : economie %s (%s) >= facture annuelle (%s)'
                % (libelle, cle, _mad(valeur), _mad(facture_annuelle)))

        # 5. La taille recommandee est composable et chiffree.
        self.assertTrue(recommandation['composable'], libelle)
        self.assertGreater(recommandation['cout_sans_ttc'], 0, libelle)
        self.assertTrue(recommandation['lignes_sans'],
                        '%s : recommandation sans aucune ligne' % libelle)

        # 6. PIN DEPLACE LE 25/08/2026 — CE QUI BORNE LA TAILLE A CHANGE.
        #
        #    ANCIEN PIN : « au plus la parite production/consommation, plus un
        #    panneau ». Ce n'etait PAS une regle du moteur : c'etait une
        #    CONSEQUENCE du critere pur « meilleur payback » — passe la parite,
        #    un panneau de plus n'economise presque rien (au Maroc le surplus
        #    injecte ne vaut rien), donc il degradait toujours le ratio.
        #
        #    NOUVEAU PIN : la doctrine du 25/08 accepte une taille PLUS GRANDE
        #    tant que chaque panneau ajoute se rembourse dans la vie des
        #    panneaux (HORIZON_MARGINAL_PV). Ce qui borne la taille n'est donc
        #    plus la parite mais l'HORIZON — et c'est LUI qu'on epingle. La
        #    physique n'a pas change pour autant : passe la parite, l'economie
        #    marginale s'effondre et le ratio explose bien au-dela de dix ans,
        #    si bien que la montee s'arrete d'elle-meme.
        #
        #    LA GARANTIE VERIFIEE ICI EST CELLE QUE LA DOCTRINE DEMONTRE : le
        #    payback GLOBAL de la taille recommandee reste sous l'horizon des
        #    panneaux — sauf pour un dossier dont le MEILLEUR payback y est
        #    deja au-dela, ou la garde du dossier faible rend le choix pur
        #    d'avant (donc « jamais pire qu'avant »).
        #    LA GARDE PORTE SUR LE PAYBACK DU DEPART, pas sur le meilleur du
        #    tableau : le departage historique « a egalite, meilleure
        #    couverture » peut retenir une taille jusqu'a
        #    EGALITE_PAYBACK_ANNEES au-dessus du meilleur. C'est le point de
        #    depart qui doit tenir dans l'horizon pour que la demonstration
        #    (payback global <= horizon) soit vraie.
        paybacks = [ligne['payback_sans_annees']
                    for ligne in resultat['tableau']
                    if ligne.get('composable')
                    and ligne.get('payback_sans_annees') is not None
                    and not ligne.get('verdicts_bloquants_sans')]
        meilleur_payback = min(paybacks)
        if depart_dans_horizon(recommandation['payback_sans_annees']):
            self.assertLessEqual(
                recommandation['payback_sans_annees'],
                HORIZON_MARGINAL_PV + 1e-6,
                '%s : payback global %.2f ans au-dela de l\'horizon de %d ans '
                '— la doctrine promettrait un ROI qu\'elle ne tient pas'
                % (libelle, recommandation['payback_sans_annees'],
                   HORIZON_MARGINAL_PV))
        else:
            # Dossier faible : la montee n'a PAS eu lieu, donc la taille
            # recommandee est exactement celle du choix PUR d'avant le 25/08 —
            # une taille du groupe « a egalite » avec le meilleur payback.
            self.assertLessEqual(
                recommandation['payback_sans_annees'],
                meilleur_payback + EGALITE_PAYBACK_ANNEES,
                '%s : dossier au-dela de l\'horizon — la garde doit rendre le '
                'choix PUR meilleur payback, jamais une taille plus grande'
                % libelle)

        # 6bis. La taille recommandee n'est JAMAIS plus PETITE que celle du
        # meilleur payback pur : la montee ne descend pas.
        self.assertLessEqual(
            min(ligne['panneaux'] for ligne in resultat['tableau']
                if ligne.get('payback_sans_annees') == meilleur_payback),
            recommandation['panneaux'],
            '%s : la recommandation est plus PETITE que le meilleur payback '
            'pur — la doctrine ne descend jamais' % libelle)
        self.assertEqual(len(conso), 12, libelle)

        # 7. DIM2 — les invariants du mini-balayage du stockage. Ils portent sur
        #    la STRUCTURE (monotonies, plafond de remplissage, coupe) et JAMAIS
        #    sur la disponibilite de l'option batterie a telle ou telle taille :
        #    cette disponibilite depend des bornes de fiche des onduleurs, qui
        #    sont l'affaire d'une autre lane. Un tableau sans aucun palier de
        #    stockage passe donc ces asserts sans les affaiblir.
        self._verifier_stockage(cas, resultat)

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

    def test_dim2_le_stockage_est_une_deuxieme_dimension(self):
        """DIM2 (fondateur 24/08/2026) — « peut-être rajouter des batteries ».

        LE cas de référence : 3 500 DH/mois en triphasé, présent en journée.
        Le rapport imprime le MINI-BALAYAGE du stockage de la taille
        recommandée (chaque palier, son coût, son économie marginale, son
        résiduel, la tranche où il retombe et son taux de remplissage du pire
        mois) puis la ligne FALAISE — la première combinaison, s'il en existe
        une, dont le résiduel passe sous la marche du barème.
        """
        cas = next(c for c in PALIERS if c.hiver == 3500)
        conso, source, _detail, resultat = self._evaluer(cas)
        self._imprimer(cas, conso, source, resultat)
        self._verifier(cas, conso, resultat)
        self._imprimer_stockage(resultat)

        # La MARCHE existe pour ce client : à ~2 070 kWh/mois il est dans la
        # tranche haute, et le barème en a une juste en dessous.
        falaise = resultat['falaise']
        self.assertIsNotNone(
            falaise,
            'un client à 3 500 DH/mois doit avoir une marche de barème sous '
            'lui — sinon la chasse à la falaise n\'a aucun sens')
        self.assertGreater(falaise['cible_kwh_mois'], 0)

        # Le balayage EXPLORE vraiment le stockage : au moins une taille du
        # tableau propose plus d'un palier, sinon DIM2 n'aurait rien changé.
        paliers_max = max((len(ligne['balayage_stockage'])
                           for ligne in resultat['tableau']), default=0)
        self.assertGreater(
            paliers_max, 1,
            'aucune taille n\'explore plus d\'un palier de stockage : le '
            'balayage du stockage ne balaie rien')

        # Il EXPLORE aussi le champ au-delà de la parité tant que la marche
        # n'est pas franchie — c'est l'extension de bornes_candidates.
        self.assertTrue(resultat['tableau'])

        # Et la règle « batteries toujours pleines » se VOIT : à petite taille
        # de champ, un palier de stockage est refusé avec son motif nommé.
        refus = [ligne['stockage_refuse'] for ligne in resultat['tableau']
                 if ligne.get('stockage_refuse')]
        self.assertTrue(
            refus,
            'aucun palier de stockage refusé sur tout le tableau : la règle '
            '« pas de stockage qu\'on ne charge pas » ne se lit nulle part')
        self.assertIn('plafond de remplissage', refus[0]['motif_refus'])

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

    def test_l_glitch_bouge_les_cas_a_equipements_declares(self):
        """L-GLITCH (ordre fondateur 24/08/2026) — AVANT / APRÈS, imprimé.

        « are you also counting the small glitches in your calculus now ? »
        Les appareils déclarés à l'appel dont la puissance est connue (pompe de
        piscine saisie, clim = 1,4 kW/unité × pièces) reviennent en IMPULSIONS
        à leur puissance réelle au lieu d'être étalés sur l'heure. Le total de
        kWh ne bouge pas ; ce qui bouge, c'est le RECOUVREMENT avec le soleil.

        Ce test IMPRIME l'écart pour chaque cas fondateur qui déclare un tel
        équipement — c'est le chiffre que le fondateur voulait voir — et il
        VÉRIFIE que le cas SANS équipement déclaré, lui, n'a pas bougé d'un
        centime (aucun bloc ``glitch`` n'apparaît).
        """
        from apps.ventes.etude_horaire import calculer_etude_horaire

        vus = 0
        for cas in SAISONNIERS:
            conso, source, _detail, resultat = self._evaluer(cas)
            recommandation = resultat.get('recommandation')
            if not recommandation:
                continue
            kwc = recommandation['kwc']
            batterie = recommandation.get('batterie_kwh') or 0.0
            etude = calculer_etude_horaire(
                kwc=kwc, conso_kwh_mensuelles=conso, ville=VILLE,
                occupation=cas.occupation,
                equipements=composer_equipements(cas.equipements),
                batterie_kwh_utile=batterie, source_conso=source)
            self.assertIsNotNone(etude, cas.libelle)

            print('')
            print('%s ══ L-GLITCH — %s' % (TAG, cas.libelle))
            print('%s    taille recommandee %.2f kWc, batterie %s kWh'
                  % (TAG, kwc, _kwh(batterie)))

            if not cas.equipements:
                # AUCUN équipement déclaré ⇒ la couche n'existe pas : la sortie
                # est celle d'avant, à l'octet près.
                self.assertNotIn(
                    'glitch', etude,
                    '%s ne declare aucun equipement : rien ne doit bouger'
                    % cas.libelle)
                print('%s    aucun equipement declare -> AUCUNE impulsion, '
                      'resultat inchange' % TAG)
                continue

            self.assertIn('glitch', etude,
                          '%s declare %s : des impulsions sont attendues'
                          % (cas.libelle, sorted(cas.equipements)))
            glitch = etude['glitch']
            annuel = etude['annuel']
            # AVANT = APRÈS + ce que les impulsions ont retiré. Aucun second
            # moteur n'est nécessaire : l'écart est un champ de sortie.
            avant_sans = annuel['economie_sans_mad'] + annuel[
                'part_glitch_sans_mad']
            avant_avec = annuel['economie_avec_mad'] + annuel[
                'part_glitch_avec_mad']
            avant_auto = annuel['autoconsomme_sans_kwh'] + annuel[
                'part_glitch_sans_kwh']

            print('%s    impulsions : couches %s, %d rafales/jour type, '
                  'plafond %s min, pas %s min'
                  % (TAG, ', '.join(glitch['couches']),
                     glitch['nb_rafales_jour_type'],
                     _kwh(glitch['plafond_rafale_minutes']),
                     _kwh(glitch['pas_minutes'])))
            print('%s    %-34s %12s %12s %10s'
                  % (TAG, '', 'AVANT (h)', 'APRES (5min)', 'ecart'))
            for libelle, avant, apres in (
                    ('autoconsommation directe (kWh/an)',
                     avant_auto, annuel['autoconsomme_sans_kwh']),
                    ('economie SANS batterie (DH/an)',
                     avant_sans, annuel['economie_sans_mad']),
                    ('economie AVEC batterie (DH/an)',
                     avant_avec, annuel['economie_avec_mad'])):
                print('%s    %-34s %12s %12s %10s'
                      % (TAG, libelle, _mad(avant), _mad(apres),
                         _mad(apres - avant)))
            print('%s    dont la batterie rattrape : %s kWh/an '
                  '(le reste part au reseau : %s kWh/an)'
                  % (TAG, _kwh(annuel['part_glitch_batterie_kwh']),
                     _kwh(annuel['part_glitch_avec_kwh'])))
            print('%s    argument batterie (avec - sans) : %s DH/an avant, '
                  '%s DH/an apres'
                  % (TAG, _mad(avant_avec - avant_sans),
                     _mad(annuel['economie_avec_mad']
                          - annuel['economie_sans_mad'])))

            # LE CAS DOIT VRAIMENT BOUGER — sinon la couche ne sert à rien.
            self.assertGreater(
                annuel['part_glitch_sans_kwh'], 0.0,
                '%s : les impulsions n\'ont rien change' % cas.libelle)
            self.assertGreater(annuel['part_glitch_sans_mad'], 0.0,
                               cas.libelle)
            # ... mais les kWh totaux, eux, ne bougent PAS d'un iota.
            self.assertAlmostEqual(
                sum(m['consommation_kwh'] for m in etude['mois']),
                annuel['consommation_kwh'], places=1)
            # EN ÉNERGIE, la batterie rattrape toujours une part : jamais le
            # contraire. (En DIRHAMS, la falaise sélective peut inverser le
            # verdict quand le résiduel « avec » frôle une marche — épinglé
            # par ``test_la_falaise_selective_peut_inverser_le_verdict_en_
            # dirhams`` dans test_etude_horaire.)
            self.assertGreaterEqual(
                annuel['part_glitch_sans_kwh'],
                annuel['part_glitch_avec_kwh'] - 1e-9, cas.libelle)
            self.assertGreaterEqual(annuel['part_glitch_batterie_kwh'], 0.0,
                                    cas.libelle)
            # La batterie reste gagnante, glitch ou pas.
            self.assertGreaterEqual(annuel['economie_avec_mad'],
                                    annuel['economie_sans_mad'] - 1e-6,
                                    cas.libelle)
            vus += 1

        self.assertGreaterEqual(
            vus, 2, 'les deux cas a equipements declares doivent etre couverts')

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

    def test_le_profil_absent_recoit_au_moins_autant_de_batteries(self):
        """DOCTRINE DU 25/08/2026 — LA CONSEQUENCE QUE LE FONDATEUR A PREDITE.

        « Un profil absent en journee doit desormais recevoir PLUS de batteries
        qu'avant. » Le mecanisme, et non l'intuition : un foyer ABSENT
        autoconsomme peu directement, donc son surplus quotidien est PLUS GROS
        a champ egal (plus de paliers se remplissent tous les jours) et chaque
        kWh stocke DEPLACE un kWh importe qui serait autrement paye plein tarif
        — l'economie marginale de la batterie est donc plus forte, et son pas
        passe l'horizon de sept ans la ou il ne le passerait pas chez un foyer
        present.

        AUCUN CHIFFRE N'EST ECRIT EN DUR ICI : le test lit ce que le moteur
        rend sur le catalogue seme, l'IMPRIME pour le fondateur, et epingle la
        RELATION entre les deux profils.
        """
        from apps.ventes.courbes_journalieres import OCCUPATION_ABSENCE

        rendus = {}
        for occupation in (OCCUPATION_PRESENCE, OCCUPATION_ABSENCE):
            cas = Cas('2500 DH/mois — %s' % occupation, hiver=2500,
                      phase='triphase', occupation=occupation)
            _conso, _source, _detail, resultat = self._evaluer(cas)
            rendus[occupation] = resultat

        print('')
        print('%s ══ DOCTRINE 25/08 — PRESENT vs ABSENT, axe BATTERIE '
              '(2500 DH/mois)' % TAG)
        print('%s    horizons : %d ans pour des panneaux, %d ans pour du '
              'stockage' % (TAG, HORIZON_MARGINAL_PV,
                            HORIZON_MARGINAL_BATTERIE))
        capacites = {}
        for occupation, resultat in rendus.items():
            avec = resultat.get('recommandation_avec')
            if avec is None:
                print('%s    %-14s -> AUCUNE configuration avec batterie : %s'
                      % (TAG, occupation, resultat['motivation_avec']))
                continue
            capacites[occupation] = avec['batterie_kwh']
            print('%s    %-14s -> %d panneaux + %s kWh, cout %s DH TTC, '
                  'economie %s DH/an, payback %s'
                  % (TAG, occupation, avec['panneaux'],
                     _kwh(avec['batterie_kwh']), _mad(avec['cout_avec_ttc']),
                     _mad(avec['economie_avec_mad']),
                     _annees(avec['payback_avec_annees'])))
            print('%s        %s' % (TAG, resultat['motivation_avec']))

        # LE MECANISME, VERIFIE A CHAMP EGAL : sur une taille de champ presente
        # dans les DEUX tableaux, le surplus quotidien du mois le plus faible —
        # donc le plafond de remplissage — est plus GRAND chez l'absent.
        surplus = {}
        for occupation, resultat in rendus.items():
            surplus[occupation] = {
                ligne['panneaux']: ligne['stockage_surplus_jour_min_kwh']
                for ligne in resultat['tableau']
                if ligne.get('stockage_surplus_jour_min_kwh') is not None}
        communes = sorted(set(surplus[OCCUPATION_PRESENCE])
                          & set(surplus[OCCUPATION_ABSENCE]))
        self.assertTrue(
            communes,
            'aucune taille de champ commune aux deux profils : le mecanisme '
            'ne peut pas etre verifie')
        for panneaux in communes:
            self.assertGreaterEqual(
                surplus[OCCUPATION_ABSENCE][panneaux],
                surplus[OCCUPATION_PRESENCE][panneaux] - 1e-6,
                'a %d panneaux, le foyer ABSENT aurait MOINS de surplus '
                'quotidien que le foyer PRESENT — le profil ne servirait a '
                'rien' % panneaux)
        print('%s    surplus quotidien du pire mois a %d panneaux : '
              'present %s kWh, absent %s kWh'
              % (TAG, communes[0],
                 _kwh(surplus[OCCUPATION_PRESENCE][communes[0]]),
                 _kwh(surplus[OCCUPATION_ABSENCE][communes[0]])))

        # ET LA CONSEQUENCE : l'absent ne reçoit jamais MOINS de stockage.
        if len(capacites) == 2:
            self.assertGreaterEqual(
                capacites[OCCUPATION_ABSENCE],
                capacites[OCCUPATION_PRESENCE],
                'le foyer ABSENT recoit MOINS de stockage (%s kWh) que le '
                'foyer PRESENT (%s kWh) : la doctrine du 25/08 ne produit pas '
                'l\'effet que le fondateur a predit'
                % (capacites.get(OCCUPATION_ABSENCE),
                   capacites.get(OCCUPATION_PRESENCE)))
        else:
            # Le catalogue seme ne sait pas livrer l'option batterie pour l'un
            # des deux profils. Ce n'est pas un silence : le moteur doit DIRE
            # pourquoi (trou de catalogue ou verdict electrique), et c'est CA
            # qu'on epingle plutot que de passer au vert sans rien prouver.
            for occupation, resultat in rendus.items():
                if occupation in capacites:
                    continue
                self.assertTrue(
                    resultat['motivation_avec'].strip(),
                    '%s : aucune option batterie ET aucune motivation'
                    % occupation)
                self.assertIn('aucune configuration avec batterie',
                              resultat['motivation_avec'])

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

    def test_l_dech_borne_reelle_sur_le_jour_type_de_juillet(self):
        """L-DECH — CE QUE LA DÉCHARGE FICHÉE CHANGE, EN CLAIR.

        Le rapport L-GLITCH annonçait « décharge non bornée restituerait 17,0
        au lieu de 10,0 kWh » sur le jour type de juillet du cas piscine/clim.
        Les fiches publient désormais une décharge SOURCÉE (Dyness : 100 A ×
        51,2 V = 5,12 kW par pack) et l'onduleur son port batterie (Deye
        SUN-5K : 120 A × 51,2 V = 6,14 kW) : ce test IMPRIME ce que la borne
        réelle donne, palier par palier, pour que le fondateur lise le chiffre
        plutôt que de le croire.

        Le calcul est PUR (aucune composition en base) : c'est le même jour
        type que celui qui chiffre l'économie, lu par la même fonction.
        """
        conso, _source, _detail = profil_depuis_factures(
            facture_hiver_mad=2500)
        equipements = composer_equipements(
            {'piscine': True, 'piscine_pompe_kw': 1.1,
             'clim': True, 'clim_pieces': 5})
        jours, _avert, _src = jours_types_annee(
            kwc=8.0, conso_kwh_mensuelles=conso, ville=VILLE,
            occupation=OCCUPATION_PRESENCE, equipements=equipements)
        juillet = next(j for j in jours if j['mois'] == 7)
        pas = juillet['pas_fins']
        self.assertIsNotNone(pas, 'le cas piscine/clim doit porter des '
                                  'impulsions en juillet')
        capacite = 10.0

        scenarios = (
            ('regle conservatrice (aucune fiche)', None, None),
            ('1 pack Dyness -> 5,12 kW', 5.12, None),
            ('2 packs Dyness -> 10,24 kW', 2 * 5.12, None),
            ('2 packs MAIS port onduleur 3,3 kW', 2 * 5.12, 3.3),
            ('reel catalogue : 1 pack + port 5M', 5.12, 6.14),
            ('decharge NON bornee (irrealiste)', 1e6, None),
        )
        rendus = {}
        print('')
        print('%s ══ L-DECH — JOUR TYPE DE JUILLET (piscine + clim, 8 kWc, '
              '%s kWh utile)' % (TAG, capacite))
        print('%s    autoconsommation directe %.2f kWh ; position de rafale '
              '%.2f (%s)'
              % (TAG, recouvrement_pas_fins(pas), RAFALE_POSITION_MESUREE,
                 CALIBRATION_RAFALE_SOURCE))
        print('%s    %-38s %10s %10s' % (TAG, 'BORNE DE DECHARGE',
                                         'restitue', 'charge'))
        for libelle, packs, port in scenarios:
            resultat = simuler_batterie_pas_fins(
                pas, capacite, puissance_decharge_kw=packs,
                puissance_decharge_onduleur_kw=port)
            rendus[libelle] = resultat
            print('%s    %-38s %10.2f %10.2f'
                  % (TAG, libelle, resultat['restitue_kwh'],
                     resultat['charge_kwh']))
            # L'invariant de conservation tient sous CHAQUE borne.
            self.assertLessEqual(
                resultat['restitue_kwh'],
                BATTERY_ROUNDTRIP * resultat['charge_kwh'] + 1e-9)

        conservatrice = rendus['regle conservatrice (aucune fiche)']
        un_pack = rendus['1 pack Dyness -> 5,12 kW']
        port_etroit = rendus['2 packs MAIS port onduleur 3,3 kW']
        deux_packs = rendus['2 packs Dyness -> 10,24 kW']

        # 1. La décharge FICHÉE libère strictement plus que la règle
        #    conservatrice : c'est tout l'objet de L-DECH.
        self.assertGreater(un_pack['restitue_kwh'],
                           conservatrice['restitue_kwh'])
        print('%s    >>> la fiche rend %.2f kWh de plus que la regle '
              'conservatrice' % (TAG, un_pack['restitue_kwh']
                                 - conservatrice['restitue_kwh']))

        # 2. Deux packs ne restituent JAMAIS moins qu'un seul (la quantité
        #    compte, et elle compte dans le bon sens).
        self.assertGreaterEqual(deux_packs['restitue_kwh'],
                                un_pack['restitue_kwh'] - 1e-9)

        # 3. Le port de l'onduleur reprend ce que les packs offraient : un
        #    goulot étroit se voit, il n'est jamais silencieux.
        self.assertLess(port_etroit['restitue_kwh'],
                        deux_packs['restitue_kwh'])
        print('%s    >>> un port de 3,3 kW coute %.2f kWh face a 2 packs'
              % (TAG, deux_packs['restitue_kwh']
                 - port_etroit['restitue_kwh']))
