// xcbench 3-slide deck — warm-ink / coral aesthetic
//
// Regenerate after new benchmark runs:
//   1. Update the Findings table in README.md.
//   2. Mirror those numbers into the three data sites below:
//        - Slide 1 stat card:  "$0.67" / "$0.14"  (search this file)
//        - Slide 3 `bars` array: cost + quality per strategy
//        - Slide 3 headline: "64% the cost" ratio (= ensemble / full_ctx)
//   3. Run:  npm i -g pptxgenjs  (once)
//           NODE_PATH=$(npm root -g) node scripts/build_deck.js
//      Writes assets/xcbench_3slides.pptx.
const pptxgen = require("pptxgenjs");

const C = {
  paper:     "F4EFE6",  // warm cream
  paperDeep: "EBE3D3",  // slightly deeper cream for sections
  ink:       "141414",  // near-black ink
  ink2:      "2B2B2B",
  muted:     "6E6557",
  rule:      "CDBEAA",
  accent:    "D9512C",  // terracotta/coral
  accent2:   "8A6E3B",  // olive-gold
};

const F = { head: "Georgia", body: "Calibri" };

let pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";  // 13.33 × 7.5
pres.author = "xcbench";
pres.title  = "Context Curation Benchmark";

const W = 13.333, H = 7.5;

// ------------ chrome applied to every slide ------------
function chrome(slide, { idx, total, dark = false }) {
  slide.background = { color: dark ? C.ink : C.paper };

  // thin left stripe (the motif)
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.16, h: H,
    fill: { color: C.accent }, line: { color: C.accent, width: 0 }
  });

  // top-right slide index
  slide.addText(
    [
      { text: String(idx).padStart(2, "0"), options: { bold: true, color: dark ? C.paper : C.ink } },
      { text: `  /  ${String(total).padStart(2, "0")}`, options: { color: dark ? C.rule : C.muted } },
    ],
    { x: W - 1.6, y: 0.35, w: 1.2, h: 0.35,
      fontFace: F.body, fontSize: 11, charSpacing: 4, align: "right", margin: 0 }
  );

  // tiny project wordmark bottom-left
  slide.addText("XCBENCH  ·  HR LIVING DOCS", {
    x: 0.55, y: H - 0.5, w: 5, h: 0.3,
    fontFace: F.body, fontSize: 9, charSpacing: 3,
    color: dark ? C.rule : C.muted, margin: 0
  });

  slide.addText("APR · 2026", {
    x: W - 1.6, y: H - 0.5, w: 1.05, h: 0.3,
    fontFace: F.body, fontSize: 9, charSpacing: 3,
    color: dark ? C.rule : C.muted, align: "right", margin: 0
  });
}

// =============================================================
// SLIDE 1 — Thesis (dark)
// =============================================================
{
  const s = pres.addSlide();
  chrome(s, { idx: 1, total: 3, dark: true });

  // overline
  s.addText("A  CONTEXT  CURATION  BENCHMARK", {
    x: 0.75, y: 0.9, w: 10, h: 0.4,
    fontFace: F.body, fontSize: 11, bold: true, charSpacing: 8,
    color: C.accent, margin: 0
  });

  // mega headline — narrower width + 78pt so it clears the stat card at x=8.5
  s.addText([
    { text: "Does",          options: { color: C.paper, breakLine: true } },
    { text: "stuffing",      options: { color: C.paper, breakLine: true } },
    { text: "still ",        options: { color: C.paper } },
    { text: "win",           options: { color: C.accent, italic: true } },
    { text: "?",             options: { color: C.paper } },
  ], {
    x: 0.75, y: 1.35, w: 7.5, h: 3.0,
    fontFace: F.head, fontSize: 78, bold: true,
    lineSpacingMultiple: 0.92, margin: 0
  });

  // subtitle — whitespace separates it from the headline, no decorative rule
  s.addText(
    "Seven context strategies measured on a New-Hire Onboarding Agent — stale GitLab Handbook " +
    "cross-cut with fresh, HR-validated Slack threads. If the full-window default still wins, " +
    "curation is a waste of cycles. If not, how cheap can ‘right’ actually get?",
    { x: 0.75, y: 5.1, w: 7.2, h: 1.5,
      fontFace: F.body, fontSize: 14, color: C.paper, lineSpacingMultiple: 1.35, margin: 0 }
  );

  // big stat block — right side
  const bx = 8.5, by = 1.55;

  // card
  s.addShape(pres.shapes.RECTANGLE, {
    x: bx, y: by, w: 4.1, h: 4.6,
    fill: { color: C.ink2 }, line: { color: C.rule, width: 0 }
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: bx, y: by, w: 4.1, h: 0.08,
    fill: { color: C.accent }, line: { color: C.accent, width: 0 }
  });

  s.addText("THE  GAP", {
    x: bx + 0.35, y: by + 0.3, w: 3.5, h: 0.3,
    fontFace: F.body, fontSize: 10, bold: true, charSpacing: 6,
    color: C.accent, margin: 0
  });

  // full_context
  s.addText("Full-context stuffing", {
    x: bx + 0.35, y: by + 0.75, w: 3.6, h: 0.3,
    fontFace: F.body, fontSize: 12, color: C.rule, margin: 0
  });
  s.addText("$0.67", {
    x: bx + 0.35, y: by + 1.05, w: 3.6, h: 1.0,
    fontFace: F.head, fontSize: 60, bold: true, color: C.paper, margin: 0
  });
  s.addText("quality 0.995  ·  19,957 tok / q", {
    x: bx + 0.35, y: by + 2.05, w: 3.6, h: 0.3,
    fontFace: F.body, fontSize: 11, color: C.muted, margin: 0
  });

  // divider
  s.addShape(pres.shapes.LINE, {
    x: bx + 0.35, y: by + 2.55, w: 3.4, h: 0,
    line: { color: C.muted, width: 0.75 }
  });

  // oracle
  s.addText("Oracle router ceiling", {
    x: bx + 0.35, y: by + 2.75, w: 3.6, h: 0.3,
    fontFace: F.body, fontSize: 12, color: C.rule, margin: 0
  });
  s.addText("$0.14", {
    x: bx + 0.35, y: by + 3.05, w: 3.6, h: 1.0,
    fontFace: F.head, fontSize: 60, bold: true, color: C.accent, margin: 0
  });
  s.addText("quality 1.000  ·  ~5× cheaper", {
    x: bx + 0.35, y: by + 4.05, w: 3.6, h: 0.3,
    fontFace: F.body, fontSize: 11, color: C.muted, margin: 0
  });
}

// =============================================================
// SLIDE 2 — Method
// =============================================================
{
  const s = pres.addSlide();
  chrome(s, { idx: 2, total: 3, dark: false });

  s.addText("METHOD", {
    x: 0.75, y: 0.9, w: 6, h: 0.32,
    fontFace: F.body, fontSize: 11, bold: true, charSpacing: 8,
    color: C.accent, margin: 0
  });

  s.addText("Seven strategies, one messy corpus.", {
    x: 0.75, y: 1.22, w: 12, h: 1.0,
    fontFace: F.head, fontSize: 40, bold: true,
    color: C.ink, lineSpacingMultiple: 1.0, margin: 0
  });

  // ==== LEFT COLUMN — corpus diagram ====
  const lx = 0.75, ly = 2.5, lw = 5.0;

  s.addText("CORPUS", {
    x: lx, y: ly, w: lw, h: 0.28,
    fontFace: F.body, fontSize: 10, bold: true, charSpacing: 6,
    color: C.muted, margin: 0
  });

  // handbook card (stale)
  s.addShape(pres.shapes.RECTANGLE, {
    x: lx, y: ly + 0.35, w: lw, h: 1.75,
    fill: { color: C.paperDeep }, line: { color: C.rule, width: 0.5 }
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: lx, y: ly + 0.35, w: 0.08, h: 1.75,
    fill: { color: C.accent2 }, line: { color: C.accent2, width: 0 }
  });
  s.addText("11  GitLab Handbook docs", {
    x: lx + 0.28, y: ly + 0.5, w: lw - 0.4, h: 0.35,
    fontFace: F.head, fontSize: 18, bold: true, color: C.ink, margin: 0
  });
  s.addText("timestamped 2026-01-01  ·  stale on purpose", {
    x: lx + 0.28, y: ly + 0.88, w: lw - 0.4, h: 0.28,
    fontFace: F.body, fontSize: 11, italic: true, color: C.muted, margin: 0
  });
  s.addText(
    "PTO · expenses · IT onboarding · benefits · parental leave · travel · remote work",
    { x: lx + 0.28, y: ly + 1.22, w: lw - 0.4, h: 0.75,
      fontFace: F.body, fontSize: 11, color: C.ink2, lineSpacingMultiple: 1.3, margin: 0 }
  );

  // slack card (fresh)
  s.addShape(pres.shapes.RECTANGLE, {
    x: lx, y: ly + 2.25, w: lw, h: 1.75,
    fill: { color: C.paperDeep }, line: { color: C.rule, width: 0.5 }
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: lx, y: ly + 2.25, w: 0.08, h: 1.75,
    fill: { color: C.accent }, line: { color: C.accent, width: 0 }
  });
  s.addText("10  Slack threads  (API shape)", {
    x: lx + 0.28, y: ly + 2.4, w: lw - 0.4, h: 0.35,
    fontFace: F.head, fontSize: 18, bold: true, color: C.ink, margin: 0
  });
  s.addText("fresh  ·  HR-validated  ·  sometimes contradicts handbook", {
    x: lx + 0.28, y: ly + 2.78, w: lw - 0.4, h: 0.28,
    fontFace: F.body, fontSize: 11, italic: true, color: C.muted, margin: 0
  });
  s.addText(
    "10 Qs across 4 categories:  portal_only · slack_contradicts · slack_only · needs_both",
    { x: lx + 0.28, y: ly + 3.12, w: lw - 0.4, h: 0.75,
      fontFace: F.body, fontSize: 11, color: C.ink2, lineSpacingMultiple: 1.3, margin: 0 }
  );

  // ==== RIGHT COLUMN — 7 strategies ====
  const rx = 6.5, ry = 2.5, rw = 6.2;

  s.addText("STRATEGIES  COMPARED", {
    x: rx, y: ry, w: rw, h: 0.28,
    fontFace: F.body, fontSize: 10, bold: true, charSpacing: 6,
    color: C.muted, margin: 0
  });

  const strategies = [
    ["full_context",            "concatenate every doc + every thread"],
    ["meta_harness_optimized",  "LLM proposer mutates a typed CurationSpec"],
    ["rag_embedding",           "bge-small + FAISS, top-k chunk retrieval"],
    ["hierarchical",            "map-summaries → LLM picks 2–5 doc_ids → expand"],
    ["agent_managed",           "tool-use loop with list_* / get_* over 6 turns"],
    ["cascade_router",          "hier → self-verify → agent → verify → full"],
    ["ensemble",                "hier ∥ agent_managed, judge picks the winner"],
  ];

  const rowH = 0.48;
  strategies.forEach(([name, desc], i) => {
    const y = ry + 0.45 + i * rowH;

    // index number
    s.addText(String(i + 1).padStart(2, "0"), {
      x: rx, y: y, w: 0.45, h: rowH - 0.05,
      fontFace: F.head, fontSize: 13, italic: true, color: C.accent, margin: 0, valign: "middle"
    });

    // name
    s.addText(name, {
      x: rx + 0.5, y: y, w: 2.5, h: rowH - 0.05,
      fontFace: F.body, fontSize: 13, bold: true, color: C.ink, margin: 0, valign: "middle"
    });

    // descriptor
    s.addText(desc, {
      x: rx + 3.1, y: y, w: rw - 3.1, h: rowH - 0.05,
      fontFace: F.body, fontSize: 11, color: C.ink2, margin: 0, valign: "middle"
    });

    // thin divider
    if (i < strategies.length - 1) {
      s.addShape(pres.shapes.LINE, {
        x: rx, y: y + rowH - 0.04, w: rw, h: 0,
        line: { color: C.rule, width: 0.5 }
      });
    }
  });

  // bottom caption
  s.addText(
    "Agent: Sonnet 4.6.   Judge / proposer: Opus 4.7.   Metrics: quality · f1 · tokens · latency · $.",
    { x: 0.75, y: H - 0.95, w: 11, h: 0.3,
      fontFace: F.body, fontSize: 10, italic: true, color: C.muted, margin: 0 }
  );
}

// =============================================================
// SLIDE 3 — Findings
// =============================================================
{
  const s = pres.addSlide();
  chrome(s, { idx: 3, total: 3, dark: false });

  s.addText("FINDINGS  ·  N=10", {
    x: 0.75, y: 0.9, w: 6, h: 0.32,
    fontFace: F.body, fontSize: 11, bold: true, charSpacing: 8,
    color: C.accent, margin: 0
  });

  s.addText([
    { text: "Ensemble ", options: { color: C.ink } },
    { text: "matches stuffing ", options: { color: C.ink } },
    { text: "at 64% the cost.", options: { color: C.accent, italic: true } },
  ], {
    x: 0.75, y: 1.22, w: 12, h: 1.0,
    fontFace: F.head, fontSize: 34, bold: true,
    lineSpacingMultiple: 1.05, margin: 0
  });

  // ==== LEFT — hand-drawn bar chart (full color control) ====
  const cx = 0.75, cy = 2.4, cw = 7.4, ch = 3.75;

  // card
  s.addShape(pres.shapes.RECTANGLE, {
    x: cx, y: cy, w: cw, h: ch,
    fill: { color: "FFFFFF" }, line: { color: C.rule, width: 0.5 }
  });

  s.addText("COST  PER  10  QUESTIONS  ($USD)", {
    x: cx + 0.3, y: cy + 0.2, w: cw - 0.6, h: 0.3,
    fontFace: F.body, fontSize: 9, bold: true, charSpacing: 6,
    color: C.muted, margin: 0
  });
  s.addText("quality score below each bar", {
    x: cx + 0.3, y: cy + 0.2, w: cw - 0.6, h: 0.3,
    fontFace: F.body, fontSize: 9, italic: true,
    color: C.muted, margin: 0, align: "right"
  });

  // plot area geometry
  const plotX = cx + 0.55, plotY = cy + 0.9;
  const plotW = cw - 0.8, plotH = 2.3;
  const maxCost = 1.0;

  // horizontal gridlines — spare, at 0.5 and 1.0 only (less crowding)
  [0.5, 1.0].forEach(v => {
    const gy = plotY + plotH - (v / maxCost) * plotH;
    s.addShape(pres.shapes.LINE, {
      x: plotX, y: gy, w: plotW, h: 0,
      line: { color: "EBE3D3", width: 0.5 }
    });
    s.addText(`$${v.toFixed(2)}`, {
      x: cx + 0.02, y: gy - 0.1, w: 0.5, h: 0.2,
      fontFace: F.body, fontSize: 7, color: C.muted,
      align: "right", margin: 0
    });
  });
  // zero line
  s.addShape(pres.shapes.LINE, {
    x: plotX, y: plotY + plotH, w: plotW, h: 0,
    line: { color: C.ink2, width: 0.75 }
  });

  const bars = [
    { l: "full_ctx",  cost: 0.670, q: 0.995, color: "3A342C", bold: false },
    { l: "meta_h",    cost: 0.431, q: 0.890, color: "3A342C", bold: false },
    { l: "rag",       cost: 0.141, q: 0.925, color: "3A342C", bold: false },
    { l: "hier",      cost: 0.118, q: 0.910, color: "3A342C", bold: false },
    { l: "agent",     cost: 0.320, q: 0.990, color: "3A342C", bold: false },
    { l: "cascade",   cost: 0.904, q: 0.925, color: "BEB09A", bold: false },  // de-emphasized (loser)
    { l: "ensemble",  cost: 0.428, q: 0.995, color: "D9512C", bold: true },   // winner — accent
    { l: "ORACLE",    cost: 0.138, q: 1.000, color: "8A6E3B", bold: true },   // ceiling — olive
  ];

  const n = bars.length;
  const gap = 0.08;
  const barW = (plotW - (n - 1) * gap) / n;

  bars.forEach((b, i) => {
    const x = plotX + i * (barW + gap);
    const h = (b.cost / maxCost) * plotH;
    const y = plotY + plotH - h;

    // bar
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: barW, h,
      fill: { color: b.color }, line: { color: b.color, width: 0 }
    });

    // cost label — always OUTSIDE above bar (simpler, consistent)
    s.addText(`$${b.cost.toFixed(2)}`, {
      x: x - 0.15, y: y - 0.26, w: barW + 0.3, h: 0.22,
      fontFace: F.body, fontSize: 9.5, bold: true,
      color: b.bold ? C.accent : C.ink, align: "center", margin: 0
    });

    // category label below bar
    s.addText(b.l, {
      x: x - 0.15, y: plotY + plotH + 0.06, w: barW + 0.3, h: 0.22,
      fontFace: F.body, fontSize: 9.5, bold: b.bold,
      color: b.bold ? C.ink : C.ink2, align: "center", margin: 0
    });

    // quality score — small muted italic beneath category label
    s.addText(`q ${b.q.toFixed(3)}`, {
      x: x - 0.15, y: plotY + plotH + 0.3, w: barW + 0.3, h: 0.2,
      fontFace: F.body, fontSize: 7.5, italic: true,
      color: C.muted, align: "center", margin: 0
    });
  });

  // ==== RIGHT — takeaways ====
  const tx = 8.4, ty = 2.5, tw = 4.3;

  const findings = [
    {
      h: "Ensemble wins as built",
      b: "hier ∥ agent_managed + judge → 0.995 quality @ $0.43. Beats full-context on cost, ties on quality."
    },
    {
      h: "Cascade self-verify fails",
      b: "$0.90 and 0.925 — worse than its own tier-2. Same-model verifier is over-confident on confidently-wrong outputs."
    },
    {
      h: "Oracle is only $0.29 away",
      b: "Picks hierarchical 9/10. A cross-model or learned router captures most of the ceiling."
    },
    {
      h: "Recency is table stakes",
      b: "All 7 strategies nail slack_contradicts at Sonnet 4.6. Recency got folded into the quality metric."
    },
  ];

  findings.forEach((f, i) => {
    const y = ty + i * 0.88;

    s.addText(String(i + 1).padStart(2, "0"), {
      x: tx, y: y + 0.02, w: 0.45, h: 0.35,
      fontFace: F.head, fontSize: 13, italic: true, color: C.accent, margin: 0
    });
    s.addText(f.h, {
      x: tx + 0.5, y: y, w: tw - 0.5, h: 0.35,
      fontFace: F.body, fontSize: 13, bold: true, color: C.ink, margin: 0
    });
    s.addText(f.b, {
      x: tx + 0.5, y: y + 0.33, w: tw - 0.5, h: 0.58,
      fontFace: F.body, fontSize: 10.5, color: C.ink2, lineSpacingMultiple: 1.25, margin: 0
    });
  });

  // verdict strip — placed below content, above footer
  const vy = 6.3;
  s.addShape(pres.shapes.LINE, {
    x: 0.75, y: vy, w: 12, h: 0,
    line: { color: C.accent, width: 1.25 }
  });
  s.addText([
    { text: "VERDICT  ",  options: { bold: true, color: C.accent, charSpacing: 4 } },
    { text: "Stuffing no longer wins by default. The cheapest win is a routed ensemble; a cross-model verifier closes the gap to oracle.",
      options: { italic: true, color: C.ink2 } },
  ], { x: 0.75, y: vy + 0.12, w: 12, h: 0.35,
       fontFace: F.body, fontSize: 11, margin: 0 });
}

const path = require("path");
const outPath = path.join(__dirname, "..", "assets", "xcbench_3slides.pptx");
pres.writeFile({ fileName: outPath }).then(n => console.log("wrote", n));
