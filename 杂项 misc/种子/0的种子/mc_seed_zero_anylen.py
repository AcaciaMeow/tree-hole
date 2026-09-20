#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minecraft Seed HashCode Zero — 任意长度通用搜索器
=====================================================
暴力搜索指定长度 n 的所有可打印 ASCII 字符串，使其 Java String.hashCode() = 0。

用法:
    python3 mc_seed_zero_anylen.py [长度] [选项]

示例:
    python3 mc_seed_zero_anylen.py 7          # 搜索 7 字符解
    python3 mc_seed_zero_anylen.py 8          # 搜索 8 字符解
    python3 mc_seed_zero_anylen.py 7 --all    # 搜索 1~7 字符所有解
    python3 mc_seed_zero_anylen.py 10 -o out.txt  # 指定输出文件

特性:
- 数学剪枝回溯，非纯暴力枚举
- 实时追加写入 txt，支持随时 Ctrl+C 中断
- 进度自动保存到 JSON，重启自动恢复
- 支持任意长度 n >= 1（但 n <= 6 时无解，n >= 7 才有解）

作者: Kimi AI
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime

# ==================== 常量 ====================
MIN_CHAR = 32       # 可打印 ASCII 下限 (空格)
MAX_CHAR = 126      # 可打印 ASCII 上限 (~)
M = 2 ** 32

# 预计算 31 的幂（足够大）
MAX_POW = 64
POW31 = [31 ** i for i in range(MAX_POW)]

# ==================== 进度管理器 ====================
class ProgressManager:
    def __init__(self, n, output_file):
        self.n = n
        self.output_file = output_file
        self.progress_file = f"progress_n{n}.json"
        self.data = {
            "n": n,
            "current_k": None,
            "found_count": 0,
            "start_time": datetime.now().isoformat(),
            "last_update": None,
        }
        self.interrupted = False
        self._dirty = False
        self._save_counter = 0

    def load(self):
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if loaded.get("n") == self.n:
                        self.data = loaded
                        print(f"[恢复进度] n={self.n}, 上次 k={self.data.get('current_k', 'N/A')}, 已找到 {self.data['found_count']} 个")
                        return True
            except Exception as e:
                print(f"[警告] 读取进度失败: {e}")
        return False

    def save(self, force=False):
        if not self._dirty and not force:
            return
        self.data["last_update"] = datetime.now().isoformat()
        try:
            with open(self.progress_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            self._dirty = False
        except Exception as e:
            print(f"[错误] 保存进度失败: {e}")

    def update(self, k=None, found_delta=0):
        if k is not None:
            self.data["current_k"] = k
        if found_delta:
            self.data["found_count"] += found_delta
        self._dirty = True
        self._save_counter += 1
        # 每处理 10 个 k 保存一次
        if self._save_counter % 10 == 0:
            self.save()

    def signal_handler(self, signum, frame):
        print("\n[收到中断信号] 正在保存进度...")
        self.interrupted = True
        self.save(force=True)
        print(f"[已保存] 进度 → {self.progress_file}")
        print(f"[已保存] 结果 → {self.output_file}")
        print("下次运行将自动从断点继续。")
        sys.exit(0)


# ==================== 核心搜索 ====================
def precompute_ranges(n):
    """预计算剩余 i 位的最小/最大贡献值"""
    rem_min = [0] * (n + 1)
    rem_max = [0] * (n + 1)
    for i in range(n + 1):
        rem_min[i] = MIN_CHAR * sum(POW31[j] for j in range(i))
        rem_max[i] = MAX_CHAR * sum(POW31[j] for j in range(i))
    return rem_min, rem_max


def backtrack_stream(N, n, rem_min, rem_max, out_f, progress):
    """
    回溯搜索所有满足 sum(c_i * 31^i) = N 的字符串
    结果直接流式写入文件，不全部保存在内存中
    返回找到的解的数量
    """
    count = 0
    path = []

    def dfs(remain, depth):
        nonlocal count
        if progress.interrupted:
            return
        if depth == 0:
            if remain == 0:
                s = "".join(path)
                out_f.write(f"{s}\n")
                count += 1
                if count % 1000 == 0:
                    out_f.flush()
            return

        coeff = POW31[depth - 1]
        c_min = max(MIN_CHAR, (remain - rem_max[depth - 1] + coeff - 1) // coeff)
        c_max = min(MAX_CHAR, (remain - rem_min[depth - 1]) // coeff)

        for c in range(c_min, c_max + 1):
            path.append(chr(c))
            dfs(remain - c * coeff, depth - 1)
            path.pop()

    dfs(N, n)
    return count


def search_length_n(n, k_start, k_end, progress, out_f):
    """搜索指定长度 n 的所有解"""
    rem_min, rem_max = precompute_ranges(n)
    total_k = k_end - k_start + 1
    batch_found = 0

    for idx, k in enumerate(range(k_start, k_end + 1), 1):
        if progress.interrupted:
            break

        progress.update(k=k)
        N = k * M

        if N < rem_min[n] or N > rem_max[n]:
            continue

        found = backtrack_stream(N, n, rem_min, rem_max, out_f, progress)
        batch_found += found

        if found > 0:
            progress.update(found_delta=found)
            print(f"  k={k:>4} ({idx:>4}/{total_k}) → {found:>6} 个解 | 累计: {progress.data['found_count']}")
        elif idx == 1 or idx % 50 == 0 or idx == total_k:
            print(f"  k={k:>4} ({idx:>4}/{total_k}) → 0 个解 | 累计: {progress.data['found_count']}")

    out_f.flush()
    return batch_found


# ==================== 主程序 ====================
def main():
    parser = argparse.ArgumentParser(
        description="搜索 Java String.hashCode() = 0 的可打印 ASCII 字符串",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s 7              搜索 7 字符解
  %(prog)s 8              搜索 8 字符解
  %(prog)s 7 --all        搜索 1~7 字符所有解
  %(prog)s 10 -o out.txt  指定输出文件名
        """
    )
    parser.add_argument("length", type=int, help="搜索的字符串长度 (>=1)")
    parser.add_argument("--all", action="store_true", help="搜索从 1 到指定长度的所有解")
    parser.add_argument("-o", "--output", type=str, default=None, help="输出文件名 (默认: seeds_n{长度}.txt)")
    args = parser.parse_args()

    if args.length < 1:
        print("[错误] 长度必须 >= 1")
        sys.exit(1)

    # 确定搜索范围
    if args.all:
        lengths = list(range(1, args.length + 1))
        output_file = args.output or f"seeds_n1_to_n{args.length}.txt"
    else:
        lengths = [args.length]
        output_file = args.output or f"seeds_n{args.length}.txt"

    print("=" * 60)
    print("Minecraft Seed HashCode Zero — 任意长度通用搜索器")
    print("=" * 60)
    print(f"搜索长度: {lengths}")
    print(f"字符范围: 可打印 ASCII ({MIN_CHAR}~{MAX_CHAR})")
    print(f"结果文件: {output_file}")
    print("提示: 按 Ctrl+C 可随时中断，下次运行自动恢复")
    print("=" * 60)

    overall_start = time.time()
    overall_found = 0

    # 打开结果文件（追加模式）
    first_open = not os.path.exists(output_file) or os.path.getsize(output_file) == 0
    with open(output_file, "a", encoding="utf-8") as out_f:
        if first_open:
            out_f.write("# ==============================================\n")
            out_f.write("# Minecraft Seed — hashCode() = 0 搜索结果\n")
            out_f.write(f"# 搜索长度: {lengths}\n")
            out_f.write(f"# 字符范围: 可打印 ASCII ({MIN_CHAR}~{MAX_CHAR})\n")
            out_f.write(f"# 开始时间: {datetime.now().isoformat()}\n")
            out_f.write("# ==============================================\n")
            out_f.flush()

        for n in lengths:
            # 每个长度独立管理进度
            progress = ProgressManager(n, output_file)
            has_progress = progress.load()

            # 注册信号处理
            signal.signal(signal.SIGINT, progress.signal_handler)
            signal.signal(signal.SIGTERM, progress.signal_handler)

            # 计算 k 范围
            min_val = MIN_CHAR * sum(POW31[i] for i in range(n))
            max_val = MAX_CHAR * sum(POW31[i] for i in range(n))
            k_start = min_val // M
            k_end = max_val // M

            if k_start > k_end:
                print(f"\n[长度 {n}] 不可能达到 2^32 的倍数，跳过")
                continue

            if has_progress and progress.data["current_k"] is not None:
                actual_k_start = progress.data["current_k"]
                print(f"\n[恢复] 长度 {n}, 从 k={actual_k_start} 继续 (范围 [{k_start}, {k_end}])")
            else:
                actual_k_start = k_start
                print(f"\n[搜索长度 {n}] k ∈ [{k_start}, {k_end}], 预计 {k_end - k_start + 1} 个 k 值")

            found = search_length_n(n, actual_k_start, k_end, progress, out_f)
            overall_found += found

            if not progress.interrupted:
                progress.save(force=True)
                # 清理该长度的进度文件
                if os.path.exists(progress.progress_file):
                    os.remove(progress.progress_file)
                print(f"[长度 {n} 完成] 找到 {progress.data['found_count']} 个解")

            if progress.interrupted:
                break

    elapsed = time.time() - overall_start
    print("\n" + "=" * 60)
    print(f"[完成] 总计找到 {overall_found} 个解")
    print(f"[耗时] {elapsed:.2f} 秒")
    print(f"[结果] 保存到 {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
