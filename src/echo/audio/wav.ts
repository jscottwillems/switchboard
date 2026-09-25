import { decodePcmS16le, encodePcmS16le } from "./pcm.js";

export interface WavAudio {
  sampleRateHz: number;
  channels: number;
  samples: Int16Array;
}

export function readWav(bytes: Uint8Array): WavAudio {
  if (bytes.byteLength < 12) {
    throw new Error("WAV is too short");
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (ascii(bytes, 0, 4) !== "RIFF" || ascii(bytes, 8, 4) !== "WAVE") {
    throw new Error("Not a RIFF WAVE file");
  }

  let format: { audioFormat: number; channels: number; sampleRateHz: number; bitsPerSample: number } | null =
    null;
  let data: Uint8Array | null = null;
  let offset = 12;
  while (offset + 8 <= bytes.byteLength) {
    const id = ascii(bytes, offset, 4);
    const size = view.getUint32(offset + 4, true);
    const start = offset + 8;
    const end = start + size;
    if (end > bytes.byteLength) {
      throw new Error(`WAV chunk ${id} extends past the file`);
    }
    if (id === "fmt ") {
      if (size < 16) {
        throw new Error("WAV fmt chunk is too small");
      }
      format = {
        audioFormat: view.getUint16(start, true),
        channels: view.getUint16(start + 2, true),
        sampleRateHz: view.getUint32(start + 4, true),
        bitsPerSample: view.getUint16(start + 14, true),
      };
    } else if (id === "data") {
      data = bytes.subarray(start, end);
    }
    offset = end + (size % 2);
  }

  if (!format || !data) {
    throw new Error("WAV is missing fmt or data");
  }
  if (format.audioFormat !== 1 || format.bitsPerSample !== 16) {
    throw new Error(
      `ECHO sample audio must be PCM 16-bit, received format ${format.audioFormat} / ${format.bitsPerSample}-bit`,
    );
  }
  if (format.channels < 1) {
    throw new Error("WAV has no channels");
  }
  return {
    sampleRateHz: format.sampleRateHz,
    channels: format.channels,
    samples: decodePcmS16le(data),
  };
}

export function writeWav(samples: Int16Array, sampleRateHz: number): Uint8Array {
  const data = encodePcmS16le(samples);
  const buffer = new ArrayBuffer(44 + data.byteLength);
  const bytes = new Uint8Array(buffer);
  const view = new DataView(buffer);
  writeAscii(bytes, 0, "RIFF");
  view.setUint32(4, 36 + data.byteLength, true);
  writeAscii(bytes, 8, "WAVE");
  writeAscii(bytes, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRateHz, true);
  view.setUint32(28, sampleRateHz * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(bytes, 36, "data");
  view.setUint32(40, data.byteLength, true);
  bytes.set(data, 44);
  return bytes;
}

function ascii(bytes: Uint8Array, offset: number, length: number): string {
  let text = "";
  for (let i = 0; i < length; i += 1) {
    text += String.fromCharCode(bytes[offset + i] ?? 0);
  }
  return text;
}

function writeAscii(bytes: Uint8Array, offset: number, text: string): void {
  for (let i = 0; i < text.length; i += 1) {
    bytes[offset + i] = text.charCodeAt(i);
  }
}
