"""ACAL63 (C-ACAL-042) — DRY-RUN : les devis NON brouillon dont la ligne
panneau changerait de produit ou serait scindée par « une ligne par modèle ».

Le devis vend désormais le module DÉSIGNÉ par le calepinage
(``modules[].produitId``), une ligne panneau par modèle. Les lignes d'un devis
ne bougent qu'au prochain geste (génération / resynchronisation) : cette
commande liste, AVANT le merge, les devis non brouillon concernés —
référence / statut / panneaux avant (produit × quantité) → après / total TTC
avant → après (ESTIMÉ : écart de quantités × prix catalogue × TVA du devis) —
pour la décision du fondateur.

LECTURE SEULE. ``--dry-run`` est le défaut ET le seul mode : aucun devis
(et surtout aucun devis envoyé) n'est jamais réécrit ici.

    python manage.py acal_dryrun_ligne_par_modele [--company <slug>] [--tous]
"""
from decimal import Decimal

from django.core.management.base import BaseCommand


def projection(devis):
    """``(avant, apres, delta_ht)`` — ``{produit_id: (nom, qte)}`` des lignes
    panneau actuelles et attendues, ou ``None`` si rien ne change."""
    from apps.ventes.domain.catalogue import _is_panel
    from apps.ventes.domain.geometrie import _produit_designe, modeles_designes
    from apps.ventes.domain.lignes import _classe_ligne

    modeles = modeles_designes(devis.roof_layout)
    if not modeles:
        return None
    avant = {}
    for ligne in devis.lignes.all():
        if not _classe_ligne(ligne, _is_panel):
            continue
        nom, qte = avant.get(ligne.produit_id, (ligne.designation, 0))
        avant[ligne.produit_id] = (nom, qte + int(ligne.quantite or 0))
    apres = {}
    prix = {}
    for modele in modeles:
        produit = (_produit_designe(devis.company, modele.get('produit_id'))
                   if modele.get('produit_id') else None)
        cle = getattr(produit, 'pk', None) or modele.get('produit_id')
        nom = getattr(produit, 'nom', '') or '#%s' % cle
        _n, qte = apres.get(cle, (nom, 0))
        apres[cle] = (nom, qte + int(modele.get('count') or 0))
        if produit is not None:
            prix[cle] = Decimal(produit.prix_vente or 0)
    if {k: q for k, (_n, q) in avant.items() if q} == {
            k: q for k, (_n, q) in apres.items() if q}:
        return None
    delta = Decimal('0')
    for cle in set(avant) | set(apres):
        ecart = apres.get(cle, ('', 0))[1] - avant.get(cle, ('', 0))[1]
        delta += Decimal(ecart) * prix.get(cle, Decimal('0'))
    return avant, apres, delta


class Command(BaseCommand):
    help = ('ACAL63 — liste (lecture seule) les devis non brouillon dont la '
            'ligne panneau changerait de produit ou serait scindée.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', default=True,
            help="Défaut et seul mode : rien n'est jamais écrit.")
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')
        parser.add_argument(
            '--tous', action='store_true', default=False,
            help='Inclure aussi les brouillons (par défaut : NON brouillons).')

    def handle(self, *args, **options):
        from apps.ventes.domain.argent import Vue, totaux
        from apps.ventes.models import Devis

        qs = (Devis.objects.filter(roof_layout__has_key='modules')
              .select_related('company').prefetch_related('lignes__produit')
              .order_by('company_id', 'reference'))
        if not options.get('tous'):
            qs = qs.exclude(statut=Devis.Statut.BROUILLON)
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        self.stdout.write('DRY-RUN (lecture seule) — aucune écriture.')
        self.stdout.write(
            'société | référence | statut | panneaux avant → après | '
            'TTC avant → après (estimé)')
        nb = 0
        for devis in qs.iterator(chunk_size=200):
            resultat = projection(devis)
            if resultat is None:
                continue
            nb += 1
            avant, apres, delta_ht = resultat
            try:
                ttc = totaux(devis, vue=Vue.NET).ttc
                taux = Decimal(20 if devis.taux_tva is None
                               else devis.taux_tva) / Decimal(100)
                ttc_apres = ttc + delta_ht * (1 + taux)
            except Exception:  # noqa: BLE001 — un total illisible est signalé
                ttc, ttc_apres = '?', '?'

            def _txt(bloc):
                return ', '.join('%s × %d' % (nom, qte)
                                 for nom, qte in bloc.values() if qte)
            self.stdout.write(
                f'  {devis.company.slug} | {devis.reference} | '
                f'{devis.statut} | {_txt(avant)} → {_txt(apres)} | '
                f'{ttc} → {ttc_apres}')
        self.stdout.write(f'Devis concernés : {nb}')
