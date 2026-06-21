"""
language_api_runner.py — Headless LLM benchmark for the Language Game.

Each level consists of sentence pairs that the model must evaluate.
For every pair the model must output:
  1. VERDICT: TRUE / FALSE / UNDECIDABLE
  2. WORDS: the selected words from sentence (b) according to the verdict
After all pairs it must output:
  3. FINAL_ANSWER: the emergent-layer answer

Results are compared against ANSWER_KEYS from language_game.py and saved as
JSON logs in logs_language/.

Supported providers
───────────────────
  Claude   (Anthropic)  →  ANTHROPIC_API_KEY
  GPT      (OpenAI)     →  OPENAI_API_KEY
  DeepSeek              →  DEEPSEEK_API_KEY
  Gemini   (Google)     →  GOOGLE_API_KEY
  Kimi     (Moonshot)   →  MOONSHOT_API_KEY

Usage
─────
  # One model, one level (default: one call per pair)
  python language_api_runner.py --model claude-opus-4-7 --level 0

  # All levels, one model
  python language_api_runner.py --model gpt-5.5

  # All models, one level
  python language_api_runner.py --all-models --level 1

  # Single-shot: all pairs in one prompt, only FINAL_ANSWER (no per-pair output)
  python language_api_runner.py --model claude-opus-4-7 --level 2 --single-shot
  python language_api_runner.py --model gpt-5.5 --level 3 --single-shot --runs 3

Output
──────
  - Live verdict log in terminal per pair
  - JSON log per run in logs_language/
  - Comparison table (VERDICT_ACC%, WORDS_ACC%, COST) when --all-models is used
"""

import argparse
import json
import os
import re
import random
import sys
import time

# ---------------------------------------------------------------------------
# Import level data and answer keys from the game file
# ---------------------------------------------------------------------------
# We import directly from language_game so that any updates to LEVELS or
# ANSWER_KEYS are automatically reflected here.
sys.path.insert(0, os.path.dirname(__file__))

# language_game.py calls pygame.init() at import time; we suppress display.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    from language_game import LEVELS, ANSWER_KEYS, WORD_SELECT_RULES, BASE_RULES, \
        META_RULES, META_META_RULES, META_META_META_RULES, EXTRA_HARD_RULES
except Exception as _e:
    print(f"[ERROR] Could not import from language_game.py: {_e}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Provider / model setup  (same as api_runner.py)
# ---------------------------------------------------------------------------
_PROVIDER_MAP = {
    "claude":   "anthropic",
    "gpt":      "openai",
    "o1":       "openai",
    "o3":       "openai",
    "deepseek": "deepseek",
    "gemini":   "gemini",
    "moonshot": "moonshot",
    "kimi":     "moonshot",
}

ALL_MODELS = [
    "claude-opus-4-7",
    "gpt-5.5",
    "gemini-3.1-pro-preview",
    "kimi-k2.6",
    "deepseek-v4-pro",
]

_REASONER_MODELS = {
    "claude-opus-4-7",
    "gpt-5.5",
    "gemini-3.1-pro-preview",
    "deepseek-reasoner",
    "deepseek-v4-pro",
    "kimi-k2.6",
}

_PRICES = {
    "claude-opus-4-7":          {"input":  5.00, "output": 25.00},
    "gpt-5.5":                  {"input":  5.00, "output": 30.00},
    "gemini-3.1-pro-preview":   {"input":  2.00, "output": 12.00},
    "deepseek-v4-pro":          {"input":  0.435, "output":  0.87},
    "deepseek-reasoner":        {"input":  0.55,  "output":  2.19},
    "kimi-k2.6":                {"input":  0.95,  "output":  4.00},
}


def _is_reasoner(model_id):
    return model_id in _REASONER_MODELS


def _provider(model_id):
    if "/" in model_id:
        return "openrouter"
    for prefix, prov in _PROVIDER_MAP.items():
        if model_id.startswith(prefix):
            return prov
    raise ValueError(f"Unknown model: {model_id!r}")


def _compute_cost(model_id, in_tok, out_tok):
    p = _PRICES.get(model_id)
    if p is None:
        return None
    return round((in_tok * p["input"] + out_tok * p["output"]) / 1_000_000, 6)


# ---------------------------------------------------------------------------
# API call  (identical routing logic as api_runner.py)
# ---------------------------------------------------------------------------
def call_model(model_id, prompt, system_prompt=None, _max_retries=5, max_tokens=None):
    for attempt in range(_max_retries):
        try:
            return _call_model_once(model_id, prompt, system_prompt, max_tokens=max_tokens)
        except Exception as e:
            msg = str(e)
            retryable = any(c in msg for c in ("503", "429", "UNAVAILABLE",
                                                "RESOURCE_EXHAUSTED", "rate limit"))
            if retryable and attempt < _max_retries - 1:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(f"  [RETRY {attempt+1}] {msg[:80]} — wacht {wait:.1f}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Unreachable")


def _call_model_once(model_id, prompt, system_prompt=None, max_tokens=None):
    provider = _provider(model_id)
    reasoner = _is_reasoner(model_id)
    max_tok  = max_tokens if max_tokens is not None else 20000

    if provider == "anthropic":
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set")
        client = anthropic.Anthropic(api_key=api_key, timeout=600.0)
        kwargs = dict(model=model_id, max_tokens=max_tok,
                      messages=[{"role": "user", "content": prompt}])
        if reasoner:
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {"effort": "max"}
        else:
            kwargs["temperature"] = 0.7
        if system_prompt:
            kwargs["system"] = system_prompt
        with client.messages.stream(**kwargs) as stream:
            resp = stream.get_final_message()
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return text, resp.usage.input_tokens, resp.usage.output_tokens, ""

    if provider == "openai":
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY not set")
        client = OpenAI(api_key=api_key, timeout=900.0)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        params = dict(model=model_id, max_completion_tokens=max_tok, messages=messages)
        if reasoner:
            params["reasoning_effort"] = "xhigh"
        else:
            params["temperature"] = 1.0
        resp = client.chat.completions.create(**params)
        text = resp.choices[0].message.content
        return text, resp.usage.prompt_tokens, resp.usage.completion_tokens, ""

    if provider == "deepseek":
        from openai import OpenAI
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise EnvironmentError("DEEPSEEK_API_KEY not set")
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=300.0)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        ds_max = max_tok
        params = dict(model=model_id, max_tokens=ds_max, messages=messages)
        if reasoner:
            params["reasoning_effort"] = "max"
            params["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            params["temperature"] = 1.0
        resp = client.chat.completions.create(**params)
        msg       = resp.choices[0].message
        reasoning = getattr(msg, "reasoning_content", None) or ""
        text      = msg.content or reasoning
        return text, resp.usage.prompt_tokens, resp.usage.completion_tokens, reasoning

    if provider == "gemini":
        from google import genai
        from google.genai import types as genai_types
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError("GOOGLE_API_KEY not set")
        client = genai.Client(api_key=api_key)
        config = {"max_output_tokens": max_tok}
        if reasoner:
            config["thinking_config"] = genai_types.ThinkingConfig(thinking_level="high")
        else:
            config["temperature"] = 1.0
        if system_prompt:
            config["system_instruction"] = system_prompt
        gen_config = genai_types.GenerateContentConfig(**config)
        ex  = ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(lambda: client.models.generate_content(
            model=model_id, contents=prompt, config=gen_config))
        try:
            resp = fut.result(timeout=900)
        except FuturesTimeout:
            ex.shutdown(wait=False)
            raise TimeoutError("Gemini timeout na 900s")
        finally:
            ex.shutdown(wait=False)
        in_t    = resp.usage_metadata.prompt_token_count    or 0
        out_t   = resp.usage_metadata.candidates_token_count or 0
        think_t = getattr(resp.usage_metadata, "thoughts_token_count", None) or 0
        return resp.text, in_t, out_t + think_t, ""

    if provider == "moonshot":
        from openai import OpenAI
        api_key = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("KIMI_API_KEY")
        if not api_key:
            raise EnvironmentError("MOONSHOT_API_KEY not set")
        client = OpenAI(api_key=api_key, base_url="https://api.moonshot.ai/v1", timeout=300.0)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        params = dict(model=model_id, max_tokens=8192, messages=messages)
        if not reasoner:
            params["temperature"] = 1.0
        resp = client.chat.completions.create(**params)
        msg  = resp.choices[0].message
        text = msg.content or getattr(msg, "reasoning_content", "") or ""
        in_t  = resp.usage.prompt_tokens     if resp.usage else 0
        out_t = resp.usage.completion_tokens if resp.usage else 0
        return text, in_t, out_t, ""

    if provider == "openrouter":
        from openai import OpenAI
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENROUTER_API_KEY not set")
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1", timeout=300.0)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model=model_id, max_tokens=max_tok, temperature=1.0, messages=messages)
        text = resp.choices[0].message.content
        return text, resp.usage.prompt_tokens, resp.usage.completion_tokens, ""

    raise ValueError(f"No handler for provider: {provider!r}")


# ---------------------------------------------------------------------------
# System prompt  (sent once, cached — contains the rules only)
# ---------------------------------------------------------------------------
def build_system_prompt(level_idx):
    lvl      = LEVELS[level_idx]
    sections = lvl["legend_sections"]

    rule_blocks = []
    for section_name, rules, _ in sections:
        rule_blocks.append(f"{section_name.upper()}\n" + "\n".join(f"  {r}" for r in rules))
    rules_text = "\n\n".join(rule_blocks)

    # All sentence pairs for this level
    pair_lines = []
    for i, pair in enumerate(lvl["pairs"], 1):
        pair_lines.append(f"  Pair {i}a: {pair['a']}")
        pair_lines.append(f"  Pair {i}b: {pair['b']}")
    pairs_text = "\n".join(pair_lines)

    return f"""You are solving a language reasoning puzzle. You will receive ONE sentence pair at a time.

  - Sentence (a) must be evaluated against the WORLD RULES below.
  - Sentence (b) is a WORD BANK only — its logic is irrelevant.

WORD SELECTION RULE
───────────────────
After you determine the verdict for sentence (a):
  TRUE        → extract words at positions 2, 4, 6, 8 ... (even positions) from sentence (b)
  FALSE       → extract words at positions 1, 3, 5, 7 ... (odd positions) from sentence (b)
  UNDECIDABLE → extract words at positions 1, 4, 7, 10 ... (every 3rd, starting at 1) from sentence (b)

Word positions are counted starting at 1 for the first word of sentence (b).

RULES IN EFFECT FOR THIS LEVEL
───────────────────────────────
{rules_text}

ALL SENTENCE PAIRS FOR THIS LEVEL
──────────────────────────────────
{pairs_text}

REASONING DISCIPLINE
────────────────────
- Do NOT repeat or restate the rules in your reasoning. They are already known.
- Only mention a rule when it is directly relevant to this specific sentence.
- Keep reasoning concise: identify the relevant rule(s), apply them, state the verdict, extract the words.

RESPONSE FORMAT
───────────────
Output ONLY this block — nothing else before or after:

REASONING: <concise step-by-step reasoning — only cite rules that actually apply to this pair>
VERDICT: <TRUE | FALSE | UNDECIDABLE | SKIP>
WORDS: <only the extracted words, comma-separated — leave empty if SKIP>

If the Sentence Dependency rule from the previous pair triggers a skip for this pair, output:
VERDICT: SKIP
WORDS:

Example of a correct WORDS line:
  WORDS: heaven, is"""


# ---------------------------------------------------------------------------
# Prompt builder — one prompt per pair
# ---------------------------------------------------------------------------
def build_pair_prompt(level_idx, pair_idx, prev_words=None, prev_sentence_a=None):
    """Build the user prompt for a single sentence pair."""
    lvl  = LEVELS[level_idx]
    pair = lvl["pairs"][pair_idx]

    prev_section = ""
    if prev_words:
        prev_section = (
            f"CARRY-OVER FROM PREVIOUS PAIR (pair {pair_idx})\n"
            f"─────────────────────────────────────────────────\n"
            f"  Sentence (a): {prev_sentence_a}\n"
            f"  Extracted words: {prev_words}\n\n"
            f"Use the sentence above to determine what day it was in that pair. "
            f"Use the extracted words to apply the Sentence Dependency rule: "
            f"check the 1st and last word to determine whether any rule modifications "
            f"carry over to this pair (e.g. last word is a preposition → Meta-C skips this pair "
            f"if Meta-C is active on that day).\n\n"
        )

    return (
        f"LEVEL {level_idx+1} — {lvl['name'].upper()}  |  Pair {pair_idx+1} of {len(lvl['pairs'])}\n\n"
        + prev_section
        + f"(a): {pair['a']}\n"
        f"(b): {pair['b']}\n\n"
        "Evaluate sentence (a) and extract the correct words from sentence (b)."
    )


def build_emergent_prompt(level_idx, extracted_words_per_pair):
    """Build the prompt for the final emergent-layer question."""
    lvl   = LEVELS[level_idx]
    n     = len(lvl["pairs"])

    # Per-pair word contributions
    pair_lines = []
    for i, w in enumerate(extracted_words_per_pair, 1):
        pair_lines.append(f"  Pair {i}: {w if w else '(no words extracted)'}")

    all_words = " ".join(w for words in extracted_words_per_pair for w in words.split(", ") if w)

    return (
        f"You have now evaluated all {n} sentence pairs.\n\n"
        f"EXTRACTED WORDS PER PAIR\n"
        f"────────────────────────\n"
        + "\n".join(pair_lines) + "\n\n"
        + f"When you read all extracted words in order (pair 1 first, then pair 2, etc.) "
        f"they together form a hidden statement or question:\n\n"
        f"  \"{all_words}\"\n\n"
        f"This hidden statement is one of three things:\n"
        f"  Case 1: A QUESTION        → answer it directly and concisely.\n"
        f"  Case 2: NEW INSTRUCTIONS  → follow the instructions and give the result.\n"
        f"  Case 3: NONSENSE          → output the nonsense string as-is.\n\n"
        f"Determine which case applies, then provide your answer.\n\n"
        f"Output ONLY these two lines — nothing else before or after:\n"
        f"CASE: <QUESTION | NEW_INSTRUCTIONS | NONSENSE>\n"
        f"FINAL_ANSWER: <your answer to the hidden statement>"
    )


# ---------------------------------------------------------------------------
# Re-evaluation prompt builder (only called when emergent was correct)
# ---------------------------------------------------------------------------
def build_re_eval_prompt(level_idx, pair_idx):
    """Build the user prompt for re-evaluating a single pair under changed world rules."""
    lvl        = LEVELS[level_idx]
    akey       = ANSWER_KEYS[level_idx]
    pair       = lvl["pairs"][pair_idx]
    rule_change = akey.get("re_eval_rule_change", "")

    return (
        f"RE-EVALUATION  |  Pair {pair_idx + 1} of {len(lvl['pairs'])}\n\n"
        f"The emergent layer revealed a rule change:\n"
        f"  {rule_change}\n\n"
        f"All other world rules remain the same.\n\n"
        f"Re-evaluate the following pair under the updated rules:\n\n"
        f"(a): {pair['a']}\n"
        f"(b): {pair['b']}\n\n"
        f"Apply the same word-selection and meta-rule logic as before, but with the updated world rule."
    )


# ---------------------------------------------------------------------------
# Parsing model output
# ---------------------------------------------------------------------------
def _norm_words(s):
    """Lowercase, strip punctuation, split — for comparison."""
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()




# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------
def score_verdict(player, correct):
    """True if the verdicts match (case-insensitive)."""
    if player is None or correct is None:
        return False
    return player.strip().lower() == correct.strip().lower()


def score_words(player_str, correct_str):
    """True if the extracted word lists match (order-sensitive, punctuation-insensitive)."""
    return _norm_words(player_str) == _norm_words(correct_str)


# ---------------------------------------------------------------------------
# Helper: parse a single-pair response
# ---------------------------------------------------------------------------
def parse_pair_response(response_text):
    """Extract verdict, words and reasoning from a single-pair response."""
    verdict_m   = re.search(r"VERDICT\s*:\s*(TRUE|FALSE|UNDECIDABLE|SKIP)", response_text, re.IGNORECASE)
    # Anchor WORDS: to start-of-line so "odd-positioned words: …" in the reasoning doesn't match
    words_m     = re.search(r"^WORDS\s*:\s*(.+?)$", response_text, re.IGNORECASE | re.MULTILINE)
    reasoning_m = re.search(r"REASONING\s*:\s*(.+?)(?=\nVERDICT|\Z)", response_text,
                             re.IGNORECASE | re.DOTALL)
    return {
        "verdict":   verdict_m.group(1).lower() if verdict_m else None,
        "words":     words_m.group(1).strip()   if words_m  else "",
        "reasoning": reasoning_m.group(1).strip() if reasoning_m else response_text.strip(),
    }


# ---------------------------------------------------------------------------
# Single level run  — one API call per pair
# ---------------------------------------------------------------------------
def run_level(level_idx, model, verbose=True, run_idx=1, log_dir="logs_language"):
    lvl   = LEVELS[level_idx]
    akey  = ANSWER_KEYS[level_idx]
    pairs = lvl["pairs"]
    n     = len(pairs)

    os.makedirs(log_dir, exist_ok=True)
    safe_model = model.replace("/", "-")
    safe_level = lvl["name"].replace(" ", "-")
    timestamp  = time.strftime("%Y%m%d_%H%M%S")
    log_path   = os.path.join(log_dir,
                              f"{safe_model}_{safe_level}_run{run_idx}_{timestamp}.json")

    sys_prompt = build_system_prompt(level_idx)

    if verbose:
        print(f"\n{'='*60}")
        print(f"  {lvl['name']}  [{model}]  ({n} pairs, one call each)")
        print(f"{'='*60}")

    total_in_tok  = 0
    total_out_tok = 0
    total_elapsed = 0.0
    pair_results  = []
    verdict_correct = 0
    words_correct   = 0
    extracted_words = []   # collect for emergent prompt

    # Build the log dict once and update it in-place after every pair,
    # so the file is always readable mid-run (same pattern as api_runner.py).
    run_log = {
        "model":                model,
        "level":                level_idx,
        "level_name":           lvl["name"],
        "run":                  run_idx,
        "status":               "in_progress",
        "pair_results":         [],
        "verdict_correct":      0,
        "words_correct":        0,
        "n_pairs":              n,
        "verdict_accuracy":     0.0,
        "words_accuracy":       0.0,
        "model_final_answer":   "",
        "correct_final_answer": akey.get("emergent_answer", ""),
        "final_answer_match":   False,
        "input_tokens":         0,
        "output_tokens":        0,
        "total_tokens":         0,
        "cost_usd":             None,
        "total_response_time_s": 0.0,
    }

    def _save_log():
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(run_log, f, indent=2, ensure_ascii=False)

    for i, pair in enumerate(pairs):
        ak         = akey["pairs"][i] if i < len(akey["pairs"]) else None
        correct_vd = ak["verdict"]        if ak else None
        correct_sw = ak["selected_words"] if ak else ""

        prev_words      = extracted_words[i - 1]      if i > 0 else None
        prev_sentence_a = pairs[i - 1]["a"]            if i > 0 else None
        user_prompt = build_pair_prompt(level_idx, i,
                                        prev_words=prev_words,
                                        prev_sentence_a=prev_sentence_a)

        t0 = time.time()
        try:
            response_text, in_tok, out_tok, reasoning = call_model(
                model, user_prompt, system_prompt=sys_prompt)
        except KeyboardInterrupt:
            print("\n  [INTERRUPTED]")
            break
        except Exception as e:
            print(f"  [API ERROR pair {i+1}] {e}")
            pair_results.append({
                "pair_idx": i + 1, "sentence_a": pair["a"], "sentence_b": pair["b"],
                "model_verdict": None, "correct_verdict": correct_vd,
                "verdict_correct": False, "model_words": "", "correct_words": correct_sw,
                "words_correct": False, "model_reasoning": f"API error: {e}",
                "answer_note": ak.get("note", "") if ak else "",
            })
            extracted_words.append("")
            continue

        elapsed = round(time.time() - t0, 2)
        total_in_tok  += in_tok
        total_out_tok += out_tok
        total_elapsed += elapsed

        # Retry empty responses up to 2 times
        if not response_text.strip():
            for _retry in range(2):
                if verbose:
                    print(f"  [!] Empty response pair {i+1} — retry {_retry+1}/2...")
                try:
                    response_text, in_tok2, out_tok2, _ = call_model(
                        model, user_prompt, system_prompt=sys_prompt)
                    total_in_tok  += in_tok2
                    total_out_tok += out_tok2
                    if response_text.strip():
                        break
                except Exception:
                    break

        pp = parse_pair_response(response_text)

        vd_ok = score_verdict(pp["verdict"], correct_vd)
        sw_ok = score_words(pp["words"], correct_sw) if pp["words"] else False

        if vd_ok: verdict_correct += 1
        if sw_ok: words_correct   += 1
        extracted_words.append(pp["words"])

        if verbose:
            pv      = pp["verdict"].upper() if pp["verdict"] else "—"
            cv      = correct_vd.upper() if correct_vd else "?"
            vd_icon = "✓" if vd_ok else "✗"
            sw_icon = "✓" if sw_ok else "✗"
            print(f"  Pair {i+1}: verdict {vd_icon} [{pv} / {cv}]  words {sw_icon}"
                  f"  ({elapsed:.1f}s  {in_tok+out_tok} tok)")
            if not sw_ok and pp["words"]:
                print(f"    model:   {pp['words']}")
                print(f"    correct: {correct_sw}")

        entry = {
            "pair_idx":        i + 1,
            "sentence_a":      pair["a"],
            "sentence_b":      pair["b"],
            "model_verdict":   pp["verdict"],
            "correct_verdict": correct_vd,
            "verdict_correct": vd_ok,
            "model_words":     pp["words"],
            "correct_words":   correct_sw,
            "words_correct":   sw_ok,
            "model_reasoning": pp["reasoning"],
            "answer_note":     ak.get("note", "") if ak else "",
            "response_time_s": elapsed,
            "tokens_in":       in_tok,
            "tokens_out":      out_tok,
            "full_response":   response_text,
        }
        if reasoning:
            entry["reasoning_chain"] = reasoning
        pair_results.append(entry)

        # Update run_log and save after every pair so the file is readable mid-run
        run_log["pair_results"]         = pair_results
        run_log["verdict_correct"]      = verdict_correct
        run_log["words_correct"]        = words_correct
        run_log["verdict_accuracy"]     = round(verdict_correct / n, 4)
        run_log["words_accuracy"]       = round(words_correct / n, 4)
        run_log["input_tokens"]         = total_in_tok
        run_log["output_tokens"]        = total_out_tok
        run_log["total_tokens"]         = total_in_tok + total_out_tok
        run_log["cost_usd"]             = _compute_cost(model, total_in_tok, total_out_tok)
        run_log["total_response_time_s"] = round(total_elapsed, 2)
        _save_log()

        time.sleep(0.2)   # brief pause between pair calls

    # Emergent layer — separate API call using the words collected above
    final_answer           = ""
    correct_fa             = akey.get("emergent_answer", "")
    fa_words_ok            = False
    emergent_case          = None
    emergent_full_response = ""
    emergent_reasoning     = ""

    if extracted_words:
        emergent_prompt = build_emergent_prompt(level_idx, extracted_words)
        try:
            fa_text, fa_in, fa_out, fa_reasoning = call_model(
                model, emergent_prompt, system_prompt=None)
            total_in_tok       += fa_in
            total_out_tok      += fa_out
            # Retry up to 2 times if response is empty
            if not fa_text.strip():
                for _retry in range(2):
                    if verbose:
                        print(f"  [!] Empty emergent response — retry {_retry+1}/2...")
                    try:
                        fa_text2, fa_in2, fa_out2, fa_reasoning2 = call_model(
                            model, emergent_prompt, system_prompt=None)
                        total_in_tok  += fa_in2
                        total_out_tok += fa_out2
                        if fa_text2.strip():
                            fa_text      = fa_text2
                            fa_reasoning = fa_reasoning2
                            break
                    except Exception:
                        break
            emergent_full_response = fa_text
            emergent_reasoning     = fa_reasoning
            case_m       = re.search(r"CASE\s*:\s*(QUESTION|NEW_INSTRUCTIONS|NONSENSE)",
                                     fa_text, re.IGNORECASE)
            fa_m         = re.search(r"FINAL_ANSWER\s*:\s*(.+)", fa_text,
                                     re.IGNORECASE | re.DOTALL)
            emergent_case  = case_m.group(1).upper() if case_m else None
            final_answer   = fa_m.group(1).strip() if fa_m else fa_text.strip()
            valid_answers  = [a.strip() for a in correct_fa.split("/")]
            fa_words_ok    = any(score_words(final_answer, va) for va in valid_answers) if final_answer else False
            if verbose:
                case_lbl = emergent_case or "?"
                print(f"\n  Emergent case: {case_lbl}")
                print(f"  Emergent answer: {'v' if fa_words_ok else 'x'}  \"{final_answer}\"")
        except Exception as e:
            emergent_case = None
            if verbose:
                print(f"  [API ERROR emergent] {e}")

    # Re-evaluation layer — only triggered when:
    #   1. emergent answer is correct (fa_words_ok)
    #   2. model recognised it as new instructions (emergent_case == NEW_INSTRUCTIONS)
    re_eval_results      = []
    re_eval_verdict_ok   = 0
    re_eval_words_ok     = 0
    re_eval_attempted    = False
    re_eval_pairs_key    = akey.get("re_eval_pairs", [])

    if emergent_case == "NEW_INSTRUCTIONS" and re_eval_pairs_key:
        re_eval_attempted = True
        if verbose:
            print(f"\n  [Re-eval] Emergent correct — starting re-evaluation of {n} pairs...")
        for i, pair in enumerate(pairs):
            ak_re = re_eval_pairs_key[i] if i < len(re_eval_pairs_key) else None
            if ak_re and ak_re.get("verdict") == "skip":
                re_eval_results.append({
                    "pair_idx":     i + 1,
                    "skipped":      True,
                    "re_eval_note": ak_re.get("re_eval_note", ""),
                })
                if verbose:
                    print(f"  Re-eval pair {i+1}: SKIP")
                continue

            correct_rv = ak_re["verdict"]        if ak_re else None
            correct_rw = ak_re["selected_words"] if ak_re else ""

            re_prompt = build_re_eval_prompt(level_idx, i)
            t0 = time.time()
            try:
                re_text, re_in, re_out, _ = call_model(
                    model, re_prompt, system_prompt=sys_prompt)
                total_in_tok  += re_in
                total_out_tok += re_out
                total_elapsed += round(time.time() - t0, 2)
            except Exception as e:
                if verbose:
                    print(f"  [API ERROR re-eval pair {i+1}] {e}")
                re_eval_results.append({
                    "pair_idx": i + 1, "error": str(e),
                    "correct_verdict": correct_rv, "correct_words": correct_rw,
                })
                continue

            pp_re   = parse_pair_response(re_text)
            vd_ok_r = score_verdict(pp_re["verdict"], correct_rv)
            sw_ok_r = score_words(pp_re["words"], correct_rw) if pp_re["words"] else False
            if vd_ok_r: re_eval_verdict_ok += 1
            if sw_ok_r: re_eval_words_ok   += 1

            if verbose:
                pv = pp_re["verdict"].upper() if pp_re["verdict"] else "—"
                cv = correct_rv.upper() if correct_rv else "?"
                print(f"  Re-eval pair {i+1}: verdict {'v' if vd_ok_r else 'x'} [{pv}/{cv}]"
                      f"  words {'v' if sw_ok_r else 'x'}")

            re_eval_results.append({
                "pair_idx":        i + 1,
                "model_verdict":   pp_re["verdict"],
                "correct_verdict": correct_rv,
                "verdict_correct": vd_ok_r,
                "model_words":     pp_re["words"],
                "correct_words":   correct_rw,
                "words_correct":   sw_ok_r,
                "model_reasoning": pp_re["reasoning"],
                "re_eval_note":    ak_re.get("re_eval_note", "") if ak_re else "",
                "full_response":   re_text,
            })
            time.sleep(0.2)

        scored_re = [r for r in re_eval_results if not r.get("skipped") and "error" not in r]
        n_re      = len(scored_re)
        if verbose and n_re:
            print(f"\n  Re-eval verdict accuracy: {re_eval_verdict_ok}/{n_re}")
            print(f"  Re-eval words accuracy:   {re_eval_words_ok}/{n_re}")

    total_cost  = _compute_cost(model, total_in_tok, total_out_tok)
    verdict_acc = verdict_correct / n if n else 0.0
    words_acc   = words_correct   / n if n else 0.0

    if verbose:
        print(f"\n  Verdict accuracy: {verdict_correct}/{n}  ({verdict_acc*100:.0f}%)")
        print(f"  Words accuracy:   {words_correct}/{n}  ({words_acc*100:.0f}%)")
        print(f"  Final answer match: {'v' if fa_words_ok else 'x'}")
        print(f"  Tokens: {total_in_tok+total_out_tok:,}  "
              f"(in={total_in_tok:,} out={total_out_tok:,})")
        if total_cost is not None:
            print(f"  Cost:   ${total_cost:.4f}")
        print(f"  Time:   {total_elapsed:.1f}s total")
        print(f"  Log:    {log_path}")

    # Final save with completed status and emergent result
    run_log["status"]                    = "done"
    run_log["model_final_answer"]        = final_answer
    run_log["emergent_case"]             = emergent_case
    run_log["emergent_full_response"]    = emergent_full_response
    run_log["emergent_reasoning"]        = emergent_reasoning
    run_log["final_answer_match"]        = fa_words_ok
    run_log["re_eval_attempted"]         = re_eval_attempted
    run_log["re_eval_results"]           = re_eval_results
    run_log["re_eval_verdict_correct"]   = re_eval_verdict_ok
    run_log["re_eval_words_correct"]     = re_eval_words_ok
    run_log["verdict_accuracy"]          = round(verdict_acc, 4)
    run_log["words_accuracy"]            = round(words_acc, 4)
    run_log["input_tokens"]              = total_in_tok
    run_log["output_tokens"]             = total_out_tok
    run_log["total_tokens"]              = total_in_tok + total_out_tok
    run_log["cost_usd"]                  = total_cost
    run_log["total_response_time_s"]     = round(total_elapsed, 2)
    _save_log()

    return run_log


# ---------------------------------------------------------------------------
# Single-shot prompt builder  (all pairs → FINAL_ANSWER only)
# ---------------------------------------------------------------------------
def build_single_shot_prompt(level_idx):
    """One prompt containing all pairs; model must output only FINAL_ANSWER."""
    lvl      = LEVELS[level_idx]
    sections = lvl["legend_sections"]

    rule_blocks = []
    for section_name, rules, _ in sections:
        rule_blocks.append(f"{section_name.upper()}\n" + "\n".join(f"  {r}" for r in rules))
    rules_text = "\n\n".join(rule_blocks)

    pair_lines = []
    for i, pair in enumerate(lvl["pairs"], 1):
        pair_lines.append(f"Pair {i}a: {pair['a']}")
        pair_lines.append(f"Pair {i}b: {pair['b']}")
        pair_lines.append("")
    pairs_text = "\n".join(pair_lines).rstrip()

    return f"""You are solving a language reasoning puzzle in one go.

RULES
─────
{rules_text}

WORD SELECTION
──────────────
After determining the verdict for each sentence (a):
  TRUE        → extract words at positions 2, 4, 6, 8 ... (even) from sentence (b)
  FALSE       → extract words at positions 1, 3, 5, 7 ... (odd) from sentence (b)
  UNDECIDABLE → extract words at positions 1, 4, 7 ... (every 3rd, from 1) from sentence (b)

EMERGENT LAYER
──────────────
After processing all pairs, read the extracted words in order (pair 1b first, then 2b, etc.).
They form a hidden sentence. That sentence is one of:
  Case 1: A QUESTION        → answer it directly.
  Case 2: NEW INSTRUCTIONS  → follow them and give the result.
  Case 3: NONSENSE          → output it as-is.

SENTENCE PAIRS
──────────────
{pairs_text}

TASK
────
Work through all pairs internally. Do NOT output per-pair verdicts or word lists.
Only output the case and your final answer to the emergent sentence.

Output ONLY these two lines — nothing else before or after:
CASE: <QUESTION | NEW_INSTRUCTIONS | NONSENSE>
FINAL_ANSWER: <your answer>"""


# ---------------------------------------------------------------------------
# Single-shot level run  — one API call for all pairs + final answer
# ---------------------------------------------------------------------------
def run_level_single_shot(level_idx, model, verbose=True, run_idx=1,
                          log_dir="logs_language_single_shot"):
    """All pairs in one prompt; model outputs only FINAL_ANSWER."""
    lvl   = LEVELS[level_idx]
    akey  = ANSWER_KEYS[level_idx]

    os.makedirs(log_dir, exist_ok=True)
    safe_model = model.replace("/", "-")
    safe_level = lvl["name"].replace(" ", "-")
    timestamp  = time.strftime("%Y%m%d_%H%M%S")
    log_path   = os.path.join(log_dir,
                              f"{safe_model}_{safe_level}_run{run_idx}_{timestamp}.json")

    prompt     = build_single_shot_prompt(level_idx)
    correct_fa = akey.get("emergent_answer", "")

    if verbose:
        print(f"\n{'='*60}")
        print(f"  {lvl['name']}  [{model}]  (single-shot)")
        print(f"{'='*60}")

    run_log = {
        "mode":                 "single_shot",
        "model":                model,
        "level":                level_idx,
        "level_name":           lvl["name"],
        "run":                  run_idx,
        "status":               "in_progress",
        "model_final_answer":   "",
        "correct_final_answer": correct_fa,
        "final_answer_match":   False,
        "input_tokens":         0,
        "output_tokens":        0,
        "total_tokens":         0,
        "cost_usd":             None,
        "total_response_time_s": 0.0,
        "full_response":        "",
    }

    def _save_log():
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(run_log, f, indent=2, ensure_ascii=False)

    _save_log()

    t0 = time.time()
    try:
        response_text, in_tok, out_tok, reasoning = call_model(model, prompt, max_tokens=100000)
    except KeyboardInterrupt:
        print("\n  [INTERRUPTED]")
        run_log["status"] = "interrupted"
        _save_log()
        return run_log
    except Exception as e:
        print(f"  [API ERROR] {e}")
        run_log["status"] = "error"
        run_log["error"]  = str(e)
        _save_log()
        return run_log

    elapsed = round(time.time() - t0, 2)

    # Retry empty response once
    if not response_text.strip():
        if verbose:
            print("  [!] Empty response — retrying...")
        try:
            response_text, in_tok2, out_tok2, reasoning = call_model(model, prompt)
            in_tok  += in_tok2
            out_tok += out_tok2
        except Exception:
            pass

    case_m       = re.search(r"CASE\s*:\s*(QUESTION|NEW_INSTRUCTIONS|NONSENSE)",
                             response_text, re.IGNORECASE)
    fa_m         = re.search(r"FINAL_ANSWER\s*:\s*(.+)", response_text,
                             re.IGNORECASE | re.DOTALL)
    emergent_case = case_m.group(1).upper() if case_m else None
    final_answer  = fa_m.group(1).strip() if fa_m else response_text.strip()

    valid_answers = [a.strip() for a in correct_fa.split("/")]
    fa_ok = any(score_words(final_answer, va) for va in valid_answers) if final_answer else False

    total_cost = _compute_cost(model, in_tok, out_tok)

    if verbose:
        icon = "v" if fa_ok else "x"
        print(f"  Case:         {emergent_case or '?'}")
        print(f"  Final answer: {icon}  \"{final_answer}\"")
        print(f"  Correct:      \"{correct_fa}\"")
        print(f"  Tokens: {in_tok+out_tok:,}  (in={in_tok:,} out={out_tok:,})")
        if total_cost is not None:
            print(f"  Cost:   ${total_cost:.4f}")
        print(f"  Time:   {elapsed:.1f}s")
        print(f"  Log:    {log_path}")

    run_log.update({
        "status":                "done",
        "emergent_case":         emergent_case,
        "model_final_answer":    final_answer,
        "final_answer_match":    fa_ok,
        "input_tokens":          in_tok,
        "output_tokens":         out_tok,
        "total_tokens":          in_tok + out_tok,
        "cost_usd":              total_cost,
        "total_response_time_s": elapsed,
        "full_response":         response_text,
    })
    if reasoning:
        run_log["reasoning_chain"] = reasoning
    _save_log()

    return run_log


# ---------------------------------------------------------------------------
# Run all levels for one model
# ---------------------------------------------------------------------------
def run_all_levels(model, verbose=True, single_shot=False):
    _run = run_level_single_shot if single_shot else run_level
    results = []
    for i in range(len(LEVELS)):
        r = _run(i, model, verbose=verbose)
        if r is not None:
            results.append(r)
        time.sleep(0.3)
    return results


# ---------------------------------------------------------------------------
# Run all models on one or all levels and print comparison table
# ---------------------------------------------------------------------------
def run_all_models(level_idx=None, verbose=False):
    level_indices = [level_idx] if level_idx is not None else list(range(len(LEVELS)))
    all_results   = {m: [] for m in ALL_MODELS}

    for model in ALL_MODELS:
        print(f"\n{'─'*60}")
        print(f"  MODEL: {model}")
        print(f"{'─'*60}")
        for idx in level_indices:
            r = run_level(idx, model, verbose=True)
            if r is not None:
                all_results[model].append(r)
            time.sleep(0.3)

    # Comparison table
    scope = LEVELS[level_idx]["name"] if level_idx is not None else "ALL LEVELS"
    print(f"\n{'='*72}")
    print(f"  COMPARISON TABLE — {scope}")
    print(f"{'='*72}")
    print(f"  {'MODEL':<24} {'VD_ACC':<10} {'WD_ACC':<10} {'FA_MATCH':<10} COST_USD")
    print(f"  {'-'*68}")

    for model in ALL_MODELS:
        rs = all_results[model]
        if not rs:
            print(f"  {model:<24} {'—':<10} {'—':<10} {'—':<10} —")
            continue
        n_total   = sum(r["n_pairs"]          for r in rs)
        vd_ok     = sum(r["verdict_correct"]  for r in rs)
        wd_ok     = sum(r["words_correct"]    for r in rs)
        fa_ok     = sum(1 for r in rs if r["final_answer_match"])
        cost      = sum(r["cost_usd"] for r in rs if r["cost_usd"] is not None)
        vd_pct    = f"{vd_ok*100//n_total}%" if n_total else "—"
        wd_pct    = f"{wd_ok*100//n_total}%" if n_total else "—"
        fa_str    = f"{fa_ok}/{len(rs)}"
        print(f"  {model:<24} {vd_pct:<10} {wd_pct:<10} {fa_str:<10} ${cost:.4f}")

    print(f"{'='*72}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Language Game — LLM benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python language_api_runner.py --model claude-opus-4-7 --level 0
  python language_api_runner.py --model gpt-5.5
  python language_api_runner.py --all-models --level 1
  python language_api_runner.py --all-models

  # Single-shot mode: all pairs in one prompt, only FINAL_ANSWER returned
  python language_api_runner.py --model claude-opus-4-7 --level 2 --single-shot
  python language_api_runner.py --model gpt-5.5 --level 3 --single-shot --runs 3
""")
    parser.add_argument("--model",       type=str,  default="claude-opus-4-7",
                        help="Model ID (e.g. claude-opus-4-7, gpt-5.5)")
    parser.add_argument("--level",       type=int,  default=None,
                        help="Level index 0-3 (omit to run all levels)")
    parser.add_argument("--all-models",  action="store_true",
                        help="Run all supported models and print comparison table")
    parser.add_argument("--runs",        type=int,  default=1,
                        help="Number of repeated runs per level (for reliability stats)")
    parser.add_argument("--single-shot", action="store_true",
                        help="Send all pairs in one prompt; model outputs only FINAL_ANSWER")
    args = parser.parse_args()

    if args.all_models:
        run_all_models(level_idx=args.level)
    elif args.level is not None:
        _run = run_level_single_shot if args.single_shot else run_level
        for run_i in range(args.runs):
            if args.runs > 1:
                print(f"\n--- Run {run_i+1}/{args.runs} ---")
            _run(args.level, args.model, verbose=True, run_idx=run_i+1)
    else:
        for run_i in range(args.runs):
            if args.runs > 1:
                print(f"\n=== Run {run_i+1}/{args.runs} ===")
            run_all_levels(args.model, verbose=True, single_shot=args.single_shot)

# ---------------------------------------------------------------------------
# API key exports (set these before running)
# ---------------------------------------------------------------------------
# export ANTHROPIC_API_KEY="sk-ant-..."
# export OPENAI_API_KEY="sk-proj-..."
# export DEEPSEEK_API_KEY="sk-..."
# export GOOGLE_API_KEY="AIzaSy..."
# export MOONSHOT_API_KEY="sk-..."
