#!/usr/bin/env node
/* sinereel — turns a reel config into a folder of PNG frames.
   Usage: node src/render.js [config.json] [--out frames] */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const args = process.argv.slice(2);
const configPath = path.resolve(args.find(a => !a.startsWith('--')) || 'reel.config.json');
const outFlag = args.indexOf('--out');
const outDir = path.resolve(outFlag > -1 ? args[outFlag + 1] : 'build/frames');

const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
const duration = config.scenes.reduce((a, s) => a + s.dur, 0);
const fps = config.fps || 24;
const total = Math.round(duration * fps);

// @fontsource packages are optional: without them the browser falls back to
// system fonts and everything still renders, just not in the intended face.
function fontFaces() {
  const root = path.join(__dirname, '..', 'node_modules', '@fontsource');
  const want = [
    ['Inter', 'inter/files/inter-latin-800-normal.woff2', 800],
    ['Inter', 'inter/files/inter-latin-600-normal.woff2', 600],
    ['Inter', 'inter/files/inter-latin-400-normal.woff2', 400],
    ['JetBrains Mono', 'jetbrains-mono/files/jetbrains-mono-latin-500-normal.woff2', 500],
    ['JetBrains Mono', 'jetbrains-mono/files/jetbrains-mono-latin-700-normal.woff2', 700],
  ];
  const css = [];
  for (const [family, rel, weight] of want) {
    const file = path.join(root, rel);
    if (!fs.existsSync(file)) continue;
    const b64 = fs.readFileSync(file).toString('base64');
    css.push(`@font-face{font-family:'${family}';font-weight:${weight};` +
      `src:url(data:font/woff2;base64,${b64}) format('woff2')}`);
  }
  if (!css.length) console.warn('! no @fontsource fonts found — falling back to system fonts');
  return css.join('\n');
}

(async () => {
  fs.rmSync(outDir, { recursive: true, force: true });
  fs.mkdirSync(outDir, { recursive: true });

  const launch = {};
  if (process.env.CHROMIUM_PATH) launch.executablePath = process.env.CHROMIUM_PATH;
  const browser = await chromium.launch(launch);
  const page = await browser.newPage({
    viewport: { width: config.width, height: config.height },
    deviceScaleFactor: 1,
  });

  const html = fs.readFileSync(path.join(__dirname, 'scene.html'), 'utf8')
    .replace('<style>', `<style>\n${fontFaces()}\n`)
    .replace('<script>', `<script>\nwindow.REEL = ${JSON.stringify(config)};\n`);

  await page.setContent(html, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);

  const started = Date.now();
  for (let i = 0; i < total; i++) {
    await page.evaluate(t => window.setT(t), i / fps);
    await page.screenshot({ path: path.join(outDir, String(i).padStart(4, '0') + '.png') });
    if (i % fps === 0) process.stdout.write(`\r  frame ${i}/${total}`);
  }
  await browser.close();

  const secs = ((Date.now() - started) / 1000).toFixed(1);
  console.log(`\r  ${total} frames in ${secs}s -> ${path.relative(process.cwd(), outDir)}`);
})().catch(e => { console.error(e); process.exit(1); });
