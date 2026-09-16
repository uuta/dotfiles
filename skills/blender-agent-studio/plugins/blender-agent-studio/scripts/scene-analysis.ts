import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { runBlender } from "./blender-process.ts";

const pluginRoot = resolve(import.meta.dir, "..");

export function runtimeExecutable(): string {
  const executable = process.env.BAS_RUNTIME_EXECUTABLE ?? join(pluginRoot, "runtime", "target", "release", process.platform === "win32" ? "bas-runtime.exe" : "bas-runtime");
  if (!existsSync(executable)) throw new Error(`Scene analysis runtime is not built. Run bun run setup:runtime in ${pluginRoot}, or set BAS_RUNTIME_EXECUTABLE to a built bas-runtime binary. Existing inspection/render tools do not require Rust.`);
  return executable;
}

export async function analyzeSceneIR(scene: unknown, options: Record<string, unknown>, timeoutMs = 30_000) {
  const input = JSON.stringify({ scene, options });
  if (Buffer.byteLength(input) > 16 * 1024 * 1024) throw new Error("SceneIR request exceeds 16 MiB");
  const proc = Bun.spawn([runtimeExecutable()], { stdin: new Blob([input]), stdout: "pipe", stderr: "pipe", windowsHide: true });
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; proc.kill(); }, timeoutMs);
  try {
    const [stdout, stderr, exitCode] = await Promise.all([new Response(proc.stdout).text(), new Response(proc.stderr).text(), proc.exited]);
    if (timedOut) throw new Error("Scene analysis timed out");
    if (exitCode !== 0) throw new Error(`Scene analysis failed: ${stderr.trim()}`);
    return JSON.parse(stdout) as Record<string, any>;
  } finally { clearTimeout(timer); }
}

export async function describeAsset(args: {
  assetPath: string; outputJson?: string; blenderPath?: string; timeoutMs: number;
  options: Record<string, unknown>;
}) {
  runtimeExecutable(); // Fail before starting Blender if setup is missing.
  const output = args.outputJson ? resolve(args.outputJson) : undefined;
  if (output && existsSync(output)) throw new Error("outputJson must be a new file");
  const temporary = await mkdtemp(join(tmpdir(), "bas-scene-ir-"));
  try {
    const sceneFile = join(temporary, "scene.json");
    const process = await runBlender({ blenderPath: args.blenderPath,
      scriptPath: join(pluginRoot, "skills/blender-asset-validation/scripts/extract_scene_ir.py"),
      scriptArgs: ["--input", resolve(args.assetPath), "--output", sceneFile], timeoutMs: args.timeoutMs });
    if (process.timedOut || process.exitCode !== 0) throw new Error(`Scene extraction failed${process.timedOut ? " (timeout)" : ""}: ${process.stderr || process.stdout}`);
    if ((await stat(sceneFile)).size > 15 * 1024 * 1024) throw new Error("SceneIR exceeds 15 MiB");
    const scene = JSON.parse(await readFile(sceneFile, "utf8"));
    const analysis = await analyzeSceneIR(scene, args.options);
    if (output) await writeFile(output, JSON.stringify({ scene, analysis }, null, 2), { flag: "wx" });
    return { ...analysis, outputJson: output ?? null };
  } finally { await rm(temporary, { recursive: true, force: true }); }
}
