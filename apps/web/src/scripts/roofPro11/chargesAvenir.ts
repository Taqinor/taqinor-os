/**
 * ACAL780 — LES CHARGES À VENIR de l'atelier (`consumption.charges[]` du document).
 *
 * Voiture électrique et pompe à chaleur, avec les SEULS champs que le serveur exige
 * (`services/charges.py::courbe_vehicule` / `::courbe_pac`, lus par `courbe_charge.py`), TOUS
 * saisis : un champ vide reste vide et REFUSE en nommant le champ, jamais une valeur de repli.
 * La case « déjà dans mes factures » (ACAL779) est proposée sur chaque charge : cochée, le
 * serveur ignore la charge et un avertissement la nomme.
 *
 * Pur, sauf `monterChargesAvenir` (rendu DOM de la liste et du formulaire). Un document relu
 * garde ses charges : tant que l'utilisateur n'y touche pas, `consommationSerialisee.ts` les
 * réémet telles quelles (jamais effacées au prochain enregistrement).
 *
 * CLIMATISATION (ACAL1645) : saisie en BTU/h, EER et heures de marche. `courbe_charge.py::_bloc_de_charge`
 * ne lit ni `btu` ni `eer` pour le type `clim` (il exige `puissance_kw` et `heures_fonctionnement`) :
 * la charge porte donc `btu` et `eer` SAISIS et `puissance_kw` = BTU/h ÷ EER ÷ 1000, la définition
 * même de l'EER (BTU/h par watt électrique) ; aucun autre coefficient n'est ajouté.
 *
 * Câblage : `Ctx.consCharges` (`context.ts`, absent tant que l'utilisateur n'y a pas touché),
 * monté par `consumption.ts` dans `[data-cons-charges]` (conteneur de `ToitureDesign.jsx`).
 */
import { esc } from './dom';

export type TypeCharge = 'vehicule' | 'pac' | 'clim';

/** Une charge telle qu'elle voyage dans `consumption.charges` (forme ouverte côté serveur). */
export interface ChargeAvenir {
  type: TypeCharge;
  /** ACAL779 — SAISI : vrai = déjà comprise dans les factures (ignorée du calcul serveur). */
  deja_dans_les_factures?: boolean;
  km_par_jour?: number;
  kwh_par_100km?: number;
  fenetre_recharge?: number[];
  puissance_kw?: number;
  cop?: number;
  btu?: number;
  eer?: number;
  heures_fonctionnement?: number[];
}

export interface RefusCharge {
  champ: string;
  message: string;
}

/** Les champs de saisie de chaque type : clé du document, libellé, nature. */
export const CHAMPS_PAR_TYPE: Record<TypeCharge, ReadonlyArray<{ cle: string; libelle: string; fenetre?: boolean }>> = {
  vehicule: [
    { cle: 'km_par_jour', libelle: 'Kilomètres par jour' },
    { cle: 'kwh_par_100km', libelle: 'Consommation (kWh pour 100 km)' },
    { cle: 'fenetre_recharge', libelle: 'Heures de recharge (ex. 22-24)', fenetre: true },
  ],
  pac: [
    { cle: 'puissance_kw', libelle: 'Puissance thermique (kW)' },
    { cle: 'cop', libelle: 'COP' },
    { cle: 'heures_fonctionnement', libelle: 'Heures de marche (ex. 6-9)', fenetre: true },
  ],
  clim: [
    { cle: 'btu', libelle: 'Puissance frigorifique (BTU/h)' },
    { cle: 'eer', libelle: 'EER (BTU/h par W)' },
    { cle: 'heures_fonctionnement', libelle: 'Heures de marche (ex. 10-15)', fenetre: true },
  ],
};

export const LIBELLE_TYPE: Record<TypeCharge, string> = { vehicule: 'Voiture électrique', pac: 'Pompe à chaleur', clim: 'Climatisation' };

/** « 22-24 » → [22, 23, 0] : de la première à la dernière heure INCLUSE, modulo 24 ; « 7 » → [7]. */
export function fenetreDepuisTexte(texte: string): number[] | null {
  const m = /^\s*(\d{1,2})\s*(?:[-–]\s*(\d{1,2}))?\s*$/.exec(texte);
  if (!m) return null;
  const debut = Number(m[1]);
  const fin = m[2] === undefined ? debut : Number(m[2]);
  if (debut > 24 || fin > 24) return null;
  const dernier = fin >= debut ? fin : fin + 24; // 22-6 : la nuit, jusqu'au lendemain
  const heures: number[] = [];
  for (let h = debut; h <= dernier; h += 1) heures.push(h % 24);
  return Array.from(new Set(heures));
}

/** Une charge depuis la saisie texte, ou le REFUS qui nomme le champ (vide, illisible, ≤ 0). */
export function chargeDepuisSaisie(
  type: TypeCharge,
  saisie: Readonly<Record<string, string>>,
  dejaDansFactures = false,
): ChargeAvenir | RefusCharge {
  const charge: Record<string, unknown> = { type };
  for (const { cle, libelle, fenetre } of CHAMPS_PAR_TYPE[type]) {
    const texte = String(saisie[cle] ?? '').trim();
    if (!texte) return { champ: cle, message: `${libelle} : à saisir (aucune valeur n'est supposée).` };
    if (fenetre) {
      const heures = fenetreDepuisTexte(texte);
      if (!heures) return { champ: cle, message: `${libelle} : écrivez deux heures de 0 à 24, par exemple 22-24.` };
      charge[cle] = heures;
    } else {
      const nombre = Number(texte.replace(',', '.'));
      if (!Number.isFinite(nombre) || nombre <= 0) return { champ: cle, message: `${libelle} : un nombre supérieur à zéro.` };
      charge[cle] = nombre;
    }
  }
  if (type === 'clim') charge.puissance_kw = (charge.btu as number) / (charge.eer as number) / 1000;
  if (dejaDansFactures) charge.deja_dans_les_factures = true;
  return charge as unknown as ChargeAvenir;
}

export const estRefusCharge = (v: ChargeAvenir | RefusCharge): v is RefusCharge => 'message' in v;

/** Les charges telles qu'écrites dans le document (copie : jamais la référence de l'écran). */
export function chargesPourDocument(charges: readonly ChargeAvenir[]): ChargeAvenir[] {
  return charges.map((c) => JSON.parse(JSON.stringify(c)) as ChargeAvenir);
}

/** Relit `consumption.charges` d'un document : seules les charges `vehicule`/`pac`/`clim` bien formées. */
export function releireCharges(documentConsumption: unknown): ChargeAvenir[] {
  const brut = (documentConsumption as { charges?: unknown } | null | undefined)?.charges;
  if (!Array.isArray(brut)) return [];
  return brut.filter((c): c is ChargeAvenir => !!c && typeof c === 'object' && (['vehicule', 'pac', 'clim'] as string[]).includes((c as ChargeAvenir).type));
}

const resume = (c: ChargeAvenir): string => (c.type === 'vehicule'
  ? `${c.km_par_jour} km/jour · ${c.kwh_par_100km} kWh/100 km · ${(c.fenetre_recharge || []).join(', ')} h`
  : c.type === 'clim'
    ? `${c.btu} BTU/h · EER ${c.eer} · ${(c.heures_fonctionnement || []).join(', ')} h`
    : `${c.puissance_kw} kW · COP ${c.cop} · ${(c.heures_fonctionnement || []).join(', ')} h`);

/** Accès de l'écran à la liste : `lire` rend la liste COURANTE (écran, sinon relue), `ecrire` la pose. */
export interface AccesCharges {
  lire: () => readonly ChargeAvenir[];
  ecrire: (charges: ChargeAvenir[]) => void;
}

/**
 * Rend la liste des charges et le formulaire d'ajout dans `hote` (bloc « Mode expert »). Chaque
 * ajout, retrait ou case cochée écrit une COPIE de la liste par `acces.ecrire`. Renvoie
 * `rafraichir` : redessine seulement si la liste a changé (document relu après le montage), sans
 * jamais effacer une saisie en cours.
 */
export function monterChargesAvenir(hote: HTMLElement, acces: AccesCharges): { rafraichir: () => void } {
  let type: TypeCharge = 'vehicule';
  let refus: RefusCharge | null = null;
  let brouillon: Record<string, string> = {}; // la saisie reste à l'écran après un refus
  let vue = '';
  const copie = (): ChargeAvenir[] => chargesPourDocument(acces.lire());
  const rendre = () => {
    const charges = acces.lire();
    vue = JSON.stringify(charges);
    const lignes = charges.map((c, i) => `<li data-cons-charge="${i}" class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <span class="font-semibold">${esc(LIBELLE_TYPE[c.type])}</span><span class="text-xs">${esc(resume(c))}</span>
      <label class="text-xs"><input type="checkbox" data-cons-charge-deja="${i}"${c.deja_dans_les_factures ? ' checked' : ''}> déjà dans mes factures</label>
      <button type="button" data-cons-charge-del="${i}" aria-label="Supprimer la charge" style="min-height:44px;min-width:44px">×</button></li>`).join('');
    const champs = CHAMPS_PAR_TYPE[type].map(({ cle, libelle }) => `<label class="block text-xs">${esc(libelle)}
      <input data-cons-charge-champ="${cle}" inputmode="decimal" step="any" value="${esc(brouillon[cle] || '')}" style="min-height:44px">
      ${refus?.champ === cle ? `<span role="alert" data-cons-charge-refus="${cle}">${esc(refus.message)}</span>` : ''}</label>`).join('');
    hote.innerHTML = `<ul>${lignes}</ul><div data-cons-charge-form>
      <select data-cons-charge-type style="min-height:44px"><option value="vehicule"${type === 'vehicule' ? ' selected' : ''}>Voiture électrique</option>
      <option value="pac"${type === 'pac' ? ' selected' : ''}>Pompe à chaleur</option>
      <option value="clim"${type === 'clim' ? ' selected' : ''}>Climatisation</option></select>${champs}
      <label class="text-xs"><input type="checkbox" data-cons-charge-nouvelle-deja> déjà dans mes factures</label>
      <button type="button" data-cons-charge-ajouter style="min-height:44px">Ajouter une charge à venir</button></div>`;
  };
  hote.addEventListener('change', (e) => {
    const cible = e.target as HTMLInputElement;
    if (cible.matches('[data-cons-charge-type]')) { type = cible.value as TypeCharge; refus = null; brouillon = {}; rendre(); return; }
    const i = cible.getAttribute('data-cons-charge-deja');
    const liste = copie();
    if (i !== null && liste[Number(i)]) {
      if (cible.checked) liste[Number(i)].deja_dans_les_factures = true; else delete liste[Number(i)].deja_dans_les_factures;
      acces.ecrire(liste);
      vue = JSON.stringify(liste);
    }
  });
  hote.addEventListener('click', (e) => {
    const cible = e.target as HTMLElement;
    const sup = cible.getAttribute('data-cons-charge-del');
    if (sup !== null) { const liste = copie(); liste.splice(Number(sup), 1); acces.ecrire(liste); rendre(); return; }
    if (!cible.hasAttribute('data-cons-charge-ajouter')) return;
    const saisie: Record<string, string> = {};
    hote.querySelectorAll<HTMLInputElement>('[data-cons-charge-champ]').forEach((el) => { saisie[el.getAttribute('data-cons-charge-champ') || ''] = el.value; });
    const deja = !!hote.querySelector<HTMLInputElement>('[data-cons-charge-nouvelle-deja]')?.checked;
    const res = chargeDepuisSaisie(type, saisie, deja);
    brouillon = saisie;
    if (estRefusCharge(res)) { refus = res; rendre(); return; }
    refus = null; brouillon = {}; acces.ecrire([...copie(), res]); rendre();
  });
  rendre();
  return { rafraichir: () => { if (JSON.stringify(acces.lire()) !== vue) rendre(); } };
}
