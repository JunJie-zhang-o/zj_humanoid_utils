import fire
from dataclasses import dataclass, field
from sys import version
from typing import List, Optional
from unittest import result

from dataclasses_json import dataclass_json
from pathlib import Path
import json5
import os


from plumbum import ProcessExecutionError, local , FG
from plumbum.cmd import sudo, chmod, echo, cat, git, sed, cp
import shutil


@dataclass_json
@dataclass
class Module:
    name:str
    version:str
    url:str
    dependencies:List[str]


@dataclass_json
@dataclass
class Resource:
    device_path:str
    url:Optional[str]
    local_path:Optional[str]


@dataclass_json
@dataclass
class Device:
    sys_env_version: Optional[str]
    build_time: Optional[str]
    branch_name: Optional[str]
    commit_id: Optional[str]
    zjhrobot: Optional[str] = None
    modules:List[Module] = field(default_factory=list)
    resources: List[Resource] = field(default_factory=list)


@dataclass_json
@dataclass
class VersionDescription:
    version: str
    build_time:str
    branch_name:str
    commit_id:str
    ORIN:Device
    PICO:Device


class AutoDeploy:
    """ZJ Humanoid 自动部署工具"""

    BASE_PATH = Path(__file__).resolve().parent

    DEFAULT_VERSION_PATH = "resources/versions"

    DEFAULT_DIR = Path("/home/nav01/.zj_humanoid")
    DEFAULT_DISTS = DEFAULT_DIR.joinpath("dists")
    DEFAULT_LOGS = DEFAULT_DIR.joinpath("logs")

    wget = local["wget"]

    def __init__(self) -> None:

        self.versions_for_release = list(self.BASE_PATH.joinpath(self.DEFAULT_VERSION_PATH, "release").rglob("*.json"))
        self.versions_for_test = list(self.BASE_PATH.joinpath(self.DEFAULT_VERSION_PATH, "test").rglob("*.json"))

        self.DEFAULT_DISTS.mkdir(parents=True, exist_ok=True)
        self.DEFAULT_LOGS.mkdir(parents=True, exist_ok=True)

    def list_version(self, test_plan: Optional[bool]=None, select:bool=False):
        """列出可用版本
        
        Args:
            test_plan: 是否仅显示测试版本
            select: 是否进入选择模式
        """
        versions = []

        if test_plan is None:
            for _json in self.versions_for_release:
                versions.append(f"release_{_json.stem}")
            
            for _json in self.versions_for_test:
                versions.append(f"test_{_json.stem}")
        else:
            _versions = (self.versions_for_test) if test_plan else (self.versions_for_release)
            prefix = "test_" if test_plan else "release_"
            for _json in _versions:
                versions.append(f"{prefix}{_json.stem}")

            
        # [print(version) for version in versions]
        for index, version in enumerate(versions):
            print(f"{index}: {version}")


        if select:
            while 1:
                index_input:str = input("please input will install verison index:")

                if not index_input.isdigit():
                    print("input is invalid!!!")
                    continue
                index = int(index_input)
                if index >= 0 and index < len(versions):
                    print(f"Select - Index:{index}, version:{versions[index]}")
                    return index, versions[index]
        

    def install(self, version: Optional[str] = None, test_plan:Optional[bool] = None):
        """安装指定版本
        
        Args:
            version: 要安装的版本（格式：release/v1.0.4 或 test/v1.1.0）
            test_plan: 是否安装测试版本
        """
        _version = None
        if version is None:
            result = self.list_version(test_plan, select=True)
            if result is not None:
                _, version_str = result
                version_str = version_str.replace("_", os.sep)
                _version = version_str.split(os.sep)[-1]
                version = version_str
            else:
                return
        else:
            _version = version.split(os.sep)[-1]



        version_file = self.BASE_PATH.joinpath(self.DEFAULT_VERSION_PATH, f"{version}.json")

        with open(version_file, 'r', encoding='utf-8') as f:
            data = json5.load(f)

        version_desc = VersionDescription.from_dict(data)  # type: ignore

        # 新建文件夹和文件复制
        for resource in version_desc.PICO.resources:
            Path(resource.device_path).mkdir(parents=True, exist_ok=True)

            if resource.url:
                pass
            
            

            if resource.local_path:
                # cp["-r", str(self.BASE_PATH.joinpath(resource.local_path)), str(resource.device_path)]  & FG
                source = local.path(self.BASE_PATH.joinpath(resource.local_path))
                target = local.path(resource.device_path)

                if self.BASE_PATH.joinpath(resource.local_path).stem == "*":
                    source =  local.path(self.BASE_PATH.joinpath(resource.local_path).parent) // "*"
                if Path(resource.device_path).stem == "*":
                    target = local.path(self.BASE_PATH.joinpath(resource.device_path).parent) // "*"

                cp[source, target]  & FG

        

        dists = self.DEFAULT_DISTS.joinpath(f"{version}")

        if dists.exists():
            shutil.rmtree(dists)
        
        dists.mkdir(parents=True, exist_ok=True)

        for module in version_desc.PICO.modules:
            module:Module
            print("=" * 60)
            print(f"Name:{module.name} | version:{module.version}")
            self.wget["-P", f"{str(dists)}", f"{module.url}"] & FG


        self.uninstall()

        with local.cwd(dists):
            sudo["apt", "-y", "install", local.path(".") // "*"] & FG

        shutil.copy2(version_file, dists.joinpath(f"{_version}.json"))
        # Path(dists.joinpath(f"{_version}.json")).symlink_to(self.DEFAULT_DIR.joinpath("version.json"))
        Path(self.DEFAULT_DIR.joinpath("version.json")).unlink(missing_ok=True)
        Path(self.DEFAULT_DIR.joinpath("version.json")).symlink_to(dists.joinpath(f"{_version}.json"))


    def uninstall(self):
        """卸载当前安装的版本"""
        try: 
            Path(self.DEFAULT_DIR.joinpath("version.json")).unlink(missing_ok=True)
            sudo["bash", "-c", "apt purge -y zj-humanoid-ros-noetic-*"] & FG
        except ProcessExecutionError as e:
            if e.retcode == 100:
                # print("没有匹配的包需要卸载")
                print("uninstall done")
            else:
                raise


# CLI 入口点
def cli():
    """ZJ Humanoid 部署工具 CLI 入口点"""
    fire.Fire(AutoDeploy)


if __name__ == "__main__":
    cli()