import { init, getSystem } from "../nms-galactic-map/nms-tools/nms-lookup.js";

import readline from "node:readline";

const rl = readline.createInterface({
    input: process.stdin,
    terminal: false,
});

async function ensureReady() {
    await init("../nms-galactic-map/nms-core");
}

async function handleRequest(request) {
    switch (request.action) {
        case "lookup": {
            await ensureReady();
            return await getSystem(
                request.portal_code,
                Number(request.galaxy ?? 0)
            );
        }

        case "batch": {
            if (!Array.isArray(request.systems)) {
                throw new Error("'systems' must be an array.");
            }

            await ensureReady();

            const results = [];

            for (const item of request.systems) {
                const system = await getSystem(
                    item.portal_code,
                    Number(item.galaxy ?? 0)
                );
                results.push(system);
            }

            return results;
        }

        default:
            throw new Error(`Unknown action: ${request.action}`);
    }
}

for await (const line of rl) {
    if (!line.trim()) continue;

    try {
        const request = JSON.parse(line);
        const result = await handleRequest(request);

        process.stdout.write(
            JSON.stringify({
                success: true,
                data: result,
            }) + "\n"
        );
    } catch (error) {
        process.stdout.write(
            JSON.stringify({
                success: false,
                error: error.message,
            }) + "\n"
        );
    }
}
