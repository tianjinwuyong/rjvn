import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

BLOCKED_TERMS = ("Danh sách CNV", "payroll", "salary", "工资", "身份证", "id_card", "employee-selfies")


def approved_paths():
    config = ROOT / "approved-sources.txt"
    for raw in config.read_text(encoding="utf-8").splitlines():
        value = raw.strip()
        if value and not value.startswith("#"):
            path = Path(value)
            if any(term.lower() in str(path).lower() for term in BLOCKED_TERMS):
                raise RuntimeError(f"Sensitive source is blocked: {path}")
            yield path


async def remember_approved():
    if not os.getenv("LLM_API_KEY"):
        raise RuntimeError("Copy .env.example to .env and set an approved LLM_API_KEY first.")
    import cognee
    count = 0
    for source in approved_paths():
        files = source.rglob("*") if source.is_dir() else [source]
        for file in files:
            if file.is_file() and file.suffix.lower() in {".md", ".txt", ".pdf"}:
                await cognee.remember(str(file))
                count += 1
    print(f"Remembered {count} approved source(s).")


async def recall(query):
    if not os.getenv("LLM_API_KEY"):
        raise RuntimeError("Copy .env.example to .env and set an approved LLM_API_KEY first.")
    import cognee
    results = await cognee.recall(query_text=query)
    for item in results:
        print(getattr(item, "text", item))


async def main():
    parser = argparse.ArgumentParser(description="Local, approved-source Cognee memory")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("remember")
    ask = sub.add_parser("recall")
    ask.add_argument("query")
    args = parser.parse_args()
    if args.command == "remember":
        await remember_approved()
    else:
        await recall(args.query)


if __name__ == "__main__":
    asyncio.run(main())
