"""
JARVIS Dictation & Text Processing Powers (PWR-050 to PWR-062)
Voice-to-text, text transformation, and document formatting:
  - Audio transcription (Whisper integration with fallback)
  - Live dictation session management
  - Tone transformation, grammar polish, summarisation, expansion
  - Translation, TTS dispatch, email/report formatting
  - Proofreading and word-count analysis
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import textwrap
import time
from typing import Any, Dict, List, Optional


class DictationPowers:
    """Voice-to-text and text processing capabilities."""

    def __init__(self) -> None:
        self._live_session_active: bool = False
        self._live_session_start: Optional[float] = None
        self._live_transcript_buffer: List[str] = []

    # ------------------------------------------------------------------
    # PWR-050  Transcribe Audio
    # ------------------------------------------------------------------
    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """PWR-050: Transcribe an audio file to text.

        Attempts to use OpenAI Whisper CLI (``whisper``) if available,
        otherwise returns a structured stub indicating the dependency.
        """
        audio_path = os.path.abspath(audio_path)
        if not os.path.isfile(audio_path):
            return {
                "power_id": "PWR-050",
                "status": "error",
                "message": f"Audio file not found: {audio_path}",
            }

        # Try Whisper CLI
        whisper_bin = shutil.which("whisper")
        if whisper_bin:
            try:
                result = subprocess.run(
                    [whisper_bin, audio_path, "--model", "base", "--output_format", "txt"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0:
                    # Whisper writes <basename>.txt next to the file by default
                    txt_path = os.path.splitext(audio_path)[0] + ".txt"
                    transcript = ""
                    if os.path.isfile(txt_path):
                        with open(txt_path, "r", encoding="utf-8") as fh:
                            transcript = fh.read().strip()
                    return {
                        "power_id": "PWR-050",
                        "status": "success",
                        "engine": "whisper",
                        "audio_path": audio_path,
                        "transcript": transcript,
                        "word_count": len(transcript.split()),
                    }
                else:
                    return {
                        "power_id": "PWR-050",
                        "status": "error",
                        "engine": "whisper",
                        "message": f"Whisper exited with code {result.returncode}",
                        "stderr": result.stderr[:500],
                    }
            except subprocess.TimeoutExpired:
                return {
                    "power_id": "PWR-050",
                    "status": "error",
                    "engine": "whisper",
                    "message": "Whisper transcription timed out (300 s limit).",
                }
            except Exception as exc:
                return {
                    "power_id": "PWR-050",
                    "status": "error",
                    "engine": "whisper",
                    "message": str(exc),
                }

        # Fallback stub
        return {
            "power_id": "PWR-050",
            "status": "stub",
            "audio_path": audio_path,
            "message": (
                "Whisper CLI not found. Install with `pip install openai-whisper` "
                "to enable local audio transcription."
            ),
            "transcript": None,
        }

    # ------------------------------------------------------------------
    # PWR-051  Live Dictation Start
    # ------------------------------------------------------------------
    def live_dictation_start(self) -> Dict[str, Any]:
        """PWR-051: Start a live microphone dictation session."""
        if self._live_session_active:
            return {
                "power_id": "PWR-051",
                "status": "already_active",
                "message": "A live dictation session is already in progress.",
                "started_at": self._live_session_start,
            }
        self._live_session_active = True
        self._live_session_start = time.time()
        self._live_transcript_buffer = []
        return {
            "power_id": "PWR-051",
            "status": "started",
            "message": (
                "Live dictation session started. Microphone capture requires a "
                "running audio pipeline (e.g., sounddevice + Whisper streaming). "
                "Call live_dictation_stop() to end and retrieve the transcript."
            ),
            "started_at": self._live_session_start,
        }

    # ------------------------------------------------------------------
    # PWR-052  Live Dictation Stop
    # ------------------------------------------------------------------
    def live_dictation_stop(self) -> Dict[str, Any]:
        """PWR-052: Stop the live dictation session and return the transcript."""
        if not self._live_session_active:
            return {
                "power_id": "PWR-052",
                "status": "no_session",
                "message": "No active dictation session to stop.",
            }
        elapsed = time.time() - (self._live_session_start or time.time())
        transcript = " ".join(self._live_transcript_buffer)
        self._live_session_active = False
        self._live_session_start = None
        self._live_transcript_buffer = []
        return {
            "power_id": "PWR-052",
            "status": "stopped",
            "duration_seconds": round(elapsed, 2),
            "transcript": transcript if transcript else "(no audio captured — microphone pipeline not connected)",
            "word_count": len(transcript.split()) if transcript else 0,
        }

    # ------------------------------------------------------------------
    # PWR-053  Tone Transform
    # ------------------------------------------------------------------
    def tone_transform(
        self, text: str, target_tone: str
    ) -> Dict[str, Any]:
        """PWR-053: Transform text to a different tone (formal/casual/technical)."""
        tone = target_tone.lower().strip()
        original_word_count = len(text.split())

        if tone == "formal":
            transformed = text.replace("can't", "cannot").replace("won't", "will not")
            transformed = transformed.replace("don't", "do not").replace("isn't", "is not")
            transformed = transformed.replace("it's", "it is").replace("I'm", "I am")
            transformed = transformed.replace("we're", "we are").replace("they're", "they are")
            transformed = transformed.replace("you're", "you are").replace("shouldn't", "should not")
            note = "Contractions expanded for formal tone."
        elif tone == "casual":
            transformed = text.replace("cannot", "can't").replace("will not", "won't")
            transformed = transformed.replace("do not", "don't").replace("is not", "isn't")
            transformed = transformed.replace("it is", "it's").replace("I am", "I'm")
            transformed = transformed.replace("we are", "we're").replace("they are", "they're")
            note = "Contractions applied for casual tone."
        elif tone == "technical":
            transformed = text
            note = (
                "Technical tone requested. For full technical rewording, "
                "integrate an LLM rewriting step. Text returned as-is."
            )
        else:
            transformed = text
            note = f"Unknown tone '{target_tone}'. Text returned unchanged."

        return {
            "power_id": "PWR-053",
            "status": "success",
            "target_tone": tone,
            "original_word_count": original_word_count,
            "transformed_text": transformed,
            "note": note,
        }

    # ------------------------------------------------------------------
    # PWR-054  Grammar Polish
    # ------------------------------------------------------------------
    def grammar_polish(self, text: str) -> Dict[str, Any]:
        """PWR-054: Apply basic grammar and formatting corrections."""
        corrections: List[str] = []
        polished = text

        # Fix double spaces
        if "  " in polished:
            polished = re.sub(r" {2,}", " ", polished)
            corrections.append("Collapsed multiple spaces.")

        # Capitalise first letter of sentences
        def _cap_first(m: re.Match) -> str:
            return m.group(0).upper()

        new = re.sub(r"(?<=[.!?]\s)\w", _cap_first, polished)
        if new != polished:
            corrections.append("Capitalised sentence starts.")
            polished = new

        # Capitalise very first character
        if polished and polished[0].islower():
            polished = polished[0].upper() + polished[1:]
            corrections.append("Capitalised opening character.")

        # Ensure trailing period
        stripped = polished.rstrip()
        if stripped and stripped[-1] not in ".!?":
            polished = stripped + "."
            corrections.append("Added missing trailing punctuation.")

        if not corrections:
            corrections.append("No obvious grammar issues detected.")

        return {
            "power_id": "PWR-054",
            "status": "success",
            "original_length": len(text),
            "polished_text": polished,
            "corrections_applied": corrections,
        }

    # ------------------------------------------------------------------
    # PWR-055  Summarise Text
    # ------------------------------------------------------------------
    def summarize_text(
        self, text: str, max_words: int = 100
    ) -> Dict[str, Any]:
        """PWR-055: Produce an extractive summary of the given text."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        summary_sentences: List[str] = []
        word_budget = max_words
        for sent in sentences:
            words_in_sent = len(sent.split())
            if word_budget - words_in_sent < 0 and summary_sentences:
                break
            summary_sentences.append(sent)
            word_budget -= words_in_sent

        summary = " ".join(summary_sentences)
        return {
            "power_id": "PWR-055",
            "status": "success",
            "original_word_count": len(text.split()),
            "summary_word_count": len(summary.split()),
            "max_words_requested": max_words,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # PWR-056  Expand Text
    # ------------------------------------------------------------------
    def expand_text(
        self, text: str, target_words: int = 500
    ) -> Dict[str, Any]:
        """PWR-056: Expand bullet points or short text into a longer draft."""
        lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
        paragraphs: List[str] = []
        for line in lines:
            # Strip bullet markers
            clean = re.sub(r"^[-•*]\s*", "", line)
            expanded = (
                f"{clean}. This is an important point worth exploring in more detail. "
                f"Consider the implications and practical applications of this idea. "
                f"Many experts in the field have noted the significance of {clean.lower().split()[0] if clean.split() else 'this'} "
                f"in shaping modern understanding."
            )
            paragraphs.append(expanded)

        draft = "\n\n".join(paragraphs)
        current_words = len(draft.split())
        return {
            "power_id": "PWR-056",
            "status": "success",
            "original_word_count": len(text.split()),
            "expanded_word_count": current_words,
            "target_words": target_words,
            "expanded_text": draft,
            "note": (
                "Template-based expansion. For richer output, route through an LLM rewriting step."
                if current_words < target_words
                else "Target word count reached."
            ),
        }

    # ------------------------------------------------------------------
    # PWR-057  Translate Text
    # ------------------------------------------------------------------
    def translate_text(
        self, text: str, target_lang: str
    ) -> Dict[str, Any]:
        """PWR-057: Translate text to a target language (placeholder)."""
        return {
            "power_id": "PWR-057",
            "status": "placeholder",
            "source_text": text[:200],
            "target_language": target_lang,
            "message": (
                "Translation requires a translation API (e.g., Google Translate, DeepL). "
                "Set TRANSLATION_API_KEY env var to enable. Text returned untranslated."
            ),
            "translated_text": None,
        }

    # ------------------------------------------------------------------
    # PWR-058  Text to Speech
    # ------------------------------------------------------------------
    def text_to_speech(
        self, text: str, voice: str = "default"
    ) -> Dict[str, Any]:
        """PWR-058: Dispatch text-to-speech synthesis."""
        # Attempt Windows SAPI via PowerShell
        if os.name == "nt":
            try:
                # Sanitise text for PowerShell
                safe_text = text.replace("'", "''").replace('"', '`"')[:2000]
                ps_script = (
                    f"Add-Type -AssemblyName System.Speech; "
                    f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$s.Speak('{safe_text}')"
                )
                subprocess.Popen(
                    ["powershell", "-Command", ps_script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return {
                    "power_id": "PWR-058",
                    "status": "dispatched",
                    "engine": "windows_sapi",
                    "voice": voice,
                    "text_length": len(text),
                    "message": "Speech synthesis dispatched via Windows SAPI.",
                }
            except Exception as exc:
                return {
                    "power_id": "PWR-058",
                    "status": "error",
                    "engine": "windows_sapi",
                    "message": str(exc),
                }

        return {
            "power_id": "PWR-058",
            "status": "stub",
            "message": "TTS not available on this platform. Install pyttsx3 or use a cloud TTS API.",
        }

    # ------------------------------------------------------------------
    # PWR-059  Format as Email
    # ------------------------------------------------------------------
    def format_as_email(
        self, text: str, recipient: str
    ) -> Dict[str, Any]:
        """PWR-059: Format raw text as a professional email."""
        # Extract a subject from the first line or first 60 chars
        first_line = text.strip().split("\n")[0][:60]
        subject = f"Re: {first_line}"

        body = textwrap.fill(text.strip(), width=72)
        email = (
            f"To: {recipient}\n"
            f"Subject: {subject}\n"
            f"\n"
            f"Dear {recipient.split('@')[0].replace('.', ' ').title()},\n\n"
            f"{body}\n\n"
            f"Best regards,\n"
            f"[Your Name]\n"
        )
        return {
            "power_id": "PWR-059",
            "status": "success",
            "recipient": recipient,
            "subject": subject,
            "formatted_email": email,
            "word_count": len(email.split()),
        }

    # ------------------------------------------------------------------
    # PWR-060  Format as Report
    # ------------------------------------------------------------------
    def format_as_report(
        self, text: str, title: str
    ) -> Dict[str, Any]:
        """PWR-060: Format raw text as a structured report."""
        paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]

        sections: List[str] = []
        sections.append(f"# {title}\n")
        sections.append(f"**Date:** {time.strftime('%Y-%m-%d')}\n")
        sections.append("---\n")
        sections.append("## Executive Summary\n")
        sections.append(paragraphs[0] + "\n")
        if len(paragraphs) > 1:
            sections.append("## Details\n")
            for i, para in enumerate(paragraphs[1:], start=1):
                sections.append(f"### Section {i}\n")
                sections.append(para + "\n")
        sections.append("---\n")
        sections.append("## Recommendations\n")
        sections.append("- *[To be completed based on findings]*\n")

        report = "\n".join(sections)
        return {
            "power_id": "PWR-060",
            "status": "success",
            "title": title,
            "formatted_report": report,
            "section_count": len(paragraphs),
            "word_count": len(report.split()),
        }

    # ------------------------------------------------------------------
    # PWR-061  Proofread
    # ------------------------------------------------------------------
    def proofread(self, text: str) -> Dict[str, Any]:
        """PWR-061: Check spelling and style issues."""
        issues: List[Dict[str, str]] = []

        # Repeated words
        for match in re.finditer(r"\b(\w+)\s+\1\b", text, re.IGNORECASE):
            issues.append({
                "type": "repeated_word",
                "word": match.group(1),
                "position": str(match.start()),
                "suggestion": f"Remove duplicate '{match.group(1)}'.",
            })

        # Very long sentences (>40 words)
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for idx, sent in enumerate(sentences):
            wc = len(sent.split())
            if wc > 40:
                issues.append({
                    "type": "long_sentence",
                    "sentence_index": str(idx),
                    "word_count": str(wc),
                    "suggestion": "Consider splitting this sentence for readability.",
                })

        # Passive voice indicators
        passive_patterns = [
            r"\b(?:is|are|was|were|been|being)\s+\w+ed\b",
        ]
        for pat in passive_patterns:
            for match in re.finditer(pat, text, re.IGNORECASE):
                issues.append({
                    "type": "possible_passive_voice",
                    "fragment": match.group(0),
                    "position": str(match.start()),
                    "suggestion": "Consider using active voice.",
                })

        return {
            "power_id": "PWR-061",
            "status": "success",
            "text_length": len(text),
            "issues_found": len(issues),
            "issues": issues[:30],  # Cap to avoid oversized output
            "note": "Rule-based check. For comprehensive proofreading, integrate LanguageTool or Grammarly API.",
        }

    # ------------------------------------------------------------------
    # PWR-062  Word Count Analysis
    # ------------------------------------------------------------------
    def word_count_analysis(self, text: str) -> Dict[str, Any]:
        """PWR-062: Compute word count, reading time, and Flesch readability score."""
        words = text.split()
        word_count = len(words)
        sentences = re.split(r"[.!?]+", text)
        sentences = [s for s in sentences if s.strip()]
        sentence_count = max(len(sentences), 1)
        char_count = len(text)

        # Syllable estimation (English heuristic)
        def _count_syllables(word: str) -> int:
            word = word.lower().strip(".,!?;:'\"")
            if len(word) <= 3:
                return 1
            vowels = "aeiouy"
            count = 0
            prev_vowel = False
            for ch in word:
                is_vowel = ch in vowels
                if is_vowel and not prev_vowel:
                    count += 1
                prev_vowel = is_vowel
            if word.endswith("e") and count > 1:
                count -= 1
            return max(count, 1)

        total_syllables = sum(_count_syllables(w) for w in words) if words else 0

        # Flesch Reading Ease
        if word_count > 0 and sentence_count > 0:
            flesch = (
                206.835
                - 1.015 * (word_count / sentence_count)
                - 84.6 * (total_syllables / word_count)
            )
            flesch = round(max(0.0, min(flesch, 100.0)), 1)
        else:
            flesch = 0.0

        # Flesch interpretation
        if flesch >= 80:
            readability = "Very Easy"
        elif flesch >= 60:
            readability = "Standard"
        elif flesch >= 40:
            readability = "Fairly Difficult"
        elif flesch >= 20:
            readability = "Difficult"
        else:
            readability = "Very Difficult"

        # Reading time (avg 238 WPM)
        reading_time_minutes = round(word_count / 238, 1)
        # Speaking time (avg 150 WPM)
        speaking_time_minutes = round(word_count / 150, 1)

        return {
            "power_id": "PWR-062",
            "status": "success",
            "word_count": word_count,
            "character_count": char_count,
            "sentence_count": sentence_count,
            "syllable_count": total_syllables,
            "flesch_reading_ease": flesch,
            "readability_level": readability,
            "estimated_reading_time_minutes": reading_time_minutes,
            "estimated_speaking_time_minutes": speaking_time_minutes,
        }


dictation_powers = DictationPowers()
