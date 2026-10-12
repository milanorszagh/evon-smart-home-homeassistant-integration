import test from "node:test";
import assert from "node:assert/strict";

// Lives in its own file: index.test.js force-exits its process after 100 ms
// (importing index.js starts the MCP server), which would cut this test short.
test("stdout stays clean at startup even when a .env file is present (stdio JSON-RPC stream)", async () => {
  // dotenv logs "injecting env (N) from .env" unless quiet; on stdout that would
  // corrupt the MCP stdio transport. Spawn the real server in a temp cwd with a
  // .env file and assert nothing reaches stdout before the first request.
  const { spawn } = await import("node:child_process");
  const { mkdtemp, writeFile } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const { join } = await import("node:path");

  const cwd = await mkdtemp(join(tmpdir(), "evon-mcp-"));
  await writeFile(join(cwd, ".env"), "SOME_VAR=value\n");

  const child = spawn(process.execPath, [new URL("../dist/index.js", import.meta.url).pathname], {
    cwd,
    env: { ...process.env, EVON_HOST: "http://example.com", EVON_USERNAME: "user", EVON_PASSWORD: "pass" },
    stdio: ["pipe", "pipe", "pipe"],
  });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (chunk) => { stdout += chunk; });
  child.stderr.on("data", (chunk) => { stderr += chunk; });
  await new Promise((resolve) => setTimeout(resolve, 1500));
  child.kill("SIGTERM");
  await new Promise((resolve) => child.on("exit", resolve));

  assert.match(stderr, /running on stdio/, "server started");
  assert.equal(stdout, "", `stdout must carry only JSON-RPC, got: ${JSON.stringify(stdout)}`);
});
