// Phoenix Group Splitter — one-off cleanup for the over-stuffed "0208" pile
// Run on https://manibhadra-phoeniximport.myshopify.com/ (storefront, NOT admin)
//
// WHAT THIS DOES
//   The 0208 group had 41 unrelated products crammed together. This script
//   partitions it into the two logical groups and unlinks everything else:
//
//     • Windorgels & windgongen (14) -> a clean group referencing only each other
//     • Meridiaankogels          (6) -> a clean group referencing only each other
//     • Tafelgongen              (3) -> a clean group referencing only each other
//     • Everything else         (18) -> custom.groep_producten emptied ([]),
//                                       i.e. removed from the pile entirely.
//
//   It REPLACES custom.groep_producten on every listed product, so the old
//   cross-links to the junk are purged. It does NOT touch groepsomschrijving /
//   groepswaarde_1 on the two real groups — define "what varies" for them
//   afterwards in the Group Entry Tool. For the cleared products it optionally
//   deletes their stale group axis metafields too (see CLEAR_AXIS_ON_CLEARED).
//
// HOW TO RUN
//   1. Paste your admin token below (from token.txt), or leave it and the
//      Group Entry Tool's "bake token" flow if you prefer.
//   2. Leave DRY_RUN = true for a no-write preview in the console first.
//   3. Set DRY_RUN = false and run again to actually write.

(async () => {
  const TOKEN = 'PASTE_TOKEN_HERE';
  const API = 'https://manibhadra-phoeniximport.myshopify.com/admin/api/2024-01/graphql.json';

  const DRY_RUN = true;                 // true = preview only, no writes
  const CLEAR_AXIS_ON_CLEARED = true;   // also delete stale group axis metafields on cleared products

  if (TOKEN === 'PASTE_TOKEN_HERE') { console.error('Set TOKEN at the top of the script.'); return; }

  // ===========================================================================
  // The partition — {sku, gid} straight from the 0208 dump (0208 = seed)
  // ===========================================================================
  const GROUPS = [
    {
      label: 'Windorgels & windgongen',
      members: [
        { sku: '0208',  gid: 'gid://shopify/Product/10769248059735' }, // Windorgel vijf buizen en hout
        { sku: '0207',  gid: 'gid://shopify/Product/10769373888855' }, // Windgong Zen zwart
        { sku: '0210',  gid: 'gid://shopify/Product/10769061577047' }, // Windorgel vijf staafjes met hout
        { sku: '0220',  gid: 'gid://shopify/Product/10769270899031' }, // Windorgel 12 buizen, drie windvangers
        { sku: '0225',  gid: 'gid://shopify/Product/10769374052695' }, // Windgong Zen
        { sku: '0234',  gid: 'gid://shopify/Product/10769321787735' }, // Windorgel vier staafjes en hout
        { sku: '0238',  gid: 'gid://shopify/Product/10769334370647' }, // Windorgel 22 staafjes en hout
        { sku: '0240',  gid: 'gid://shopify/Product/10769128685911' }, // Windorgel Yin Yang vijf buizen
        { sku: '0250',  gid: 'gid://shopify/Product/10769134158167' }, // Windorgel 'Pure sound' Toonladder zwart
        { sku: '0252',  gid: 'gid://shopify/Product/10769159684439' }, // Windorgel zes staafjes en hout
        { sku: '0253',  gid: 'gid://shopify/Product/10769271390551' }, // Windorgel vierkant vijf staafjes + kristal
        { sku: '0254',  gid: 'gid://shopify/Product/10769307697495' }, // Windorgel rond vijf staafjes + kristal
        { sku: '0259',  gid: 'gid://shopify/Product/10769711989079' }, // Windbellen met vijf engelen
        { sku: '1028',  gid: 'gid://shopify/Product/10769180557655' }, // Windmobiel witte hartjes Capiz schelp
      ],
    },
    {
      label: 'Meridiaankogels',
      members: [
        { sku: '05631', gid: 'gid://shopify/Product/10769259495767' }, // Olifanten rood/wit
        { sku: '05691', gid: 'gid://shopify/Product/10769271619927' }, // Zon & Maan rood geel op zwart
        { sku: '05811', gid: 'gid://shopify/Product/10769179935063' }, // Draak & Phoenix donkerblauw
        { sku: '05841', gid: 'gid://shopify/Product/10769190191447' }, // Vlinder
        { sku: '05871', gid: 'gid://shopify/Product/10769198285143' }, // Qi Xin Ylang
        { sku: '05941', gid: 'gid://shopify/Product/10769207066967' }, // Gele draak
      ],
    },
    {
      label: 'Tafelgongen',
      members: [
        { sku: '0200',  gid: 'gid://shopify/Product/10769059938647' }, // Tafelgong met klopper en houten frame
        { sku: '0206',  gid: 'gid://shopify/Product/10769216995671' }, // Tafelgong klein zwart en goudkleur
        { sku: '0224',  gid: 'gid://shopify/Product/10769064493399' }, // Tafelgong met klopper en roodhouten frame
      ],
    },
    {
      label: 'Tabiano biosulfur zwavel',
      members: [
        { sku: '031100', gid: 'gid://shopify/Product/10769070948695' }, // Tabiano biosulfur zwavel douchegel
        { sku: '031200', gid: 'gid://shopify/Product/10769238393175' }, // Tabiano biosulfur zwavel shampoo
        { sku: '031400', gid: 'gid://shopify/Product/10769248551255' }, // Tabiano biosulfur zwavel zeep
      ],
    },
  ];

  // Unlinked entirely (groep_producten -> []).
  const CLEAR = [
    { sku: '0115',   gid: 'gid://shopify/Product/10769756979543' }, // Boeddha met kaarshouder steengrijs
    { sku: '0120',   gid: 'gid://shopify/Product/10769217126743' }, // Sfeerlicht kaarshouder Mudra
    { sku: '0121',   gid: 'gid://shopify/Product/10769771987287' }, // Twee engeltjes met waxinelichthouders
    { sku: '0123',   gid: 'gid://shopify/Product/10769779720535' }, // Meditatie Boeddha met kaarshouder steengrijs
    { sku: '0124',   gid: 'gid://shopify/Product/10769660608855' }, // Boeddha met kaarshouder zilverkleurig
    { sku: '0149',   gid: 'gid://shopify/Product/10769674469719' }, // Meditatie Boeddha
    { sku: '0150',   gid: 'gid://shopify/Product/10769682235735' }, // Boeddha met kaarshouder
    { sku: '02513',  gid: 'gid://shopify/Product/10769374085463' }, // Lavandin - lavendel bloemen zakje
    { sku: '02545',  gid: 'gid://shopify/Product/10769374642519' }, // Marseille zeep Lavendel
    { sku: '02575',  gid: 'gid://shopify/Product/10769699340631' }, // Kussengeur Provençaalse Lavendel
    { sku: '10118',  gid: 'gid://shopify/Product/10769259233623' }, // Zakje zand
    { sku: '1013',   gid: 'gid://shopify/Product/10769376870743' }, // Wierook Nag Champa Super Hit
    { sku: '1017',   gid: 'gid://shopify/Product/10769377067351' }, // Wierook Satya Natural
    { sku: '102',    gid: 'gid://shopify/Product/10769377100119' }, // Viva Mainichi-koh wierook sandelhout
    { sku: '103',    gid: 'gid://shopify/Product/10769739972951' }, // Viva Mainichi-koh wierook sandelhout lang
  ];

  const AXIS_KEYS = ['groepsomschrijving', 'groepswaarde_1', 'groepsomschrijving_2', 'groepswaarde_2'];

  // ===========================================================================
  async function gql(query, variables) {
    const res = await fetch(API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Shopify-Access-Token': TOKEN },
      body: JSON.stringify({ query, variables }),
    });
    const j = await res.json();
    if (j.errors) console.error('GraphQL errors:', j.errors);
    return j.data;
  }

  async function setGroup(gid, gids) {
    const mfs = [{
      ownerId: gid, namespace: 'custom', key: 'groep_producten',
      type: 'list.product_reference', value: JSON.stringify(gids),
    }];
    const d = await gql(
      `mutation($mfs:[MetafieldsSetInput!]!){metafieldsSet(metafields:$mfs){metafields{id} userErrors{field message}}}`,
      { mfs });
    const errs = d && d.metafieldsSet && d.metafieldsSet.userErrors;
    if (errs && errs.length) console.error('  set errors:', errs);
    return !(errs && errs.length);
  }

  async function deleteAxisMetafields(gid) {
    const identifiers = AXIS_KEYS.map(key => ({ ownerId: gid, namespace: 'custom', key }));
    const d = await gql(
      `mutation($mf:[MetafieldIdentifierInput!]!){metafieldsDelete(metafields:$mf){deletedMetafields{key} userErrors{field message}}}`,
      { mf: identifiers });
    const errs = d && d.metafieldsDelete && d.metafieldsDelete.userErrors;
    if (errs && errs.length) console.error('  axis delete errors:', errs);
    return (d && d.metafieldsDelete && d.metafieldsDelete.deletedMetafields || []).map(x => x.key);
  }

  // ===========================================================================
  const total = GROUPS.reduce((n, g) => n + g.members.length, 0) + CLEAR.length;
  console.log('[split] ' + (DRY_RUN ? 'DRY RUN — no writes. ' : '') + total + ' products: '
    + GROUPS.map(g => g.label + ' (' + g.members.length + ')').join(', ') + ', cleared (' + CLEAR.length + ').');

  const results = [];

  // 1) Rebuild each logical group: every member references only its group-mates
  for (const g of GROUPS) {
    const gids = g.members.map(m => m.gid);
    for (const m of g.members) {
      const others = gids.filter(x => x !== m.gid);
      let ok = true;
      if (!DRY_RUN) ok = await setGroup(m.gid, others);
      console.log('[split] ' + m.sku + ' -> ' + g.label + ' (' + others.length + ' refs)' + (ok ? '' : ' FAILED'));
      results.push({ sku: m.sku, action: g.label, refs: others.length, ok });
    }
  }

  // 2) Clear the unlogical products: empty membership, optionally drop stale axis fields
  for (const c of CLEAR) {
    let ok = true, dropped = [];
    if (!DRY_RUN) {
      ok = await setGroup(c.gid, []);
      if (CLEAR_AXIS_ON_CLEARED) dropped = await deleteAxisMetafields(c.gid);
    }
    console.log('[split] ' + c.sku + ' -> cleared' + (CLEAR_AXIS_ON_CLEARED && dropped.length ? ' (axis: ' + dropped.join(',') + ')' : '') + (ok ? '' : ' FAILED'));
    results.push({ sku: c.sku, action: 'cleared', refs: 0, ok });
  }

  window._phoenixSplitCleanup = results;
  console.log('[split] ' + (DRY_RUN ? 'DRY RUN complete — set DRY_RUN = false to write.' : 'All done.') + ' Results on window._phoenixSplitCleanup');
  console.table(results);
})();
