/**
 * ACAL777 — LA FACTURE QUE LIT LA CARTE « Recommandation » (et le Total).
 *
 * En mode calepinage le champ `rp9-bill` n'existe pas : `monthlyBill()` rend 0 et la carte
 * affichait « 0 MAD – 0 MAD/an » et « ≈ 0 % ». Le serveur sert la facture mensuelle du lead
 * (`consommation_lead.facture_mensuelle_mad`, ACAL776) : elle sert de REPLI D'AFFICHAGE aux deux
 * calculs de carte seulement. Le champ saisi PRIME quand il existe (mode lead inchangé) ;
 * `monthlyBill()` lui-même ne change pas, donc le nombre de panneaux ne bouge jamais ; aucune
 * facture n'est inventée (`null` ⇒ 0, c'est ACAL852 qui parle alors) ; rien n'est écrit au document.
 */

/** La facture mensuelle (MAD) saisie dans le champ, 0 si vide ou illisible (corps de `monthlyBill`). */
export function lireFactureSaisie(billEl: { value?: string } | null | undefined): number {
  const raw = parseFloat((billEl?.value || '').replace(/\s/g, '').replace(',', '.'));
  return Number.isFinite(raw) && raw > 0 ? raw : 0;
}

/** Facture de la carte : la saisie si > 0, sinon la facture du lead servie, sinon 0. */
export function factureCarteDe(saisie: number, factureLead: number | null | undefined): number {
  if (saisie > 0) return saisie;
  return typeof factureLead === 'number' && Number.isFinite(factureLead) && factureLead > 0 ? factureLead : 0;
}
