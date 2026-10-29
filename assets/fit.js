/* Fame Half-Life: per-event measures and the three decay models, in the browser.
   A line-for-line port of scripts/fits.py (post-audit version, 2026-10-29), so a curve fitted
   here matches the published one; scripts/check_fit_parity.py compares the two.
   Series: daily views for days -60 ... +365 (index 60 is day 0); NaN after the last available day. */
(function (root) {
  "use strict";
  var PRE = 60, POST = 365, BASE = [-60, -8], PEAK = [0, 3], DELAY = [4, 30], LIFT = [335, 365];
  var MIN_LIFT_DAYS = 21, MIN_FIT_DAYS = 30;
  function idx(d) { return d + PRE; }
  function isnan(x) { return x !== x; }
  function nanmean(a) { var s = 0, n = 0; a.forEach(function (x) { if (!isnan(x)) { s += x; n++; } }); return n ? s / n : NaN; }
  function median(a) {
    var b = a.filter(function (x) { return !isnan(x); }).sort(function (p, q) { return p - q; });
    if (!b.length) return NaN;
    var m = b.length >> 1;
    return b.length % 2 ? b[m] : (b[m - 1] + b[m]) / 2;
  }
  function nanargmax(a) { var bi = -1; for (var i = 0; i < a.length; i++) if (!isnan(a[i]) && (bi < 0 || a[i] > a[bi])) bi = i; return bi; }

  function dowFactors(vb, wd0) {
    var wb = vb.map(function (_, k) { return (wd0 + k) % 7; }), m = nanmean(vb), f = [1, 1, 1, 1, 1, 1, 1];
    if (m > 0) {
      for (var d = 0; d < 7; d++) {
        var x = vb.filter(function (_, i) { return wb[i] === d; });
        if (x.length) f[d] = Math.min(2, Math.max(0.5, nanmean(x) / m));
      }
      var fm = f.reduce(function (s, x) { return s + x; }, 0) / 7;
      f = f.map(function (x) { return x / fm; });
    }
    return f;
  }

  function smooth(x, win) {
    var out = x.map(function () { return NaN; }), h = win >> 1;
    for (var i = h; i < x.length - (win - 1 - h); i++) {
      var s = 0, bad = false;
      for (var j = i - h; j < i - h + win; j++) { if (isnan(x[j])) { bad = true; break; } s += x[j]; }
      if (!bad) out[i] = s / win;
    }
    return out;
  }
  function firstBelow(x, start, level) {
    for (var t = start + 1; t < x.length; t++) if (!isnan(x[t]) && x[t] < level) return t - start;
    return NaN;
  }

  /* base: optional {v: views, wd0: weekday} of another window for the baseline and day-of-week factors. */
  function measures(views, weekday0, win, base) {
    win = win || 7;
    var v = views.slice(), w = v.map(function (_, k) { return (weekday0 + k) % 7; }), f, baseline = null;
    if (base) {
      f = dowFactors(base.v, base.wd0);
      baseline = median(base.v.map(function (x, k) { return x / f[(base.wd0 + k) % 7]; }));
    } else {
      f = dowFactors(v.slice(idx(BASE[0]), idx(BASE[1]) + 1), weekday0);
    }
    var a = v.map(function (x, i) { return x / f[w[i]]; });
    if (baseline === null) baseline = median(a.slice(idx(BASE[0]), idx(BASE[1]) + 1));
    var pk = a.slice(idx(PEAK[0]), idx(PEAK[1]) + 1), pd = nanargmax(pk);
    var peakDay = pd + PEAK[0], peak = pk[pd];
    var ex = a.map(function (x) { return x - baseline; }), pex = peak - baseline;
    var spike = baseline > 0 && pex > baseline, kind = spike ? "spike" : "none";
    if (!spike && baseline > 0) {
      var late = a.slice(idx(DELAY[0]), idx(DELAY[1]) + 1), li = nanargmax(late);
      if (li >= 0 && late[li] > 2 * baseline) kind = "delayed";
    }
    var out = { baseline: baseline, peak: peak, peakDay: peakDay, peakRatio: baseline > 0 ? peak / baseline : NaN,
                spike: spike, spikeKind: kind, halfLife: NaN, halfLifeRaw: NaN, halfLifeCensored: false,
                smoothPeakDay: NaN, lateShare: NaN, lift: NaN };
    if (pex > 0) {
      var sm = smooth(ex, win), spk = sm.slice(idx(PEAK[0]), idx(PEAK[1]) + 1), si = nanargmax(spk);
      if (si >= 0) {
        out.smoothPeakDay = si + PEAK[0];
        out.halfLife = firstBelow(sm, idx(out.smoothPeakDay), 0.5 * spk[si]);
        out.halfLifeCensored = isnan(out.halfLife);
      }
      out.halfLifeRaw = firstBelow(ex, idx(peakDay), 0.5 * pex);
      var tot = 0, lt = 0;
      for (var k = idx(peakDay); k <= idx(POST); k++) {
        var e = isnan(ex[k]) ? 0 : Math.max(0, ex[k]);
        tot += e; if (k - idx(peakDay) >= 8) lt += e;
      }
      if (tot > 0) out.lateShare = lt / tot;
    }
    var lw = a.slice(idx(LIFT[0]), idx(LIFT[1]) + 1).filter(function (x) { return !isnan(x); });
    if (baseline > 0 && lw.length >= MIN_LIFT_DAYS) out.lift = median(lw) / baseline;
    return { m: out, adjusted: a, excess: ex };
  }

  /* ---- decay models: log(1 + a_t) against log(1 + b + f(t)) on every day after the peak ---- */
  function fitPoints(a, peakDay) {
    var t = [], y = [];
    for (var k = 1; k <= POST - peakDay; k++) {
      var x = a[idx(peakDay) + k];
      if (!isnan(x)) { t.push(k); y.push(Math.log1p(Math.max(x, 0))); }
    }
    return { t: t, y: y };
  }
  function curveAt(model, p, t) {
    if (model === "exp") return Math.exp(p[0]) * Math.exp(-t / Math.exp(p[1]));
    if (model === "pow") return Math.exp(p[0]) * Math.pow(t, -Math.exp(p[1]));
    var w = 1 / (1 + Math.exp(-p[3]));
    return Math.exp(p[0]) * (w * Math.exp(-t / Math.exp(p[1])) + (1 - w) * Math.exp(-t / Math.exp(p[2])));
  }
  function rss(model, p, t, y, b) {
    if (model === "biexp" && !(p[1] < p[2])) return Infinity;
    var s = 0;
    for (var i = 0; i < t.length; i++) { var r = y[i] - Math.log1p(b + curveAt(model, p, t[i])); s += r * r; }
    return isFinite(s) ? s : Infinity;
  }
  function geom(a, b, n) { var out = []; for (var i = 0; i < n; i++) out.push(a * Math.pow(b / a, i / (n - 1))); return out; }
  var DA = [], i0; for (i0 = 0; i0 < 9; i0++) DA.push(-2 + 0.5 * i0);
  var TAU = geom(0.3, 3000, 30), ALPHA = geom(0.05, 5, 30), TAU1 = geom(0.3, 30, 10), TAU2 = geom(3, 3000, 12);
  var WS = geom(1e-3, 0.5, 8).map(function (x) { return 1 - x; });
  function grids(a0) {
    var la = DA.map(function (d) { return Math.log(a0) + d; }), g = { exp: [], pow: [], biexp: [] };
    la.forEach(function (x) { TAU.forEach(function (tau) { g.exp.push([x, Math.log(tau)]); }); });
    la.forEach(function (x) { ALPHA.forEach(function (al) { g.pow.push([x, Math.log(al)]); }); });
    la.forEach(function (x) { TAU1.forEach(function (t1) { TAU2.forEach(function (t2) {
      if (t2 > 1.5 * t1) WS.forEach(function (w) { g.biexp.push([x, Math.log(t1), Math.log(t2), Math.log(w / (1 - w))]); });
    }); }); });
    return g;
  }
  function aic(r, n, k) { return n * Math.log(r / n) + 2 * (k + 1); }

  function nelderMead(f, x0, step, iters, tol) {
    step = step || 0.3; iters = iters || 600; tol = tol || 1e-10;
    var n = x0.length, pts = [x0.slice()], vals, i, j;
    for (i = 0; i < n; i++) { var p = x0.slice(); p[i] += step; pts.push(p); }
    vals = pts.map(f);
    for (var it = 0; it < iters; it++) {
      var order = pts.map(function (_, k) { return k; }).sort(function (p, q) { return vals[p] - vals[q]; });
      pts = order.map(function (k) { return pts[k]; }); vals = order.map(function (k) { return vals[k]; });
      if (Math.abs(vals[n] - vals[0]) <= tol * (Math.abs(vals[0]) + tol)) break;
      var c = [];
      for (j = 0; j < n; j++) { var s = 0; for (i = 0; i < n; i++) s += pts[i][j]; c.push(s / n); }
      var xr = c.map(function (cj, k) { return cj + (cj - pts[n][k]); }), fr = f(xr);
      if (fr < vals[0]) {
        var xe = c.map(function (cj, k) { return cj + 2 * (cj - pts[n][k]); }), fe = f(xe);
        if (fe < fr) { pts[n] = xe; vals[n] = fe; } else { pts[n] = xr; vals[n] = fr; }
      } else if (fr < vals[n - 1]) { pts[n] = xr; vals[n] = fr; }
      else {
        var xc = c.map(function (cj, k) { return cj + 0.5 * (pts[n][k] - cj); }), fc = f(xc);
        if (fc < vals[n]) { pts[n] = xc; vals[n] = fc; }
        else {
          for (i = 1; i <= n; i++) {
            pts[i] = pts[i].map(function (x, k) { return pts[0][k] + 0.5 * (x - pts[0][k]); });
            vals[i] = f(pts[i]);
          }
        }
      }
    }
    var bi = 0; for (i = 1; i <= n; i++) if (vals[i] < vals[bi]) bi = i;
    return pts[bi];
  }

  var K = { exp: 2, pow: 2, biexp: 4 };
  function fitAll(a, baseline, peakDay) {
    var pts = fitPoints(a, peakDay), t = pts.t, y = pts.y, n = t.length;
    if (n < MIN_FIT_DAYS) return null;
    var x1 = a[idx(peakDay) + 1], a0 = isnan(x1) ? 1 : Math.max(x1 - baseline, 1), G = grids(a0);
    var out = { n: n, params: {}, rss: {}, aic: {} };
    ["exp", "pow", "biexp"].forEach(function (m) {
      var best = Infinity, start = null;
      G[m].forEach(function (g) { var r = rss(m, g, t, y, baseline); if (r < best) { best = r; start = g; } });
      var p = nelderMead(function (q) { return rss(m, q, t, y, baseline); }, start);
      out.params[m] = p; out.rss[m] = rss(m, p, t, y, baseline); out.aic[m] = aic(out.rss[m], n, K[m]);
    });
    out.best = ["exp", "pow", "biexp"].reduce(function (b, k) { return out.aic[k] < out.aic[b] ? k : b; }, "exp");
    return out;
  }
  function curve(fit, model, t) { return curveAt(model, fit.params[model], t); }

  var api = { PRE: PRE, POST: POST, measures: measures, fitAll: fitAll, curve: curve };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.FameFit = api;
})(this);
