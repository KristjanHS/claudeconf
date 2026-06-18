# General AI Text Detection Heuristics

Applicable across models. Use alongside `claude-opus-patterns.md` for comprehensive analysis.
If the text doesn't match Claude-specific patterns, check these general indicators to determine
if it may be from another LLM.

## The Five Cue Families (2026 Framework)

From rapid review literature on distinguishing AI from human writing.

### 1. Surface Cues
- **Lexical diversity**: AI text typically has lower type-token ratio (TTR), lower
  moving-average TTR (MATTR), and fewer hapax legomena (words appearing only once)
- **POS distributions**: AI text uses more nouns, determiners, and adpositions;
  fewer adjectives and adverbs compared to human text
- **Readability**: AI text tends toward moderate readability scores (Flesch-Kincaid
  8-12 range) -- rarely very simple or very complex
- **Punctuation patterns**: More consistent punctuation usage; fewer creative
  punctuation choices (ellipses, dashes in unusual positions, intentional fragments)

### 2. Discourse/Pragmatic Cues
- **Metadiscourse density**: AI text uses more metadiscourse markers
  (transitions, frame markers, evidentials) than typical human writing
- **Rhetorical organization**: AI follows textbook rhetorical structures more
  closely -- clear thesis, organized support, balanced conclusions
- **Stance expression**: AI hedges more, takes fewer firm positions, qualifies
  more -- resulting in a "careful neutral" stance even on topics humans feel
  strongly about

### 3. Epistemic/Content Cues
- **Grounding**: AI claims are often general rather than grounded in specific
  personal experience, exact dates, or verifiable micro-details
- **Evidentiality**: AI tends to cite "research shows" or "studies suggest"
  without specific citations (or with hallucinated ones)
- **Plausibility**: AI rarely makes surprising or counter-intuitive claims;
  it tends to stay within the "safest" interpretation
- **Specificity gradient**: AI is specific on well-known topics but vague on
  niche ones -- the opposite of human domain experts

### 4. Predictability/Probabilistic Cues
- **Perplexity**: AI text tends to have lower, more consistent perplexity
  (each word is "expected" given the preceding context)
- **Entropy**: Lower per-token entropy -- AI takes the "safe" next-token
  choice more consistently
- **Bigram/trigram predictability**: Higher predictability in AI text
- **Burstiness**: Low variance in sentence complexity/length is characteristic
  of AI. Humans write in bursts -- one complex 40-word sentence followed by
  a 5-word fragment for emphasis

### 5. Provenance Cues
- **Formatting artifacts**: Consistent markdown, suspicious uniformity in
  bullet point style, "clean" formatting without human messiness
- **Citation artifacts**: utm_source=openai, oai_cite tags, contentReference[],
  grok_card entries, invalid DOIs, hallucinated references
- **Structural templates**: Responses that follow an identifiable template
  (problem/solution/tradeoffs, or intro/points/summary/caveats)

## Statistical Baselines

Approximate baselines for distinguishing human vs. AI text (long-form, English):

| Metric | Human Range | AI Range | Notes |
|--------|-----------|---------|-------|
| Sentence length std dev | 8-20 words | 3-8 words | Higher = more human |
| TTR (per 100 tokens) | 0.55-0.75 | 0.45-0.60 | Higher = more human |
| Hapax legomena % | 40-60% | 25-40% | Higher = more human |
| Avg paragraph length (sentences) | 2-8 (high variance) | 3-6 (low variance) | More variable = more human |
| Em-dash frequency (per 1000 words) | 1-4 | 5-15 (Claude), 2-6 (GPT) | Model-specific |
| Hedge word density (per 100 words) | 0.5-2.0 | 2.0-5.0 | Higher = more likely AI |

These are approximate ranges from available research. Use as guidelines, not hard thresholds.

## Common AI Vocabulary Across Models

Words and phrases that appear significantly more often in AI text than human text:

### High-frequency AI markers (cross-model)
- "delve" / "delve into" / "delving"
- "tapestry" (especially "rich tapestry")
- "landscape" (as metaphor: "the evolving landscape of...")
- "multifaceted"
- "in the realm of"
- "it's important to note"
- "comprehensive" / "comprehensively"
- "holistic" / "holistically"
- "leverage" (as verb)
- "robust"
- "encompasses"
- "fosters" / "fostering"
- "underscores" / "underscoring"
- "highlights" / "highlighting"
- "navigating" (as metaphor)
- "in today's [X]" / "in the [adjective] landscape of"

### Structural Markers
- "Let's break this down"
- "In conclusion" (at the end of even short texts)
- "There are several key factors..."
- "First and foremost"
- Numbered steps in free-form text where humans would use prose

## Signs of Human Writing (Counter-Indicators)

These patterns suggest human authorship. Their presence should reduce AI probability:

- **Personal anecdotes** with specific, non-generic details (names, dates, places)
- **Inconsistent formatting** (shifts between styles within a document)
- **Emotional variation** (excitement, frustration, humor within the same piece)
- **Grammatical bending** (intentional fragments, starting with conjunctions, creative syntax)
- **Domain-specific jargon** used casually (not explained for a general audience)
- **Opinions stated without qualification** ("This is the best approach" vs. "This is arguably...")
- **Tangents and digressions** that break the main thread and return to it
- **Self-correction** within text ("actually, scratch that" or revised phrasing)
- **Cultural/temporal specificity** (references to current events, memes, slang)
- **Profanity, slang, or very informal language** used naturally
- **Run-on sentences** or stream-of-consciousness passages
- **Typos, autocorrect artifacts** (in informal text)
