import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { concatFrames } from "./audio/pcm.js";
import { writeWav } from "./audio/wav.js";
import { ECHO_MEDIA } from "./media.js";
import { runSampleCall } from "./pipeline/runSample.js";
import type { MetricEvent } from "./types.js";

const DEFAULT_INPUT = path.join("tests", "audio", "sample_call.wav");
const DEFAULT_METADATA = path.join("tests", "audio", "sample_call.json");
const DEFAULT_OUT = path.join("artifacts", "sample_call_response.wav");
const DEFAULT_METRICS = path.join("artifacts", "sample_call_metrics.json");

export function main(argv: readonly string[] = process.argv.slice(2)): number {
  try {
    const args = parseArgs(argv);
    const result = runSampleCall({
      wavPath: args.input,
      metadataPath: args.metadata,
    });
    mkdirSync(path.dirname(args.out), { recursive: true });
    mkdirSync(path.dirname(args.metrics), { recursive: true });
    const samples = concatFrames(result.outbound);
    writeFileSync(args.out, writeWav(samples, ECHO_MEDIA.sampleRateHz));
    const report = {
      transcript: result.transcript,
      reply: result.replyText,
      endpointReason: result.endpointReason,
      partials: result.partials,
      outboundFrames: result.outbound.length,
      outboundDurationMs: (samples.length / ECHO_MEDIA.sampleRateHz) * 1000,
      inputDurationMs: result.inputDurationMs,
      metrics: result.metrics,
    };
    writeFileSync(args.metrics, `${JSON.stringify(report, null, 2)}\n`);
    printReport(args, report);
    return 0;
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`ECHO sample failed: ${message}\n`);
    return 1;
  }
}

function printReport(
  args: { input: string; out: string; metrics: string },
  report: {
    transcript: string;
    reply: string;
    endpointReason: string | null;
    outboundFrames: number;
    outboundDurationMs: number;
    inputDurationMs: number;
    metrics: readonly MetricEvent[];
  },
): void {
  const lines = [
    "ECHO sample call",
    `  inbound: ${args.input} (${Math.round(report.inputDurationMs)} ms)`,
    `  final transcript: ${report.transcript}`,
    `  reply: ${report.reply}`,
    `  endpoint: ${report.endpointReason ?? "none"}`,
    `  outbound: ${args.out} (${report.outboundFrames} frames, ${Math.round(report.outboundDurationMs)} ms)`,
    `  metrics file: ${args.metrics}`,
    "  metrics:",
  ];
  for (const metric of report.metrics) {
    const audio = metric.audioTimeMs === undefined ? "" : ` audio ${metric.audioTimeMs} ms`;
    lines.push(
      `    ${metric.name.padEnd(28)} value ${metric.valueMs} ms  at ${metric.atMs} ms${audio}`,
    );
  }
  process.stdout.write(`${lines.join("\n")}\n`);
}

function parseArgs(argv: readonly string[]): { input: string; metadata: string; out: string; metrics: string } {
  let input = DEFAULT_INPUT;
  let metadata = DEFAULT_METADATA;
  let out = DEFAULT_OUT;
  let metrics = DEFAULT_METRICS;
  for (let i = 0; i < argv.length; i += 1) {
    const flag = argv[i];
    const value = argv[i + 1];
    if (value === undefined) {
      throw new Error(`Missing value for ${flag ?? "argument"}`);
    }
    switch (flag) {
      case "--input":
        input = value;
        i += 1;
        break;
      case "--metadata":
        metadata = value;
        i += 1;
        break;
      case "--out":
        out = value;
        i += 1;
        break;
      case "--metrics":
        metrics = value;
        i += 1;
        break;
      default:
        throw new Error(`Unknown argument ${flag ?? ""}`);
    }
  }
  return { input, metadata, out, metrics };
}

const invokedDirectly =
  process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href;

if (invokedDirectly) {
  process.exitCode = main();
}
