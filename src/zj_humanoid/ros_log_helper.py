import re
import csv
from decimal import Decimal
from typing import List, Tuple


TIMESTAMP_PATTERN = re.compile(r"\[(\d{9,}\.\d+)\]")


def extract_timestamps(text: str) -> List[Decimal]:
	"""从 ROS 日志文本中提取形如 [1766459755.097116622] 的时间戳列表。

	- 仅匹配方括号中为纯数字 + 小数点的片段，避免匹配人类可读时间如 [2025-12-23 ...]
	- 返回 Decimal 列表以保持精度。
	"""
	matches = TIMESTAMP_PATTERN.findall(text)
	return [Decimal(m) for m in matches]


def compute_deltas(timestamps: List[Decimal]) -> List[Decimal]:
	"""计算相邻时间戳增量，首个增量为 0。"""
	if not timestamps:
		return []
	deltas: List[Decimal] = [Decimal("0")]  # 首项增量设为 0
	for i in range(1, len(timestamps)):
		deltas.append(timestamps[i] - timestamps[i - 1])
	return deltas


def count_deltas_over_5ms(deltas: List[Decimal]) -> int:
	"""统计增量严格大于 5ms 的个数。"""
	threshold_sec = Decimal("0.005")  # 5ms = 0.005s
	return sum(1 for d in deltas if d > threshold_sec)


def write_csv_two_rows(output_path: str, timestamps: List[Decimal], deltas: List[Decimal]) -> None:
	"""按列写入 CSV：每行两列 [timestamp, delta]。"""
	with open(output_path, "w", newline="", encoding="utf-8") as f:
		writer = csv.writer(f)
		for t, d in zip(timestamps, deltas):
			writer.writerow([str(t), str(d)])




def parse_log_file_to_csv(input_path: str, output_path: str) -> Tuple[int, int]:
	"""解析日志文件并写出两列 CSV，返回(时间戳数量, 增量数量)。"""
	with open(input_path, "r", encoding="utf-8", errors="ignore") as f:
		text = f.read()
	timestamps = extract_timestamps(text)
	deltas = compute_deltas(timestamps)
	write_csv_two_rows(output_path, timestamps, deltas)
	return (len(timestamps), len(deltas))


def _demo_sample() -> Tuple[List[Decimal], List[Decimal]]:
	"""使用内置样例进行一次快速解析验证。"""
	sample = (
		"[2025-12-23 11:15:55.098] [DEBUG] [1766459755.097116622]: DualArmRobot::check_uplimb_can_control\n"
		"[2025-12-23 11:16:10.846] [DEBUG] [1766459770.831956526]: DualArmRobot::subscrib_whole_body_servoj\n"
	)
	ts = extract_timestamps(sample)
	ds = compute_deltas(ts)
	return ts, ds


def main():
	import argparse
	parser = argparse.ArgumentParser(description="提取 ROS 日志中的时间戳并输出两列 CSV（timestamp, delta）。")
	parser.add_argument("-i", "--input", required=True, help="输入日志文件路径")
	parser.add_argument("-o", "--output", required=True, help="输出 CSV 文件路径")
	parser.add_argument("--demo", action="store_true", help="运行内置样例解析并退出")
	args = parser.parse_args()

	if args.demo:
		ts, ds = _demo_sample()
		print(f"demo timestamps: {[str(x) for x in ts]}")
		print(f"demo deltas:    {[str(x) for x in ds]}")
		print(f"demo >5ms count: {count_deltas_over_5ms(ds)}")
		return

	n_ts, n_ds = parse_log_file_to_csv(args.input, args.output)
	print(f"parsed timestamps: {n_ts}, deltas: {n_ds}")
	# 重新计算增量用于统计 >5ms 个数（也可在 parse 中返回，但保持接口简单）
	with open(args.input, "r", encoding="utf-8", errors="ignore") as f:
		_text = f.read()
	_ts = extract_timestamps(_text)
	_ds = compute_deltas(_ts)
	print(f">5ms count: {count_deltas_over_5ms(_ds)}")

	# 仅生成 CSV，不再写 HDF5
	if n_ts == 0:
		print("warning: 未在日志中匹配到任何时间戳，检查日志格式是否包含 [<epoch>.<frac>] 片段。")


if __name__ == "__main__":
	main()

