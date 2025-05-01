import subprocess

from agentmode.logs import logger

def install_dependencies(package_names: list) -> bool:
    """Install a list of Python packages using 'uv add'.

    Args:
        package_names (list): A list of package names to install.

    Returns:
        bool: True if all packages were installed successfully, False otherwise.
    """
    for package_name in package_names:
        try:
            result = subprocess.run(
                ["uv", "add", package_name],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            # log stdout and stderr
            logger.info(f"uv logs: {result.stdout.decode()}")
            if result.stderr:
                logger.error(f"uv stderr logs: {result.stderr.decode()}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install {package_name}", exc_info=True)
            return False
    return True
