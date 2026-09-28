import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const wikiRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "Wiki");

const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

try {
    await page.goto(pathToFileURL(path.join(wikiRoot, "index.html")).href);
    await page.waitForLoadState("networkidle");
    await page.locator(".character-card").first().waitFor();

    const modal = page.locator("#characterModal");
    if (await modal.evaluate(element => getComputedStyle(element).display) !== "none") {
        throw new Error("Modal phải ẩn khi trang vừa tải");
    }

    await page.locator(".character-card").first().click();
    if (await modal.evaluate(element => getComputedStyle(element).display) !== "flex") {
        throw new Error("Modal phải hiện sau khi bấm thẻ nhân vật");
    }

    const panelBackground = await page.locator(".modal-panel")
        .evaluate(element => getComputedStyle(element).backgroundColor);
    if (panelBackground === "rgba(0, 0, 0, 0)") {
        throw new Error("Panel chi tiết chưa nhận style nền");
    }

    await page.locator("#closeModal").click();
    if (await modal.evaluate(element => getComputedStyle(element).display) !== "none") {
        throw new Error("Modal phải ẩn sau khi bấm đóng");
    }

    console.log("PASS: modal ẩn/hiện/đóng đúng và panel có style");
} finally {
    await browser.close();
}
