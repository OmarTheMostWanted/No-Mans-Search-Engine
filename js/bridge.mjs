import path from "node:path";
import { fileURLToPath } from "node:url";
import readline from "node:readline";

import { init, getSystem } from "../nms-galactic-map/nms-tools/nms-lookup.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const corePath = path.resolve(here, "../nms-galactic-map/nms-core");
const rl = readline.createInterface({ input: process.stdin, terminal: false });
let ready;

async function ensureReady() {
    ready ??= init(corePath);
    await ready;
}

function validateAddress(address) {
    if (typeof address !== "string" || !/^[0-9A-Fa-f]{12}$/.test(address)) {
        throw new Error("portal_code must be exactly 12 hexadecimal characters");
    }
}

function validateGalaxy(galaxy) {
    if (!Number.isInteger(galaxy) || galaxy < 0 || galaxy > 255) {
        throw new Error("galaxy must be an integer from 0 to 255");
    }
}

async function lookup(item) {
    validateAddress(item.portal_code);
    const galaxy = Number(item.galaxy ?? 0);
    validateGalaxy(galaxy);
    const address = item.portal_code.toUpperCase();
    const system = await getSystem(address, galaxy);
    // Strictly preserve the documented nms-lookup.js response contract.
    const required = ["address", "galaxy", "starType", "planets", "moons", "race", "economy", "econTier", "conflict", "conTier", "abandoned", "uncharted", "outlaw", "isBlackHole", "isAtlas", "coords"];
    for (const key of required) {
        if (!(key in system)) throw new Error(`nms-lookup response missing required field: ${key}`);
    }
    return system;
}

async function handle(request) {
    if (!request || typeof request !== "object") throw new Error("request must be an object");
    await ensureReady();
    if (request.action === "lookup") return lookup(request);
    if (request.action === "batch") {
        if (!Array.isArray(request.systems)) throw new Error("systems must be an array");
        return Promise.all(request.systems.map(lookup));
    }
    throw new Error(`Unknown action: ${request.action}`);
}

for await (const line of rl) {
    if (!line.trim()) continue;
    try {
        const data = await handle(JSON.parse(line));
        process.stdout.write(JSON.stringify({ success: true, data }) + "\n");
    } catch (error) {
        process.stdout.write(JSON.stringify({ success: false, error: error?.message ?? String(error) }) + "\n");
    }
}
