import re
import fire
from dataclasses import dataclass, field
from sys import version
from typing import List, Literal, Optional, Tuple, Union
from unittest import result

from dataclasses_json import dataclass_json
from pathlib import Path
import json5
import os
from string import Template

from plumbum import ProcessExecutionError, local , FG
from plumbum.cmd import sudo, chmod, echo, cat, git, sed, cp, bash
import shutil
# from art import  zprint
from zjh_utils.utils import zprint

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
class ScriptHook:
    name: Optional[str] = None
    cmd: Optional[str] = None
    path: Optional[str] = None

    def execute(self) -> bool:
        if self.name is not None:
            zprint(self.name )
        if self.cmd is not None and self.cmd.strip() != "":
            bash["-c", self.cmd] & FG
        elif self.path is not None and self.path.strip() != "":
            if Path(self.path).exists():
                chmod["+x", self.path] & FG
                with local.cwd(Path(self.path).resolve().parent):
                    local[self.path] & FG
            else:
                print(f"Error: {self.path} not exist.")
                return False
        
        return True


@dataclass_json
@dataclass
class Scripts:
    pre_install: List[ScriptHook] = field(default_factory=list)
    post_install: List[ScriptHook] = field(default_factory=list)
    pre_uninstall: List[ScriptHook] = field(default_factory=list)
    post_uninstall: List[ScriptHook] = field(default_factory=list)




@dataclass_json
@dataclass
class Device:
    sys_env_version: Optional[str]
    build_time: Optional[str]
    branch_name: Optional[str]
    commit_id: Optional[str]
    scripts:  Optional[Scripts] = None
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

    @classmethod
    def load(cls, path:str) -> "VersionDescription":
        with open(path, 'r', encoding='utf-8') as f:
            data = json5.load(f)

        version_desc:VersionDescription = VersionDescription.from_dict(data)  # type: ignore
        return version_desc


class AutoDeploy:
    """ZJ Humanoid 自动部署工具"""

    BASE_PATH = Path(__file__).resolve().parent

    DEFAULT_VERSION_PATH = "resources/versions"

    DEFAULT_DIR = Path("/home/nav01/.zj_humanoid")
    DEFAULT_DISTS = DEFAULT_DIR.joinpath("dists")
    DEFAULT_LOGS = DEFAULT_DIR.joinpath("logs")

    wget = local["wget"]

    def __init__(self) -> None:

        versions_for_release = list(self.BASE_PATH.joinpath(self.DEFAULT_VERSION_PATH, "release").rglob("*.json"))
        versions_for_test = list(self.BASE_PATH.joinpath(self.DEFAULT_VERSION_PATH, "test").rglob("*.json"))

        self.release_versions, self.test_versions = {}, {}
        
        for _json in versions_for_release:
            _version_desc = self.load_version(str(_json))
            self.release_versions.update({f"release_{_json.stem}": _json})
        
        for _json in versions_for_test:

            _version_desc = self.load_version(str(_json))
            self.test_versions.update({f"test_{_json.stem}_{_version_desc.commit_id} | {_version_desc.build_time}": _json})


    def list_version(self,  test_plan: Optional[bool]=None, select:bool=False) -> Optional[Tuple[str, Path]]:
        """列出可用版本
        
        Args:
            test_plan: 是否仅显示测试版本
            select: 是否进入选择模式
        """

        show_versions = {}
        if test_plan is None:
            # versions = [all_versions for i in all_versions]
            show_versions = {**self.release_versions, **self.test_versions}
        elif test_plan:
            show_versions = {**self.test_versions}
        else:
            show_versions = {**self.release_versions}


        num = 0
        for key, value in show_versions.items():
            print(f"{num}: {key}")
            num += 1


        if select:
            while 1:
                index_input:str = input("please input will install verison index:")

                if not index_input.isdigit():
                    print("input is invalid!!!")
                    continue
                index = int(index_input)
                if index >= 0 and index < num:
                    print(f"Select - Index:{index}, version:{list(show_versions.keys())[index]}, path:{list(show_versions.values())[index]}")
                    # return index, index_versions[index]
                    return list(show_versions.keys())[index], list(show_versions.values())[index]
    
    @classmethod
    def load_version(cls, json_path: str) -> VersionDescription:

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json5.load(f)

        version_desc:VersionDescription = VersionDescription.from_dict(data)  # type: ignore
        return version_desc



    def install(self, robot_type: Optional[Literal["WA1", "WA2", "U1", "H1", "I2"]] = None, version: Optional[Union[str, Path]] = None, test_plan:Optional[bool] = None):
        """安装指定版本
        
        Args:
            version: 要安装的版本(格式:release/v1.0.4 或 test/v1.1.0)
            test_plan: 是否安装测试版本
        """
        if robot_type is None:
            _robot_type = ["WA1", "WA2", "U1","H1", "I2"]
            print("Please select the model of the robot you wish to install.:")
            for i, v in enumerate(_robot_type):
                print(f"{i}: {v}")

            while 1:
                index_input:str = input("please input will install robot model:")

                if not index_input.isdigit():
                    print("input is invalid!!!")
                    continue
                index = int(index_input)
                if index >= 0 and index < len(_robot_type):
                    robot_type = _robot_type[index]
                    break

        zprint(f"Install | Robot Type:{robot_type}")
        self.DEFAULT_DISTS.mkdir(parents=True, exist_ok=True)
        self.DEFAULT_LOGS.mkdir(parents=True, exist_ok=True)
        _version = None
        if version is None:
            result = self.list_version(test_plan, select=True)
            if result is not None:
                version_key, version_value = result
                version = version_value
            else:
                return
        else:
            print("Installation of a specific version is not currently supported.")
            exit()


        version_file = version
        if version_file is None or version_file == "":
            print("The current version is invalid and automatic deployment is not possible.")
            return
        

        self.pre_global_install(robot_type=robot_type, version=version_key)

        version_desc = self.load_version(str(version_file))


        self.pre_uninstall(desc=version_desc)
        self.uninstall()
        self.post_uninstall(desc=version_desc)

        zprint("install") 
        # 新建文件夹和文件复制
        for resource in version_desc.PICO.resources:
            zprint(str(self.BASE_PATH.joinpath(resource.local_path)))
            zprint(resource.device_path)

            if resource.device_path:
                if Path(resource.device_path).suffix == "":
                    Path(resource.device_path).mkdir(parents=True, exist_ok=True)
                else:
                    Path(resource.device_path).parent.mkdir(parents=True, exist_ok=True)


            if resource.local_path:

                # cp["-r", str(self.BASE_PATH.joinpath(resource.local_path)), str(resource.device_path)]  & FG
                source = local.path(self.BASE_PATH.joinpath(resource.local_path))
                target = local.path(resource.device_path)

                if self.BASE_PATH.joinpath(resource.local_path).stem == "*":
                    source =  local.path(self.BASE_PATH.joinpath(resource.local_path).parent) // "*"
                if Path(resource.device_path).stem == "*":
                    target = local.path(self.BASE_PATH.joinpath(resource.device_path).parent) // "*"
                print(f"source:{source}")
                print(f"target:{target}")
                cp[source, target]  & FG



        dists = self.DEFAULT_DISTS.joinpath(f"{version.parent.name}", f"{version.stem}")

        if dists.exists():
            shutil.rmtree(dists)
        
        dists.mkdir(parents=True, exist_ok=True)

        for module in version_desc.PICO.modules:
            module:Module
            zprint(f"Name:{module.name} | version:{module.version}")
            self.wget["-P", f"{str(dists)}", f"{module.url}"] & FG


        

        self.pre_install(desc=version_desc)
        zprint("install")
        with local.cwd(dists):
            sudo["apt", "-y", "install", local.path(".") // "*"] & FG

        shutil.copy2(version_file, dists.joinpath(f"{version_file.name}"))
        Path(self.DEFAULT_DIR.joinpath("version.json")).unlink(missing_ok=True)
        Path(self.DEFAULT_DIR.joinpath("version.json")).symlink_to(dists.joinpath(f"{_version}.json"))
        self.post_global_install(robot_type)
        self.post_install(desc=version_desc)



    def pre_global_install(self, robot_type, version, robot_name: str="zj_humanoid"):

        bashrc_local  = Path(self.BASE_PATH.joinpath("resources",".bash_zjh"))
        bashrc_device = Path(self.DEFAULT_DIR.joinpath(".bash_zjh"))
        content = bashrc_local.read_text() if bashrc_local.exists() else ""

        py_var = {
            "py_robot_type": robot_type,
            "py_robot_name": robot_name,
            "py_version": version,

        }

        template = Template(content)

        out = template.safe_substitute(py_var)
        bashrc_device.write_text(out)

        bashrc_path = Path("/home/nav01/.bashrc")
        source_line = f"source {bashrc_device}"
        
        if bashrc_path.exists():
            bashrc_content = bashrc_path.read_text()
            # 仅匹配未被注释的有效 source 语句（支持 "source" 或 "." 形式）
            bashrc_device_escaped = re.escape(str(bashrc_device))
            has_active_source = (
                re.search(rf'^\s*source\s+{bashrc_device_escaped}\s*(?:#.*)?$', bashrc_content, re.MULTILINE) or
                re.search(rf'^\s*\.\s+{bashrc_device_escaped}\s*(?:#.*)?$', bashrc_content, re.MULTILINE)
            )
            if not has_active_source:
                # 添加有效的 source 语句到 .bashrc
                with bashrc_path.open('a') as f:
                    f.write(f'\n# ZJ Humanoid environment\n{source_line}\n')
                print(f"✓ 已添加 source 语句到 {bashrc_path}")
            else:
                print(f"✓ {bashrc_path} 已包含有效的 source 语句")
        else:
            print(f"⚠ 警告: {bashrc_path} 不存在")
        



    def post_global_install(self, robot_type: str):
        run_sh = Path('/home/nav01/zj_humanoid/run.sh')
        if run_sh.exists():
            content = run_sh.read_text()
            # 匹配 export ROBOT_TYPE="..." 或 ROBOT_TYPE="..."，只替换第一个
            content = re.sub(r'^(export\s+)?ROBOT_TYPE="[^"]*"', f'export ROBOT_TYPE="{robot_type}"', content, count=1, flags=re.MULTILINE)
            run_sh.write_text(content)
            print(f"✓ run.sh: export ROBOT_TYPE=\"{robot_type}\"")

        # 更新 .bashrc - 只替换第一个匹配
        bashrc = Path("/home/nav01/.bashrc")
        content = bashrc.read_text() if bashrc.exists() else ""

        if re.search(r'^export\s+ROBOT_TYPE=', content, re.MULTILINE):
            content = re.sub(r'^export\s+ROBOT_TYPE=.*$', f'export ROBOT_TYPE="{robot_type}"', content, count=1, flags=re.MULTILINE)
        else:
            content += f'\nexport ROBOT_TYPE="{robot_type}"\n'

        bashrc.write_text(content)


    def pre_install(self, desc:VersionDescription):

        if desc.PICO.scripts is None:
            return

        zprint("pre_install")
        if len(desc.PICO.scripts.pre_install) >= 0:
            for script in desc.PICO.scripts.pre_install:
                script.execute()


    def post_install(self, desc:VersionDescription):
        
        if desc.PICO.scripts is None:
            return

        zprint("post_install")
        if len(desc.PICO.scripts.post_install) >= 0:
            for script in desc.PICO.scripts.post_install:
                script.execute()

    def pre_uninstall(self, desc:VersionDescription):

        if desc.PICO.scripts is None:
            return

        zprint("pre_uninstall") 
        if len(desc.PICO.scripts.pre_uninstall) >= 0:
            for script in desc.PICO.scripts.pre_uninstall:
                script.execute()


    def post_uninstall(self, desc:VersionDescription):

        if desc.PICO.scripts is None:
            return

        zprint("post_uninstall") 
        if len(desc.PICO.scripts.post_uninstall) >= 0:
            for script in desc.PICO.scripts.post_uninstall:
                script.execute()



    def uninstall(self):
        """卸载当前安装的版本"""
        zprint("uninstall") 
        # shutil.rmtree("/home/nav01/zj_humanoid")
        sudo["rm", "-r", "/home/nav01/zj_humanoid"] & FG
        try: 
            Path(self.DEFAULT_DIR.joinpath("version.json")).unlink(missing_ok=True)
            sudo["bash", "-c", "apt purge -y zj-humanoid-ros-noetic-*"] & FG
        except ProcessExecutionError as e:
            if e.retcode == 100:
                # print("没有匹配的包需要卸载")
                print("uninstall done")
            else:
                raise



# class AutoDeployCli:




#     def 


# CLI 入口点
def cli():
    """ZJ Humanoid 部署工具 CLI 入口点"""
    # 远程调试配置（可通过环境变量控制）
    import os
    if os.getenv('ENABLE_REMOTE_DEBUG', '').lower() in ('true', '1', 'yes'):
        try:
            import debugpy
            debugpy.listen(("0.0.0.0", 5678))
            print("⏳ Waiting for debugger to attach on port 5678...")
            debugpy.wait_for_client()  # 等待调试器连接
            print("✅ Debugger attached!")
        except ImportError:
            print("⚠️ debugpy not installed. Run: pip install debugpy")
        except Exception as e:
            print(f"⚠️ Remote debug error: {e}")
    
    fire.Fire(AutoDeploy)


if __name__ == "__main__":
    cli()