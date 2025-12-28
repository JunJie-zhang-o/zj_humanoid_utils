



import re
from pathlib import Path


PROJECT_PATH = Path(__file__).resolve().parent.parent

def get_version():
    version_file = PROJECT_PATH / 'src/zjh_utils/__init__.py'
    with open(version_file, 'r') as f:
        version_content = f.read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_content, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

def format_version(context=None):
    if context:
        print(context, "args=======")
    base_version = get_version()
    try:
        dynamic_version = f"{base_version}.dev{context.distance}+{context.branch}.{context.node[1:]}"
        return dynamic_version
    except Exception as e:
        print("Error generating dynamic version:", e)
        return base_version