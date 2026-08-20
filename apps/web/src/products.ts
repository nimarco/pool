/* Product imagery, resolved at build time.
 *
 * Every catalogue photograph is a file committed to this repository and emitted into
 * `assets/` by Vite, so a product card is served from Pool's own origin. That is not
 * incidental:
 *
 *   - the deployed CSP is `img-src 'self'`, which forbids remote images outright, and
 *     weakening a security header to make a demo prettier is the wrong trade;
 *   - the Lambda that serves the built app serves exactly `index.html` and
 *     `/assets/{name}`, so a hashed asset is the only path that actually resolves;
 *   - a demo whose product photographs come from a third-party image host is a demo
 *     that can break in front of judges because someone else had an outage.
 *
 * `import.meta.glob` with `eager` gives Vite the whole directory at build time, so each
 * file gets a content hash and an immutable cache header for free, and anything the
 * catalogue stopped referencing simply stops being imported.
 *
 * Images are from Open Food Facts contributors under CC-BY-SA; the credit is rendered
 * wherever they are (see `CatalogAttribution`).
 */

const FILES = import.meta.glob<string>("./assets/products/*.jpg", {
  eager: true,
  query: "?url",
  import: "default",
});

/** `{ prod_0748927069525: "/assets/prod_0748927069525-a1b2c3.jpg" }` */
const BY_REF: Record<string, string> = Object.fromEntries(
  Object.entries(FILES).map(([path, url]) => [
    path.slice(path.lastIndexOf("/") + 1).replace(/\.jpg$/, ""),
    url,
  ]),
);

/** The bundled photograph for a product, or null when there is none.
 *
 *  Null is an ordinary answer, not an error: household consumables are curated and
 *  carry no photograph at all, because no open catalogue covers them and inventing a
 *  brand to get a picture would be worse than a tile. */
export function productImage(imageRef: string): string | null {
  if (!imageRef) return null;
  return BY_REF[imageRef] ?? null;
}

/** The ground a missing photograph sits on.
 *
 *  It used to be category-coloured. In this visual system colour means exactly one
 *  thing — demand accumulating toward a threshold — so tinting a tile by category would
 *  spend the only meaningful hue on a fact that is not a quantity. The tile is therefore
 *  a cold neutral step of the same chart stock everything else is drawn on, which also
 *  says the true thing: there is no photograph here.
 *
 *  Still deterministic, and still varies a little across the two neutral steps, so a
 *  results list of unphotographed products does not read as one solid block.
 */
export function categoryTone(category: string): string {
  switch (category) {
    case "nutrition":
    case "beverage":
      return "var(--stock-sunken)";
    default:
      return "var(--stock-deep)";
  }
}

/** The one or two letters a fallback tile shows. Brand first when there is one; a
 *  curated household product has none, so the product name carries it. */
export function productInitials(brand: string, name: string): string {
  const source = (brand || name || "?").trim();
  const words = source.split(/\s+/).filter(Boolean);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}
