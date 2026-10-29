/* Fame Half-Life: per-event measures and the three decay models, in the browser.
   A line-for-line port of scripts/fits.py, so a curve fitted here matches the published one.
   Series: daily views for days -60 ... +365 (index 60 is day 0); NaN after the last available day. */
(function (root) {
  "use strict";
  var PRE = 60, POST = 365, BASE = [-60, -8], PEAK = [0, 3], LIFT = [335, 365], MIN_LIFT_DAYS = 21, MIN_FIT_DAYS = 30;
  function idx(d) { return d + PRE; }
  function isnan(x) { return x !== x; }
  function nanmean(a) { var s = 0, n = 0; a.forEach(function (x) { if (!isnan(x)) { s += x; n++; } }); return n ? s / n : NaN; }
  function median(a) {
    var b = a.filter(function (x) { return !isnan(x); }).sort(function (p, q) { return p - q; });
    if (!b.length) return NaN;
    var m = b.length >> 1;
    return b.length % 2 ? b[m] : (b[m - 1] + b[m]) / 2;
  }

  function dowFactors(v, weekday0) {
    var w = v.map(function (_, k) { return (weekday0 + k) % 7; });
    var lo = idx(BASE[0]), hi = idx(BASE[1]) + 1;
    var vb = v.slice(lo, hi), wb = w.slice(lo, hi), m = nanmean(vb), f = [1, 1, 1, 1, 1, 1, 1];
    if (m > 0) {
      for (var d = 0; d < 7; d++) {
        var x = vb.filter(function (_, i) { return wb[i] === d; });
        if (x.length) f[d] = Math.min(2, Math.max(0.5, nanmean(x) / m));
      }
      var fm = f.reduce(function (s, x) { return s + x; }, 0) / 7;
      f = f.map(function (x) { return x / fm; });
    }
    return { f: f, w: w };
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

  function measures(views, weekday0, win) {
    win = win || 7;
    var v = views.slice(), df = dowFactors(v, weekday0);
    var a = v.map(function (x, i) { return x / df.f[df.w[i]]; });
    var base = median(a.slice(idx(BASE[0]), idx(BASE[1]) + 1));
    var pk = a.slice(idx(PEAK[0]), idx(PEAK[1]) + 1), pd = 0;
    for (var i = 1; i < pk.length; i++) if (pk[i] > pk[pd]) pd = i;
    var peakDay = pd + PEAK[0], peak = pk[pd];
    var ex = a.map(function (x) { return x - base; }), pex = peak - base;
    var out = { baseline: base, peak: peak, peakDay: peakDay, peakRatio: base > 0 ? peak / base : NaN,
                spike: base > 0 && pex > base, halfLife: NaN, halfLifeCensored: false, lift: NaN };
    if (pex > 0) {
      var sm = smooth(ex, win);
      for (var t = idx(peakDay) + 1; t < sm.length; t++) {
        if (!isnan(sm[t]) && sm[t] < 0.5 * pex) { out.halfLife = t - idx(peakDay); break; }
      }
      out.halfLifeCensored = isnan(out.halfLife);
      // Share of the first year's excess views (from the peak day on) that arrived more than a week after the peak.
      var tot = 0, late = 0;
      for (var k = idx(peakDay); k <= idx(POST); k++) {
        var e = isnan(ex[k]) ? 0 : Math.max(0, ex[k]);
        tot += e; if (k - idx(peakDay) >= 8) late += e;
      }
      out.lateShare = tot > 0 ? late / tot : NaN;
    }
    var lw = a.slice(idx(LIFT[0]), idx(LIFT[1]) + 1).filter(function (x) { return !isnan(x); });
    if (base > 0 && lw.length >= MIN_LIFT_DAYS) out.lift = median(lw) / base;
    return { m: out, adjusted: a, excess: ex };
  }

  function fitPoints(ex, peakDay) {
    var t = [], y = [];
    for (var k = 1; k <= POST - peakDay; k++) {
      var e = ex[idx(peakDay) + k];
      if (!isnan(e) && e > 0) { t.push(k); y.push(Math.log(e)); }
    }
    return { t: t, y: y };
  }
  function aic(rss, n, k) { return n * Math.log(rss / n) + 2 * (k + 1); }
  function ols(x, y) {
    var n = x.length, xm = 0, ym = 0, sxx = 0, sxy = 0, i;
    for (i = 0; i < n; i++) { xm += x[i]; ym += y[i]; }
    xm /= n; ym /= n;
    for (i = 0; i < n; i++) { sxx += (x[i] - xm) * (x[i] - xm); sxy += (x[i] - xm) * (y[i] - ym); }
    var b = sxx > 0 ? sxy / sxx : 0;
    return [ym - b * xm, b];
  }
  function fitExp(t, y) {
    var ab = ols(t, y), rss = 0;
    for (var i = 0; i < t.length; i++) rss += Math.pow(y[i] - (ab[0] + ab[1] * t[i]), 2);
    return { A: Math.exp(ab[0]), tau: ab[1] < 0 ? -1 / ab[1] : Infinity, rss: rss };
  }
  function fitPow(t, y) {
    var lt = t.map(Math.log), ab = ols(lt, y), rss = 0;
    for (var i = 0; i < t.length; i++) rss += Math.pow(y[i] - (ab[0] + ab[1] * lt[i]), 2);
    return { A: Math.exp(ab[0]), alpha: -ab[1], rss: rss };
  }
  function biRss(t, y, lt1, lt2, lw) {
    var t1 = Math.exp(lt1), t2 = Math.exp(lt2), w = 1 / (1 + Math.exp(-lw)), n = t.length;
    var ls = new Array(n), la = 0, i;
    for (i = 0; i < n; i++) {
      var s = w * Math.exp(-t[i] / t1) + (1 - w) * Math.exp(-t[i] / t2);
      if (!(s > 0)) return [Infinity, 0];
      ls[i] = Math.log(s); la += y[i] - ls[i];
    }
    la /= n;
    var rss = 0;
    for (i = 0; i < n; i++) rss += Math.pow(y[i] - la - ls[i], 2);
    return [rss, la];
  }
  function geom(a, b, n) { var out = []; for (var i = 0; i < n; i++) out.push(a * Math.pow(b / a, i / (n - 1))); return out; }
  var T1 = geom(0.3, 60, 16), T2 = geom(3, 3000, 18), W = geom(1e-4, 0.5, 14).map(function (x) { return 1 - x; });

  function nelderMead(f, x0, step, iters, tol) {
    step = step || 0.3; iters = iters || 400; tol = tol || 1e-9;
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

  function fitBiexp(t, y) {
    var best = [Infinity, null];
    T1.forEach(function (t1) {
      T2.forEach(function (t2) {
        if (t2 <= t1 * 1.5) return;
        W.forEach(function (w) {
          var q = [Math.log(t1), Math.log(t2), Math.log(w / (1 - w))], r = biRss(t, y, q[0], q[1], q[2])[0];
          if (r < best[0]) best = [r, q];
        });
      });
    });
    var p = nelderMead(function (q) { return q[0] < q[1] ? biRss(t, y, q[0], q[1], q[2])[0] : Infinity; }, best[1]);
    var r = biRss(t, y, p[0], p[1], p[2]);
    return { A: Math.exp(r[1]), tau1: Math.exp(p[0]), tau2: Math.exp(p[1]), w: 1 / (1 + Math.exp(-p[2])), rss: r[0] };
  }

  function fitAll(ex, peakDay) {
    var pts = fitPoints(ex, peakDay), n = pts.t.length;
    if (n < MIN_FIT_DAYS) return null;
    var e = fitExp(pts.t, pts.y), p = fitPow(pts.t, pts.y), b = fitBiexp(pts.t, pts.y);
    var out = { n: n, exp: e, pow: p, biexp: b, aic: { exp: aic(e.rss, n, 2), pow: aic(p.rss, n, 2), biexp: aic(b.rss, n, 4) } };
    out.best = ["exp", "pow", "biexp"].reduce(function (a, k) { return out.aic[k] < out.aic[a] ? k : a; }, "exp");
    return out;
  }

  function curve(f, model, t) {
    var m = f[model];
    if (model === "exp") return m.A * Math.exp(-t / m.tau);
    if (model === "pow") return m.A * Math.pow(t, -m.alpha);
    return m.A * (m.w * Math.exp(-t / m.tau1) + (1 - m.w) * Math.exp(-t / m.tau2));
  }

  var api = { PRE: PRE, POST: POST, measures: measures, fitAll: fitAll, curve: curve };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.FameFit = api;
})(this);
