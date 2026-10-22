"""Explicit offline demonstration adapters. No model calls or speech synthesis."""
import asyncio
from io import BytesIO
import math
import struct
import wave

from app.services.llm_client import BaseLLMClient, LocalFallbackLLMClient, LLMClientError

# Demo server is intentionally single-worker; changed only through an admin route.
fault = 'none'


class DemoLLMClient(BaseLLMClient):
    provider = 'simulated_model'
    model = 'delayed-extractive-demo'

    def chat(self, messages, temperature=0.1):
        if fault != 'none':
            raise LLMClientError('injected demo failure')
        response = LocalFallbackLLMClient().chat(messages, temperature)
        from app.services.llm_client import LLMResponse
        return LLMResponse(response.content, self.provider, self.model)

    async def achat_stream(self, messages, temperature=0.1):
        selected_fault = fault
        if selected_fault == 'empty': return
        if selected_fault == 'timeout':
            await asyncio.sleep(0.15)
            raise LLMClientError('injected timeout')
        answer = LocalFallbackLLMClient().chat(messages, temperature).content
        for offset in range(0, len(answer), 8):
            await asyncio.sleep(0.06)
            yield answer[offset:offset + 8]
            if selected_fault == 'partial': raise LLMClientError('injected mid-stream failure')


def demo_audio(text: str, rate: float) -> bytes:
    """PCM tone with fixed silent regions, not Chinese speech or phoneme timing."""
    sample_rate = 16000
    duration = min(4.0, max(1.2, len(text) * 0.06 / rate))
    samples = bytearray()
    for index in range(int(duration * sample_rate)):
        t = index / sample_rate
        sounding = 0.2 < t % 1.0 < 0.65
        value = int(6500 * math.sin(2 * math.pi * 220 * t)) if sounding else 0
        samples.extend(struct.pack('<h', value))
    output = BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(sample_rate)
        audio.writeframes(samples)
    return output.getvalue()
