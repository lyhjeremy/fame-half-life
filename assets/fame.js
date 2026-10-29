/* Fame Half-Life page script. Plain SVG, no libraries.
   Data: assets/data.json and assets/series/NN.json (scripts/export_web.py). Fits: assets/fit.js. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var BASE_URL = new URL(".", document.currentScript.src).href;
  var D = null, byId = {}, shardCache = {};
  var F = window.FameFit;
  var MODEL = { exp: "exponential", pow: "power law", biexp: "biexponential" };
  var MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, parent, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function clear(svg) { while (svg.lastChild && svg.lastChild.tagName !== "title") svg.removeChild(svg.lastChild); }
  function size(svg, h) {
    var w = Math.round(Math.max(320, Math.min(900, svg.parentNode.clientWidth || 900)));
    svg.setAttribute("viewBox", "0 0 " + w + " " + h);
    return w;
  }
  function lin(d0, d1, r0, r1) { return function (v) { return r0 + (v - d0) / (d1 - d0) * (r1 - r0); }; }
  function logs(d0, d1, r0, r1) { var a = Math.log(d0), b = Math.log(d1); return function (v) { return r0 + (Math.log(v) - a) / (b - a) * (r1 - r0); }; }
  function addDays(iso, n) { var t = new Date(iso + "T00:00:00Z"); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); }
  function fmtDate(iso) { var p = iso.split("-"); return +p[2] + " " + MON[+p[1] - 1] + " " + p[0]; }
  function fmtN(v) { return v == null || v !== v ? "n/a" : v >= 100 ? Math.round(v).toLocaleString("en-US") : v >= 10 ? v.toFixed(0) : v.toFixed(1); }
  function fmtX(v) { return v == null || v !== v ? "n/a" : (v >= 10 ? v.toFixed(0) : v.toFixed(2)) + "x"; }
  function logTicks(lo, hi) {
    var out = [], e0 = Math.floor(Math.log10(lo)), e1 = Math.ceil(Math.log10(hi)), steps = e1 - e0 <= 2 ? [1, 2, 5] : [1];
    for (var e = e0; e <= e1; e++) steps.forEach(function (s) { var v = s * Math.pow(10, e); if (v >= lo && v <= hi) out.push(v); });
    return out;
  }
  function fmtTick(v) { return v >= 1e6 ? v / 1e6 + "M" : v >= 1e3 ? v / 1e3 + "k" : String(+v.toPrecision(3)); }
  function segButtons(host, items, active, onPick) {
    host.innerHTML = "";
    items.forEach(function (it) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "btn"; b.textContent = it[1];
      b.setAttribute("aria-pressed", it[0] === active ? "true" : "false");
      b.addEventListener("click", function () {
        host.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", "false"); });
        b.setAttribute("aria-pressed", "true"); onPick(it[0]);
      });
      host.appendChild(b);
    });
  }

  /* ---------- One event: views, baseline, fitted decay, half-life ---------- */
  function analyse(views, wd0) {
    var r = F.measures(views, wd0, 7);
    var fit = r.m.spike ? F.fitAll(r.excess, r.m.peakDay) : null;
    return { views: views, m: r.m, fit: fit };
  }

  function drawEvent(svg, readout, ev, day0, range) {
    clear(svg);
    var H = 300, W = size(svg, H), L = 56, R = 16, T = 14, B = 34;
    var d0 = range === "zoom" ? -14 : -60, d1 = range === "zoom" ? 60 : 365;
    var x = lin(d0, d1, L, W - R);
    var vals = [], i, d;
    for (d = d0; d <= d1; d++) { var v = ev.views[d + 60]; if (v != null && v === v && v > 0) vals.push(v); }
    var m = ev.m, fit = ev.fit;
    if (m.baseline > 0) vals.push(m.baseline);
    var lo = Math.max(1, Math.min.apply(null, vals) * 0.8), hi = Math.max.apply(null, vals) * 1.25;
    var y = logs(lo, hi, H - B, T);
    var g = el("g", { "class": "grid" }, svg);
    logTicks(lo, hi).forEach(function (t) {
      el("line", { x1: L, x2: W - R, y1: y(t), y2: y(t) }, g);
      el("text", { x: L - 8, y: y(t) + 4, "text-anchor": "end", "font-size": 12 }, g, fmtTick(t));
    });
    var xt = range === "zoom" ? (W < 520 ? [-14, 0, 30, 60] : [-14, 0, 14, 30, 45, 60]) : (W < 520 ? [-60, 0, 90, 180, 365] : [-60, 0, 30, 90, 180, 270, 365]);
    xt.forEach(function (t) { el("text", { x: x(t), y: H - B + 20, "text-anchor": "middle", "font-size": 12 }, svg, t === 0 ? "day 0" : (t > 0 ? "+" : "") + t); });
    el("line", { x1: x(0), x2: x(0), y1: T, y2: H - B, "class": "base" }, svg);
    var pts = [];
    for (d = d0; d <= d1; d++) {
      var vv = ev.views[d + 60];
      if (vv == null || vv !== vv) continue;
      pts.push(x(d).toFixed(1) + "," + y(Math.max(lo, vv)).toFixed(1));
    }
    el("polyline", { points: pts.join(" "), "class": "s-raw" }, svg);
    if (m.baseline > 0) el("line", { x1: x(d0), x2: x(d1), y1: y(m.baseline), y2: y(m.baseline), "class": "s-gray s-dash" }, svg);
    if (fit) {
      var fp = [];
      for (d = m.peakDay + 1; d <= d1; d++) {
        if (d < d0) continue;
        var fv = m.baseline + F.curve(fit, fit.best, d - m.peakDay);
        if (fv >= lo && fv <= hi * 4) fp.push(x(d).toFixed(1) + "," + y(Math.min(hi, fv)).toFixed(1));
      }
      el("polyline", { points: fp.join(" "), "class": "s-red" }, svg);
    }
    if (m.halfLife === m.halfLife && m.peakDay + m.halfLife <= d1) {
      var hx = x(m.peakDay + m.halfLife);
      el("line", { x1: hx, x2: hx, y1: T, y2: H - B, "class": "s-blue" }, svg);
      el("text", { x: hx + 6, y: T + 12, "font-size": 12, "class": "lab" }, svg, "half-life " + m.halfLife + (m.halfLife === 1 ? " day" : " days"));
    }
    var cur = el("line", { x1: 0, x2: 0, y1: T, y2: H - B, "class": "cursor", visibility: "hidden" }, svg);
    function show(dd) {
      var vv = ev.views[dd + 60];
      cur.setAttribute("x1", x(dd)); cur.setAttribute("x2", x(dd)); cur.setAttribute("visibility", "visible");
      readout.textContent = "Day " + (dd > 0 ? "+" : "") + dd + " (" + fmtDate(addDays(day0, dd)) + "): " +
        (vv == null || vv !== vv ? "no data yet" : Math.round(vv).toLocaleString("en-US") + " views");
    }
    var at = 0;
    svg.onmousemove = function (e) {
      var r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
      var px = (e.clientX - r.left) / r.width * vb.width;
      at = Math.round(d0 + (px - L) / (W - R - L) * (d1 - d0)); at = Math.max(d0, Math.min(d1, at)); show(at);
    };
    svg.onkeydown = function (e) {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        at = Math.max(d0, Math.min(d1, at + (e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 10 : 1))); show(at); e.preventDefault();
      }
    };
    readout.textContent = "";
  }

  function statsHtml(ev) {
    var m = ev.m, f = ev.fit, hl;
    if (!m.spike) hl = "no spike";
    else if (m.halfLifeCensored) hl = "over a year";
    else hl = m.halfLife + (m.halfLife === 1 ? " day" : " days");
    var best = f ? MODEL[f.best] : (m.spike ? "too few days to fit" : "not fitted");
    function s(k, v, cls) { return '<div class="stat"><div class="k">' + k + '</div><div class="v' + (cls ? " " + cls : "") + '">' + v + "</div></div>"; }
    var late = m.lateShare === m.lateShare && m.lateShare != null ? Math.round(100 * m.lateShare) + "%" : "n/a";
    return s("Baseline", fmtN(m.baseline) + "/day") + s("Peak", fmtX(m.peakRatio)) + s("Half-life", hl, "hl") +
      s("After week one", late) + s("A year later", m.lift === m.lift ? fmtX(m.lift) : "not yet") + s("Best fit", best);
  }
  function noteFor(ev) {
    var m = ev.m, f = ev.fit, out = [];
    if (!m.spike) out.push("The peak was less than twice the baseline, so this counts as no visible spike and no curve is fitted.");
    if (f) {
      var o = ["exp", "pow", "biexp"].filter(function (k) { return k !== f.best; });
      var gap = Math.min(f.aic[o[0]], f.aic[o[1]]) - f.aic[f.best];
      out.push("The " + MODEL[f.best] + " curve fits best, by " + gap.toFixed(1) + " AIC points over the next model (" + f.n + " days above baseline).");
    }
    if (m.lift !== m.lift && m.baseline > 0) out.push("The lift needs at least 21 days between day +335 and +365, which have not happened yet.");
    return out.join(" ");
  }

  function renderEvent(prefix, ev, day0, label, sub) {
    $(prefix + "-who").innerHTML = "";
    $(prefix + "-who").appendChild(document.createTextNode(label));
    var sm = document.createElement("small"); sm.textContent = sub; $(prefix + "-who").appendChild(sm);
    $(prefix + "-stats").innerHTML = statsHtml(ev);
    $(prefix + "-note").textContent = noteFor(ev);
    var range = "full";
    var svg = $(prefix + "-svg"), ro = $(prefix + "-read");
    segButtons($(prefix + "-range"), [["full", "Days -60 to +365"], ["zoom", "Days -14 to +60"]], range, function (r) { range = r; drawEvent(svg, ro, ev, day0, r); });
    drawEvent(svg, ro, ev, day0, range);
    window.addEventListener("resize", function () { if ($(prefix + "-svg") === svg) drawEvent(svg, ro, ev, day0, range); });
  }

  /* ---------- Dataset search ---------- */
  var TYPE = { d: "death", a: "award" };
  function eventLabel(e) { return e[2] === "d" ? "Death, " + fmtDate(e[4]) : e[3] + ", " + fmtDate(e[4]); }
  function initSearch() {
    var input = $("ds-q"), list = $("ds-list");
    if (!input) return;
    D.events.forEach(function (e) {
      byId[e[0]] = e;
      var o = document.createElement("option");
      o.value = e[1] + " (" + (e[2] === "d" ? "death " + e[4].slice(0, 4) : e[3].replace("Academy Award for ", "Oscar, ").replace("Nobel Prize in ", "Nobel, ") + " " + e[4].slice(0, 4)) + ")";
      o.dataset.id = e[0];
      list.appendChild(o);
    });
    var opts = {};
    Array.prototype.forEach.call(list.options, function (o) { opts[o.value] = o.dataset.id; });
    function pick(id) {
      var e = byId[id];
      if (!e) return;
      $("ds-out").classList.add("hidden"); $("ds-sk").classList.remove("hidden"); $("ds-err").classList.add("hidden");
      loadShard(e[6]).then(function (sh) {
        var s = sh[id];
        var views = s.v.map(function (v) { return v == null ? NaN : v; });
        var ev = analyse(views, s.wd0);
        $("ds-sk").classList.add("hidden"); $("ds-out").classList.remove("hidden");
        renderEvent("ds", ev, e[4], e[1], eventLabel(e) + ", " + e[5]);
      }).catch(function () {
        $("ds-sk").classList.add("hidden");
        showErr("ds-err", "Could not load the stored series.", "Reload the page and try again.");
      });
    }
    function go() {
      var id = opts[input.value];
      if (!id) {
        var q = input.value.trim().toLowerCase();
        var hit = D.events.filter(function (e) { return e[1].toLowerCase().indexOf(q) === 0; })[0] ||
                  D.events.filter(function (e) { return e[1].toLowerCase().indexOf(q) >= 0; })[0];
        if (!q || !hit) { showErr("ds-err", "No match.", "The dataset holds " + D.events.length.toLocaleString("en-US") + " events; try a surname, or use the live box below for anyone else."); return; }
        id = hit[0];
      }
      pick(id);
    }
    input.addEventListener("change", go);
    $("ds-go").addEventListener("click", go);
    input.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); go(); } });
    var start = D.events.filter(function (e) { return e[1] === input.dataset.start; })[0];
    if (start) { input.value = Object.keys(opts).filter(function (k) { return opts[k] === start[0]; })[0]; pick(start[0]); }
  }
  function loadShard(k) {
    if (!shardCache[k]) shardCache[k] = fetch(BASE_URL + "series/" + (k < 10 ? "0" : "") + k + ".json").then(function (r) {
      if (!r.ok) throw new Error("shard"); return r.json();
    });
    return shardCache[k];
  }
  function showErr(id, lead, text) {
    var b = $(id); b.innerHTML = ""; var s = document.createElement("b"); s.textContent = lead + " ";
    b.appendChild(s); b.appendChild(document.createTextNode(text)); b.classList.remove("hidden");
  }

  /* ---------- Live lookup against the Wikimedia API ---------- */
  var FIRST = "2015-07-01";
  function ymd(iso) { return iso.replace(/-/g, ""); }
  function yesterday() { var t = new Date(); t.setUTCDate(t.getUTCDate() - 1); return t.toISOString().slice(0, 10); }
  function daysBetween(a, b) { return Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 864e5); }
  function LiveError(lead, text) { this.lead = lead; this.text = text; }
  function wmFetch(url) {
    return fetch(url, { referrerPolicy: "no-referrer", credentials: "omit" }).catch(function () {
      throw new LiveError("Could not reach Wikimedia.", "Check your connection and try again.");
    }).then(function (r) {
      if (r.status === 429) throw new LiveError("Wikimedia is limiting requests right now.", "Wait a minute and try again.");
      return r;
    });
  }
  function initLive() {
    var form = $("lv-form");
    if (!form) return;
    var busy = false;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (busy) return;
      var title = $("lv-title").value.trim(), date = $("lv-date").value;
      $("lv-err").classList.add("hidden");
      if (!title) { showErr("lv-err", "Type an article title.", "For example Queen Elizabeth II, or paste the part of the URL after /wiki/."); return; }
      title = decodeURIComponent(title.replace(/^https?:\/\/en\.(m\.)?wikipedia\.org\/wiki\//, "")).replace(/_/g, " ");
      var last = yesterday();
      if (date) {
        if (date < addDays(FIRST, 60)) { showErr("lv-err", "That date is too early.", "Pageview data starts on 1 July 2015, and the baseline needs the 60 days before the event, so pick a date on or after 30 August 2015."); return; }
        if (date > addDays(last, -3)) { showErr("lv-err", "That date is too recent.", "The peak is read over days 0 to +3, so pick a date at least four days ago."); return; }
      }
      busy = true; $("lv-go").disabled = true;
      $("lv-out").classList.add("hidden"); $("lv-sk").classList.remove("hidden");
      var resolved;
      wmFetch("https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&redirects=1&origin=*&titles=" + encodeURIComponent(title))
        .then(function (r) {
          if (!r.ok) throw new LiveError("Wikipedia did not answer.", "It returned status " + r.status + ". Try again in a moment.");
          return r.json();
        }).then(function (j) {
          var p = j.query && j.query.pages && j.query.pages[0];
          if (!p || p.invalid) throw new LiveError("That is not a valid article title.", "Check for stray characters such as # or [ ].");
          if (p.missing) throw new LiveError("No English Wikipedia article has that title.", "Check the spelling, or copy the title from the article's address bar.");
          if (p.ns !== 0) throw new LiveError("That page is not an article.", "Only main-space articles have the pageview series used here.");
          resolved = p.title;
          return wmFetch("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/" +
            encodeURIComponent(resolved.replace(/ /g, "_")) + "/daily/" + ymd(FIRST) + "/" + ymd(last));
        }).then(function (r) {
          if (r.status === 404) throw new LiveError("Wikimedia has no pageview data for " + resolved + ".", "Very new articles can take a day to appear.");
          if (!r.ok) throw new LiveError("The pageview service did not answer.", "It returned status " + r.status + ". Try again in a moment.");
          return r.json();
        }).then(function (j) {
          var byDay = {};
          (j.items || []).forEach(function (it) { byDay[it.timestamp.slice(0, 8)] = it.views; });
          var keys = Object.keys(byDay).sort();
          if (!keys.length) throw new LiveError("Wikimedia has no pageview data for " + resolved + ".", "Very new articles can take a day to appear.");
          var firstDay = keys[0].slice(0, 4) + "-" + keys[0].slice(4, 6) + "-" + keys[0].slice(6, 8);
          var day0 = date, auto = false;
          if (!day0) {
            // No date given: use the busiest day that leaves 60 days of history before it.
            var from = firstDay > addDays(FIRST, 60) ? addDays(firstDay, 60) : addDays(FIRST, 60), best = null, bv = -1;
            for (var d = from; d <= addDays(last, -3); d = addDays(d, 1)) { var v = byDay[ymd(d)] || 0; if (v > bv) { bv = v; best = d; } }
            if (!best) throw new LiveError("This article is too new.", "It needs 60 days of views before an event, plus four days after it.");
            day0 = best; auto = true;
          } else if (addDays(date, -60) < firstDay) {
            throw new LiveError("No baseline for that date.", resolved + " has views only from " + fmtDate(firstDay) + ", and the baseline needs the 60 days before the event.");
          }
          var views = [];
          for (var k = -60; k <= 365; k++) { var dd = addDays(day0, k); views.push(dd > last ? NaN : (byDay[ymd(dd)] || 0)); }
          var wd0 = new Date(addDays(day0, -60) + "T00:00:00Z").getUTCDay(); wd0 = (wd0 + 6) % 7;
          var ev = analyse(views, wd0);
          $("lv-sk").classList.add("hidden"); $("lv-out").classList.remove("hidden");
          renderEvent("lv", ev, day0, resolved, (auto ? "Busiest day since July 2015: " : "Event date: ") + fmtDate(day0));
        }).catch(function (err) {
          $("lv-sk").classList.add("hidden");
          if (err instanceof LiveError) showErr("lv-err", err.lead, err.text);
          else showErr("lv-err", "Something went wrong.", "The data came back in a form this page did not expect. Try again.");
        }).then(function () { busy = false; $("lv-go").disabled = false; });
    });
  }

  /* ---------- Averaged curves ---------- */
  function drawAvg(range) {
    var svg = $("avg"); if (!svg) return;
    clear(svg);
    var H = 320, W = size(svg, H), L = 52, R = 16, T = 14, B = 34, a = D.avg;
    var d0 = range === "zoom" ? -14 : -60, d1 = range === "zoom" ? 60 : 365;
    var x = lin(d0, d1, L, W - R), lo = 0.5, hi = 1, i;
    a.day.forEach(function (d, i) { if (d >= d0 && d <= d1) { hi = Math.max(hi, a.death_p75[i] || 0, a.award_p75[i] || 0); } });
    hi *= 1.2;
    var y = logs(lo, hi, H - B, T), g = el("g", { "class": "grid" }, svg);
    [0.5, 1, 2, 5, 10, 20, 50, 100, 200].filter(function (t) { return t >= lo && t <= hi; }).forEach(function (t) {
      el("line", { x1: L, x2: W - R, y1: y(t), y2: y(t) }, g);
      el("text", { x: L - 8, y: y(t) + 4, "text-anchor": "end", "font-size": 12 }, g, t + "x");
    });
    (range === "zoom" ? (W < 520 ? [-14, 0, 30, 60] : [-14, 0, 14, 30, 45, 60]) : (W < 520 ? [-60, 0, 90, 180, 365] : [-60, 0, 30, 90, 180, 270, 365])).forEach(function (t) {
      el("text", { x: x(t), y: H - B + 20, "text-anchor": "middle", "font-size": 12 }, svg, t === 0 ? "day 0" : (t > 0 ? "+" : "") + t);
    });
    el("line", { x1: x(d0), x2: x(d1), y1: y(1), y2: y(1), "class": "s-gray s-dash" }, svg);
    [["award", "blue"], ["death", "red"]].forEach(function (s) {
      var up = [], dn = [], ln = [];
      a.day.forEach(function (d, i) {
        if (d < d0 || d > d1) return;
        up.push(x(d).toFixed(1) + "," + y(Math.max(lo, a[s[0] + "_p75"][i])).toFixed(1));
        dn.unshift(x(d).toFixed(1) + "," + y(Math.max(lo, a[s[0] + "_p25"][i])).toFixed(1));
        ln.push(x(d).toFixed(1) + "," + y(Math.max(lo, a[s[0] + "_median"][i])).toFixed(1));
      });
      el("polygon", { points: up.concat(dn).join(" "), "class": "band-" + s[1] }, svg);
      el("polyline", { points: ln.join(" "), "class": "s-" + s[1] }, svg);
    });
    var cur = el("line", { x1: 0, x2: 0, y1: T, y2: H - B, "class": "cursor", visibility: "hidden" }, svg), at = 0;
    function show(d) {
      var i = d + 60;
      cur.setAttribute("x1", x(d)); cur.setAttribute("x2", x(d)); cur.setAttribute("visibility", "visible");
      $("avg-read").textContent = "Day " + (d > 0 ? "+" : "") + d + ": deaths " + fmtX(a.death_median[i]) + ", awards " + fmtX(a.award_median[i]) + " (median multiple of baseline)";
    }
    svg.onmousemove = function (e) {
      var r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal, px = (e.clientX - r.left) / r.width * vb.width;
      at = Math.max(d0, Math.min(d1, Math.round(d0 + (px - L) / (W - R - L) * (d1 - d0)))); show(at);
    };
    svg.onkeydown = function (e) {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") { at = Math.max(d0, Math.min(d1, at + (e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 10 : 1))); show(at); e.preventDefault(); }
    };
  }

  /* ---------- Model wins ---------- */
  function drawWins() {
    var svg = $("wins"); if (!svg) return;
    clear(svg);
    var rows = D.wins.filter(function (w) { return w.sample !== "all"; }).concat(D.wins.filter(function (w) { return w.sample === "all"; }));
    var H = 40 + rows.length * 44, W = size(svg, H), L = W < 520 ? 92 : 130, R = 12, T = 10;
    var x = lin(0, 1, L, W - R), names = { all: "All events", death: "Deaths", award: "Awards" };
    var order = [["biexp", "f-blue", "biexponential"], ["pow", "f-red", "power law"], ["exp", "f-gray", "exponential"]];
    rows.forEach(function (w, i) {
      var y0 = T + i * 44, left = 0;
      el("text", { x: L - 8, y: y0 + 16, "text-anchor": "end", "class": "lab" }, svg, names[w.sample]);
      el("text", { x: L - 8, y: y0 + 30, "text-anchor": "end", "font-size": 11 }, svg, "n = " + w.n.toLocaleString("en-US"));
      order.forEach(function (o) {
        var v = w[o[0]];
        var r = el("rect", { x: x(left), y: y0, width: Math.max(0, x(left + v) - x(left)), height: 30, "class": o[1] }, svg);
        el("title", {}, r, o[2] + ": " + (100 * v).toFixed(1) + "%");
        if (x(left + v) - x(left) > 38) el("text", { x: (x(left) + x(left + v)) / 2, y: y0 + 20, "text-anchor": "middle", "font-size": 12, style: "fill:var(--paper)" }, svg, Math.round(100 * v) + "%");
        left += v;
      });
    });
    [0, 0.25, 0.5, 0.75, 1].forEach(function (t) { el("text", { x: x(t), y: H - 6, "text-anchor": "middle", "font-size": 11 }, svg, (100 * t) + "%"); });
  }

  /* ---------- Lift distribution ---------- */
  function drawLift() {
    var svg = $("lift"); if (!svg) return;
    clear(svg);
    var H = 280, W = size(svg, H), L = 48, R = 12, T = 12, B = 40, e = D.lift.edges;
    var x = logs(e[0], e[e.length - 1], L, W - R), hi = 0;
    var sh = {};
    ["death", "award"].forEach(function (t) { var n = D.lift[t + "_n"]; sh[t] = D.lift[t].map(function (c) { return c / n; }); hi = Math.max.apply(null, [hi].concat(sh[t])); });
    var y = lin(0, hi * 1.1, H - B, T), g = el("g", { "class": "grid" }, svg);
    [0, 0.05, 0.1, 0.15, 0.2, 0.25].filter(function (t) { return t <= hi * 1.1; }).forEach(function (t) {
      el("line", { x1: L, x2: W - R, y1: y(t), y2: y(t) }, g);
      el("text", { x: L - 6, y: y(t) + 4, "text-anchor": "end", "font-size": 11 }, g, Math.round(t * 100) + "%");
    });
    [0.125, 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64].forEach(function (t) {
      el("text", { x: x(t), y: H - B + 18, "text-anchor": "middle", "font-size": 11 }, svg, (t < 1 ? "1/" + (1 / t) : t) + "x");
    });
    el("line", { x1: x(1), x2: x(1), y1: T, y2: H - B, "class": "s-gray s-dash" }, svg);
    [["award", "blue"], ["death", "red"]].forEach(function (s) {
      var p = [];
      sh[s[0]].forEach(function (v, i) { p.push(x(e[i]).toFixed(1) + "," + y(v).toFixed(1)); p.push(x(e[i + 1]).toFixed(1) + "," + y(v).toFixed(1)); });
      el("polyline", { points: p.join(" "), "class": "s-" + s[1] }, svg);
    });
    el("text", { x: (L + W - R) / 2, y: H - 4, "text-anchor": "middle", "font-size": 12 }, svg, "views on days +335 to +365, as a multiple of baseline");
  }

  /* ---------- Groups ---------- */
  function drawGroups(metric) {
    var svg = $("groups"); if (!svg) return;
    clear(svg);
    var rows = D.groups.filter(function (g) { return g.n >= 15 && g[metric] != null; });
    rows.sort(function (a, b) { return (a.kind === b.kind ? 0 : a.kind === "event" ? -1 : 1) || b[metric] - a[metric]; });
    var H = 30 + rows.length * 26 + 32, W = size(svg, H), L = W < 520 ? 150 : 210, R = 50, T = 10;
    var vals = rows.map(function (r) { return r[metric]; }), lo = 0, hi = Math.max.apply(null, vals) * 1.1;
    var logx = metric === "lift";
    if (logx) { lo = Math.min(0.5, Math.min.apply(null, vals) * 0.8); hi = Math.max(2, hi); }
    var x = logx ? logs(lo, hi, L, W - R) : lin(lo, hi, L, W - R);
    var ref = logx ? 1 : null;
    if (ref) el("line", { x1: x(ref), x2: x(ref), y1: T, y2: H - 20, "class": "s-gray s-dash" }, svg);
    var ticks = logx ? [0.5, 1, 2, 4].filter(function (t) { return t >= lo && t <= hi; }) : niceTicks(0, hi, 4);
    function fv(v) { return logx ? fmtX(v) : Math.round(100 * v) + "%"; }
    ticks.forEach(function (t) { el("text", { x: x(t), y: H - 4, "text-anchor": "middle", "font-size": 11 }, svg, logx ? t + "x" : Math.round(100 * t) + "%"); });
    var prevKind = rows.length ? rows[0].kind : null;
    rows.forEach(function (r, i) {
      var y0 = T + i * 26 + 12 + (r.kind !== rows[0].kind ? 26 : 0);
      if (r.kind !== prevKind) {
        el("line", { x1: 0, x2: W - R, y1: y0 - 34, y2: y0 - 34, "class": "base" }, svg);
        el("text", { x: 0, y: y0 - 18, "font-size": 11, "font-style": "italic" }, svg, "Deaths, by occupation");
        prevKind = r.kind;
      }
      var name = r.label;
      el("text", { x: L - 10, y: y0 + 4, "text-anchor": "end", "class": "lab", "font-size": 12 }, svg, name);
      el("line", { x1: x(logx ? lo : 0), x2: x(r[metric]), y1: y0, y2: y0, "class": "grid-l", stroke: "var(--rule)" }, svg);
      el("circle", { cx: x(r[metric]), cy: y0, r: 5, "class": r.kind === "event" && r.label !== "Death" ? "f-blue" : "f-red" }, svg);
      el("text", { x: x(r[metric]) + 9, y: y0 + 4, "font-size": 11 }, svg, fv(r[metric]) + "  n=" + r.n);
    });
  }
  function niceTicks(lo, hi, n) {
    var span = hi - lo, step = Math.pow(10, Math.floor(Math.log10(span / n))), err = span / n / step;
    step *= err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1;
    var out = []; for (var v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
    return out;
  }

  function initCharts() {
    var avgRange = "full";
    if ($("avg-range")) segButtons($("avg-range"), [["full", "Days -60 to +365"], ["zoom", "Days -14 to +60"]], avgRange, function (r) { avgRange = r; drawAvg(r); });
    drawAvg(avgRange); drawWins(); drawLift();
    var gm = $("groups-metric") ? $("groups-metric").dataset.start || "late" : "late";
    if ($("groups-metric")) segButtons($("groups-metric"), [["late", "Extra views after week one"], ["lift", "Lift after a year"]], gm, function (m) { gm = m; drawGroups(m); });
    drawGroups(gm);
    var t;
    window.addEventListener("resize", function () { clearTimeout(t); t = setTimeout(function () { drawAvg(avgRange); drawWins(); drawLift(); drawGroups(gm); }, 150); });
  }

  initLive();
  fetch(BASE_URL + "data.json").then(function (r) { return r.json(); }).then(function (d) {
    D = d;
    document.querySelectorAll("[data-loading]").forEach(function (n) { n.classList.add("hidden"); });
    initSearch(); initCharts();
  }).catch(function () {
    document.querySelectorAll("[data-loading]").forEach(function (n) { n.textContent = "The chart data did not load. Reload the page to try again."; n.classList.remove("skeleton"); });
  });
})();
