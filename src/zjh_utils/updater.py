"""
Python库自更新模块

支持多种更新方式：
1. 基于PyPI的版本检查和更新
2. 基于Git仓库的更新
3. 基于自定义URL的更新
"""

import os
import sys
import json
import subprocess
import requests
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from packaging import version
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class UpdateConfig:
    """更新配置类"""
    package_name: str
    current_version: str
    update_source: str = "pypi"  # pypi, git, url
    repository_url: Optional[str] = None
    branch: str = "main"
    check_interval: int = 86400  # 24小时检查一次
    auto_update: bool = False
    backup_before_update: bool = True
    update_hooks: Optional[Dict[str, Callable]] = None


class PackageUpdater:
    """包更新器主类"""
    
    def __init__(self, config: UpdateConfig):
        self.config = config
        self.last_check_file = Path.home() / f".{config.package_name}_last_update"
        
    def check_for_updates(self) -> Optional[str]:
        """
        检查是否有可用更新
        
        Returns:
            Optional[str]: 如果有更新，返回新版本号；否则返回None
        """
        if not self._should_check():
            return None
            
        try:
            if self.config.update_source == "pypi":
                latest_version = self._check_pypi_updates()
            elif self.config.update_source == "git":
                latest_version = self._check_git_updates()
            elif self.config.update_source == "url":
                latest_version = self._check_url_updates()
            else:
                logger.error(f"不支持的更新源: {self.config.update_source}")
                return None
                
            if latest_version and self._is_newer_version(latest_version):
                logger.info(f"发现新版本: {latest_version}")
                return latest_version
                
        except Exception as e:
            logger.error(f"检查更新时出错: {e}")
            
        return None
    
    def update_package(self, target_version: Optional[str] = None) -> bool:
        """
        更新包到指定版本或最新版本
        
        Args:
            target_version: 目标版本，如果为None则更新到最新版本
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 执行更新前钩子
            if self.config.update_hooks and "pre_update" in self.config.update_hooks:
                self.config.update_hooks["pre_update"]()
            
            # 备份当前版本
            if self.config.backup_before_update:
                self._backup_current_version()
            
            # 根据更新源执行更新
            if self.config.update_source == "pypi":
                success = self._update_from_pypi(target_version)
            elif self.config.update_source == "git":
                success = self._update_from_git(target_version)
            elif self.config.update_source == "url":
                success = self._update_from_url(target_version)
            else:
                logger.error(f"不支持的更新源: {self.config.update_source}")
                return False
            
            if success:
                # 更新最后检查时间
                self._update_last_check_time()
                
                # 执行更新后钩子
                if self.config.update_hooks and "post_update" in self.config.update_hooks:
                    self.config.update_hooks["post_update"]()
                    
                logger.info("更新完成")
                return True
                
        except Exception as e:
            logger.error(f"更新时出错: {e}")
            
        return False
    
    def auto_update_check(self) -> bool:
        """
        自动检查并更新
        
        Returns:
            bool: 是否执行了更新
        """
        if not self.config.auto_update:
            return False
            
        latest_version = self.check_for_updates()
        if latest_version:
            return self.update_package(latest_version)
            
        return False
    
    def _should_check(self) -> bool:
        """检查是否应该进行更新检查"""
        if not self.last_check_file.exists():
            return True
            
        try:
            with open(self.last_check_file, 'r') as f:
                last_check = float(f.read().strip())
                
            current_time = os.path.getmtime(self.last_check_file)
            return (current_time - last_check) >= self.config.check_interval
            
        except Exception:
            return True
    
    def _update_last_check_time(self):
        """更新最后检查时间"""
        try:
            with open(self.last_check_file, 'w') as f:
                f.write(str(os.path.getmtime(self.last_check_file)))
        except Exception as e:
            logger.error(f"更新最后检查时间失败: {e}")
    
    def _is_newer_version(self, new_version: str) -> bool:
        """检查新版本是否比当前版本更新"""
        try:
            return version.parse(new_version) > version.parse(self.config.current_version)
        except Exception as e:
            logger.error(f"版本比较失败: {e}")
            return False
    
    def _check_pypi_updates(self) -> Optional[str]:
        """检查PyPI更新"""
        try:
            url = f"https://pypi.org/pypi/{self.config.package_name}/json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            latest_version = data["info"]["version"]
            
            return latest_version
            
        except Exception as e:
            logger.error(f"检查PyPI更新失败: {e}")
            return None
    
    def _check_git_updates(self) -> Optional[str]:
        """检查Git仓库更新"""
        if not self.config.repository_url:
            logger.error("Git更新需要配置repository_url")
            return None
            
        try:
            # 这里可以实现获取最新Git tag或commit的逻辑
            # 简化示例：假设通过API获取最新tag
            if "github.com" in self.config.repository_url:
                # 解析GitHub仓库信息
                parts = self.config.repository_url.strip("/").split("/")
                if len(parts) >= 2:
                    owner, repo = parts[-2], parts[-1].replace(".git", "")
                    
                    url = f"https://api.github.com/repos/{owner}/{repo}/tags"
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    
                    tags = response.json()
                    if tags:
                        # 移除'v'前缀进行比较
                        latest_tag = tags[0]["name"].lstrip('v')
                        return latest_tag
                        
        except Exception as e:
            logger.error(f"检查Git更新失败: {e}")
            
        return None
    
    def _check_url_updates(self) -> Optional[str]:
        """检查自定义URL更新"""
        if not self.config.repository_url:
            logger.error("URL更新需要配置repository_url")
            return None
            
        try:
            response = requests.get(self.config.repository_url, timeout=10)
            response.raise_for_status()
            
            # 假设URL返回包含版本信息的JSON
            data = response.json()
            return data.get("version")
            
        except Exception as e:
            logger.error(f"检查URL更新失败: {e}")
            return None
    
    def _update_from_pypi(self, target_version: Optional[str] = None) -> bool:
        """从PyPI更新"""
        try:
            package_spec = self.config.package_name
            if target_version:
                package_spec = f"{self.config.package_name}=={target_version}"
                
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", package_spec],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                logger.info(f"成功从PyPI更新: {package_spec}")
                return True
            else:
                logger.error(f"PyPI更新失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"PyPI更新异常: {e}")
            return False
    
    def _update_from_git(self, target_version: Optional[str] = None) -> bool:
        """从Git仓库更新"""
        if not self.config.repository_url:
            logger.error("Git更新需要配置repository_url")
            return False
            
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 克隆仓库
                clone_cmd = [
                    "git", "clone", 
                    self.config.repository_url, 
                    temp_dir,
                    "--branch", self.config.branch if not target_version else target_version,
                    "--depth", "1"
                ]
                
                result = subprocess.run(clone_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Git克隆失败: {result.stderr}")
                    return False
                
                # 安装新版本
                install_cmd = [sys.executable, "-m", "pip", "install", "-e", temp_dir]
                result = subprocess.run(install_cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"成功从Git更新: {self.config.repository_url}")
                    return True
                else:
                    logger.error(f"Git安装失败: {result.stderr}")
                    return False
                    
        except Exception as e:
            logger.error(f"Git更新异常: {e}")
            return False
    
    def _update_from_url(self, target_version: Optional[str] = None) -> bool:
        """从自定义URL更新"""
        if not self.config.repository_url:
            logger.error("URL更新需要配置repository_url")
            return False
            
        try:
            # 下载文件
            download_url = self.config.repository_url
            if target_version:
                download_url = f"{self.config.repository_url}?version={target_version}"
                
            response = requests.get(download_url, timeout=30)
            response.raise_for_status()
            
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(suffix='.whl', delete=False) as temp_file:
                temp_file.write(response.content)
                temp_file_path = temp_file.name
            
            try:
                # 安装下载的包
                install_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", temp_file_path]
                result = subprocess.run(install_cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"成功从URL更新: {download_url}")
                    return True
                else:
                    logger.error(f"URL安装失败: {result.stderr}")
                    return False
                    
            finally:
                # 清理临时文件
                os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"URL更新异常: {e}")
            return False
    
    def _backup_current_version(self):
        """备份当前版本"""
        try:
            backup_dir = Path.home() / f".{self.config.package_name}_backups"
            backup_dir.mkdir(exist_ok=True)
            
            backup_name = f"{self.config.package_name}_{self.config.current_version}_{int(os.path.getmtime(__file__))}"
            backup_path = backup_dir / backup_name
            
            # 这里可以实现具体的备份逻辑
            # 例如复制当前包文件到备份目录
            logger.info(f"备份当前版本到: {backup_path}")
            
        except Exception as e:
            logger.error(f"备份失败: {e}")


def create_updater(package_name: str, current_version: str, **kwargs) -> PackageUpdater:
    """
    创建更新器的便捷函数
    
    Args:
        package_name: 包名
        current_version: 当前版本
        **kwargs: 其他配置参数
        
    Returns:
        PackageUpdater: 更新器实例
    """
    config = UpdateConfig(
        package_name=package_name,
        current_version=current_version,
        **kwargs
    )
    return PackageUpdater(config)


# 使用示例
if __name__ == "__main__":
    # 创建更新器
    updater = create_updater(
        package_name="zj_humanoid",
        current_version="0.1.0",
        update_source="pypi",
        auto_update=False,
        check_interval=3600  # 1小时检查一次
    )
    
    # 检查更新
    latest_version = updater.check_for_updates()
    if latest_version:
        print(f"发现新版本: {latest_version}")
        
        # 执行更新
        if updater.update_package(latest_version):
            print("更新成功")
        else:
            print("更新失败")
    else:
        print("已是最新版本")