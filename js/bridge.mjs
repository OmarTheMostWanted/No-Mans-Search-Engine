import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { readFile } from "node:fs/promises";
import readline from "node:readline";

import { init, getSystem } from "../nms-galactic-map/nms-tools/nms-lookup.js";
import { systemAttributes, planetSeeds } from "../nms-galactic-map/nms-core/system.js";
import { rollSystemFlavorFromAttrs } from "../nms-galactic-map/nms-core/economy.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..");
const corePath = path.join(repoRoot, "nms-galactic-map", "nms-core");
const letterMapPath = path.join(corePath, "letter-map");

// The upstream letter-map loader uses fetch(). In Node, adapt file: URLs so
// the checked-in JSON shards are read locally (no server, network, or mocks).
const nativeFetch = globalThis.fetch;
globalThis.fetch = async (input, ...options) => {
    const url = String(input);
    if (url.startsWith("file:")) {
        try {
            const contents = await readFile(fileURLToPath(url), "utf8");
            return { ok: true, status: 200, json: async () => JSON.parse(contents) };
        } catch (error) {
            return { ok: false, status: 404, json: async () => { throw error; } };
        }
    }
    return nativeFetch(input, ...options);
};

const rl = readline.createInterface({ input: process.stdin, terminal: false });
let ready;
async function ensureReady() {
    ready ??= init(pathToFileURL(letterMapPath + path.sep).href);
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
function mulberry32(seed) {
    let state = (seed >>> 0) || 1;
    return () => {
        state |= 0;
        state = state + 0x6D2B79F5 | 0;
        let value = Math.imul(state ^ (state >>> 15), 1 | state);
        value = value + Math.imul(value ^ (value >>> 7), 61 | value) ^ value;
        return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
    };
}

async function lookup(item) {
    if (!item || typeof item !== "object") throw new Error("system request must be an object");
    validateAddress(item.portal_code);
    const galaxy = Number(item.galaxy ?? 0);
    validateGalaxy(galaxy);
    const address = item.portal_code.toUpperCase();
    const code = BigInt(`0x${address}`);
    const system = await getSystem(address, galaxy);

    // nms-lookup currently uses its flavour-only fallback. Re-derive the
    // actual attributes with the submodule's portal-code generator and use
    // its attrs-aware flavour routine so filters reflect the NMS RNG data.
    const attrs = systemAttributes(code, galaxy);
    const bodies = planetSeeds(code, galaxy);
    const flavorRng = mulberry32(Number(code & 0xFFFFFFFFn) ^ (galaxy * 0x9E3779B9));
    const flavor = rollSystemFlavorFromAttrs(flavorRng, attrs);
    const colors = ["yellow", "green", "blue", "red", "purple"];
    return {
        ...system,
        starType: colors[attrs.star_type] ?? system.starType,
        planets: bodies.planet_count,
        moons: bodies.moon_count,
        race: flavor.race,
        economy: flavor.econName,
        econType: flavor.econType,
        econTier: flavor.econTier,
        econDesc: flavor.econDesc,
        conflict: flavor.conflict,
        conTier: flavor.conTier,
        abandoned: attrs.abandoned,
        uncharted: attrs.uncharted,
        outlaw: attrs.pirate,
        isBlackHole: ((code >> 32n) & 0xFFFn) === 0x079n,
        isAtlas: ((code >> 32n) & 0xFFFn) === 0x07An,
        address,
        galaxy,
    };
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
        process.stdout.write(JSON.stringify({ success: false, error: error?.stack ?? String(error) }) + "\n");
    }
}
