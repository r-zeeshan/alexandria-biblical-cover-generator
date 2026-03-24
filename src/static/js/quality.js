function _clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value));
}

function _getImageData(imageEl, size = 192) {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(imageEl, 0, 0, size, size);
  return ctx.getImageData(0, 0, size, size).data;
}

function _computeBasicMetrics(imageEl) {
  const data = _getImageData(imageEl, 192);
  let mean = 0;
  let sat = 0;
  let contrastAccumulator = 0;
  let edgeAccumulator = 0;

  for (let i = 0; i < data.length; i += 4) {
    const r = data[i] / 255;
    const g = data[i + 1] / 255;
    const b = data[i + 2] / 255;
    const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    mean += lum;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    sat += max - min;
    contrastAccumulator += lum * lum;
    if ((i / 4) % 192 !== 0) {
      const prevR = data[i - 4] / 255;
      const prevG = data[i - 3] / 255;
      const prevB = data[i - 2] / 255;
      edgeAccumulator += Math.abs(r - prevR) + Math.abs(g - prevG) + Math.abs(b - prevB);
    }
  }

  const px = data.length / 4;
  mean /= px;
  sat /= px;
  const variance = Math.max(0, contrastAccumulator / px - mean * mean);
  const contrast = Math.sqrt(variance);
  const edge = edgeAccumulator / px;

  return { mean, sat, contrast, edge };
}

window.Quality = {
  async scoreGeneratedImage(imageEl) {
    const m = _computeBasicMetrics(imageEl);
    const brightnessScore = 1 - Math.abs(m.mean - 0.52) * 1.5;
    const colorScore = _clamp(m.sat * 2.1);
    const contrastScore = _clamp(m.contrast * 4.5);
    const edgeScore = _clamp(m.edge * 3.0);
    return _clamp((brightnessScore + colorScore + contrastScore + edgeScore) / 4);
  },

  async getDetailedScores(imageEl) {
    const m = _computeBasicMetrics(imageEl);
    const edge = _clamp(m.edge * 3.0);
    const centerMass = _clamp(1 - Math.abs(m.mean - 0.5));
    const circular = _clamp((edge + centerMass) / 2);
    const color = _clamp(m.sat * 2.1);
    const brightness = _clamp(1 - Math.abs(m.mean - 0.52) * 1.5);
    const contrast = _clamp(m.contrast * 4.5);
    const diversity = _clamp((color + contrast) / 2);

    const overall = _clamp(
      edge * 0.25 +
      centerMass * 0.20 +
      circular * 0.20 +
      color * 0.12 +
      brightness * 0.08 +
      contrast * 0.08 +
      diversity * 0.07
    );

    return {
      overall,
      edge,
      center_mass: centerMass,
      circular,
      color,
      brightness,
      contrast,
      diversity,
    };
  },
};
