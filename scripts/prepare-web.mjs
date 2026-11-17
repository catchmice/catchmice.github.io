#!/usr/bin/env node
/**
 * CatchMICE 앱 웹 번들 준비 스크립트
 * ------------------------------------------------------------
 * 저장소 루트의 "정적 사이트 실행 파일만" 골라 www/ 로 깨끗하게 복사합니다.
 * (node_modules, android, scripts, .git 같은 개발용 폴더는 절대 들어가지 않습니다.)
 *
 * 사용법:  npm run prepare:web
 * 결과물:  www/  ← Capacitor가 이 폴더를 앱 안에 넣습니다 (오프라인에서도 동작)
 */
import { cp, mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(ROOT, "www");

/** 앱이 실행되는 데 반드시 필요한 파일 (없으면 실패) */
const REQUIRED_FILES = [
  "index.html",
  "404.html",
  "sw.js",
  "manifest.webmanifest",
  "jobs.json",
  "news.json",
  "events.json",
  "papers.json",
];

/** 있으면 함께 넣는 보조 파일 */
const OPTIONAL_FILES = ["robots.txt"];

/** 이미지·아이콘과 섹션별 짧은 주소(index.html 리다이렉트 스텁) 폴더 */
const REQUIRED_DIRS = ["icons", "img"];
const OPTIONAL_DIRS = ["home", "jobs", "news", "papers", "guide", "calendar", "crew", "walk"];

async function isDir(p) {
  try {
    return (await stat(p)).isDirectory();
  } catch {
    return false;
  }
}

async function isFile(p) {
  try {
    return (await stat(p)).isFile();
  } catch {
    return false;
  }
}

async function main() {
  const missing = [];
  for (const f of REQUIRED_FILES) if (!(await isFile(join(ROOT, f)))) missing.push(f);
  for (const d of REQUIRED_DIRS) if (!(await isDir(join(ROOT, d)))) missing.push(d + "/");
  if (missing.length) {
    console.error("✗ 웹 번들에 필요한 파일이 없습니다: " + missing.join(", "));
    process.exit(1);
  }

  await rm(OUT, { recursive: true, force: true });
  await mkdir(OUT, { recursive: true });

  const copied = [];
  for (const f of REQUIRED_FILES.concat(OPTIONAL_FILES)) {
    if (!(await isFile(join(ROOT, f)))) continue;
    await cp(join(ROOT, f), join(OUT, f));
    copied.push(f);
  }
  for (const d of REQUIRED_DIRS.concat(OPTIONAL_DIRS)) {
    if (!(await isDir(join(ROOT, d)))) continue;
    await cp(join(ROOT, d), join(OUT, d), { recursive: true });
    copied.push(d + "/");
  }

  // www/ 가 실수로 커밋되지 않도록 안전장치 (루트 .gitignore 와 별개)
  await writeFile(join(OUT, ".gitignore"), "*\n", "utf8");

  // manifest.webmanifest 가 가리키는 아이콘이 실제로 번들에 있는지 확인
  const manifest = JSON.parse(await readFile(join(OUT, "manifest.webmanifest"), "utf8"));
  const missingIcons = (manifest.icons || [])
    .map((i) => i.src)
    .filter((src) => !existsSync(join(OUT, src)));
  if (missingIcons.length) {
    console.error("✗ manifest.webmanifest 가 가리키는 아이콘이 없습니다: " + missingIcons.join(", "));
    process.exit(1);
  }

  const html = await readFile(join(OUT, "index.html"), "utf8");
  if (!html.includes("manifest.webmanifest")) {
    console.warn("! 경고: index.html 에서 manifest.webmanifest 링크를 찾지 못했습니다.");
  }

  console.log("✓ www/ 준비 완료 (" + copied.length + "개 항목)");
  for (const c of copied) console.log("  - " + c);
  console.log("  경로: " + relative(process.cwd(), OUT) + "/");
}

main().catch((err) => {
  console.error("✗ prepare-web 실패: " + (err && err.stack ? err.stack : err));
  process.exit(1);
});
