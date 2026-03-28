from __future__ import annotations

import argparse

from email_agent.services.agent_service import run_agent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LangGraph email agent.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Override the MAX_EMAILS setting for this run.",
    )
    parser.add_argument(
        "--show-body",
        action="store_true",
        help="Print the drafted reply body when one is created.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_agent(limit=args.limit, include_draft_body=args.show_body)

    if summary["processed_count"] == 0:
        print("No unread emails found.")
        return 0

    print(
        f"Processing {summary['processed_count']} email(s) with backend "
        f"'{summary['backend']}'."
    )

    for result in summary["results"]:
        print()
        print(f"[{result['id']}] {result['subject']}")
        print(f"Intent: {result['intent']}")
        print(f"Urgency: {result['urgency']}")
        print(f"Risk: {result['risk']}")
        print(f"Action: {result['action']}")
        print(f"Why: {result['reason']}")
        print(f"Delivery: {result['delivery_status']}")

        if "draft" in result:
            print(f"Draft subject: {result['draft']['subject']}")
            if args.show_body:
                print("Draft body:")
                print(result["draft"]["body"])

        if "human_decision" in result:
            print(f"Human review: {result['human_decision']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
