def start_robot_state_launch(self):
    """启动 robot_state.launch"""
    self.log("=" * 60)
    self.log("Starting robot_state.launch...")
    self.log("=" * 60)
    
    try:
        # 修改这里：继承父进程的 stdout 和 stderr
        self.robot_state_process = subprocess.Popen(
            self.ROBOT_STATE_LAUNCH_CMD,
            stdout=sys.stdout,
            stderr=sys.stderr
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
        # 修改这里：继承父进程的 stdout 和 stderr
        subprocess.Popen(
            self.STARTUP_LAUNCH_CMD,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        self.log("✓ robot_startUp.launch started successfully")
        return True
        
    except Exception as e:
        self.log(f"✗ Failed to start robot_startUp.launch: {e}", "ERROR")
        return False