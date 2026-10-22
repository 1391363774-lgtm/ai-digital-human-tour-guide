/** Incremental text segmentation. Sentence IDs are assigned by the caller, once. */
export class SentenceBuffer {
  private pending = ''
  constructor(private readonly maxChars = 160) {
    if (maxChars < 2) throw new Error('maxChars must be at least 2')
  }

  push(delta: string): string[] {
    this.pending += delta
    const output: string[] = []
    while (this.pending) {
      // A decimal such as 1.5 is not a sentence boundary.
      // Hold a trailing dot until the next delta/flush disambiguates a decimal.
      const boundary = /[。！？!?；;\n]|\.(?=\D)/u.exec(this.pending)
      const chars = Array.from(this.pending)
      let end = boundary ? boundary.index + boundary[0].length : 0
      if ((!end || end > this.maxChars) && chars.length >= this.maxChars) {
        const prefix = chars.slice(0, this.maxChars).join('')
        const softBreak = Math.max(prefix.lastIndexOf('，'), prefix.lastIndexOf(','), prefix.lastIndexOf(' '))
        end = softBreak >= this.maxChars / 2 ? softBreak + 1 : prefix.length
      }
      if (!end) break
      const text = this.pending.slice(0, end).trim()
      this.pending = this.pending.slice(end)
      if (text) output.push(text)
    }
    return output
  }

  flush(): string[] {
    const text = this.pending.trim()
    this.pending = ''
    return text ? [text] : []
  }
}
