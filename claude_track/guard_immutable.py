"""claude_track/predictions/ は追加のみ許可。既存ファイルの変更・削除・名前変更は失敗させる。
使い方: python3 claude_track/guard_immutable.py <base> [<head>]   (base...head の差分を検査)
"""
from __future__ import annotations
import subprocess, sys

PROTECTED = ("claude_track/predictions/",)


def violations(diff_lines: list[str]) -> list[str]:
    """diff_lines: `git diff --name-status -M` の各行。A(追加)以外で保護パスに触れたら違反。"""
    bad = []
    for line in diff_lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, paths = parts[0], parts[1:]
        touched = [p for p in paths if p.startswith(PROTECTED)]
        if touched and not status.startswith("A"):
            bad.append(f"{status}\t" + " -> ".join(paths))
    return bad


def main(argv: list[str]) -> int:
    base = argv[1]
    head = argv[2] if len(argv) > 2 else "HEAD"
    out = subprocess.run(["git", "diff", "--name-status", "-M", f"{base}...{head}"],
                         capture_output=True, text=True, check=True).stdout.splitlines()
    bad = violations(out)
    if bad:
        print("NG: 保存済みの Claude 予想は変更できません（追加のみ可）。修正は新しいファイルとして追加してください。")
        for b in bad:
            print("  ", b)
        return 1
    print("OK: claude_track/predictions/ に既存ファイルの変更はありません")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
