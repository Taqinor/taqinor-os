"""QJR48 — ``refresh_etude_consistency`` (QX24) est SUPPRIMÉE : elle payait un
``Devis.save`` et un recalcul complet d'``option_totaux`` à chaque ligne, pour
une clé que personne ne lit.

CE QUE CES TESTS TIENNENT.

1. **Le balayage d'absence de lecteur est REJOUÉ ici**, pas seulement joint au
   commit : si quelqu'un se met un jour à lire ``etude_params['payback_annees']``
   sans le rétablir côté écriture, ce test le dit tout de suite. Les autres
   ``payback_annees`` du dépôt (cartes ``offres_tailles``, paliers de
   ``dimensionnement``, comparateurs ``compta``/``parametres``, échantillons de
   contrat) appartiennent à des blocs qui portent leur PROPRE payback et le
   calculent eux-mêmes — ils ne lisent jamais celui d'``etude_params``.
2. **Une sauvegarde de ligne ne déclenche plus ni ``Devis.save`` ni
   ``option_totaux``.**
3. **Aucun chiffre rendu ne change** : la clé n'était consommée nulle part.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_coherence_etude -v 2
"""
import ast
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

#: Racine du projet Django (``backend/django_core``).
RACINE = Path(__file__).resolve().parents[3]

#: Les modules dont le ``payback_annees`` appartient à un AUTRE bloc (paliers,
#: cartes de taille, comparateurs) et qui ne lisent donc jamais celui
#: d'``etude_params``. Chacun est justifié — la liste n'est pas un fourre-tout.
LECTEURS_LEGITIMES = {
    # Les cartes des trois tailles portent LEUR payback (prix ÷ économie).
    'apps/ventes/offres_tailles.py',
    # Les paliers/combinaisons du balayage portent LEUR payback.
    'apps/ventes/dimensionnement.py',
    # QJR77 (30/08/2026) — MÊME payback de palier, NOUVEAU fichier. La
    # scission de `dimensionnement.py` a emporté la couche liée au devis,
    # dont `_echelle_paliers_batterie`, qui pose sa PROPRE clé
    # `payback_annees` (`prix_ttc / economies_annuelles`) dans le dict d'un
    # palier. Ce n'est toujours PAS une lecture d'``etude_params`` : le
    # déplacement n'a rien ajouté, il a changé le chemin d'un producteur
    # déjà déclaré ici. L'invariant de QJR48 est intact.
    'apps/ventes/domain/dimensionnement_devis.py',
    # Projection publique des PALIERS batterie (jamais d'``etude_params``).
    'apps/ventes/public_views.py',
    # Comparateurs de financement — un tout autre domaine.
    'apps/compta/services.py',
    'apps/parametres/tariff.py',
}

#: Les modules qui NOMMENT la clé sans jamais la LIRE (29/08/2026, vague M2).
#: Distincts des lecteurs ci-dessus, et volontairement : ce ne sont pas des
#: consommateurs, ce sont des DÉCLARATIONS — et chacune RENFORCE l'invariant
#: de QJR48 au lieu de l'affaiblir.
DECLARANTS_LEGITIMES = {
    # QJR61 — le SCHÉMA d'``etude_params`` déclare ``payback_annees`` avec le
    # propriétaire ``ORPHELINE`` (« personne ne l'écrit ») pour qu'un devis
    # ANCIEN qui la porte encore ne soit pas signalé comme invalide par
    # ``valider``. C'est une entrée de table, jamais une lecture.
    'apps/ventes/domain/etude_schema.py',
    # QJR58 — le registre de surcharges la liste dans ``CHAMPS_DERIVES``, sa
    # liste de REFUS : toute tentative de poser ce nombre par override est
    # rejetée en 400. Nommer la clé pour l'interdire, c'est l'inverse d'en
    # dépendre.
    'apps/ventes/domain/overrides.py',
}


def _fichiers_python():
    for chemin in RACINE.rglob('*.py'):
        relatif = chemin.relative_to(RACINE).as_posix()
        if '/tests' in relatif or relatif.startswith('tests'):
            continue
        if 'migrations/' in relatif:
            continue
        yield relatif, chemin


class AucunLecteurDeLaCleTests(TestCase):
    """Le balayage « grep d'absence de lecteur », rejoué à chaque CI."""

    def test_aucun_module_de_production_ne_lit_payback_annees_hors_liste(self):
        coupables = []
        for relatif, chemin in _fichiers_python():
            if relatif in LECTEURS_LEGITIMES | DECLARANTS_LEGITIMES:
                continue
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            # AST, pas un grep : un COMMENTAIRE de suppression (il y en a un
            # dans ``services.py`` et un dans ``receivers.py``) ne doit pas
            # passer pour un lecteur.
            for noeud in ast.walk(arbre):
                if (isinstance(noeud, ast.Constant)
                        and noeud.value == 'payback_annees'):
                    coupables.append(relatif)
                    break
        coupables = sorted(set(coupables))
        self.assertEqual(
            coupables, [],
            "QJR48 : ``etude_params['payback_annees']`` n'est plus écrit. "
            'Ces modules citent pourtant la clé sans figurer ni dans les '
            'lecteurs légitimes (qui portent leur PROPRE payback) ni dans les '
            'déclarants (schéma, liste de refus) : %s. Trois cas — ils lisent '
            "un AUTRE bloc (à déclarer dans LECTEURS_LEGITIMES), ils NOMMENT "
            'la clé sans la lire (DECLARANTS_LEGITIMES), ou ils attendent une '
            'clé que plus rien ne pose — et là il faut corriger le code, pas '
            'la liste.' % coupables)

    def test_le_service_et_ses_recepteurs_ont_bien_disparu(self):
        from apps.ventes import receivers, services
        self.assertFalse(hasattr(services, 'refresh_etude_consistency'))
        for nom in ('_qx24_refresh_etude_on_ligne_change',
                    '_qx24_refresh_etude_on_devis_change'):
            with self.subTest(nom=nom):
                self.assertFalse(hasattr(receivers, nom))

    def test_aucun_appelant_ne_subsiste(self):
        """AST, pas un grep textuel : un commentaire ne doit pas suffire à
        faire croire que le chemin existe encore."""
        restants = []
        for relatif, chemin in _fichiers_python():
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                cible = None
                if isinstance(noeud, ast.Call):
                    cible = noeud.func
                if isinstance(cible, ast.Attribute):
                    if cible.attr == 'refresh_etude_consistency':
                        restants.append(relatif)
                elif isinstance(cible, ast.Name):
                    if cible.id == 'refresh_etude_consistency':
                        restants.append(relatif)
        self.assertEqual(sorted(set(restants)), [])


class AucunCoutParLigneTests(TestCase):
    """Sauvegarder une ligne ne coûte plus ni ``Devis.save`` ni totaux."""

    def _devis(self, slug):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        client_obj = Client.objects.get_or_create(
            company=company, nom=f'Client {slug}', defaults={})[0]
        return Devis.objects.create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            client=client_obj, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel',
            # Le cas que QX24 visait : des économies stockées et une remise.
            remise_globale=Decimal('10'),
            etude_params={'economies_annuelles': 7000,
                          'production_annuelle': 8000})

    def test_sauvegarder_une_ligne_ne_sauvegarde_plus_le_devis(self):
        devis = self._devis('qjr48-cout')
        vrai_save = Devis.save
        appels = []

        def espion(self, *args, **kwargs):
            appels.append(list(kwargs.get('update_fields') or []))
            return vrai_save(self, *args, **kwargs)

        with mock.patch.object(Devis, 'save', espion):
            LigneDevis.objects.create(
                devis=devis, designation='Panneau 550 W',
                quantite=Decimal('9'), prix_unitaire=Decimal('1100'),
                remise=Decimal('0'))
        self.assertNotIn(['etude_params'], appels)
        self.assertEqual(appels, [])

    def test_sauvegarder_une_ligne_ne_recalcule_plus_option_totaux(self):
        devis = self._devis('qjr48-totaux')
        from apps.ventes.utils import options as module_options
        vrai = module_options.option_totaux
        appels = []

        def espion(*args, **kwargs):
            appels.append(1)
            return vrai(*args, **kwargs)

        with mock.patch.object(module_options, 'option_totaux', espion):
            LigneDevis.objects.create(
                devis=devis, designation='Onduleur hybride 5 kW',
                quantite=Decimal('1'), prix_unitaire=Decimal('14000'),
                remise=Decimal('0'))
        self.assertEqual(appels, [])

    def test_aucun_payback_annees_n_apparait_dans_etude_params(self):
        devis = self._devis('qjr48-cle')
        LigneDevis.objects.create(
            devis=devis, designation='Panneau 550 W',
            quantite=Decimal('9'), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'))
        devis.refresh_from_db()
        self.assertNotIn('payback_annees', devis.etude_params or {})
        # Et le reste d'``etude_params`` est INTACT : rien d'autre ne bouge.
        self.assertEqual(devis.etude_params,
                         {'economies_annuelles': 7000,
                          'production_annuelle': 8000})
