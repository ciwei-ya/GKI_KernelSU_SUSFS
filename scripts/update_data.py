"""增量更新 GKI 内核版本数据。

读取现有 JSON 数据，仅抓取最后日期之后的新月份，同时更新 LTS 版本。
"""

import json
import os
import time

from gki_fetch import (
    TARGETS, DATA_DIR,
    make_date_range, get_end_date,
    fetch_makefile, fetch_lts, parse_version, json_path,
)


def next_month(date: str) -> str:
    """返回给定 YYYY-MM 的下一个月"""
    y, m = map(int, date.split("-"))
    m += 1
    if m > 12:
        m = 1
        y += 1
    return f"{y}-{m:02d}"


def update_target(android_ver: str, kernel_ver: str,
                  date_start: str, date_end: str | None,
                  dep_cutoff: str) -> bool:
    """增量更新单个目标，返回是否有数据变更"""
    path = json_path(android_ver, kernel_ver)
    end = get_end_date(date_end)
    changed = False

    # 读取现有数据
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("entries", [])
    else:
        data = {
            "android_version": android_ver,
            "kernel_version": kernel_ver,
            "lts": None,
            "entries": [],
        }
        entries = []

    # 确定需要抓取的日期范围
    existing_dates = {e["date"] for e in entries}
    if entries:
        last_date = max(entries, key=lambda e: e["date"])["date"]
        fetch_start = next_month(last_date)
    else:
        fetch_start = date_start

    if fetch_start > end:
        print(f"  Data already up-to-date (last: {end})")
    else:
        new_dates = make_date_range(fetch_start, end)
        # 过滤掉已有的日期
        new_dates = [d for d in new_dates if d not in existing_dates]

        if not new_dates:
            print(f"  No new months to fetch")
        else:
            print(f"  Fetching {len(new_dates)} new month(s): {new_dates[0]} ~ {new_dates[-1]}")
            for date in new_dates:
                label = f"{android_ver}-{kernel_ver}-{date}"
                print(f"    [{label}] ", end="", flush=True)

                text = fetch_makefile(android_ver, kernel_ver, date, dep_cutoff)
                if text is None:
                    print("not found, skip")
                    continue

                ver = parse_version(text)
                if ver is None:
                    print("parse failed, skip")
                    continue

                version, patchlevel, sublevel = ver
                detail = f"{version}.{patchlevel}.{sublevel}"
                entries.append({"date": date, "kernel": detail})
                changed = True
                print(f"-> {detail}")
                time.sleep(0.3)

    # 按日期排序
    entries.sort(key=lambda e: e["date"])

    # 更新 LTS
    lts_label = f"{android_ver}-{kernel_ver}-lts"
    print(f"  [{lts_label}] ", end="", flush=True)
    lts_text = fetch_lts(android_ver, kernel_ver)
    if lts_text is None:
        print("not found, skip")
    else:
        ver = parse_version(lts_text)
        if ver is None:
            print("parse failed, skip")
        else:
            version, patchlevel, sublevel = ver
            lts_value = f"{version}.{patchlevel}.{sublevel}"
            old_lts = data.get("lts")
            if old_lts != lts_value:
                changed = True
                print(f"-> {lts_value} (was {old_lts})")
            else:
                print(f"-> {lts_value} (unchanged)")
            data["lts"] = lts_value

    # 保存
    data["entries"] = entries
    if changed:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  => Saved {len(entries)} entries to {path}")
    else:
        print(f"  => No changes")

    return changed


def main():
    any_changed = False
    for (android_ver, kernel_ver), (date_start, date_end, dep_cutoff) in TARGETS.items():
        print(f"\n=== {android_ver} / {kernel_ver} ===")
        if update_target(android_ver, kernel_ver, date_start, date_end, dep_cutoff):
            any_changed = True

    print(f"\n{'Data updated.' if any_changed else 'All data up-to-date.'}")
    return any_changed


if __name__ == "__main__":
    import sys
    changed = main()
    sys.exit(0 if changed else 1)
