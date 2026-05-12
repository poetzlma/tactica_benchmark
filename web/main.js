// Tactica replay viewer.

const CELL = 18;
const BASE_TICK_MS = 50;
const HP_BAR_W = 16;
const HP_BAR_H = 2;
const UTYPE_ORDER = ["mbt", "infantry", "mortar", "medic", "drone"];

const TEAM_COLORS = { red: 0xd84444, blue: 0x3d8ed8 };
const TEAM_DARK = { red: 0x6e1f1f, blue: 0x1a3e60 };
const TEAM_LIGHT = { red: 0xff8a8a, blue: 0x8ec1ee };

const SHADOW_COLOR = 0x000000;
const SHADOW_ALPHA = 0.35;

async function tryFetch(url) {
  try {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

async function loadManifest() {
  return await tryFetch("rounds/manifest.json");
}

async function loadBattleFile(path) {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error(`Failed to load ${path}: ${r.status}`);
  return await r.json();
}

async function loadBattle() {
  return await loadBattleFile("battle.json");
}

function drawUnitShape(g, type, teamColor, darkColor, lightColor) {
  g.clear();
  switch (type) {
    case "mbt": {
      // Treads (drawn first, run along sides)
      g.beginFill(0x1a1f26).drawRoundedRect(-10, -8, 20, 4, 1.5).endFill();
      g.beginFill(0x1a1f26).drawRoundedRect(-10, 4, 20, 4, 1.5).endFill();
      // Tread segments
      g.beginFill(0x2c333d);
      for (let i = -9; i < 10; i += 3) {
        g.drawRect(i, -7, 1.5, 2);
        g.drawRect(i, 5, 1.5, 2);
      }
      g.endFill();
      // Hull
      g.beginFill(teamColor).lineStyle(1, darkColor, 1).drawRoundedRect(-9, -5, 18, 10, 1.5).endFill();
      // Hull plating accent
      g.lineStyle(1, darkColor, 0.6).moveTo(-8, -2).lineTo(8, -2);
      g.moveTo(-8, 2).lineTo(8, 2);
      // Turret base
      g.beginFill(darkColor).lineStyle(1, 0x000000, 0.4).drawCircle(0, 0, 4.5).endFill();
      // Turret top
      g.beginFill(teamColor).lineStyle(0).drawCircle(-1, 0, 3).endFill();
      // Barrel (points forward = +x in unit-local space)
      g.beginFill(darkColor).drawRoundedRect(2, -1, 9, 2, 0.8).endFill();
      // Barrel muzzle
      g.beginFill(0x000000).drawRect(10, -1, 1.5, 2).endFill();
      break;
    }
    case "infantry": {
      // Pack/backpack (rear)
      g.beginFill(darkColor).drawRect(-5, -2, 3, 4).endFill();
      // Body
      g.beginFill(teamColor).lineStyle(1, darkColor, 1).drawCircle(0, 0, 4.5).endFill();
      // Helmet (forward-facing)
      g.beginFill(0x2a2e36).drawCircle(1, -0.5, 2.3).endFill();
      g.beginFill(lightColor).lineStyle(0).drawCircle(2, -1, 0.8).endFill(); // eye glint
      // Rifle pointing forward
      g.beginFill(0x1a1f26).drawRect(2, 1, 6, 1).endFill();
      break;
    }
    case "mortar": {
      // Sandbag base
      g.beginFill(0x6b5a3f).lineStyle(1, 0x4a3e2a, 1).drawRoundedRect(-7, 2, 14, 5, 2).endFill();
      g.lineStyle(0.5, 0x4a3e2a, 0.6).moveTo(-4, 2).lineTo(-4, 7);
      g.moveTo(0, 2).lineTo(0, 7);
      g.moveTo(4, 2).lineTo(4, 7);
      // Tube (angled up-forward)
      g.beginFill(0x2c333d).lineStyle(1, 0x000000, 0.5)
        .moveTo(-1, 2).lineTo(1, 2).lineTo(5, -7).lineTo(3, -7).closePath().endFill();
      // Team color crew indicator
      g.beginFill(teamColor).drawCircle(-3, 0, 2).endFill();
      break;
    }
    case "medic": {
      // Vehicle body (white/cream over team color base)
      g.beginFill(darkColor).lineStyle(1, 0x000000, 0.5).drawRoundedRect(-8, -6, 16, 12, 2).endFill();
      g.beginFill(0xe8e4d8).drawRoundedRect(-7, -5, 14, 10, 1.5).endFill();
      // Red cross (always red, not team-colored)
      g.beginFill(0xc83838).drawRect(-1.5, -4, 3, 8).drawRect(-4.5, -1, 9, 2).endFill();
      // Team indicator stripe (front)
      g.beginFill(teamColor).drawRect(6, -5, 2, 10).endFill();
      // Wheels
      g.beginFill(0x1a1f26).drawCircle(-5, 6, 2).drawCircle(5, 6, 2).endFill();
      break;
    }
    case "drone": {
      // Central body
      g.beginFill(teamColor).lineStyle(1, darkColor, 1)
        .moveTo(0, -4).lineTo(4, 0).lineTo(0, 4).lineTo(-4, 0).closePath().endFill();
      // Camera dot
      g.beginFill(0x000000).drawCircle(0, 0, 1.2).endFill();
      g.beginFill(lightColor).drawCircle(0.4, -0.4, 0.5).endFill();
      // Rotor arms
      g.lineStyle(1.2, darkColor, 1)
        .moveTo(-6, -6).lineTo(6, 6).moveTo(-6, 6).lineTo(6, -6);
      // Rotor blade circles
      g.beginFill(0xffffff, 0.15).lineStyle(0.5, lightColor, 0.4)
        .drawCircle(-6, -6, 3.5).drawCircle(6, 6, 3.5)
        .drawCircle(-6, 6, 3.5).drawCircle(6, -6, 3.5).endFill();
      break;
    }
    default:
      g.beginFill(teamColor).drawCircle(0, 0, 4).endFill();
  }
}

function hpColor(frac) {
  if (frac > 0.6) return 0x4cc06f;
  if (frac > 0.3) return 0xd8a040;
  return 0xd84848;
}

function angleBetween(ax, ay, bx, by) {
  return Math.atan2(by - ay, bx - ax);
}

function shortestAngleDelta(from, to) {
  let d = to - from;
  while (d > Math.PI) d -= 2 * Math.PI;
  while (d < -Math.PI) d += 2 * Math.PI;
  return d;
}

class Renderer {
  constructor(battle, hostEl) {
    this.battle = battle;
    this.map = battle.map;
    this.unitMeta = {};
    for (const u of battle.unit_index) this.unitMeta[u.id] = u;

    this.app = new PIXI.Application({
      width: this.map.width * CELL,
      height: this.map.height * CELL,
      background: 0x12161e,
      antialias: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      autoDensity: true,
    });
    hostEl.appendChild(this.app.view);

    this.terrainLayer = new PIXI.Container();
    this.heatmapLayer = new PIXI.Container();
    this.visionLayer = new PIXI.Container();
    this.shadowLayer = new PIXI.Container();
    this.unitLayer = new PIXI.Container();
    this.effectLayer = new PIXI.Container();
    this.app.stage.addChild(
      this.terrainLayer, this.heatmapLayer, this.visionLayer, this.shadowLayer,
      this.unitLayer, this.effectLayer,
    );

    this.drawTerrain();
    this.unitSprites = new Map();
    this.effects = [];
    this.lastFrameIdx = -1;
  }

  drawTerrain() {
    const w = this.map.width, h = this.map.height;
    const W = w * CELL, H = h * CELL;

    // Background base — radial-ish dark
    const bg = new PIXI.Graphics();
    bg.beginFill(0x171c25).drawRect(0, 0, W, H).endFill();
    this.terrainLayer.addChild(bg);

    // Vignette overlay
    const vign = new PIXI.Graphics();
    const cx = W / 2, cy = H / 2;
    for (let i = 0; i < 6; i++) {
      const t = i / 5;
      const inset = (1 - t) * Math.min(W, H) * 0.55;
      vign.beginFill(0x000000, 0.05).drawRect(0, 0, W, H).endFill();
      // Cut out the center with subtract via blend mode would be more correct;
      // approximate by overlaying darker rectangles at edges.
      vign.beginFill(0x000000, 0.06).drawRect(0, 0, W, inset / 4).endFill();
      vign.beginFill(0x000000, 0.06).drawRect(0, H - inset / 4, W, inset / 4).endFill();
      vign.beginFill(0x000000, 0.06).drawRect(0, 0, inset / 4, H).endFill();
      vign.beginFill(0x000000, 0.06).drawRect(W - inset / 4, 0, inset / 4, H).endFill();
    }
    vign.alpha = 0.4;
    this.terrainLayer.addChild(vign);

    // Very faint grid
    const grid = new PIXI.Graphics();
    grid.lineStyle(1, 0x222a36, 0.22);
    for (let x = 0; x <= w; x++) grid.moveTo(x * CELL, 0).lineTo(x * CELL, h * CELL);
    for (let y = 0; y <= h; y++) grid.moveTo(0, y * CELL).lineTo(w * CELL, y * CELL);
    this.terrainLayer.addChild(grid);

    // Spawn zones — flag-style hatched square
    const drawSpawn = (pos, color) => {
      const zone = new PIXI.Graphics();
      const x = (pos[0] + 0.5) * CELL, y = (pos[1] + 0.5) * CELL;
      zone.lineStyle(2, color, 0.7).drawCircle(x, y, CELL * 1.4);
      zone.beginFill(color, 0.06).drawCircle(x, y, CELL * 1.4).endFill();
      // Hatch lines
      zone.lineStyle(1, color, 0.25);
      for (let i = -CELL * 1.2; i <= CELL * 1.2; i += 4) {
        zone.moveTo(x + i, y - CELL * 1.2).lineTo(x + i, y + CELL * 1.2);
      }
      this.terrainLayer.addChild(zone);
    };
    drawSpawn(this.map.red_spawn, TEAM_COLORS.red);
    drawSpawn(this.map.blue_spawn, TEAM_COLORS.blue);

    // Obstacles — concrete blocks with shadow + bevel
    const obsShadow = new PIXI.Graphics();
    obsShadow.beginFill(0x000000, 0.45);
    for (const [x, y] of this.map.obstacles) {
      obsShadow.drawRoundedRect(x * CELL + 2, y * CELL + 3, CELL - 2, CELL - 2, 2);
    }
    obsShadow.endFill();
    this.terrainLayer.addChild(obsShadow);

    const obs = new PIXI.Graphics();
    for (const [x, y] of this.map.obstacles) {
      const px = x * CELL + 1, py = y * CELL + 1, s = CELL - 2;
      obs.beginFill(0x4a525e).lineStyle(1, 0x2c333d, 1).drawRoundedRect(px, py, s, s, 2).endFill();
      // Top highlight
      obs.beginFill(0x5d6675).lineStyle(0).drawRoundedRect(px, py, s, 2, 1).endFill();
      // Texture marks
      obs.lineStyle(0.5, 0x363c47, 0.5);
      obs.moveTo(px + s * 0.3, py + 3).lineTo(px + s * 0.3, py + s - 3);
      obs.moveTo(px + s * 0.7, py + 3).lineTo(px + s * 0.7, py + s - 3);
    }
    this.terrainLayer.addChild(obs);
  }

  ensureUnitSprite(id) {
    let s = this.unitSprites.get(id);
    if (s) return s;
    const meta = this.unitMeta[id];

    // Shadow
    const shadow = new PIXI.Graphics();
    shadow.beginFill(SHADOW_COLOR, SHADOW_ALPHA).drawEllipse(0, 2, 9, 4).endFill();
    this.shadowLayer.addChild(shadow);

    // Vision ring (only for drone) — soft, always-on
    let visionRing = null;
    if (meta.type === "drone") {
      visionRing = new PIXI.Graphics();
      const r = (this.battle.unit_specs.drone.vision + 0.3) * CELL;
      visionRing.beginFill(TEAM_COLORS[meta.team], 0.045).drawCircle(0, 0, r).endFill();
      visionRing.lineStyle(1, TEAM_COLORS[meta.team], 0.18).drawCircle(0, 0, r);
      this.visionLayer.addChild(visionRing);
    }

    // Body container (rotates)
    const c = new PIXI.Container();
    const body = new PIXI.Graphics();
    drawUnitShape(body, meta.type, TEAM_COLORS[meta.team], TEAM_DARK[meta.team], TEAM_LIGHT[meta.team]);
    c.addChild(body);

    // HP bar (does not rotate — separate container parented to a wrapper)
    const wrapper = new PIXI.Container();
    wrapper.addChild(c);
    const hp = new PIXI.Graphics();
    hp.position.set(-HP_BAR_W / 2, -CELL * 0.72);
    wrapper.addChild(hp);
    this.unitLayer.addChild(wrapper);

    // Initial facing depends on team — red faces right (+x), blue faces left.
    const initialFacing = meta.team === "red" ? 0 : Math.PI;
    c.rotation = initialFacing;

    s = {
      wrapper, body: c, bodyGfx: body, hp, shadow, visionRing,
      type: meta.type, team: meta.team, maxHp: meta.max_hp,
      lastTickPos: null, facing: initialFacing,
    };
    this.unitSprites.set(id, s);
    return s;
  }

  applyFrame(frameIdx, alpha) {
    const frames = this.battle.frames;
    if (frames.length === 0) return;
    frameIdx = Math.max(0, Math.min(frameIdx, frames.length - 1));
    const cur = frames[frameIdx];
    const next = frames[Math.min(frameIdx + 1, frames.length - 1)];

    const curMap = new Map();
    for (const [id, x, y, hp] of cur.units) curMap.set(id, [x, y, hp]);
    const nextMap = new Map();
    for (const [id, x, y, hp] of next.units) nextMap.set(id, [x, y, hp]);

    // Hide units missing from current frame
    for (const [id, s] of this.unitSprites) {
      if (!curMap.has(id)) {
        s.wrapper.visible = false;
        s.shadow.visible = false;
        if (s.visionRing) s.visionRing.visible = false;
      }
    }

    // On a frame advance, recompute facing from movement
    const frameAdvanced = frameIdx !== this.lastFrameIdx;

    for (const [id, [cx, cy, hpv]] of curMap) {
      const s = this.ensureUnitSprite(id);
      s.wrapper.visible = true;
      s.shadow.visible = true;
      if (s.visionRing) s.visionRing.visible = true;

      // Update facing on frame advance from prevTickPos -> current
      if (frameAdvanced) {
        if (s.lastTickPos) {
          const [px, py] = s.lastTickPos;
          if (px !== cx || py !== cy) {
            const targetAngle = angleBetween(px, py, cx, cy);
            // Smooth-rotate toward target
            const delta = shortestAngleDelta(s.facing, targetAngle);
            s.facing += delta * 0.6;  // 60% step
          }
        }
        s.lastTickPos = [cx, cy];
      }

      // Interpolate position
      let ix = cx, iy = cy;
      const nx = nextMap.get(id);
      if (nx) { ix = cx + (nx[0] - cx) * alpha; iy = cy + (nx[1] - cy) * alpha; }
      const px = (ix + 0.5) * CELL, py = (iy + 0.5) * CELL;
      s.wrapper.position.set(px, py);
      s.shadow.position.set(px, py + 1);
      if (s.visionRing) s.visionRing.position.set(px, py);

      s.body.rotation = s.facing;

      // HP bar
      s.hp.clear();
      s.hp.beginFill(0x000000, 0.55).drawRect(-1, -1, HP_BAR_W + 2, HP_BAR_H + 2).endFill();
      const frac = Math.max(0, Math.min(1, hpv / s.maxHp));
      s.hp.beginFill(hpColor(frac)).drawRect(0, 0, HP_BAR_W * frac, HP_BAR_H).endFill();
    }

    this.lastFrameIdx = frameIdx;
  }

  spawnEffectsForFrame(frame) {
    if (!frame || !frame.events) return;
    const findSprite = (id) => this.unitSprites.get(id);

    for (const ev of frame.events) {
      if (ev.kind === "attack") {
        const a = findSprite(ev.from_id), b = findSprite(ev.to_id);
        if (!a || !b || !a.wrapper.visible || !b.wrapper.visible) continue;
        const meta = this.unitMeta[ev.from_id];
        if (meta && meta.type === "mortar") {
          this.spawnMortarShell(a, b);
        } else {
          this.spawnDirectFire(a, b);
        }
        // Rotate attacker toward target — overrides movement facing for snap
        const tx = b.wrapper.x, ty = b.wrapper.y;
        const angle = Math.atan2(ty - a.wrapper.y, tx - a.wrapper.x);
        a.facing = angle;
        a.body.rotation = angle;
      } else if (ev.kind === "kill") {
        const v = findSprite(ev.victim_id);
        if (!v) continue;
        this.spawnDeath(v);
      } else if (ev.kind === "heal") {
        const a = findSprite(ev.to_id);
        if (!a) continue;
        this.spawnHealPulse(a);
      }
    }
  }

  spawnDirectFire(attacker, target) {
    const ax = attacker.wrapper.x, ay = attacker.wrapper.y;
    const bx = target.wrapper.x, by = target.wrapper.y;
    const color = TEAM_COLORS[attacker.team];
    const light = TEAM_LIGHT[attacker.team];

    // Tracer line
    const tracer = new PIXI.Graphics();
    tracer.lineStyle(2, light, 1).moveTo(ax, ay).lineTo(bx, by);
    tracer.lineStyle(4, color, 0.45).moveTo(ax, ay).lineTo(bx, by);
    this.effectLayer.addChild(tracer);
    this.effects.push({ gfx: tracer, ttl: 110, totalTtl: 110,
      update: (e) => { e.gfx.alpha = (e.ttl / e.totalTtl) ** 1.5; } });

    // Muzzle flash
    const flash = new PIXI.Graphics();
    flash.beginFill(0xfff0c0, 0.95).drawCircle(0, 0, 5).endFill();
    flash.beginFill(0xffd060, 0.6).drawCircle(0, 0, 3).endFill();
    flash.position.set(ax, ay);
    this.effectLayer.addChild(flash);
    this.effects.push({ gfx: flash, ttl: 110, totalTtl: 110, update: (e) => {
      const t = 1 - e.ttl / e.totalTtl;
      e.gfx.scale.set(1 + t * 0.8);
      e.gfx.alpha = 1 - t;
    }});

    // Impact spark
    const spark = new PIXI.Graphics();
    spark.beginFill(0xffe080, 0.9).drawCircle(0, 0, 3).endFill();
    spark.position.set(bx, by);
    this.effectLayer.addChild(spark);
    this.effects.push({ gfx: spark, ttl: 180, totalTtl: 180, update: (e) => {
      const t = 1 - e.ttl / e.totalTtl;
      e.gfx.scale.set(0.7 + t * 1.6);
      e.gfx.alpha = 1 - t;
    }});
  }

  spawnMortarShell(attacker, target) {
    const ax = attacker.wrapper.x, ay = attacker.wrapper.y;
    const bx = target.wrapper.x, by = target.wrapper.y;
    const dist = Math.hypot(bx - ax, by - ay);
    const arcHeight = Math.min(50, dist * 0.35);
    const totalTtl = 420;

    const shell = new PIXI.Graphics();
    shell.beginFill(0x1a1f26).lineStyle(1, 0x000000, 0.6).drawCircle(0, 0, 2.2).endFill();
    shell.beginFill(0xff8040, 0.8).drawCircle(0, 0, 1.0).endFill();
    this.effectLayer.addChild(shell);

    // Trail
    const trail = new PIXI.Graphics();
    this.effectLayer.addChild(trail);

    const trailPts = [];
    this.effects.push({
      gfx: shell, ttl: totalTtl, totalTtl,
      _trail: trail, _trailPts: trailPts,
      update: (e) => {
        const t = 1 - e.ttl / e.totalTtl;
        const lx = ax + (bx - ax) * t;
        const ly = ay + (by - ay) * t - Math.sin(Math.PI * t) * arcHeight;
        e.gfx.position.set(lx, ly);
        e._trailPts.push([lx, ly, e.ttl]);
        if (e._trailPts.length > 12) e._trailPts.shift();
        e._trail.clear();
        for (let i = 1; i < e._trailPts.length; i++) {
          const [x0, y0] = e._trailPts[i - 1];
          const [x1, y1] = e._trailPts[i];
          const a = (i / e._trailPts.length) * 0.5;
          e._trail.lineStyle(2, 0xc8a060, a).moveTo(x0, y0).lineTo(x1, y1);
        }
      },
      onDone: () => {
        this.effectLayer.removeChild(trail);
        trail.destroy();
        this.spawnExplosion(bx, by);
      },
    });
  }

  spawnExplosion(x, y) {
    // Bright core
    const core = new PIXI.Graphics();
    core.beginFill(0xfff0a0, 1).drawCircle(0, 0, 5).endFill();
    core.beginFill(0xff8040, 0.8).drawCircle(0, 0, 8).endFill();
    core.position.set(x, y);
    this.effectLayer.addChild(core);
    this.effects.push({ gfx: core, ttl: 300, totalTtl: 300, update: (e) => {
      const t = 1 - e.ttl / e.totalTtl;
      e.gfx.scale.set(1 + t * 1.8);
      e.gfx.alpha = 1 - t;
    }});

    // Shockwave ring
    const ring = new PIXI.Graphics();
    ring.lineStyle(2, 0xffb060, 1).drawCircle(0, 0, 4);
    ring.position.set(x, y);
    this.effectLayer.addChild(ring);
    this.effects.push({ gfx: ring, ttl: 380, totalTtl: 380, update: (e) => {
      const t = 1 - e.ttl / e.totalTtl;
      e.gfx.scale.set(1 + t * 4);
      e.gfx.alpha = 1 - t;
    }});

    // Smoke
    for (let i = 0; i < 4; i++) {
      const s = new PIXI.Graphics();
      s.beginFill(0x807870, 0.7).drawCircle(0, 0, 3 + Math.random() * 2).endFill();
      const dx = (Math.random() - 0.5) * 8;
      const dy = (Math.random() - 0.5) * 8;
      s.position.set(x + dx, y + dy);
      this.effectLayer.addChild(s);
      const drift = (Math.random() - 0.5) * 0.08;
      this.effects.push({ gfx: s, ttl: 900 + Math.random() * 400, totalTtl: 1100, _drift: drift,
        update: (e) => {
          const t = 1 - e.ttl / e.totalTtl;
          e.gfx.y -= 0.15;
          e.gfx.x += e._drift;
          e.gfx.scale.set(1 + t * 1.5);
          e.gfx.alpha = 0.7 * (1 - t);
        }});
    }
  }

  spawnDeath(victim) {
    const x = victim.wrapper.x, y = victim.wrapper.y;
    // Wreck mark (lingering, decays slowly)
    const wreck = new PIXI.Graphics();
    wreck.beginFill(0x1a1f26, 0.85).lineStyle(1, 0x000000, 0.7).drawCircle(0, 0, 5).endFill();
    wreck.beginFill(0x3a3f48, 0.6).drawCircle(-1, -1, 2.5).endFill();
    wreck.position.set(x, y);
    this.effectLayer.addChild(wreck);
    this.effects.push({ gfx: wreck, ttl: 2500, totalTtl: 2500, update: (e) => {
      e.gfx.alpha = 0.85 * Math.max(0, e.ttl / e.totalTtl);
    }});

    // Initial puff
    const puff = new PIXI.Graphics();
    puff.beginFill(0x4a4540, 0.85).drawCircle(0, 0, 4).endFill();
    puff.position.set(x, y);
    this.effectLayer.addChild(puff);
    this.effects.push({ gfx: puff, ttl: 600, totalTtl: 600, update: (e) => {
      const t = 1 - e.ttl / e.totalTtl;
      e.gfx.scale.set(1 + t * 3);
      e.gfx.alpha = 0.85 * (1 - t);
    }});

    // Drifting smoke
    for (let i = 0; i < 3; i++) {
      const s = new PIXI.Graphics();
      s.beginFill(0x6b6660, 0.6).drawCircle(0, 0, 2 + Math.random() * 2).endFill();
      s.position.set(x + (Math.random() - 0.5) * 6, y + (Math.random() - 0.5) * 6);
      this.effectLayer.addChild(s);
      this.effects.push({ gfx: s, ttl: 1500 + Math.random() * 400, totalTtl: 1700,
        update: (e) => {
          const t = 1 - e.ttl / e.totalTtl;
          e.gfx.y -= 0.12;
          e.gfx.scale.set(1 + t * 1.8);
          e.gfx.alpha = 0.6 * (1 - t);
        }});
    }
  }

  spawnHealPulse(unit) {
    const x = unit.wrapper.x, y = unit.wrapper.y;
    const g = new PIXI.Graphics();
    g.lineStyle(2, 0x6cd084, 1).drawCircle(0, 0, 6);
    g.beginFill(0x6cd084, 0.18).drawCircle(0, 0, 6).endFill();
    g.position.set(x, y);
    this.effectLayer.addChild(g);
    this.effects.push({ gfx: g, ttl: 400, totalTtl: 400, update: (e) => {
      const t = 1 - e.ttl / e.totalTtl;
      e.gfx.scale.set(1 + t * 1.6);
      e.gfx.alpha = 1 - t;
    }});
    // Cross flash
    const cross = new PIXI.Graphics();
    cross.beginFill(0x6cd084, 0.9).drawRect(-1, -5, 2, 10).drawRect(-5, -1, 10, 2).endFill();
    cross.position.set(x, y - 12);
    this.effectLayer.addChild(cross);
    this.effects.push({ gfx: cross, ttl: 500, totalTtl: 500, update: (e) => {
      const t = 1 - e.ttl / e.totalTtl;
      e.gfx.y = (y - 12) - t * 8;
      e.gfx.alpha = 1 - t;
    }});
  }

  clearHeatmap() {
    this.heatmapLayer.removeChildren().forEach((c) => c.destroy());
  }

  renderHeatmap(heatmaps, mode, teams) {
    this.clearHeatmap();
    if (!heatmaps || mode === "off" || !teams || teams.length === 0) return null;
    const grids = heatmaps[mode];
    if (!grids) return null;
    const w = heatmaps.width || this.map.width;
    const h = heatmaps.height || this.map.height;

    // Find shared peak across selected teams so cross-team intensity is comparable.
    let peak = 0;
    for (const t of teams) {
      const g = grids[t];
      if (!g) continue;
      for (let i = 0; i < g.length; i++) if (g[i] > peak) peak = g[i];
    }
    if (peak <= 0) return { peak: 0, mode, teams };

    // Per-team palette: base color + alpha scaling. Each tint blended additively.
    const palette = {
      red:  { deaths: 0xff4848, damage_dealt: 0xff8030, presence: 0xc04040 },
      blue: { deaths: 0x4090e0, damage_dealt: 0x40c8e0, presence: 0x4070c0 },
    };

    const g = new PIXI.Graphics();
    for (const team of teams) {
      const grid = grids[team];
      if (!grid) continue;
      const color = (palette[team] && palette[team][mode]) || 0xffffff;
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const v = grid[y * w + x];
          if (v <= 0) continue;
          const t = v / peak;
          // Soft non-linear ramp so faint cells are still visible.
          const a = Math.min(0.85, 0.18 + Math.pow(t, 0.6) * 0.65);
          g.beginFill(color, a).drawRect(x * CELL, y * CELL, CELL, CELL).endFill();
        }
      }
    }
    this.heatmapLayer.addChild(g);
    return { peak, mode, teams };
  }

  tickEffects(dtMs) {
    for (let i = this.effects.length - 1; i >= 0; i--) {
      const e = this.effects[i];
      e.ttl -= dtMs;
      if (e.ttl <= 0) {
        if (e.onDone) e.onDone();
        this.effectLayer.removeChild(e.gfx);
        e.gfx.destroy();
        this.effects.splice(i, 1);
      } else e.update(e);
    }
  }
}

class Playback {
  constructor(battle, renderer, ui) {
    this.battle = battle; this.renderer = renderer; this.ui = ui;
    this.frameIdx = 0; this.alpha = 0;
    this.playing = false; this.speed = 1;
    this.lastWall = performance.now();
  }
  totalFrames() { return this.battle.frames.length; }
  setFrame(i, alpha = 0) {
    const prev = this.frameIdx;
    this.frameIdx = Math.max(0, Math.min(i, this.totalFrames() - 1));
    this.alpha = alpha;
    if (this.frameIdx !== prev) {
      const frame = this.battle.frames[this.frameIdx];
      this.renderer.spawnEffectsForFrame(frame);
      this.ui.appendEvents(frame);
    }
    this.renderer.applyFrame(this.frameIdx, this.alpha);
    this.ui.updateScrubber(this.frameIdx);
  }
  step(n = 1) { this.setFrame(this.frameIdx + n, 0); }
  play() { this.playing = true; this.lastWall = performance.now(); this.ui.setPlaying(true); }
  pause() { this.playing = false; this.ui.setPlaying(false); }
  toggle() { this.playing ? this.pause() : this.play(); }
  tick(now) {
    const dt = now - this.lastWall; this.lastWall = now;
    this.renderer.tickEffects(dt);
    if (!this.playing) return;
    const tickDur = BASE_TICK_MS / this.speed;
    this.alpha += dt / tickDur;
    while (this.alpha >= 1) {
      this.alpha -= 1;
      if (this.frameIdx >= this.totalFrames() - 1) { this.alpha = 0; this.pause(); return; }
      this.setFrame(this.frameIdx + 1, this.alpha);
    }
    this.renderer.applyFrame(this.frameIdx, this.alpha);
  }
}

// ---------- minimal markdown renderer ----------

function escapeHtml(s) {
  // Escape & first, then <, > so substitutions do not double-escape
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function renderInline(s) {
  let out = escapeHtml(s);
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^_])_([^_]+)_/g, "$1<em>$2</em>");
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  return out;
}
function renderMarkdown(md) {
  const lines = md.split("\n");
  const out = [];
  let inList = false, inTable = false, tableHeaderEmitted = false;
  const closeList = () => { if (inList) { out.push("</ul>"); inList = false; } };
  const closeTable = () => { if (inTable) { out.push("</table>"); inTable = false; tableHeaderEmitted = false; } };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trimEnd();
    if (/^#{1,3}\s+/.test(line)) {
      closeList(); closeTable();
      const m = line.match(/^(#{1,3})\s+(.*)$/);
      out.push(`<h${m[1].length}>${renderInline(m[2])}</h${m[1].length}>`);
    } else if (/^---\s*$/.test(line)) {
      closeList(); closeTable(); out.push("<hr />");
    } else if (/^\s*-\s+/.test(line)) {
      closeTable();
      if (!inList) { out.push("<ul>"); inList = true; }
      out.push(`<li>${renderInline(line.replace(/^\s*-\s+/, ""))}</li>`);
    } else if (/^\|.*\|$/.test(line)) {
      closeList();
      if (!inTable) { out.push("<table>"); inTable = true; tableHeaderEmitted = false; }
      if (/^\|[\s:|-]+\|$/.test(line)) continue;
      const cells = line.slice(1, -1).split("|").map((c) => c.trim());
      const tag = tableHeaderEmitted ? "td" : "th";
      out.push("<tr>" + cells.map((c) => `<${tag}>${renderInline(c)}</${tag}>`).join("") + "</tr>");
      tableHeaderEmitted = true;
    } else if (line === "") {
      closeList(); closeTable();
    } else {
      closeList(); closeTable();
      out.push(`<p>${renderInline(line)}</p>`);
    }
  }
  closeList(); closeTable();
  return out.join("\n");
}

// ---------- UI ----------

class SidePanel {
  constructor(rootEl, team, brief, report) {
    this.root = rootEl;
    this.team = team;
    this.brief = brief;
    this.report = report;
    this.utype = "mbt";
    this.bindTabs();
    this.bindUtypeTabs();
    this.render();
  }
  $(role) { return this.root.querySelector(`[data-role="${role}"]`); }
  bindTabs() {
    const tabs = this.root.querySelectorAll(".tab");
    const contents = this.root.querySelectorAll(".tab-content");
    tabs.forEach((t) => {
      t.addEventListener("click", () => {
        tabs.forEach((x) => x.classList.remove("active"));
        contents.forEach((x) => x.classList.remove("active"));
        t.classList.add("active");
        const content = this.root.querySelector(`.tab-content[data-tab="${t.dataset.tab}"]`);
        if (content) content.classList.add("active");
      });
    });
  }
  bindUtypeTabs() {
    const host = this.$("utype-tabs");
    host.innerHTML = "";
    for (const ut of UTYPE_ORDER) {
      const b = document.createElement("button");
      b.className = "utab" + (ut === this.utype ? " active" : "");
      b.textContent = ut;
      b.addEventListener("click", () => {
        this.utype = ut;
        host.querySelectorAll(".utab").forEach((x) =>
          x.classList.toggle("active", x.textContent === ut));
        this.renderCode();
      });
      host.appendChild(b);
    }
  }
  render() {
    this.root.querySelector('[data-role="model"]').textContent = this.brief.model || "—";
    this.renderComp(); this.renderCode(); this.renderScratch();
    this.renderReason(); this.renderReport();
  }
  renderComp() {
    const host = this.$("comp");
    const comp = this.brief.composition;
    const order = UTYPE_ORDER.filter((k) => k in comp);
    let total = 0;
    let html = `<table class="comp-table">
      <tr><th>Unit</th><th class="num">Count</th><th class="num">Cost</th><th class="num">Pts</th></tr>`;
    for (const ut of order) {
      const c = comp[ut]; const cost = window.UNIT_SPEC_COSTS[ut]; const sub = c * cost;
      total += sub;
      html += `<tr><td>${ut}</td><td class="num">${c}</td><td class="num">${cost}</td><td class="num">${sub}</td></tr>`;
    }
    html += `<tr class="total"><td>Total</td><td colspan="2"></td><td class="num">${total}</td></tr></table>`;
    host.innerHTML = html;
  }
  renderCode() {
    const host = this.$("code");
    const src = this.brief.tactics[this.utype] || "";
    if (!src.trim()) { host.className = "code-view empty"; host.textContent = "(no code for this unit type)"; }
    else { host.className = "code-view"; host.textContent = src.trim(); }
  }
  renderScratch() {
    const host = this.$("scratch");
    const s = (this.brief.scratchpad || "").trim();
    if (!s) { host.className = "empty"; host.textContent = "(empty — no scratchpad this round)"; }
    else { host.className = ""; host.textContent = s; }
  }
  renderReason() {
    const host = this.$("reason");
    const r = (this.brief.reasoning || "").trim();
    if (!r) host.innerHTML = `<div class="empty-msg">(no reasoning recorded — hardcoded tactic)</div>`;
    else host.textContent = r;
  }
  renderReport() {
    const host = this.$("report");
    const r = (this.report || "").trim();
    if (!r) host.innerHTML = `<div class="empty-msg">(no report yet)</div>`;
    else host.innerHTML = renderMarkdown(r);
  }
}

class UI {
  constructor(battle) {
    this.battle = battle;
    this.scrubber = document.getElementById("scrubber");
    this.tickDisplay = document.getElementById("tick-display");
    this.playBtn = document.getElementById("play-btn");
    this.stepBtn = document.getElementById("step-btn");
    this.speedSel = document.getElementById("speed");
    this.eventStrip = document.getElementById("event-strip");

    this.scrubber.max = battle.frames.length - 1;
    document.getElementById("seed-pill").textContent = `seed ${battle.seed}`;
    document.getElementById("round-pill").textContent = `round ${battle.round || 1}`;
    document.getElementById("red-pill").textContent =
      `RED alive ${battle.red_alive} (${battle.red_survivors_value} pts)`;
    document.getElementById("blue-pill").textContent =
      `BLUE alive ${battle.blue_alive} (${battle.blue_survivors_value} pts)`;
    document.getElementById("outcome-pill").textContent = battle.outcome;

    const costs = {};
    for (const [ut, spec] of Object.entries(battle.unit_specs)) costs[ut] = spec.cost;
    window.UNIT_SPEC_COSTS = costs;

    this.redPanel = new SidePanel(
      document.getElementById("red-panel"), "red", battle.briefs.red, battle.reports.red,
    );
    this.bluePanel = new SidePanel(
      document.getElementById("blue-panel"), "blue", battle.briefs.blue, battle.reports.blue,
    );
  }
  setPlaying(p) { this.playBtn.textContent = p ? "⏸ Pause" : "▶ Play"; }
  updateScrubber(frame) {
    this.scrubber.value = frame;
    this.tickDisplay.textContent = `tick ${frame} / ${this.battle.frames.length - 1}`;
  }
  appendEvents(frame) {
    if (!frame.events) return;
    for (const ev of frame.events) {
      if (ev.kind !== "kill") continue;
      const div = document.createElement("div");
      div.className = "ev kill";
      div.innerHTML = `<span class="t">t=${frame.t}</span>#${ev.killer_id} → #${ev.victim_id}`;
      this.eventStrip.appendChild(div);
    }
    while (this.eventStrip.children.length > 80) this.eventStrip.removeChild(this.eventStrip.firstChild);
    this.eventStrip.scrollLeft = this.eventStrip.scrollWidth;
  }
}

async function loadModels() {
  try {
    const r = await fetch("/api/models", { cache: "no-store" });
    if (!r.ok) return [];
    const d = await r.json();
    return d.models || [];
  } catch { return []; }
}

async function fetchState() {
  try {
    const r = await fetch("/api/state", { cache: "no-store" });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

async function startRun(mode, model, rounds) {
  const r = await fetch("/api/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, rounds, mode }),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(e.error || `HTTP ${r.status}`);
  }
}

async function main() {
  const host = document.getElementById("canvas-host");
  const roundSelect = document.getElementById("round-select");
  const statusEl = document.getElementById("tournament-status");
  const modelSel = document.getElementById("model-select");
  const roundsInput = document.getElementById("rounds-input");
  const runNextBtn = document.getElementById("run-next-btn");
  const runFreshBtn = document.getElementById("run-fresh-btn");

  // Populate model picker
  const models = await loadModels();
  if (models.length === 0) {
    const opt = document.createElement("option");
    opt.value = ""; opt.textContent = "no gateway"; opt.disabled = true;
    modelSel.appendChild(opt);
  } else {
    for (const m of models) {
      const opt = document.createElement("option");
      opt.value = m; opt.textContent = m;
      modelSel.appendChild(opt);
    }
    const saved = localStorage.getItem("tactica.model");
    if (saved && models.includes(saved)) modelSel.value = saved;
    else if (models.includes("nemotron-3-nano-omni")) modelSel.value = "nemotron-3-nano-omni";
  }
  modelSel.addEventListener("change", () => {
    localStorage.setItem("tactica.model", modelSel.value);
  });

  let battle;
  let manifest = await loadManifest();
  let renderer = null, ui = null, pb = null;

  function populateRoundSelect(m) {
    roundSelect.innerHTML = "";
    if (m && m.rounds && m.rounds.length > 0) {
      roundSelect.style.display = "";
      for (let i = m.rounds.length - 1; i >= 0; i--) {
        const r = m.rounds[i];
        const opt = document.createElement("option");
        opt.value = r.file;
        opt.textContent = `round ${r.round} — ${r.outcome}`;
        roundSelect.appendChild(opt);
      }
    } else {
      roundSelect.style.display = "none";
    }
  }

  async function loadAndRender(file) {
    const data = file
      ? await loadBattleFile(`rounds/${file}`)
      : await loadBattle();
    // Preserve the heatmap toolbar across re-renders; only the canvas redraws.
    const bar = document.getElementById("heatmap-bar");
    const legend = document.getElementById("heatmap-legend");
    host.innerHTML = "";
    if (bar) host.appendChild(bar);
    if (legend) host.appendChild(legend);
    renderer = new Renderer(data, host);
    ui = new UI(data);
    pb = new Playback(data, renderer, ui);
    pb.setFrame(0, 0);
    bindPlaybackControls();
    applyHeatmap(data);
    return data;
  }

  // ---------- heatmap toolbar (persistent across rounds) ----------

  const heatmapState = { mode: "off", teams: new Set(["red", "blue"]) };

  function setHeatmapButtons() {
    const bar = document.getElementById("heatmap-bar");
    bar.querySelectorAll("[data-hm-mode]").forEach((b) => {
      b.classList.toggle("active", b.dataset.hmMode === heatmapState.mode);
    });
    bar.querySelectorAll("[data-hm-team]").forEach((b) => {
      b.classList.toggle("active", heatmapState.teams.has(b.dataset.hmTeam));
    });
  }

  function applyHeatmap(data) {
    if (!renderer) return;
    const battle = data || (pb && pb.battle);
    const heatmaps = battle && battle.heatmaps;
    const result = renderer.renderHeatmap(
      heatmaps, heatmapState.mode, [...heatmapState.teams]
    );
    const legendEl = document.getElementById("heatmap-legend");
    if (heatmapState.mode === "off" || !result || result.peak === 0) {
      legendEl.classList.remove("visible");
      legendEl.innerHTML = "";
    } else {
      const labels = {
        deaths: "deaths per cell",
        damage_dealt: "damage dealt from cell",
        presence: "unit-ticks in cell",
      };
      const teamsTxt = [...heatmapState.teams].join(" + ") || "(none)";
      legendEl.classList.add("visible");
      legendEl.innerHTML =
        `<strong>${labels[heatmapState.mode]}</strong> · ${teamsTxt} · ` +
        `<span class="legend-bar" style="background:linear-gradient(to right,rgba(255,255,255,0.05),rgba(255,255,255,0.85))"></span>` +
        ` 0 → ${result.peak}`;
    }
  }

  function bindHeatmapBar() {
    const bar = document.getElementById("heatmap-bar");
    bar.querySelectorAll("[data-hm-mode]").forEach((b) => {
      b.addEventListener("click", () => {
        heatmapState.mode = b.dataset.hmMode;
        setHeatmapButtons();
        applyHeatmap();
      });
    });
    bar.querySelectorAll("[data-hm-team]").forEach((b) => {
      b.addEventListener("click", () => {
        const t = b.dataset.hmTeam;
        if (heatmapState.teams.has(t)) heatmapState.teams.delete(t);
        else heatmapState.teams.add(t);
        setHeatmapButtons();
        applyHeatmap();
      });
    });
    setHeatmapButtons();
  }

  bindHeatmapBar();

  function bindPlaybackControls() {
    ui.playBtn.onclick = () => pb.toggle();
    ui.stepBtn.onclick = () => { pb.pause(); pb.step(1); };
    ui.speedSel.onchange = (e) => { pb.speed = parseFloat(e.target.value); };
    ui.scrubber.oninput = (e) => { pb.pause(); pb.setFrame(parseInt(e.target.value, 10), 0); };
  }

  populateRoundSelect(manifest);
  if (manifest && manifest.rounds && manifest.rounds.length > 0) {
    const latest = manifest.rounds[manifest.rounds.length - 1];
    battle = await loadAndRender(latest.file);
    roundSelect.value = latest.file;
  } else {
    battle = await loadAndRender(null);
  }

  roundSelect.addEventListener("change", (e) => loadAndRender(e.target.value));

  // ---------- mobile drawers ----------

  const edgeRed = document.getElementById("edge-red");
  const edgeBlue = document.getElementById("edge-blue");
  const backdrop = document.getElementById("drawer-backdrop");
  const redPanelEl = document.getElementById("red-panel");
  const bluePanelEl = document.getElementById("blue-panel");
  const closeBtns = document.querySelectorAll(".drawer-close");

  function openDrawer(team) {
    redPanelEl.classList.toggle("drawer-open", team === "red");
    bluePanelEl.classList.toggle("drawer-open", team === "blue");
    backdrop.classList.toggle("active", team === "red" || team === "blue");
  }
  function closeDrawers() {
    redPanelEl.classList.remove("drawer-open");
    bluePanelEl.classList.remove("drawer-open");
    backdrop.classList.remove("active");
  }
  edgeRed.addEventListener("click", () => openDrawer("red"));
  edgeBlue.addEventListener("click", () => openDrawer("blue"));
  backdrop.addEventListener("click", closeDrawers);
  for (const b of closeBtns) b.addEventListener("click", closeDrawers);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawers();
  });

  // ---------- tournament controls ----------

  let lastStatus = "idle";
  let polling = false;

  function setRunningUI(isRunning) {
    runNextBtn.disabled = isRunning;
    runFreshBtn.disabled = isRunning;
    modelSel.disabled = isRunning;
    roundsInput.disabled = isRunning;
  }

  async function refreshAfterRun(autoSelectLatest) {
    manifest = await loadManifest();
    populateRoundSelect(manifest);
    if (autoSelectLatest && manifest && manifest.rounds && manifest.rounds.length > 0) {
      const latest = manifest.rounds[manifest.rounds.length - 1];
      await loadAndRender(latest.file);
      roundSelect.value = latest.file;
    }
  }

  async function pollLoop() {
    if (polling) return;
    polling = true;
    while (true) {
      const s = await fetchState();
      if (!s) { await sleep(2000); continue; }
      if (s.status === "running") {
        statusEl.style.display = "";
        statusEl.className = "pill running";
        statusEl.textContent = s.message || "running";
        setRunningUI(true);
        lastStatus = "running";
        await sleep(1500);
        continue;
      }
      // not running
      if (lastStatus === "running") {
        // Just finished — refresh
        if (s.status === "done") {
          statusEl.className = "pill done";
          statusEl.textContent = s.message || "done";
        } else if (s.status === "error") {
          statusEl.className = "pill error";
          statusEl.textContent = s.message || "error";
        }
        await refreshAfterRun(true);
        setRunningUI(false);
      } else {
        // Stayed idle / done across loops
        if (s.status === "idle") {
          statusEl.style.display = "none";
        }
        setRunningUI(false);
      }
      lastStatus = s.status;
      await sleep(2000);
    }
  }

  // Initial state probe so disabled-state is right if a run is already going.
  const initial = await fetchState();
  if (initial && initial.status === "running") {
    statusEl.style.display = "";
    statusEl.className = "pill running";
    statusEl.textContent = initial.message || "running";
    setRunningUI(true);
    lastStatus = "running";
  }
  pollLoop();

  runNextBtn.addEventListener("click", async () => {
    const model = modelSel.value;
    const rounds = parseInt(roundsInput.value, 10) || 1;
    if (!model) { alert("No model selected"); return; }
    try {
      setRunningUI(true);
      statusEl.style.display = "";
      statusEl.className = "pill running";
      statusEl.textContent = "starting…";
      lastStatus = "running";
      await startRun("continue", model, rounds);
    } catch (e) {
      alert(`Failed to start: ${e.message}`);
      setRunningUI(false);
    }
  });

  runFreshBtn.addEventListener("click", async () => {
    if (manifest && manifest.rounds && manifest.rounds.length > 0) {
      if (!confirm(`This will discard the existing ${manifest.rounds.length} round(s) and start a new tournament. Continue?`)) return;
    }
    const model = modelSel.value;
    const rounds = parseInt(roundsInput.value, 10) || 1;
    if (!model) { alert("No model selected"); return; }
    try {
      setRunningUI(true);
      statusEl.style.display = "";
      statusEl.className = "pill running";
      statusEl.textContent = "starting fresh…";
      lastStatus = "running";
      await startRun("fresh", model, rounds);
    } catch (e) {
      alert(`Failed to start: ${e.message}`);
      setRunningUI(false);
    }
  });

  document.addEventListener("keydown", (e) => {
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return;
    if (e.key === " ") { e.preventDefault(); pb.toggle(); }
    if (e.key === "ArrowRight") { pb.pause(); pb.step(1); }
    if (e.key === "ArrowLeft") { pb.pause(); pb.setFrame(pb.frameIdx - 1, 0); }
  });

  function loop(now) { if (pb) pb.tick(now); requestAnimationFrame(loop); }
  requestAnimationFrame(loop);
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

main().catch((e) => {
  console.error(e);
  document.body.innerHTML = `<pre style="color:#e04848;padding:20px">${e.stack || e}</pre>`;
});
