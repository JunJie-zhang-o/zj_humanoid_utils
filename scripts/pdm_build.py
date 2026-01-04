"""
PDM 构建钩子：在打包前根据 pyproject 的 [tool.deploy] 字段
自动更新版本 JSON 文件中的 `build_time`, `branch_name`, `commit_id`。

放置位置：scripts/pdm_build.py（已由 PDM 后端自动发现）

兼容说明：
- 优先使用 Git 获取分支与提交号；若不可用则回退为 "unknown"。
- 使用 json5 解析与写回，仅更新顶层字段，避免修改 ORIN/PICO 中同名字段。
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
import time
from typing import Optional, Tuple
import json5
import tomli as tomllib


def _project_root() -> Path:
    # 当前文件位于 scripts/ 下，项目根目录为其父目录
    return Path(__file__).resolve().parent.parent


def _read_deploy_config() -> dict:
    """读取 pyproject.toml 的 [tool.deploy] 配置。

    在 Python 3.11+ 使用 tomllib；否则尝试 tomli。
    """
    root = _project_root()

    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
            print(data)
        return data.get("tool", {}).get("deploy", {}) or {}
    except Exception:
        return {}


def _git_info(cwd: Path) -> Tuple[str, str]:
    """获取当前 Git 分支名与短提交号，不可用时返回 unknown。"""
    def _run(cmd: list[str]) -> Optional[str]:
        try:
            out = subprocess.check_output(cmd, cwd=str(cwd))
            return out.decode().strip()
        except Exception:
            return None

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    commit = _run(["git", "rev-parse", "--short", "HEAD"]) or "unknown"
    return branch, commit


def _update_json_fields(file_path: Path, build_time: str, branch: str, commit: str) -> None:
    """以结构化方式更新顶层字段：build_time/branch_name/commit_id。

    使用 json5 解析（支持注释与宽松语法），写回时不保留原注释与格式。
    """
    if not file_path.exists():
        return

    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json5.load(f)
        if not isinstance(data, dict):
            return
        if data["commit_id"] == commit and data["build_time"] != "":
            print("No need to update if the current commit_id is the same.")
            return 
        data["build_time"] = build_time
        data["branch_name"] = branch
        data["commit_id"] = commit
        with file_path.open("w", encoding="utf-8") as f:
            json5.dump(data, f, indent=4, quote_keys=True)
    except Exception:
        # 解析或写回失败则跳过，避免破坏文件
        return


def _target_json_from_config(deploy_cfg: dict) -> Optional[Path]:
    """根据 [tool.deploy] 配置定位待更新的 JSON 文件。

    当前支持：
    - test_version: 更新 src/zjh_utils/resources/versions/test/<version>.json
    - release_version（若未来新增）: 更新 src/zjh_utils/resources/versions/release/<version>.json
    """
    root = _project_root()
    base = root / "src" / "zjh_utils" / "resources" / "versions"

    # 优先 test_version
    test_ver = deploy_cfg.get("test_version")
    if isinstance(test_ver, str) and test_ver:
        return base / "test" / f"{test_ver}.json"

    # 其次 release_version（若存在）
    rel_ver = deploy_cfg.get("release_version")
    if isinstance(rel_ver, str) and rel_ver:
        return base / "release" / f"{rel_ver}.json"

    return None


def _update_version_json() -> None:
    """执行更新逻辑：读取配置、获取 Git 信息、写入 JSON。"""
    deploy_cfg = _read_deploy_config()
    print(f"deploy_cfg:{deploy_cfg}")
    target = _target_json_from_config(deploy_cfg)
    if not target:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    branch, commit = _git_info(_project_root())
    _update_json_fields(target, now, branch, commit)


# === PDM 构建钩子（由 pdm-backend 调用）===
def pdm_build_initialize(context=None):  # noqa: D401
    """在构建开始时调用，更新版本 JSON 的构建信息。"""
    print("-------------------------------------")
    _update_version_json()


# def pdm_build_finalize(context=None):  # noqa: D401
#     """构建结束时的钩子（当前不需要处理）。"""
#     return None


# def pdm_build_clean(context=None):  # noqa: D401
#     """清理钩子（保留以兼容调用顺序，当前不处理）。"""
#     return None



if __name__ == "__main__":
    pdm_build_initialize()