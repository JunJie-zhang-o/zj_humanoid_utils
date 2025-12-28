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
#   4. 监控状态读取超时,超过15秒自动重启 robot_state.launch
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
    ROBOT_STATE_LAUNCH_CMD = ["roslaunch", "robot_state", "robot_state.launch", "--screen"]
    STARTUP_LAUNCH_CMD = ["roslaunch", "--screen", os.path.join(STARTUP_DIR, "robot_startUp.launch")]
    
    # 超时和检查间隔
    STATE_CHECK_TIMEOUT = 600  # 秒
    CHECK_INTERVAL = 1        # 秒
    INIT_WAIT_TIME = 5        # 秒
    
    # 新增: 状态读取超时重启配置
    STATE_READ_TIMEOUT = 15    # 连续读取失败超过15秒则重启
    MAX_RESTART_ATTEMPTS = 3   # 最大重启次数
    
    # 日志标识前缀
    LOG_PREFIX = "startup_manager.py"
    
    def __init__(self):
        """初始化启动管理器"""
        self.robot_state_process = None
        self.main_launch_process = None
        self.robot_name = os.getenv('ROBOT_NAME', 'zj_humanoid')
        self.state_topic = f"/{self.robot_name}/robot/robot_state"
        
        # 状态读取监控变量
        self.last_successful_read_time = None
        self.restart_count = 0
        
        # 确保必要的目录存在
        os.makedirs(self.LOG_DIR, exist_ok=True)
        
    def log(self, message, level="INFO"):
        """输出日志信息"""
        print(f"[{self.LOG_PREFIX}] [{level}] {message}", flush=True)

    def build_subprocess_env(self):
        """构造子进程环境，确保实时输出"""
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["ROSCONSOLE_STDOUT_LINE_BUFFERED"] = "1"
        return env

    def check_robot_state(self):
        """
        检查 robot_state 话题的 state 字段
        
        Returns:
            str: state 值 (如 '5'),如果获取失败返回 None
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
                output = result.stdout.strip()
                self.log(f"Retrieved from {self.state_topic}: {repr(output[:50])}...", "DEBUG")
                
                # 解析 "state: 5" 这一行
                for line in output.split('\n'):
                    if line.startswith('state:'):
                        state_value = line.split(':')[1].strip()
                        self.log(f"Parsed state value: {state_value}", "DEBUG")
                        # 更新成功读取时间
                        self.last_successful_read_time = time.time()
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
    
    def restart_robot_state_launch(self):
        """重启 robot_state.launch"""
        self.restart_count += 1
        
        if self.restart_count > self.MAX_RESTART_ATTEMPTS:
            self.log(f"Exceeded maximum restart attempts ({self.MAX_RESTART_ATTEMPTS})", "ERROR")
            return False
        
        self.log(f"Restarting robot_state.launch (attempt {self.restart_count}/{self.MAX_RESTART_ATTEMPTS})...", "WARN")
        
        # 终止现有进程
        if self.robot_state_process:
            try:
                self.log("Terminating existing robot_state.launch process...")
                self.robot_state_process.send_signal(signal.SIGINT)
                self.robot_state_process.wait(timeout=5)
                self.log("✓ Existing process terminated")
            except Exception as e:
                self.log(f"Error terminating process, forcing kill: {e}", "WARN")
                self.robot_state_process.kill()
                self.robot_state_process.wait()
        
        # 等待一段时间让资源释放
        time.sleep(2)
        
        # 重新启动
        success = self.start_robot_state_launch()
        if success:
            self.log(f"✓ robot_state.launch restarted successfully", "INFO")
            # 重置成功读取时间
            self.last_successful_read_time = time.time()
        else:
            self.log(f"✗ Failed to restart robot_state.launch", "ERROR")
        
        return success
    
    def check_state_read_timeout(self):
        """
        检查状态读取是否超时
        
        Returns:
            bool: True 表示超时需要重启, False 表示正常
        """
        if self.last_successful_read_time is None:
            # 首次运行,尚未成功读取过
            return False
        
        elapsed = time.time() - self.last_successful_read_time
        if elapsed > self.STATE_READ_TIMEOUT:
            self.log(f"State read timeout detected: {elapsed:.1f}s since last successful read", "WARN")
            return True
        
        return False
    
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
        consecutive_failures = 0
        max_consecutive_failures = 30  # 允许连续30次失败
        
        # 初始化成功读取时间
        self.last_successful_read_time = time.time()
        
        while time.time() - start_time < self.STATE_CHECK_TIMEOUT:
            # 检查是否需要重启 robot_state.launch
            if self.check_state_read_timeout():
                self.log("Triggering robot_state.launch restart due to read timeout...", "WARN")
                if not self.restart_robot_state_launch():
                    self.log("Failed to restart robot_state.launch, aborting", "ERROR")
                    return False
                
                # 重启后重置计数器
                consecutive_failures = 0
                start_time = time.time()  # 重置总超时计时
                continue
            
            state = self.check_robot_state()
            
            if state == target_state:
                self.log(f"✓ State reached {target_state}", "INFO")
                return True
            elif state is None:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    self.log(f"✗ Too many consecutive failures ({consecutive_failures}), will trigger restart", "WARN")
            else:
                consecutive_failures = 0  # 重置失败计数
                
            elapsed = int(time.time() - start_time)
            time_since_last_read = int(time.time() - self.last_successful_read_time) if self.last_successful_read_time else 0
            self.log(f"Current state: {state} (waiting {elapsed}/{self.STATE_CHECK_TIMEOUT}s, "
                    f"last read: {time_since_last_read}s ago)", "INFO")
            
            time.sleep(self.CHECK_INTERVAL)
        
        self.log(f"✗ Timeout waiting for state {target_state}", "ERROR")
        return False
    
    def start_robot_state_launch(self):
        """启动 robot_state.launch"""
        self.log("=" * 60)
        self.log("Starting robot_state.launch...")
        self.log("=" * 60)
        
        try:
            # 关键优化：不使用 PIPE，让子进程直接继承 stdout/stderr
            # 这样高频输出不会被 64KB 管道缓冲区阻塞
            self.robot_state_process = subprocess.Popen(
                self.ROBOT_STATE_LAUNCH_CMD,
                stdout=None,  # 继承父进程的 stdout
                stderr=None,  # 继承父进程的 stderr
                env=self.build_subprocess_env()
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
            # 关键优化：不使用 PIPE，让子进程直接继承 stdout/stderr
            self.main_launch_process = subprocess.Popen(
                self.STARTUP_LAUNCH_CMD,
                stdout=None,  # 继承父进程的 stdout
                stderr=None,  # 继承父进程的 stderr
                env=self.build_subprocess_env()
            )
            self.log(f"✓ robot_startUp.launch started (PID: {self.main_launch_process.pid})")
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
        if self.main_launch_process:
            self.log("Terminating robot_startUp.launch...")
            try:
                self.main_launch_process.send_signal(signal.SIGINT)
                self.main_launch_process.wait(timeout=5)
                self.log("✓ robot_startUp.launch terminated")
            except Exception as e:
                self.log(f"✗ Error terminating robot_startUp.launch: {e}", "ERROR")
                self.main_launch_process.kill()

    def run(self):
        """主运行流程"""
        try:
            # 1. 启动 robot_state.launch
            if not self.start_robot_state_launch():
                return 1
            
            # 2. 等待状态达到 5 (包含自动重启机制)
            if not self.wait_for_state(target_state='5'):
                self.log("Failed to reach target state, aborting startup", "ERROR")
                return 1
            
            # 3. 启动主 launch 文件
            if not self.start_main_launch():
                return 1

            self.log("=" * 60)
            self.log("✓ All launches started successfully!")
            self.log("=" * 60)
            
            # 保持运行，等待子进程
            self.log("Startup manager running. Press Ctrl+C to exit.")
            
            # 等待任一子进程退出
            while True:
                # 检查子进程状态
                if self.robot_state_process and self.robot_state_process.poll() is not None:
                    self.log(f"robot_state.launch exited with code {self.robot_state_process.returncode}", "WARN")
                    break
                if self.main_launch_process and self.main_launch_process.poll() is not None:
                    self.log(f"robot_startUp.launch exited with code {self.main_launch_process.returncode}", "WARN")
                    break
                time.sleep(1)
            
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