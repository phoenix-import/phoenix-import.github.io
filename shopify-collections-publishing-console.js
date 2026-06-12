/* ============================================================================
   Phoenix Import — Collections + Publishing Status puller (browser console)
   ----------------------------------------------------------------------------
   WHAT IT DOES
     Pulls every collection (handle, title, type, product count) and its
     publishing status across ALL sales channels / publications
     (Online Store, POS, etc.), then downloads collections-publishing.csv.

   HOW TO RUN  (same pattern as the other console scripts)
     1. Open the STOREFRONT domain in a tab, e.g.
          manibhadra-phoeniximport.myshopify.com/products.json
        NOT the admin domain (admin overrides fetch & blocks the call).
     2. Open DevTools > Console.
     3. Paste this whole file, hit Enter.
     4. Paste the Admin API token (shpat_...) when prompted.
     5. Wait for "Done" — collections-publishing.csv downloads automatically.

   NOTES
     - Needs a token with read_publications + read_products scopes.
     - Read-only: it never writes anything back to the store.
   ========================================================================== */
(async () => {
  const API_VERSION = '2024-01';
  const ENDPOINT    = `/admin/api/${API_VERSION}/graphql.json`;
  const PAGE_SIZE   = 100;          // kept well under the 1000-point query-cost cap
  const TOKEN = (window.__SHPAT__ || prompt('Shopify Admin API token (shpat_...):') || '').trim();
  if (!TOKEN) { console.error('No token — aborted.'); return; }

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // --- GraphQL helper with throttle-aware retry --------------------------
  async function gql(query, attempt = 0) {
    let r;
    try {
      r = await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Shopify-Access-Token': TOKEN },
        body: JSON.stringify({ query }),
      });
    } catch (e) {
      if (attempt < 4) { await sleep(1000 * 2 ** attempt); return gql(query, attempt + 1); }
      throw e;
    }
    const j = await r.json().catch(() => ({}));
    const throttled = (j.errors || []).some(e => (e.extensions?.code || e.message || '').toString().includes('THROTTLED'));
    if (throttled && attempt < 6) {
      const wait = (j.extensions?.cost?.throttleStatus?.restoreRate ? 1500 : 1000) * (attempt + 1);
      console.warn(`Throttled — waiting ${wait}ms…`);
      await sleep(wait);
      return gql(query, attempt + 1);
    }
    if (j.errors) throw new Error(JSON.stringify(j.errors, null, 2));
    // gentle pacing so we don't trip the bucket on big stores
    const avail = j.extensions?.cost?.throttleStatus?.currentlyAvailable;
    if (typeof avail === 'number' && avail < 200) await sleep(800);
    return j.data;
  }

  // --- 1. publications (sales channels) ----------------------------------
  console.log('Fetching publications…');
  const pubData = await gql(`{
    publications(first: 50) { edges { node { id name } } }
  }`);
  const pubs = pubData.publications.edges.map(e => e.node);
  if (!pubs.length) { console.error('No publications returned — token missing read_publications?'); return; }
  console.log('Publications:', pubs.map(p => p.name).join(', '));
  const onlineStore = pubs.find(p => /online store/i.test(p.name));

  // per-channel boolean aliases injected into the collection query
  const chanFields = pubs
    .map((p, i) => `ch${i}: publishedOnPublication(publicationId: ${JSON.stringify(p.id)})`)
    .join('\n        ');

  // --- 2. page through all collections -----------------------------------
  const rows = [];
  let after = null, page = 0;
  do {
    const q = `{
      collections(first: ${PAGE_SIZE}${after ? `, after: ${JSON.stringify(after)}` : ''}) {
        pageInfo { hasNextPage endCursor }
        edges { node {
          handle
          title
          productsCount { count }
          ruleSet { appliedDisjunctively }   # present => smart (automated) collection
          ${chanFields}
        } }
      }
    }`;
    const d = await gql(q);
    const conn = d.collections;
    for (const { node } of conn.edges) {
      const channelsOn = pubs.filter((_, i) => node[`ch${i}`]).map(p => p.name);
      rows.push({
        handle: node.handle,
        title: node.title,
        type: node.ruleSet ? 'smart' : 'custom',
        products_count: node.productsCount?.count ?? '',
        online_store: onlineStore ? !!node[`ch${pubs.indexOf(onlineStore)}`] : '',
        channels_published_count: channelsOn.length,
        channels_published: channelsOn.join(' | '),
        ...Object.fromEntries(pubs.map((p, i) => [`pub:${p.name}`, node[`ch${i}`] ? 'TRUE' : 'FALSE'])),
      });
    }
    after = conn.pageInfo.hasNextPage ? conn.pageInfo.endCursor : null;
    console.log(`Page ${++page} — ${rows.length} collections so far…`);
  } while (after);

  // --- 3. build + download CSV -------------------------------------------
  const cols = Object.keys(rows[0] || { handle: '', title: '' });
  const esc = v => {
    const s = v === null || v === undefined ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [cols.join(','), ...rows.map(r => cols.map(c => esc(r[c])).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const a = Object.assign(document.createElement('a'), { href: url, download: 'collections-publishing.csv' });
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);

  const unpublished = rows.filter(r => r.online_store === false).length;
  console.log(`Done. ${rows.length} collections — ${unpublished} NOT on Online Store. CSV downloaded.`);
  window.__COLLECTIONS__ = rows; // also left on window for ad-hoc inspection
})();
