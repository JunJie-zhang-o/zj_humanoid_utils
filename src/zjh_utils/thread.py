import os
import re
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from plumbum import local
import fire


def _parse_cpu_list(cpu_list_str: str) -> Set[int]:
	s = cpu_list_str.strip()
	if not s:
		return set()
	result: Set[int] = set()
	for part in s.split(","):
		part = part.strip()
		if not part:
			continue
		if "-" in part:
			a, b = part.split("-", 1)
			try:
				start = int(a)
				end = int(b)
				if start <= end:
					result.update(range(start, end + 1))
			except ValueError:
				continue
		else:
			try:
				result.add(int(part))
			except ValueError:
				continue
	return result


def _read_first_line(p: Path) -> Optional[str]:
	try:
		with p.open("r", encoding="utf-8", errors="ignore") as f:
			return f.readline().rstrip("\n")
	except Exception:
		return None


def _read_status_field(status_path: Path, key: str) -> Optional[str]:
	try:
		with status_path.open("r", encoding="utf-8", errors="ignore") as f:
			for line in f:
				if line.startswith(key):
					return line.split(":", 1)[1].strip()
	except Exception:
		pass
	return None


def _iter_threads() -> Iterable[Tuple[int, int, Optional[str], Optional[str]]]:
	proc = Path("/proc")
	for pid_dir in proc.iterdir():
		if not pid_dir.name.isdigit():
			continue
		pid = int(pid_dir.name)
		task_dir = pid_dir / "task"
		if not task_dir.exists():
			continue
		for tid_dir in task_dir.iterdir():
			if not tid_dir.name.isdigit():
				continue
			tid = int(tid_dir.name)
			comm = _read_first_line(tid_dir / "comm")
			status_path = tid_dir / "status"
			cpus_allowed_list = _read_status_field(status_path, "Cpus_allowed_list")
			yield pid, tid, comm, cpus_allowed_list


def _get_rt_policy_priority(tid: int) -> Tuple[Optional[str], Optional[int]]:
	chrt = local["chrt"]
	try:
		out = chrt["-p", str(tid)]()
	except Exception:
		return None, None
	# Expected lines like:
	# pid 123's current scheduling policy: SCHED_FIFO
	# pid 123's current scheduling priority: 50
	policy_match = re.search(r"policy:\s*(\S+)", out)
	prio_match = re.search(r"priority:\s*(\d+)", out)
	policy = policy_match.group(1) if policy_match else None
	prio = int(prio_match.group(1)) if prio_match else None
	return policy, prio


def _read_last_cpu(tid: int) -> Optional[int]:
	"""读取 /proc/<tid>/stat 的 processor 字段（最后运行的 CPU）。"""
	stat_path = Path(f"/proc/{tid}/stat")
	try:
		txt = stat_path.read_text(encoding="utf-8", errors="ignore")
	except Exception:
		return None
	# 解析：pid (comm) state ... 其中 processor 是第 39 个字段（1-based）
	# 去掉括号内容，剩余字段从 state 开始（第 3 个字段），故索引为 39-3=36
	try:
		l = txt.strip()
		p1 = l.find("(")
		p2 = l.rfind(")")
		rest = l[p2 + 1 :].strip()
		fields = rest.split()
		if len(fields) >= 37:
			return int(fields[36])
	except Exception:
		return None
	return None


def _is_kernel_thread(pid: int) -> bool:
	"""若 /proc/<pid>/cmdline 为空，则视为内核线程。"""
	try:
		data = Path(f"/proc/{pid}/cmdline").read_bytes()
		return len(data) == 0
	except Exception:
		return False


def _format_table(rows: List[Dict[str, object]]) -> str:
	if not rows:
		return ""
	headers = ["PID", "TID", "NAME", "POLICY", "PRIO"]
	str_rows = [
		[
			str(r.get("pid", "")),
			str(r.get("tid", "")),
			str(r.get("name", "")),
			str(r.get("policy", "")),
			str(r.get("prio", "")),
		]
		for r in rows
	]
	cols = list(zip(*([headers] + str_rows)))
	widths = [max(len(c) for c in col) for col in cols]

	def fmt(row: List[str]) -> str:
		return "  ".join(val.ljust(w) for val, w in zip(row, widths))

	lines = [fmt(headers), fmt(["-" * w for w in widths])]
	lines.extend(fmt(r) for r in str_rows)
	return "\n".join(lines)


class ThreadCLI:
	def cpu(
		self,
		cpu: int,
		json_out: bool = False,
		only_rt: bool = False,
		mode: str = "last",
		include_kernel: bool = False,
	) -> int:
		"""
		列出与指定 CPU 相关的线程，并显示名称与实时优先级。

		参数:
		- cpu: 目标 CPU 序号 (从 0 开始)
		- json_out: 以 JSON 输出结果
		- only_rt: 仅显示实时调度线程 (SCHED_FIFO/SCHED_RR 且优先级>0)
		- mode: 过滤模式："last" 使用 /proc/<tid>/stat 的 processor 字段（更贴近 htop 的显示），
				"affinity" 使用 Cpus_allowed_list（线程允许运行的 CPU 集合）
		- include_kernel: 是否包含内核线程（默认不包含）

		返回: 0 表示成功
		"""
		target = int(cpu)
		records: List[Dict[str, object]] = []

		for pid, tid, name, allowed in _iter_threads():
			if not include_kernel and _is_kernel_thread(pid):
				continue

			match = False
			if mode == "affinity":
				if not allowed:
					continue
				allowed_set = _parse_cpu_list(allowed)
				match = target in allowed_set
			else:  # mode == "last"
				last = _read_last_cpu(tid)
				match = last == target
			if not match:
				continue

			policy, prio = _get_rt_policy_priority(tid)
			if only_rt:
				if not policy or policy not in {"SCHED_FIFO", "SCHED_RR"} or not prio or prio <= 0:
					continue

			records.append(
				{
					"pid": pid,
					"tid": tid,
					"name": name or "",
					"policy": policy or "",
					"prio": prio if prio is not None else "",
				}
			)

		# Sort: realtime first by prio desc, then by name
		def sort_key(r: Dict[str, object]):
			policy = r.get("policy") or ""
			prio = r.get("prio")
			prio_val = int(prio) if isinstance(prio, int) else -1
			is_rt = 1 if policy in ("SCHED_FIFO", "SCHED_RR") else 0
			return (-is_rt, -prio_val, str(r.get("name") or ""))

		records.sort(key=sort_key)

		if json_out:
			print(json.dumps(records, ensure_ascii=False, indent=2))
		else:
			if not records:
				print(f"No threads found for CPU {target}.")
			else:
				print(_format_table(records))
		return 0


def main():
	fire.Fire(ThreadCLI)


if __name__ == "__main__":
	main()

