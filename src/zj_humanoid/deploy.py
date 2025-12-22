


from dataclasses import dataclass, field
from typing import List, Optional

from dataclasses_json import dataclass_json



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
    url:str
    path:str


@dataclass_json
@dataclass
class PICO:
    sys_env_version: Optional[str]
    build_time: Optional[str]
    branch_name: Optional[str]
    commit_id: Optional[str]
    modules:List[Module] = field(default_factory=list)
    resources: List[Resource] = field(default_factory=list)