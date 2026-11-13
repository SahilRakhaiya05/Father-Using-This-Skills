/* mg.js — tiny deterministic motion runtime for HTML scenes.
 * Part of the motion-graphics skill. Licensed under the MIT License.
 *
 * Contract: every pixel is a pure function of time. The renderer calls
 * window.__mg.seek(t) for each frame; nothing here reads a clock, a timer
 * or unseeded randomness. Opening the page in a browser plays a preview
 * that calls the very same seek().
 */
(function () {
  "use strict";
  var clamp = function (v, a, b) { return v < a ? a : v > b ? b : v; };
  var lerp = function (a, b, p) { return a + (b - a) * p; };

  var EASE = {
    linear: function (p) { return p; },
    in: function (p) { return p * p * p; },
    out: function (p) { return 1 - Math.pow(1 - p, 3); },
    inout: function (p) { return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2; },
    smooth: function (p) { return p * p * (3 - 2 * p); },
    snap: function (p) { return 1 - Math.pow(1 - p, 5); },
    expo: function (p) { return p >= 1 ? 1 : 1 - Math.pow(2, -10 * p); },
    back: function (p) { var c = 1.70158; return 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2); },
    elastic: function (p) {
      if (p <= 0 || p >= 1) return clamp(p, 0, 1);
      return Math.pow(2, -10 * p) * Math.sin((p * 10 - 0.75) * (2 * Math.PI / 3)) + 1;
    },
    bounce: function (p) {
      var n = 7.5625, d = 2.75;
      if (p < 1 / d) return n * p * p;
      if (p < 2 / d) return n * (p -= 1.5 / d) * p + 0.75;
      if (p < 2.5 / d) return n * (p -= 2.25 / d) * p + 0.9375;
      return n * (p -= 2.625 / d) * p + 0.984375;
    },
    steps: function (p) { return Math.floor(p * 8) / 8; }
  };

  /* from-states; identity is {o:1,x:0,y:0,s:1,r:0,b:0}. x/y are in stage units (1 = 1/1080 of the short side). */
  var PRESET = {
    fade: { o: 0 },
    rise: { o: 0, y: 48 },
    drop: { o: 0, y: -48 },
    left: { o: 0, x: -80 },
    right: { o: 0, x: 80 },
    scale: { o: 0, s: 0.82 },
    pop: { o: 0, s: 0.4, ease: "back" },
    "zoom-out": { o: 0, s: 1.35 },
    blur: { o: 0, b: 18 },
    tilt: { o: 0, r: -7, y: 36 },
    slam: { o: 0, s: 2.2, ease: "snap" },
    wipe: { clip: "right" },
    "wipe-up": { clip: "top" },
    "wipe-down": { clip: "bottom" },
    reveal: { clip: "top", y: 30 },
    bar: { sx: 0, origin: "left center" },
    grow: { sy: 0, origin: "center bottom" },
    type: { special: "type" },
    count: { special: "count" },
    draw: { special: "draw" },
    none: {}
  };

  var LOOPS = {
    float: function (t, a, per) { return { y: Math.sin(t / per * 2 * Math.PI) * a }; },
    drift: function (t, a, per) { return { x: Math.sin(t / per * 2 * Math.PI) * a, y: Math.cos(t / per * 2 * Math.PI) * a * 0.5 }; },
    pulse: function (t, a, per) { return { s: 1 + Math.sin(t / per * 2 * Math.PI) * a / 100 }; },
    spin: function (t, a, per) { return { r: (t / per) * 360 }; },
    sway: function (t, a, per) { return { r: Math.sin(t / per * 2 * Math.PI) * a / 4 }; }
  };

  function rand(seed) { /* mulberry32: seeded, repeatable */
    var a = (seed >>> 0) || 1;
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function num(el, name, dflt) {
    var v = el.getAttribute("data-" + name);
    if (v === null || v === "") return dflt;
    var n = parseFloat(v);
    return isNaN(n) ? dflt : n;
  }
  function str(el, name, dflt) {
    var v = el.getAttribute("data-" + name);
    return v === null || v === "" ? dflt : v;
  }
  function prog(t, at, dur, ease) {
    var p = dur <= 0 ? (t >= at ? 1 : 0) : clamp((t - at) / dur, 0, 1);
    return (EASE[ease] || EASE.out)(p);
  }

  var M = { fps: 30, width: 1920, height: 1080, duration: 0, scenes: [], hooks: [], sceneHooks: [], u: 1 };
  var body, stage, render;

  function splitText(el, mode) {
    var parts = [];
    var walk = function (node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (child) {
        if (child.nodeType === 3) {
          var frag = document.createDocumentFragment();
          child.nodeValue.split(/(\s+)/).forEach(function (tok) {
            if (!tok) return;
            if (/^\s+$/.test(tok)) { frag.appendChild(document.createTextNode(" ")); return; }
            var w = document.createElement("span");
            w.className = "mg-w"; w.style.display = "inline-block"; w.style.whiteSpace = "nowrap";
            if (mode === "chars") {
              Array.from(tok).forEach(function (ch) {
                var c = document.createElement("span");
                c.className = "mg-c"; c.style.display = "inline-block"; c.textContent = ch;
                w.appendChild(c); parts.push(c);
              });
            } else { w.textContent = tok; parts.push(w); }
            frag.appendChild(w);
          });
          node.replaceChild(frag, child);
        } else if (child.nodeType === 1 && child.tagName !== "BR") { walk(child); }
      });
    };
    walk(el);
    return parts;
  }

  function build() {
    body = document.body;
    stage = document.getElementById("stage");
    M.fps = num(body, "fps", 30);
    M.width = num(body, "width", 1920);
    M.height = num(body, "height", 1080);
    M.u = Math.min(M.width, M.height) / 1080;
    var cs = getComputedStyle(document.documentElement);
    var dDur = parseFloat(cs.getPropertyValue("--mg-dur")) || 0.6;
    var dEase = (cs.getPropertyValue("--mg-ease") || "out").trim() || "out";
    var dStag = parseFloat(cs.getPropertyValue("--mg-stagger")) || 0.06;
    var dAnim = (cs.getPropertyValue("--mg-anim") || "rise").trim() || "rise";
    var dTrans = (cs.getPropertyValue("--mg-transition") || "cut").trim() || "cut";
    var dCam = (cs.getPropertyValue("--mg-cam") || "push").trim() || "push";
    stage.style.width = M.width + "px";
    stage.style.height = M.height + "px";
    document.documentElement.style.setProperty("--u", (Math.min(M.width, M.height) / 100) + "px");
    document.documentElement.style.setProperty("--w", M.width + "px");
    document.documentElement.style.setProperty("--h", M.height + "px");

    var cursor = 0;
    Array.prototype.slice.call(stage.querySelectorAll(".scene")).forEach(function (el, i) {
      var sc = { el: el, index: i, id: el.id || "scene" + (i + 1), dur: num(el, "dur", 3), items: [] };
      sc.trans = i === 0 ? "cut" : str(el, "in", dTrans);
      sc.transDur = sc.trans === "cut" ? 0 : Math.min(num(el, "in-dur", 0.5), sc.dur);
      sc.transEase = str(el, "in-ease", "inout");
      sc.start = Math.max(0, cursor - sc.transDur);
      sc.end = sc.start + sc.dur;
      cursor = sc.end;
      el.style.zIndex = String(i + 1);
      /* slow "camera" move on the scene's content so a hold never goes fully still */
      sc.cam = str(el, "cam", dCam); sc.camAmt = num(el, "cam-amt", 4);
      if (sc.cam !== "none") {
        var cam = document.createElement("div");
        cam.className = "mg-cam";
        cam.style.cssText = "display:flex;flex-direction:inherit;justify-content:inherit;align-items:inherit;gap:inherit;text-align:inherit;width:100%;height:100%;min-height:0";
        while (el.firstChild) cam.appendChild(el.firstChild);
        el.appendChild(cam); sc.camEl = cam;
      }
      Array.prototype.slice.call(el.querySelectorAll("[data-anim],[data-out],[data-loop]")).forEach(function (node) {
        var name = str(node, "anim", node.hasAttribute("data-anim") ? dAnim : "none");
        var preset = PRESET[name] || PRESET.fade;
        var base = {
          name: name, preset: preset,
          at: num(node, "at", 0), dur: num(node, "dur", dDur),
          ease: str(node, "ease", preset.ease || dEase),
          out: str(node, "out", ""), outAt: num(node, "out-at", -1), outDur: num(node, "out-dur", dDur * 0.7),
          loop: str(node, "loop", ""), loopAmp: num(node, "loop-amp", 10), loopPer: num(node, "loop-period", 4)
        };
        if (base.out && base.outAt < 0) base.outAt = sc.dur - base.outDur;
        var mode = str(node, "split", name === "type" ? "chars" : "");
        var stag = num(node, "stagger", dStag);
        if (preset.special === "count") {
          base.from = num(node, "from", 0);
          base.to = num(node, "to", parseFloat(node.textContent) || 0);
          base.decimals = num(node, "decimals", 0);
          base.prefix = str(node, "prefix", ""); base.suffix = str(node, "suffix", "");
          base.sep = str(node, "sep", ",");
        }
        if (preset.special === "draw") {
          var shapes = node.matches("path,line,circle,rect,polyline,polygon,ellipse") ? [node]
            : Array.prototype.slice.call(node.querySelectorAll("path,line,circle,rect,polyline,polygon,ellipse"));
          shapes.forEach(function (s) { s.setAttribute("pathLength", "1"); s.style.strokeDasharray = "1"; });
          base.shapes = shapes;
        }
        if (mode === "words" || mode === "chars") {
          var parts = splitText(node, mode);
          if (name === "type") stag = parts.length ? base.dur / parts.length : 0;
          parts.forEach(function (p, k) {
            var it = Object.assign({}, base, { el: p, at: base.at + k * stag });
            if (name === "type") { it.dur = 0; it.preset = PRESET.fade; }
            it.loop = "";
            sc.items.push(it);
          });
          if (base.loop) sc.items.push(Object.assign({}, base, { el: node, preset: PRESET.none, out: "" }));
        } else {
          sc.items.push(Object.assign({}, base, { el: node }));
        }
      });
      M.scenes.push(sc);
    });
    M.duration = M.scenes.length ? M.scenes[M.scenes.length - 1].end : 0;
    var forced = num(body, "duration", 0);
    if (forced > 0) M.duration = forced;
  }

  function fmtNum(v, it) {
    var s = v.toFixed(it.decimals);
    if (it.sep) { var a = s.split("."); a[0] = a[0].replace(/\B(?=(\d{3})+(?!\d))/g, it.sep); s = a.join("."); }
    return it.prefix + s + it.suffix;
  }
  function clipFor(side, e) {
    var r = ((1 - e) * 100).toFixed(3) + "%";
    if (side === "right") return "inset(0 " + r + " 0 0)";
    if (side === "left") return "inset(0 0 0 " + r + ")";
    if (side === "top") return "inset(0 0 " + r + " 0)";
    return "inset(" + r + " 0 0 0)";
  }

  function applyItem(it, lt) {
    var e = prog(lt, it.at, it.dur, it.ease), P = it.preset, st = it.el.style;
    var o = lerp(P.o === undefined ? 1 : P.o, 1, e);
    var x = lerp(P.x || 0, 0, e), y = lerp(P.y || 0, 0, e);
    var s = lerp(P.s === undefined ? 1 : P.s, 1, e), r = lerp(P.r || 0, 0, e), b = lerp(P.b || 0, 0, e);
    var sx = P.sx === undefined ? 1 : lerp(P.sx, 1, e), sy = P.sy === undefined ? 1 : lerp(P.sy, 1, e);
    var clip = P.clip ? clipFor(P.clip, e) : "";
    if (P.o !== undefined && lt < it.at) o = 0;
    if (P.special === "count") it.el.textContent = fmtNum(lerp(it.from, it.to, e), it);
    if (P.special === "draw") it.shapes.forEach(function (sh) { sh.style.strokeDashoffset = String(1 - e); });
    if (it.out && lt >= it.outAt) {
      var Q = PRESET[it.out] || PRESET.fade, q = prog(lt, it.outAt, it.outDur, "in");
      o *= lerp(1, Q.o === undefined ? 1 : Q.o, q);
      x += lerp(0, -(Q.x || 0), q); y += lerp(0, -(Q.y || 0), q);
      s *= lerp(1, Q.s === undefined ? 1 : Q.s, q); r += lerp(0, -(Q.r || 0), q); b += lerp(0, Q.b || 0, q);
      if (Q.clip) clip = clipFor(Q.clip === "right" ? "left" : Q.clip === "top" ? "bottom" : Q.clip, 1 - q);
    }
    if (it.loop && LOOPS[it.loop]) {
      var L = LOOPS[it.loop](lt, it.loopAmp, it.loopPer);
      x += L.x || 0; y += L.y || 0; r += L.r || 0; s *= L.s || 1;
    }
    var u = M.u, tf = "";
    if (x || y) tf += "translate(" + (x * u).toFixed(3) + "px," + (y * u).toFixed(3) + "px) ";
    if (s !== 1 || sx !== 1 || sy !== 1) tf += "scale(" + (s * sx).toFixed(5) + "," + (s * sy).toFixed(5) + ") ";
    if (r) tf += "rotate(" + r.toFixed(4) + "deg)";
    st.opacity = o.toFixed(4);
    st.transform = tf || "none";
    if (P.origin) st.transformOrigin = P.origin;
    st.filter = b > 0.01 ? "blur(" + (b * u).toFixed(2) + "px)" : "";
    st.clipPath = clip;
  }

  function applyTransition(sc, prev, t) {
    var st = sc.el.style, ps = prev ? prev.el.style : null;
    st.opacity = "1"; st.transform = "none"; st.clipPath = "";
    if (!sc.transDur || t >= sc.start + sc.transDur) return;
    var p = prog(t, sc.start, sc.transDur, sc.transEase), W = M.width, H = M.height;
    switch (sc.trans) {
      case "fade": st.opacity = p.toFixed(4); break;
      case "push": case "push-left":
        st.transform = "translateX(" + ((1 - p) * W).toFixed(2) + "px)";
        if (ps) ps.transform = "translateX(" + (-p * W).toFixed(2) + "px)"; break;
      case "push-right":
        st.transform = "translateX(" + (-(1 - p) * W).toFixed(2) + "px)";
        if (ps) ps.transform = "translateX(" + (p * W).toFixed(2) + "px)"; break;
      case "push-up":
        st.transform = "translateY(" + ((1 - p) * H).toFixed(2) + "px)";
        if (ps) ps.transform = "translateY(" + (-p * H).toFixed(2) + "px)"; break;
      case "slide": st.transform = "translateY(" + ((1 - p) * H).toFixed(2) + "px)"; break;
      case "wipe": st.clipPath = "inset(0 " + ((1 - p) * 100).toFixed(3) + "% 0 0)"; break;
      case "wipe-up": st.clipPath = "inset(" + ((1 - p) * 100).toFixed(3) + "% 0 0 0)"; break;
      case "iris": st.clipPath = "circle(" + (p * 75).toFixed(3) + "% at 50% 50%)"; break;
      case "zoom":
        st.opacity = p.toFixed(4); st.transform = "scale(" + lerp(1.18, 1, p).toFixed(5) + ")";
        if (ps) ps.transform = "scale(" + lerp(1, 0.9, p).toFixed(5) + ")"; break;
      case "flash": st.opacity = t >= sc.start + sc.transDur / 2 ? "1" : "0"; break;
      default: break;
    }
  }

  function seek(t) {
    t = clamp(t, 0, Math.max(0, M.duration));
    M.time = t;
    for (var i = 0; i < M.scenes.length; i++) {
      var sc = M.scenes[i], last = i === M.scenes.length - 1;
      var on = t >= sc.start && (t < sc.end || (last && t >= sc.end));
      sc.el.style.visibility = on ? "visible" : "hidden";
      if (!on) continue;
      applyTransition(sc, i > 0 ? M.scenes[i - 1] : null, t);
      var lt = t - sc.start;
      if (sc.camEl) {
        var cp = clamp(lt / sc.dur, 0, 1), ca = sc.camAmt / 100, ctf = "none";
        if (sc.cam === "push") ctf = "scale(" + (1 + ca * cp).toFixed(5) + ")";
        else if (sc.cam === "pull") ctf = "scale(" + (1 + ca * (1 - cp)).toFixed(5) + ")";
        else if (sc.cam === "pan-left") ctf = "translateX(" + ((0.5 - cp) * ca * M.width).toFixed(2) + "px)";
        else if (sc.cam === "pan-right") ctf = "translateX(" + ((cp - 0.5) * ca * M.width).toFixed(2) + "px)";
        else if (sc.cam === "rise") ctf = "translateY(" + ((0.5 - cp) * ca * M.height).toFixed(2) + "px)";
        sc.camEl.style.transform = ctf;
      }
      for (var k = 0; k < sc.items.length; k++) applyItem(sc.items[k], lt);
    }
    for (var h = 0; h < M.sceneHooks.length; h++) {
      var hk = M.sceneHooks[h], s2 = hk.scene;
      if (s2 && t >= s2.start && t <= s2.end) hk.fn(t - s2.start, s2.dur, s2.el);
    }
    for (var j = 0; j < M.hooks.length; j++) M.hooks[j](t, M);
    var flash = document.getElementById("mg-flash");
    if (flash) {
      var f = 0;
      M.scenes.forEach(function (s3) {
        if (s3.trans === "flash" && s3.transDur) f = Math.max(f, 1 - Math.abs(t - (s3.start + s3.transDur / 2)) / (s3.transDur / 2));
      });
      flash.style.opacity = clamp(f, 0, 1).toFixed(3);
    }
  }

  function cues() {
    var out = [];
    M.scenes.forEach(function (sc) {
      out.push({ t: +sc.start.toFixed(3), type: "scene", id: sc.id, dur: sc.dur, transition: sc.trans });
      var seen = [];
      sc.items.forEach(function (it) {
        var node = it.el.closest("[data-anim],[data-out],[data-loop]") || it.el;
        if (seen.indexOf(node) >= 0 || it.name === "none") return;
        seen.push(node);
        out.push({ t: +(sc.start + num(node, "at", 0)).toFixed(3), type: "anim", scene: sc.id, anim: it.name,
          cue: str(node, "cue", ""), text: (node.textContent || "").trim().slice(0, 60) });
      });
    });
    return out.sort(function (a, b) { return a.t - b.t; });
  }

  function preview() {
    var bar = document.createElement("div");
    bar.id = "mg-preview";
    bar.style.cssText = "position:fixed;left:0;right:0;bottom:0;height:34px;background:#111c;color:#fff;font:12px/34px system-ui,sans-serif;display:flex;gap:10px;padding:0 12px;z-index:99999;align-items:center";
    var btn = document.createElement("button"); btn.textContent = "Pause"; btn.style.cssText = "font:inherit;padding:2px 10px";
    var rng = document.createElement("input"); rng.type = "range"; rng.min = "0"; rng.max = String(M.duration); rng.step = String(1 / M.fps); rng.style.flex = "1";
    var lab = document.createElement("span");
    bar.appendChild(btn); bar.appendChild(rng); bar.appendChild(lab); document.body.appendChild(bar);
    var fit = function () {
      var k = Math.min(window.innerWidth / M.width, (window.innerHeight - 34) / M.height);
      stage.style.transformOrigin = "0 0";
      stage.style.transform = "translate(" + ((window.innerWidth - M.width * k) / 2) + "px,0) scale(" + k + ")";
    };
    fit(); window.addEventListener("resize", fit);
    /* preview only: a wall clock drives the same seek() the renderer uses */
    var playing = true, t = 0, lastTs = null, raf = window["request" + "AnimationFrame"].bind(window);
    var tick = function (ts) {
      if (lastTs !== null && playing) { t += (ts - lastTs) / 1000; if (t > M.duration) t = 0; }
      lastTs = ts;
      var ft = Math.floor(t * M.fps) / M.fps;
      seek(ft); rng.value = String(ft); lab.textContent = ft.toFixed(2) + " / " + M.duration.toFixed(2) + " s";
      raf(tick);
    };
    btn.onclick = function () { playing = !playing; btn.textContent = playing ? "Pause" : "Play"; };
    rng.oninput = function () { playing = false; btn.textContent = "Play"; t = parseFloat(rng.value); };
    document.addEventListener("keydown", function (e) { if (e.code === "Space") { e.preventDefault(); btn.onclick(); } });
    raf(tick);
  }

  var api = {
    ease: EASE, presets: PRESET, rand: rand, lerp: lerp, clamp: clamp, prog: prog,
    /* run fn(t, info) on every frame */
    frame: function (fn) { M.hooks.push(fn); },
    /* run fn(localTime, sceneDuration, sceneElement) while a scene is on screen */
    scene: function (idOrEl, fn) { M.sceneHooks.push({ key: idOrEl, fn: fn, scene: null }); }
  };
  window.MG = api;

  function start() {
    build();
    M.sceneHooks.forEach(function (h) {
      h.scene = M.scenes.filter(function (s) { return s.el === h.key || s.id === h.key; })[0] || null;
    });
    render = /(^|[#&?])render\b/.test(location.hash + location.search);
    document.documentElement.classList.add(render ? "mg-render" : "mg-preview");
    var waits = [];
    if (document.fonts && document.fonts.ready) waits.push(document.fonts.ready);
    Array.prototype.slice.call(document.images).forEach(function (img) {
      if (!img.complete) waits.push(new Promise(function (res) { img.onload = img.onerror = res; }));
    });
    var ready = Promise.all(waits).then(function () { seek(0); if (!render) preview(); return true; });
    window.__mg = {
      get duration() { return M.duration; }, get fps() { return M.fps; },
      get width() { return M.width; }, get height() { return M.height; },
      get scenes() { return M.scenes.map(function (s) { return { id: s.id, start: s.start, end: s.end, dur: s.dur, transition: s.trans, transDur: s.transDur }; }); },
      seek: seek, cues: cues, ready: ready
    };
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
