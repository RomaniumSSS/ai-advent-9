const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const baseUrl = process.argv[2] || "http://127.0.0.1:8044";
const root = path.resolve(__dirname, "..");
const results = path.join(root, "results");
const output = path.join(__dirname, "day13-task-state.webm");
const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const objective = "Подготовить короткий чек-лист canary-релиза на 10%: ровно 5 пунктов, до 500 знаков";

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitReady(page, selector, timeout = 300_000) {
  await page.waitForFunction((target) => {
    const element = document.querySelector(target);
    return element && !element.hidden && !element.disabled;
  }, selector, { timeout });
}

(async () => {
  fs.mkdirSync(results, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: chrome });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    recordVideo: { dir: results, size: { width: 1280, height: 800 } },
  });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("Failed to load resource")) {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => errors.push(String(error)));

  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.locator("#task-objective").fill(objective);
  await page.locator("#start-task").click();
  await page.locator("#task-state").scrollIntoViewIfNeeded();
  await pause(1800);

  // Настоящий provider формирует planning proposal; кнопки заблокированы на время call.
  await page.locator("#workflow-run").click();
  await waitReady(page, "#workflow-approve");
  await pause(2800);

  // Durable proposal должен пережить pause + новый экземпляр без повторного call.
  await page.locator("#pause").click();
  await pause(1200);
  await page.locator("#restart").click();
  await pause(1400);
  await page.locator("#resume").click();
  await waitReady(page, "#workflow-approve");
  await pause(1800);

  // Пользователь, а не модель, выполняет переходы по проверенной таблице FSM.
  await page.locator("#task-result").fill("План принят: canary 10%, метрики, rollback и окно наблюдения");
  await page.locator("#advance").click();
  await page.waitForFunction(() => document.querySelector("#expected")?.textContent === "submit_result");
  await pause(1800);
  await page.locator("#task-result").fill("Чек-лист подготовлен; фактический запуск оставлен оператору");
  await page.locator("#advance").click();
  await page.waitForFunction(() => document.querySelector("#expected")?.textContent === "approve");
  await pause(1800);
  await page.locator("#task-result").fill("Проверено: 5 пунктов, canary 10%, критерии отката указаны");
  await page.locator("#advance").click();
  await page.waitForFunction(() => document.querySelector("#expected")?.textContent === "нет");
  await pause(3200);
  await page.screenshot({
    path: path.join(results, "video-live-final.png"),
    fullPage: true,
  });

  const video = page.video();
  await context.close();
  const recorded = await video.path();
  fs.copyFileSync(recorded, output);
  await browser.close();
  if (errors.length) throw new Error(`Ошибки страницы: ${errors.join("; ")}`);
  console.log(JSON.stringify({ output, objective, consoleErrors: errors.length }));
})().catch((error) => { console.error(error); process.exit(1); });
