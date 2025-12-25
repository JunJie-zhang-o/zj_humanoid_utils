#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
################################################################################
# 文件: startup_manager.py
# 位置: /home/nav01/zj_humanoid/startup/startup_manager.py
# 说明: 机器人启动管理脚本
# 功能: 
#   1. 先启动 robot_state.launch
#   2. 检查 /robot_state/state 话题状态
#   3. 当 state==5 时启动 robot_startUp.launch
################################################################################
"""

import time
import subprocess
import signal
import os
import sys


class StartupManager:
    """机器人启动管理器"""
    
    # 配置路径
    WORKSPACE_ROOT = "/home/nav01/zj_humanoid"
    CONFIG_DIR = os.path.join(WORKSPACE_ROOT, "config")
    STARTUP_DIR = os.path.join(WORKSPACE_ROOT, "startup")
    LOG_DIR = os.path.join(WORKSPACE_ROOT, "logs")
    
    # Launch 命令
    ROBOT_STATE_LAUNCH_CMD = ["roslaunch", "robot_state", "robot_state.launch"]
    STARTUP_LAUNCH_CMD = ["roslaunch", os.path.join(STARTUP_DIR, "robot_startUp.launch")]
    
    # 超时和检查间隔
    STATE_CHECK_TIMEOUT = 600  # 秒
    CHECK_INTERVAL = 1        # 秒
    INIT_WAIT_TIME = 5        # 秒
    
    def __init__(self):
        """初始化启动管理器"""
        self.robot_state_process = None
        self.robot_name = os.getenv('ROBOT_NAME', 'zj_humanoid')
        self.state_topic = f"/{self.robot_name}/robot/robot_state"
        
        # 确保必要的目录存在
        os.makedirs(self.LOG_DIR, exist_ok=True)
        
    def log(self, message, level="INFO"):
        """输出日志信息"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        sys.stdout.flush()
        
    def check_robot_state(self):
        """
        检查 robot_state 话题的 state 字段
        
        Returns:
            str: state 值 (如 '5')，如果获取失败返回 None
        """
        try:
            result = subprocess.run(
                ["rostopic", "echo", "-n", "1", self.state_topic],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # 输出格式是:
                # state: 5
                # state_info: "STATE_ROBOT_RUN"
                # ---
                output = result.stdout.strip()
                self.log(f"Retrieved from {self.state_topic}: {repr(output[:50])}...", "DEBUG")
                
                # 解析 "state: 5" 这一行
                for line in output.split('\n'):
                    if line.startswith('state:'):
                        state_value = line.split(':')[1].strip()
                        self.log(f"Parsed state value: {state_value}", "DEBUG")
                        return state_value
                
                return None
            else:
                self.log(f"Failed to read {self.state_topic}: {result.stderr}", "WARN")
                return None
                
        except subprocess.TimeoutExpired:
            self.log(f"Timeout reading {self.state_topic}", "WARN")
            return None
        except Exception as e:
            self.log(f"Error checking {self.state_topic}: {e}", "ERROR")
            return None
    
    def wait_for_state(self, target_state='5'):
        """
        等待 robot_state 达到目标状态
        
        Args:
            target_state: 目标状态值
            
        Returns:
            bool: 是否在超时前达到目标状态
        """
        self.log(f"Waiting for {self.state_topic} to reach state {target_state}...")
        
        start_time = time.time()
        
        while time.time() - start_time < self.STATE_CHECK_TIMEOUT:
            state = self.check_robot_state()
            
            if state == target_state:
                self.log(f"✓ State reached {target_state}", "INFO")
                return True
            else:
                elapsed = int(time.time() - start_time)
                self.log(f"Current state: {state} (waiting {elapsed}/{self.STATE_CHECK_TIMEOUT}s)", "INFO")
                time.sleep(self.CHECK_INTERVAL)
        
        self.log(f"✗ Timeout waiting for state {target_state}", "ERROR")
        return False
    
    def start_robot_state_launch(self):
        """启动 robot_state.launch"""
        self.log("=" * 60)
        self.log("Starting robot_state.launch...")
        self.log("=" * 60)
        
        try:
            self.robot_state_process = subprocess.Popen(
                self.ROBOT_STATE_LAUNCH_CMD,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.log(f"✓ robot_state.launch started (PID: {self.robot_state_process.pid})")
            
            # 等待 topic 初始化
            self.log(f"Waiting {self.INIT_WAIT_TIME}s for topics to initialize...")
            time.sleep(self.INIT_WAIT_TIME)
            
            return True
            
        except Exception as e:
            self.log(f"✗ Failed to start robot_state.launch: {e}", "ERROR")
            return False
    
    def start_main_launch(self):
        """启动主 launch 文件"""
        self.log("=" * 60)
        self.log("Starting robot_startUp.launch...")
        self.log("=" * 60)
        
        try:
            # 使用 Popen 以便主进程可以持续运行
            subprocess.Popen(self.STARTUP_LAUNCH_CMD)
            self.log("✓ robot_startUp.launch started successfully")
            return True
            
        except Exception as e:
            self.log(f"✗ Failed to start robot_startUp.launch: {e}", "ERROR")
            return False
    
    def cleanup(self):
        """清理资源"""
        if self.robot_state_process:
            self.log("Terminating robot_state.launch...")
            try:
                self.robot_state_process.send_signal(signal.SIGINT)
                self.robot_state_process.wait(timeout=5)
                self.log("✓ robot_state.launch terminated")
            except Exception as e:
                self.log(f"✗ Error terminating robot_state.launch: {e}", "ERROR")
                self.robot_state_process.kill()
    
    def run(self):
        """主运行流程"""
        try:
            # 1. 启动 robot_state.launch
            if not self.start_robot_state_launch():
                return 1
            
            # 2. 等待状态达到 5
            if not self.wait_for_state(target_state='5'):
                self.log("Failed to reach target state, aborting startup", "ERROR")
                return 1
            
            # 3. 启动主 launch 文件
            if not self.start_main_launch():
                return 1
            
            self.log("=" * 60)
            self.log("✓ All launches started successfully!")
            self.log("=" * 60)
            
            # 保持运行
            self.log("Startup manager running. Press Ctrl+C to exit.")
            signal.pause()
            
            return 0
            
        except KeyboardInterrupt:
            self.log("Received interrupt signal", "INFO")
            return 0
        except Exception as e:
            self.log(f"Unexpected error: {e}", "ERROR")
            return 1
        finally:
            self.cleanup()


def main():
    """主入口函数"""
    manager = StartupManager()
    sys.exit(manager.run())


if __name__ == "__main__":
    main()