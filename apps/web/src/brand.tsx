/* Brand marks and the one explanatory figure on the site.
 *
 * The wordmark's glyph is a ring of separate people around a single pooled order: the
 * product in one shape. The centre is clay because the thing in the middle is not
 * automation — it is a person's order, and one of the people carries the box.
 */

/** The logo glyph. Legible from 16 px (favicon) to 96 px. */
export function BrandMark({ size = 24 }: { size?: number }) {
  const ring = [
    [12, 4],
    [18.93, 8],
    [18.93, 16],
    [12, 20],
    [5.07, 16],
    [5.07, 8],
  ];
  return (
    <svg className="brand-mark" viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
      {ring.map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2.05" fill="var(--moss)" />
      ))}
      <circle cx="12" cy="12" r="3.4" fill="var(--clay)" />
    </svg>
  );
}

/* --------------------------------------------------------------- the figure */

/** Eleven people, eleven separate restock dates, one pool day.
 *
 * This is not decoration and it is not an illustration of the general idea — it is the
 * arithmetic of the pool this community actually forms, drawn. Eight people were going to buy about now
 * anyway, and that is eighteen units against a supplier minimum of twenty-four. Two more
 * would not have bought until later; Pool may bring them forward only because those two
 * authorised an early purchase, and their six units close the gap exactly. An eleventh
 * authorised nothing, so nothing happens to them.
 *
 * Those counts come from the same `evaluate_timing` the matcher uses, reported by the
 * transcript as `due_now_members` / `pulled_forward_members`. If the seed changes so
 * does the run, and this figure has to change with it.
 */
export function ConvergenceFigure() {
  const left = 4;
  const right = 356;
  const poolX = 214;
  // Each row is one person. `x` is the day they would have bought on their own:
  // eight already due, two who authorised buying early, one who did not.
  const rows: { x: number; kind: "due" | "pulled" | "left" }[] = [
    { x: 118, kind: "due" },
    { x: 178, kind: "due" },
    { x: 62, kind: "due" },
    { x: 196, kind: "due" },
    { x: 144, kind: "due" },
    { x: 90, kind: "due" },
    { x: 166, kind: "due" },
    { x: 132, kind: "due" },
    { x: 276, kind: "pulled" },
    { x: 318, kind: "pulled" },
    { x: 348, kind: "left" },
  ];
  const top = 30;
  const gap = 19;
  const baseline = top + (rows.length - 1) * gap;
  const height = baseline + 46;

  return (
    <figure style={{ margin: 0 }}>
      <svg
        className="converge"
        viewBox={`0 0 360 ${height}`}
        role="img"
        aria-label="Eleven people with eleven separate restock dates. Eight fall due inside the same week and join naturally, which is eighteen units against a supplier minimum of twenty-four. Two more are pulled forward onto the pool day because those buyers had authorised an early purchase, and their six units close the gap exactly. The eleventh had not authorised anything, and is left alone."
      >
        {/* The pool day: a fixed weekly moment. Everything that joins lands on it. */}
        <line
          x1={poolX}
          y1={top - 16}
          x2={poolX}
          y2={baseline + 13}
          stroke="var(--moss)"
          strokeWidth="1.5"
        />
        <text
          x={poolX}
          y={top - 22}
          fill="var(--moss)"
          fontSize="10"
          textAnchor="middle"
          letterSpacing="0.08em"
        >
          ONE POOL DAY
        </text>

        {rows.map((row, i) => {
          const y = top + i * gap;
          const joins = row.kind !== "left";
          return (
            <g key={i}>
              <line
                x1={left}
                y1={y}
                x2={right}
                y2={y}
                stroke="var(--rule)"
                strokeWidth="1"
                strokeDasharray="1.5 4"
              />
              {joins ? (
                <line
                  x1={Math.min(row.x, poolX)}
                  y1={y}
                  x2={Math.max(row.x, poolX)}
                  y2={y}
                  stroke={row.kind === "pulled" ? "var(--clay)" : "var(--moss)"}
                  strokeWidth="1.4"
                  strokeDasharray={row.kind === "pulled" ? "3 2.5" : undefined}
                />
              ) : null}
              <circle
                cx={row.x}
                cy={y}
                r={row.kind === "left" ? 2.5 : 3.3}
                fill={
                  row.kind === "left"
                    ? "var(--ink-faint)"
                    : row.kind === "pulled"
                      ? "var(--clay)"
                      : "var(--moss)"
                }
                opacity={row.kind === "left" ? 0.6 : 1}
              />
              {joins ? <circle cx={poolX} cy={y} r="2.4" fill="var(--moss)" /> : null}
            </g>
          );
        })}

        <text x={left} y={baseline + 30} fill="var(--ink-faint)" fontSize="10" letterSpacing="0.06em">
          EARLIER
        </text>
        <text
          x={right}
          y={baseline + 30}
          fill="var(--ink-faint)"
          fontSize="10"
          textAnchor="end"
          letterSpacing="0.06em"
        >
          LATER
        </text>
      </svg>
      <figcaption className="tiny muted" style={{ marginTop: 10, maxWidth: "46ch" }}>
        Each line is one person's restock date. <strong>Eight</strong> were going to buy
        about now anyway — eighteen units, against a supplier minimum of twenty-four.{" "}
        <strong>Two</strong> more are pulled forward, allowed only because they authorised
        an early purchase, and their six units close the gap exactly. The eleventh
        authorised nothing, so nothing happens to them.
      </figcaption>
    </figure>
  );
}
