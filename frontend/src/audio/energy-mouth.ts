/** Audio amplitude / activity, deliberately not phoneme alignment. */
export class EnergyMouth {
  private value = 0
  constructor(private readonly silenceThreshold = 0.012) {}

  sample(samples: Float32Array, advancing: boolean): number {
    if (!advancing || !samples.length) return this.reset()
    let squareSum = 0
    for (const sample of samples) squareSum += sample * sample
    const rms = Math.sqrt(squareSum / samples.length)
    if (!Number.isFinite(rms) || rms <= this.silenceThreshold) return this.reset()
    const target = Math.min(1, (rms - this.silenceThreshold) * 8)
    const smoothing = target > this.value ? 0.55 : 0.3
    this.value += (target - this.value) * smoothing
    return this.value
  }

  reset(): number { this.value = 0; return 0 }
}
