"""Multi-round tournament driver. LLM writes both sides' code per round."""

import argparse
import json
import os
import sys
import time
import traceback

from .battle import run_battle
from .brief import TeamBrief
from .llm import DEFAULT_BASE_URL, LLMClient, LLMError
from .parse import ParseError, parse_brief_response
from .prompts import SYSTEM_PROMPT, build_user_message
from .recorder import Recorder, dump_json
from .report import generate_report
from .sandbox import SandboxError, load_tactic
from .types import Team, UnitType
from .validate import validate_brief


RETRY_FEEDBACK_TEMPLATE = """Your previous response had {n} validation error(s):

{errors}

Fix the issues and resubmit using the same EXACT delimited format from the
system prompt. No prose, no code fences, no JSON wrapping."""


def _format_errors(errors):
    return "\n".join(f"- {e}" for e in errors)


def get_brief_from_llm(client, model, team, round_n, prev_report, *,
                       temperature=0.6, log=print):
    """Call the LLM, parse + validate, retry once on failure.
    Returns a TeamBrief on success. Raises on unrecoverable failure."""
    user_msg = build_user_message(team, round_n, prev_report or "")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    for attempt in range(2):
        log(f"    [{team}] LLM call (attempt {attempt + 1})...")
        t0 = time.perf_counter()
        resp = client.chat(messages, model, temperature=temperature)
        elapsed = time.perf_counter() - t0
        log(f"    [{team}] {elapsed:.1f}s   "
            f"tokens: prompt={resp['usage'].get('prompt_tokens', '?')} "
            f"completion={resp['usage'].get('completion_tokens', '?')}  "
            f"finish={resp['finish_reason']}")
        if resp["finish_reason"] == "length":
            log(f"    [{team}] WARNING: response hit max_tokens — output may be truncated")

        try:
            parsed = parse_brief_response(resp["content"])
            ok, errors = validate_brief(parsed)
        except ParseError as e:
            ok = False
            errors = [f"parse error: {e}"]
            parsed = None

        if ok:
            return TeamBrief(
                round=round_n,
                team=team,
                model=model,
                reasoning=resp["reasoning_content"] or "",
                composition=parsed["composition"],
                tactics=parsed["tactics"],
                scratchpad=parsed["scratchpad"],
            )

        log(f"    [{team}] validation failed:")
        for e in errors:
            log(f"      - {e}")
        if attempt == 1:
            raise RuntimeError(
                f"{team} brief invalid after retry: {errors}"
            )
        # Retry with feedback
        messages.append({"role": "assistant", "content": resp["content"]})
        messages.append({"role": "user", "content": RETRY_FEEDBACK_TEMPLATE.format(
            n=len(errors), errors=_format_errors(errors),
        )})


def _brief_to_classes(brief):
    return {
        UnitType(ut): load_tactic(src, f"r{brief.round}_{brief.team}_{ut}")
        for ut, src in brief.tactics.items()
        if ut in {"mbt", "infantry", "mortar", "medic", "drone"}
    }


def _brief_to_comp_enum(brief):
    return {UnitType(k): v for k, v in brief.composition.items() if v > 0}


def _ensure_all_tactic_classes(brief, fallback_src):
    """Make sure every unit type with count > 0 has a loadable Tactic class.
    If something is missing (shouldn't happen post-validate), fall back to a
    hold-only stub so the battle can run."""
    classes = _brief_to_classes(brief)
    for ut_str, count in brief.composition.items():
        if count <= 0:
            continue
        ut = UnitType(ut_str)
        if ut not in classes:
            classes[ut] = load_tactic(fallback_src, f"fallback_{ut_str}")
    return classes


HOLD_FALLBACK = """
class Tactic:
    def __init__(self):
        pass
    def tick(self, me, world):
        return me.hold()
"""


def run_one_round(client, model, round_n, seed, prev_reports, out_dir, log=print):
    log(f"\n=== Round {round_n} (seed={seed}) ===")

    red_brief = get_brief_from_llm(client, model, "red", round_n,
                                   prev_reports.get("red"), log=log)
    blue_brief = get_brief_from_llm(client, model, "blue", round_n,
                                    prev_reports.get("blue"), log=log)

    log(f"  Compositions:")
    log(f"    RED:  {red_brief.composition}")
    log(f"    BLUE: {blue_brief.composition}")

    red_classes = _ensure_all_tactic_classes(red_brief, HOLD_FALLBACK)
    blue_classes = _ensure_all_tactic_classes(blue_brief, HOLD_FALLBACK)

    recorder_box = [None]

    def on_frame(world, tick):
        if recorder_box[0] is None:
            recorder_box[0] = Recorder(world, red_brief=red_brief,
                                        blue_brief=blue_brief, seed=seed)
        recorder_box[0].snapshot()

    log(f"  Running battle...")
    t0 = time.perf_counter()
    result = run_battle(
        comp_red=_brief_to_comp_enum(red_brief),
        tactics_red=red_classes,
        comp_blue=_brief_to_comp_enum(blue_brief),
        tactics_blue=blue_classes,
        seed=seed, on_frame=on_frame,
    )
    log(f"  Battle done in {time.perf_counter() - t0:.1f}s real time, "
        f"{result['duration_ticks']} ticks. Outcome: {result['outcome']}")
    log(f"    RED  alive: {result['red_alive']} ({result['red_survivors_value']} pts) "
        f"crashes: {result['stats'][Team.RED]['crashes']}")
    log(f"    BLUE alive: {result['blue_alive']} ({result['blue_survivors_value']} pts) "
        f"crashes: {result['stats'][Team.BLUE]['crashes']}")

    red_report = generate_report("red", result, red_brief, blue_brief)
    blue_report = generate_report("blue", result, blue_brief, red_brief)

    rec = recorder_box[0]
    data = rec.finalize(result, red_report=red_report, blue_report=blue_report)

    fname = f"round_{round_n:03d}.json"
    path = os.path.join(out_dir, fname)
    dump_json(data, path)
    log(f"  Recording: {fname}")

    return {
        "round": round_n,
        "file": fname,
        "outcome": result["outcome"],
        "duration_ticks": result["duration_ticks"],
        "red_alive": result["red_alive"],
        "blue_alive": result["blue_alive"],
        "red_survivors_value": result["red_survivors_value"],
        "blue_survivors_value": result["blue_survivors_value"],
    }, {"red": red_report, "blue": blue_report}


def write_manifest(manifest, out_dir):
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)


def load_existing_state(out_dir):
    """Returns (manifest, prev_reports, start_round) for --continue mode."""
    manifest_path = os.path.join(out_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return None, {"red": None, "blue": None}, 1
    with open(manifest_path) as f:
        manifest = json.load(f)
    if not manifest.get("rounds"):
        return manifest, {"red": None, "blue": None}, 1
    last = manifest["rounds"][-1]
    last_path = os.path.join(out_dir, last["file"])
    with open(last_path) as f:
        last_data = json.load(f)
    prev_reports = {
        "red": last_data.get("reports", {}).get("red") or None,
        "blue": last_data.get("reports", {}).get("blue") or None,
    }
    return manifest, prev_reports, last["round"] + 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run an N-round Tactica tournament.")
    parser.add_argument("--model", required=True, help="Model id, e.g. nemotron-3-nano-omni")
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--seed-base", type=int, default=1000)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out-dir", default="web/rounds")
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument(
        "--continue", dest="cont", action="store_true",
        help="Append --rounds more rounds to an existing tournament in --out-dir.",
    )
    args = parser.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)

    client = LLMClient(base_url=args.base_url)

    # Confirm model is listed
    try:
        models = client.list_models()
    except LLMError as e:
        print(f"ERROR listing models: {e}", file=sys.stderr)
        return 2
    if args.model not in models:
        print(f"WARNING: model {args.model!r} not in gateway list: {models}",
              file=sys.stderr)

    if args.cont:
        manifest, prev_reports, start_round = load_existing_state(args.out_dir)
        if manifest is None:
            print(f"--continue: no existing manifest at {args.out_dir}; starting fresh",
                  file=sys.stderr)
            manifest = {
                "model": args.model, "base_url": args.base_url,
                "rounds_total": 0, "rounds": [],
            }
            start_round = 1
        else:
            print(f"--continue: resuming from round {start_round}, "
                  f"existing rounds: {len(manifest['rounds'])}")
    else:
        manifest = {
            "model": args.model, "base_url": args.base_url,
            "rounds_total": 0, "rounds": [],
        }
        prev_reports = {"red": None, "blue": None}
        start_round = 1

    end_round = start_round + args.rounds
    manifest["rounds_total"] = end_round - 1
    manifest["model"] = args.model
    manifest["base_url"] = args.base_url
    write_manifest(manifest, args.out_dir)

    for round_n in range(start_round, end_round):
        seed = args.seed_base + round_n
        try:
            summary, reports = run_one_round(
                client, args.model, round_n, seed, prev_reports, args.out_dir,
            )
        except (LLMError, RuntimeError, SandboxError) as e:
            print(f"\nRound {round_n} FAILED: {e}", file=sys.stderr)
            traceback.print_exc()
            return 3

        manifest["rounds"].append(summary)
        write_manifest(manifest, args.out_dir)
        prev_reports = reports

    print(f"\nDone. {len(manifest['rounds'])} rounds saved to {args.out_dir}/")
    print(f"Manifest: {args.out_dir}/manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
