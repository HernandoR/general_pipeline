"""子进程执行工具模块"""
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from general_pipeline.utils.log_utils import get_logger

logger = get_logger()


def run_cmd(
    command: str | List[str],
    cwd: Optional[Path | str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None,
    capture_output: bool = True,
    shell: bool = False,
    check: bool = False,
) -> Tuple[int, str, str]:
    """
    通用命令执行函数
    
    :param command: 要执行的命令（字符串或列表）
    :param cwd: 工作目录
    :param env: 环境变量
    :param timeout: 超时时间（秒）
    :param capture_output: 是否捕获输出
    :param shell: 是否使用shell执行
    :param check: 是否检查返回码并在非零时抛出异常
    :return: (exit_code, stdout, stderr)
    """
    # 准备环境变量
    exec_env = os.environ.copy()
    if env:
        exec_env.update(env)
    
    try:
        if capture_output:
            result = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                env=exec_env,
                capture_output=True,
                text=True,
                shell=shell,
                timeout=timeout,
                check=check
            )
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                env=exec_env,
                shell=shell,
                timeout=timeout,
                check=check
            )
            return result.returncode, "", ""
    except subprocess.TimeoutExpired as e:
        logger.error(f"命令执行超时: {command}")
        return -1, str(e.stdout) if e.stdout else "", str(e.stderr) if e.stderr else ""
    except subprocess.CalledProcessError as e:
        logger.error(f"命令执行失败: {command}, exit_code={e.returncode}")
        return e.returncode, e.stdout if e.stdout else "", e.stderr if e.stderr else ""
    except Exception as e:
        logger.error(f"命令执行异常: {command}, error={e}")
        return -1, "", str(e)


def run_cmd_stream(
    command: str,
    cwd: Optional[Path | str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None,
    shell: bool = True,
    on_output: Optional[callable] = None,
) -> int:
    """
    流式执行命令并实时输出
    
    :param command: 要执行的命令
    :param cwd: 工作目录
    :param env: 环境变量
    :param timeout: 超时时间（秒）
    :param shell: 是否使用shell执行
    :param on_output: 输出回调函数，接收每行输出
    :return: exit_code
    """
    # 准备环境变量
    exec_env = os.environ.copy()
    if env:
        exec_env.update(env)
    
    try:
        process = subprocess.Popen(
            command,
            shell=shell,
            cwd=str(cwd) if cwd else None,
            env=exec_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        start_time = time.time()
        
        # 实时读取输出
        while True:
            # 检查进程是否结束
            retcode = process.poll()
            if retcode is not None:
                break
            
            # 检查超时
            if timeout and (time.time() - start_time) > timeout:
                logger.error(f"命令执行超时（{timeout}秒），强制终止")
                process.send_signal(signal.SIGTERM)
                time.sleep(5)
                if process.poll() is None:
                    process.kill()
                return -1
            
            # 读取输出
            line = process.stdout.readline()
            if line:
                if on_output:
                    on_output(line.rstrip())
        
        # 读取剩余输出
        for line in process.stdout:
            if on_output:
                on_output(line.rstrip())
        
        return process.returncode
        
    except Exception as e:
        logger.error(f"流式命令执行异常: {command}, error={e}")
        return -1
