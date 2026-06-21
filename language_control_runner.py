"""
language_control_runner.py — Control condition benchmark for the Language Game.

Each control condition presents a pre-formed emergent sentence directly to the model.
The model must identify its type (QUESTION / NEW_INSTRUCTIONS / NONSENSE) and answer.

Control conditions:
  0 = Low complexity      (question)
  1 = Medium complexity   (question)
  2 = High complexity     (nonsense)
  3 = Maximum complexity  (new instructions)

Usage
─────
  python language_control_runner.py --model gpt-5.5
  python language_control_runner.py --model claude-opus-4-7 --condition 2
  python language_control_runner.py --all-models
  python language_control_runner.py --model gemini-3.1-pro-preview --runs 3

Output
──────
  JSON log per run in logs_language_control/
"""

import argparse
import json
import os
import re
import random
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    from language_game import BASE_RULES, WORD_SELECT_RULES
except Exception as e:
    print(f"[ERROR] Could not import from language_game.py: {e}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Control conditions
# ---------------------------------------------------------------------------
CONTROL_CONDITIONS = [
    {
        "name":            "Low Complexity Control",
        "level_idx":       0,
        "emergent":        "What is the normal color of leaves on a tree?",
        "correct_answer":  "green",
        "valid_answers":   ["green"],
        "expected_case":   "QUESTION",
    },
    {
        "name":            "Medium Complexity Control",
        "level_idx":       1,
        "emergent":        "How many hours are in 3 days?",
        "correct_answer":  "72",
        "valid_answers":   ["72", "72 hours", "seventy two", "seventy-two"],
        "expected_case":   "QUESTION",
    },
    {
        "name":            "High Complexity Control",
        "level_idx":       2,
        "emergent":        "My neighbors' dog jumped pool down to the store and however way the food ran up.",
        "correct_answer":  "My neighbors' dog jumped pool down to the store and however way the food ran up.",
        "valid_answers":   ["my neighbors dog jumped pool down to the store and however way the food ran up"],
        "expected_case":   "NONSENSE",
    },
    {
        "name":            "Maximum Complexity Control",
        "level_idx":       3,
        # accept any ordering/formatting of B,A,A
        "correct_answer":  "B, A, A",
        "valid_answers":   ["b a a", "b, a, a", "baa", "b,a,a", "b a, a", "b-a-a",
                            "a a b", "a, a, b", "aab",
                            "1=b 2=a 3=a", "q1 b q2 a q3 a",
                            "question 1 b question 2 a question 3 a"],
        "emergent": (
            "The new game goes in this way: the first sentence spells the first question. "
            "The second spells the second question, etc.. "
            "Your answer to these questions may be A, B, C or D and the corresponding answers "
            "will be listed after these letters. The idea of this game is that the answers to "
            "the different questions refer to each other, this means you can only find the answer "
            "by finding the right combination of answers. The game starts now.\n\n"
            "Question 1: How many answers are A?\n"
            "A = 1\nB = 2\nC = 3\nD = 4\n\n"
            "Question 2: I'm unhappy when I wear what color?\n"
            "A = Green\nB = Blue\nC = Purple\nD = Grass\n\n"
            "Question 3: The answer to this question is?\n"
            "A = A\nB = B\nC = C\nD = D"
        ),
        "correct_answer": "B, A, A",
        "expected_case":  "NEW_INSTRUCTIONS",
    },
]

# ---------------------------------------------------------------------------
# Provider / model setup  (mirrors language_api_runner.py)
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
    "claude-opus-4-7":        {"input":  5.00, "output": 25.00},
    "gpt-5.5":                {"input":  5.00, "output": 30.00},
    "gemini-3.1-pro-preview": {"input":  2.00, "output": 12.00},
    "deepseek-v4-pro":        {"input":  0.435,"output":  0.87},
    "deepseek-reasoner":      {"input":  0.55, "output":  2.19},
    "kimi-k2.6":              {"input":  0.95, "output":  4.00},
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
# API call  (identical to language_api_runner.py)
# ---------------------------------------------------------------------------
def call_model(model_id, prompt, system_prompt=None, _max_retries=5):
    for attempt in range(_max_retries):
        try:
            return _call_model_once(model_id, prompt, system_prompt)
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


def _call_model_once(model_id, prompt, system_prompt=None):
    provider = _provider(model_id)
    reasoner = _is_reasoner(model_id)
    max_tok  = 50000

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
        params = dict(model=model_id, max_tokens=max_tok, messages=messages)
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
        return text, resp.usage.prompt_tokens, resp.usage.completion_tokens, ""

    raise ValueError(f"No handler for provider: {provider!r}")


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
def build_control_prompt(condition_idx):
    cond = CONTROL_CONDITIONS[condition_idx]

    base_rules_text = "\n".join(BASE_RULES)
    word_select_text = "\n".join(WORD_SELECT_RULES)

    return f"""You are solving the emergent layer of a language reasoning puzzle.

The extracted words from the sentence pairs have been collected and form the following hidden statement:

  \"{cond['emergent']}\"

BASE WORLD RULES
────────────────
{base_rules_text}

EMERGENT LAYER INSTRUCTIONS
────────────────────────────
{word_select_text}

TASK
────
Determine which of the three cases applies to the hidden statement above, then provide your answer.

Output ONLY these two lines — nothing else before or after:
CASE: <QUESTION | NEW_INSTRUCTIONS | NONSENSE>
FINAL_ANSWER: <your answer>"""


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()


def score_answer(given, valid_answers):
    """True if the given answer matches any of the valid answers (token-level)."""
    given_norm = _norm(given)
    for va in valid_answers:
        if given_norm == _norm(va):
            return True
    # also check if all tokens of the shortest valid answer appear in given
    # (handles "72" matching "72 hours" and vice versa for numeric answers)
    for va in valid_answers:
        va_norm = _norm(va)
        if len(va_norm) == 1 and va_norm[0] in given_norm:
            return True
    return False


# ---------------------------------------------------------------------------
# Run one control condition
# ---------------------------------------------------------------------------
def run_control_condition(condition_idx, model, verbose=True, run_idx=1,
                          log_dir="logs_language_control"):
    cond = CONTROL_CONDITIONS[condition_idx]

    os.makedirs(log_dir, exist_ok=True)
    safe_model = model.replace("/", "-")
    safe_name  = cond["name"].replace(" ", "-")
    timestamp  = time.strftime("%Y%m%d_%H%M%S")
    log_path   = os.path.join(log_dir, f"{safe_model}_{safe_name}_run{run_idx}_{timestamp}.json")

    prompt = build_control_prompt(condition_idx)

    if verbose:
        print(f"\n{'='*60}")
        print(f"  {cond['name']}  [{model}]")
        print(f"{'='*60}")
        print(f"  Emergent: \"{cond['emergent'][:80]}{'...' if len(cond['emergent'])>80 else ''}\"")

    run_log = {
        "model":            model,
        "condition_idx":    condition_idx,
        "condition_name":   cond["name"],
        "run":              run_idx,
        "status":           "in_progress",
        "emergent_sentence": cond["emergent"],
        "expected_case":    cond["expected_case"],
        "correct_answer":   cond["correct_answer"],
        "emergent_case":    None,
        "model_answer":     "",
        "answer_correct":   False,
        "case_correct":     False,
        "full_response":    "",
        "response_time_s":  0.0,
        "tokens_in":        0,
        "tokens_out":       0,
        "total_tokens":     0,
        "cost_usd":         None,
    }

    def _save():
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(run_log, f, indent=2, ensure_ascii=False)

    _save()

    t0 = time.time()
    try:
        response_text, in_tok, out_tok, _ = call_model(model, prompt)
    except KeyboardInterrupt:
        print("\n  [INTERRUPTED]")
        run_log["status"] = "interrupted"
        _save()
        return run_log
    except Exception as e:
        print(f"  [API ERROR] {e}")
        run_log["status"] = "error"
        run_log["error"]  = str(e)
        _save()
        return run_log

    elapsed = round(time.time() - t0, 2)

    # retry empty response once
    if not response_text.strip():
        if verbose:
            print("  [!] Empty response — retrying...")
        try:
            response_text2, in_tok2, out_tok2, _ = call_model(model, prompt)
            in_tok  += in_tok2
            out_tok += out_tok2
            if response_text2.strip():
                response_text = response_text2
        except Exception:
            pass

    case_m  = re.search(r"CASE\s*:\s*(QUESTION|NEW_INSTRUCTIONS|NONSENSE)",
                        response_text, re.IGNORECASE)
    ans_m   = re.search(r"FINAL_ANSWER\s*:\s*(.+)", response_text,
                        re.IGNORECASE | re.DOTALL)

    emergent_case = case_m.group(1).upper() if case_m else None
    model_answer  = ans_m.group(1).strip()  if ans_m  else response_text.strip()

    answer_ok = score_answer(model_answer, cond.get("valid_answers", [cond["correct_answer"]]))
    case_ok   = (emergent_case == cond["expected_case"]) if emergent_case else False

    total_cost = _compute_cost(model, in_tok, out_tok)

    if verbose:
        print(f"  Case:    {emergent_case or '?'}  {'✓' if case_ok else '✗'} (expected: {cond['expected_case']})")
        print(f"  Answer:  {'✓' if answer_ok else '✗'}  \"{model_answer[:100]}\"")
        print(f"  Correct: \"{cond['correct_answer']}\"")
        print(f"  Tokens:  {in_tok+out_tok:,}  (in={in_tok:,} out={out_tok:,})")
        if total_cost is not None:
            print(f"  Cost:    ${total_cost:.4f}")
        print(f"  Time:    {elapsed:.1f}s")
        print(f"  Log:     {log_path}")

    run_log.update({
        "status":          "done",
        "emergent_case":   emergent_case,
        "model_answer":    model_answer,
        "answer_correct":  answer_ok,
        "case_correct":    case_ok,
        "full_response":   response_text,
        "response_time_s": elapsed,
        "tokens_in":       in_tok,
        "tokens_out":      out_tok,
        "total_tokens":    in_tok + out_tok,
        "cost_usd":        total_cost,
    })
    _save()
    return run_log


# ---------------------------------------------------------------------------
# Run all conditions for one model
# ---------------------------------------------------------------------------
def run_all_conditions(model, verbose=True, run_idx=1):
    results = []
    for i in range(len(CONTROL_CONDITIONS)):
        r = run_control_condition(i, model, verbose=verbose, run_idx=run_idx)
        results.append(r)
        time.sleep(0.3)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Language Game — Control Condition Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python language_control_runner.py --model gpt-5.5
  python language_control_runner.py --model claude-opus-4-7 --condition 2
  python language_control_runner.py --model gemini-3.1-pro-preview --runs 3
  python language_control_runner.py --all-models
""")
    parser.add_argument("--model",      type=str, default="claude-opus-4-7")
    parser.add_argument("--condition",  type=int, default=None,
                        help="Condition index 0-3 (omit to run all)")
    parser.add_argument("--all-models", action="store_true")
    parser.add_argument("--runs",       type=int, default=1)
    args = parser.parse_args()

    if args.all_models:
        for model in ALL_MODELS:
            print(f"\n{'─'*60}")
            print(f"  MODEL: {model}")
            print(f"{'─'*60}")
            for run_i in range(args.runs):
                if args.runs > 1:
                    print(f"\n--- Run {run_i+1}/{args.runs} ---")
                run_all_conditions(model, verbose=True, run_idx=run_i+1)
    elif args.condition is not None:
        for run_i in range(args.runs):
            if args.runs > 1:
                print(f"\n--- Run {run_i+1}/{args.runs} ---")
            run_control_condition(args.condition, args.model, verbose=True, run_idx=run_i+1)
    else:
        for run_i in range(args.runs):
            if args.runs > 1:
                print(f"\n--- Run {run_i+1}/{args.runs} ---")
            run_all_conditions(args.model, verbose=True, run_idx=run_i+1)
